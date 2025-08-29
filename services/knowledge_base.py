from bs4 import BeautifulSoup, Tag
from pathlib import Path
from typing import List, Dict, Any
import re

# Canonical HMO names (Hebrew), with loose aliases
_HMO_ALIASES = {
    "מכבי": ["מכבי", "maccabi"],
    "מאוחדת": ["מאוחדת", "meuhedet"],
    "כללית": ["כללית", "clalit"],
}
_HMO_CANON_BY_TOKEN = {tok.lower(): canon for canon, toks in _HMO_ALIASES.items() for tok in toks}

# Map filenames to a clean category label
_FILE_CATEGORY_MAP = {
    "optometry_services.html": "אופטומטריה",
    "communication_clinic_services.html": "מרפאות תקשורת",
    "dentel_services.html": "מרפאות שיניים",   # file name is intentionally misspelled ("dentel")
    "alternative_services.html": "רפואה משלימה",
    "pragrency_services.html": "שירותי הריון",  # file name has a typo ("pragrency")
    "workshops_services.html": "סדנאות בריאות",
}

_TIER_ALIASES = {
    "זהב": ["זהב", "gold"],
    "כסף": ["כסף", "silver"],
    "ארד": ["ארד", "bronze"],
}
_TIER_CANON_BY_TOKEN = {tok.lower(): canon for canon, toks in _TIER_ALIASES.items() for tok in toks}

def _clean_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _canon_hmo_from_text(s: str) -> str | None:
    s = (s or "").lower()
    for tok, canon in _HMO_CANON_BY_TOKEN.items():
        if tok in s:
            return canon
    return None

def _explode_tiers(text: str) -> List[Dict[str, str]]:
    """
    Find segments like:
      'זהב: ... כסף: ... ארד: ...'
    Return [{'tier':'זהב','text':'...'}, ...]
    Works with English labels (Gold/Silver/Bronze) too.
    """
    if not text:
        return []

    # Build a regex that finds any tier label followed by colon
    label_group = "|".join(re.escape(t) for toks in _TIER_ALIASES.values() for t in toks)
    pat = re.compile(rf"(?P<label>{label_group})\s*:\s*", flags=re.IGNORECASE)

    chunks: List[Dict[str, str]] = []
    matches = list(pat.finditer(text))
    if not matches:
        # No explicit tier labels -> single chunk with unknown tier
        return [{"tier": "", "text": _clean_text(text)}]

    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw = text[start:end]
        tier_tok = m.group("label").lower()
        tier = _TIER_CANON_BY_TOKEN.get(tier_tok, "")
        if _clean_text(raw):
            chunks.append({"tier": tier, "text": _clean_text(raw)})

    # Deduplicate identical tier texts within the same row
    seen = set()
    uniq = []
    for c in chunks:
        key = (c["tier"], c["text"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return uniq if uniq else [{"tier": "", "text": _clean_text(text)}]

def _nearest_hmo_heading(node: Tag) -> str | None:
    """
    Walk up/siblings to find the nearest heading or bold text that contains an HMO token.
    """
    # Check this node's previous siblings
    cur = node
    while cur and isinstance(cur, Tag):
        # Look at previous siblings first
        sib = cur.previous_sibling
        while sib:
            if isinstance(sib, Tag):
                txt = _clean_text(sib.get_text(" "))
                h = _canon_hmo_from_text(txt)
                if h:
                    return h
                # Also search within the sibling for bold/headings
                for cand in sib.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
                    h2 = _canon_hmo_from_text(cand.get_text(" "))
                    if h2:
                        return h2
            sib = sib.previous_sibling
        # Move up to parent and repeat
        cur = cur.parent
        if cur and isinstance(cur, Tag):
            txt = _clean_text(cur.get_text(" "))
            h = _canon_hmo_from_text(txt)
            if h:
                return h
    return None

def _category_from_file(p: Path, soup: BeautifulSoup) -> str:
    if p.name in _FILE_CATEGORY_MAP:
        return _FILE_CATEGORY_MAP[p.name]
    # fallback to title or stem
    title = soup.title.text if soup.title else ""
    return _clean_text(title or p.stem.replace("_", " "))

def parse_html_file(p: Path) -> List[Dict[str, str]]:
    """
    Parse the provided HTML into atomic benefit rows:
      {
        "category": "...",
        "service": "...",
        "hmo": "מכבי|מאוחדת|כללית",
        "tier": "זהב|כסף|ארד|''",
        "text": "benefit text",
        "source": "filename.html"
      }
    """
    html = p.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")
    category = _category_from_file(p, soup)
    rows: List[Dict[str, str]] = []

    tables = soup.find_all("table")
    for t in tables:
        # --- detect column headers (HMO names are in THs) ---
        header_ths = []
        first_tr = t.find("tr")
        if first_tr:
            header_ths = [ _clean_text(th.get_text(" ")) for th in first_tr.find_all("th") ]

        # Build a column index -> HMO map (col 0 is service name)
        col_hmo: Dict[int, str] = {}
        if header_ths and len(header_ths) >= 2:
            for j, htxt in enumerate(header_ths[1:], start=1):
                hcanon = _canon_hmo_from_text(htxt)  # "מכבי"/"מאוחדת"/"כללית" if present
                if hcanon:
                    col_hmo[j] = hcanon

        # Iterate TRs; skip the header TR with THs
        trs = t.find_all("tr")
        for tr in trs:
            # If this row is the header (mostly THs), skip
            if tr.find_all("th") and not tr.find_all("td"):
                continue

            tds = tr.find_all("td")
            if not tds:
                continue

            service = _clean_text(tds[0].get_text(" "))
            if not service:
                service = category

            # If we have column HMOs, create one record per HMO column
            if col_hmo:
                for j in range(1, len(tds)):
                    body = _clean_text(tds[j].get_text(" "))
                    hmo = col_hmo.get(j, "")
                    if not body:
                        continue
                    parts = _explode_tiers(body)
                    for part in parts:
                        rows.append({
                            "category": category,
                            "service": service,
                            "hmo": hmo or "",
                            "tier": part["tier"],
                            "text": part["text"],
                            "source": p.name
                        })
            else:
                # Fallback: no header HMOs detected → single combined body as before
                body = _clean_text(" ".join(td.get_text(" ") for td in tds[1:])) if len(tds) > 1 else ""
                # Try to detect HMO inside the row or the nearest heading
                row_hmo = _canon_hmo_from_text(body) or _nearest_hmo_heading(tr) or ""
                parts = _explode_tiers(body)
                for part in parts:
                    rows.append({
                        "category": category,
                        "service": service,
                        "hmo": row_hmo,
                        "tier": part["tier"],
                        "text": part["text"],
                        "source": p.name
                    })

    # --- Fallback parse for non-table content (optional; keep as-is if you had it) ---
    if not tables:
        current_hmo: str | None = None
        for el in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b", "p", "li"]):
            txt = _clean_text(el.get_text(" "))
            h = _canon_hmo_from_text(txt)
            if h:
                current_hmo = h
                continue
            if el.name in {"p", "li"} and txt:
                if ":" in txt:
                    svc, det = txt.split(":", 1)
                else:
                    svc, det = category, txt
                for part in _explode_tiers(det):
                    rows.append({
                        "category": category,
                        "service": _clean_text(svc),
                        "hmo": current_hmo or "",
                        "tier": part["tier"],
                        "text": part["text"],
                        "source": p.name
                    })

    # Deduplicate
    uniq = {
        (r["category"], r["service"], r["hmo"], r["tier"], r["text"], r["source"]): r
        for r in rows
        if r["text"]  # drop empties
    }
    return list(uniq.values())


def load_kb(dir_path: str | Path) -> List[Dict[str, str]]:
    dirp = Path(dir_path)
    assert dirp.exists(), f"KB dir not found: {dirp}"
    out: List[Dict[str, str]] = []
    for f in dirp.glob("*.html"):
        out.extend(parse_html_file(f))
    return out
