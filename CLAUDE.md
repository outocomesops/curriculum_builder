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

---

## Session Log — 2026-04-22

### Changes Made
- **`exporter/curriculum_exporter.py`** — new module with `build_curriculum_export()` and `save_curriculum_export()`; assembles a structured `curriculum_export.json` from all session state data (metadata, inputs, curriculum content) using schema version 1.0
- **JSON export wired into Tab 4 (Export)** — `app.py` now imports `curriculum_exporter`; two new controls added: an in-browser `Download curriculum_export.json` button and a `Save JSON to Output Folder` button that writes alongside the PDFs; `import json` added to `app.py` top-level imports
- **`curriculum_export_sample.json`** — complete, realistic sample file for a "Bachelor of Applied Software Engineering" at Lambton College; includes 40 ranked skills, CEAB accreditation data, institutional summary, reputation text, two deep research modules, full learning outcomes + 34-course list + competency map + two full syllabi (CS102, CS208)
- **`/bais` skill updated** — added Step 2 (Update README.md) with detailed instructions for creating or updating a project-facing README; step numbering updated throughout; checklist and session closure box updated to include README.md

### Decisions & Rationale
- JSON export uses `schema_version: "1.0"` field so downstream apps can handle format evolution gracefully
- `build_curriculum_export()` is a pure function (takes explicit args, no session state dependency) — makes it independently testable and usable outside Streamlit
- Download button (`st.download_button`) assembles JSON in-memory without disk I/O; the separate "Save to Folder" button writes to the same output folder hierarchy as the PDFs — two modes to suit different workflows
- Sample file uses Lambton College as the fictional institution (consistent with project test data conventions from prior sessions)
- `courses_detected` array in the export is parsed from the course list markdown using the existing regex pattern already present in `app.py` Tab 3 — no duplication of logic

### Known Issues / TODOs
- JSON export is not yet auto-triggered when a full curriculum is built — it requires a manual button click in Tab 4; could be auto-saved at the end of each generation step
- `curriculum_exporter.py` has no dedicated unit tests yet (the module is pure Python with no Streamlit dependency, so tests would be straightforward to add)
- Deep research results are still not cached to disk — `utils/deep_research_cache.py` remains a TODO from prior session
- No per-module re-run button in Tab 5 (carried forward from previous session)

### Next Session Starting Point
- Add unit tests for `exporter/curriculum_exporter.py` (pure function, easy to test with mock DataFrames)
- Consider auto-saving `curriculum_export.json` at end of each generation step (not just on manual Export tab click)
- Test the full export round-trip: generate curriculum → download JSON → load in the downstream app being built
- Review `utils/deep_research_cache.py` implementation to cache deep research results between sessions

---

## Session Log — 2026-04-24

### Changes Made
- **Deep Research tab merged into Tab 2** — Tab 5 (Deep Research) removed entirely; its full UI (module checkboxes, config, run button, results, context preview) embedded inside Tab 2, now renamed "Context & Research"; `with tab_research:` orphaned block deleted from `app.py`; app now has 4 tabs
- **NLM native web research replaces DuckDuckGo** — `loaders/deep_research_loader.py` and `loaders/reputation_loader_nlm.py` were returning zero URLs via DuckDuckGo; replaced broken DDG pre-search with `nlm research start --mode deep --auto-import` so NLM discovers and imports its own real web sources (~40 for deep, ~10 for fast) before the notebook is queried
- **`deep_research_loader.py` rewritten** — removed `_DDG_MAX_PER_QUERY`, `_search_urls_for_module()`, `_add_url_sources_best_effort()`; added `_run_nlm_research()` helper; each MODULE_REGISTRY entry now has `research_query_template` (concise web-search query) instead of `search_query_templates`; `run_research_module()` parameters changed: `source_wait_timeout` → `research_timeout` (default 420 s), added `research_mode` (default "deep")
- **`reputation_loader_nlm.py` rewritten** — removed `_search_reputation_urls()`; added `_run_nlm_research()`; `fetch_reputation_via_notebooklm()` now calls NLM research before querying; params updated to `research_timeout` and `research_mode`
- **App.py UI updates** — "Source wait (s)" replaced with Research mode dropdown (deep/fast) + Research timeout field (default 420 s); `run_research_module()` calls updated to pass `research_timeout` and `research_mode`; reputation NLM call updated to drop `source_wait_timeout`

### Decisions & Rationale
- Replaced DuckDuckGo with NLM native research (`nlm research start --auto-import`) — root cause was that the DDG library was returning zero results; NLM's built-in research is more reliable, requires no external API, and discovers higher-quality academic/institutional sources
- `--auto-import` flag used over the 3-step start→status→import cycle — it blocks the subprocess until research completes and sources are ingested, simpler and removes polling logic from Python
- `research_mode` defaults to "deep" (~5 min, ~40 sources) over "fast" (~30s, ~10 sources) — deep mode provides materially better source coverage for academic research; fast mode offered in UI for quicker iteration
- Kept extra_urls support as a best-effort bonus step after NLM research — allows manual supplementation without depending on it
- `research_timeout` default set to 420 s (7 min) to safely cover NLM deep mode duration + source import overhead

### Known Issues / TODOs
- Deep research results are still not cached to disk — `utils/deep_research_cache.py` remains a TODO
- No per-module re-run button; users must deselect and re-run the full set
- `curriculum_exporter.py` still has no unit tests
- JSON export not auto-triggered at end of generation pipeline
- Non-Latin-1 scripts still require TTF font addition in `pdf_exporter.py`

### Next Session Starting Point
- Run the full end-to-end pipeline: Tab 1 → load data → Tab 2 → run one deep research module (fast mode for speed) → Tab 3 → generate learning outcomes; verify deep research context appears in the prompt
- Add unit tests for `exporter/curriculum_exporter.py`
- Implement `utils/deep_research_cache.py` to persist deep research results between browser sessions

---

## Session Log — 2026-04-26

### Changes Made
- **New Tab 3 — Outcomes & Bloom** — embedded full Bloom's Taxonomy analysis pipeline as a new tab between "Context & Research" and "Generate"; app now has 5 tabs: Sources & Setup → Context & Research → Outcomes & Bloom → Generate → Export
- **`analyzers/` package** — ported and adapted four files from `pedagogy_context`: `verb_extractor.py`, `bloom_classifier.py`, `outcome_analyzer.py`, `coverage_analyzer.py`; removed `pedagogy_context` config imports, inlined OLLAMA constants
- **`data/bloom_verbs.json`, `data/weak_verbs.json`** — copied verb banks from `pedagogy_context`
- **`loaders/bloom_loader.py`** — ported with data path relative to `data/` directory; added `load_bloom_taxonomy()` convenience function returning `(verb_index, weak_lookup, bloom_data)` in one call
- **`loaders/bloom_outcome_extractor.py`** — new file (no equivalent in `pedagogy_context`); parses learning outcomes markdown directly from `session_state["learning_outcomes"]` using `_parse_peos()` and `_parse_slos()` logic; replaces `curriculum_loader.py` which read from a JSON file
- **`generator/outcome_improver.py`** — ported; config imports replaced with inlined `_OLLAMA_TEMPERATURE_GENERATION = 0.4`; streams Ollama-generated outcome rewrites
- **`generator/bloom_prompt_builder.py`** — ported `build_improvement_prompt()` from `pedagogy_context`; builds Bloom-aligned rewrite prompt with institution/program context
- **`exporter/bloom_exporter.py`** — ported `build_pedagogy_block()` and `merge_with_curriculum()`; removed all file I/O (save handled by curriculum_exporter)
- **`config.py`** — added `BLOOM_LEVEL_ORDER`, `BLOOM_LEVEL_COLORS`, `OUTCOME_TYPE_LABELS`, `BLOOM_VERBS_FILE`, `WEAK_VERBS_FILE`
- **`exporter/curriculum_exporter.py`** — added optional `analysis_results` and `coverage` params; sets `schema_version="2.0"` and appends `pedagogy` block when Bloom analysis has been run
- **`app.py`** — major refactor: 5-tab layout; new Tab 3 (Step 1: generate outcomes, Step 2: Bloom analysis with KPI row + bar chart + filterable table, Step 3: refine flagged outcomes with AI rewrite + approve flow); Tab 4 (Generate) now starts at Course List with guard requiring outcomes from Tab 3; Tab 5 Export passes analysis_results/coverage to exporter; Bloom session state keys added to `_DEFAULTS`

### Decisions & Rationale
- Bloom tab placed at position 3 (before Generate) so all research inputs are present when outcomes are written, and Bloom alignment happens immediately after — before courses and syllabi are generated from those outcomes
- `bloom_outcome_extractor.py` parses markdown directly (no JSON roundtrip) — simpler, always in sync with the actual generated text; reuses `_parse_peos` and `_parse_slos` logic from `pedagogy_context/loaders/curriculum_loader.py` which already handles the exact markdown format that `curriculum_gen.generate_learning_outcomes()` produces
- `bloom_exporter.py` has no file I/O — the curriculum_exporter owns all disk writes; single responsibility, independently testable
- `curriculum_exporter.py` schema auto-upgrades to "2.0" only when Bloom analysis is present — backwards compatible, downstream apps can check `schema_version` to know whether to expect the `pedagogy` block
- Ollama constants inlined in analyzer files (`OLLAMA_TEMPERATURE_ANALYSIS = 0.1`) rather than pulled from config — avoids config bloat for values that are Bloom-specific and unlikely to need user tuning
- Approval flow uses `str.replace(original_text, improved_text, 1)` — safe because each outcome sentence is unique within the markdown; simpler than line-by-line diffing
- Tab 4 guard uses `st.stop()` on empty learning_outcomes — prevents users from attempting to generate course lists without outcomes, which would produce incoherent output

### Known Issues / TODOs
- Deep research results are still not cached to disk — `utils/deep_research_cache.py` remains a TODO
- No per-module re-run button in Tab 2 (Deep Research)
- `curriculum_exporter.py` and new Bloom modules have no unit tests yet
- JSON export not auto-triggered at end of generation pipeline
- Non-Latin-1 scripts still require TTF font addition in `pdf_exporter.py`
- `pedagogy_context` app has not yet been simplified (remove Bloom tabs, keep only Quality Committee) — that work is deferred
- Tab 3 Bloom analysis chart requires `altair` — already in requirements.txt via Streamlit, but worth verifying in fresh envs

### Next Session Starting Point
- Test Tab 3 end-to-end: Tab 1 → load skills + agencies → Tab 2 → Tab 3 → generate outcomes → Run Bloom Analysis → confirm chart renders, table populates, approve one refinement → Tab 4 → generate course list (confirm it receives refined outcomes) → Tab 5 → download JSON → confirm `schema_version: "2.0"` and `pedagogy` block present
- Simplify `pedagogy_context` app: remove Tabs 1–4 (Load, Bloom, Improve, Export); add Load tab that reads `curriculum_export_pedagogy.json` schema v2.0 and reconstructs `analysis_results`/`coverage` from the `pedagogy` block; keep Quality Committee tabs unchanged
- Add unit tests for `loaders/bloom_outcome_extractor.py`, `analyzers/coverage_analyzer.py`, `exporter/bloom_exporter.py`

---

## Session Log — 2026-05-03

### Changes Made
- **Reputation section moved from Tab 1 → Tab 2** — removed entire "Institutional Reputation (Public Perception)" expander (NotebookLM button, DuckDuckGo fallback, manual paste) from Tab 1; reputation is now researched exclusively through the unified Deep Research engine in Tab 2
- **6-module deep research** — added `institutional_reputation` as module 0 in `MODULE_REGISTRY` (was 5 modules, now 6); when the reputation module succeeds, its answer is stored in `st.session_state["reputation_summary"]` so it flows into all downstream generation prompts unchanged
- **Multi-pass fast research replaces deep/fast toggle** — removed research mode dropdown and research timeout input from Tab 2 UI; each module now always runs 3 targeted fast-research passes (~10 sources each, ~30 total per module) via `_run_one_pass` / `_run_all_passes` helpers in `deep_research_loader.py`
- **`loaders/nlm_client.py`** (new file) — extracted shared `NotebookLMClient` factory; `check_auth()` checks token age (warns if >7 days); `get_nlm_client()` loads cookies + metadata, creates client, and patches the underlying `httpx.Client` default timeout from 30 s → 120 s to prevent `get_notebook()` read timeouts on notebooks with many sources
- **NLM timeout hardening** — `poll_research` calls in `_run_one_pass` wrapped in try/except; transient network timeouts are logged as warnings and polling continues; `add_text_source(wait=True)` also wrapped gracefully
- **Bloom outcome extractor fixed for Continuous Education** — `bloom_outcome_extractor.py` only knew `# Program Educational Objectives` and `# Student Learning Outcomes`; CE programs generate `# Learning Objectives` which produced 0 matches; extractor now handles 6 heading variants (`Learning Objectives`, `Learning Outcomes`, `Program Outcomes`, `Course Outcomes`, `Competencies`) plus a fallback that collects all numbered list items with 5+ words when no recognised heading is found
- **Import cleanup** — removed unused `from loaders.reputation_loader_nlm import fetch_reputation_via_notebooklm`, `from loaders.reputation_loader import fetch_reputation_snippets`, and `summarize_reputation` from `app.py` top-level imports
- **Encoding fix** — corrected `U+2026` (`…`) replacement character corruption in `deep_research_loader.py` that caused a `SyntaxError` at startup

### Decisions & Rationale
- Reputation moved to Tab 2 (not deleted) because it belongs with all other NLM research; running it as a named module means its findings appear in the Research Results section alongside the other five modules, giving the user a single place to review all intelligence before generation
- Multi-pass fast research always used (no user-selectable deep mode) because deep mode returns `code 8` (quota/feature restriction) on the Workspace Google account in use; 3 × fast = ~30 sources per module, comparable to deep mode's ~40
- httpx client timeout patched in `get_nlm_client()` rather than in individual call sites — one change covers all `_call_rpc` invocations that lack explicit timeouts (`get_notebook`, `poll_research`, `create_notebook`, etc.) without requiring library modifications
- Bloom extractor uses a priority list of heading patterns (most specific first, fallback last) with deduplication — ensures outcomes are not double-counted if the LLM happens to use both `# Learning Outcomes` and `# Student Learning Outcomes` headings

### Known Issues / TODOs
- Deep research results are still not cached to disk — `utils/deep_research_cache.py` remains a TODO
- No per-module re-run button in Tab 2 (Deep Research); users must deselect and rerun the full set
- `curriculum_exporter.py` and new Bloom modules have no unit tests yet
- JSON export not auto-triggered at end of generation pipeline
- Non-Latin-1 scripts still require TTF font addition in `pdf_exporter.py`
- `reputation_loader_nlm.py` is imported by nothing in `app.py` now but kept for potential programmatic use

### Next Session Starting Point
- Run full end-to-end with a CE program: Tab 1 → load skills + agencies → Tab 2 → run reputation + 1-2 research modules → Tab 3 → generate outcomes → confirm Bloom analysis finds all outcomes → Tab 4 → generate course list → Tab 5 → export JSON
- Implement `utils/deep_research_cache.py` to persist deep research results between browser sessions (same pattern as `institutional_cache.py`)
- Add unit tests for `loaders/bloom_outcome_extractor.py` — especially the CE heading variant and fallback path
- Consider auto-saving `curriculum_export.json` at the end of each generation step (not only on manual Export tab click)
