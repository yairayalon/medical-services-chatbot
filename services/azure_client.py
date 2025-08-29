import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class AzureOpenAIClient:
    def __init__(self):
        self.endpoint = self._sanitize_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT"))
        self.key = os.getenv("AZURE_OPENAI_KEY")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
        if not (self.endpoint and self.key and self.deployment):
            raise RuntimeError("Azure OpenAI chat env vars missing")
        self.api_version = "2024-06-01"

    def _sanitize_endpoint(self, ep: str | None) -> str | None:
        if not ep:
            return ep
        i = ep.find("/openai")
        if i != -1:
            ep = ep[:i]
        return ep.rstrip("/")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    def chat(self, messages, temperature=0.2, max_tokens=500):
        """Simple convenience (no tools)."""
        data = self.chat_api(messages, temperature=temperature, max_tokens=max_tokens)
        return data["choices"][0]["message"].get("content", "")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    def chat_api(self, messages, temperature=0.2, max_tokens=500, tools=None, tool_choice=None, response_format=None):
        """Full access to Azure Chat Completions (incl. tool calls). Returns raw JSON."""
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
        headers = {"api-key": self.key, "Content-Type": "application/json"}
        payload = {
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice  # "auto" | {"type":"function","function":{"name":"..."}}
        if response_format:
            payload["response_format"] = response_format
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()
