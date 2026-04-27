from dataclasses import dataclass, field
from typing import Optional

from analyzers.bloom_classifier import ClassificationResult, classify_verb
from analyzers.verb_extractor import extract_verb


@dataclass
class AnalysisResult:
    outcome_id: str
    outcome_type: str
    course_code: Optional[str]
    original_text: str
    extracted_verb: Optional[str]
    classification: ClassificationResult
    is_weak_verb: bool
    weak_reason: Optional[str]
    issues: list[str] = field(default_factory=list)
    suggested_verbs: list[str] = field(default_factory=list)
    improved_text: Optional[str] = None
    improvement_approved: bool = False


def analyze_outcome(
    outcome,
    verb_index: dict[str, str],
    weak_verb_lookup: dict[str, dict],
    ollama_url: str = "http://localhost:11434",
    model: str = "llama3",
    use_ollama_fallback: bool = True,
) -> AnalysisResult:
    verb = extract_verb(outcome.text)
    classification = classify_verb(
        verb or "",
        outcome.text,
        verb_index,
        ollama_url,
        model,
        use_ollama_fallback=use_ollama_fallback and bool(verb),
    )

    issues: list[str] = []
    suggested: list[str] = []
    is_weak = False
    weak_reason = None

    if verb is None:
        issues.append("No action verb detected — outcome may be missing a clear behavioural verb.")
    else:
        weak_entry = weak_verb_lookup.get(verb.lower())
        if weak_entry:
            is_weak = True
            weak_reason = weak_entry["reason"]
            issues.append(f"'{verb}' is {weak_reason}.")
            for level_alternatives in weak_entry.get("alternatives_by_level", {}).values():
                for v in level_alternatives:
                    if v not in suggested:
                        suggested.append(v)

        if classification.source == "unclassified":
            issues.append(
                f"'{verb}' could not be classified into a Bloom's level — "
                "consider replacing it with a verb from the Bloom's verb bank."
            )

    return AnalysisResult(
        outcome_id=outcome.id,
        outcome_type=outcome.outcome_type,
        course_code=outcome.course_code,
        original_text=outcome.text,
        extracted_verb=verb,
        classification=classification,
        is_weak_verb=is_weak,
        weak_reason=weak_reason,
        issues=issues,
        suggested_verbs=suggested,
    )


def analyze_all_outcomes(
    outcomes,
    verb_index: dict[str, str],
    weak_verb_lookup: dict[str, dict],
    ollama_url: str = "http://localhost:11434",
    model: str = "llama3",
    use_ollama_fallback: bool = True,
) -> list[AnalysisResult]:
    return [
        analyze_outcome(o, verb_index, weak_verb_lookup, ollama_url, model, use_ollama_fallback)
        for o in outcomes
    ]
