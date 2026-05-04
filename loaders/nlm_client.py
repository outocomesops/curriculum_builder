"""
Factory for NotebookLMClient using saved auth credentials.

Auth tokens live in ~/.notebooklm-mcp-cli/profiles/default/
and are written by `nlm login`. Both this module and the nlm CLI/MCP
server read from the same location, so a single `nlm login` fixes all.
"""
from __future__ import annotations

import json
from pathlib import Path

AUTH_HINT = (
    "NotebookLM authentication has expired.\n"
    "Fix: type  ! nlm login  in the Claude Code prompt (opens a browser to re-authenticate).\n"
    "After logging in, try again."
)

_PROFILE_DIR = Path.home() / ".notebooklm-mcp-cli" / "profiles" / "default"


def check_auth() -> tuple[bool, str]:
    """
    Return (ok, message).

    Checks file presence and token age (>7 days = likely expired).
    Does NOT make a network call — use get_nlm_client() + an API call for that.
    """
    import time

    cookies_file = _PROFILE_DIR / "cookies.json"
    metadata_file = _PROFILE_DIR / "metadata.json"

    if not cookies_file.exists():
        return False, AUTH_HINT
    try:
        cookies = json.loads(cookies_file.read_text(encoding="utf-8"))
        if not cookies:
            return False, AUTH_HINT
    except Exception:
        return False, AUTH_HINT

    # Check token age via metadata last_validated timestamp
    if metadata_file.exists():
        try:
            meta = json.loads(metadata_file.read_text(encoding="utf-8"))
            from datetime import datetime
            last_validated_str = meta.get("last_validated", "")
            if last_validated_str:
                last_validated = datetime.fromisoformat(last_validated_str)
                age_days = (datetime.now() - last_validated).days
                if age_days > 7:
                    return False, (
                        f"NotebookLM auth tokens are {age_days} days old (last login: "
                        f"{last_validated.strftime('%Y-%m-%d')}) and are likely expired.\n"
                        + AUTH_HINT
                    )
        except Exception:
            pass

    return True, ""


def get_nlm_client():
    """
    Create a NotebookLMClient from saved auth credentials.

    Raises RuntimeError with a user-readable message if auth is missing
    or expired. The caller should surface that message in the Streamlit UI.
    """
    import httpx
    from notebooklm_tools.core.client import NotebookLMClient
    from notebooklm_tools.core.errors import ClientAuthenticationError

    cookies_file = _PROFILE_DIR / "cookies.json"
    metadata_file = _PROFILE_DIR / "metadata.json"

    if not cookies_file.exists():
        raise RuntimeError(AUTH_HINT)

    try:
        cookies = json.loads(cookies_file.read_text(encoding="utf-8"))
        metadata: dict = {}
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

        client = NotebookLMClient(
            cookies=cookies,
            csrf_token=metadata.get("csrf_token", ""),
            session_id=metadata.get("session_id", ""),
            build_label=metadata.get("build_label", ""),
        )

        # The underlying httpx.Client defaults to timeout=30s, which is too short
        # for get_notebook() calls on notebooks with many sources (~30 after research
        # passes). Patch it to 120s so all RPC calls without explicit timeouts
        # (get_notebook, poll_research, etc.) have enough headroom.
        http = client._get_client()
        http.timeout = httpx.Timeout(120.0)

        return client

    except ClientAuthenticationError as exc:
        raise RuntimeError(AUTH_HINT) from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to initialise NotebookLM client: {exc}\n\n{AUTH_HINT}") from exc
