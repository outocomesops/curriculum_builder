from pathlib import Path

import pandas as pd

from exporter import curriculum_exporter as ce


def _base_export_kwargs():
    skills_df = pd.DataFrame(
        [
            {"skill_name": "Python", "skill_type": "tool", "job_count": 10, "mention_rate": 0.4},
            {"skill_name": "SQL", "skill_type": "tool", "job_count": 8, "mention_rate": 0.3},
        ]
    )
    return dict(
        institution_name="My College!",
        program_name="BASc Software Engineering",
        program_level="Undergraduate",
        language="English",
        course_hours=45,
        skills_df=skills_df,
        top_n=1,
        agencies=[],
        institutional_docs=[{"filename": "mission.pdf", "char_count": 1000}],
        consolidated_summary="summary",
        reputation_snippets=[{"title": "snippet"}],
        reputation_summary="rep summary",
        program_specs_docs=[{"filename": "spec.docx", "file_type": "docx", "char_count": 200}],
        deep_research_results={"legal_framework": {"status": "ok", "answer": "x", "sources_added": 3}},
        learning_outcomes="los",
        course_list="**CS101 Intro to Programming**",
        competency_map="map",
        syllabi={"CS101": "syllabus"},
    )


def test_sanitize_folder_removes_punctuation():
    assert ce._sanitize_folder("My College! @ 2026") == "My_College__2026"


def test_build_curriculum_export_without_pedagogy_uses_schema_1():
    data = ce.build_curriculum_export(**_base_export_kwargs())
    assert data["schema_version"] == "1.0"
    assert data["inputs"]["skills"]["top_n_used"] == 1
    assert data["curriculum"]["course_list"]["courses_detected"][0]["code"] == "CS101"


def test_build_curriculum_export_with_pedagogy_uses_schema_2():
    kwargs = _base_export_kwargs()
    kwargs["analysis_results"] = [object()]
    kwargs["coverage"] = object()
    original_builder = ce.build_pedagogy_block
    ce.build_pedagogy_block = lambda *_args, **_kwargs: {"coverage_score": 0.5}
    try:
        data = ce.build_curriculum_export(**kwargs)
    finally:
        ce.build_pedagogy_block = original_builder
    assert data["schema_version"] == "2.0"
    assert "pedagogy" in data


def test_save_curriculum_export_writes_expected_path(tmp_path):
    export_data = {
        "metadata": {"year_month": "2026-04"},
        "schema_version": "1.0",
    }
    out = ce.save_curriculum_export(
        export_data,
        institution_name="My College!",
        program_name="BASc Software Engineering",
        base_outputs=Path(tmp_path),
    )
    assert out.name == "curriculum_export.json"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert '"schema_version": "1.0"' in text
