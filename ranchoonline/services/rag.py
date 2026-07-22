from .embeddings import embed_text
from .vector_store import store
from .llm import get_chat_response
from ..prompts.system import build_prompt
from ..config import settings
from ..database import get_config

MAX_CONTEXT_CHARS = 6500
MAX_CHUNK_CHARS = 1200


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    if not truncated:
        truncated = text[:max_chars]
    return f"{truncated} ..."


def ask_question(user_message: str, system_prompt: str, temperature: float, max_tokens: int, top_p: float) -> dict:
    if store.index is None:
        return {
            "answer": "Indeks dokumentow jest pusty. Admin musi zaladowac embedding.",
            "sources": [],
        }

    query_embedding = embed_text(user_message)
    top_k = int(get_config("top_k", str(settings.top_k)))
    results = store.search(query_embedding, top_k=top_k)

    if not results:
        return {
            "answer": "Nie mam tej informacji w dostepnych materialach.",
            "sources": [],
            "found_in_materials": False,
        }

    context_parts = []
    sources = []
    for r in results:
        snippet = _truncate_text(r["chunk"].strip(), MAX_CHUNK_CHARS)
        context_parts.append(f"[Source: {r['source']}\n{snippet}")
        sources.append(r["source"])

    context = "\n\n---\n\n".join(context_parts)
    if len(context) > MAX_CONTEXT_CHARS:
        context = _truncate_text(context, MAX_CONTEXT_CHARS - 120)
        context += "\n\n... [Kontekst zostal skrocony]"

    messages = build_prompt(system_prompt, context, user_message)
    answer = get_chat_response(messages, temperature, max_tokens, top_p)

    return {"answer": answer, "sources": list(set(sources)), "found_in_materials": True}
