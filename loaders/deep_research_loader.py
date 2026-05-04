"""
Deep Research Loader
====================
Runs multi-module NotebookLM research on a higher-education institution.

Each module runs 3 targeted fast-research passes on its own notebook,
giving ~30 web sources per module (equivalent coverage to deep research).
Deep research mode is not available on all Google accounts (returns API
error code 8); multi-pass fast research is the robust alternative.

Each module is independent — one failure never blocks the others.
Add new modules by appending dicts to MODULE_REGISTRY.
"""
from __future__ import annotations

import time
from typing import Callable

from .nlm_client import AUTH_HINT, get_nlm_client

DEFAULT_QUERY_TIMEOUT: int = 300       # streaming query can take 2-3 min
_PASS_TIMEOUT: int = 120               # per research pass (fast completes in ~30s)
_POLL_INTERVAL: int = 10              # seconds between status polls
_INTER_PASS_DELAY: int = 4            # seconds between consecutive research passes

# ---------------------------------------------------------------------------
# Research module registry
# Each module has three research_queries covering different angles of the
# same topic. Running all three fast-research passes gives ~30 sources,
# matching the breadth of deep research.
# ---------------------------------------------------------------------------

MODULE_REGISTRY: list[dict] = [
    {
        "key": "institutional_reputation",
        "title": "Institutional Reputation",
        "icon": "⭐",
        "description": (
            "Public perception, student reviews, rankings, graduate outcomes, "
            "community relations, and notable news about the institution."
        ),
        "research_queries": [
            "{institution_name} student reviews ratings experience programs quality satisfaction",
            "{institution_name} graduate outcomes employment alumni reputation community",
            "{institution_name} rankings awards news international students public perception",
        ],
        "seed_text_template": (
            "{institution_name} is a higher education institution offering {program_name}. "
            "This research covers the public reputation, student experience, graduate outcomes, "
            "community standing, and general perception of {institution_name}."
        ),
        "query_template": (
            "What do students, graduates, employers, and the general public think about "
            "{institution_name}? Provide a comprehensive reputation summary covering: overall "
            "public sentiment (positive/negative/mixed), specifically praised programs or "
            "services, commonly cited criticisms or concerns, graduate employment outcomes and "
            "alumni success stories, community relationships and social standing, notable "
            "rankings or awards, any significant recent news or events, and international "
            "student experience if relevant. Be specific and cite notable details from the sources."
        ),
    },
    {
        "key": "legal_framework",
        "title": "Legal Framework & Regulations",
        "icon": "⚖️",
        "description": (
            "Applicable laws, government policies, accreditation regulations, "
            "and quality assurance frameworks governing the institution and its country's "
            "higher-education sector."
        ),
        "research_queries": [
            "{institution_name} higher education accreditation regulations requirements",
            "{institution_name} government policy compliance student protection legislation",
            "higher education regulatory framework {program_name} accreditation standards quality",
        ],
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
        "research_queries": [
            "{institution_name} {program_name} competitors peer institutions comparison",
            "{institution_name} tuition enrollment market share position rankings",
            "{program_name} programs colleges universities rankings comparison differentiation",
        ],
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
        "research_queries": [
            "{institution_name} graduate employment outcomes salary employers",
            "{institution_name} student enrollment demographics recruitment international",
            "{institution_name} {program_name} industry partnerships employer perception brand",
        ],
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
        "research_queries": [
            "{institution_name} history founding milestones achievements",
            "{institution_name} mission values strategic direction pedagogy",
            "{institution_name} identity culture traditions institutional evolution",
        ],
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
        "research_queries": [
            "{institution_name} strategic plan growth expansion new programs initiatives",
            "{institution_name} competitive strategy enrollment market position response",
            "{institution_name} government funding policy adaptation partnerships",
        ],
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
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_delete(client, notebook_id: str) -> None:
    if not notebook_id:
        return
    try:
        client.delete_notebook(notebook_id)
    except Exception:
        pass


def _run_one_pass(
    client,
    notebook_id: str,
    query: str,
    pass_num: int,
    total_passes: int,
    cb: Callable[[str], None],
) -> int:
    """Run one fast-research pass, poll to completion, import sources. Returns source count."""
    cb(f"Pass {pass_num}/{total_passes}: searching - \"{query[:70]}...\"")

    try:
        task = client.start_research(notebook_id, query=query, source="web", mode="fast")
    except Exception as exc:
        cb(f"Pass {pass_num} failed to start: {str(exc)[:100]} — skipping.")
        return 0

    if not task:
        cb(f"Pass {pass_num} did not start — skipping.")
        return 0

    task_id = task.get("task_id")
    deadline = time.time() + _PASS_TIMEOUT

    while time.time() < deadline:
        try:
            status_data = client.poll_research(
                notebook_id, target_task_id=task_id, target_query=query
            )
        except Exception as poll_exc:
            # Transient network timeout on the poll call — keep waiting
            cb(f"Pass {pass_num} poll warning: {str(poll_exc)[:80]} — retrying...")
            time.sleep(_POLL_INTERVAL)
            continue

        status = (status_data or {}).get("status", "")
        if status == "completed":
            sources_found = (status_data or {}).get("sources", [])
            try:
                client.import_research_sources(notebook_id, task_id, sources_found)
            except Exception as exc:
                cb(f"Pass {pass_num} import warning: {str(exc)[:80]}")
            cb(f"Pass {pass_num} done — {len(sources_found)} source(s) imported.")
            return len(sources_found)
        elif status in ("failed", "error"):
            cb(f"Pass {pass_num} ended with status '{status}'.")
            return 0
        time.sleep(_POLL_INTERVAL)

    cb(f"Pass {pass_num} timed out.")
    return 0


def _run_all_passes(
    client,
    notebook_id: str,
    research_queries: list[str],
    cb: Callable[[str], None],
) -> int:
    """Run all research passes sequentially. Returns total source count."""
    total = 0
    for i, query in enumerate(research_queries, 1):
        total += _run_one_pass(client, notebook_id, query, i, len(research_queries), cb)
        if i < len(research_queries):
            time.sleep(_INTER_PASS_DELAY)
    cb(f"All {len(research_queries)} passes complete — {total} source(s) total.")
    return total


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_research_module(
    module_key: str,
    institution_name: str,
    program_name: str,
    extra_urls: list[str] | None = None,
    query_timeout: int = DEFAULT_QUERY_TIMEOUT,
    cleanup: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> dict:
    """
    Run one research module end-to-end against NotebookLM.

    Runs 3 fast-research passes on a dedicated notebook (≈30 sources),
    then queries the notebook for a structured answer.

    Never raises — all exceptions are caught and returned in "error" field.

    Returns dict with keys:
      module_key, status ("ok"|"error"), answer, error, notebook_id, sources_added
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
    research_queries = [
        q.format(institution_name=institution_name, program_name=program_name)
        for q in module["research_queries"]
    ]
    query = module["query_template"].format(
        institution_name=institution_name, program_name=program_name
    )

    notebook_id = ""
    sources_added = 0

    try:
        client = get_nlm_client()

        # Step 1: create notebook
        _cb("Creating NotebookLM notebook…")
        nb = client.create_notebook(title=f"Research: {module['title']} — {institution_name}")
        notebook_id = nb.id

        # Step 2: text seed (guarantees at least one source)
        _cb("Adding context seed...")
        try:
            client.add_text_source(notebook_id, text=seed_text, title="Research seed", wait=True)
        except Exception as exc:
            _cb(f"Seed add warning: {str(exc)[:80]} — continuing anyway.")

        # Step 3: multi-pass fast research (~30 sources across 3 passes)
        sources_added = _run_all_passes(client, notebook_id, research_queries, _cb)

        # Step 4: extra URLs (best-effort, on top of research sources)
        if extra_urls:
            _cb(f"Adding {len(extra_urls)} extra URL(s)…")
            added = 0
            for url in extra_urls:
                try:
                    client.add_url_source(notebook_id, url=url, wait=True)
                    added += 1
                except Exception:
                    pass
            sources_added += added
            if added:
                _cb(f"{added}/{len(extra_urls)} extra URL(s) added.")

        # Step 5: query the notebook
        _cb("Querying NotebookLM — this may take 2-3 minutes…")
        result = client.query(notebook_id, query, timeout=query_timeout)
        answer = (result or {}).get("answer", "") if isinstance(result, dict) else str(result or "")

        if cleanup:
            _cb("Cleaning up notebook…")
            _safe_delete(client, notebook_id)
            notebook_id = ""

        return {
            "module_key": module_key, "status": "ok",
            "answer": answer, "error": "",
            "notebook_id": notebook_id,
            "sources_added": sources_added,
        }

    except Exception as exc:
        try:
            _safe_delete(client, notebook_id)
        except Exception:
            pass
        err = str(exc)
        if "Authentication" in err or "expired" in err.lower() or "login" in err.lower():
            err = AUTH_HINT
        elif "code 8" in err or "UserDisplayableError" in err:
            err = (
                "NotebookLM returned quota error (code 8). "
                "This is usually a transient rate-limit. Wait 1-2 minutes and try again."
            )
        return {
            "module_key": module_key, "status": "error",
            "answer": "", "error": err,
            "notebook_id": notebook_id, "sources_added": sources_added,
        }


def build_deep_research_context(
    research_results: dict,
    selected_modules: list[str] | None = None,
) -> str:
    """Format successful module results into a prompt-injectable string."""
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
