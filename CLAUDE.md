# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

## Architecture

This app synthesises three input streams into a generated academic curriculum:

1. **Job market demand** — skill frequencies from `job_market_search/jobs.db` (SQLite) or a CSV export
2. **Accreditation quality standards** — structured `quality_definition.json` files from `quality_assurance/sources/`
3. **Institutional documentation** — arbitrary PDFs/DOCX/TXT files in a user-specified folder

### Module layout

```
app.py                      Streamlit entrypoint — 4 tabs
config.py                   Constants: Ollama URL, output path, languages, program levels

loaders/
  job_loader.py             Reads jobs.db (tables: jobs, skills) and CSV exports
  quality_loader.py         Reads catalog.json + quality_definition.json from quality_assurance/sources/
  doc_loader.py             Extracts text from PDF/DOCX/TXT files using pdfplumber / python-docx

generator/
  doc_summarizer.py         LLM pass that extracts institutional values/policies from raw doc text
  prompt_builder.py         Assembles skills context, accreditation context, institutional context
  curriculum_gen.py         All Ollama streaming generation calls (outcomes, course list, competency map, syllabi)

exporter/
  pdf_exporter.py           Converts LLM markdown output to PDF via fpdf2; saves to outputs/
```

### App tabs

| Tab | Purpose |
|-----|---------|
| Sources & Setup | Configure paths, load data, set institution/program metadata |
| Context Preview | Review skills table, agency requirements, and run doc summarisation |
| Generate | Sequential pipeline: outcomes → course list → competency map → individual syllabi |
| Export | Save full curriculum or individual sections as PDF; Markdown download |

### Data flow

```
jobs.db / CSV ──► job_loader ──► skills_df (DataFrame)
                                     │
catalog.json + quality_definition ──► quality_loader ──► agencies list
                                                              │
institutional docs ──► doc_loader ──► doc_summarizer ──► summaries
                                                              │
                            prompt_builder ◄─────────────────┘
                                  │
                          curriculum_gen (Ollama streaming)
                                  │
                          session_state storage
                                  │
                          pdf_exporter → outputs/{institution}/{YYYY-MM}/{program}/
```

### Output folder structure

```
outputs/
  {Institution_Name}/
    {YYYY-MM}/
      {Program_Name}/
        full_curriculum.pdf
        01_Learning_Outcomes.pdf
        02_Course_List.pdf
        03_Competency_Map.pdf
        syllabi/
          CS101.pdf
          CS102.pdf
          ...
```

### Key dependencies on upstream projects

- **job_market_search**: `jobs.db` schema — `jobs(job_id, query, title, employer, description, job_city, job_country, posted_at)` and `skills(job_id, skill_name, skill_type, match_score, source)`
- **quality_assurance**: `sources/catalog.json` with `agencies[].metadata_path` and per-agency `quality_definition.json` with fields `definition_of_quality`, `core_quality_dimensions`, `curriculum_requirements`, `what_agencies_measure`, `best_practices_for_programs`

### Ollama integration

- Models are discovered via `GET /api/tags` at startup; if unreachable the user enters a model name manually
- All generation uses `POST /api/chat` with `stream: true`; chunks are yielded to Streamlit's `st.markdown()` for live output
- Doc summarisation uses `stream: false` (single response, not shown live)
- Default context window: `num_ctx: 8192`

### PDF rendering

`exporter/pdf_exporter.py` uses `fpdf2` with Helvetica (Latin-1). The `_s()` function sanitises common Unicode punctuation (em-dashes, curly quotes, bullets) before rendering. For non-Latin-1 scripts a TTF font would need to be added via `pdf.add_font()`.

---

## Session Log — 2026-04-18

### Changes Made
- Built complete Streamlit app (`app.py`) with 4 tabs: Sources & Setup, Context Preview, Generate, Export
- Implemented all loaders: `job_loader.py`, `quality_loader.py`, `doc_loader.py`
- Implemented generator modules: `doc_summarizer.py`, `prompt_builder.py`, `curriculum_gen.py`
- Implemented `pdf_exporter.py` with Unicode sanitisation via `_s()`
- Added `config.py` with Ollama URL, output path, language, and program level constants
- Set up `requirements.txt` with all dependencies
- Wrote `CLAUDE.md` architecture documentation

### Decisions & Rationale
- Used Ollama `POST /api/chat` with `stream: true` for all generation steps to give live feedback in Streamlit
- Doc summarisation uses `stream: false` since it runs in background before generation
- PDF output uses fpdf2 with Helvetica (Latin-1 safe); Unicode sanitisation handles em-dashes, curly quotes, bullets
- Sequential pipeline stored in `st.session_state` so partial results survive reruns

### Known Issues / TODOs
- Non-Latin-1 scripts (e.g., Arabic, Chinese) require adding a TTF font via `pdf.add_font()`
- No error handling if Ollama goes offline mid-stream
- Competency map is rendered as plain text; a table renderer would improve readability

### Next Session Starting Point
- Test end-to-end with a real `jobs.db` + a quality_definition agency + a sample PDF
- Focus on `app.py` tab 3 (Generate) and `generator/curriculum_gen.py` for any prompt tuning
- Consider adding a progress bar across the 4 generation steps
