"""
Reputation loader using the notebooklm_tools Python API directly.

Pipeline:
  1. Create a notebook titled "Reputation: <institution>"
  2. Add a text seed source (baseline context)
  3. Start NLM native web research and wait for completion
  4. Import discovered sources into the notebook
  5. Optionally add any caller-supplied extra URLs
  6. Query the notebook for a reputation summary
  7. Optionally delete the notebook
  8. Return (notebook_id, summary_text)

No subprocess calls — uses notebooklm_tools directly so auth and error
handling are consistent with the MCP server.
"""
from __future__ import annotations

import time
from typing import Callable

from .nlm_client import AUTH_HINT, get_nlm_client

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

_DEFAULT_RESEARCH_TIMEOUT: int = 120   # fast mode completes in ~30s; deep may not be available
_POLL_INTERVAL: int = 10              # seconds between research status polls


def fetch_reputation_via_notebooklm(
    institution_name: str,
    city: str = "",
    extra_urls: list[str] | None = None,
    cleanup: bool = True,
    research_timeout: int = _DEFAULT_RESEARCH_TIMEOUT,
    research_mode: str = "fast",
    query_timeout: int = 300,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    """
    Research public reputation of an institution using NotebookLM.

    Returns (notebook_id, reputation_summary_text).
    Raises RuntimeError on auth failure (with instructions) or API errors.
    """
    def _cb(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    search_name = f"{institution_name} {city}".strip() if city else institution_name

    try:
        client = get_nlm_client()
    except RuntimeError:
        raise

    notebook_id = ""
    try:
        # Step 1: create notebook
        _cb("Creating NotebookLM notebook…")
        nb = client.create_notebook(title=f"Reputation: {institution_name}")
        notebook_id = nb.id if hasattr(nb, "id") else str(nb)

        # Step 2: text seed so notebook always has at least one source
        location = f" in {city}" if city else ""
        seed = (
            f"{institution_name} is a higher education institution{location}. "
            f"This notebook researches the public reputation, academic programs, "
            f"student experience, graduate outcomes, and community standing of {institution_name}."
        )
        _cb("Adding text seed source…")
        client.add_text_source(notebook_id, text=seed, title="Research seed", wait=True)

        # Step 3: start NLM native web research
        research_query = _REPUTATION_RESEARCH_QUERY.format(name=search_name)
        mode_label = "deep (~5 min, ~40 sources)" if research_mode == "deep" else "fast (~30 s, ~10 sources)"
        _cb(f"Starting NLM {mode_label} research…")
        try:
            task = client.start_research(notebook_id, query=research_query, source="web", mode=research_mode)
        except Exception as exc:
            err = str(exc)
            if research_mode == "deep" and ("code 8" in err or "UserDisplayableError" in err):
                _cb("Deep research unavailable on this account — falling back to fast mode…")
                try:
                    task = client.start_research(notebook_id, query=research_query, source="web", mode="fast")
                except Exception:
                    task = None
            else:
                _cb(f"Research start failed: {err[:120]} — continuing with seed source only.")
                task = None

        if task:
            task_id = task.get("task_id")
            # Step 4: poll until complete then import
            deadline = time.time() + research_timeout
            while time.time() < deadline:
                status_data = client.poll_research(notebook_id, target_task_id=task_id, target_query=research_query)
                status = (status_data or {}).get("status", "")
                if status == "completed":
                    sources_found = (status_data or {}).get("sources", [])
                    _cb(f"Research complete — importing {len(sources_found)} source(s)…")
                    client.import_research_sources(notebook_id, task_id, sources_found)
                    _cb(f"Imported {len(sources_found)} source(s).")
                    break
                elif status in ("failed", "error"):
                    _cb(f"Research ended with status '{status}' — continuing with seed only.")
                    break
                _cb(f"Research status: {status or 'pending'} — waiting…")
                time.sleep(_POLL_INTERVAL)
            else:
                _cb("Research timed out — continuing with sources found so far.")
        else:
            _cb("Research task did not start — continuing with seed source only.")

        # Step 5: add caller-supplied extra URLs (best-effort)
        if extra_urls:
            _cb(f"Adding {len(extra_urls)} extra URL(s)…")
            added = 0
            for url in extra_urls:
                try:
                    client.add_url_source(notebook_id, url=url, wait=True)
                    added += 1
                except Exception:
                    pass
            _cb(f"{added}/{len(extra_urls)} extra URL(s) added.")

        # Step 6: query
        _cb("Querying NotebookLM for reputation summary…")
        question = _REPUTATION_QUERY.format(name=search_name)
        result = client.query(notebook_id, question, timeout=query_timeout)
        answer = (result or {}).get("answer", "") if isinstance(result, dict) else str(result or "")

        if cleanup:
            _cb("Cleaning up notebook…")
            _safe_delete(client, notebook_id)
            return "", answer
        return notebook_id, answer

    except RuntimeError:
        raise
    except Exception as exc:
        _safe_delete(client, notebook_id)
        err = str(exc)
        if "Authentication" in err or "expired" in err.lower() or "login" in err.lower():
            raise RuntimeError(AUTH_HINT) from exc
        raise RuntimeError(f"NotebookLM reputation research failed: {err}") from exc


def delete_notebook(notebook_id: str) -> None:
    """Delete a notebook by ID (best-effort, never raises)."""
    if not notebook_id:
        return
    try:
        client = get_nlm_client()
        _safe_delete(client, notebook_id)
    except Exception:
        pass


def _safe_delete(client, notebook_id: str) -> None:
    if not notebook_id:
        return
    try:
        client.delete_notebook(notebook_id)
    except Exception:
        pass
