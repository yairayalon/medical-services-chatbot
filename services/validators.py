import re

DIGITS_9 = re.compile(r"^\d{9}$")
AGE = re.compile(r"^(?:1[01]\d|[1-9]?\d|120)$")  # 0-120 inclusive
HMO_CANON = {"מכבי": "מכבי", "מאוחדת": "מאוחדת", "כללית": "כללית",
             "maccabi": "מכבי", "clalit": "כללית", "meuhedet": "מאוחדת"}
TIER_CANON = {"זהב": "זהב", "כסף": "כסף", "ארד": "ארד",
              "gold": "זהב", "silver": "כסף", "bronze": "ארד"}

def normalize_hmo(s: str) -> str | None:
    s = (s or "").strip().lower()
    return HMO_CANON.get(s)

def normalize_tier(s: str) -> str | None:
    s = (s or "").strip().lower()
    return TIER_CANON.get(s)

def is_valid_id(s: str) -> bool:
    return bool(DIGITS_9.match((s or "").strip()))

def is_valid_age(s: str | int) -> bool:
    try:
        v = int(s)
    except Exception:
        return False
    return 0 <= v <= 120

def validate_profile(p: dict) -> dict:
    """Return dict of {field: error} for invalids."""
    errors = {}
    if "id" in p and p["id"] and not is_valid_id(p["id"]):
        errors["id"] = "ID must be 9 digits."
    if "age" in p and p["age"] not in (None, "") and not is_valid_age(p["age"]):
        errors["age"] = "Age must be between 0 and 120."
    if "hmo" in p and p["hmo"]:
        h = normalize_hmo(p["hmo"])
        if not h:
            errors["hmo"] = "Unknown HMO."
        else:
            p["hmo"] = h
    if "hmo_card" in p and p["hmo_card"] and not is_valid_id(p["hmo_card"]):
        errors["hmo_card"] = "HMO card must be 9 digits."
    if "tier" in p and p["tier"]:
        t = normalize_tier(p["tier"])
        if not t:
            errors["tier"] = "Unknown tier."
        else:
            p["tier"] = t
    return errors
