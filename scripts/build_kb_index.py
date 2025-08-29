import os
import json
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

from services.knowledge_base import load_kb
from services.embedding_client import AzureEmbeddingClient

def make_chunk_text(row: dict) -> str:
    return f"{row['category']} | {row['service']} | HMO:{row.get('hmo','')} | Tier:{row.get('tier','')}\n{row['text']}"

def main():
    load_dotenv()
    data_dir = Path(os.getenv("PHASE2_DATA_DIR", "./phase2_data"))
    out_path = Path(os.getenv("KB_INDEX_PATH", "./data/kb_index.npz"))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = load_kb(data_dir)
    print(f"Parsed {len(rows)} rows from {data_dir}")

    embedder = AzureEmbeddingClient()
    X_list = []
    meta = []
    BATCH = 64
    for i in tqdm(range(0, len(rows), BATCH), desc="Embedding"):
        batch = rows[i:i+BATCH]
        texts = [make_chunk_text(r) for r in batch]
        vecs = embedder.embed(texts)
        X_list.append(vecs.astype(np.float32))
        for r in batch:
            meta.append({
                "category": r["category"],
                "service": r["service"],
                "hmo": r.get("hmo", ""),
                "tier": r.get("tier", ""),
                "text": r["text"],
                "source": r["source"],
            })
    X = np.vstack(X_list) if X_list else np.zeros((0, 1536), dtype=np.float32)
    meta_json = json.dumps(meta, ensure_ascii=False)
    np.savez_compressed(out_path, X=X, meta=np.array(meta_json, dtype=object))
    print(f"Saved index: {out_path} with X={X.shape}")

if __name__ == "__main__":
    main()
