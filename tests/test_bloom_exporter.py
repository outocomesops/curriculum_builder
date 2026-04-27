from analyzers.bloom_classifier import ClassificationResult
from analyzers.coverage_analyzer import CoverageReport
from analyzers.outcome_analyzer import AnalysisResult
from exporter.bloom_exporter import build_pedagogy_block, merge_with_curriculum


def test_build_pedagogy_block_serializes_results():
    row = AnalysisResult(
        outcome_id="SLO-1",
        outcome_type="SLO",
        course_code="CS101",
        original_text="Design software modules.",
        extracted_verb="design",
        classification=ClassificationResult("create", 6, 1.0, "keyword"),
        is_weak_verb=False,
        weak_reason=None,
        issues=[],
        suggested_verbs=["construct"],
        improved_text="Students will design software modules.",
        improvement_approved=True,
    )
    coverage = CoverageReport(
        distribution={"remember": 0, "understand": 0, "apply": 0, "analyze": 0, "evaluate": 0, "create": 1},
        coverage_score=0.167,
        missing_levels=["remember", "understand", "apply", "analyze", "evaluate"],
        weak_verb_count=0,
        unclassified_count=0,
        outcomes_analyzed=1,
        flags=[],
    )
    block = build_pedagogy_block([row], coverage)
    assert block["framework"].startswith("Bloom's Revised")
    assert block["coverage_score"] == 0.167
    assert block["outcomes"][0]["id"] == "SLO-1"
    assert block["outcomes"][0]["classification_source"] == "keyword"


def test_merge_with_curriculum_updates_schema_and_keeps_original():
    curriculum = {"schema_version": "1.0", "metadata": {"program_name": "BASc"}}
    out = merge_with_curriculum(curriculum, {"coverage_score": 0.5})
    assert out["schema_version"] == "2.0"
    assert out["pedagogy"]["coverage_score"] == 0.5
    assert curriculum["schema_version"] == "1.0"
