from pathlib import Path

import config


def test_constants_have_expected_types():
    assert isinstance(config.OLLAMA_DEFAULT_URL, str)
    assert config.OLLAMA_DEFAULT_URL.startswith("http")
    assert isinstance(config.OUTPUTS_DIR, Path)
    assert isinstance(config.JOB_MARKET_DB, Path)
    assert isinstance(config.QUALITY_SOURCES_DIR, Path)
    assert isinstance(config.INSTITUTIONAL_DOCS_DIR, Path)
    assert isinstance(config.INSTITUTIONS_DIR, Path)


def test_supported_languages_has_english():
    assert "English" in config.SUPPORTED_LANGUAGES
    assert config.SUPPORTED_LANGUAGES["English"] == "English"


def test_program_levels_non_empty_and_strings():
    assert len(config.PROGRAM_LEVELS) >= 1
    assert "Undergraduate" in config.PROGRAM_LEVELS
    assert all(isinstance(x, str) for x in config.PROGRAM_LEVELS)
