"""
Reputation loader using NotebookLM via the nlm CLI.

Pipeline:
  1. Create a notebook titled "Reputation: <institution>"
  2. Add a text seed source (baseline context)
  3. Run NLM's native web research (`nlm research start --auto-import`) so NLM
     discovers and ingests real sources about the institution's reputation
  4. Optionally add any caller-supplied extra URLs
  5. Query the notebook
  6. Optionally delete the notebook
  7. Return (notebook_id, summary_text)
"""
from __future__ import annotations

import json
import re
import subprocess


_REPUTATION_QUERY = (
    "What do students, graduates, and the community think about {name}? "
    "Summarise the public reputation covering: overall sentiment, praised programs "
    "or services, criticisms or complaints, graduate employment outcomes, community "
    "relationships, notable achievements, and any significant recent events. "
    "Be specific and cite notable details from the sources."
)

_REPUTATION_RESEARCH_QUERY = (
    "{name} reputation reviews student experience graduate outcomes public perception"
)

_DEFAULT_RESEARCH_TIMEOUT: int = 420   # 7 min covers NLM deep mode (~5 min) + import


def _run_nlm(args: list[str], timeout: int = 180) -> tuple[str, str, int]:
    result = subprocess.run(
        ["nlm"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def _create_notebook(institution_name: str) -> str:
    title = f"Reputation: {institution_name}"
    stdout, stderr, rc = _run_nlm(["notebook", "create", title])
    if rc != 0:
        raise RuntimeError(f"Failed to create notebook: {stderr}")
    match = re.search(
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        stdout,
    )
    if not match:
        raise RuntimeError(f"Could not parse notebook ID from nlm output: {stdout}")
    return match.group(1)


def _add_text_seed(notebook_id: str, institution_name: str, city: str = "") -> None:
    """Add a minimal text source so the notebook always has at least one source."""
    location = f" in {city}" if city else ""
    seed = (
        f"{institution_name} is a higher education institution{location}. "
        f"This notebook researches the public reputation, academic programs, "
        f"student experience, graduate outcomes, and community standing of {institution_name}."
    )
    _run_nlm(
        ["source", "add", notebook_id, "--text", seed, "--title", "Research seed", "--wait"],
        timeout=60,
    )


def _run_nlm_research(
    notebook_id: str,
    query: str,
    mode: str = "deep",
    timeout: int = _DEFAULT_RESEARCH_TIMEOUT,
) -> tuple[str, str, int]:
    """
    Triggers NLM's native web research and waits until discovered sources are
    imported into the notebook. --auto-import handles status polling + import.
    """
    return _run_nlm(
        ["research", "start", query,
         "--notebook-id", notebook_id,
         "--mode", mode,
         "--auto-import"],
        timeout=timeout,
    )


def _add_sources_best_effort(
    notebook_id: str,
    urls: list[str],
    timeout: int = 90,
) -> list[str]:
    """Add caller-supplied extra URLs on top of NLM-researched sources."""
    added: list[str] = []
    for url in urls:
        _, _, rc = _run_nlm(
            ["source", "add", notebook_id, "--url", url,
             "--wait", "--wait-timeout", "60"],
            timeout=timeout,
        )
        if rc == 0:
            added.append(url)
    return added


def _query_notebook(notebook_id: str, question: str, timeout: int = 120) -> str:
    stdout, stderr, rc = _run_nlm(
        ["notebook", "query", "--json", notebook_id, question],
        timeout=timeout,
    )
    if rc != 0:
        raise RuntimeError(f"Notebook query failed: {stderr}")
    try:
        data = json.loads(stdout)
        return data.get("value", {}).get("answer", stdout)
    except json.JSONDecodeError:
        return stdout


def delete_notebook(notebook_id: str) -> None:
    try:
        _run_nlm(["notebook", "delete", "-y", notebook_id])
    except Exception:
        pass


def fetch_reputation_via_notebooklm(
    institution_name: str,
    city: str = "",
    extra_urls: list[str] | None = None,
    cleanup: bool = True,
    research_timeout: int = _DEFAULT_RESEARCH_TIMEOUT,
    research_mode: str = "deep",
    query_timeout: int = 120,
) -> tuple[str, str]:
    """
    Research public reputation of an institution using NotebookLM.

    Uses NLM's native web research to find real sources about the institution's
    reputation — NLM discovers its own references rather than relying on an
    external search library.

    Returns (notebook_id, reputation_summary_text).
    """
    search_name = f"{institution_name} {city}".strip() if city else institution_name

    notebook_id = _create_notebook(institution_name)
    try:
        # Always add a text seed so the notebook has guaranteed baseline context
        _add_text_seed(notebook_id, institution_name, city)

        # NLM native web research — discovers and imports real reputation sources
        research_query = _REPUTATION_RESEARCH_QUERY.format(name=search_name)
        _run_nlm_research(notebook_id, research_query, mode=research_mode, timeout=research_timeout)

        # Add any caller-supplied extra URLs on top (best-effort)
        if extra_urls:
            _add_sources_best_effort(notebook_id, extra_urls)

        question = _REPUTATION_QUERY.format(name=search_name)
        answer = _query_notebook(notebook_id, question, timeout=query_timeout)
        return notebook_id, answer
    finally:
        if cleanup:
            delete_notebook(notebook_id)
