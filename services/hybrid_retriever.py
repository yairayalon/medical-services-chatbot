from typing import List, Dict, Any
from rapidfuzz import fuzz
import numpy as np
from pathlib import Path
import json
from services.embedding_client import AzureEmbeddingClient

def _norm(s: str) -> str:
    return (s or "").strip().lower()

def cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return a @ b.T

# Query keywords → restrict to these source files (category gating)
_QUERY_SOURCE_HINTS = {
    # Dental
    "שיניים": ["dentel_services.html"], "שן": ["dentel_services.html"],
    "dental": ["dentel_services.html"], "dent": ["dentel_services.html"],

    # Optometry
    "אופטומטר": ["optometry_services.html"], "עדשות": ["optometry_services.html"], "משקפ": ["optometry_services.html"],
    "ראיה": ["optometry_services.html"], "ראייה": ["optometry_services.html"], "laser": ["optometry_services.html"],
    "optometry": ["optometry_services.html"], "lenses": ["optometry_services.html"],

    # Alternative medicine
    "דיקור": ["alternative_services.html"], "אקופונקטורה": ["alternative_services.html"],
    "שיאצו": ["alternative_services.html"], "רפואה משלימה": ["alternative_services.html"],
    "acupuncture": ["alternative_services.html"], "complementary": ["alternative_services.html"],

    # Communication clinic
    "תקשורת": ["communication_clinic_services.html"], "גמגום": ["communication_clinic_services.html"],
    "בליעה": ["communication_clinic_services.html"], "speech": ["communication_clinic_services.html"],

    # Pregnancy
    "הריון": ["pragrency_services.html"], "סקירה": ["pragrency_services.html"], "prenatal": ["pragrency_services.html"],
    "pregnan": ["pragrency_services.html"],

    # Workshops
    "סדנא": ["workshops_services.html"], "סדנאות": ["workshops_services.html"],
    "עישון": ["workshops_services.html"], "wellness": ["workshops_services.html"], "workshop": ["workshops_services.html"],
}

# Light synonyms to help keyword gating
_SERVICE_SYNONYMS = [
    "עדשות", "contact lens", "contact lenses", "lenses",
    "טיפולי שיניים", "מרפאות שיניים", "טיפול שיניים", "dental", "dentistry", "tooth", "teeth",
    "לייזר", "laser", "vision correction",
]

class HybridRetriever:
    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.meta: List[Dict[str, Any]] = []
        self.X: np.ndarray | None = None
        self.embedder = None  # lazy

    def boot(self):
        if not self.index_path.exists():
            raise RuntimeError(f"KB index not found at {self.index_path}. Run scripts/build_kb_index.py")
        data = np.load(self.index_path, allow_pickle=True)
        self.X = data["X"]
        self.meta = json.loads(data["meta"].item())  # stored as JSON string

    def _ensure_embedder(self):
        if self.embedder is None:
            self.embedder = AzureEmbeddingClient()

    def _allowed_sources_for_query(self, q: str) -> set[str]:
        ql = _norm(q)
        allowed: set[str] = set()
        for key, files in _QUERY_SOURCE_HINTS.items():
            if key in ql:
                allowed.update(files)
        return allowed

    def _keyword_filter(self, q: str, allowed_sources: set[str], k: int = 200) -> List[int]:
        """
        Fuzzy prefilter by 'service' with optional source gating.
        """
        ql = _norm(q)
        services = [m["service"] for m in self.meta]
        scored = []
        for idx, svc in enumerate(services):
            if allowed_sources and self.meta[idx]["source"] not in allowed_sources:
                continue
            score = max(
                fuzz.WRatio(ql, _norm(svc)),
                max((fuzz.WRatio(_norm(syn), _norm(svc)) for syn in _SERVICE_SYNONYMS), default=0),
            )
            scored.append((idx, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [i for (i, _) in scored[:k]] or list(range(len(self.meta)))

    def search(self, query: str, hmo: str | None, tier: str | None,
               top_k: int = 10) -> List[Dict[str, Any]]:
        allowed_sources = self._allowed_sources_for_query(query)

        # 1) keyword prefilter (with category gating)
        cand_idx = self._keyword_filter(query, allowed_sources, k=200)

        # (optional) widen: ensure all exact HMO+Tier rows are included
        if hmo and tier:
            tier_pool = [
                i for i, m in enumerate(self.meta)
                if (not allowed_sources or self.meta[i][
                    "source"] in allowed_sources)
                   and m.get("hmo") == hmo
                   and m.get("tier") == tier
            ]
            if tier_pool:
                cand_idx = list(set(cand_idx) | set(tier_pool))

        # 2) prefer HMO and 3) prefer Tier (soft fallbacks)
        if hmo:
            hmo_only = [i for i in cand_idx if self.meta[i].get("hmo") == hmo]
            if hmo_only:
                cand_idx = hmo_only
        if tier:
            tier_only = [i for i in cand_idx if
                         self.meta[i].get("tier") == tier]
            if tier_only:
                cand_idx = tier_only

        # Safety
        if not cand_idx:
            cand_idx = list(range(len(self.meta)))

        # >>> INSERT BACKFILL BLOCK *HERE* (before semantic re-rank) <<<
        # If there are no exact HMO+Tier items in candidates, union all same-HMO items (any tier),
        # respecting allowed_sources if present. This helps broad queries.
        if hmo and tier:
            exact = [i for i in cand_idx
                     if self.meta[i].get("hmo") == hmo and self.meta[i].get(
                    "tier") == tier]
            if not exact:
                same_hmo = [i for i in range(len(self.meta)) if
                            self.meta[i].get("hmo") == hmo]
                if allowed_sources:
                    same_hmo = [i for i in same_hmo if
                                self.meta[i]["source"] in allowed_sources]
                cand_idx = list(set(cand_idx) | set(same_hmo))
        # >>> END BACKFILL BLOCK <<<

        # 4) semantic re-rank
        self._ensure_embedder()
        qtext = query + (f" HMO:{hmo}" if hmo else "") + (
            f" Tier:{tier}" if tier else "")
        qvec = self.embedder.embed(qtext)[0]
        Xc = self.X[cand_idx]
        sims = cosine_sim(Xc, qvec.reshape(1, -1)).ravel()

        # 6) small boosts on exact matches (secondary to hard widening above)
        boosts = np.ones_like(sims)
        for i, mi in enumerate(cand_idx):
            meta = self.meta[mi]
            if hmo and meta.get("hmo") == hmo:
                boosts[i] *= 1.15
            if tier and meta.get("tier") == tier:
                boosts[i] *= 1.10
        score = sims * boosts

        # 7) top-k with diversity by (service,hmo,tier)
        top_idx = np.argsort(-score)[:max(top_k * 2, 10)]
        results, seen = [], set()
        for i in top_idx:
            mi = cand_idx[i]
            m = self.meta[mi]
            key = (m.get("service", ""), m.get("hmo", ""), m.get("tier", ""))
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "score": float(score[i]),
                "category": m.get("category", ""),
                "service": m.get("service", ""),
                "hmo": m.get("hmo", ""),
                "tier": m.get("tier", ""),
                "text": m.get("text", ""),
                "source": m.get("source", ""),
            })
            if len(results) >= top_k:
                break
        return results
