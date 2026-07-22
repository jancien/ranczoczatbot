import os
import faiss
import numpy as np
import json
import io
from pathlib import Path
from ..config import settings


FAISS_DIR = Path(os.environ.get("FAISS_DIR", Path.home() / ".ranchoonline" / "faiss_index"))


class VectorStore:
    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        self.index: faiss.IndexFlatIP | None = None
        self.chunks: list[str] = []
        self.sources: list[str] = []

    def build(self, embeddings: list[list[float]], chunks: list[str], sources: list[str]):
        arr = np.array(embeddings, dtype=np.float32)
        if arr.ndim != 2:
            raise ValueError("Embeddings must be a 2D list of vectors")
        self.dimension = arr.shape[1]
        faiss.normalize_L2(arr)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(arr)
        self.chunks = chunks
        self.sources = sources

    def save(self):
        FAISS_DIR.mkdir(parents=True, exist_ok=True)
        if self.index is not None:
            faiss.write_index(self.index, str(FAISS_DIR / "index.faiss"))
        with open(FAISS_DIR / "index.json", "w", encoding="utf-8") as f:
            json.dump({"chunks": self.chunks, "sources": self.sources}, f, ensure_ascii=False)

    def load(self) -> bool:
        faiss_path = FAISS_DIR / "index.faiss"
        if not faiss_path.exists():
            return False
        self.index = faiss.read_index(str(faiss_path))
        self.dimension = self.index.d
        with open(FAISS_DIR / "index.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        self.chunks = data["chunks"]
        self.sources = data["sources"]
        return True

    async def load_from_storage(self) -> bool:
        try:
            from ..database import get_supabase
            sb = get_supabase()
            bucket = sb.storage.from_(settings.faiss_bucket)

            faiss_bytes = bucket.download("index.faiss")
            json_bytes = bucket.download("index.json")

            FAISS_DIR.mkdir(parents=True, exist_ok=True)
            (FAISS_DIR / "index.faiss").write_bytes(faiss_bytes)
            (FAISS_DIR / "index.json").write_text(json_bytes.decode("utf-8"))

            return self.load()
        except Exception:
            return False

    def save_to_storage(self):
        try:
            from ..database import get_supabase
            sb = get_supabase()

            try:
                sb.storage.create_bucket(settings.faiss_bucket, {"public": False})
            except Exception:
                pass

            bucket = sb.storage.from_(settings.faiss_bucket)

            if self.index is not None:
                buf = io.BytesIO()
                faiss.write_index(self.index, buf)
                bucket.upload("index.faiss", buf.getvalue(), {"content-type": "application/octet-stream"})

            json_data = json.dumps({"chunks": self.chunks, "sources": self.sources}, ensure_ascii=False)
            bucket.upload("index.json", json_data.encode("utf-8"), {"content-type": "application/json"})
        except Exception as e:
            print(f"[ostrzezenie] Nie udalo sie zapisac do Supabase Storage: {e}")

    def search(self, query_embedding: list[float], top_k: int = None) -> list[dict]:
        top_k = top_k or settings.top_k
        if self.index is None:
            return []
        q = np.array([query_embedding], dtype=np.float32)
        if q.ndim != 2 or q.shape[1] != self.index.d:
            raise ValueError(
                f"Query embedding dimension {q.shape[1]} does not match FAISS index dimension {self.index.d}. "
                "Rebuild the index with the same embedding model."
            )
        faiss.normalize_L2(q)
        scores, indices = self.index.search(q, top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.chunks):
                results.append({
                    "chunk": self.chunks[idx],
                    "source": self.sources[idx],
                    "score": float(score),
                })
        return results


store = VectorStore()
