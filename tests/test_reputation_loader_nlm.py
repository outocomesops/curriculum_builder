from unittest.mock import patch

import pytest

from loaders import reputation_loader_nlm as rln


class FakeCompletedProcess:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _notebook_id():
    return "12345678-aaaa-bbbb-cccc-1234567890ab"


@patch("loaders.reputation_loader_nlm.subprocess.run")
def test_run_nlm_strips_output(mock_run):
    mock_run.return_value = FakeCompletedProcess(stdout=" hello \n", stderr=" err ", returncode=0)
    out, err, rc = rln._run_nlm(["notebook", "list"])
    assert out == "hello"
    assert err == "err"
    assert rc == 0


@patch("loaders.reputation_loader_nlm.subprocess.run")
def test_create_notebook_parses_uuid(mock_run):
    mock_run.return_value = FakeCompletedProcess(
        stdout=f"Created notebook {_notebook_id()} OK", returncode=0
    )
    nid = rln._create_notebook("MyUni")
    assert nid == _notebook_id()


@patch("loaders.reputation_loader_nlm.subprocess.run")
def test_create_notebook_fails_on_nonzero(mock_run):
    mock_run.return_value = FakeCompletedProcess(stderr="denied", returncode=1)
    with pytest.raises(RuntimeError, match="Failed to create"):
        rln._create_notebook("MyUni")


@patch("loaders.reputation_loader_nlm.subprocess.run")
def test_create_notebook_fails_when_uuid_not_found(mock_run):
    mock_run.return_value = FakeCompletedProcess(stdout="no uuid here", returncode=0)
    with pytest.raises(RuntimeError, match="Could not parse"):
        rln._create_notebook("MyUni")


@patch("loaders.reputation_loader_nlm.subprocess.run")
def test_query_notebook_parses_json(mock_run):
    mock_run.return_value = FakeCompletedProcess(
        stdout='{"value": {"answer": "Great reputation."}}', returncode=0
    )
    assert rln._query_notebook(_notebook_id(), "q?") == "Great reputation."


@patch("loaders.reputation_loader_nlm.subprocess.run")
def test_query_notebook_falls_back_to_raw_stdout(mock_run):
    mock_run.return_value = FakeCompletedProcess(stdout="not json", returncode=0)
    assert rln._query_notebook(_notebook_id(), "q?") == "not json"


@patch("loaders.reputation_loader_nlm.subprocess.run")
def test_query_notebook_raises_on_failure(mock_run):
    mock_run.return_value = FakeCompletedProcess(stderr="auth expired", returncode=1)
    with pytest.raises(RuntimeError, match="query failed"):
        rln._query_notebook(_notebook_id(), "q?")


@patch("loaders.reputation_loader_nlm.subprocess.run")
def test_delete_notebook_swallows_errors(mock_run):
    mock_run.side_effect = RuntimeError("cannot delete")
    # Should not raise
    rln.delete_notebook(_notebook_id())


@patch("loaders.reputation_loader_nlm.subprocess.run")
def test_add_sources_best_effort_returns_only_successes(mock_run):
    # First call succeeds, second fails
    mock_run.side_effect = [
        FakeCompletedProcess(returncode=0),
        FakeCompletedProcess(returncode=1, stderr="nope"),
    ]
    added = rln._add_sources_best_effort(_notebook_id(), ["https://a", "https://b"])
    assert added == ["https://a"]


@patch("loaders.reputation_loader_nlm._create_notebook")
@patch("loaders.reputation_loader_nlm._add_text_seed")
@patch("loaders.reputation_loader_nlm._add_sources_best_effort")
@patch("loaders.reputation_loader_nlm._query_notebook")
@patch("loaders.reputation_loader_nlm.delete_notebook")
def test_fetch_reputation_full_pipeline(
    mock_delete, mock_query, mock_add_urls, mock_add_seed, mock_create
):
    mock_create.return_value = _notebook_id()
    mock_query.return_value = "Great summary."
    mock_add_urls.return_value = ["https://x"]

    nid, summary = rln.fetch_reputation_via_notebooklm(
        "MyUni", city="Boston", extra_urls=["https://x"], cleanup=True
    )

    assert nid == _notebook_id()
    assert summary == "Great summary."
    mock_add_seed.assert_called_once()
    mock_add_urls.assert_called_once()
    mock_delete.assert_called_once_with(_notebook_id())


@patch("loaders.reputation_loader_nlm._create_notebook")
@patch("loaders.reputation_loader_nlm._add_text_seed")
@patch("loaders.reputation_loader_nlm._query_notebook")
@patch("loaders.reputation_loader_nlm.delete_notebook")
def test_fetch_reputation_no_cleanup(mock_delete, mock_query, mock_seed, mock_create):
    mock_create.return_value = _notebook_id()
    mock_query.return_value = "ans"
    rln.fetch_reputation_via_notebooklm("MyUni", cleanup=False)
    mock_delete.assert_not_called()
