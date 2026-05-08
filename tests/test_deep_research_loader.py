from unittest.mock import MagicMock, patch

import pytest

from loaders import deep_research_loader as drl

NB_ID = "12345678-aaaa-bbbb-cccc-1234567890ab"


def _make_client() -> MagicMock:
    """Return a mock NLM client pre-configured for a happy-path run."""
    client = MagicMock()
    nb = MagicMock()
    nb.id = NB_ID
    client.create_notebook.return_value = nb
    client.query.return_value = {"answer": "Findings."}
    return client


def test_get_module_by_key_returns_none_for_unknown():
    assert drl.get_module_by_key("nope") is None


def test_get_module_by_key_returns_legal_framework():
    m = drl.get_module_by_key("legal_framework")
    assert m is not None
    assert m["title"].startswith("Legal Framework")


def test_module_registry_all_keys_unique():
    keys = [m["key"] for m in drl.MODULE_REGISTRY]
    assert len(keys) == len(set(keys))


def test_module_registry_has_required_fields():
    required = {"key", "title", "icon", "description", "seed_text_template", "query_template"}
    for m in drl.MODULE_REGISTRY:
        missing = required - set(m)
        assert not missing, f"Module {m.get('key')} missing {missing}"


def test_build_deep_research_context_empty_results_returns_placeholder():
    assert drl.build_deep_research_context({}) == "No deep research data available."


def test_build_deep_research_context_only_successful_included():
    results = {
        "legal_framework": {"status": "ok", "answer": "Legal content."},
        "competitive_landscape": {"status": "error", "answer": ""},
    }
    ctx = drl.build_deep_research_context(results)
    assert "Legal content." in ctx
    assert "Competitive Landscape" not in ctx


def test_build_deep_research_context_respects_selected_modules():
    results = {
        "legal_framework": {"status": "ok", "answer": "Legal."},
        "student_market": {"status": "ok", "answer": "Market."},
    }
    ctx = drl.build_deep_research_context(results, selected_modules=["student_market"])
    assert "Market." in ctx
    assert "Legal." not in ctx


def test_build_deep_research_context_all_filtered_out():
    results = {"legal_framework": {"status": "ok", "answer": "X"}}
    ctx = drl.build_deep_research_context(results, selected_modules=["student_market"])
    assert ctx == "No deep research data available."


def test_run_research_module_unknown_key_returns_error():
    r = drl.run_research_module("not_a_key", "U", "P")
    assert r["status"] == "error"
    assert "Unknown module" in r["error"]


@patch("loaders.deep_research_loader.get_nlm_client")
@patch("loaders.deep_research_loader._run_all_passes")
def test_run_research_module_success_with_cleanup(mock_passes, mock_get_client):
    client = _make_client()
    mock_get_client.return_value = client
    mock_passes.return_value = 12  # sources_added

    msgs = []
    res = drl.run_research_module(
        "legal_framework", "MyUni", "CS",
        extra_urls=["https://a"],
        cleanup=True,
        progress_callback=msgs.append,
    )
    assert res["status"] == "ok"
    assert res["answer"] == "Findings."
    assert res["notebook_id"] == ""  # cleaned up → blanked
    client.delete_notebook.assert_called_once_with(NB_ID)
    assert len(msgs) >= 2


@patch("loaders.deep_research_loader.get_nlm_client")
@patch("loaders.deep_research_loader._run_all_passes")
def test_run_research_module_no_cleanup_keeps_id(mock_passes, mock_get_client):
    client = _make_client()
    mock_get_client.return_value = client
    mock_passes.return_value = 5

    res = drl.run_research_module("legal_framework", "U", "P", cleanup=False)
    assert res["notebook_id"] == NB_ID
    client.delete_notebook.assert_not_called()


@patch("loaders.deep_research_loader.get_nlm_client")
def test_run_research_module_catches_exception(mock_get_client):
    mock_get_client.side_effect = RuntimeError("nlm not found")
    res = drl.run_research_module("legal_framework", "U", "P")
    assert res["status"] == "error"
    assert "nlm not found" in res["error"]


@patch("loaders.deep_research_loader.get_nlm_client")
@patch("loaders.deep_research_loader._run_all_passes")
def test_run_research_module_extra_urls_added(mock_passes, mock_get_client):
    client = _make_client()
    mock_get_client.return_value = client
    mock_passes.return_value = 8

    drl.run_research_module(
        "legal_framework", "MyUni", "CS",
        extra_urls=["https://a.com", "https://b.com"],
        cleanup=True,
    )
    assert client.add_url_source.call_count == 2


@patch("loaders.deep_research_loader.get_nlm_client")
@patch("loaders.deep_research_loader._run_all_passes")
def test_run_research_module_extra_url_failure_does_not_raise(mock_passes, mock_get_client):
    client = _make_client()
    client.add_url_source.side_effect = RuntimeError("blocked")
    mock_get_client.return_value = client
    mock_passes.return_value = 5

    res = drl.run_research_module(
        "legal_framework", "MyUni", "CS",
        extra_urls=["https://a.com"],
        cleanup=True,
    )
    assert res["status"] == "ok"


@patch("loaders.deep_research_loader.get_nlm_client")
@patch("loaders.deep_research_loader._run_all_passes")
def test_run_research_module_progress_callback_invoked(mock_passes, mock_get_client):
    client = _make_client()
    mock_get_client.return_value = client
    mock_passes.return_value = 10

    messages: list[str] = []
    drl.run_research_module(
        "legal_framework", "MyUni", "CS",
        cleanup=True,
        progress_callback=messages.append,
    )
    assert any("Creating" in m or "notebook" in m.lower() for m in messages)


@patch("loaders.deep_research_loader.get_nlm_client")
@patch("loaders.deep_research_loader._run_all_passes")
def test_run_research_module_query_dict_answer_extracted(mock_passes, mock_get_client):
    client = _make_client()
    client.query.return_value = {"answer": "Detailed findings here."}
    mock_get_client.return_value = client
    mock_passes.return_value = 5

    res = drl.run_research_module("legal_framework", "MyUni", "CS")
    assert res["answer"] == "Detailed findings here."
