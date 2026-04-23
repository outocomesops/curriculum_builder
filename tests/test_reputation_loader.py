from unittest.mock import MagicMock, patch

from loaders import reputation_loader


class FakeDDGS:
    def __init__(self, results_by_query=None):
        self._results = results_by_query or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def text(self, query, max_results=5):
        # Return different results for each distinct template-filled query to exercise dedup
        for r in self._results.get(query, [])[:max_results]:
            yield r


def test_fetch_reputation_snippets_dedups_by_url():
    # All 5 queries return the same one URL — should appear only once
    shared = [{"title": "T", "href": "https://shared.example", "body": "snippet"}]
    per_query = {}
    for tpl in reputation_loader._SEARCH_QUERIES:
        per_query[tpl.format(name="MyUni")] = shared

    with patch("duckduckgo_search.DDGS", return_value=FakeDDGS(per_query)):
        result = reputation_loader.fetch_reputation_snippets("MyUni", max_results_per_query=5)
    assert len(result) == 1
    assert result[0]["url"] == "https://shared.example"
    assert result[0]["snippet"] == "snippet"


def test_fetch_reputation_snippets_handles_missing_package():
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "duckduckgo_search":
            raise ImportError("no duckduckgo")
        return real_import(name, *a, **kw)

    with patch("builtins.__import__", side_effect=fake_import):
        result = reputation_loader.fetch_reputation_snippets("MyUni")
    assert len(result) == 1
    assert "not installed" in result[0]["snippet"]


def test_fetch_reputation_snippets_continues_past_query_exception():
    class ExplodingDDGS(FakeDDGS):
        def text(self, query, max_results=5):
            if "reputation" in query:
                raise RuntimeError("boom")
            yield {"title": "OK", "href": f"https://ex.test/{query}", "body": "good"}

    with patch("duckduckgo_search.DDGS", return_value=ExplodingDDGS()):
        result = reputation_loader.fetch_reputation_snippets("MyUni")
    # Should have at least one successful result (exploding query is skipped)
    assert len(result) >= 1
    assert all(r["title"] == "OK" for r in result)
