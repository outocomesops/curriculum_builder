from dataclasses import dataclass, field

from config import BLOOM_LEVEL_ORDER


@dataclass
class CoverageReport:
    distribution: dict[str, int]
    coverage_score: float
    missing_levels: list[str]
    weak_verb_count: int
    unclassified_count: int
    outcomes_analyzed: int
    flags: list[str] = field(default_factory=list)


def analyze_coverage(analysis_results: list) -> CoverageReport:
    distribution = {lvl: 0 for lvl in BLOOM_LEVEL_ORDER}
    weak_count = 0
    unclassified_count = 0

    for result in analysis_results:
        lvl = result.classification.bloom_level
        if lvl and lvl in distribution:
            distribution[lvl] += 1
        else:
            unclassified_count += 1
        if result.is_weak_verb:
            weak_count += 1

    present_levels = [lvl for lvl, cnt in distribution.items() if cnt > 0]
    missing_levels = [lvl for lvl in BLOOM_LEVEL_ORDER if distribution[lvl] == 0]
    coverage_score = len(present_levels) / len(BLOOM_LEVEL_ORDER)

    flags: list[str] = []

    if "create" in missing_levels:
        flags.append(
            "No outcomes at 'Create' (Level 6) — consider adding synthesis, design, or "
            "production tasks, especially in upper-level and capstone courses."
        )
    if "evaluate" in missing_levels:
        flags.append(
            "No outcomes at 'Evaluate' (Level 5) — learners may not be challenged to "
            "critically assess or justify professional decisions."
        )
    if distribution.get("remember", 0) > distribution.get("apply", 0) * 2:
        flags.append(
            "Heavy concentration at 'Remember' relative to 'Apply' — curriculum may be "
            "over-weighted toward memorisation rather than practical skill transfer."
        )
    if weak_count > 0:
        verb_list = [r.extracted_verb for r in analysis_results if r.is_weak_verb]
        counts: dict[str, int] = {}
        for v in verb_list:
            if v:
                counts[v] = counts.get(v, 0) + 1
        summary = ", ".join(f"{v}x{n}" for v, n in counts.items())
        flags.append(
            f"{weak_count} outcome(s) use unmeasurable or vague verbs ({summary}). "
            "Replace with observable, Bloom's-aligned verbs."
        )
    if unclassified_count > 0:
        flags.append(
            f"{unclassified_count} outcome(s) contain verbs that could not be classified. "
            "Review and replace with verbs from the Bloom's verb bank."
        )

    return CoverageReport(
        distribution=distribution,
        coverage_score=round(coverage_score, 3),
        missing_levels=missing_levels,
        weak_verb_count=weak_count,
        unclassified_count=unclassified_count,
        outcomes_analyzed=len(analysis_results),
        flags=flags,
    )
