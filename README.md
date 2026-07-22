# Ranczo Dziki Sad – Asystent Online

Chatbot RAG dla Ranczo Dziki Sad z panelem administracyjnym.

## Wymagania

- Python 3.11+
- Klucz API [Groq](https://console.groq.com)
- Klucz API [Gemini](https://aistudio.google.com)
- Projekt [Supabase](https://supabase.com) (baza + storage)

## Szybki start

```bash
# 1. Wirtualne srodowisko
python -m venv venv
.\venv\Scripts\activate

# 2. Zaleznosci
pip install -r requirements.txt

# 3. Konfiguracja
copy .env.example .env
# wypelnij .env swoimi kluczami

# 4. Uruchom
uvicorn ranchoonline.main:app --reload --port 8080
```

Aplikacja bedzie dostepna pod `http://localhost:8080`, panel admina pod `http://localhost:8080/admin/`.

## Zmienne srodowiskowe (.env)

| Zmienna | Opis |
|---|---|
| `GROQ_API_KEY` | Klucz API Groq do czatu |
| `GROQ_MODEL` | Model Groq (np. `llama-3.1-8b-instant`) |
| `JINA_API_KEY` | Klucz API Jina do embeddingu |
| `SUPABASE_URL` | URL projektu Supabase |
| `SUPABASE_ANON_KEY` | Klucz anonimowy Supabase |
| `SUPABASE_SERVICE_KEY` | Klucz serwisowy Supabase |
| `PORT` | Port serwera (domyslnie 8080) |
| `ADMIN_PASSWORD` | haslo admina do konfiguracji |



## Funkcje

- **Czat**: interaktywny chatbot na stronie glownej
- **RAG**: odpowiedzi na podstawie wgranej dokumentacji (FAISS + Gemini embedding)
- **Admin**: panel do zarzadzania konfiguracja, wgrywania indeksu FAISS (ZIP) i podgladu historii czatow

## Deployment (Fly.io)

```bash
fly launch
fly secrets set GROQ_API_KEY=... GEMINI_API_KEY=... SUPABASE_URL=... SUPABASE_SERVICE_KEY=...
fly deploy
```
