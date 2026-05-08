# Curriculum Builder

An AI-powered Streamlit application that synthesises job market demand, accreditation standards, institutional documentation, expert pedagogical knowledge, and Bloom's Taxonomy alignment into a complete academic curriculum proposal — using a locally-running Ollama LLM and NotebookLM for deep research.

---

## What It Does

Academic curriculum design is traditionally slow, anecdotal, and disconnected from real-world labour market signals. Curriculum Builder solves this by pulling multiple streams of evidence — what employers are actually hiring for, what accreditation bodies require, what the institution already stands for, and what expert pedagogical and accreditation literature recommends — and feeding them into a large language model that writes the full curriculum document set in one guided pipeline run.

The app produces program-level learning outcomes, a sequenced course list, a competency mapping table, and individual course syllabi. Every generated document is grounded in real skill frequency data from job postings, structured quality standards from accreditation agencies, the institution's own policies and reputation profile, and expert knowledge retrieved via an agentic RAG system from curated pedagogical, accreditation, and industry literature.

Once outcomes are generated, the built-in Bloom's Taxonomy analyser classifies every outcome by cognitive level, flags weak or unmeasurable verbs, shows a distribution chart, and offers AI-assisted rewriting of flagged items — all before the rest of the curriculum is built. The result is a pedagogically grounded, structured, exportable curriculum proposal saved as a machine-readable `curriculum_export.json` (schema v2.0 includes a full `pedagogy` block) for downstream applications such as committee review tools, program comparison dashboards, or accreditation reporting systems.

---

## Key Features

- **Job market skill analysis** — loads skill frequency data from a SQLite database (`jobs.db`) or CSV export; ranks skills by job count and mention rate
- **Accreditation standards integration** — reads structured `quality_definition.json` files from a multi-agency quality assurance library; filters by program scope and jurisdiction
- **Institutional document summarisation** — extracts and consolidates content from PDF, DOCX, and TXT policy files using an Ollama LLM; caches the consolidated profile per institution
- **Program specifications loader** — ingests any stakeholder materials folder: Excel, Word, PDF, PowerPoint, images (via Ollama vision), video/audio (via Whisper), CSV, TXT
- **Six-module deep research engine** — Tab 2 runs six independent NotebookLM research modules (Institutional Reputation, Legal Framework, Competitive Landscape, Student Market, Institutional History, Strategic Analysis); each module runs 3 targeted fast-research passes (~30 sources per module) and queries NotebookLM for a structured answer
- **Agentic RAG on expert knowledge bases** — Tab 4 indexes curated PDFs from a `pedagogy_context/knowledge_bases/` folder (pedagogical_expert, accreditation_specialist, industry_liaison, student_advocate personas); before each generation step, an Ollama call generates targeted retrieval queries, top chunks are fetched via TF-IDF, and injected into the generation prompt; retrieved excerpts are visible in collapsible expanders
- **Explicit program duration** — a "Duration (semesters)" field in Tab 1 (hidden for CE programs) is threaded through all generation steps to ensure consistent semester references across every generated document
- **Bloom's Taxonomy analysis** — classifies every learning outcome by cognitive level (remember → create), flags weak/unmeasurable verbs, displays a distribution bar chart, and offers AI-assisted rewriting of flagged outcomes before course generation begins
- **Enforced course code format** — course list generation uses a strict `**[CODE] Course Name**` prompt rule (e.g. CS101, DATA301) so Step 3 auto-detects all course codes without manual fallback; CE programs use `**[MOD001]**` format
- **Three-step curriculum generation** — sequential LLM pipeline (Tab 4): course list → competency map → individual syllabi; outcomes are authored in Tab 3
- **JSON proposal export** — saves a structured `curriculum_export.json` to the output folder with all inputs and generated content; schema v2.0 includes a `pedagogy` block when Bloom analysis was run

---

## Architecture Overview

The app follows a five-tab pipeline. Loaders ingest heterogeneous source data, the agentic RAG retriever indexes expert knowledge, the generator builds LLM context and streams curriculum text, the Bloom analyser classifies outcomes, and the exporter writes the proposal JSON to disk.

```
jobs.db / CSV ──► job_loader ───────────────────────────────► skills_df
quality_definition.json ──► quality_loader ─────────────────► agencies list
institutional PDFs ──► doc_loader ──► doc_summarizer ───────► consolidated summary
program specs folder ──► program_specs_loader ──────────────► specs text
NotebookLM modules ──► deep_research_loader ────────────────► research results (6 modules)
knowledge_bases PDFs ──► kb_loader ──► kb_retriever ────────► expert KB chunks (agentic TF-IDF)
                                    │
                            prompt_builder (assembles context)              [Tab 2]
                                    │
                    curriculum_gen → generate_learning_outcomes             [Tab 3]
                                    │
              bloom_outcome_extractor → analyze_all_outcomes               [Tab 3]
              → analyze_coverage → improve_outcome (Bloom pipeline)
                                    │
              kb_retriever (agentic query gen → TF-IDF retrieval)          [Tab 4]
                                    │
                    curriculum_gen → course list, map, syllabi              [Tab 4]
                                    │
                          curriculum_exporter → curriculum_export.json      [Tab 5]
```

All Ollama generation uses `POST /api/chat` with `stream: true`. Doc summarisation and KB query generation use `stream: false`. Models are discovered at startup via `GET /api/tags`. Bloom keyword classification uses `bloom_verbs.json`; unresolved verbs fall back to Ollama LLM classification.

---

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) running locally (default: `http://localhost:11434`) with at least one model pulled (e.g. `ollama pull llama3`)
- Optional: `nlm` CLI authenticated (`nlm login`) for NotebookLM-based deep research features
- Optional: `ffmpeg` + `openai-whisper` for video/audio transcription in the program specs loader
- Optional: `pedagogy_context/knowledge_bases/` folder with expert PDFs for the agentic RAG feature

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
Set the institution name, program name, program level, and program duration in semesters (or total contact hours for CE programs). Load job market skills from `jobs.db`, quality standards from the accreditation library, program specification documents from a folder, and institutional policy PDFs.

**Tab 2 — Context & Research**
The central intelligence tab. Review loaded skills and agency requirements, summarise and consolidate institutional documents (with per-institution disk cache), and run all six NotebookLM deep research modules. Each module runs 3 fast-research passes and queries NotebookLM for a structured answer. The reputation module result is stored as the program's reputation profile for injection into generation prompts. The full assembled LLM context is visible for inspection.

**Tab 3 — Outcomes & Bloom**
Three-step sub-pipeline: (1) Generate learning outcomes from all gathered context — streams live. (2) Run Bloom's Taxonomy analysis — classifies every outcome by cognitive level, shows KPI metrics, a level distribution bar chart, and a filterable outcome table with flags. (3) Refine flagged outcomes — for each outcome with weak or unmeasurable verbs, generate an AI-written rewrite and approve it to replace the original.

**Tab 4 — Generate**
Run the three remaining curriculum generation steps, each streaming live. Requires learning outcomes from Tab 3. Start by clicking **Load Knowledge Bases** to enable agentic RAG — before each step, Ollama generates targeted retrieval queries and expert chunks are injected into the prompt. Steps: (1) Course List, (2) Competency Map, (3) Individual Syllabi (select which courses to generate).

**Tab 5 — Export**
Click **Save Proposal to Output Folder** to build and save `curriculum_export.json` to the dated output folder hierarchy. The export includes all inputs, generated content, and (if run) the full Bloom pedagogy block.

---

## Project Structure

```
curriculum_builder/
├── app.py                        Streamlit entrypoint — 5 tabs
├── config.py                     Constants: Ollama URL, output paths, languages, program levels
├── requirements.txt              Python dependencies (includes scikit-learn for RAG)
├── curriculum_export_sample.json Sample JSON export (Lambton College / Software Engineering)
│
├── loaders/
│   ├── job_loader.py             Reads jobs.db (SQLite) and CSV skill exports
│   ├── quality_loader.py         Reads catalog.json + quality_definition.json files
│   ├── doc_loader.py             Extracts text from PDF/DOCX/TXT institutional docs
│   ├── program_specs_loader.py   Multi-format loader: Excel, Word, PPTX, images, video, audio
│   ├── nlm_client.py             Shared NotebookLMClient factory; auth check; httpx timeout patch
│   ├── bloom_outcome_extractor.py Parses outcomes markdown → OutcomeRecord list (6 heading variants)
│   ├── bloom_loader.py           Loads bloom_verbs.json + weak_verbs.json into lookup structures
│   ├── pdf_downloader.py         Scrapes and downloads PDFs from a given webpage URL
│   ├── deep_research_loader.py   Six-module NotebookLM research engine (3 passes/module)
│   ├── kb_loader.py              Chunks PDFs from knowledge_bases/ by expert persona for RAG
│   └── kb_retriever.py           TF-IDF index + agentic Ollama query gen + context builder
│
├── generator/
│   ├── doc_summarizer.py         LLM summarisation of institutional documents
│   ├── prompt_builder.py         Assembles all context strings for LLM prompts
│   ├── curriculum_gen.py         Ollama streaming generation: outcomes, courses, map, syllabi
│   ├── bloom_prompt_builder.py   Builds Bloom-aligned outcome rewrite prompts
│   └── outcome_improver.py       Streams AI rewrites of flagged outcomes
│
├── analyzers/
│   ├── bloom_classifier.py       Classifies verbs by Bloom level (keyword + LLM fallback)
│   ├── verb_extractor.py         Extracts leading action verbs from outcome sentences
│   ├── outcome_analyzer.py       Runs full Bloom analysis on a list of OutcomeRecords
│   └── coverage_analyzer.py      Aggregates Bloom level distribution across all outcomes
│
├── exporter/
│   ├── pdf_exporter.py           Markdown → PDF via fpdf2 (available for future use)
│   ├── bloom_exporter.py         Formats Bloom analysis results as exportable block
│   └── curriculum_exporter.py    Builds and saves structured curriculum_export.json
│
├── data/
│   ├── bloom_verbs.json          Verb → Bloom level lookup table
│   └── weak_verbs.json           Weak/unmeasurable verb list
│
├── utils/
│   ├── institutional_cache.py    Fingerprints doc set; caches consolidated summaries to disk
│   └── deep_research_cache.py    Persists deep research results between sessions (keyed by institution + module set)
│
├── tests/                        pytest test suite (203 tests across all modules)
└── outputs/                      Generated JSON proposals (git-ignored)
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
| Knowledge bases | `../pedagogy_context/knowledge_bases/` | Hardcoded in `loaders/kb_loader.py` as `KB_ROOT` |
| LLM context window | 8192 tokens | Set in `curriculum_gen.py` `_OPTIONS` |
| Ollama temperature | 0.45 (generation), 0.2 (RAG queries) | Set per-function in `curriculum_gen.py` and `kb_retriever.py` |
| KB max context | 6000 chars | Set in `kb_retriever.py` `_MAX_KB_CONTEXT_CHARS` |

The app expects Ollama to be running. If unreachable at startup, the model selector falls back to a free-text input. The knowledge bases RAG is optional — if the folder doesn't exist or **Load Knowledge Bases** is not clicked, generation proceeds without it.

---

## Output / Exports

### JSON Export (`curriculum_export.json`)

Saved to `outputs/{Institution}/{YYYY-MM}/{Program}/curriculum_export.json`.

Schema version `1.0` (or `2.0` when Bloom analysis was run). Top-level structure:

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

When Bloom analysis has been run, `schema_version` is `"2.0"` and a `pedagogy` block is appended containing the full analysis results and coverage report.

See `curriculum_export_sample.json` for a complete worked example.

---

## Known Limitations

- **Ollama must be running** for all generation and summarisation steps; no offline fallback
- **`nlm login` required** for NotebookLM features; session-based auth expires and must be re-run manually
- **KB index rebuilt on every browser refresh** — stored in session state only; a disk pickle cache would speed up repeat loads (deep research results are cached to disk via `utils/deep_research_cache.py` and restored on next session)
- **NLM deep research uses fast mode exclusively** (deep mode returns a quota error on the Google Workspace account used); 3 passes × ~10 sources = ~30 sources per module
- **Non-Latin-1 scripts** (Arabic, Chinese, etc.) require adding a TTF font via `pdf.add_font()` in `pdf_exporter.py`
- **Video/audio transcription** requires `pip install openai-whisper` and `ffmpeg` on PATH (not in `requirements.txt`)
- **Competency map** is plain markdown text; a dedicated table renderer would improve readability in the UI

---

## License

MIT. Built with Streamlit, Ollama, scikit-learn, pdfplumber, python-docx, fpdf2, and the `nlm` CLI.
