import json
from pathlib import Path


def load_catalog(sources_path: str) -> list[dict]:
    catalog_path = Path(sources_path) / "catalog.json"
    if not catalog_path.exists():
        return []
    with open(catalog_path, encoding="utf-8") as f:
        return json.load(f).get("agencies", [])


def _load_quality_definition(sources_path: str, jurisdiction: str, agency_code: str) -> dict:
    qd_path = Path(sources_path) / jurisdiction / agency_code / "quality_definition.json"
    if not qd_path.exists():
        return {}
    with open(qd_path, encoding="utf-8") as f:
        return json.load(f)


def get_all_scopes(sources_path: str) -> list[str]:
    scopes: set[str] = set()
    for entry in load_catalog(sources_path):
        ps = entry.get("program_scope", [])
        if isinstance(ps, list):
            scopes.update(ps)
        elif isinstance(ps, str):
            scopes.add(ps)
    return sorted(scopes)


def load_agencies_with_quality(
    sources_path: str,
    scope_filter: list[str] | None = None,
) -> list[dict]:
    """
    Load all agencies from catalog and merge with their quality_definition.json.
    Optionally filter by program_scope values.
    """
    results = []
    for entry in load_catalog(sources_path):
        parts = Path(entry["metadata_path"]).parts
        jurisdiction, agency_code = parts[0], parts[1]

        if scope_filter:
            ps = entry.get("program_scope", [])
            if isinstance(ps, str):
                ps = [ps]
            if not any(s in ps for s in scope_filter):
                continue

        qd = _load_quality_definition(sources_path, jurisdiction, agency_code)

        results.append({
            "agency_code": entry.get("agency_code", agency_code),
            "agency_name": entry.get("agency_name", ""),
            "full_name": entry.get("full_name", ""),
            "jurisdiction": jurisdiction,
            "program_scope": entry.get("program_scope", []),
            "definition_of_quality": qd.get("definition_of_quality", ""),
            "core_quality_dimensions": qd.get("core_quality_dimensions", []),
            "curriculum_requirements": qd.get("curriculum_requirements", []),
            "what_agencies_measure": qd.get("what_agencies_measure", []),
            "best_practices_for_programs": qd.get("best_practices_for_programs", []),
        })

    return results
