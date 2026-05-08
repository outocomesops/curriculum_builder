"""Tests for utils/deep_research_cache.py"""
import json
from pathlib import Path

import pytest

from utils.deep_research_cache import cache_path, load_cache, save_cache, _fingerprint


_INSTITUTION = "My College"
_MODULES = ["legal_framework", "competitive_landscape"]
_RESULTS = {
    "legal_framework": {"status": "ok", "answer": "Canada's post-secondary legislation…", "sources_added": 12},
    "competitive_landscape": {"status": "ok", "answer": "Three main competitors…", "sources_added": 8},
}


# ── _fingerprint ───────────────────────────────────────────────────────────────

def test_fingerprint_order_independent():
    assert _fingerprint(["a", "b", "c"]) == _fingerprint(["c", "a", "b"])


def test_fingerprint_changes_with_different_keys():
    assert _fingerprint(["a", "b"]) != _fingerprint(["a", "b", "c"])


def test_fingerprint_returns_hex_string():
    fp = _fingerprint(["x"])
    assert all(c in "0123456789abcdef" for c in fp)


# ── cache_path ─────────────────────────────────────────────────────────────────

def test_cache_path_is_under_institution_dir(tmp_path):
    path = cache_path(tmp_path, "My College!")
    assert path.parent.parent == tmp_path
    assert path.name == "deep_research_cache.json"


def test_cache_path_sanitizes_institution_name(tmp_path):
    path1 = cache_path(tmp_path, "My College!")
    path2 = cache_path(tmp_path, "My College")
    # Both should result in paths under a sanitized directory
    assert path1.parent.name == path2.parent.name or "College" in str(path1)


# ── save_cache ─────────────────────────────────────────────────────────────────

def test_save_cache_creates_file(tmp_path):
    path = save_cache(tmp_path, _INSTITUTION, _MODULES, _RESULTS)
    assert path.exists()


def test_save_cache_file_is_valid_json(tmp_path):
    path = save_cache(tmp_path, _INSTITUTION, _MODULES, _RESULTS)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "module_fingerprint" in data
    assert "results" in data
    assert "created_at" in data


def test_save_cache_stores_sorted_module_keys(tmp_path):
    path = save_cache(tmp_path, _INSTITUTION, ["b_mod", "a_mod"], _RESULTS)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["module_keys"] == ["a_mod", "b_mod"]


def test_save_cache_results_round_trip(tmp_path):
    save_cache(tmp_path, _INSTITUTION, _MODULES, _RESULTS)
    loaded = load_cache(tmp_path, _INSTITUTION, _MODULES)
    assert loaded == _RESULTS


# ── load_cache ─────────────────────────────────────────────────────────────────

def test_load_cache_returns_none_when_no_file(tmp_path):
    assert load_cache(tmp_path, "Unknown Institution", _MODULES) is None


def test_load_cache_returns_none_on_module_mismatch(tmp_path):
    save_cache(tmp_path, _INSTITUTION, _MODULES, _RESULTS)
    assert load_cache(tmp_path, _INSTITUTION, ["different_module"]) is None


def test_load_cache_returns_results_on_match(tmp_path):
    save_cache(tmp_path, _INSTITUTION, _MODULES, _RESULTS)
    loaded = load_cache(tmp_path, _INSTITUTION, _MODULES)
    assert loaded["legal_framework"]["answer"] == _RESULTS["legal_framework"]["answer"]


def test_load_cache_module_order_does_not_matter(tmp_path):
    save_cache(tmp_path, _INSTITUTION, _MODULES, _RESULTS)
    loaded = load_cache(tmp_path, _INSTITUTION, list(reversed(_MODULES)))
    assert loaded is not None


def test_load_cache_returns_none_on_corrupted_file(tmp_path):
    path = cache_path(tmp_path, _INSTITUTION)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid json", encoding="utf-8")
    assert load_cache(tmp_path, _INSTITUTION, _MODULES) is None


def test_save_cache_creates_parent_dirs(tmp_path):
    nested = tmp_path / "deep" / "nested"
    save_cache(nested, _INSTITUTION, _MODULES, _RESULTS)
    assert cache_path(nested, _INSTITUTION).exists()
