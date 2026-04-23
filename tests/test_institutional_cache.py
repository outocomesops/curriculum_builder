import json
from pathlib import Path

from utils import institutional_cache as ic


DOCS = [
    {"filename": "a.pdf", "char_count": 100},
    {"filename": "b.pdf", "char_count": 200},
]


def test_safe_name_strips_specials():
    assert ic._safe_name("Acme University!") == "Acme_University"
    assert ic._safe_name("  spaces  ") == "spaces"
    # Hyphens preserved
    assert ic._safe_name("Tech-Institute") == "Tech-Institute"


def test_fingerprint_is_order_independent():
    a = ic._fingerprint(DOCS)
    b = ic._fingerprint(list(reversed(DOCS)))
    assert a == b


def test_fingerprint_changes_on_content_change():
    fp1 = ic._fingerprint(DOCS)
    changed = [{"filename": "a.pdf", "char_count": 999}, {"filename": "b.pdf", "char_count": 200}]
    fp2 = ic._fingerprint(changed)
    assert fp1 != fp2


def test_cache_path_composition(tmp_path: Path):
    p = ic.cache_path(tmp_path, "My University")
    assert p == tmp_path / "My_University" / "institutional_summary.json"


def test_save_and_load_cache_roundtrip(tmp_path: Path):
    saved_path = ic.save_cache(tmp_path, "My University", DOCS, "Summary text.")
    assert saved_path.exists()

    # Validate stored payload structure
    payload = json.loads(saved_path.read_text(encoding="utf-8"))
    assert payload["institution_name"] == "My University"
    assert payload["doc_count"] == 2
    assert payload["consolidated_summary"] == "Summary text."
    assert set(payload["doc_files"]) == {"a.pdf", "b.pdf"}

    loaded = ic.load_cache(tmp_path, "My University", DOCS)
    assert loaded == "Summary text."


def test_load_cache_returns_none_for_missing(tmp_path: Path):
    assert ic.load_cache(tmp_path, "Unknown", DOCS) is None


def test_load_cache_invalidates_when_docs_change(tmp_path: Path):
    ic.save_cache(tmp_path, "My U", DOCS, "S")
    # A different set of docs must invalidate the cache (fingerprint mismatch)
    other = DOCS + [{"filename": "c.pdf", "char_count": 50}]
    assert ic.load_cache(tmp_path, "My U", other) is None


def test_load_cache_handles_corrupt_json(tmp_path: Path):
    path = ic.cache_path(tmp_path, "BadJSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")
    assert ic.load_cache(tmp_path, "BadJSON", DOCS) is None
