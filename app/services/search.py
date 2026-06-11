"""
app/services/search.py
======================
Tavily web-search integration.
Returns plain-text snippets ready to inject into the AI prompt.
"""

import requests

from app.config.settings import Config

_cfg = Config()

def tavily_search(query: str, max_results: int = 3) -> str:
    """
    Perform a Tavily web search and return concatenated result snippets.

    Parameters
    ----------
    query : The search query string.
    max_results : Maximum number of results to fetch.

    Returns
    -------
    str
        Up to 4 000 characters of combined result content,
        or an empty string if the key is missing or the call fails.
    """
    if not _cfg.TAVILY_API_KEY:
        return ""

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
        chunks = [res.get("content", "") for res in data.get("results", [])]
        return "\n\n".join(filter(None, chunks))[:4000]
    except Exception as exc:  # pragma: no cover
        print(f"[Tavily error] {exc}")
        return ""
