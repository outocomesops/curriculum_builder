import pandas as pd


def build_skills_context(skills_df: pd.DataFrame, top_n: int = 40) -> str:
    if skills_df is None or skills_df.empty:
        return "No job market data available."

    top = skills_df.head(top_n)
    lines = [f"Top {len(top)} in-demand skills from job market analysis:"]
    for _, row in top.iterrows():
        rate = row.get("mention_rate", "")
        rate_str = f" — {rate}% of job postings" if rate else ""
        lines.append(f"  - {row['skill_name']} [{row['skill_type']}]{rate_str}")
    return "\n".join(lines)


def build_accreditation_context(agencies: list[dict]) -> str:
    if not agencies:
        return "No accreditation standards selected."

    sections = []
    for a in agencies:
        parts = [f"### {a['agency_name']} ({a['jurisdiction'].upper()})"]

        if a.get("definition_of_quality"):
            parts.append(f"Quality philosophy: {a['definition_of_quality']}")

        if a.get("curriculum_requirements"):
            parts.append("Curriculum requirements:")
            for r in a["curriculum_requirements"]:
                parts.append(f"  - {r}")

        if a.get("core_quality_dimensions"):
            parts.append("Core quality dimensions:")
            for d in a["core_quality_dimensions"]:
                parts.append(f"  - {d}")

        if a.get("best_practices_for_programs"):
            parts.append("Best practices:")
            for bp in a["best_practices_for_programs"]:
                parts.append(f"  - {bp}")

        sections.append("\n".join(parts))

    return "\n\n".join(sections)


def build_institutional_context(doc_summaries: list[dict]) -> str:
    useful = [d for d in doc_summaries if d.get("has_content") and d.get("summary")]
    if not useful:
        return "No institutional documentation provided."

    parts = ["Institutional context extracted from provided documents:"]
    for d in useful:
        parts.append(f"\n--- Source: {d['filename']} ---\n{d['summary']}")
    return "\n".join(parts)
