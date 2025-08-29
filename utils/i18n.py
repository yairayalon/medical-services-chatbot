from typing import List, Dict

def detect_lang(messages: List[Dict[str, str]]) -> str:
    """Very lightweight heuristic: Hebrew if any Hebrew letter in last user msg; else English."""
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    if not user_msgs:
        return "he"
    last = user_msgs[-1]
    for ch in last:
        if "\u0590" <= ch <= "\u05FF":
            return "he"
    return "en"
