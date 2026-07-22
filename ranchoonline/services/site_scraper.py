import re
import threading
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx

from .embeddings import embed_text
from .vector_store import VectorStore, FAISS_DIR

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
DEFAULT_MAX_PAGES = 50

_status_lock = threading.Lock()
SCRAPER_STATUS = {
    "state": "idle",
    "message": "Nie rozpoczęto zadania.",
    "progress": 0,
    "total": 0,
    "docs_found": 0,
    "details": [],
    "error": None,
}


def _set_status(**kwargs):
    with _status_lock:
        for key, value in kwargs.items():
            SCRAPER_STATUS[key] = value


def get_scraper_status() -> dict:
    with _status_lock:
        return SCRAPER_STATUS.copy()


def reset_scraper_status() -> None:
    with _status_lock:
        SCRAPER_STATUS.update({
            "state": "idle",
            "message": "Nie rozpoczęto zadania.",
            "progress": 0,
            "total": 0,
            "docs_found": 0,
            "details": [],
            "error": None,
        })


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._ignore = False
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._ignore = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._ignore = False
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._ignore:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        text = " ".join(self._parts)
        return re.sub(r"\s+", " ", text).strip()


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                url = self._normalize(value)
                if url:
                    self.links.add(url)

    def _normalize(self, href: str) -> str | None:
        href = href.strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            return None
        url = urljoin(self.base_url, href)
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None
        return parsed._replace(fragment="").geturl()


def _safe_name(url: str, existing: Iterable[str]) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path.endswith("/"):
        path = path[:-1]
    if not path or path == "":
        name = "home"
    else:
        name = path.strip("/")
    if not name:
        name = "home"
    name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if parsed.query:
        query = re.sub(r"[^a-z0-9]+", "-", parsed.query.lower()).strip("-")
        if query:
            name = f"{name}-{query}" if name else query
    if not name:
        name = "page"

    candidate = f"{name}.txt"
    counter = 1
    while candidate in existing:
        candidate = f"{name}-{counter}.txt"
        counter += 1
    return candidate


def _text_from_html(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return parser.get_text()


def _links_from_html(html: str, base_url: str) -> set[str]:
    parser = LinkExtractor(base_url)
    parser.feed(html)
    return parser.links


def scrape_site_to_docs(site_url: str, max_pages: int = DEFAULT_MAX_PAGES) -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for path in DOCS_DIR.glob("*.txt"):
        path.unlink()

    parsed_start = urlparse(site_url)
    if not parsed_start.scheme:
        raise ValueError("URL musi zawierac scheme http:// lub https://")
    if not parsed_start.netloc:
        raise ValueError("URL musi zawierac poprawna domena")

    _set_status(state="scraping", message="Rozpoczynam przeszukiwanie strony...", progress=0, total=max_pages, docs_found=0, details=[], error=None)

    base_netloc = parsed_start.netloc
    urls = [parsed_start.geturl()]
    visited: set[str] = set()
    saved_files: set[str] = set()
    docs_count = 0

    with httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (compatible; RanchoBot/1.0)"}) as client:
        while urls and docs_count < max_pages:
            url = urls.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                resp = client.get(url)
                resp.raise_for_status()
            except Exception:
                continue

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                continue

            html_text = resp.text
            text = _text_from_html(html_text)
            if not text:
                continue

            filename = _safe_name(url, saved_files)
            saved_files.add(filename)
            (DOCS_DIR / filename).write_text(text, encoding="utf-8")
            docs_count += 1
            _set_status(
                message=f"Found {docs_count} docs in docs",
                docs_found=docs_count,
                progress=min(100, int(docs_count / max_pages * 100)),
                details=SCRAPER_STATUS["details"] + [f"Found {docs_count} docs in docs"],
            )

            for link in _links_from_html(html_text, url):
                parsed = urlparse(link)
                if parsed.netloc != base_netloc:
                    continue
                if link not in visited and link not in urls:
                    urls.append(link)

    return docs_count


def build_faiss_from_docs() -> tuple[int, int]:
    docs = []
    if not DOCS_DIR.exists():
        raise FileNotFoundError("Folder docs/ nie istnieje")

    for path in sorted(DOCS_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        docs.append((path.name, text))

    if not docs:
        raise ValueError("Brak dokumentow do zindeksowania w folderze docs/")

    _set_status(state="embedding", message="Rozpoczynam tworzenie embeddingów...", progress=0, total=len(docs), docs_found=len(docs), details=SCRAPER_STATUS["details"], error=None)

    embeddings = []
    chunks = []
    sources = []
    for index, (filename, text) in enumerate(docs, start=1):
        _set_status(
            message=f"Embedding {filename}...",
            progress=min(100, int(index / len(docs) * 100)),
            details=SCRAPER_STATUS["details"] + [f"Embedding {filename}..."],
        )
        embeddings.append(embed_text(text))
        chunks.append(text)
        sources.append(filename)

    store = VectorStore()
    store.build(embeddings, chunks, sources)
    store.save()
    try:
        store.save_to_storage()
    except Exception as e:
        print(f"[ostrzezenie] Nie udalo sie zapisac indeksu do Supabase: {e}")
    _set_status(state="completed", message="Gotowe. Indeks zbudowany.", progress=100, details=SCRAPER_STATUS["details"] + ["Gotowe. Indeks zbudowany."], error=None)
    return len(docs), store.dimension
