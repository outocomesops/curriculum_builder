"""
Reputation loader — searches the web for public perception of an institution
and returns raw snippets for LLM processing.
Uses DuckDuckGo (no API key required).
"""
from __future__ import annotations


_SEARCH_QUERIES = [
    '"{name}" reviews students',
    '"{name}" reputation academics',
    '"{name}" graduate outcomes employment',
    '"{name}" ranking accreditation',
    '"{name}" student experience complaints',
]


def fetch_reputation_snippets(
    institution_name: str,
    max_results_per_query: int = 5,
) -> list[dict]:
    """
    Run several DuckDuckGo searches about the institution.
    Returns list of {title, url, snippet} dicts.
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return [{"title": "Error", "url": "", "snippet": "duckduckgo-search not installed."}]

    results: list[dict] = []
    seen_urls: set[str] = set()

    with DDGS() as ddgs:
        for query_template in _SEARCH_QUERIES:
            query = query_template.format(name=institution_name)
            try:
                for r in ddgs.text(query, max_results=max_results_per_query):
                    url = r.get("href", "")
                    if url not in seen_urls:
                        seen_urls.add(url)
                        results.append({
                            "title": r.get("title", ""),
                            "url": url,
                            "snippet": r.get("body", ""),
                        })
            except Exception:
                continue

    return results
