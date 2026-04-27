from config import BLOOM_LEVEL_ORDER


def build_improvement_prompt(
    outcome_record,
    analysis_result,
    program_context: dict,
    bloom_data: dict,
) -> str:
    institution = program_context.get("institution", "the institution")
    program = program_context.get("program", "the program")
    level = program_context.get("level", "undergraduate")
    top_skills = program_context.get("top_skills", [])
    skills_str = ", ".join(top_skills[:3]) if top_skills else "relevant professional skills"

    bloom_level = analysis_result.classification.bloom_level or "apply"
    bloom_level_num = analysis_result.classification.bloom_level_num or 3
    level_desc = bloom_data["levels"].get(bloom_level, {}).get("description", "")
    level_verbs = bloom_data["levels"].get(bloom_level, {}).get("verbs", [])
    verbs_sample = ", ".join(level_verbs[:8])

    if outcome_record.course_code:
        year = outcome_record.course_level or "?"
        course_context = (
            f"This is a course-level objective for {outcome_record.course_title} "
            f"({outcome_record.course_code}), Year {year} of the program."
        )
    else:
        type_label = {"PEO": "program educational objective", "SLO": "student learning outcome"}.get(
            outcome_record.outcome_type, "learning outcome"
        )
        course_context = f"This is a program-level {type_label}."

    issues_str = " ".join(analysis_result.issues) if analysis_result.issues else ""
    suggested_str = ", ".join(analysis_result.suggested_verbs) if analysis_result.suggested_verbs else verbs_sample

    return f"""You are an expert instructional designer specialising in Bloom's Revised Taxonomy (Anderson & Krathwohl, 2001) and outcomes-based education.

Context:
- Institution: {institution}
- Program: {program} ({level})
- Key employer-demanded skills: {skills_str}
- {course_context}

Original learning outcome:
"{outcome_record.text}"

Pedagogical issue:
{issues_str if issues_str else f"The verb should be classified at Bloom's Level {bloom_level_num} ({bloom_level.capitalize()})."}

Target Bloom's level: {bloom_level.capitalize()} (Level {bloom_level_num}) — {level_desc}
Suggested verbs for this level: {suggested_str}

Task:
Rewrite the learning outcome using a precise, observable, and measurable verb at the {bloom_level.capitalize()} level of Bloom's Revised Taxonomy.

Rules:
- Use a strong, specific verb from: {verbs_sample}
- Keep the outcome concise (one sentence, 15–35 words)
- Preserve the subject matter and context of the original
- Make it relevant to {program} students and the skills employers need
- Begin with a verb (imperative form) or "Students will [verb]..."
- Return ONLY the rewritten outcome sentence. No explanation, no preamble."""
