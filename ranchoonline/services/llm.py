from groq import Groq, APIError, APIConnectionError, AuthenticationError
from ..config import settings
from ..database import get_config

MAX_GROQ_REQUEST_TOKENS = 6000
TOKEN_ESTIMATE_RATIO = 3.5


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / TOKEN_ESTIMATE_RATIO))


def _normalize_max_tokens(messages: list[dict], max_tokens: int) -> int:
    prompt_text = " ".join(m.get("content", "") for m in messages)
    prompt_tokens = _estimate_tokens(prompt_text)
    if prompt_tokens + max_tokens > MAX_GROQ_REQUEST_TOKENS:
        allowed = MAX_GROQ_REQUEST_TOKENS - prompt_tokens
        if allowed < 64:
            raise ValueError(
                "Zbyt duzo tekstu w kontekście. Zmniejsz zakres dokumentów lub skróć pytanie."
            )
        return max(64, min(max_tokens, allowed))
    return max_tokens


def get_chat_response(messages: list[dict], temperature: float, max_tokens: int, top_p: float) -> str:
    normalized_max_tokens = _normalize_max_tokens(messages, max_tokens)
    return _groq_chat(messages, temperature, normalized_max_tokens, top_p)


def _groq_chat(messages: list[dict], temperature: float, max_tokens: int, top_p: float) -> str:
    api_key = get_config("groq_api_key") or settings.groq_api_key
    model = get_config("groq_model") or settings.groq_model

    if not api_key:
        return "Brak klucza API Groq. Skonfiguruj go w panelu admina."

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        return response.choices[0].message.content or ""
    except AuthenticationError:
        return "Blad autoryzacji API. Sprawdz klucz API Groq."
    except APIConnectionError:
        return "Blad polaczenia z API Groq."
    except APIError as e:
        return f"Blad API Groq: {e.message}"
    except Exception as e:
        return f"Blad: {str(e)}"
