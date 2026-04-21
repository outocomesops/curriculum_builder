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

---

## Session Log — 2026-04-19

### Changes Made
- **NotebookLM reputation research** — `loaders/reputation_loader_nlm.py` uses `nlm` CLI (subprocess) to create a notebook, add a text seed + optional URLs, query for reputation, and return a structured summary; moved to Tab 1 (Sources & Setup)
- **PDF scraper/downloader** — `loaders/pdf_downloader.py` scrapes PDF links from any webpage and downloads them to a local folder; integrated into Tab 1 institutional docs section with preview + multiselect
- **Fixed data paths** — `config.py` now exposes `JOB_MARKET_DB`, `QUALITY_SOURCES_DIR`, `INSTITUTIONAL_DOCS_DIR`, and `INSTITUTIONS_DIR` as fixed sibling-project paths; Tab 1 no longer asks for file paths
- **Per-tab LLM model selectors** — model dropdown moved out of sidebar into Tab 2 (`model_ctx`) and Tab 3 (`model_gen`) independently; sidebar only shows available model count
- **Institutional summary cache** — `utils/institutional_cache.py` fingerprints the doc set and saves the consolidated summary to `outcomesops_institutions/{institution}/institutional_summary.json`; Tab 2 detects a valid cache and offers one-click load, skipping re-summarisation
- **Restored doc_summarizer.py** — file was corrupted mid-session (`def 0(` syntax error + truncation); restored with all four functions: `summarize_doc`, `batch_summarize`, `consolidate_summaries`, `summarize_reputation`
- **NotebookLM auth** — ran `nlm login` to authenticate; fixed empty-notebook query error by always adding a text seed source before querying

### Decisions & Rationale
- `nlm` CLI called via subprocess rather than importing internal library — the package has no public Python API; subprocess is stable and matches how the MCP server uses it
- Text seed source added unconditionally before NLM query — NotebookLM requires ≥1 source; Reddit auto-URLs were blocked by Reddit and dropped
- Cache fingerprint uses `(filename, char_count)` pairs hashed with MD5 — lightweight, no file re-read required; invalidates naturally when files are added/replaced
- Reputation section moved to Tab 1 so all data-gathering happens before context review, matching the intended workflow
- Per-tab model selectors allow using a faster/cheaper model for doc summarisation and a more capable one for curriculum generation

### Known Issues / TODOs
- DuckDuckGo reputation option uses Ollama (local LLM); requires Ollama running — NotebookLM option has no such dependency
- `nlm login` must be re-run if auth cookies expire (session-based); no auto-refresh in the app
- Non-Latin-1 scripts still require TTF font addition in `pdf_exporter.py`
- Competency map rendered as plain text — a table renderer would improve readability

### Next Session Starting Point
- Test full pipeline end-to-end: load jobs.db → quality standards → download PDFs from URL → reputation research → generate curriculum → export PDF
- Focus on `generator/curriculum_gen.py` prompt tuning once real data is flowing
- Consider caching the reputation summary similarly to institutional summary (same pattern in `utils/`)
- `outcomesops_institutions/` folder structure: verify cache files are written correctly on first consolidated run

---

## Session Log — 2026-04-20

### Changes Made
- **Program Specifications loader** — `loaders/program_specs_loader.py` extracts content from any file type in a folder: TXT/MD/CSV (direct read), PDF (pdfplumber), DOCX (python-docx including tables), XLSX/XLS (openpyxl, all sheets), PPTX/PPT (python-pptx, all slide text), images via Ollama vision API (base64), video/audio via openai-whisper (if installed)
- **Program Specifications UI** — new section in Tab 1 (Sources & Setup) between quality standards and institutional docs: folder path input, vision model selector (picks from loaded Ollama models), progress bar during loading, file-by-file results with type icons
- **`build_program_specs_context()`** — added to `generator/prompt_builder.py`; formats extracted specs into a prompt-injectable string (truncates to 12,000 chars)
- **Deep Research tab** — new Tab 5 in `app.py` backed by `loaders/deep_research_loader.py`
- **`MODULE_REGISTRY`** — 5 research modules: Legal Framework (⚖️), Competitive Landscape (🏆), Student Market & Employer Perception (🎓), Institutional History & Identity (🏛️), Strategic Analysis / Game Theory (♟️)
- **`run_research_module()`** — one NLM notebook per module (created → seeded → queried → deleted); never raises; returns `{status, answer, error, notebook_id, sources_added}`
- **`build_deep_research_context()`** — formats successful module results into `=== DEEP RESEARCH INTELLIGENCE ===` prompt block
- **Tab 5 UI** — module checkboxes (2-column grid with tooltips), extra seed URLs textarea, source/query timeouts, cleanup toggle, per-module `st.status()` live progress, results with metric row + expandable answers, context preview
- **Generator integration** — `deep_research_context` injected into `generate_learning_outcomes` and `generate_course_list` prompts; visible in Tab 2 context preview
- **Added to `requirements.txt`**: `openpyxl>=3.1`, `python-pptx>=0.6`
- All 125 existing tests pass

### Decisions & Rationale
- One NLM notebook per research module (not one shared notebook): module isolation prevents context bleed between topics (e.g. legal answers drifting into competitive analysis), and one module failure cannot kill others
- `run_research_module` never raises by contract — the calling loop in Tab 5 always continues to the next module; errors surface in the UI expander for that module only
- Program specs loader uses Ollama vision API for images (reuses existing Ollama integration) rather than adding a tesseract dependency; gracefully skips if no vision model is selected
- Video transcription via whisper is optional (not in requirements.txt) — requires ffmpeg; app degrades gracefully with a clear error message
- `MODULE_REGISTRY` is the single extensibility point: adding a 6th research module requires only appending one dict to the list; all UI and context assembly code renders from it dynamically

### Known Issues / TODOs
- `st.status()` requires Streamlit ≥ 1.28; already met (project uses ≥ 1.35) — no concern
- Video/audio transcription (whisper) not installed by default; users must `pip install openai-whisper` + have `ffmpeg` on PATH
- Deep research results are not cached to disk (unlike institutional summary); closing the browser loses them — consider adding a JSON cache in `outcomesops_institutions/{institution}/deep_research_cache.json`
- No per-module re-run button yet; users re-run by unchecking succeeded modules and clicking Run again
- Competency map and syllabi generation do not receive deep research context (intentional — they are downstream derivations; add if needed)

### Next Session Starting Point
- Test full pipeline end-to-end: Tab 1 → load job skills + quality standards + program specs folder → Tab 5 → run 1–2 research modules → Tab 3 → generate learning outcomes and verify deep research context appears in the prompt
- Focus on `loaders/deep_research_loader.py` query tuning once real institution data flows through NLM
- Consider adding disk cache for deep research results (`utils/deep_research_cache.py`, same pattern as `utils/institutional_cache.py`)
- Consider per-module re-run button in Tab 5 results section
