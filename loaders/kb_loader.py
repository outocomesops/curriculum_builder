"""
Knowledge Base Loader
Chunks PDFs from pedagogy_context/knowledge_bases by expert persona.
"""
from __future__ import annotations

from pathlib import Path

import pdfplumber

KB_ROOT = Path(r"C:\Users\Sebmatecho\Documents\pedagogy_context\knowledge_bases")

_SKIP_PERSONAS = {"institutional_fit_reviewer"}


def _chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    words = text.split()
    chunks, current = [], []
    current_len = 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= chunk_size:
            chunks.append(" ".join(current))
            current, current_len = [], 0
    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if len(c.strip()) > 50]


def _extract_pdf_text(pdf_path: Path, max_pages: int = 30) -> str:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = pdf.pages[:max_pages]
            return "\n".join(p.extract_text() or "" for p in pages)
    except Exception:
        return ""


def load_kb_index(
    kb_root: Path = KB_ROOT,
    chunk_size: int = 500,
) -> dict[str, list[dict]]:
    """
    Returns {persona_name: [{"persona": str, "source": str, "text": str}, ...]}.
    Skips personas with no PDFs.
    """
    index: dict[str, list[dict]] = {}

    if not kb_root.exists():
        return index

    for persona_dir in sorted(kb_root.iterdir()):
        if not persona_dir.is_dir():
            continue
        persona = persona_dir.name
        if persona in _SKIP_PERSONAS:
            continue

        sources_dir = persona_dir / "sources"
        if not sources_dir.exists():
            continue

        pdfs = sorted(sources_dir.glob("*.pdf")) + sorted(sources_dir.glob("*.PDF"))
        if not pdfs:
            continue

        chunks: list[dict] = []
        for pdf_path in pdfs:
            text = _extract_pdf_text(pdf_path)
            if not text.strip():
                continue
            for chunk in _chunk_text(text, chunk_size):
                chunks.append({
                    "persona": persona,
                    "source": pdf_path.name,
                    "text": chunk,
                })

        if chunks:
            index[persona] = chunks

    return index


def total_chunks(kb_index: dict) -> int:
    return sum(len(v) for v in kb_index.values())
