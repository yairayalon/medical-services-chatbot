from typing import List, Dict, Any, Tuple
import json
from services.azure_client import AzureOpenAIClient
from services.validators import validate_profile
from services.prompts import build_collection_messages, build_qa_messages
from services.hybrid_retriever import HybridRetriever
from utils.i18n import detect_lang

class ChatRouter:
    def __init__(self, data_dir: str, index_path: str):
        self.data_dir = data_dir
        self.index_path = index_path
        self.chat = AzureOpenAIClient()
        self.retriever = HybridRetriever(index_path=index_path)
        self.kb_loaded = False

    def boot(self):
        self.retriever.boot()
        self.kb_loaded = True

    def _submit_profile_tool(self):
        """Azure tool/function schema for finalizing the user profile."""
        return [{
            "type": "function",
            "function": {
                "name": "submit_profile",
                "description": "Finalize the user profile after explicit user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "id": {"type": "string", "description": "9 digits"},
                        "gender": {"type": "string"},
                        "age": {"type": "integer"},
                        "hmo": {"type": "string", "enum": ["מכבי","מאוחדת","כללית","Maccabi","Meuhedet","Clalit"]},
                        "hmo_card": {"type": "string", "description": "9 digits"},
                        "tier": {"type": "string", "enum": ["זהב","כסף","ארד","Gold","Silver","Bronze"]},
                    },
                    "required": ["first_name","last_name","id","gender","age","hmo","hmo_card","tier"],
                    "additionalProperties": False
                }
            }
        }]

    # ---------- Phase A: collection ----------
    def collect_user_info(self, messages: List[Dict[str, str]], language_hint: str | None, user_profile: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        lang = language_hint or detect_lang(messages)
        profile = dict(user_profile)

        llm_messages = build_collection_messages(messages, profile, {}, lang="he" if lang == "he" else "en")
        tools = self._submit_profile_tool()

        # Call with tools; let model decide when to call submit_profile (after explicit confirmation)
        data = self.chat.chat_api(
            messages=llm_messages,
            temperature=0.2,
            max_tokens=600,
            tools=tools,
            tool_choice="auto"
        )
        choice = data["choices"][0]["message"]
        tool_calls = choice.get("tool_calls") or []
        content = (choice.get("content") or "").strip()
        profile_confirmed = False

        if tool_calls:
            # Consume the submit_profile call and update profile
            for call in tool_calls:
                if call.get("type") == "function" and call["function"]["name"] == "submit_profile":
                    try:
                        args = json.loads(call["function"]["arguments"])
                    except Exception:
                        args = {}
                    keep = ["first_name","last_name","id","gender","age","hmo","hmo_card","tier"]
                    for k in keep:
                        if args.get(k) not in (None, "", []):
                            profile[k] = args[k]
                    # Normalize & validate (also normalizes HMO/Tier labels)
                    _ = validate_profile(profile)
                    profile_confirmed = True

            # If the model only returned a tool call with no user-visible text,
            # produce a short, clean confirmation message.
            if not content:
                content = "✅ הפרופיל אושר. אפשר לשאול שאלות על ההטבות לפי הקופה והרמה שלך."

        # Never show tool arguments/JSON to the user
        assistant_visible = content

        return assistant_visible, profile, profile_confirmed

    # ---------- Phase B: Q&A ----------
    def answer_question(self, messages: List[Dict[str, str]], user_profile: Dict[str, Any], language_hint: str | None) -> Tuple[str, List[Dict[str, Any]]]:
        if not self.kb_loaded:
            raise RuntimeError("KB not initialized")
        lang = language_hint or detect_lang(messages)

        # Query = last user message
        user_texts = [m["content"] for m in messages if m["role"] == "user"]
        if not user_texts:
            raise ValueError("No user query found.")
        query = user_texts[-1]

        hmo = user_profile.get("hmo")
        tier = user_profile.get("tier")

        snippets = self.retriever.search(query=query, hmo=hmo, tier=tier, top_k=5)
        if not snippets:
            empty_answer = "לא מצאתי התאמה במאגר שסיפקת. אפשר לנסח אחרת או לבחור קטגוריה אחרת?" if lang == "he" else \
                           "I couldn’t find a match in the provided knowledge base. Please rephrase or choose another category."
            return empty_answer, []

        llm_messages = build_qa_messages(messages, lang=("he" if lang == "he" else "en"), snippets=snippets, profile=user_profile)
        answer = self.chat.chat(llm_messages, temperature=0.0, max_tokens=700)
        return answer, snippets
