import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class OutcomeRecord:
    id: str
    text: str
    outcome_type: str        # "PEO" | "SLO"
    course_code: Optional[str]
    course_title: Optional[str]
    course_level: Optional[int]
    context: str


def _clean(text: str) -> str:
    return text.strip().strip("*").strip()


def _parse_peos(markdown: str) -> list[dict]:
    peos = []
    in_section = False
    for line in markdown.splitlines():
        if re.match(r"#\s*Program Educational Objectives", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if line.startswith("#"):
                break
            m = re.match(r"^\s*(\d+)\.\s+(.+)", line)
            if m:
                peos.append({"num": int(m.group(1)), "text": _clean(m.group(2))})
    return peos


def _parse_slos(markdown: str) -> list[dict]:
    slos = []
    in_section = False
    for line in markdown.splitlines():
        if re.match(r"#\s*Student Learning Outcomes", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if line.startswith("#"):
                break
            m = re.match(r"^\s*(\d+)\.\s+(.+)", line)
            if m:
                raw = m.group(2)
                raw = re.sub(r"\*\*(.+?)\*\*\s*[—\-]\s*", "", raw).strip()
                if raw:
                    slos.append({"num": int(m.group(1)), "text": _clean(raw)})
                else:
                    title_m = re.match(r"\*\*(.+?)\*\*", m.group(2))
                    if title_m:
                        slos.append({"num": int(m.group(1)), "text": _clean(title_m.group(1))})
    return slos


def extract_outcomes_from_markdown(
    markdown: str,
    program_name: str = "",
    institution_name: str = "",
) -> list[OutcomeRecord]:
    """Parse learning outcomes markdown produced by curriculum_gen.generate_learning_outcomes()."""
    context_prefix = f"{institution_name} — {program_name}" if institution_name else program_name
    records: list[OutcomeRecord] = []

    for peo in _parse_peos(markdown):
        records.append(OutcomeRecord(
            id=f"PEO-{peo['num']}",
            text=peo["text"],
            outcome_type="PEO",
            course_code=None,
            course_title=None,
            course_level=None,
            context=f"{context_prefix} | Program-level objective",
        ))

    for slo in _parse_slos(markdown):
        records.append(OutcomeRecord(
            id=f"SLO-{slo['num']}",
            text=slo["text"],
            outcome_type="SLO",
            course_code=None,
            course_title=None,
            course_level=None,
            context=f"{context_prefix} | Program-level student learning outcome",
        ))

    return records
