"""
Cache for consolidated institutional document summaries.

Saves to: INSTITUTIONS_DIR/{safe_institution_name}/institutional_summary.json
The cache is valid as long as the set of documents (filenames + sizes) has not changed.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def _fingerprint(docs: list[dict]) -> str:
    """Stable hash of (filename, char_count) pairs — changes when docs are added/removed/modified."""
    key = sorted((d["filename"], d["char_count"]) for d in docs)
    return hashlib.md5(str(key).encode()).hexdigest()


def cache_path(institutions_dir: Path, institution_name: str) -> Path:
    return institutions_dir / _safe_name(institution_name) / "institutional_summary.json"


def load_cache(institutions_dir: Path, institution_name: str, docs: list[dict]) -> str | None:
    """
    Return the cached consolidated summary if it exists and matches the current docs.
    Returns None if no valid cache found.
    """
    path = cache_path(institutions_dir, institution_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("doc_fingerprint") == _fingerprint(docs):
            return data.get("consolidated_summary", "")
    except Exception:
        pass
    return None


def save_cache(
    institutions_dir: Path,
    institution_name: str,
    docs: list[dict],
    consolidated_summary: str,
) -> Path:
    """Persist the consolidated summary. Returns the file path written."""
    path = cache_path(institutions_dir, institution_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "institution_name": institution_name,
        "created_at": datetime.now().isoformat(),
        "doc_fingerprint": _fingerprint(docs),
        "doc_count": len(docs),
        "doc_files": [d["filename"] for d in docs],
        "consolidated_summary": consolidated_summary,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
