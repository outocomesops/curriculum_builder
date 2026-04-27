from types import SimpleNamespace

from generator.bloom_prompt_builder import build_improvement_prompt
from loaders.bloom_outcome_extractor import OutcomeRecord


def test_build_improvement_prompt_for_program_level_outcome():
    outcome = OutcomeRecord("PEO-1", "Apply engineering ethics.", "PEO", None, None, None, "ctx")
    analysis = SimpleNamespace(
        classification=SimpleNamespace(bloom_level="apply", bloom_level_num=3),
        issues=["Verb is weak."],
        suggested_verbs=["demonstrate", "implement"],
    )
    bloom_data = {
        "levels": {"apply": {"description": "Use knowledge", "verbs": ["apply", "demonstrate", "implement"]}}
    }
    prompt = build_improvement_prompt(
        outcome,
        analysis,
        {"institution": "My College", "program": "BASc", "level": "undergraduate", "top_skills": ["Python"]},
        bloom_data,
    )
    assert "My College" in prompt
    assert "program-level program educational objective" in prompt
    assert "Suggested verbs for this level: demonstrate, implement" in prompt


def test_build_improvement_prompt_for_course_level_outcome():
    outcome = OutcomeRecord("SLO-2", "Design APIs.", "SLO", "CS101", "Intro", 1, "ctx")
    analysis = SimpleNamespace(
        classification=SimpleNamespace(bloom_level="create", bloom_level_num=6),
        issues=[],
        suggested_verbs=[],
    )
    bloom_data = {
        "levels": {"create": {"description": "Create artifacts", "verbs": ["design", "build", "construct"]}}
    }
    prompt = build_improvement_prompt(outcome, analysis, {"program": "BASc"}, bloom_data)
    assert "CS101" in prompt
    assert "Year 1" in prompt
    assert "Target Bloom's level: Create (Level 6)" in prompt
