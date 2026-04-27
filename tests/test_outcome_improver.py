import json
from unittest.mock import patch

from generator import outcome_improver as oi
from tests.conftest import FakeResponse


@patch("generator.outcome_improver.requests.post")
def test_improve_outcome_streams_tokens_and_ignores_bad_lines(mock_post):
    payload = [
        json.dumps({"message": {"content": "Students will "}, "done": False}).encode("utf-8"),
        b"{bad json",
        json.dumps({"message": {"content": "design secure systems."}, "done": True}).encode("utf-8"),
    ]
    mock_post.return_value = FakeResponse(iter_lines_data=payload, status_code=200)
    out = "".join(list(oi.improve_outcome("prompt", "http://x", "m")))
    assert out == "Students will design secure systems."


@patch("generator.outcome_improver.improve_outcome")
def test_improve_outcome_sync_handles_exception(mock_improve):
    mock_improve.side_effect = RuntimeError("boom")
    assert oi.improve_outcome_sync("prompt") == ""
