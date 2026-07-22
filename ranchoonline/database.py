from datetime import datetime, timedelta
try:
    from supabase import create_client
except ImportError:
    print("=" * 60)
    print("BLAD: Brak paczki 'supabase'. Zainstaluj ja:")
    print("pip install supabase")
    print("=" * 60)
    raise
from .config import settings


_supabase = None


def _supabase_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key)


def get_supabase():
    global _supabase
    if not _supabase_configured():
        raise ConnectionError("Supabase nie jest skonfigurowane. Ustaw SUPABASE_URL i SUPABASE_SERVICE_KEY w .env")
    if _supabase is None:
        _supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    return _supabase


def save_chat(ip_address: str, question: str, answer: str, found_in_materials: bool):
    if not _supabase_configured():
        return
    try:
        sb = get_supabase()
        sb.table("chat_history").insert({
            "ip_address": ip_address,
            "question": question,
            "answer": answer,
            "found_in_materials": found_in_materials,
        }).execute()
    except Exception:
        pass


def get_chat_history(days: int = 30) -> list[dict]:
    if not _supabase_configured():
        return []
    try:
        sb = get_supabase()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        r = sb.table("chat_history").select("*").gte("timestamp", cutoff).order("timestamp", desc=True).execute()
        return r.data
    except Exception:
        return []


def get_config(key: str, default: str = "") -> str:
    if not _supabase_configured():
        return default
    try:
        sb = get_supabase()
        r = sb.table("bot_config").select("value").eq("key", key).execute()
        return r.data[0]["value"] if r.data else default
    except Exception:
        return default


def set_config(key: str, value: str):
    if not _supabase_configured():
        return
    try:
        sb = get_supabase()
        sb.table("bot_config").upsert({"key": key, "value": value}).execute()
    except Exception:
        pass


def get_all_config() -> dict:
    if not _supabase_configured():
        return {}
    try:
        sb = get_supabase()
        r = sb.table("bot_config").select("*").execute()
        return {row["key"]: row["value"] for row in r.data}
    except Exception:
        return {}
