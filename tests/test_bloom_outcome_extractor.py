from loaders import bloom_outcome_extractor as boe


SAMPLE_MD = """
# Program Educational Objectives
1. Demonstrate professional communication.
2. Apply software engineering practices.

# Student Learning Outcomes
1. **Programming Fundamentals** - Build robust scripts.
2. **Ethics**
""".strip()


def test_clean_strips_whitespace_and_markers():
    assert boe._clean("  **Text**  ") == "Text"


def test_parse_peos_extracts_numbered_items():
    peos = boe._parse_peos(SAMPLE_MD)
    assert peos == [
        {"num": 1, "text": "Demonstrate professional communication."},
        {"num": 2, "text": "Apply software engineering practices."},
    ]


def test_parse_slos_handles_title_prefix_and_fallback():
    slos = boe._parse_slos(SAMPLE_MD)
    assert slos == [
        {"num": 1, "text": "Build robust scripts."},
        {"num": 2, "text": "Ethics"},
    ]


def test_extract_outcomes_from_markdown_builds_records():
    rows = boe.extract_outcomes_from_markdown(
        SAMPLE_MD,
        program_name="BASc",
        institution_name="My College",
    )
    assert len(rows) == 4
    assert rows[0].id == "PEO-1"
    assert rows[0].outcome_type == "PEO"
    assert rows[-1].id == "SLO-2"
    assert "My College" in rows[-1].context
