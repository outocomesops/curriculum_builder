from pathlib import Path

from loaders import bloom_loader as bl


def test_load_bloom_files_and_build_indexes(tmp_path):
    bloom_file = tmp_path / "bloom.json"
    weak_file = tmp_path / "weak.json"
    bloom_file.write_text(
        """
{
  "levels": {
    "apply": {"cognitive_level": 3, "description": "Use", "verbs": ["apply", "execute"]},
    "evaluate": {"cognitive_level": 5, "description": "Judge", "verbs": ["evaluate"]}
  }
}
""".strip(),
        encoding="utf-8",
    )
    weak_file.write_text(
        """
{
  "weak_verbs": [
    {"verb": "understand", "reason": "too vague", "alternatives_by_level": {"apply": ["demonstrate"]}}
  ]
}
""".strip(),
        encoding="utf-8",
    )

    original_bloom = bl._BLOOM_VERBS_FILE
    original_weak = bl._WEAK_VERBS_FILE
    bl._BLOOM_VERBS_FILE = Path(bloom_file)
    bl._WEAK_VERBS_FILE = Path(weak_file)
    try:
        bloom_data = bl.load_bloom_verbs()
        weak_data = bl.load_weak_verbs()
        verb_index = bl.build_verb_index(bloom_data)
        weak_lookup = bl.build_weak_verb_lookup(weak_data)
        metadata = bl.get_level_metadata(bloom_data)
        combo_index, combo_weak, combo_bloom = bl.load_bloom_taxonomy()
    finally:
        bl._BLOOM_VERBS_FILE = original_bloom
        bl._WEAK_VERBS_FILE = original_weak

    assert verb_index["apply"] == "apply"
    assert verb_index["execute"] == "apply"
    assert weak_lookup["understand"]["reason"] == "too vague"
    assert metadata["evaluate"]["cognitive_level"] == 5
    assert combo_index == verb_index
    assert combo_weak == weak_lookup
    assert combo_bloom == bloom_data
