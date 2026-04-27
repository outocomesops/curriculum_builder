from types import SimpleNamespace

from analyzers.coverage_analyzer import analyze_coverage


def _result(level, weak=False, verb=None):
    return SimpleNamespace(
        classification=SimpleNamespace(bloom_level=level),
        is_weak_verb=weak,
        extracted_verb=verb,
    )


def test_analyze_coverage_generates_distribution_and_flags():
    results = [
        _result("remember"),
        _result("remember"),
        _result(None, weak=True, verb="understand"),
    ]
    report = analyze_coverage(results)
    assert report.outcomes_analyzed == 3
    assert report.distribution["remember"] == 2
    assert report.unclassified_count == 1
    assert report.weak_verb_count == 1
    assert any("Create" in f for f in report.flags)
    assert any("Evaluate" in f for f in report.flags)
    assert any("Remember" in f for f in report.flags)
    assert any("unmeasurable or vague verbs" in f for f in report.flags)
