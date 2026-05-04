import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class OutcomeRecord:
    id: str
    text: str
    outcome_type: str        # "PEO" | "SLO" | "LO"
    course_code: Optional[str]
    course_title: Optional[str]
    course_level: Optional[int]
    context: str


def _clean(text: str) -> str:
    return text.strip().strip("*").strip()


# Heading patterns for each section type.
# Each tuple: (regex_pattern, outcome_type, strip_bold_prefix)
_SECTION_PATTERNS = [
    (r"#\s*Program Educational Objectives", "PEO", False),
    (r"#\s*Student Learning Outcomes",      "SLO", True),
    (r"#\s*Learning Objectives",            "LO",  False),
    (r"#\s*Learning Outcomes",              "LO",  False),
    (r"#\s*Program Outcomes",               "SLO", False),
    (r"#\s*Course Outcomes",                "SLO", False),
    (r"#\s*Competencies",                   "LO",  False),
]


def _parse_section(markdown: str, heading_pattern: str, strip_bold: bool) -> list[dict]:
    """Extract numbered items under a markdown heading that matches heading_pattern."""
    items = []
    in_section = False
    for line in markdown.splitlines():
        if re.match(heading_pattern, line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if line.startswith("#"):
                break
            m = re.match(r"^\s*(\d+)[.)]\s+(.+)", line)
            if m:
                raw = m.group(2)
                if strip_bold:
                    raw = re.sub(r"\*\*(.+?)\*\*\s*[—\-]\s*", "", raw).strip()
                    if not raw:
                        title_m = re.match(r"\*\*(.+?)\*\*", m.group(2))
                        raw = title_m.group(1) if title_m else m.group(2)
                cleaned = _clean(raw)
                if cleaned:
                    items.append({"num": int(m.group(1)), "text": cleaned})
    return items


def _fallback_numbered_items(markdown: str) -> list[dict]:
    """
    Last-resort: collect every numbered list item in the document that
    looks like an outcome (starts with an action verb, > 5 words).
    Used when no recognised heading is found at all.
    """
    items = []
    num = 0
    for line in markdown.splitlines():
        m = re.match(r"^\s*(\d+)[.)]\s+(.+)", line)
        if m:
            raw = _clean(m.group(2))
            # Skip very short items (likely list annotations, not outcomes)
            if len(raw.split()) >= 5:
                num += 1
                items.append({"num": num, "text": raw})
    return items


def extract_outcomes_from_markdown(
    markdown: str,
    program_name: str = "",
    institution_name: str = "",
) -> list[OutcomeRecord]:
    """Parse learning outcomes markdown produced by curriculum_gen.generate_learning_outcomes().

    Handles all heading variants the LLM may produce (PEOs, SLOs, Learning
    Objectives, Learning Outcomes, etc.) and falls back to any numbered list
    when no recognised heading is present.
    """
    context_prefix = f"{institution_name} — {program_name}" if institution_name else program_name
    records: list[OutcomeRecord] = []
    seen_texts: set[str] = set()

    for pattern, otype, strip_bold in _SECTION_PATTERNS:
        for item in _parse_section(markdown, pattern, strip_bold):
            key = item["text"].lower()
            if key in seen_texts:
                continue
            seen_texts.add(key)
            records.append(OutcomeRecord(
                id=f"{otype}-{item['num']}",
                text=item["text"],
                outcome_type=otype,
                course_code=None,
                course_title=None,
                course_level=None,
                context=f"{context_prefix} | {otype}",
            ))

    # If nothing was found via headings, fall back to all numbered items
    if not records:
        for item in _fallback_numbered_items(markdown):
            records.append(OutcomeRecord(
                id=f"LO-{item['num']}",
                text=item["text"],
                outcome_type="LO",
                course_code=None,
                course_title=None,
                course_level=None,
                context=f"{context_prefix} | Learning outcome",
            ))

    return records
