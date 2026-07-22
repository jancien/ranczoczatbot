from pathlib import Path
from fasthtml.common import *
from starlette.responses import JSONResponse, FileResponse
from ..app import rt
from ..models import ChatRequest
from ..services.rag import ask_question
from ..database import save_chat, get_config, get_all_config
from ..prompts.system import DEFAULT_SYSTEM_PROMPT
from ..config import settings
import traceback


@rt("/background")
def get():
    resp = FileResponse(str(Path(__file__).parent.parent / "zielen2.png"), media_type="image/png")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@rt("/lisek")
def get():
    return FileResponse(str(Path(__file__).parent.parent / "lisek.png"), media_type="image/png")


DEFAULT_QUESTIONS = [
    "Jakie macie atrakcje dla dzieci?",
    "Czy mozna przyjechac z psem?",
    "Jaka jest cena za nocleg?",
    "Co warto zobaczyc w okolicy?",
    "Czy serwujecie sniadania?",
    "Jakie sa wasze domowe wyroby?",
]


@rt("/")
def get():
    cfg = get_all_config()
    example_questions = [str(cfg.get(f"example_q{i}", DEFAULT_QUESTIONS[i-1])) for i in range(1, 7)]
    return Html(
        Head(
            Title("Ranczo Dziki Sad - Asystent"),
            Style("""
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; min-height: 100vh; }
                .container { max-width: 800px; margin: 0 auto; padding: 16px; }
                .header { text-align: center; padding: 20px 0; }
                .header h1 { font-size: 5rem; color: #2d5016; line-height: 1; }
                .subtitle-row { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 10px; }
                .subtitle-icon { width: 86px; height: 86px; flex-shrink: 0; }
                .subtitle-icon img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
                .subtitle-text { font-size: 2.1rem; color: #3a3a3a; }
                .chat-box { background: rgba(255,255,255); backdrop-filter: blur(4px); border-radius: 8px; height: 500px; overflow-y: auto; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 4px solid #3a3a3a; }
                .msg-row { display: flex; gap: 8px; margin-bottom: 12px; align-items: flex-start; }
                .msg-row.bot { flex-direction: row; }
                .msg-row.user { flex-direction: row-reverse; }
                .msg-icon { width: 43px; height: 43px; border-radius: 50%; flex-shrink: 0; }
                .msg-icon img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
                .msg { padding: 10px 14px; border-radius: 12px; max-width: 75%; word-wrap: break-word; }
                .msg-user { background: #2d5016; color: #fff; border-bottom-right-radius: 4px; }
                .msg-bot { background: #e8f0e0; color: #333; border-bottom-left-radius: 4px; }
                .msg-sources { font-size: 0.75rem; color: #888; margin-top: 4px; }
                .input-area { display: flex; gap: 8px; }
                .input-area input { flex: 1; border: 4px solid #3a3a3a; border-radius: 8px; padding: 12px; font-size: 1rem; }
                .btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.9rem; }
                .btn-primary { background: #2d5016; color: #fff; }
                .btn-primary:hover { background: #3a6b1c; }
                .examples { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
                .examples button { padding: 8px 14px; border: 2px solid #3a3a3a; border-radius: 20px; background: rgba(255,255,255,0.7); cursor: pointer; font-size: 0.85rem; color: #555; transition: all 0.2s; }
                .examples button:hover { background: #2d5016; color: #fff; border-color: #3a3a3a; }
                .status { font-size: 0.8rem; color: #666; text-align: center; margin-bottom: 8px; }
            """),
        ),
        Body(
            Div(
                Div(
                    H1("Ranczo Dziki Sad"),
                    Div(
                        Div(Img(src="/lisek", alt="lisek"), cls="subtitle-icon"),
                        P("Zapytaj asystenta o nasze ranczo", cls="subtitle-text"),
                        cls="subtitle-row",
                    ),
                    cls="header",
                ),
                Div(id="status", cls="status"),
                Div(id="chat-box", cls="chat-box"),
                Div(
                    *(Button(q, onclick="exampleClick(this)") for q in example_questions),
                    cls="examples",
                ),
                Div(
                    Input(type="text", id="user-input", placeholder="Napisz pytanie...", onkeydown="if(event.key==='Enter')sendMessage()"),
                    Button("Wyslij", cls="btn btn-primary", onclick="sendMessage()"),
                    cls="input-area",
                ),
                Script("""
                    async function sendMessage() {
                        const input = document.getElementById('user-input');
                        const msg = input.value.trim();
                        if (!msg) return;
                        input.value = '';
                        addMessage(msg, 'user');
                        const status = document.getElementById('status');
                        status.textContent = 'Oczekiwanie na odpowiedz...';
                        try {
                            const res = await fetch('/api/chat', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({message: msg})
                            });
                            const data = await res.json();
                            addMessage(data.answer, 'bot', data.sources);
                        } catch (e) {
                            addMessage('Blad polaczenia z serwerem.', 'bot');
                        }
                        status.textContent = '';
                    }
                    function addMessage(text, role, sources) {
                        const box = document.getElementById('chat-box');
                        const row = document.createElement('div');
                        row.className = 'msg-row ' + role;
                        if (role === 'bot') {
                            const icon = document.createElement('div');
                            icon.className = 'msg-icon';
                            icon.innerHTML = '<img src="/lisek" alt="lisek">';
                            row.appendChild(icon);
                        }
                        const bubble = document.createElement('div');
                        bubble.className = 'msg msg-' + role;
                        bubble.textContent = text;
                        if (sources && sources.length) {
                            const src = document.createElement('div');
                            src.className = 'msg-sources';
                            src.textContent = 'Zrodla: ' + sources.join(', ');
                            bubble.appendChild(src);
                        }
                        row.appendChild(bubble);
                        box.appendChild(row);
                        box.scrollTop = box.scrollHeight;
                    }
                    function exampleClick(btn) {
                        document.getElementById('user-input').value = btn.textContent;
                        sendMessage();
                    }
                """),
                cls="container",
            ),
            cls="user-page",
        ),
    )


@rt("/api/chat")
def post(request, req: ChatRequest):
    try:
        system_prompt = get_config("system_prompt") or DEFAULT_SYSTEM_PROMPT
        temperature = float(get_config("temperature", str(settings.groq_temperature)))
        max_tokens = int(get_config("max_tokens", str(settings.groq_max_tokens)))
        top_p = float(get_config("top_p", str(settings.groq_top_p)))

        result = ask_question(
            user_message=req.message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

        found_in_materials = result.get("found_in_materials", False)
        if found_in_materials and "nie mam tej informacji" in result["answer"].lower():
            found_in_materials = False

        client_ip = request.client.host if request.client else "unknown"
        save_chat(
            ip_address=client_ip,
            question=req.message,
            answer=result["answer"],
            found_in_materials=found_in_materials,
        )

        return JSONResponse({
            "answer": result["answer"],
            "sources": result["sources"],
            "found_in_materials": found_in_materials,
        })
    except Exception as e:
        print(f"[API CHAT ERROR] {type(e).__name__}: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse({"answer": f"Blad serwera: {str(e)}", "sources": [], "found_in_materials": False})
