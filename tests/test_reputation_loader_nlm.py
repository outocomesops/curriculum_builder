"""
Tests for loaders/reputation_loader_nlm.py

The module uses get_nlm_client() to obtain an NLM API client object.
All tests mock that factory and drive a mock client.
"""
from unittest.mock import MagicMock, patch, call

import pytest

from loaders import reputation_loader_nlm as rln

NID = "12345678-aaaa-bbbb-cccc-1234567890ab"


def _make_client() -> MagicMock:
    """Return a mock NLM client pre-configured for a happy-path run."""
    client = MagicMock()
    nb = MagicMock()
    nb.id = NID
    client.create_notebook.return_value = nb
    client.start_research.return_value = {"task_id": "t1"}
    client.poll_research.return_value = {"status": "completed", "sources": ["https://s1.com"]}
    client.query.return_value = {"answer": "Great reputation."}
    return client


# ── Happy path ────────────────────────────────────────────────────────────────

@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_fetch_returns_answer_with_cleanup(mock_get):
    client = _make_client()
    mock_get.return_value = client

    nid, answer = rln.fetch_reputation_via_notebooklm(
        "MyUni", city="Boston", cleanup=True, research_timeout=10
    )
    assert answer == "Great reputation."
    assert nid == ""  # notebook deleted, id cleared
    client.delete_notebook.assert_called_once_with(NID)


@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_fetch_returns_notebook_id_when_no_cleanup(mock_get):
    client = _make_client()
    mock_get.return_value = client

    nid, answer = rln.fetch_reputation_via_notebooklm(
        "MyUni", cleanup=False, research_timeout=10
    )
    assert nid == NID
    assert answer == "Great reputation."
    client.delete_notebook.assert_not_called()


@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_text_seed_always_added(mock_get):
    client = _make_client()
    mock_get.return_value = client

    rln.fetch_reputation_via_notebooklm("MyUni", cleanup=True, research_timeout=10)
    client.add_text_source.assert_called_once()
    _, kwargs = client.add_text_source.call_args
    assert "MyUni" in kwargs.get("text", "") or "MyUni" in str(client.add_text_source.call_args)


# ── Extra URLs ─────────────────────────────────────────────────────────────────

@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_extra_urls_all_added(mock_get):
    client = _make_client()
    mock_get.return_value = client

    rln.fetch_reputation_via_notebooklm(
        "MyUni", extra_urls=["https://a.com", "https://b.com"],
        cleanup=True, research_timeout=10,
    )
    assert client.add_url_source.call_count == 2


@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_extra_urls_partial_failure_does_not_raise(mock_get):
    client = _make_client()
    client.add_url_source.side_effect = [None, RuntimeError("blocked")]
    mock_get.return_value = client

    rln.fetch_reputation_via_notebooklm(
        "MyUni", extra_urls=["https://a.com", "https://b.com"],
        cleanup=True, research_timeout=10,
    )  # must not raise


# ── Research edge cases ────────────────────────────────────────────────────────

@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_research_failed_status_continues_to_query(mock_get):
    client = _make_client()
    client.poll_research.return_value = {"status": "failed"}
    mock_get.return_value = client

    _, answer = rln.fetch_reputation_via_notebooklm("MyUni", cleanup=True, research_timeout=10)
    assert answer == "Great reputation."
    client.query.assert_called_once()


@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_research_start_exception_continues_with_seed_only(mock_get):
    client = _make_client()
    client.start_research.side_effect = RuntimeError("quota exceeded")
    mock_get.return_value = client

    _, answer = rln.fetch_reputation_via_notebooklm("MyUni", cleanup=True, research_timeout=10)
    assert answer == "Great reputation."
    client.poll_research.assert_not_called()
    client.query.assert_called_once()


@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_deep_mode_falls_back_to_fast_on_code8(mock_get):
    client = _make_client()
    client.start_research.side_effect = [
        RuntimeError("UserDisplayableError code 8 quota"),
        {"task_id": "t2"},
    ]
    mock_get.return_value = client

    _, answer = rln.fetch_reputation_via_notebooklm(
        "MyUni", research_mode="deep", cleanup=True, research_timeout=10
    )
    assert answer == "Great reputation."
    assert client.start_research.call_count == 2


# ── Auth failures ──────────────────────────────────────────────────────────────

@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_auth_failure_from_client_factory_re_raises(mock_get):
    mock_get.side_effect = RuntimeError("Authentication failed — run nlm login")
    with pytest.raises(RuntimeError):
        rln.fetch_reputation_via_notebooklm("MyUni")


# ── Progress callback ──────────────────────────────────────────────────────────

@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_progress_callback_invoked_at_key_stages(mock_get):
    client = _make_client()
    mock_get.return_value = client

    messages: list[str] = []
    rln.fetch_reputation_via_notebooklm(
        "MyUni", cleanup=True, research_timeout=10,
        progress_callback=lambda msg: messages.append(msg),
    )
    assert any("Creating" in m for m in messages)
    assert any("seed" in m.lower() or "Querying" in m for m in messages)


# ── delete_notebook helpers ───────────────────────────────────────────────────

def test_delete_notebook_empty_id_does_not_raise():
    rln.delete_notebook("")


@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_delete_notebook_swallows_client_errors(mock_get):
    client = MagicMock()
    client.delete_notebook.side_effect = RuntimeError("cannot delete")
    mock_get.return_value = client
    rln.delete_notebook(NID)  # must not raise


@patch("loaders.reputation_loader_nlm.get_nlm_client")
def test_safe_delete_skips_empty_id(mock_get):
    client = MagicMock()
    mock_get.return_value = client
    rln._safe_delete(client, "")
    client.delete_notebook.assert_not_called()
