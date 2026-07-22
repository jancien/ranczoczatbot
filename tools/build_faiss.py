import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ranchoonline.config import settings
from ranchoonline.services.embeddings import embed_text
from ranchoonline.services.vector_store import VectorStore, FAISS_DIR


def load_docs(doc_dir: Path) -> list[tuple[str, str]]:
    docs = []
    for path in sorted(doc_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        docs.append((path.name, text))
    return docs


def main() -> None:
    doc_dir = Path("docs")
    if not doc_dir.exists():
        raise SystemExit("Directory 'docs' not found")

    docs = load_docs(doc_dir)
    if not docs:
        raise SystemExit("No TXT files found in docs/")

    print(f"Found {len(docs)} docs in {doc_dir}")
    embeddings = []
    chunks = []
    sources = []

    for filename, text in docs:
        print(f"Embedding {filename}...")
        embedding = embed_text(text)
        embeddings.append(embedding)
        chunks.append(text)
        sources.append(filename)

    store = VectorStore()
    store.build(embeddings, chunks, sources)
    print(f"Built FAISS index with dimension {store.dimension} and {len(embeddings)} vectors")

    FAISS_DIR.mkdir(parents=True, exist_ok=True)
    faiss_path = FAISS_DIR / "index.faiss"
    json_path = FAISS_DIR / "index.json"

    store.save()
    print(f"Saved index to {faiss_path}")
    print(f"Saved metadata to {json_path}")

    print("Done.")


if __name__ == "__main__":
    main()
