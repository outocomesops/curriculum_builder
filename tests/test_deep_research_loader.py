from unittest.mock import patch

import pytest

from loaders import deep_research_loader as drl


class FakeCompletedProcess:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


NB_ID = "12345678-aaaa-bbbb-cccc-1234567890ab"


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


@patch("loaders.deep_research_loader._delete_notebook")
@patch("loaders.deep_research_loader._query_notebook")
@patch("loaders.deep_research_loader._add_url_sources_best_effort")
@patch("loaders.deep_research_loader._add_text_source")
@patch("loaders.deep_research_loader._create_notebook")
def test_run_research_module_success_with_cleanup(
    mock_create, mock_add_text, mock_add_urls, mock_query, mock_delete
):
    mock_create.return_value = NB_ID
    mock_query.return_value = "Findings."
    mock_add_urls.return_value = ["https://a"]

    msgs = []
    res = drl.run_research_module(
        "legal_framework", "MyUni", "CS",
        extra_urls=["https://a"],
        cleanup=True,
        progress_callback=msgs.append,
    )
    assert res["status"] == "ok"
    assert res["answer"] == "Findings."
    assert res["sources_added"] == 1
    assert res["notebook_id"] == ""  # cleaned up → blanked out
    mock_delete.assert_called_once_with(NB_ID)
    assert len(msgs) >= 3


@patch("loaders.deep_research_loader._delete_notebook")
@patch("loaders.deep_research_loader._query_notebook")
@patch("loaders.deep_research_loader._add_text_source")
@patch("loaders.deep_research_loader._create_notebook")
def test_run_research_module_no_cleanup_keeps_id(
    mock_create, mock_add_text, mock_query, mock_delete
):
    mock_create.return_value = NB_ID
    mock_query.return_value = "."
    res = drl.run_research_module("legal_framework", "U", "P", cleanup=False)
    assert res["notebook_id"] == NB_ID
    mock_delete.assert_not_called()


@patch("loaders.deep_research_loader._delete_notebook")
@patch("loaders.deep_research_loader._create_notebook")
def test_run_research_module_catches_exception(mock_create, mock_delete):
    mock_create.side_effect = RuntimeError("nlm not found")
    res = drl.run_research_module("legal_framework", "U", "P")
    assert res["status"] == "error"
    assert "nlm not found" in res["error"]


@patch("loaders.deep_research_loader.subprocess.run")
def test_create_notebook_parses_uuid(mock_run):
    mock_run.return_value = FakeCompletedProcess(
        stdout=f"created {NB_ID}", returncode=0
    )
    assert drl._create_notebook("title") == NB_ID


@patch("loaders.deep_research_loader.subprocess.run")
def test_create_notebook_raises_on_error(mock_run):
    mock_run.return_value = FakeCompletedProcess(stderr="bad", returncode=1)
    with pytest.raises(RuntimeError):
        drl._create_notebook("title")


@patch("loaders.deep_research_loader.subprocess.run")
def test_query_notebook_handles_plain_json(mock_run):
    mock_run.return_value = FakeCompletedProcess(
        stdout='{"answer": "plain"}', returncode=0
    )
    assert drl._query_notebook(NB_ID, "q") == "plain"


@patch("loaders.deep_research_loader.subprocess.run")
def test_add_url_sources_best_effort_silent_on_exceptions(mock_run):
    mock_run.side_effect = [
        FakeCompletedProcess(returncode=0),
        RuntimeError("network error"),
    ]
    got = drl._add_url_sources_best_effort(NB_ID, ["https://a", "https://b"])
    assert got == ["https://a"]
