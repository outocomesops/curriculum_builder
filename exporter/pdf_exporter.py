"""
PDF exporter — converts LLM-generated markdown text to formatted PDF files
and saves them under outputs/{institution}/{YYYY-MM}/{program_name}/.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

# ---------------------------------------------------------------------------
# Unicode font discovery
# Tries common system TTF paths; falls back to Helvetica (Latin-1).
# ---------------------------------------------------------------------------
_UNICODE_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/ArialUni.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

_UNICODE_FONT_PATH: str | None = None
for _candidate in _UNICODE_FONT_CANDIDATES:
    if Path(_candidate).exists():
        _UNICODE_FONT_PATH = _candidate
        break

_USE_UNICODE = _UNICODE_FONT_PATH is not None
_BODY_FONT = "UniFont" if _USE_UNICODE else "Helvetica"


# ---------------------------------------------------------------------------
# Unicode sanitiser — only used when no Unicode TTF is available.
# ---------------------------------------------------------------------------
_UNICODE_MAP = str.maketrans({
    "\u2014": "--", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2022": "-",
    "\u00b7": "-", "\u2192": "->", "\u2190": "<-", "\u00b0": "deg",
    "\u00d7": "x",  "\u2212": "-",
})


def _s(text: str) -> str:
    if _USE_UNICODE:
        return text
    text = text.translate(_UNICODE_MAP)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ---------------------------------------------------------------------------
# PDF class
# ---------------------------------------------------------------------------
class _CurriculumPDF(FPDF):
    def __init__(self, doc_title: str, institution: str, program: str):
        super().__init__()
        self._doc_title = doc_title
        self._institution = institution
        self._program = program
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(15, 15, 15)
        if _USE_UNICODE:
            self.add_font(_BODY_FONT, style="", fname=_UNICODE_FONT_PATH)
            self.add_font(_BODY_FONT, style="B", fname=_UNICODE_FONT_PATH)

    def _font(self, style: str = "", size: int = 10) -> None:
        self.set_font(_BODY_FONT, style, size)

    def header(self):
        self._font("B", 8)
        self.set_text_color(120, 120, 120)
        header_text = _s(f"{self._institution}  |  {self._program}  |  {self._doc_title}")
        self.cell(0, 7, header_text, align="L")
        self.set_draw_color(200, 200, 200)
        self.line(15, self.get_y() + 1, 195, self.get_y() + 1)
        self.ln(6)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-13)
        self._font("", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)


# ---------------------------------------------------------------------------
# Markdown → PDF renderer
# ---------------------------------------------------------------------------
def _col_widths(n_cols: int, cells: list[str]) -> list[float]:
    """
    Compute column widths for a markdown table row.
    For wide tables (many SLO columns in competency maps) the first column
    gets extra space; the rest share the remainder equally.
    """
    total = 175.0
    if n_cols <= 4:
        w = total / n_cols
        return [w] * n_cols
    # Competency-map style: generous first column, narrow SLO columns
    first_w = min(65.0, total * 0.40)
    rest_w = (total - first_w) / (n_cols - 1)
    # If rest_w is too narrow, compress first column further
    min_col = 8.0
    if rest_w < min_col:
        rest_w = min_col
        first_w = total - rest_w * (n_cols - 1)
    return [first_w] + [rest_w] * (n_cols - 1)


def _render_markdown(pdf: _CurriculumPDF, text: str) -> None:
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = _s(raw.rstrip())

        # H1
        if line.startswith("# "):
            pdf._font("B", 17)
            pdf.set_fill_color(26, 58, 140)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 11, line[2:].strip(), fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(4)

        # H2
        elif line.startswith("## "):
            pdf.ln(3)
            pdf._font("B", 13)
            pdf.set_text_color(26, 58, 140)
            pdf.cell(0, 9, line[3:].strip(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(180, 200, 240)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)

        # H3
        elif line.startswith("### "):
            pdf.ln(2)
            pdf._font("B", 11)
            pdf.set_text_color(50, 80, 160)
            pdf.cell(0, 8, line[4:].strip(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)

        # H4
        elif line.startswith("#### "):
            pdf._font("B", 10)
            pdf.cell(0, 7, line[5:].strip(), new_x="LMARGIN", new_y="NEXT")

        # Horizontal rule
        elif re.match(r"^[-*_]{3,}$", line.strip()):
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(2)

        # Table row (pipe-delimited)
        elif "|" in line and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # skip separator rows like |---|---|
            if all(re.match(r"^[-: ]+$", c) for c in cells):
                i += 1
                continue
            n = max(len(cells), 1)
            widths = _col_widths(n, cells)
            is_header = (i == 0 or not lines[i - 1].strip().startswith("|"))
            # Also treat rows that contain **bold** as section separators (semester headers)
            is_section_row = all(
                re.match(r"^\*\*.*\*\*$", c.strip()) or c.strip() == "" for c in cells
            ) and any(c.strip() for c in cells)

            if is_section_row:
                pdf._font("B", 8)
                pdf.set_fill_color(210, 220, 245)
                for j, (c, w) in enumerate(zip(cells, widths)):
                    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", c)
                    pdf.cell(w, 6, _s(clean[:60]), border=1, fill=True)
                pdf.ln()
            elif is_header:
                pdf._font("B", 8)
                pdf.set_fill_color(230, 235, 250)
                for j, (c, w) in enumerate(zip(cells, widths)):
                    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", c)
                    trunc_len = 60 if j == 0 else 8
                    pdf.cell(w, 6, _s(clean[:trunc_len]), border=1, fill=True)
                pdf.ln()
            else:
                pdf._font("", 8)
                for j, (c, w) in enumerate(zip(cells, widths)):
                    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", c)
                    clean = re.sub(r"\*(.+?)\*", r"\1", clean)
                    trunc_len = 60 if j == 0 else 8
                    pdf.cell(w, 6, _s(clean[:trunc_len]), border=1)
                pdf.ln()

        # Bullet (- or *)
        elif re.match(r"^(\s{0,3})[-*] ", line):
            indent = len(line) - len(line.lstrip())
            bullet_text = re.sub(r"^(\s*[-*] )", "", line)
            bullet_text = re.sub(r"\*\*(.+?)\*\*", r"\1", bullet_text)
            bullet_text = re.sub(r"\*(.+?)\*", r"\1", bullet_text)
            pdf._font("", 10)
            x_offset = 15 + indent * 3
            pdf.set_x(x_offset)
            pdf.cell(5, 6, chr(149) if indent == 0 else "-")
            pdf.multi_cell(0, 6, bullet_text.strip())

        # Numbered list
        elif re.match(r"^\d+\. ", line):
            text_body = re.sub(r"^\d+\. ", "", line)
            text_body = re.sub(r"\*\*(.+?)\*\*", r"\1", text_body)
            num = re.match(r"^(\d+)\.", line).group(1)
            pdf._font("", 10)
            pdf.set_x(15)
            pdf.cell(7, 6, f"{num}.")
            pdf.multi_cell(0, 6, text_body.strip())

        # Blank line
        elif not line.strip():
            pdf.ln(3)

        # Bold-only line (acts as mini-header)
        elif re.match(r"^\*\*.+\*\*$", line.strip()):
            inner = re.sub(r"\*\*(.+?)\*\*", r"\1", line.strip())
            pdf._font("B", 10)
            pdf.multi_cell(0, 6, inner)

        # Regular paragraph
        else:
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            clean = re.sub(r"\*(.+?)\*", r"\1", clean)
            clean = re.sub(r"`(.+?)`", r"\1", clean)
            pdf._font("", 10)
            pdf.multi_cell(0, 6, clean)

        i += 1


# ---------------------------------------------------------------------------
# Title page
# ---------------------------------------------------------------------------
def _title_page(pdf: _CurriculumPDF, institution: str, program: str, program_level: str, date_str: str) -> None:
    pdf.add_page()
    pdf.ln(30)
    pdf._font("B", 24)
    pdf.set_text_color(26, 58, 140)
    pdf.multi_cell(0, 14, _s(program), align="C")
    pdf.ln(6)
    pdf._font("", 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, _s(program_level), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_draw_color(26, 58, 140)
    pdf.set_line_width(0.8)
    pdf.line(40, pdf.get_y(), 170, pdf.get_y())
    pdf.ln(10)
    pdf._font("B", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, _s(institution), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf._font("", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, f"Generated: {date_str}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_line_width(0.2)
    pdf.set_text_color(0, 0, 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _output_dir(base_outputs: Path, institution: str, program_name: str) -> Path:
    year_month = datetime.now().strftime("%Y-%m")
    safe_inst = re.sub(r"[^\w\s-]", "", institution).strip().replace(" ", "_")
    safe_prog = re.sub(r"[^\w\s-]", "", program_name).strip().replace(" ", "_")
    path = base_outputs / safe_inst / year_month / safe_prog
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_section_pdf(
    content: str,
    section_name: str,
    institution: str,
    program_name: str,
    program_level: str,
    base_outputs: Path,
) -> Path:
    out_dir = _output_dir(base_outputs, institution, program_name)
    safe_section = re.sub(r"[^\w\s-]", "", section_name).strip().replace(" ", "_")
    file_path = out_dir / f"{safe_section}.pdf"

    pdf = _CurriculumPDF(section_name, institution, program_name)
    pdf.add_page()
    _render_markdown(pdf, content)
    pdf.output(str(file_path))
    return file_path


def save_full_curriculum_pdf(
    sections: dict[str, str],
    syllabi: dict[str, str],
    institution: str,
    program_name: str,
    program_level: str,
    base_outputs: Path,
) -> Path:
    out_dir = _output_dir(base_outputs, institution, program_name)
    file_path = out_dir / "full_curriculum.pdf"

    date_str = datetime.now().strftime("%B %Y")
    pdf = _CurriculumPDF("Full Curriculum", institution, program_name)

    _title_page(pdf, institution, program_name, program_level, date_str)

    for section_title, content in sections.items():
        if content.strip():
            pdf.add_page()
            _render_markdown(pdf, content)

    if syllabi:
        pdf.add_page()
        pdf._font("B", 20)
        pdf.set_text_color(26, 58, 140)
        pdf.cell(0, 14, "Course Syllabi", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        for course_code, syllabus in syllabi.items():
            if syllabus.strip():
                pdf.add_page()
                _render_markdown(pdf, syllabus)

    pdf.output(str(file_path))
    return file_path


def save_syllabus_pdf(
    course_code: str,
    content: str,
    institution: str,
    program_name: str,
    program_level: str,
    base_outputs: Path,
) -> Path:
    out_dir = _output_dir(base_outputs, institution, program_name) / "syllabi"
    out_dir.mkdir(exist_ok=True)
    safe = re.sub(r"[^\w\s-]", "", course_code).strip().replace(" ", "_")
    file_path = out_dir / f"{safe}.pdf"

    pdf = _CurriculumPDF(course_code, institution, program_name)
    pdf.add_page()
    _render_markdown(pdf, content)
    pdf.output(str(file_path))
    return file_path
