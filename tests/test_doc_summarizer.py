from unittest.mock import patch

import requests

from generator import doc_summarizer as ds
from tests.conftest import FakeResponse


@patch("generator.doc_summarizer.requests.post")
def test_summarize_doc_returns_summary(mock_post):
    mock_post.return_value = FakeResponse(
        json_data={"message": {"content": "Mission is clarity."}}, status_code=200
    )
    result = ds.summarize_doc("text body", "mission.txt", "http://x", "llama")
    assert result["filename"] == "mission.txt"
    assert result["has_content"] is True
    assert result["summary"] == "Mission is clarity."


@patch("generator.doc_summarizer.requests.post")
def test_summarize_doc_no_content_marker(mock_post):
    mock_post.return_value = FakeResponse(
        json_data={"message": {"content": "NO_CONTENT"}}, status_code=200
    )
    result = ds.summarize_doc("irrelevant", "other.txt", "http://x", "llama")
    assert result["has_content"] is False
    assert result["summary"] == ""


@patch("generator.doc_summarizer.requests.post")
def test_summarize_doc_handles_http_error(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("unreachable")
    result = ds.summarize_doc("text", "f.txt", "http://x", "m")
    assert result["has_content"] is False
    assert "error" in result
    assert "unreachable" in result["error"]


@patch("generator.doc_summarizer.requests.post")
def test_summarize_doc_truncates_excerpt(mock_post):
    captured = {}

    def record(*args, **kwargs):
        captured["json"] = kwargs.get("json")
        return FakeResponse(json_data={"message": {"content": "ok"}}, status_code=200)

    mock_post.side_effect = record
    sentinel = "\u2603" * 10_000  # use a character not present in the prompt template
    ds.summarize_doc(sentinel, "f.txt", "http://x", "m")
    prompt = captured["json"]["messages"][0]["content"]
    count = prompt.count("\u2603")
    # Loader caps the excerpt at 4500 characters before formatting into the prompt
    assert count == 4500


@patch("generator.doc_summarizer.summarize_doc")
def test_batch_summarize_invokes_per_doc_and_progress(mock_sum):
    mock_sum.side_effect = lambda text, fn, url, model: {
        "filename": fn, "summary": f"s-{fn}", "has_content": True
    }
    docs = [{"text": "a", "filename": "1"}, {"text": "b", "filename": "2"}]
    calls = []
    results = ds.batch_summarize(docs, "http://x", "m", progress_callback=lambda i, t, n: calls.append((i, t, n)))
    assert len(results) == 2
    assert results[0]["summary"] == "s-1"
    assert calls == [(1, 2, "1"), (2, 2, "2")]


def test_consolidate_summaries_empty_returns_empty():
    assert ds.consolidate_summaries([], "http://x", "m") == ""
    assert ds.consolidate_summaries([{"has_content": False, "summary": ""}], "http://x", "m") == ""


@patch("generator.doc_summarizer.requests.post")
def test_consolidate_summaries_returns_text(mock_post):
    mock_post.return_value = FakeResponse(
        json_data={"message": {"content": "Consolidated profile."}}, status_code=200
    )
    out = ds.consolidate_summaries(
        [{"has_content": True, "summary": "piece", "filename": "f.pdf"}],
        "http://x",
        "m",
    )
    assert out == "Consolidated profile."


@patch("generator.doc_summarizer.requests.post")
def test_consolidate_summaries_http_error(mock_post):
    mock_post.side_effect = RuntimeError("boom")
    out = ds.consolidate_summaries(
        [{"has_content": True, "summary": "p", "filename": "f"}],
        "http://x",
        "m",
    )
    assert out.startswith("Consolidation failed")


@patch("generator.doc_summarizer.requests.post")
def test_summarize_reputation_no_usable_sources(mock_post):
    out = ds.summarize_reputation("MyUni", [], "http://x", "m")
    assert "No reputation data" in out
    mock_post.assert_not_called()


@patch("generator.doc_summarizer.requests.post")
def test_summarize_reputation_with_snippets(mock_post):
    mock_post.return_value = FakeResponse(
        json_data={"message": {"content": "Reputation is strong."}}, status_code=200
    )
    snippets = [{"title": "Review", "snippet": "Praised curriculum"}]
    out = ds.summarize_reputation("MyUni", snippets, "http://x", "m")
    assert "strong" in out


@patch("generator.doc_summarizer.requests.post")
def test_summarize_reputation_error(mock_post):
    mock_post.side_effect = RuntimeError("net down")
    out = ds.summarize_reputation(
        "MyUni", [{"title": "t", "text": "some text"}], "http://x", "m"
    )
    assert out.startswith("Reputation analysis failed")
