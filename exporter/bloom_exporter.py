from datetime import datetime, timezone


def build_pedagogy_block(
    analysis_results: list,
    coverage_report,
    framework: str = "Bloom's Revised Taxonomy (Anderson & Krathwohl, 2001)",
) -> dict:
    outcomes_payload = []
    for r in analysis_results:
        outcomes_payload.append({
            "id": r.outcome_id,
            "outcome_type": r.outcome_type,
            "course_code": r.course_code,
            "original": r.original_text,
            "extracted_verb": r.extracted_verb,
            "bloom_level": r.classification.bloom_level,
            "bloom_level_num": r.classification.bloom_level_num,
            "classification_confidence": r.classification.confidence,
            "classification_source": r.classification.source,
            "is_weak_verb": r.is_weak_verb,
            "weak_reason": r.weak_reason,
            "issues": r.issues,
            "suggested_verbs": r.suggested_verbs,
            "improved": r.improved_text,
            "improvement_approved": r.improvement_approved,
        })

    return {
        "framework": framework,
        "analysis_date": datetime.now(timezone.utc).isoformat(),
        "program_bloom_distribution": coverage_report.distribution,
        "coverage_score": coverage_report.coverage_score,
        "missing_levels": coverage_report.missing_levels,
        "weak_verb_count": coverage_report.weak_verb_count,
        "unclassified_count": coverage_report.unclassified_count,
        "outcomes_analyzed": coverage_report.outcomes_analyzed,
        "flags": coverage_report.flags,
        "outcomes": outcomes_payload,
    }


def merge_with_curriculum(curriculum_dict: dict, pedagogy_block: dict) -> dict:
    enriched = dict(curriculum_dict)
    enriched["schema_version"] = "2.0"
    enriched["pedagogy"] = pedagogy_block
    return enriched
