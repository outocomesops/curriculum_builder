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


def build_institutional_context(consolidated_summary: str, doc_summaries: list[dict] | None = None) -> str:
    """
    Returns the consolidated institutional profile (preferred) or falls back
    to concatenating individual document summaries if consolidation hasn't run.
    """
    if consolidated_summary and consolidated_summary.strip():
        return f"Consolidated institutional profile:\n\n{consolidated_summary}"

    # Fallback: join individual summaries (legacy / pre-consolidation path)
    if not doc_summaries:
        return "No institutional documentation provided."
    useful = [d for d in doc_summaries if d.get("has_content") and d.get("summary")]
    if not useful:
        return "No institutional documentation provided."

    parts = ["Institutional context extracted from provided documents:"]
    for d in useful:
        parts.append(f"\n--- Source: {d['filename']} ---\n{d['summary']}")
    return "\n".join(parts)


def build_program_specs_context(specs_docs: list[dict], max_chars: int = 12000) -> str:
    """
    Combines extracted text from all program specification files into a single
    context block for the LLM.  Truncates to max_chars to stay within context limits.
    """
    if not specs_docs:
        return "No program specification documents provided."

    useful = [d for d in specs_docs if not d.get("error") and d.get("char_count", 0) > 0]
    if not useful:
        return "No program specification documents provided."

    parts = [f"Program specification materials ({len(useful)} file(s)):"]
    total = 0
    for d in useful:
        header = f"\n--- {d['filename']} ({d['file_type']}) ---\n"
        text = d["text"]
        remaining = max_chars - total - len(header)
        if remaining <= 0:
            parts.append("\n[... additional files truncated to fit context limit ...]")
            break
        if len(text) > remaining:
            text = text[:remaining] + "\n[... truncated ...]"
        parts.append(header + text)
        total += len(header) + len(text)
    return "\n".join(parts)


def build_reputation_context(reputation_summary: str) -> str:
    if not reputation_summary or not reputation_summary.strip():
        return "No public reputation data available."
    return f"Public perception & institutional reputation:\n\n{reputation_summary}"
