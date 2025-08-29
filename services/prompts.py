from typing import List, Dict, Any

MISSING_FIELDS_ORDER = ["first_name", "last_name", "id", "gender", "age", "hmo", "hmo_card", "tier"]

def build_collection_system(lang: str = "he") -> str:
    he = (
        "אתה סוכן איסוף מידע. נהל שיחה קצרה כדי לאסוף: שם פרטי, שם משפחה, מספר זהות (9 ספרות), "
        "מין, גיל (0–120), קופת חולים (מכבי/מאוחדת/כללית), מספר כרטיס קופה (9 ספרות), ורמת חברות (זהב/כסף/ארד). "
        "שאל רק את מה שחסר או לא תקין. אם ערך לא תקין – הסבר בקצרה ובקש שוב. "
        "כאשר הכול תקין, הצג 'כרטיס אישור' ושאל האם לאשר. "
        "**חשוב**: לאחר שהמשתמש מאשר במפורש, **אל תדפיס JSON למשתמש**; במקום זאת קרא לכלי submit_profile עם הערכים."
    )
    en = (
        "You are an information-collection assistant. Collect: first name, last name, ID (9 digits), gender, age (0–120), "
        "HMO (Maccabi/Meuhedet/Clalit), HMO card (9 digits), and tier (Gold/Silver/Bronze). "
        "Ask only for missing/invalid fields. When everything looks valid, show a confirmation card and ask to confirm. "
        "**Important**: after explicit user confirmation, **do not print JSON**; instead call the submit_profile tool with the values."
    )
    return he if lang == "he" else en

FEW_SHOT_COLLECTION: List[Dict[str, Any]] = [
    {"role": "user", "content": "שלום"},
    {"role": "assistant", "content": "שלום! כדי להתחיל, מה שמך הפרטי ושם המשפחה?"},
    {"role": "user", "content": "נועה לוי"},
    {"role": "assistant", "content": "תודה נועה לוי. מה מספר תעודת הזהות שלך (9 ספרות)?"},
    {"role": "user", "content": "נכונים"},
    {"role": "assistant", "content": "נהדר! אאשר ואעדכן את הפרופיל."}
]

def build_collection_messages(user_messages: List[Dict[str, str]], profile: Dict[str, Any], validation_errors: Dict[str, str], lang="he"):
    sys = {"role": "system", "content": build_collection_system(lang)}
    few = FEW_SHOT_COLLECTION if lang == "he" else [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hi! What's your first and last name?"},
        {"role": "user", "content": "Confirmed"},
        {"role": "assistant", "content": "Great—I'll confirm and update your profile."}
    ]
    context = {
        "role": "system",
        "content": (
            f"Known profile fields: { {k: v for k, v in profile.items() if v} }.\n"
            f"Validation errors (if any): {validation_errors}.\n"
            f"Ask only for missing/invalid fields in this order: {MISSING_FIELDS_ORDER}.\n"
            f"Never print tool arguments or JSON to the user."
        )
    }
    return [sys] + few + [context] + user_messages

def build_qa_system(lang: str = "he") -> str:
    he = (
        "אתה עוזר מומחה לשירותים רפואיים. ענה אך ורק מקטעי הידע שסופקו. "
        "אם המשתמש לא ציין קופה/רמה, הנח אותם מהפרופיל. "
        "אם השאלה כללית, סכם תתי־שירותים רלוונטיים. "
        "אל תשתמש במונח 'ברונזה'; אמור 'ארד' בלבד."
    )
    en = (
        "You are a medical-services expert. Answer strictly from the provided snippets. "
        "If HMO/Tier are omitted, assume them from the profile. "
        "For broad questions, summarize key sub-services. "
        "Do not use the term 'Bronze' in Hebrew; use 'ארד' for Hebrew output."
    )
    return he if lang == "he" else en

def build_qa_messages(user_messages: List[Dict[str, str]], lang: str, snippets: List[Dict[str, Any]], profile: Dict[str, Any] | None):
    sys = {"role": "system", "content": build_qa_system(lang)}
    profile_line = {"role": "system", "content": f"User profile (defaults): HMO={profile.get('hmo') if profile else ''}, Tier={profile.get('tier') if profile else ''}."}
    ground = {"role": "system", "content": f"Grounding snippets:\n{snippets}"}
    return [sys, profile_line, ground] + user_messages
