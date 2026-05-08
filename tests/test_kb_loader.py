"""Tests for loaders/kb_loader.py"""
from pathlib import Path
from unittest.mock import patch

import pytest

from loaders.kb_loader import _chunk_text, _extract_pdf_text, load_kb_index, total_chunks


# ── _chunk_text ────────────────────────────────────────────────────────────────

def test_chunk_text_splits_long_text():
    text = " ".join(["word"] * 300)
    chunks = _chunk_text(text, chunk_size=100)
    assert len(chunks) > 1


def test_chunk_text_filters_short_chunks():
    # Each chunk < 50 chars must be dropped
    chunks = _chunk_text("tiny text here ok", chunk_size=500)
    assert chunks == []


def test_chunk_text_empty_string():
    assert _chunk_text("") == []


def test_chunk_text_preserves_content():
    text = " ".join(["alpha"] * 200)
    chunks = _chunk_text(text, chunk_size=100)
    for chunk in chunks:
        assert "alpha" in chunk


def test_chunk_text_minimum_chunk_length():
    text = " ".join(["word"] * 100)
    chunks = _chunk_text(text, chunk_size=200)
    for chunk in chunks:
        assert len(chunk.strip()) > 50


# ── total_chunks ───────────────────────────────────────────────────────────────

def test_total_chunks_sums_across_personas():
    index = {"persona_a": [{"text": "x"}] * 7, "persona_b": [{"text": "y"}] * 3}
    assert total_chunks(index) == 10


def test_total_chunks_empty_index():
    assert total_chunks({}) == 0


# ── _extract_pdf_text ──────────────────────────────────────────────────────────

def test_extract_pdf_text_missing_file_returns_empty():
    result = _extract_pdf_text(Path("/nonexistent/path/file.pdf"))
    assert result == ""


def test_extract_pdf_text_invalid_bytes_returns_empty(tmp_path):
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"not a real pdf")
    result = _extract_pdf_text(bad_pdf)
    assert result == ""


# ── load_kb_index ──────────────────────────────────────────────────────────────

def test_load_kb_index_missing_root_returns_empty():
    result = load_kb_index(kb_root=Path("/nonexistent/kb_root"))
    assert result == {}


def test_load_kb_index_skips_directory_without_sources(tmp_path):
    (tmp_path / "pedagogical_expert").mkdir()
    result = load_kb_index(kb_root=tmp_path)
    assert "pedagogical_expert" not in result


def test_load_kb_index_skips_sources_dir_with_no_pdfs(tmp_path):
    sources = tmp_path / "pedagogical_expert" / "sources"
    sources.mkdir(parents=True)
    (sources / "notes.txt").write_text("some notes")
    result = load_kb_index(kb_root=tmp_path)
    assert "pedagogical_expert" not in result


def test_load_kb_index_skips_skip_persona(tmp_path):
    sources = tmp_path / "institutional_fit_reviewer" / "sources"
    sources.mkdir(parents=True)
    (sources / "doc.pdf").write_bytes(b"%PDF-1.4 fake")
    result = load_kb_index(kb_root=tmp_path)
    assert "institutional_fit_reviewer" not in result


@patch("loaders.kb_loader._extract_pdf_text")
def test_load_kb_index_builds_chunks_for_persona(mock_extract, tmp_path):
    sources = tmp_path / "pedagogical_expert" / "sources"
    sources.mkdir(parents=True)
    (sources / "doc.pdf").write_bytes(b"%PDF fake")
    mock_extract.return_value = " ".join(["knowledge"] * 200)

    result = load_kb_index(kb_root=tmp_path)
    assert "pedagogical_expert" in result
    assert len(result["pedagogical_expert"]) > 0
    first = result["pedagogical_expert"][0]
    assert first["persona"] == "pedagogical_expert"
    assert first["source"] == "doc.pdf"
    assert "knowledge" in first["text"]


@patch("loaders.kb_loader._extract_pdf_text")
def test_load_kb_index_skips_empty_pdf(mock_extract, tmp_path):
    sources = tmp_path / "pedagogical_expert" / "sources"
    sources.mkdir(parents=True)
    (sources / "empty.pdf").write_bytes(b"%PDF fake")
    mock_extract.return_value = ""

    result = load_kb_index(kb_root=tmp_path)
    assert "pedagogical_expert" not in result


@patch("loaders.kb_loader._extract_pdf_text")
def test_load_kb_index_multiple_personas(mock_extract, tmp_path):
    for persona in ("pedagogical_expert", "accreditation_specialist"):
        sources = tmp_path / persona / "sources"
        sources.mkdir(parents=True)
        (sources / "doc.pdf").write_bytes(b"%PDF fake")
    mock_extract.return_value = " ".join(["content"] * 200)

    result = load_kb_index(kb_root=tmp_path)
    assert "pedagogical_expert" in result
    assert "accreditation_specialist" in result
