import json, csv, io, tempfile, zipfile, shutil, threading
from pathlib import Path
from fasthtml.common import *
from starlette.responses import RedirectResponse, Response, JSONResponse
from ..app import rt
from ..config import settings
from ..database import get_chat_history, get_all_config, set_config
from ..services.site_scraper import (
    scrape_site_to_docs,
    build_faiss_from_docs,
    reset_scraper_status,
    get_scraper_status,
    _set_status,
)
from ..services.vector_store import store, FAISS_DIR
from ..prompts.system import DEFAULT_SYSTEM_PROMPT


ADMIN_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body.admin-page { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; }
    .container { max-width: 900px; margin: 0 auto; padding: 20px; }
    .header { padding: 16px 0; }
    .header h1 { font-size: 1.4rem; color: #2d5016; }
    .nav { display: flex; gap: 16px; margin-top: 8px; }
    .nav a { color: #2d5016; text-decoration: none; font-weight: 500; font-size: 0.9rem; }
    .nav a:hover { text-decoration: underline; }
    .card { background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
    .card h2 { font-size: 1rem; color: #555; margin-bottom: 12px; }
    .badge { color: #888; font-size: 0.85rem; margin-bottom: 4px; }
    .row { display: flex; gap: 12px; margin-bottom: 12px; }
    .row > div { flex: 1; }
    .field { margin-bottom: 12px; }
    .field label, label { display: block; font-weight: 600; font-size: 0.85rem; color: #444; margin-bottom: 4px; }
    .input-full, input:not([type="file"]) { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 8px; }
    .textarea-full { width: 100%; height: 120px; padding: 8px; border: 1px solid #ddd; border-radius: 8px; }
    .textarea-full.code { font-family: monospace; }
    .section-title { font-size: 1rem; color: #555; margin: 16px 0 8px; }
    .btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.9rem; }
    .btn-primary { background: #2d5016; color: #fff; }
    .btn-primary:hover { background: #3a6b1c; }
    .btn-full { width: 100%; }
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #eee; }
    th { background: #2d5016; color: #fff; font-weight: 600; }
    tr:hover { background: #f5f5f5; }
"""


def check_admin(session) -> bool:
    return session.get("admin_logged_in", False)


@rt("/admin/login")
def get(session):
    if check_admin(session):
        return RedirectResponse("/admin/", status_code=303)
    return Html(
        Head(Title("Admin - Logowanie"), Style(ADMIN_CSS)),
        Body(
            Div(
                H1("Panel administracyjny"),
                Form(
                    Input(type="password", name="password", placeholder="Haslo", cls="input-full"),
                    Button("Zaloguj", type="submit", cls="btn btn-primary btn-full"),
                    action="/admin/login", method="post",
                ),
                cls="card", style="max-width:400px;margin:100px auto;",
            ),
            cls="admin-page",
        ),
    )


@rt("/admin/login")
async def post(request):
    form = await request.form()
    password = form.get("password", "")
    session = request.scope.get("session", {})
    if password == settings.admin_password:
        session["admin_logged_in"] = True
        return RedirectResponse("/admin/", status_code=303)
    return Html(
        Head(Title("Admin - Logowanie"), Style(ADMIN_CSS)),
        Body(
            Div(
                H1("Panel administracyjny"),
                P("Nieprawidlowe haslo", style="color:#cc0000;"),
                Form(
                    Input(type="password", name="password", placeholder="Haslo", cls="input-full"),
                    Button("Zaloguj", type="submit", cls="btn btn-primary btn-full"),
                    action="/admin/login", method="post",
                ),
                cls="card", style="max-width:400px;margin:100px auto;",
            ),
            cls="admin-page",
        ),
    )


@rt("/admin/logout")
def get(session):
    session.pop("admin_logged_in", None)
    return RedirectResponse("/admin/login", status_code=303)


@rt("/admin")
def get(session):
    if not check_admin(session):
        return RedirectResponse("/admin/login", status_code=303)

    has_index = store.index is not None
    cfg = get_all_config()
    config_data = cfg

    return Html(
        Head(Title("Admin - Dashboard"), Style(ADMIN_CSS)),
        Body(
            Div(
                Div(H1("Panel administracyjny"), cls="header"),
                Div(A("Dashboard", href="/admin/"), A("Konfiguracja", href="/admin/config"), A("Historia", href="/admin/history"), A("Wyloguj", href="/admin/logout"), cls="nav"),
                Div(
                    H2("Status"),
                    P(f"Indeks FAISS: {'Zaladowany' if has_index else 'Pusty'}", cls="badge"),
                    P(f"Model: {config_data.get('groq_model', settings.groq_model)}"),
                    cls="card",
                ),
                Div(
                    H2("Zaladuj embedding z URL"),
                    Div(
                        Input(type="text", id="site-url", cls="input-full", value=cfg.get("site_url", "https://ranczo-dziki-sad.pl/"), placeholder="Wpisz adres strony..."),
                        Div(Label("Maksymalna liczba stron:"), Input(type="number", id="max-pages", cls="input-full", value=cfg.get("max_pages", "50"), min="1", max="200")),
                        Input(type="button", value="Zaladuj", cls="btn btn-primary", id="scrape-button"),
                        cls="field",
                    ),
                    Div(
                        H3("Status zadania"),
                        Div(id="scrape-start", style="margin-top:12px;line-height:1.5em;"),
                        Div(id="scrape-status", style="margin-top:12px;line-height:1.5em;"),
                        Div(id="scrape-details", style="margin-top:12px;font-family:monospace;white-space:pre-wrap;max-height:220px;overflow:auto;background:#f9f9f9;border:1px solid #ddd;padding:12px;border-radius:8px;"),
                    ),
                    cls="card",
                ),
                Script(r"""
                    document.addEventListener('DOMContentLoaded', function() {
                        var statusLabel = document.getElementById('scrape-status');
                        var statusDetails = document.getElementById('scrape-details');
                        var startLabel = document.getElementById('scrape-start');
                        var button = document.getElementById('scrape-button');

                        if (!button) {
                            console.error('Brak przycisku scrape-button');
                            return;
                        }

                        function fetchScrapeStatus() {
                            fetch('/admin/scrape/status', { credentials: 'same-origin' })
                                .then(function(res) {
                                    if (!res.ok) {
                                        return res.text().then(function(text) {
                                            console.error('Status fetch failed:', res.status, text);
                                            if (statusLabel) {
                                                statusLabel.textContent = 'Blad pobierania statusu: ' + res.status;
                                            }
                                        });
                                    }
                                    return res.json().then(function(data) {
                                        if (statusLabel) {
                                            if (data.state === 'completed') {
                                                statusLabel.textContent = 'Gotowe!';
                                            } else {
                                                statusLabel.textContent = 'Stan: ' + data.state + ' | ' + data.message + ' | ' + data.docs_found + ' dokumentow | ' + data.progress + '%';
                                            }
                                        }
                                        if (statusDetails) {
                                            statusDetails.textContent = Array.isArray(data.details) ? data.details.join('\\n') : JSON.stringify(data.details);
                                        }
                                    });
                                })
                                .catch(function(err) {
                                    console.error(err);
                                    if (statusLabel) {
                                        statusLabel.textContent = 'Blad pobierania statusu. Sprawdz konsolę.';
                                    }
                                });
                        }

                        button.addEventListener('click', function() {
                            var siteUrl = document.getElementById('site-url').value;
                            var maxPages = document.getElementById('max-pages').value;
                            var formData = new FormData();
                            formData.append('site_url', siteUrl);
                            formData.append('max_pages', maxPages);
                            fetch('/admin/scrape', {
                                method: 'POST',
                                credentials: 'same-origin',
                                body: formData,
                            })
                                .then(function(res) {
                                    if (!res.ok) {
                                        return res.text().then(function(text) {
                                            if (startLabel) {
                                                startLabel.textContent = 'Blad uruchomienia: ' + res.status;
                                            }
                                            console.error(text);
                                        });
                                    }
                                    return res.json().then(function(data) {
                                        if (startLabel) {
                                            if (data.status !== 'started') {
                                                startLabel.textContent = 'Blad: ' + data.message;
                                            }
                                        }
                                    });
                                })
                                .catch(function(err) {
                                    if (startLabel) {
                                        startLabel.textContent = 'Blad uruchomienia zadania.';
                                    }
                                    console.error(err);
                                });
                        });

                        setInterval(fetchScrapeStatus, 2000);
                        fetchScrapeStatus();
                    });
                """),
                cls="container",
            ),
            cls="admin-page",
        ),
    )


@rt("/admin/scrape")
async def post(request, session):
    if not check_admin(session):
        return RedirectResponse("/admin/login", status_code=303)

    form = await request.form()
    site_url = form.get("site_url", "https://ranczo-dziki-sad.pl/").strip()
    max_pages = int(form.get("max_pages", "50"))

    try:
        reset_scraper_status()

        def run_scrape():
            try:
                scrape_site_to_docs(site_url, max_pages=max_pages)
                build_faiss_from_docs()
                store.load()
            except Exception as e:
                _set_status(state="error", message=str(e), error=str(e))

        thread = threading.Thread(target=run_scrape, daemon=True)
        thread.start()

        return JSONResponse({"status": "started", "message": "Zadanie uruchomione."})
    except Exception as e:
        return Html(
            Head(Title("Blad"), Style(ADMIN_CSS)),
            Body(Div(H1(f"Blad: {str(e)}"), A("Wroc", href="/admin/"), cls="card", style="max-width:600px;margin:40px auto;"), cls="admin-page"),
        )


@rt("/admin/scrape/status")
def status(session):
    if not check_admin(session):
        return JSONResponse({"error": "Brak autoryzacji"}, status_code=403)
    return JSONResponse(get_scraper_status())


@rt("/admin/config")
def get(session):
    if not check_admin(session):
        return RedirectResponse("/admin/login", status_code=303)

    cfg = get_all_config()

    return Html(
        Head(Title("Admin - Konfiguracja"), Style(ADMIN_CSS)),
        Body(
            Div(
                Div(H1("Konfiguracja bota"), cls="header"),
                Div(A("Dashboard", href="/admin/"), A("Historia", href="/admin/history"), A("Wyloguj", href="/admin/logout"), cls="nav"),
                Form(
                    Div(Label("System prompt:"), Textarea(cfg.get("system_prompt", DEFAULT_SYSTEM_PROMPT), name="system_prompt", cls="textarea-full code")),

                    Div(cls="row",
                        children=[
                            Div(Label("Groq API Key:"), Input(type="text", name="groq_api_key", value=cfg.get("groq_api_key", ""), cls="input-full")),
                            Div(Label("Groq Model:"), Input(type="text", name="groq_model", value=cfg.get("groq_model", settings.groq_model), cls="input-full")),
                        ],
                    ),
                    Div(cls="row",
                        children=[
                            Div(Label("Temperature:"), Input(type="number", name="temperature", value=cfg.get("temperature", str(settings.groq_temperature)), min="0", max="2", step="0.1", cls="input-full")),
                            Div(Label("Max tokens:"), Input(type="number", name="max_tokens", value=cfg.get("max_tokens", str(settings.groq_max_tokens)), min="1", max="4096", cls="input-full")),
                            Div(Label("Top-p:"), Input(type="number", name="top_p", value=cfg.get("top_p", str(settings.groq_top_p)), min="0", max="1", step="0.1", cls="input-full")),
                            Div(Label("Top K:"), Input(type="number", name="top_k", value=cfg.get("top_k", str(settings.top_k)), min="1", max="20", cls="input-full")),
                        ],
                    ),
                    H3("Przykladowe pytania", cls="section-title"),
                    *(Div(Label(f"Przykladowe pytanie {i}:"), Input(type="text", name=f"example_q{i}", value=cfg.get(f"example_q{i}", ""), cls="input-full"), cls="field") for i in range(1, 7)),
                    Button("Zapisz konfiguracje", type="submit", cls="btn btn-primary", style="margin-top:16px;"),
                    action="/admin/config", method="post",
                ),
                cls="container",
            ),
            cls="admin-page",
        ),
    )


@rt("/admin/config")
def post(session, system_prompt: str = "", groq_api_key: str = "", groq_model: str = "", temperature: str = "0.3", max_tokens: str = "1024", top_p: str = "0.9", top_k: str = "3", example_q1: str = "", example_q2: str = "", example_q3: str = "", example_q4: str = "", example_q5: str = "", example_q6: str = ""):
    if not check_admin(session):
        return RedirectResponse("/admin/login", status_code=303)

    set_config("system_prompt", system_prompt)
    set_config("groq_api_key", groq_api_key)
    set_config("groq_model", groq_model)
    set_config("temperature", temperature)
    set_config("max_tokens", max_tokens)
    set_config("top_p", top_p)
    set_config("top_k", top_k)
    for i in range(1, 7):
        set_config(f"example_q{i}", locals()[f"example_q{i}"])

    return RedirectResponse("/admin/config?saved=1", status_code=303)


@rt("/admin/history")
def get(session):
    if not check_admin(session):
        return RedirectResponse("/admin/login", status_code=303)

    days = 30
    history = get_chat_history(days)

    rows_html = ""
    for h in history:
        found = "Tak" if h["found_in_materials"] else "Nie"
        truncated_q = h["question"][:80] + "..." if len(h["question"]) > 80 else h["question"]
        truncated_a = h["answer"][:100] + "..." if len(h["answer"]) > 100 else h["answer"]
        rows_html += f"<tr><td>{h['ip_address']}</td><td>{h['timestamp'][:19]}</td><td>{truncated_q}</td><td>{truncated_a}</td><td>{found}</td></tr>"

    return Html(
        Head(Title("Admin - Historia"), Style(ADMIN_CSS)),
        Body(
            Div(
                Div(H1("Historia czatow (30 dni)"), cls="header"),
                Div(A("Dashboard", href="/admin/"), A("Konfiguracja", href="/admin/config"), A("Wyloguj", href="/admin/logout"), cls="nav"),
                Div(
                    Div(
                        P(f"Liczba wpisow: {len(history)}", style="color:#888;font-size:0.85rem;display:inline;"),
                        A("Eksportuj do CSV", href="/admin/history/export", cls="btn btn-primary", style="float:right;text-decoration:none;"),
                        style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;",
                    ),
                    Div(
                        table := Table(
                            Thead(Tr(Th("IP"), Th("Data"), Th("Pytanie"), Th("Odpowiedz"), Th("Znaleziono"))),
                            Tbody(NotStr(rows_html)),
                        ),
                        style="overflow-x:auto;",
                    ) if history else P("Brak historii czatow."),
                    cls="card",
                ),
                cls="container",
            ),
            cls="admin-page",
        ),
    )


@rt("/admin/history/export")
def get(session):
    if not check_admin(session):
        return RedirectResponse("/admin/login", status_code=303)

    history = get_chat_history(36500)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ip_address", "question", "answer", "timestamp", "found_in_materials"])
    for h in history:
        writer.writerow([h["ip_address"], h["question"], h["answer"], h["timestamp"], h["found_in_materials"]])
    csv_content = buf.getvalue()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=chat_history.csv"},
    )
