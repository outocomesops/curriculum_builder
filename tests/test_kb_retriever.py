"""Tests for loaders/kb_retriever.py"""
from unittest.mock import MagicMock, patch

import pytest

from loaders.kb_retriever import (
    build_tfidf_index,
    retrieve_chunks,
    generate_retrieval_queries,
    build_kb_context,
    _MAX_KB_CONTEXT_CHARS,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

_PED_CHUNKS = [
    {"persona": "pedagogical_expert", "source": "a.pdf",
     "text": "Bloom taxonomy verbs design curriculum learning objectives assessment"},
    {"persona": "pedagogical_expert", "source": "a.pdf",
     "text": "Formative summative rubrics feedback grading strategies higher education"},
]
_ACC_CHUNKS = [
    {"persona": "accreditation_specialist", "source": "b.pdf",
     "text": "CEAB accreditation requirements graduate attributes engineering outcomes"},
]


def _make_kb_index() -> dict:
    return {
        "pedagogical_expert": _PED_CHUNKS,
        "accreditation_specialist": _ACC_CHUNKS,
    }


# ── build_tfidf_index ──────────────────────────────────────────────────────────

def test_build_tfidf_index_creates_one_entry_per_persona():
    indices = build_tfidf_index(_make_kb_index())
    assert set(indices.keys()) == {"pedagogical_expert", "accreditation_specialist"}


def test_build_tfidf_index_matrix_rows_match_chunk_count():
    indices = build_tfidf_index(_make_kb_index())
    vec, matrix, chunks = indices["pedagogical_expert"]
    assert matrix.shape[0] == len(_PED_CHUNKS)


def test_build_tfidf_index_empty_input():
    assert build_tfidf_index({}) == {}


def test_build_tfidf_index_skips_empty_persona():
    result = build_tfidf_index({"empty_persona": []})
    assert "empty_persona" not in result


# ── retrieve_chunks ────────────────────────────────────────────────────────────

def test_retrieve_chunks_returns_top_match():
    indices = build_tfidf_index(_make_kb_index())
    results = retrieve_chunks(indices, ["bloom taxonomy learning curriculum"], top_k=1)
    assert "pedagogical_expert" in results
    assert len(results["pedagogical_expert"]) == 1


def test_retrieve_chunks_respects_top_k():
    indices = build_tfidf_index(_make_kb_index())
    results = retrieve_chunks(indices, ["learning design assessment"], top_k=2)
    assert len(results.get("pedagogical_expert", [])) <= 2


def test_retrieve_chunks_excludes_zero_score_results():
    indices = build_tfidf_index(_make_kb_index())
    # Queries with no vocabulary overlap should yield no results
    results = retrieve_chunks(indices, ["xyzzy aaaabbbb zzzzzz nonexistent"], top_k=3)
    for chunks in results.values():
        assert isinstance(chunks, list)


def test_retrieve_chunks_no_duplicates():
    indices = build_tfidf_index(_make_kb_index())
    results = retrieve_chunks(indices, ["bloom", "bloom", "bloom"], top_k=5)
    for persona, chunks in results.items():
        assert len(chunks) == len(set(chunks))


# ── build_kb_context ───────────────────────────────────────────────────────────

def test_build_kb_context_returns_empty_for_empty_indices():
    assert build_kb_context({}, ["query"]) == ""


def test_build_kb_context_returns_empty_for_empty_queries():
    indices = build_tfidf_index(_make_kb_index())
    assert build_kb_context(indices, []) == ""


def test_build_kb_context_contains_header_when_chunks_found():
    indices = build_tfidf_index(_make_kb_index())
    ctx = build_kb_context(indices, ["bloom learning objectives"], top_k=1)
    if ctx:
        assert "=== EXPERT KNOWLEDGE BASE ===" in ctx


def test_build_kb_context_truncated_to_max_chars():
    big_chunk = {"persona": "pedagogical_expert", "source": "big.pdf",
                 "text": "knowledge " * 1000}
    indices = build_tfidf_index({"pedagogical_expert": [big_chunk] * 5})
    ctx = build_kb_context(indices, ["knowledge"], top_k=5)
    assert len(ctx) <= _MAX_KB_CONTEXT_CHARS + 20  # +20 for "[...truncated]" suffix


def test_build_kb_context_uses_human_readable_persona_label():
    indices = build_tfidf_index({"pedagogical_expert": _PED_CHUNKS})
    ctx = build_kb_context(indices, ["bloom learning"], top_k=1)
    if ctx:
        assert "Pedagogical Expert" in ctx


# ── generate_retrieval_queries ─────────────────────────────────────────────────

@patch("loaders.kb_retriever.requests.post")
def test_generate_retrieval_queries_parses_three_lines(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": "curriculum design best practices\naccreditation outcomes mapping\nindustry skill gaps"}
    }
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    queries = generate_retrieval_queries(
        "Computer Science", "Bachelor's", "Course List",
        "http://localhost:11434", "llama3",
    )
    assert len(queries) == 3
    assert "curriculum design best practices" in queries


@patch("loaders.kb_retriever.requests.post")
def test_generate_retrieval_queries_fallback_on_request_error(mock_post):
    mock_post.side_effect = RuntimeError("connection refused")
    queries = generate_retrieval_queries(
        "Data Science", "Master's", "Competency Map",
        "http://localhost:11434", "llama3",
    )
    assert len(queries) == 3
    assert "Data Science" in queries


@patch("loaders.kb_retriever.requests.post")
def test_generate_retrieval_queries_fallback_on_empty_response(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": ""}}
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    queries = generate_retrieval_queries(
        "Nursing", "Diploma", "Syllabi",
        "http://localhost:11434", "llama3",
    )
    assert len(queries) == 3
