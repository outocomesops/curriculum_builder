"""
Deep Research Loader
====================
Runs multi-module NotebookLM research on a higher-education institution.

Each module:
  1. Creates its own NLM notebook
  2. Adds a text seed source
  3. Uses NLM's native deep-research (`nlm research start --auto-import`) so
     NLM itself discovers and ingests ~40 real web sources — no external search
     library needed
  4. Optionally adds any caller-supplied extra URLs
  5. Queries the notebook
  6. Cleans up

Module-level isolation means one failure never blocks the others.
Add new modules by appending dicts to MODULE_REGISTRY — no other code changes needed.
"""
from __future__ import annotations

import json
import re
import subprocess
from typing import Callable

DEFAULT_RESEARCH_TIMEOUT: int = 420   # 7 min covers NLM deep mode (~5 min) + import
DEFAULT_QUERY_TIMEOUT: int = 120

# ---------------------------------------------------------------------------
# Research module registry
# ---------------------------------------------------------------------------

MODULE_REGISTRY: list[dict] = [
    {
        "key": "legal_framework",
        "title": "Legal Framework & Regulations",
        "icon": "⚖️",
        "description": (
            "Applicable laws, government policies, accreditation regulations, "
            "and quality assurance frameworks governing the institution and its country's "
            "higher-education sector."
        ),
        "research_query_template": (
            "{institution_name} higher education accreditation regulations legal requirements {program_name}"
        ),
        "seed_text_template": (
            "{institution_name} is a higher education institution offering {program_name}. "
            "This research covers the legal and regulatory framework governing higher education "
            "in the institution's country/region, including accreditation bodies, government "
            "oversight, compliance requirements, and student-protection legislation."
        ),
        "query_template": (
            "What laws, government policies, accreditation regulations, and quality assurance "
            "frameworks govern {institution_name} and the broader higher education sector in its "
            "country or region? Include: relevant legislation, regulatory agencies, accreditation "
            "requirements specific to the {program_name} program area, student-protection laws, "
            "tuition or fee regulations, and any recent or pending policy changes that affect "
            "curriculum design or program delivery."
        ),
    },
    {
        "key": "competitive_landscape",
        "title": "Competitive Landscape",
        "icon": "🏆",
        "description": (
            "Main competitors, program comparison, market positioning, "
            "tuition benchmarks, and enrollment data."
        ),
        "research_query_template": (
            "{institution_name} {program_name} competitors peer institutions ranking tuition comparison"
        ),
        "seed_text_template": (
            "{institution_name} offers {program_name}. "
            "This research examines the competitive higher education landscape, identifying peer "
            "institutions, alternative program providers, and the relative positioning of "
            "{institution_name} in terms of program offerings, reputation, and market share."
        ),
        "query_template": (
            "Who are the main competitors of {institution_name} for the {program_name} program? "
            "Provide: a list of peer and rival institutions in the same geographic and program market, "
            "a comparison of their program offerings versus {institution_name}, the institution's "
            "competitive differentiators or weaknesses, tuition and delivery format comparisons "
            "where available, and any enrollment ranking or market share data."
        ),
    },
    {
        "key": "student_market",
        "title": "Student Market & Employer Perception",
        "icon": "🎓",
        "description": (
            "Target student demographics, enrollment trends, graduate employment outcomes, "
            "and how the institution is perceived by employers and prospective students."
        ),
        "research_query_template": (
            "{institution_name} graduate employment outcomes salary employer perception student reviews {program_name}"
        ),
        "seed_text_template": (
            "{institution_name} offers {program_name}. "
            "This research covers how students, prospective applicants, graduates, and employers "
            "perceive {institution_name}, including graduate employment outcomes, salary data, "
            "and the institution's brand equity in the labour market."
        ),
        "query_template": (
            "What is the target student demographic for {institution_name}'s {program_name} program? "
            "How do graduates of this institution perform in the labour market — include employment "
            "rates, typical employers, salary ranges, and time-to-employment where available. "
            "How do employers and prospective students perceive the quality and reputation of "
            "{institution_name} and this specific program? Note any notable alumni outcomes, "
            "industry partnerships, or student satisfaction data."
        ),
    },
    {
        "key": "institutional_history",
        "title": "Institutional History & Identity",
        "icon": "🏛️",
        "description": (
            "Founding story, key milestones, mission evolution, pedagogical traditions, "
            "and the cultural identity that shapes how the institution operates."
        ),
        "research_query_template": (
            "{institution_name} history founding milestones mission values identity"
        ),
        "seed_text_template": (
            "{institution_name} is a higher education institution. "
            "This research covers its founding history, key institutional milestones, evolution "
            "of mission and values, and the cultural identity that shapes how it operates and "
            "positions itself in the {program_name} field."
        ),
        "query_template": (
            "Describe the history and cultural identity of {institution_name}. Include: year and "
            "circumstances of founding, key milestones in institutional development, how its mission "
            "and strategic vision have evolved over time, distinctive pedagogical values or traditions, "
            "any significant name changes or structural transformations, notable figures associated "
            "with the institution's history, and how that history shapes its current approach "
            "to {program_name}."
        ),
    },
    {
        "key": "strategic_analysis",
        "title": "Strategic Analysis (Game Theory)",
        "icon": "♟️",
        "description": (
            "Institution as a rational actor: incentive structures, competitive dynamics, "
            "responses to policy and market pressures, and strategic decision-making patterns."
        ),
        "research_query_template": (
            "{institution_name} strategic plan priorities enrollment trends market position new programs"
        ),
        "seed_text_template": (
            "{institution_name} operates in a competitive and regulated higher education market. "
            "This research analyses the institution's strategic decision-making patterns, how it "
            "responds to competitive, policy, and student-demand pressures, and the incentive "
            "structures that shape its behaviour as a rational actor."
        ),
        "query_template": (
            "Analyse {institution_name} as a strategic actor in higher education using a game theory "
            "or strategic management lens. Describe: the dominant incentives driving the institution's "
            "decisions (tuition revenue, rankings, accreditation, government funding, enrolment targets), "
            "observable strategic moves in response to competitor actions, how it has adapted to "
            "government policy changes, how it responds to shifts in student demand for {program_name}, "
            "any pattern of differentiation or cost-leadership, potential Nash equilibria in its "
            "competitive environment, and its likely strategic priorities for {program_name} over "
            "the next 3-5 years."
        ),
    },
]


# ---------------------------------------------------------------------------
# Internal NLM CLI helpers
# ---------------------------------------------------------------------------

def _run_nlm(args: list[str], timeout: int = 180) -> tuple[str, str, int]:
    result = subprocess.run(
        ["nlm"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout, result.stderr, result.returncode


def _create_notebook(title: str) -> str:
    stdout, stderr, rc = _run_nlm(["notebook", "create", title], timeout=60)
    if rc != 0:
        raise RuntimeError(f"nlm notebook create failed (rc={rc}): {stderr.strip() or stdout.strip()}")
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", stdout)
    if not match:
        raise RuntimeError(f"Could not extract notebook ID from output: {stdout.strip()}")
    return match.group(0)


def _add_text_source(notebook_id: str, text: str, title: str, timeout: int = 60) -> None:
    _, stderr, rc = _run_nlm(
        ["source", "add", notebook_id, "--text", text, "--title", title, "--wait"],
        timeout=timeout,
    )
    if rc != 0:
        raise RuntimeError(f"nlm source add (text) failed (rc={rc}): {stderr.strip()}")


def _run_nlm_research(
    notebook_id: str,
    query: str,
    mode: str = "deep",
    timeout: int = DEFAULT_RESEARCH_TIMEOUT,
) -> tuple[str, str, int]:
    """
    Triggers NLM's native web research for the given query and waits until
    all discovered sources are imported into the notebook.

    --auto-import blocks the subprocess until research completes and sources
    are ingested — no separate status/import step needed.
    """
    return _run_nlm(
        ["research", "start", query,
         "--notebook-id", notebook_id,
         "--mode", mode,
         "--auto-import"],
        timeout=timeout,
    )


def _add_url_sources_best_effort(
    notebook_id: str,
    urls: list[str],
    timeout: int = 90,
) -> list[str]:
    """Add caller-supplied extra URLs on top of NLM-researched sources."""
    succeeded = []
    for url in urls:
        try:
            _, _, rc = _run_nlm(
                ["source", "add", notebook_id, "--url", url, "--wait", "--wait-timeout", "60"],
                timeout=timeout,
            )
            if rc == 0:
                succeeded.append(url)
        except Exception:
            pass
    return succeeded


def _query_notebook(notebook_id: str, question: str, timeout: int = 120) -> str:
    stdout, stderr, rc = _run_nlm(
        ["notebook", "query", "--json", notebook_id, question],
        timeout=timeout,
    )
    if rc != 0:
        raise RuntimeError(f"nlm notebook query failed (rc={rc}): {stderr.strip() or stdout.strip()}")
    try:
        data = json.loads(stdout)
        answer = data.get("value", {}).get("answer", "") or data.get("answer", "")
        if answer:
            return answer
    except (json.JSONDecodeError, AttributeError):
        pass
    return stdout.strip()


def _delete_notebook(notebook_id: str) -> None:
    try:
        _run_nlm(["notebook", "delete", "-y", notebook_id], timeout=30)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_research_module(
    module_key: str,
    institution_name: str,
    program_name: str,
    extra_urls: list[str] | None = None,
    research_timeout: int = DEFAULT_RESEARCH_TIMEOUT,
    query_timeout: int = DEFAULT_QUERY_TIMEOUT,
    cleanup: bool = True,
    progress_callback: Callable[[str], None] | None = None,
    research_mode: str = "deep",
) -> dict:
    """
    Runs one research module end-to-end against NotebookLM.

    Uses NLM's native web research (`nlm research start --mode <mode> --auto-import`)
    to discover and ingest real sources — NLM finds its own references rather
    than relying on an external search library.

    Returns a dict with keys:
      module_key, status ("ok"|"error"), answer, error, notebook_id, sources_added

    Never raises — all exceptions are caught and returned in the "error" field.
    """
    def _cb(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    module = next((m for m in MODULE_REGISTRY if m["key"] == module_key), None)
    if module is None:
        return {
            "module_key": module_key, "status": "error",
            "answer": "", "error": f"Unknown module key: {module_key!r}",
            "notebook_id": "", "sources_added": 0,
        }

    seed_text = module["seed_text_template"].format(
        institution_name=institution_name, program_name=program_name
    )
    research_query = module["research_query_template"].format(
        institution_name=institution_name, program_name=program_name
    )
    query = module["query_template"].format(
        institution_name=institution_name, program_name=program_name
    )

    notebook_id = ""
    sources_added = 0

    try:
        # Step 1: create notebook
        _cb("Creating NotebookLM notebook…")
        notebook_id = _create_notebook(
            f"DeepResearch: {module['title']} — {institution_name}"
        )

        # Step 2: add text seed so notebook always has baseline context
        _cb("Adding text seed source…")
        _add_text_source(notebook_id, seed_text, title="Research seed", timeout=60)

        # Step 3: NLM native web research — NLM discovers and imports its own sources
        mode_label = "deep (~5 min, ~40 sources)" if research_mode == "deep" else "fast (~30 s, ~10 sources)"
        _cb(f'Running NLM {mode_label} research: "{research_query}"...')
        stdout, stderr, rc = _run_nlm_research(
            notebook_id, research_query, mode=research_mode, timeout=research_timeout
        )
        if rc != 0:
            _cb(f"NLM research warning (rc={rc}): {stderr.strip()[:200] or stdout.strip()[:200]}")
        else:
            # Try to count imported sources from output
            count_match = re.search(r"(\d+)\s+source", stdout, re.IGNORECASE)
            if count_match:
                sources_added = int(count_match.group(1))
                _cb(f"NLM research complete — {sources_added} source(s) imported.")
            else:
                _cb("NLM research complete.")

        # Step 4: add caller-supplied extra URLs (bonus, best-effort)
        if extra_urls:
            _cb(f"Adding {len(extra_urls)} extra URL(s)…")
            added = _add_url_sources_best_effort(notebook_id, extra_urls)
            sources_added += len(added)
            _cb(f"{len(added)}/{len(extra_urls)} extra URL(s) ingested.")

        # Step 5: query
        _cb("Querying NotebookLM…")
        answer = _query_notebook(notebook_id, query, timeout=query_timeout)

        if cleanup:
            _cb("Cleaning up notebook…")
            _delete_notebook(notebook_id)

        return {
            "module_key": module_key, "status": "ok",
            "answer": answer, "error": "",
            "notebook_id": "" if cleanup else notebook_id,
            "sources_added": sources_added,
        }

    except Exception as exc:
        _delete_notebook(notebook_id)
        return {
            "module_key": module_key, "status": "error",
            "answer": "", "error": str(exc),
            "notebook_id": notebook_id,
            "sources_added": sources_added,
        }


def build_deep_research_context(
    research_results: dict,
    selected_modules: list[str] | None = None,
) -> str:
    """
    Formats successful module results into a prompt-injectable string.
    Only modules with status=="ok" are included.
    """
    if not research_results:
        return "No deep research data available."

    parts = ["=== DEEP RESEARCH INTELLIGENCE ==="]
    included = 0
    for module in MODULE_REGISTRY:
        key = module["key"]
        if selected_modules is not None and key not in selected_modules:
            continue
        result = research_results.get(key)
        if result and result.get("status") == "ok" and result.get("answer"):
            parts.append(f"\n--- {module['title']} ---\n{result['answer']}")
            included += 1

    if included == 0:
        return "No deep research data available."
    return "\n".join(parts)


def get_module_by_key(module_key: str) -> dict | None:
    return next((m for m in MODULE_REGISTRY if m["key"] == module_key), None)
