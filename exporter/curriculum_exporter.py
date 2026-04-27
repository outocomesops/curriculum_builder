"""
Assembles a structured JSON export of the full curriculum session state.
The JSON is the machine-readable counterpart to the PDF export and serves
as the interchange format for downstream applications.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from exporter.bloom_exporter import build_pedagogy_block


SCHEMA_VERSION = "1.0"
SCHEMA_VERSION_PEDAGOGY = "2.0"


def _sanitize_folder(name: str) -> str:
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def build_curriculum_export(
    institution_name: str,
    program_name: str,
    program_level: str,
    language: str,
    course_hours: int | None,
    skills_df: pd.DataFrame | None,
    top_n: int,
    agencies: list[dict],
    institutional_docs: list[dict],
    consolidated_summary: str,
    reputation_snippets: list[dict],
    reputation_summary: str,
    program_specs_docs: list[dict],
    deep_research_results: dict[str, dict],
    learning_outcomes: str,
    course_list: str,
    competency_map: str,
    syllabi: dict[str, str],
    analysis_results: Optional[list] = None,
    coverage: Optional[Any] = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    course_pattern = re.compile(r"\*\*\[?([A-Z]{2,6}\d{3,4}[A-Z]?)\]?\s+([^\*\n]+)\*\*")
    detected_courses = [
        {"code": code, "name": name.strip()}
        for code, name in course_pattern.findall(course_list)
    ]

    skills_data: list[dict] = []
    if skills_df is not None and not skills_df.empty:
        for _, row in skills_df.head(top_n).iterrows():
            skills_data.append({
                "skill_name": str(row.get("skill_name", "")),
                "skill_type": str(row.get("skill_type", "")),
                "job_count": int(row.get("job_count", 0)),
                "mention_rate": float(round(row.get("mention_rate", 0.0), 4)),
            })

    agencies_export = [
        {
            "agency_code": a.get("agency_code", ""),
            "agency_name": a.get("agency_name", ""),
            "full_name": a.get("full_name", ""),
            "jurisdiction": a.get("jurisdiction", ""),
            "program_scope": a.get("program_scope", []),
            "definition_of_quality": a.get("definition_of_quality", ""),
            "core_quality_dimensions": a.get("core_quality_dimensions", []),
            "curriculum_requirements": a.get("curriculum_requirements", []),
            "what_agencies_measure": a.get("what_agencies_measure", []),
            "best_practices_for_programs": a.get("best_practices_for_programs", []),
        }
        for a in agencies
    ]

    dr_export: dict[str, Any] = {
        "modules_run": list(deep_research_results.keys()),
        "results": {
            key: {
                "status": r.get("status", ""),
                "answer": r.get("answer", ""),
                "sources_added": r.get("sources_added", 0),
                "error": r.get("error"),
            }
            for key, r in deep_research_results.items()
        },
    }

    schema = SCHEMA_VERSION_PEDAGOGY if (analysis_results and coverage) else SCHEMA_VERSION

    export: dict[str, Any] = {
        "schema_version": schema,
        "generated_at": now.isoformat(),
        "metadata": {
            "institution_name": institution_name,
            "program_name": program_name,
            "program_level": program_level,
            "language": language,
            "course_hours": course_hours,
            "year_month": now.strftime("%Y-%m"),
        },
        "inputs": {
            "skills": {
                "total_skills_in_db": len(skills_df) if skills_df is not None else 0,
                "top_n_used": top_n,
                "skills": skills_data,
            },
            "accreditation_agencies": agencies_export,
            "institutional_context": {
                "consolidated_summary": consolidated_summary,
                "source_documents_count": len(institutional_docs),
                "source_documents": [
                    {"filename": d["filename"], "char_count": d.get("char_count", 0)}
                    for d in institutional_docs
                ],
            },
            "reputation": {
                "summary": reputation_summary,
                "source_count": len(reputation_snippets),
            },
            "program_specifications": {
                "file_count": len(program_specs_docs),
                "files": [
                    {
                        "filename": d["filename"],
                        "file_type": d.get("file_type", "unknown"),
                        "char_count": d.get("char_count", 0),
                    }
                    for d in program_specs_docs
                    if not d.get("error") and d.get("char_count", 0) > 0
                ],
            },
            "deep_research": dr_export,
        },
        "curriculum": {
            "learning_outcomes": {"markdown": learning_outcomes},
            "course_list": {
                "markdown": course_list,
                "courses_detected": detected_courses,
            },
            "competency_map": {"markdown": competency_map},
            "syllabi": {
                code: {"markdown": text}
                for code, text in syllabi.items()
            },
        },
    }

    if analysis_results and coverage:
        export["pedagogy"] = build_pedagogy_block(analysis_results, coverage)

    return export


def save_curriculum_export(
    export_data: dict[str, Any],
    institution_name: str,
    program_name: str,
    base_outputs: Path,
) -> Path:
    year_month = export_data["metadata"]["year_month"]
    out_dir = (
        base_outputs
        / _sanitize_folder(institution_name)
        / year_month
        / _sanitize_folder(program_name)
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "curriculum_export.json"
    out_path.write_text(
        json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path
