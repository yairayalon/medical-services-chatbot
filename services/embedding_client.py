import os
import httpx
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential

class AzureEmbeddingClient:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_EMBEDDINGS_ENDPOINT")
        self.key = os.getenv("AZURE_OPENAI_EMBEDDINGS_KEY")
        self.deployment = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "text-embedding-ada-002")
        if not (self.endpoint and self.key and self.deployment):
            raise RuntimeError("Azure embeddings env vars missing")
        self.api_version = "2024-06-01"
        self.dim = 1536

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    def embed(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/embeddings?api-version={self.api_version}"
        headers = {"api-key": self.key, "Content-Type": "application/json"}
        payload = {"input": texts}
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            vecs = [np.array(d["embedding"], dtype=np.float32) for d in data["data"]]
            return np.vstack(vecs)
