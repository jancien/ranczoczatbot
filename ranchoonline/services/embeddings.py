import httpx
from ..config import settings

TIMEOUT = 30.0

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
JINA_URL = "https://api.jina.ai/v1/embeddings"


def _parse_embedding_response(data: dict) -> list[float]:
    item = data.get("data", [None])[0]
    if not item:
        raise ValueError("Brak danych embeddingu w odpowiedzi serwera.")
    embedding = item.get("embedding") or item.get("embeddings") or item.get("vector")
    if not embedding:
        raise ValueError("Nie znaleziono pola embedding w odpowiedzi serwera.")
    return embedding


def _embed_with_voyage(text: str) -> list[float]:
    api_key = settings.voyage_api_key
    if not api_key:
        raise ValueError("Brak VOYAGE_API_KEY w konfiguracji.")

    payload = {"input": text, "model": settings.voyage_embedding_model, "input_type": "query"}
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(
            VOYAGE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return _parse_embedding_response(data)


def _embed_with_jina(text: str) -> list[float]:
    api_key = settings.jina_api_key
    if not api_key:
        raise ValueError("Brak JINA_API_KEY w konfiguracji.")

    payload = {"model": settings.jina_embedding_model, "input": [text], "task": "retrieval.query"}
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(
            JINA_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code != 200:
            print(f"[EMBEDDING ERROR] JINA status: {resp.status_code}")
            print(f"[EMBEDDING ERROR] JINA body: {resp.text}")
        resp.raise_for_status()
        data = resp.json()
        return _parse_embedding_response(data)


def embed_text(text: str) -> list[float]:
    if settings.jina_api_key:
        try:
            return _embed_with_jina(text)
        except Exception as e:
            print(f"[EMBEDDING ERROR] JINA: {e}")
            raise

    if settings.voyage_api_key:
        try:
            return _embed_with_voyage(text)
        except Exception as e:
            print(f"[EMBEDDING ERROR] VOYAGE: {e}")
            raise

    raise ValueError("Brak JINA_API_KEY lub VOYAGE_API_KEY w konfiguracji.")