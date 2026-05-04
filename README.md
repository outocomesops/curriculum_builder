# Curriculum Builder

An AI-powered Streamlit application that synthesises job market demand, accreditation standards, institutional documentation, and Bloom's Taxonomy alignment into a complete, publication-ready academic curriculum — using a locally-running Ollama LLM and NotebookLM for deep research.

---

## What It Does

Academic curriculum design is traditionally slow, anecdotal, and disconnected from real-world labour market signals. Curriculum Builder solves this by pulling three streams of evidence — what employers are actually hiring for, what accreditation bodies require, and what the institution already stands for — and feeding them into a large language model that writes the full curriculum document set in one guided pipeline run.

The app produces program-level learning outcomes, a sequenced course list, a competency mapping table, and individual course syllabi. Every generated document is grounded in real skill frequency data from job postings, structured quality standards from accreditation agencies, and the institution's own policies and reputation profile.

Once outcomes are generated, the built-in Bloom's Taxonomy analyser classifies every outcome by cognitive level, flags weak or unmeasurable verbs, shows a distribution chart, and offers AI-assisted rewriting of flagged items — all before the rest of the curriculum is built. The result is a pedagogically grounded, structured, exportable curriculum package: a full PDF for institutional use and a machine-readable `curriculum_export.json` (schema v2.0 includes a full `pedagogy` block) for downstream applications such as committee review tools, program comparison dashboards, or accreditation reporting systems.

---

## Key Features

- **Job market skill analysis** — loads skill frequency data from a SQLite database (`jobs.db`) or CSV export; ranks skills by job count and mention rate
- **Accreditation standards integration** — reads structured `quality_definition.json` files from a multi-agency quality assurance library; filters by program scope and jurisdiction
- **Institutional document summarisation** — extracts and consolidates content from PDF, DOCX, and TXT policy files using an Ollama LLM; caches the consolidated profile per institution
- **Program specifications loader** — ingests any stakeholder materials folder: Excel, Word, PDF, PowerPoint, images (via Ollama vision), video/audio (via Whisper), CSV, TXT
- **Six-module deep research engine** — Tab 2 runs six independent NotebookLM research modules: Institutional Reputation, Legal Framework, Competitive Landscape, Student Market & Employer Perception, Institutional History, Strategic Analysis; each module runs 3 targeted fast-research passes (~10 sources per pass, ~30 total) and queries NotebookLM for a structured answer; all six results are injected into generation prompts
- **Bloom's Taxonomy analysis** — classifies every learning outcome by cognitive level (remember → create), flags weak/unmeasurable verbs, displays a distribution bar chart, and offers AI-assisted rewriting of flagged outcomes before course generation begins
- **Three-step curriculum generation** — sequential LLM pipeline (Tab 4): course list → competency map → individual syllabi; outcomes are authored in Tab 3
- **PDF export** — saves full curriculum or individual sections as formatted PDFs in a dated folder hierarchy (`outputs/{Institution}/{YYYY-MM}/{Program}/`)
- **JSON export** — produces a structured `curriculum_export.json` with all inputs and generated content; downloadable from the browser or saved to the output folder
- **Institutional summary cache** — fingerprints the document set and saves consolidated summaries to disk; avoids re-summarisation when documents are unchanged

---

## Architecture Overview

The app follows a five-tab pipeline. Loaders ingest heterogeneous source data, the generator builds LLM context and streams curriculum text, the Bloom analyser classifies outcomes, and exporters write output to PDF and JSON.

```
jobs.db / CSV ──► job_loader ──────────────────────────────► skills_df
quality_definition.json ──► quality_loader ──────────────► agencies list
institutional PDFs ──► doc_loader ──► doc_summarizer ──► consolidated summary
program specs folder ──► program_specs_loader ──────────► specs text
reputation sources ──► reputation_loader_nlm ───────────► reputation summary
NotebookLM modules ──► deep_research_loader ────────────► research results
                                    │
                            prompt_builder (assembles context)          [Tab 2]
                                    │
                    curriculum_gen → generate_learning_outcomes          [Tab 3]
                                    │
              bloom_outcome_extractor → analyze_all_outcomes             [Tab 3]
              → analyze_coverage → improve_outcome (Bloom pipeline)
                                    │
                    curriculum_gen → course list, map, syllabi           [Tab 4]
                                    │
              ┌─────────────────────┼──────────────────────┐           [Tab 5]
              ▼                     ▼                       ▼
         pdf_exporter        curriculum_exporter      session_state
    (PDF files on disk)  (curriculum_export.json     (live UI display)
                          schema v1.0 or v2.0)
```

All Ollama calls use `POST /api/chat` with `stream: true`. Doc summarisation uses `stream: false`. Models are discovered at startup via `GET /api/tags`. Bloom keyword classification uses `bloom_verbs.json`; unresolved verbs fall back to Ollama LLM classification.

---

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) running locally (default: `http://localhost:11434`) with at least one model pulled (e.g. `ollama pull llama3`)
- Optional: `nlm` CLI authenticated (`nlm login`) for NotebookLM-based features
- Optional: `ffmpeg` + `openai-whisper` for video/audio transcription

### Installation

```bash
git clone <repo-url>
cd curriculum_builder
pip install -r requirements.txt
```

### Run

```bash
python -m streamlit run app.py
```

The app opens at `http://localhost:8501` (or the next available port).

---

## Usage

The app is divided into five tabs, intended to be used in order:

**Tab 1 — Sources & Setup**
Set the institution name, program name, and level. Load job market skills from `jobs.db`, quality standards from the accreditation library, program specification documents from a folder, and institutional policy PDFs.

**Tab 2 — Context & Research**
The central intelligence tab. Review loaded skills and agency requirements, summarise and consolidate institutional documents (with per-institution disk cache), and run all six NotebookLM deep research modules: Institutional Reputation, Legal Framework, Competitive Landscape, Student Market, Institutional History, Strategic Analysis. Each module runs 3 fast-research passes and queries NotebookLM for a structured answer. The reputation module result is also stored as the program's reputation profile for injection into generation prompts. The full assembled LLM context is visible for inspection.

**Tab 3 — Outcomes & Bloom**
Three-step sub-pipeline: (1) Generate learning outcomes from all gathered context — streams live. (2) Run Bloom's Taxonomy analysis — classifies every outcome by cognitive level, shows KPI metrics, a level distribution bar chart, and a filterable outcome table with flags. (3) Refine flagged outcomes — for each outcome with weak or unmeasurable verbs, generate an AI-written rewrite and approve it to replace the original in the learning outcomes text.

**Tab 4 — Generate**
Run the three remaining curriculum generation steps, each streaming live. Requires learning outcomes from Tab 3. Steps: (1) Course List, (2) Competency Map, (3) Individual Syllabi (select which courses to generate).

**Tab 5 — Export**
Save the full curriculum or individual sections as PDFs. Download the curriculum as Markdown or as `curriculum_export.json` (schema v2.0 with `pedagogy` block if Bloom analysis was run, v1.0 otherwise). Save the JSON to the output folder alongside the PDFs.

---

## Project Structure

```
curriculum_builder/
├── app.py                        Streamlit entrypoint — 5 tabs
├── config.py                     Constants: Ollama URL, output paths, languages, program levels
├── requirements.txt              Python dependencies
├── curriculum_export_sample.json Sample JSON export (Lambton College / Software Engineering)
│
├── loaders/
│   ├── job_loader.py             Reads jobs.db (SQLite) and CSV skill exports
│   ├── quality_loader.py         Reads catalog.json + quality_definition.json files
│   ├── doc_loader.py             Extracts text from PDF/DOCX/TXT institutional docs
│   ├── program_specs_loader.py   Multi-format loader: Excel, Word, PPTX, images, video, audio
│   ├── nlm_client.py             Shared NotebookLMClient factory; auth check; httpx timeout patch
│   ├── bloom_outcome_extractor.py Parses outcomes markdown → OutcomeRecord list (all heading variants)
│   ├── bloom_loader.py           Loads bloom_verbs.json + weak_verbs.json into lookup structures
│   ├── pdf_downloader.py         Scrapes and downloads PDFs from a given webpage URL
│   └── deep_research_loader.py   Six-module NotebookLM research engine (3 passes/module, ~30 sources)
│
├── generator/
│   ├── doc_summarizer.py         LLM summarisation of institutional documents
│   ├── prompt_builder.py         Assembles all context strings for LLM prompts
│   └── curriculum_gen.py         Ollama streaming generation: outcomes, courses, map, syllabi
│
├── exporter/
│   ├── pdf_exporter.py           Markdown → PDF via fpdf2; saves to outputs/ folder hierarchy
│   └── curriculum_exporter.py    Builds and saves structured curriculum_export.json
│
├── utils/
│   └── institutional_cache.py    Fingerprints doc set; caches consolidated summaries to disk
│
├── tests/                        pytest test suite (125+ tests)
└── outputs/                      Generated PDFs and JSON (git-ignored)
```

---

## Configuration

| Item | Default | Description |
|---|---|---|
| Ollama URL | `http://localhost:11434` | Configurable in the app sidebar |
| Output folder | `outputs/` (sibling of `app.py`) | Configurable in the app sidebar |
| Job market DB | `../job_market_search/jobs.db` | Sibling project path defined in `config.py` |
| Quality standards | `../quality_assurance/sources/` | Sibling project path defined in `config.py` |
| Institutional docs | `../outcomesops_institutions/` | Sibling project path defined in `config.py` |
| LLM context window | 8192 tokens | Set in `curriculum_gen.py` `_OPTIONS` |
| Ollama temperature | 0.45 | Set in `curriculum_gen.py` `_OPTIONS` |

The app expects Ollama to be running. If unreachable at startup, the model selector falls back to a free-text input.

---

## Output / Exports

### PDF Output

Saved to:
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
```

### JSON Export (`curriculum_export.json`)

Schema version `1.0`. Top-level structure:

```json
{
  "schema_version": "1.0",
  "generated_at": "<ISO 8601 timestamp>",
  "metadata": {
    "institution_name", "program_name", "program_level",
    "language", "course_hours", "year_month"
  },
  "inputs": {
    "skills": { "total_skills_in_db", "top_n_used", "skills": [...] },
    "accreditation_agencies": [...],
    "institutional_context": { "consolidated_summary", "source_documents": [...] },
    "reputation": { "summary", "source_count" },
    "program_specifications": { "file_count", "files": [...] },
    "deep_research": { "modules_run": [...], "results": { ... } }
  },
  "curriculum": {
    "learning_outcomes": { "markdown": "..." },
    "course_list": { "markdown": "...", "courses_detected": [...] },
    "competency_map": { "markdown": "..." },
    "syllabi": { "CODE": { "markdown": "..." } }
  }
}
```

See `curriculum_export_sample.json` for a complete worked example.

---

## Known Limitations

- **Non-Latin-1 scripts** (Arabic, Chinese, etc.) require adding a TTF font via `pdf.add_font()` in `pdf_exporter.py`; Latin-1 is the current default with Unicode approximation
- **Ollama must be running** for all generation and summarisation steps; no offline fallback
- **`nlm login` required** for NotebookLM features; session-based auth expires and must be re-run manually
- **Deep research results are not cached** to disk — closing the browser tab loses them; `utils/deep_research_cache.py` is a planned addition
- **NLM deep research uses fast mode exclusively** (deep mode returns a quota error on the Google Workspace account used); 3 passes × ~10 sources = ~30 sources per module
- **JSON export requires manual trigger** in Tab 4; it is not auto-saved at the end of each generation step
- **Video/audio transcription** requires `pip install openai-whisper` and `ffmpeg` on PATH (not in `requirements.txt`)
- **Competency map** is plain markdown text; a dedicated table renderer would improve readability in the UI

---

## License

MIT. Built with Streamlit, Ollama, fpdf2, pdfplumber, python-docx, and the `nlm` CLI.
