"""
All curriculum generation functions.
Each returns a generator that yields text chunks from the Ollama streaming API.
"""
from __future__ import annotations

import json
from typing import Generator

import requests

_CHAT_PATH = "/api/chat"
_OPTIONS = {"temperature": 0.45, "num_ctx": 8192}


def list_ollama_models(ollama_url: str) -> list[str]:
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def _stream(ollama_url: str, model: str, prompt: str) -> Generator[str, None, None]:
    try:
        resp = requests.post(
            f"{ollama_url}{_CHAT_PATH}",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "options": _OPTIONS,
            },
            timeout=600,
            stream=True,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
    except requests.exceptions.ConnectionError:
        yield "\n\n> **ERROR:** Cannot reach Ollama. Confirm it is running at the configured URL."
    except requests.exceptions.Timeout:
        yield "\n\n> **ERROR:** Ollama request timed out. Try a smaller model or increase context."
    except requests.exceptions.HTTPError as exc:
        yield f"\n\n> **ERROR:** Ollama returned HTTP {exc.response.status_code}. Check the model name."
    except Exception as exc:
        yield f"\n\n> **ERROR:** {exc}"


def generate_learning_outcomes(
    program_name: str,
    program_level: str,
    program_scope: str,
    skills_context: str,
    accreditation_context: str,
    institutional_context: str,
    language: str,
    ollama_url: str,
    model: str,
    course_hours: int | None = None,
    reputation_context: str = "",
    program_specs_context: str = "",
    deep_research_context: str = "",
    program_duration_semesters: int | None = None,
    kb_context: str = "",
) -> Generator[str, None, None]:
    is_ce = program_level == "Continuous Education"
    hours_line = f"TOTAL CONTACT HOURS: {course_hours}" if is_ce and course_hours else ""
    duration_line = f"DURATION: {program_duration_semesters} semesters" if program_duration_semesters and not is_ce else ""

    if is_ce:
        outcomes_instruction = """
# Program Overview
One to two paragraphs describing the continuing education program, its target audience (working professionals),
and the specific professional gap or need it addresses.

# Learning Objectives
Five to eight concrete, immediately applicable competencies participants will demonstrate upon completion.
Number each one. Use action verbs suited to adult professional learners (apply, implement, evaluate, design...).

# Participant Profile
A brief description of the ideal participant: current role, prior experience expected, and how they will
use these new competencies in their work context immediately after the program."""
    else:
        outcomes_instruction = """
# Program Overview
Two to three paragraphs describing the program, its purpose, societal relevance, and the professional profile it targets.

# Program Educational Objectives (PEOs)
Three to five broad outcomes expected 3-5 years post-graduation. Number each one.

# Student Learning Outcomes (SLOs)
Eight to twelve specific, measurable competencies graduates will demonstrate at completion.
Number each one. Use action verbs (analyze, design, apply, evaluate...).

# Graduate Profile
A concise description of the graduate: knowledge areas, technical skills, professional values,
and the contexts in which they will work."""

    reputation_section = f"\n=== INSTITUTIONAL REPUTATION & PUBLIC PERCEPTION ===\n{reputation_context}" if reputation_context else ""
    specs_section = f"\n=== PROGRAM SPECIFICATION MATERIALS (stakeholder documents) ===\n{program_specs_context}" if program_specs_context else ""
    research_section = f"\n{deep_research_context}" if deep_research_context and "No deep research" not in deep_research_context else ""
    kb_section = f"\n{kb_context}" if kb_context else ""

    prompt = f"""You are an expert curriculum designer for higher education.
Write entirely in {language}.

Design the foundational program documentation for:
PROGRAM: {program_name}
LEVEL: {program_level}
FIELD: {program_scope}
{duration_line}
{hours_line}

=== JOB MARKET DEMAND ===
{skills_context}

=== ACCREDITATION STANDARDS ===
{accreditation_context}

=== INSTITUTIONAL CONTEXT ===
{institutional_context}{reputation_section}{specs_section}{research_section}{kb_section}

---
Generate the following sections in {language}:
{outcomes_instruction}

Align all content tightly with job market demand, accreditation requirements, institutional identity,
public reputation signals, and the deep research intelligence above."""

    yield from _stream(ollama_url, model, prompt)


def generate_course_list(
    program_name: str,
    program_level: str,
    learning_outcomes: str,
    skills_context: str,
    accreditation_context: str,
    language: str,
    ollama_url: str,
    model: str,
    course_hours: int | None = None,
    program_specs_context: str = "",
    deep_research_context: str = "",
    program_duration_semesters: int | None = None,
    kb_context: str = "",
) -> Generator[str, None, None]:
    is_ce = program_level == "Continuous Education"

    if is_ce and course_hours:
        structure_rules = f"""Rules for Continuous Education ({course_hours} total contact hours):
- Divide the total {course_hours} hours into modules (not semesters).
- Each module should be 4-16 hours. Aim for 4-8 modules depending on program depth.
- Final module must be a practical application, workshop, or capstone project.
- Ensure each learning objective is addressed by at least one module.
- Balance theoretical input (max 40%) with applied practice (min 60%).

CRITICAL FORMATTING RULE: Every module MUST use this EXACT format on its own line:
**[MOD001] Module Name** (X hours) — [Core/Applied/Workshop]
> Brief description (2 sentences). Addresses Objectives: #X, #Y.

The code is MOD followed by a zero-padded 3-digit number (MOD001, MOD002, MOD003, ...).
Do NOT deviate from this format — the course extractor depends on it exactly."""
    else:
        duration_str = f"{program_duration_semesters} semesters" if program_duration_semesters else "the appropriate number of semesters"
        structure_rules = f"""Rules:
- Program duration: exactly {duration_str}. Do NOT use a different number of semesters anywhere.
- Distribute courses evenly across all {duration_str}. Label each semester group clearly.
- Undergraduate programs: 35-45 courses total, 3 credits each by default.
- Graduate programs: 18-28 courses total.
- Final semester must include a capstone or integrating project.
- Ensure each SLO is addressed by at least two courses.
- Distribute skill coverage across the program (do not front-load).
- Include at least one research methods course and one professional ethics course.

CRITICAL FORMATTING RULE: Every course MUST use this EXACT format on its own line:
**[CODE] Course Name** (N credits) — [Core/Elective/Capstone]
> Brief description (2 sentences). Addresses SLOs: #X, #Y.

Where CODE = 2-6 uppercase letters immediately followed by 3-4 digits, no space (examples: CS101, ENGR205, DATA301, MGT410, COMP3200).
Do NOT use any other format — the course code extractor depends on this exact pattern."""

    hours_line = f"TOTAL CONTACT HOURS: {course_hours}" if is_ce and course_hours else ""
    duration_line = f"DURATION: {duration_str}" if not is_ce and program_duration_semesters else ""
    kb_section = f"\n{kb_context}" if kb_context else ""

    prompt = f"""You are an expert curriculum designer. Write entirely in {language}.

Design a complete course list for:
PROGRAM: {program_name}  |  LEVEL: {program_level}
{duration_line}
{hours_line}

=== PROGRAM LEARNING OUTCOMES ===
{learning_outcomes}

=== IN-DEMAND SKILLS TO COVER ===
{skills_context}

=== ACCREDITATION CURRICULUM REQUIREMENTS ===
{accreditation_context}
{f"=== PROGRAM SPECIFICATION MATERIALS ===" + chr(10) + program_specs_context if program_specs_context else ""}
{deep_research_context if deep_research_context and "No deep research" not in deep_research_context else ""}
{kb_section}
---
Generate a full module/course list in {language}.

{structure_rules}"""

    yield from _stream(ollama_url, model, prompt)


def generate_competency_map(
    program_name: str,
    learning_outcomes: str,
    course_list: str,
    language: str,
    ollama_url: str,
    model: str,
    program_duration_semesters: int | None = None,
    kb_context: str = "",
) -> Generator[str, None, None]:
    duration_str = f"{program_duration_semesters} semesters" if program_duration_semesters else "the program duration"
    semester_rule = (
        f"Group courses by semester — there are exactly {duration_str}. "
        f"Use a separator row for every semester: | **Semester N** | | | ..."
        if program_duration_semesters
        else "Group courses by semester with a separator row: | **Semester N** | | | ..."
    )
    kb_section = f"\n{kb_context}" if kb_context else ""

    prompt = f"""You are an expert curriculum designer. Write entirely in {language}.

Create the competency map for:
PROGRAM: {program_name}
DURATION: {duration_str}

=== STUDENT LEARNING OUTCOMES ===
{learning_outcomes}

=== COURSE LIST ===
{course_list}
{kb_section}
---
Generate in {language}:

# Competency Map

A markdown table where:
- Rows = courses (Course Code + Name in the first column)
- Columns = SLO numbers (SLO1, SLO2, ...)
- Cells = I (Introduced), D (Developed), A (Assessed/Mastered), or blank

IMPORTANT formatting rules:
- Use short course codes only in column 1 (e.g. "CS101 Intro Programming"), keep under 35 chars
- Use only SLO abbreviations in headers (SLO1, SLO2, ...)
- {semester_rule}
- Keep every cell short: I, D, A, or blank only

# Curriculum Threads
Identify 3-5 thematic threads running through the curriculum (e.g. "Technical Core",
"Professional Practice", "Research & Innovation"). For each thread list the courses that
belong to it and explain how they develop progressively across the {duration_str}.

# Assessment Philosophy
Two paragraphs describing the overall assessment strategy: how student achievement is
measured across the program, what mix of formative/summative methods is used, and how
the program closes the assessment loop for continuous improvement."""

    yield from _stream(ollama_url, model, prompt)


def generate_syllabus(
    course_code: str,
    course_name: str,
    program_name: str,
    relevant_slos: str,
    skills_context: str,
    language: str,
    ollama_url: str,
    model: str,
    weeks_per_semester: int = 16,
    kb_context: str = "",
) -> Generator[str, None, None]:
    kb_section = f"\n{kb_context}" if kb_context else ""

    prompt = f"""You are an expert course designer. Write entirely in {language}.

Write a complete course syllabus for:
COURSE: {course_code} — {course_name}
PROGRAM: {program_name}

=== PROGRAM SLOs THIS COURSE ADDRESSES ===
{relevant_slos}

=== RELEVANT JOB MARKET SKILLS ===
{skills_context}
{kb_section}
---
Generate a complete syllabus in {language}:

# {course_code}: {course_name}

## Course Description
Two to three sentences.

## Prerequisites
List or "None".

## Course Learning Outcomes
Four to six specific, measurable outcomes. Number each.

## Weekly Schedule
| Week | Topic | Learning Activities | Assessment/Deliverable |
Use exactly {weeks_per_semester} weeks.

## Assessment Plan
| Component | Weight | Description |
Include: participation, assignments, midterm exam, final exam or project, and any labs/workshops.
Total must equal 100%.

## Required Resources
List textbooks (author, title, edition), software, and key online resources.

## Teaching Methodology
Brief description of instructional approaches: lectures, case studies, labs, flipped classroom, etc.

## Grading Scale
Standard letter-grade scale."""

    yield from _stream(ollama_url, model, prompt)
