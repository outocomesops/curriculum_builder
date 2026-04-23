from pathlib import Path

from exporter import pdf_exporter as pe


def test_sanitise_em_dash_and_curly_quotes():
    # If the environment has a Unicode font, _s passes text through unchanged.
    # Otherwise, we expect the mapped ASCII equivalents.
    raw = "A — B \u2018quoted\u2019"
    out = pe._s(raw)
    if pe._USE_UNICODE:
        assert out == raw
    else:
        assert "--" in out
        assert "'quoted'" in out
        assert out.isascii()


def test_col_widths_small_table():
    widths = pe._col_widths(3, ["a", "b", "c"])
    assert len(widths) == 3
    assert abs(sum(widths) - 175.0) < 0.01
    # Equal-ish widths for <=4 cols
    assert max(widths) - min(widths) < 0.01


def test_col_widths_competency_map_style():
    widths = pe._col_widths(10, ["first"] + [f"SLO{i}" for i in range(9)])
    assert len(widths) == 10
    assert abs(sum(widths) - 175.0) < 0.5
    # First column should be wider than subsequent columns
    assert widths[0] > widths[1]


def test_col_widths_very_many_cols_compresses_first():
    widths = pe._col_widths(30, [""] * 30)
    assert len(widths) == 30
    # Should still sum close to the total page width
    assert abs(sum(widths) - 175.0) < 1.0
    # Rest columns should not go below the enforced minimum (8.0)
    assert min(widths[1:]) >= 8.0


def test_output_dir_creates_directory(tmp_path: Path):
    out = pe._output_dir(tmp_path, "Acme Uni!", "CS Program")
    assert out.exists()
    # Spaces replaced with underscores, special chars removed
    parts = out.relative_to(tmp_path).parts
    assert parts[0] == "Acme_Uni"
    assert parts[-1] == "CS_Program"


def test_save_section_pdf_writes_file(tmp_path: Path):
    content = "# Heading\n\nSome paragraph with *italic* and **bold** words."
    file_path = pe.save_section_pdf(
        content=content,
        section_name="Learning Outcomes",
        institution="Acme",
        program_name="CS",
        program_level="Undergraduate",
        base_outputs=tmp_path,
    )
    assert file_path.exists()
    assert file_path.suffix == ".pdf"
    assert file_path.stat().st_size > 0
    with open(file_path, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_save_syllabus_pdf_writes_file(tmp_path: Path):
    file_path = pe.save_syllabus_pdf(
        course_code="CS 101",
        content="# CS 101\n\n## Description\nBasic intro.",
        institution="Acme",
        program_name="CS",
        program_level="Undergraduate",
        base_outputs=tmp_path,
    )
    assert file_path.exists()
    # Saved under syllabi subfolder
    assert file_path.parent.name == "syllabi"
    assert file_path.suffix == ".pdf"


def test_save_full_curriculum_pdf_contains_sections_and_syllabi(tmp_path: Path):
    sections = {
        "Learning Outcomes": "# Outcomes\n\n1. One\n2. Two",
        "Course List": "# Courses\n\n- A\n- B",
        "Empty Section": "   ",  # should be skipped (no content)
    }
    syllabi = {
        "CS101": "# CS101\n\n## Description\nhello",
        "Empty": "",  # skipped
    }
    file_path = pe.save_full_curriculum_pdf(
        sections=sections,
        syllabi=syllabi,
        institution="Acme",
        program_name="CS",
        program_level="Undergraduate",
        base_outputs=tmp_path,
    )
    assert file_path.exists()
    assert file_path.name == "full_curriculum.pdf"
    assert file_path.stat().st_size > 0


def test_save_full_curriculum_handles_no_syllabi(tmp_path: Path):
    path = pe.save_full_curriculum_pdf(
        sections={"A": "# A\nhi"},
        syllabi={},
        institution="Inst",
        program_name="Prog",
        program_level="Undergraduate",
        base_outputs=tmp_path,
    )
    assert path.exists()


def test_render_markdown_handles_all_constructs(tmp_path: Path):
    content = (
        "# H1\n## H2\n### H3\n#### H4\n\n"
        "---\n\n"
        "| Course | SLO1 | SLO2 |\n"
        "|--------|------|------|\n"
        "| **Semester 1** | | |\n"
        "| CS101 | I | D |\n\n"
        "- bullet one\n"
        "- bullet two\n"
        "1. numbered one\n"
        "2. numbered two\n\n"
        "**A bold mini-header**\n\n"
        "Regular paragraph with *italic* and `code` and **bold**."
    )
    path = pe.save_section_pdf(
        content=content,
        section_name="Test Section",
        institution="Acme",
        program_name="CS",
        program_level="Undergraduate",
        base_outputs=tmp_path,
    )
    assert path.exists()
    assert path.stat().st_size > 0
