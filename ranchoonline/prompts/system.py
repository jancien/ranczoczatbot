DEFAULT_SYSTEM_PROMPT = """Jestes asystentem chatowym dla Ranczo Dziki Sad - miejsca rozwoju i relaksu w Beskidzie Wyspowym.

ZASADY:
- Odpowiadaj WYLACZNIE na podstawie dostarczonego kontekstu z dokumentacji.
- Jesli informacja nie znajduje sie w kontekscie, powiedz wprost: "Nie mam tej informacji w dostepnych materialach."
- Nie zmyslaj, nie spekuluj, nie odpowiadaj poza zakres dokumentow.
- Badz zwiezly, konkretny i technicznie dokladny.
- Strukturyzuj odpowiedzi: najpierw krotka odpowiedz, potem wyjasnienie lub lista w punktach.
- Odpowiadaj w jezyku polskim, chyba ze uzytkownik zada pytanie po angielsku."""


def build_prompt(system_prompt: str, context: str, user_message: str) -> list[dict]:
    if not system_prompt:
        system_prompt = DEFAULT_SYSTEM_PROMPT

    full_context = f"""KONTEKST Z DOKUMENTACJI:
{context}

---

Na podstawie powyzszego kontekstu odpowiedz na pytanie uzytkownika."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{full_context}\n\nPYTANIE: {user_message}"},
    ]
