from pathlib import Path

from loaders import quality_loader


def test_load_catalog_missing_returns_empty(tmp_path: Path):
    assert quality_loader.load_catalog(str(tmp_path)) == []


def test_load_catalog_returns_agencies(tmp_quality_sources: Path):
    catalog = quality_loader.load_catalog(str(tmp_quality_sources))
    assert isinstance(catalog, list)
    assert len(catalog) == 2
    codes = [a["agency_code"] for a in catalog]
    assert "ABC" in codes and "XYZ" in codes


def test_get_all_scopes_merges_list_and_string(tmp_quality_sources: Path):
    scopes = quality_loader.get_all_scopes(str(tmp_quality_sources))
    assert scopes == sorted(scopes)
    for expected in ("engineering", "computing", "business"):
        assert expected in scopes


def test_load_agencies_with_quality_no_filter(tmp_quality_sources: Path):
    agencies = quality_loader.load_agencies_with_quality(str(tmp_quality_sources))
    assert len(agencies) == 2

    abc = next(a for a in agencies if a["agency_code"] == "ABC")
    assert abc["definition_of_quality"].startswith("High quality")
    assert "math core" in abc["curriculum_requirements"]
    assert abc["jurisdiction"] == "us"

    # XYZ has no quality_definition.json — should default to empty fields
    xyz = next(a for a in agencies if a["agency_code"] == "XYZ")
    assert xyz["definition_of_quality"] == ""
    assert xyz["core_quality_dimensions"] == []


def test_load_agencies_with_quality_scope_filter(tmp_quality_sources: Path):
    only_eng = quality_loader.load_agencies_with_quality(
        str(tmp_quality_sources), scope_filter=["engineering"]
    )
    assert len(only_eng) == 1
    assert only_eng[0]["agency_code"] == "ABC"

    only_biz = quality_loader.load_agencies_with_quality(
        str(tmp_quality_sources), scope_filter=["business"]
    )
    assert len(only_biz) == 1
    assert only_biz[0]["agency_code"] == "XYZ"

    none_match = quality_loader.load_agencies_with_quality(
        str(tmp_quality_sources), scope_filter=["art"]
    )
    assert none_match == []
