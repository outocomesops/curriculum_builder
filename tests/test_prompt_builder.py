import pandas as pd

from generator import prompt_builder as pb


def test_build_skills_context_empty_dataframe():
    assert pb.build_skills_context(pd.DataFrame()) == "No job market data available."


def test_build_skills_context_none():
    assert pb.build_skills_context(None) == "No job market data available."


def test_build_skills_context_renders_with_mention_rate():
    df = pd.DataFrame(
        [
            {"skill_name": "Python", "skill_type": "tool", "mention_rate": 66.7},
            {"skill_name": "SQL",    "skill_type": "tool", "mention_rate": 40.0},
        ]
    )
    ctx = pb.build_skills_context(df)
    assert "Python" in ctx
    assert "SQL" in ctx
    assert "66.7%" in ctx
    assert "Top 2 in-demand skills" in ctx


def test_build_skills_context_respects_top_n():
    df = pd.DataFrame(
        [{"skill_name": f"Skill{i}", "skill_type": "tool", "mention_rate": 10} for i in range(50)]
    )
    ctx = pb.build_skills_context(df, top_n=3)
    assert "Top 3" in ctx
    assert "Skill0" in ctx and "Skill2" in ctx
    assert "Skill3" not in ctx


def test_build_accreditation_context_empty():
    assert pb.build_accreditation_context([]) == "No accreditation standards selected."


def test_build_accreditation_context_renders_all_fields():
    agencies = [
        {
            "agency_name": "Agency A",
            "jurisdiction": "us",
            "definition_of_quality": "Quality def.",
            "curriculum_requirements": ["req1", "req2"],
            "core_quality_dimensions": ["dim1"],
            "best_practices_for_programs": ["bp1"],
        }
    ]
    ctx = pb.build_accreditation_context(agencies)
    assert "### Agency A (US)" in ctx
    assert "Quality def." in ctx
    assert "req1" in ctx and "req2" in ctx
    assert "dim1" in ctx and "bp1" in ctx


def test_build_accreditation_context_skips_missing_optional():
    agencies = [{
        "agency_name": "Agency B", "jurisdiction": "uk",
        "definition_of_quality": "",
        "curriculum_requirements": [],
        "core_quality_dimensions": [],
        "best_practices_for_programs": [],
    }]
    ctx = pb.build_accreditation_context(agencies)
    assert "### Agency B (UK)" in ctx
    assert "Quality philosophy" not in ctx
    assert "Curriculum requirements" not in ctx


def test_build_institutional_context_prefers_consolidated():
    out = pb.build_institutional_context("Consolidated text.", [{"has_content": True, "summary": "X", "filename": "f"}])
    assert "Consolidated institutional profile" in out
    assert "Consolidated text." in out
    assert "Source:" not in out


def test_build_institutional_context_fallback_to_summaries():
    out = pb.build_institutional_context("", [
        {"has_content": True, "summary": "sum A", "filename": "a.pdf"},
        {"has_content": False, "summary": "", "filename": "b.pdf"},
    ])
    assert "Source: a.pdf" in out
    assert "sum A" in out
    assert "b.pdf" not in out


def test_build_institutional_context_empty_fallback():
    assert pb.build_institutional_context("", None) == "No institutional documentation provided."
    assert pb.build_institutional_context("", []) == "No institutional documentation provided."
    assert pb.build_institutional_context("   ", [{"has_content": False, "summary": ""}]) == (
        "No institutional documentation provided."
    )


def test_build_program_specs_context_empty():
    assert pb.build_program_specs_context([]) == "No program specification documents provided."


def test_build_program_specs_context_skips_errors_and_empty():
    docs = [
        {"filename": "a.txt", "file_type": "text", "text": "Alpha content", "char_count": 13, "error": None},
        {"filename": "b.txt", "file_type": "text", "text": "", "char_count": 0, "error": "bad"},
    ]
    ctx = pb.build_program_specs_context(docs)
    assert "Alpha content" in ctx
    assert "b.txt" not in ctx


def test_build_program_specs_context_truncates_on_max_chars():
    big = "X" * 5000
    docs = [
        {"filename": "a.txt", "file_type": "text", "text": big, "char_count": len(big), "error": None},
        {"filename": "b.txt", "file_type": "text", "text": big, "char_count": len(big), "error": None},
        {"filename": "c.txt", "file_type": "text", "text": big, "char_count": len(big), "error": None},
    ]
    ctx = pb.build_program_specs_context(docs, max_chars=1000)
    assert len(ctx) < 1500 + 500  # some headers/truncation overhead
    assert ("truncated" in ctx) or ("..." in ctx)


def test_build_reputation_context_empty():
    assert pb.build_reputation_context("") == "No public reputation data available."
    assert pb.build_reputation_context("   ") == "No public reputation data available."


def test_build_reputation_context_renders_summary():
    ctx = pb.build_reputation_context("Well-regarded university.")
    assert "Well-regarded university." in ctx
    assert "Public perception" in ctx
