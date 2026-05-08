"""
Cache for deep research module results between browser sessions.

Saves to: INSTITUTIONS_DIR/{institution}/deep_research_cache.json
Cache is valid as long as institution name and set of module keys match.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def _fingerprint(module_keys: list[str]) -> str:
    """Stable hash of the sorted module keys that were run."""
    return hashlib.md5(str(sorted(module_keys)).encode()).hexdigest()


def cache_path(institutions_dir: Path, institution_name: str) -> Path:
    return institutions_dir / _safe_name(institution_name) / "deep_research_cache.json"


def load_cache(
    institutions_dir: Path,
    institution_name: str,
    module_keys: list[str],
) -> dict | None:
    """
    Return cached deep_research_results dict if it exists and the module set matches.
    Returns None if no valid cache found.
    """
    path = cache_path(institutions_dir, institution_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("module_fingerprint") == _fingerprint(module_keys):
            return data.get("results")
    except Exception:
        pass
    return None


def save_cache(
    institutions_dir: Path,
    institution_name: str,
    module_keys: list[str],
    results: dict,
) -> Path:
    """Persist deep research results to disk. Returns the file path written."""
    path = cache_path(institutions_dir, institution_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "institution_name": institution_name,
        "created_at": datetime.now().isoformat(),
        "module_fingerprint": _fingerprint(module_keys),
        "module_keys": sorted(module_keys),
        "results": results,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
