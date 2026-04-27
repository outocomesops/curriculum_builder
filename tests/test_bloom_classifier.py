from unittest.mock import patch

from analyzers import bloom_classifier as bc
from tests.conftest import FakeResponse


def test_keyword_classify_exact_and_partial_matches():
    index = {"analyze": "analyze", "evaluate": "evaluate"}
    assert bc._keyword_classify("analyze", index) == "analyze"
    assert bc._keyword_classify("analy", index) == "analyze"
    assert bc._keyword_classify("unknown", index) is None


@patch("analyzers.bloom_classifier.requests.post")
def test_ollama_classify_returns_level_on_valid_response(mock_post):
    mock_post.return_value = FakeResponse(
        json_data={"message": {"content": "Apply\nExplanation ignored"}},
        status_code=200,
    )
    assert bc._ollama_classify("implement", "Implement features", "http://x", "m") == "apply"


@patch("analyzers.bloom_classifier.requests.post")
def test_ollama_classify_returns_none_on_error(mock_post):
    mock_post.side_effect = RuntimeError("offline")
    assert bc._ollama_classify("implement", "Implement features", "http://x", "m") is None


def test_classify_verb_keyword_path():
    res = bc.classify_verb("evaluate", "Evaluate designs", {"evaluate": "evaluate"}, use_ollama_fallback=False)
    assert res.bloom_level == "evaluate"
    assert res.source == "keyword"
    assert res.confidence == 1.0


@patch("analyzers.bloom_classifier._ollama_classify")
def test_classify_verb_llm_fallback_path(mock_llm):
    mock_llm.return_value = "apply"
    res = bc.classify_verb("prototype", "Prototype a solution", {}, use_ollama_fallback=True)
    assert res.bloom_level == "apply"
    assert res.source == "llm"
    assert res.confidence == 0.75


@patch("analyzers.bloom_classifier._ollama_classify")
def test_classify_verb_unclassified_path(mock_llm):
    mock_llm.return_value = None
    res = bc.classify_verb("prototype", "Prototype a solution", {}, use_ollama_fallback=True)
    assert res.bloom_level is None
    assert res.source == "unclassified"
