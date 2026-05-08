import json
from unittest.mock import patch

import requests

from generator import curriculum_gen as cg
from tests.conftest import FakeResponse


def _stream_response(chunks: list[str], status: int = 200) -> FakeResponse:
    lines = [json.dumps({"message": {"content": c}}).encode() for c in chunks]
    return FakeResponse(status_code=status, iter_lines_data=lines)


@patch("generator.curriculum_gen.requests.get")
def test_list_ollama_models_success(mock_get):
    mock_get.return_value = FakeResponse(
        json_data={"models": [{"name": "llama3"}, {"name": "mistral"}]}, status_code=200
    )
    assert cg.list_ollama_models("http://x") == ["llama3", "mistral"]


@patch("generator.curriculum_gen.requests.get")
def test_list_ollama_models_failure_returns_empty(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("down")
    assert cg.list_ollama_models("http://x") == []


@patch("generator.curriculum_gen.requests.post")
def test_stream_yields_chunks(mock_post):
    mock_post.return_value = _stream_response(["Hello ", "world"])
    out = "".join(cg._stream("http://x", "m", "prompt"))
    assert out == "Hello world"


@patch("generator.curriculum_gen.requests.post")
def test_stream_connection_error_message(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("gone")
    out = "".join(cg._stream("http://x", "m", "p"))
    assert "Cannot reach Ollama" in out


@patch("generator.curriculum_gen.requests.post")
def test_stream_timeout_message(mock_post):
    mock_post.side_effect = requests.exceptions.Timeout("slow")
    out = "".join(cg._stream("http://x", "m", "p"))
    assert "timed out" in out


@patch("generator.curriculum_gen.requests.post")
def test_stream_http_error_message(mock_post):
    resp = FakeResponse(status_code=404)
    err = requests.exceptions.HTTPError("404")
    err.response = resp
    mock_post.side_effect = err
    out = "".join(cg._stream("http://x", "m", "p"))
    assert "HTTP 404" in out


@patch("generator.curriculum_gen.requests.post")
def test_stream_generic_exception(mock_post):
    mock_post.side_effect = RuntimeError("weird")
    out = "".join(cg._stream("http://x", "m", "p"))
    assert "weird" in out


@patch("generator.curriculum_gen._stream")
def test_generate_learning_outcomes_injects_all_contexts(mock_stream):
    captured = {}
    def fake(ollama_url, model, prompt):
        captured["prompt"] = prompt
        yield "ok"

    mock_stream.side_effect = fake

    out = "".join(
        cg.generate_learning_outcomes(
            program_name="CS BSc",
            program_level="Undergraduate",
            program_scope="Computing",
            skills_context="Skill ctx",
            accreditation_context="Accred ctx",
            institutional_context="Inst ctx",
            language="English",
            ollama_url="http://x",
            model="m",
            reputation_context="Rep ctx",
            program_specs_context="Specs ctx",
            deep_research_context="=== DEEP RESEARCH INTELLIGENCE === body",
        )
    )
    prompt = captured["prompt"]
    assert out == "ok"
    assert "CS BSc" in prompt
    assert "Skill ctx" in prompt and "Accred ctx" in prompt
    assert "Inst ctx" in prompt
    assert "Rep ctx" in prompt
    assert "Specs ctx" in prompt
    assert "DEEP RESEARCH INTELLIGENCE" in prompt
    assert "Student Learning Outcomes" in prompt  # non-CE branch
    assert "Write entirely in English." in prompt


@patch("generator.curriculum_gen._stream")
def test_generate_learning_outcomes_continuous_education_branch(mock_stream):
    captured = {}
    def fake(ollama_url, model, prompt):
        captured["prompt"] = prompt
        yield ""

    mock_stream.side_effect = fake

    list(cg.generate_learning_outcomes(
        program_name="Data Bootcamp",
        program_level="Continuous Education",
        program_scope="Data",
        skills_context="s",
        accreditation_context="a",
        institutional_context="i",
        language="English",
        ollama_url="http://x",
        model="m",
        course_hours=40,
    ))
    prompt = captured["prompt"]
    assert "TOTAL CONTACT HOURS: 40" in prompt
    assert "Learning Objectives" in prompt
    assert "Participant Profile" in prompt
    # Should not include SLO section
    assert "Student Learning Outcomes" not in prompt


@patch("generator.curriculum_gen._stream")
def test_generate_learning_outcomes_suppresses_empty_deep_research(mock_stream):
    captured = {}
    def fake(ollama_url, model, prompt):
        captured["prompt"] = prompt
        yield ""
    mock_stream.side_effect = fake
    list(cg.generate_learning_outcomes(
        "P", "Undergraduate", "F", "s", "a", "i", "English",
        "http://x", "m", deep_research_context="No deep research data available.",
    ))
    assert "No deep research" not in captured["prompt"]


@patch("generator.curriculum_gen._stream")
def test_generate_course_list_ce_hours(mock_stream):
    captured = {}
    def fake(u, m, p):
        captured["prompt"] = p
        yield ""
    mock_stream.side_effect = fake
    list(cg.generate_course_list(
        "CE Program", "Continuous Education", "outcomes", "skills", "accred",
        "English", "http://x", "m", course_hours=30,
    ))
    prompt = captured["prompt"]
    assert "TOTAL CONTACT HOURS: 30" in prompt
    assert "Continuous Education (30 total contact hours)" in prompt


@patch("generator.curriculum_gen._stream")
def test_generate_course_list_standard(mock_stream):
    captured = {}
    def fake(u, m, p):
        captured["prompt"] = p
        yield ""
    mock_stream.side_effect = fake
    list(cg.generate_course_list(
        "BSc", "Undergraduate", "outcomes", "skills", "accred",
        "English", "http://x", "m", program_duration_semesters=8,
    ))
    prompt = captured["prompt"]
    assert "8 semesters" in prompt


@patch("generator.curriculum_gen._stream")
def test_generate_competency_map(mock_stream):
    captured = {}
    def fake(u, m, p):
        captured["prompt"] = p
        yield "t"
    mock_stream.side_effect = fake
    list(cg.generate_competency_map(
        "BSc", "SLOs...", "Course list...", "English", "http://x", "m"
    ))
    assert "Competency Map" in captured["prompt"]
    assert "BSc" in captured["prompt"]


@patch("generator.curriculum_gen._stream")
def test_generate_syllabus(mock_stream):
    captured = {}
    def fake(u, m, p):
        captured["prompt"] = p
        yield ""
    mock_stream.side_effect = fake
    list(cg.generate_syllabus(
        "CS101", "Intro to CS", "BSc CS", "SLO1, SLO2", "skills",
        "English", "http://x", "m",
    ))
    prompt = captured["prompt"]
    assert "CS101" in prompt
    assert "Intro to CS" in prompt
    assert "Weekly Schedule" in prompt
    assert "Assessment Plan" in prompt
