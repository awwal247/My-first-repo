"""
app/services/search.py
======================
Web-search integration for "deep research" (v2.1).

Exa AI (https://exa.ai) is the PRIMARY web-search provider. It returns
structured results (title + url + content snippet), which lets us build
a proper "Sources" list to attach to the AI's answer.

Tavily is kept as an AUTOMATIC FALLBACK:
  - used if EXA_API_KEY is not configured, or
  - used if an Exa request fails for any reason.

Both providers are exposed through a single entry point, `web_search()`,
which always returns a dict with:
    {
        "context": str,                # text to inject into the AI prompt
        "sources": [{"title": str, "url": str}, ...],
        "provider": "exa" | "tavily" | "",
    }
"""

import requests

from app.config.settings import Config

_cfg = Config()


# ---------------------------------------------------------------------------
# Exa AI (primary)
# ---------------------------------------------------------------------------

def exa_search(query: str, max_results: int = 5) -> dict:
    """
    Perform an Exa AI web search.

    Returns a dict with `context` (concatenated snippets) and `sources`
    (list of {"title", "url"} dicts), or an empty dict if the key is
    missing or the request fails.
    """
    if not _cfg.EXA_API_KEY:
        return {}

    try:
        response = requests.post(
            f"{_cfg.EXA_BASE_URL}/search",
            headers={
                "x-api-key": _cfg.EXA_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "numResults": max_results,
                "type": "auto",
                "contents": {"text": {"maxCharacters": 1200}},
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        chunks: list[str] = []
        sources: list[dict] = []

        for res in results:
            title = (res.get("title") or "").strip()
            url = (res.get("url") or "").strip()
            text = (res.get("text") or "").strip()

            if text:
                label = title or url
                chunks.append(f"[{label}]\n{text}")
            if url:
                sources.append({"title": title or url, "url": url})

        return {
            "context": "\n\n".join(chunks)[:6000],
            "sources": sources,
            "provider": "exa",
        }
    except Exception as exc:  # pragma: no cover
        print(f"[Exa error] {exc}")
        return {}


# ---------------------------------------------------------------------------
# Tavily (automatic fallback)
# ---------------------------------------------------------------------------

def tavily_search(query: str, max_results: int = 3) -> dict:
    """
    Perform a Tavily web search.

    Returns a dict with `context` and `sources`, or an empty dict if the
    key is missing or the call fails.
    """
    if not _cfg.TAVILY_API_KEY:
        return {}

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": _cfg.TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        chunks: list[str] = []
        sources: list[dict] = []

        for res in results:
            title = (res.get("title") or "").strip()
            url = (res.get("url") or "").strip()
            content = (res.get("content") or "").strip()

            if content:
                label = title or url
                chunks.append(f"[{label}]\n{content}")
            if url:
                sources.append({"title": title or url, "url": url})

        return {
            "context": "\n\n".join(chunks)[:6000],
            "sources": sources,
            "provider": "tavily",
        }
    except Exception as exc:  # pragma: no cover
        print(f"[Tavily error] {exc}")
        return {}


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 5) -> dict:
    """
    Perform a "deep research" web search.

    Tries Exa AI first (if configured); falls back to Tavily if Exa is
    unavailable or returns nothing useful. Always returns a dict with
    `context`, `sources`, and `provider` keys (all empty if no provider
    is configured or every search failed).
    """
    if not query:
        return {"context": "", "sources": [], "provider": ""}

    result = exa_search(query, max_results=max_results)
    if result and result.get("context"):
        return result

    result = tavily_search(query, max_results=max_results)
    if result and result.get("context"):
        return result

    return {"context": "", "sources": [], "provider": ""}


def format_sources(sources: list[dict]) -> str:
    """
    Render a `Sources` section in Markdown, ready to append to an
    AI answer. Returns "" if `sources` is empty.
    """
    if not sources:
        return ""

    lines = ["\n\n---\n**Sources:**"]
    for i, src in enumerate(sources, 1):
        title = src.get("title") or src.get("url")
        url = src.get("url")
        if url:
            lines.append(f"{i}. [{title}]({url})")
        else:
            lines.append(f"{i}. {title}")
    return "\n".join(lines)
