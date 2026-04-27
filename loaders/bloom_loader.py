import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"
_BLOOM_VERBS_FILE = _DATA_DIR / "bloom_verbs.json"
_WEAK_VERBS_FILE = _DATA_DIR / "weak_verbs.json"


def load_bloom_verbs() -> dict:
    with open(_BLOOM_VERBS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_weak_verbs() -> dict:
    with open(_WEAK_VERBS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_verb_index(bloom_data: dict) -> dict[str, str]:
    index: dict[str, str] = {}
    for level_name, level_data in bloom_data["levels"].items():
        for verb in level_data["verbs"]:
            index[verb.lower()] = level_name
    return index


def build_weak_verb_lookup(weak_data: dict) -> dict[str, dict]:
    return {entry["verb"].lower(): entry for entry in weak_data["weak_verbs"]}


def get_level_metadata(bloom_data: dict) -> dict[str, dict]:
    return {
        name: {
            "cognitive_level": data["cognitive_level"],
            "description": data["description"],
        }
        for name, data in bloom_data["levels"].items()
    }


def load_bloom_taxonomy() -> tuple[dict[str, str], dict[str, dict], dict]:
    """Returns (verb_index, weak_verb_lookup, bloom_data) in one call."""
    bloom_data = load_bloom_verbs()
    weak_data = load_weak_verbs()
    return build_verb_index(bloom_data), build_weak_verb_lookup(weak_data), bloom_data
