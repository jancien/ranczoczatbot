from fasthtml.common import fast_app, FT
from pathlib import Path
from .services.vector_store import store


def _sanitize_element(value):
    if isinstance(value, FT):
        return _sanitize_ft_tree(value)
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (list, tuple)):
        return type(value)(_sanitize_element(v) for v in value)
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value
    return str(value) if value is not None else ''


def _sanitize_ft_tree(node):
    if isinstance(node, FT):
        sanitized_children = [_sanitize_element(child) for child in node.children]
        node.children = sanitized_children
        for child in node.children:
            if isinstance(child, FT):
                _sanitize_ft_tree(child)
    return node


def sanitize_response(resp, req):
    if hasattr(req, 'injects') and req.injects:
        req.injects = [_sanitize_element(i) if not isinstance(i, FT) else _sanitize_ft_tree(i) for i in req.injects]
    if isinstance(resp, (list, tuple)):
        return type(resp)(_sanitize_element(r) if not isinstance(r, FT) else _sanitize_ft_tree(r) for r in resp)
    return _sanitize_ft_tree(resp) if isinstance(resp, FT) else _sanitize_element(resp)


async def lifespan(app):
    try:
        loaded = await store.load_from_storage()
        if loaded:
            print("[online] Zaladowano indeks FAISS z Supabase Storage.")
        elif store.load():
            print("[online] Zaladowano lokalny indeks FAISS.")
        else:
            print("[online] Brak indeksu FAISS. Admin musi zaladowac embedding.")
    except Exception as e:
        print(f"[online] Ostrzezenie: Nie udalo sie zaladowac indeksu: {e}")
    yield


app, rt = fast_app(
    lifespan=lifespan,
    after=(sanitize_response,),
    pico=False,
    static_dir=str(Path(__file__).parent / "static"),
)
