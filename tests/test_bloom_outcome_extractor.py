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


def test_parse_section_extracts_peos():
    items = boe._parse_section(SAMPLE_MD, r"#\s*Program Educational Objectives", strip_bold=False)
    assert items == [
        {"num": 1, "text": "Demonstrate professional communication."},
        {"num": 2, "text": "Apply software engineering practices."},
    ]


def test_parse_section_extracts_slos_strips_bold_prefix():
    items = boe._parse_section(SAMPLE_MD, r"#\s*Student Learning Outcomes", strip_bold=True)
    assert items == [
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
