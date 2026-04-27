from analyzers import outcome_analyzer as oa
from analyzers.bloom_classifier import ClassificationResult
from loaders.bloom_outcome_extractor import OutcomeRecord


def _sample_outcome(text: str) -> OutcomeRecord:
    return OutcomeRecord(
        id="SLO-1",
        text=text,
        outcome_type="SLO",
        course_code=None,
        course_title=None,
        course_level=None,
        context="ctx",
    )


def test_analyze_outcome_flags_weak_verb_and_suggestions():
    out = _sample_outcome("Students will understand core networking concepts.")
    weak_lookup = {
        "understand": {
            "reason": "too vague",
            "alternatives_by_level": {"apply": ["demonstrate", "implement"]},
        }
    }
    result = oa.analyze_outcome(out, {"demonstrate": "apply"}, weak_lookup, use_ollama_fallback=False)
    assert result.is_weak_verb is True
    assert "too vague" in (result.weak_reason or "")
    assert "demonstrate" in result.suggested_verbs


def test_analyze_outcome_adds_unclassified_issue():
    out = _sample_outcome("Students will prototype secure systems.")
    result = oa.analyze_outcome(out, {}, {}, use_ollama_fallback=False)
    assert result.classification.source == "unclassified"
    assert any("could not be classified" in issue for issue in result.issues)


def test_analyze_all_outcomes_maps_all_entries():
    rows = [_sample_outcome("Students will apply math."), _sample_outcome("Students will evaluate tradeoffs.")]
    results = oa.analyze_all_outcomes(rows, {"apply": "apply", "evaluate": "evaluate"}, {}, use_ollama_fallback=False)
    assert len(results) == 2
    assert all(isinstance(r.classification, ClassificationResult) for r in results)
