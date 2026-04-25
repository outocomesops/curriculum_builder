"""
Curriculum Builder
==================
Streamlit app that synthesises job market demand, accreditation quality standards,
institutional documentation, and public reputation into a fully generated academic curriculum.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import json
import re
import sys
import os
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    OLLAMA_DEFAULT_URL, OUTPUTS_DIR, SUPPORTED_LANGUAGES, PROGRAM_LEVELS,
    JOB_MARKET_DB, QUALITY_SOURCES_DIR, INSTITUTIONAL_DOCS_DIR, INSTITUTIONS_DIR,
)
from utils.institutional_cache import load_cache, save_cache, cache_path
from loaders.job_loader import get_available_queries, load_skills_from_db, load_skills_from_csv
from loaders.quality_loader import get_all_scopes, load_agencies_with_quality
from loaders.doc_loader import load_institutional_docs
from loaders.program_specs_loader import load_program_specs
from loaders.deep_research_loader import MODULE_REGISTRY, run_research_module, build_deep_research_context
from loaders.pdf_downloader import scrape_pdf_links, download_pdfs
from loaders.reputation_loader import fetch_reputation_snippets
from loaders.reputation_loader_nlm import fetch_reputation_via_notebooklm
from generator.doc_summarizer import (
    batch_summarize,
    consolidate_summaries,
    summarize_reputation,
    summarize_doc,
)
from generator.prompt_builder import (
    build_skills_context,
    build_accreditation_context,
    build_institutional_context,
    build_reputation_context,
    build_program_specs_context,
)
from generator.curriculum_gen import (
    list_ollama_models,
    generate_learning_outcomes,
    generate_course_list,
    generate_competency_map,
    generate_syllabus,
)
from exporter.pdf_exporter import (
    save_section_pdf,
    save_syllabus_pdf,
    save_full_curriculum_pdf,
    _USE_UNICODE,
    _UNICODE_FONT_PATH,
)
from exporter.curriculum_exporter import build_curriculum_export, save_curriculum_export

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Curriculum Builder",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "skills_df": None,
    "agencies": [],
    "institutional_docs": [],
    "doc_summaries": [],
    "consolidated_summary": "",
    "reputation_snippets": [],
    "reputation_summary": "",
    "reputation_nlm_notebook_id": "",
    "_preview_pdf_links": [],
    "program_specs_docs": [],
    "deep_research_results": {},
    "learning_outcomes": "",
    "course_list": "",
    "competency_map": "",
    "syllabi": {},
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ---------------------------------------------------------------------------
# Sidebar — global settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📚 Curriculum Builder")
    st.caption("Job Market × Accreditation × Institution × Reputation")
    st.divider()

    st.subheader("Ollama Settings")
    ollama_url = st.text_input(
        "Ollama URL",
        value=OLLAMA_DEFAULT_URL,
        help="URL of the local Ollama instance (default: http://localhost:11434)",
    )

    available_models = list_ollama_models(ollama_url)
    if available_models:
        st.caption(f"✅ {len(available_models)} model(s) available — select per tab below.")
    else:
        st.warning("Cannot reach Ollama. Check that it is running.")

    st.divider()

    st.subheader("Output Language")
    language_label = st.selectbox("Language", options=list(SUPPORTED_LANGUAGES.keys()))
    language = SUPPORTED_LANGUAGES[language_label]

    st.divider()

    st.subheader("Output Folder")
    custom_output = st.text_input(
        "Base output directory",
        value=str(OUTPUTS_DIR),
        help="All PDFs will be saved under {output}/{institution}/{YYYY-MM}/{program}/",
    )
    base_outputs = Path(custom_output)

    st.divider()
    if _USE_UNICODE:
        st.caption(f"✅ Unicode font: `{Path(_UNICODE_FONT_PATH).name}`")
    else:
        st.caption("⚠️ Latin-1 font only (non-Latin scripts will be approximated)")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_sources, tab_context, tab_generate, tab_export = st.tabs([
    "1  Sources & Setup",
    "2  Context & Research",
    "3  Generate",
    "4  Export",
])


# ============================================================
# TAB 1 — SOURCES & SETUP
# ============================================================
with tab_sources:
    st.header("Sources & Program Setup")

    # ---- Institution & Program ----
    st.subheader("Institution & Program")
    col_inst_a, col_inst_b, col_inst_c = st.columns([3, 3, 2])
    with col_inst_a:
        institution_name = st.text_input("Institution name", placeholder="e.g. Universidad Libertadores")
    with col_inst_b:
        program_name = st.text_input("Program name", placeholder="e.g. Bachelor of Software Engineering")
    with col_inst_c:
        program_level = st.selectbox("Program level", options=PROGRAM_LEVELS)

    course_hours: int | None = None
    if program_level == "Continuous Education":
        course_hours = st.number_input(
            "Total course hours",
            min_value=8, max_value=1000, value=40, step=8,
            help="Total contact/instructional hours for the continuing education program.",
        )

    st.divider()

    # ---- Job market data ----
    st.subheader("Job Market Skills")
    _db_exists = JOB_MARKET_DB.exists()
    if _db_exists:
        st.caption(f"Database: `{JOB_MARKET_DB}`")
        _db_queries = get_available_queries(str(JOB_MARKET_DB))
        if _db_queries:
            selected_queries = st.multiselect(
                "Filter by job-title queries",
                options=_db_queries,
                default=_db_queries,
                help="Select which job-title queries to include in the skill analysis.",
            )
        else:
            selected_queries = []
            st.warning("No queries found in jobs.db — run the job-market search first.")

        col_db1, col_db2 = st.columns([1, 3])
        with col_db1:
            if st.button("Load Skills from DB", type="primary", disabled=not _db_queries):
                with st.spinner("Loading skills..."):
                    df = load_skills_from_db(str(JOB_MARKET_DB), selected_queries or None)
                if df.empty:
                    st.error("No skills found. Make sure the job-market analysis has been run.")
                else:
                    st.session_state["skills_df"] = df
                    st.success(f"Loaded {len(df)} unique skills.")
        with col_db2:
            if st.session_state["skills_df"] is not None and not st.session_state["skills_df"].empty:
                st.caption(f"✅ {len(st.session_state['skills_df'])} skills loaded")
    else:
        st.warning(f"jobs.db not found at `{JOB_MARKET_DB}`. Use CSV export instead.")

    with st.expander("Load from CSV instead"):
        csv_path = st.text_input("Path to skills CSV", placeholder=r"C:\Users\...\skills_export.csv")
        if st.button("Load Skills from CSV", disabled=not csv_path):
            with st.spinner("Loading..."):
                df = load_skills_from_csv(csv_path)
            if df.empty:
                st.error("Could not load CSV.")
            else:
                st.session_state["skills_df"] = df
                st.success(f"Loaded {len(df)} unique skills.")

    st.divider()

    # ---- Quality standards ----
    st.subheader("Accreditation Quality Standards")
    _qa_exists = QUALITY_SOURCES_DIR.exists()
    if _qa_exists:
        st.caption(f"Standards folder: `{QUALITY_SOURCES_DIR}`")
        _qa_scopes = get_all_scopes(str(QUALITY_SOURCES_DIR))
        if _qa_scopes:
            selected_scopes = st.multiselect(
                "Program scope filter",
                options=_qa_scopes,
                help="Filter agencies to those covering your program type.",
            )
            _agencies_preview = load_agencies_with_quality(str(QUALITY_SOURCES_DIR), selected_scopes or None)
            if _agencies_preview:
                _agency_options = {
                    f"{a['agency_name']} ({a['jurisdiction'].upper()})": a
                    for a in _agencies_preview
                }
                selected_agency_labels = st.multiselect(
                    f"Select agencies ({len(_agencies_preview)} available)",
                    options=list(_agency_options.keys()),
                    default=list(_agency_options.keys()),
                )
            else:
                selected_agency_labels = []
                st.info("No agencies match the selected scopes.")
        else:
            selected_scopes = []
            selected_agency_labels = []
            st.warning("Could not read catalog.json — check the quality_assurance/sources/ folder.")

        col_qa1, col_qa2 = st.columns([1, 3])
        with col_qa1:
            if st.button("Load Quality Standards", type="primary", disabled=not _qa_exists):
                with st.spinner("Loading agency data..."):
                    all_agencies = load_agencies_with_quality(str(QUALITY_SOURCES_DIR), selected_scopes or None)
                    if selected_agency_labels:
                        label_set = set(selected_agency_labels)
                        filtered = [
                            a for a in all_agencies
                            if f"{a['agency_name']} ({a['jurisdiction'].upper()})" in label_set
                        ]
                    else:
                        filtered = all_agencies
                    st.session_state["agencies"] = filtered
                st.success(f"Loaded {len(filtered)} agency quality definition(s).")
        with col_qa2:
            if st.session_state["agencies"]:
                st.caption(f"✅ {len(st.session_state['agencies'])} agency standard(s) loaded")
    else:
        st.warning(f"Quality standards folder not found at `{QUALITY_SOURCES_DIR}`.")

    st.divider()

    # ---- Program Specifications ----
    st.subheader("Program Specifications")
    st.caption(
        "Point to a folder containing **any** stakeholder materials: "
        "Excel, Word, PDF, PowerPoint, images (PNG/JPG/…), videos, audio, CSV, TXT. "
        "The app will extract as much content as possible from every file."
    )

    specs_folder = st.text_input(
        "Program specs folder",
        placeholder=r"C:\Users\...\program_specifications",
        key="specs_folder",
        help="All sub-folders are scanned recursively.",
    )

    # Vision model selector (only shown when images may be present)
    _vision_model_options = ["(none — skip images)"] + (available_models if available_models else [])
    specs_vision_model = st.selectbox(
        "Vision model for image files",
        options=_vision_model_options,
        key="specs_vision_model",
        help="Select a vision-capable model (e.g. llava, gemma3) to extract text from images. "
             "Leave as '(none)' to skip image files.",
    )
    _vision_model = None if specs_vision_model.startswith("(none") else specs_vision_model

    col_specs1, col_specs2 = st.columns([1, 3])
    with col_specs1:
        _load_specs_disabled = not specs_folder
        if st.button("Load Program Specs", type="primary", disabled=_load_specs_disabled, key="btn_load_specs"):
            _prog_bar = st.progress(0, "Scanning folder…")

            def _specs_progress(i, total, name):
                pct = int((i + 1) / max(total, 1) * 100)
                _prog_bar.progress(pct, f"Processing: {name}")

            with st.spinner("Extracting content from all files…"):
                _specs_docs = load_program_specs(
                    specs_folder,
                    ollama_url=ollama_url,
                    vision_model=_vision_model,
                    progress_callback=_specs_progress,
                )
            _prog_bar.empty()

            st.session_state["program_specs_docs"] = _specs_docs

            _ok_s   = [d for d in _specs_docs if not d["error"] and d["char_count"] > 0]
            _warn_s  = [d for d in _specs_docs if not d["error"] and d["char_count"] == 0]
            _err_s   = [d for d in _specs_docs if d["error"]]

            if _ok_s:
                st.success(f"Extracted content from {len(_ok_s)} file(s).")
            if not _specs_docs:
                st.warning(f"No supported files found in `{specs_folder}`.")

    with col_specs2:
        _loaded_specs = st.session_state.get("program_specs_docs", [])
        if _loaded_specs:
            _ok_s  = [d for d in _loaded_specs if not d["error"] and d["char_count"] > 0]
            _err_s = [d for d in _loaded_specs if d["error"]]
            st.caption(f"✅ {len(_ok_s)} file(s) loaded  |  ❌ {len(_err_s)} error(s)")

    if st.session_state.get("program_specs_docs"):
        with st.expander("View loaded program spec files", expanded=False):
            _type_icons = {
                "text": "📄", "spreadsheet": "📊", "pdf": "📑",
                "word": "📝", "excel": "📊", "presentation": "📋",
                "image": "🖼️", "video": "🎬", "audio": "🎵", "unknown": "❓",
            }
            for d in st.session_state["program_specs_docs"]:
                icon = _type_icons.get(d["file_type"], "❓")
                if d["error"]:
                    st.caption(f"  {icon} ❌ **{d['filename']}** — {d['error']}")
                elif d["char_count"] == 0:
                    st.caption(f"  {icon} ⚠️ **{d['filename']}** — no text extracted")
                else:
                    st.caption(f"  {icon} ✅ **{d['filename']}** ({d['char_count']:,} chars)")

    st.divider()

    # ---- Institutional documentation ----
    st.subheader("Institutional Documentation")
    st.caption(
        "Provide the institution's policy, mission, and strategic planning documents "
        "for the LLM to extract values and context."
    )

    doc_tab_local, doc_tab_url = st.tabs(["📁  Load from folder", "🌐  Download from URL"])

    # -- Local folder --
    with doc_tab_local:
        _default_docs_folder = str(INSTITUTIONAL_DOCS_DIR)
        docs_folder = st.text_input(
            "Folder path",
            value=_default_docs_folder,
            help="Folder with PDF, DOCX, or TXT files.",
        )
        if st.button("Load Documents from Folder", type="primary"):
            with st.spinner("Scanning folder..."):
                docs = load_institutional_docs(docs_folder)
            if not docs:
                st.warning(f"No files found in `{docs_folder}`.")
            else:
                ok = [d for d in docs if not d["error"] and d["char_count"] > 0]
                empty = [d for d in docs if not d["error"] and d["char_count"] == 0]
                errors = [d for d in docs if d["error"]]
                st.session_state["institutional_docs"] = ok
                st.session_state["doc_summaries"] = []
                st.session_state["consolidated_summary"] = ""
                if ok:
                    st.success(f"Loaded {len(ok)} document(s) with text.")
                    for d in ok:
                        st.caption(f"  ✅ {d['filename']}  ({d['char_count']:,} chars)")
                if empty:
                    for d in empty:
                        st.caption(f"  ⚠️ {d['filename']} — no extractable text")
                if errors:
                    for d in errors:
                        st.caption(f"  ❌ {d['filename']} — {d['error']}")

    # -- Download from URL --
    with doc_tab_url:
        st.markdown(
            "Paste the URL of a webpage that lists PDF documents "
            "(e.g. an institutional documents portal). "
            "The app will scrape all PDF links and download them automatically."
        )
        doc_page_url = st.text_input(
            "Webpage URL",
            placeholder="https://www.institution.edu/documentos-institucionales/",
            key="doc_page_url",
        )
        download_dest = st.text_input(
            "Save PDFs to folder",
            value=str(INSTITUTIONAL_DOCS_DIR),
            key="doc_download_dest",
        )

        if doc_page_url:
            if st.button("Preview PDF links on this page", key="btn_preview_pdfs"):
                with st.spinner("Fetching page..."):
                    try:
                        found_links = scrape_pdf_links(doc_page_url)
                        st.session_state["_preview_pdf_links"] = found_links
                    except Exception as exc:
                        st.error(f"Could not fetch page: {exc}")
                        st.session_state["_preview_pdf_links"] = []

            if st.session_state.get("_preview_pdf_links"):
                found_links = st.session_state["_preview_pdf_links"]
                st.info(f"Found {len(found_links)} PDF link(s) on this page.")
                selected_links = st.multiselect(
                    "Select PDFs to download",
                    options=found_links,
                    default=found_links,
                    format_func=lambda u: Path(u).name,
                    key="selected_pdf_links",
                )
                if st.button(
                    f"Download {len(selected_links)} PDF(s)",
                    type="primary",
                    disabled=not selected_links,
                    key="btn_download_pdfs",
                ):
                    prog = st.progress(0, "Starting downloads...")

                    def _prog_cb(i, total, url):
                        prog.progress((i + 1) / total, f"Downloading: {Path(url).name}")

                    with st.spinner("Downloading..."):
                        results = download_pdfs(
                            selected_links,
                            Path(download_dest),
                            progress_callback=_prog_cb,
                        )
                    prog.empty()

                    ok_dl = [r for r in results if not r["error"]]
                    fail_dl = [r for r in results if r["error"]]
                    if ok_dl:
                        st.success(f"Downloaded {len(ok_dl)} PDF(s) to `{download_dest}`.")
                    if fail_dl:
                        for r in fail_dl:
                            st.warning(f"Failed: {r['filename']} — {r['error']}")

                    # Auto-load downloaded files into session
                    if ok_dl:
                        with st.spinner("Loading downloaded documents..."):
                            docs = load_institutional_docs(download_dest)
                        ok = [d for d in docs if not d["error"] and d["char_count"] > 0]
                        st.session_state["institutional_docs"] = ok
                        st.session_state["doc_summaries"] = []
                        st.session_state["consolidated_summary"] = ""
                        if ok:
                            st.info(f"Auto-loaded {len(ok)} document(s) — ready for summarisation in Context Preview.")

    # ---- Institutional Reputation ----
    st.divider()
    with st.expander("Institutional Reputation (Public Perception)", expanded=False):
        inst_for_rep = institution_name
        if not inst_for_rep:
            st.info("Enter the institution name above first.")
        else:
            st.markdown(
                f"Research public perception of **{inst_for_rep}** "
                "(reviews, rankings, news, graduate outcomes)."
            )

            col_rep1, col_rep2, col_rep3 = st.columns([3, 2, 1])
            with col_rep1:
                rep_name_override = st.text_input(
                    "Institution name for search (edit if needed)",
                    value=inst_for_rep,
                    key="rep_name",
                )
            with col_rep2:
                rep_city = st.text_input(
                    "City / region (optional)",
                    placeholder="e.g. Sarnia, Ontario",
                    key="rep_city",
                )
            with col_rep3:
                max_results = st.number_input("Results per query", min_value=3, max_value=15, value=5)

            # --- NotebookLM research (primary) ---
            st.markdown("**Option 1 — Research via NotebookLM** *(recommended)*")
            st.caption(
                "Creates a NotebookLM notebook, loads web sources about the institution, "
                "and queries them for a structured reputation summary."
            )
            extra_urls_raw = st.text_area(
                "Extra URLs to include as sources (one per line, optional)",
                height=80,
                key="rep_extra_urls",
                placeholder="https://www.theobserver.ca/tag/lambton-college\nhttps://en.wikipedia.org/wiki/Lambton_College",
            )
            nlm_cleanup = st.checkbox(
                "Delete NotebookLM notebook after research", value=True, key="rep_nlm_cleanup"
            )

            if st.button("Research Reputation via NotebookLM", type="primary", key="btn_rep_nlm"):
                extra_urls = [u.strip() for u in extra_urls_raw.splitlines() if u.strip()]
                with st.spinner("Creating NotebookLM notebook and loading web sources…"):
                    try:
                        nb_id, rep_summary = fetch_reputation_via_notebooklm(
                            institution_name=rep_name_override,
                            city=rep_city,
                            extra_urls=extra_urls or None,
                            cleanup=nlm_cleanup,
                            research_timeout=420,
                            research_mode="deep",
                            query_timeout=120,
                        )
                        st.session_state["reputation_summary"] = rep_summary
                        st.session_state["reputation_snippets"] = []
                        st.session_state["reputation_nlm_notebook_id"] = "" if nlm_cleanup else nb_id
                        if not nlm_cleanup:
                            st.info(f"Notebook kept — ID: `{nb_id}`")
                        st.success("Reputation profile ready.")
                    except Exception as exc:
                        st.error(f"NotebookLM research failed: {exc}")

            st.divider()

            # --- DuckDuckGo fallback ---
            st.markdown("**Option 2 — Web search + Ollama analysis** *(fallback)*")
            _rep_ddg_col1, _rep_ddg_col2 = st.columns([2, 3])
            with _rep_ddg_col1:
                _rep_model = (
                    st.selectbox("Model for analysis", options=available_models, key="rep_model")
                    if available_models
                    else st.text_input("Model for analysis", value="llama3", key="rep_model")
                )
            if st.button("Search & Analyse Reputation (DuckDuckGo)", key="btn_rep_ddg"):
                with st.spinner("Searching the web for reputation data..."):
                    snippets = fetch_reputation_snippets(rep_name_override, max_results_per_query=max_results)
                st.session_state["reputation_snippets"] = snippets
                if snippets:
                    st.info(f"Found {len(snippets)} web snippets. Running LLM analysis...")
                    with st.spinner("LLM is analysing public perception..."):
                        rep_summary = summarize_reputation(
                            rep_name_override, snippets, ollama_url, _rep_model
                        )
                    st.session_state["reputation_summary"] = rep_summary
                    st.success("Reputation profile ready.")
                else:
                    st.warning("No web results returned. Check your internet connection or try a different name.")

            st.divider()

            # --- Manual paste ---
            st.markdown("**Option 3 — Paste your own text**")
            manual_rep = st.text_area(
                "Paste reputation text here",
                height=120,
                key="manual_rep_text",
                placeholder="Paste any text about the institution's public reputation, rankings, reviews, etc.",
            )
            if st.button("Analyse Pasted Reputation Text", disabled=not manual_rep.strip()):
                _rep_model_paste = available_models[0] if available_models else "llama3"
                with st.spinner("LLM is analysing..."):
                    manual_snippets = [{"title": "Manual input", "snippet": manual_rep}]
                    rep_summary = summarize_reputation(
                        inst_for_rep, manual_snippets, ollama_url, _rep_model_paste
                    )
                st.session_state["reputation_summary"] = rep_summary
                st.session_state["reputation_snippets"] = manual_snippets
                st.success("Reputation profile ready.")

            if st.session_state["reputation_summary"]:
                st.divider()
                st.subheader("Reputation Profile")
                word_count = len(st.session_state["reputation_summary"].split())
                st.caption(f"{word_count} words — will be passed to curriculum generation")
                st.markdown(st.session_state["reputation_summary"])

                if st.button("Clear reputation data"):
                    st.session_state["reputation_snippets"] = []
                    st.session_state["reputation_summary"] = ""
                    st.session_state["reputation_nlm_notebook_id"] = ""
                    st.rerun()

    # ---- Status summary ----
    st.divider()
    st.subheader("Setup Status")
    c1, c2, c3, c4 = st.columns(4)
    skills_df: pd.DataFrame | None = st.session_state["skills_df"]
    c1.metric("Skills loaded", len(skills_df) if skills_df is not None and not skills_df.empty else 0)
    c2.metric("Agencies loaded", len(st.session_state["agencies"]))
    c3.metric("Documents loaded", len(st.session_state["institutional_docs"]))
    c4.metric("Reputation data", "Yes" if st.session_state["reputation_summary"] else "No")

    st.session_state["_institution"] = institution_name
    st.session_state["_program"] = program_name
    st.session_state["_program_level"] = program_level
    st.session_state["_course_hours"] = course_hours


# ============================================================
# TAB 2 — CONTEXT PREVIEW
# ============================================================
with tab_context:
    st.header("Context Preview")
    st.caption("Review and process all inputs before generating.")

    # Model selector for this tab
    _ctx_col1, _ctx_col2 = st.columns([2, 5])
    with _ctx_col1:
        if available_models:
            model_ctx = st.selectbox("LLM model (summarisation)", options=available_models, key="model_ctx")
        else:
            model_ctx = st.text_input("LLM model (summarisation)", value="llama3", key="model_ctx")

    skills_df = st.session_state["skills_df"]
    agencies = st.session_state["agencies"]
    docs = st.session_state["institutional_docs"]

    # ---- Skills preview ----
    with st.expander("Job Market Skills", expanded=bool(skills_df is not None and not skills_df.empty)):
        if skills_df is not None and not skills_df.empty:
            top_n = st.slider("Top N skills to use in generation", 10, 80, 40, key="top_n_ctx")
            st.dataframe(
                skills_df.head(top_n).rename(columns={
                    "skill_name": "Skill", "skill_type": "Type",
                    "job_count": "# Jobs", "mention_rate": "Mention Rate (%)",
                }),
                height=300,
                use_container_width=True,
            )
        else:
            st.info("No skills loaded yet — go to Sources & Setup.")

    # ---- Agencies preview ----
    with st.expander("Accreditation Standards", expanded=bool(agencies)):
        if agencies:
            for a in agencies:
                st.markdown(f"**{a['agency_name']}** — {a['jurisdiction'].upper()}")
                if a.get("curriculum_requirements"):
                    for r in a["curriculum_requirements"]:
                        st.markdown(f"  - {r}")
                st.caption(a.get("definition_of_quality", ""))
                st.divider()
        else:
            st.info("No agencies loaded yet.")

    # ---- Institutional docs + summarisation ----
    with st.expander("Institutional Documents & Summarisation", expanded=bool(docs)):
        if docs:
            st.write(f"{len(docs)} document(s) loaded:")
            for d in docs:
                st.markdown(f"- **{d['filename']}** ({d['char_count']:,} chars)")

            st.divider()

            # Check for a cached consolidated summary for this institution + doc set
            _inst_name_ctx = st.session_state.get("_institution", "")
            _cached = load_cache(INSTITUTIONS_DIR, _inst_name_ctx, docs) if _inst_name_ctx else None

            if _cached and not st.session_state["consolidated_summary"]:
                st.success(
                    f"Cached institutional profile found for **{_inst_name_ctx}** "
                    f"(documents unchanged). Load it to skip re-summarising."
                )
                _cp = cache_path(INSTITUTIONS_DIR, _inst_name_ctx)
                st.caption(f"Cache file: `{_cp}`")
                if st.button("Load from cache", type="primary", key="btn_load_cache"):
                    st.session_state["consolidated_summary"] = _cached
                    st.session_state["doc_summaries"] = []
                    st.success("Loaded from cache — ready for generation.")

            st.divider()

            # Step 1: individual summaries
            if st.button("Step 1 — Summarise Individual Documents", type="primary"):
                summaries = []
                prog = st.progress(0, text="Starting...")
                for i, doc in enumerate(docs):
                    prog.progress((i + 1) / len(docs), text=f"Summarising: {doc['filename']}")
                    result = summarize_doc(doc["text"], doc["filename"], ollama_url, model_ctx)
                    summaries.append(result)
                prog.empty()
                st.session_state["doc_summaries"] = summaries
                st.session_state["consolidated_summary"] = ""
                useful = sum(1 for s in summaries if s["has_content"])
                st.success(f"Done. {useful}/{len(docs)} documents contained usable content.")

            if st.session_state["doc_summaries"]:
                st.subheader("Individual Document Summaries")
                for s in st.session_state["doc_summaries"]:
                    icon = "✅" if s["has_content"] else "⚠️"
                    with st.expander(f"{icon} {s['filename']}"):
                        if s["has_content"]:
                            st.markdown(s["summary"])
                        elif s.get("error"):
                            st.error(f"Error: {s['error']}")
                        else:
                            st.warning("No relevant institutional content found.")

                st.divider()

                # Step 2: consolidated summary
                useful_count = sum(1 for s in st.session_state["doc_summaries"] if s["has_content"])
                if st.button(
                    "Step 2 — Consolidate into Single Institutional Profile (≤1000 words)",
                    type="primary",
                    disabled=useful_count == 0,
                ):
                    with st.spinner("Consolidating all summaries into one institutional profile..."):
                        consolidated = consolidate_summaries(
                            st.session_state["doc_summaries"], ollama_url, model_ctx
                        )
                    st.session_state["consolidated_summary"] = consolidated

                    # Auto-save to cache
                    if _inst_name_ctx and consolidated:
                        try:
                            saved_path = save_cache(INSTITUTIONS_DIR, _inst_name_ctx, docs, consolidated)
                            st.success(
                                f"Consolidated profile ready — saved to cache at `{saved_path}`."
                            )
                        except Exception as _ce:
                            st.success("Consolidated profile ready — this will be passed to the curriculum LLM.")
                            st.warning(f"Could not save cache: {_ce}")
                    else:
                        st.success("Consolidated profile ready — this will be passed to the curriculum LLM.")

            if st.session_state["consolidated_summary"]:
                st.subheader("Consolidated Institutional Profile")
                word_count = len(st.session_state["consolidated_summary"].split())
                st.caption(f"{word_count} words")
                st.markdown(st.session_state["consolidated_summary"])
        else:
            st.info("No documents loaded yet.")

    # ---- Deep Research ----
    st.divider()
    st.subheader("Deep Research")
    st.caption(
        "Multi-module NotebookLM research — legal framework, competitive landscape, "
        "student market, institutional history, and strategic analysis. "
        "Results are automatically injected into curriculum generation."
    )

    _dr_institution = st.session_state.get("_institution", "")
    _dr_program = st.session_state.get("_program", "")

    if not _dr_institution or not _dr_program:
        st.info("Set institution name and program name in **Sources & Setup** to enable deep research.")
    else:
        st.info(f"Researching: **{_dr_institution}** / {_dr_program}")

        # Module selection
        col_mod_l, col_mod_r = st.columns(2)
        for i, mod in enumerate(MODULE_REGISTRY):
            col = col_mod_l if i < 3 else col_mod_r
            with col:
                st.checkbox(
                    f"{mod['icon']}  {mod['title']}",
                    value=True,
                    key=f"deep_research_mod_{mod['key']}",
                    help=mod["description"],
                )

        _selected_keys = [
            m["key"] for m in MODULE_REGISTRY
            if st.session_state.get(f"deep_research_mod_{m['key']}", True)
        ]
        st.caption(f"{len(_selected_keys)} module(s) selected")

        # Configuration
        _dr_col1, _dr_col2, _dr_col3, _dr_col4 = st.columns([2, 1, 1, 1])
        with _dr_col1:
            _dr_extra_urls_raw = st.text_area(
                "Extra seed URLs (one per line, optional)",
                height=75,
                key="deep_research_extra_urls",
                placeholder="https://en.wikipedia.org/wiki/...\nhttps://www.institution.edu/about",
                help="Added as sources on top of the NLM-researched sources.",
            )
        with _dr_col2:
            _dr_research_mode = st.selectbox(
                "Research mode",
                options=["deep", "fast"],
                index=0,
                key="deep_research_mode",
                help="deep: ~5 min, ~40 sources  |  fast: ~30 s, ~10 sources",
            )
        with _dr_col3:
            _dr_research_timeout = st.number_input(
                "Research timeout (s)", min_value=60, max_value=900,
                value=420,
                key="deep_research_research_timeout",
                help="Total time allowed for NLM web research + source import per module.",
            )
        with _dr_col4:
            _dr_qry_timeout = st.number_input(
                "Query timeout (s)", min_value=30, max_value=300, value=120,
                key="deep_research_qry_timeout",
            )

        _dr_cleanup = st.checkbox(
            "Delete NotebookLM notebooks after research", value=True,
            key="deep_research_cleanup",
        )

        # Run button
        _run_label = f"Run Deep Research ({len(_selected_keys)} module(s))"
        if st.button(_run_label, type="primary", disabled=not _selected_keys, key="btn_deep_research"):
            _extra_urls = [u.strip() for u in _dr_extra_urls_raw.splitlines() if u.strip()]
            _ok_count = 0
            _total = len(_selected_keys)

            for _mod_key in _selected_keys:
                _mod = next(m for m in MODULE_REGISTRY if m["key"] == _mod_key)
                with st.status(f"{_mod['icon']}  {_mod['title']}…", expanded=True) as _status:
                    def _make_cb(status_ctx):
                        def _cb(msg):
                            status_ctx.write(msg)
                        return _cb

                    _result = run_research_module(
                        module_key=_mod_key,
                        institution_name=_dr_institution,
                        program_name=_dr_program,
                        extra_urls=_extra_urls or None,
                        research_timeout=int(_dr_research_timeout),
                        query_timeout=int(_dr_qry_timeout),
                        cleanup=_dr_cleanup,
                        progress_callback=_make_cb(_status),
                        research_mode=_dr_research_mode,
                    )
                    st.session_state["deep_research_results"][_mod_key] = _result

                    if _result["status"] == "ok":
                        _ok_count += 1
                        _status.update(label=f"✅ {_mod['title']}", state="complete")
                    else:
                        _status.update(label=f"❌ {_mod['title']}", state="error")
                        st.error(f"Error: {_result['error']}")
                        if _result.get("notebook_id"):
                            st.caption(f"Orphaned notebook ID: {_result['notebook_id']}")

            if _ok_count == _total:
                st.success(f"All {_total} module(s) completed successfully.")
            else:
                st.warning(f"{_ok_count}/{_total} module(s) succeeded.")

        # Results
        _dr_results = st.session_state.get("deep_research_results", {})
        if _dr_results:
            st.divider()
            st.subheader("Research Results")

            _metric_cols = st.columns(len(MODULE_REGISTRY))
            for _ci, _mod in enumerate(MODULE_REGISTRY):
                _r = _dr_results.get(_mod["key"])
                if _r is None:
                    _val = "Pending"
                elif _r["status"] == "ok":
                    _val = "Done"
                else:
                    _val = "Error"
                _metric_cols[_ci].metric(f"{_mod['icon']} {_mod['title']}", _val)

            st.divider()

            for _mod in MODULE_REGISTRY:
                _r = _dr_results.get(_mod["key"])
                if _r is None:
                    continue
                _exp_icon = "✅" if _r["status"] == "ok" else "❌"
                with st.expander(
                    f"{_exp_icon} {_mod['icon']} {_mod['title']}",
                    expanded=(_r["status"] == "error"),
                ):
                    if _r["status"] == "ok":
                        _wc = len(_r["answer"].split())
                        st.caption(f"{_wc:,} words · {_r['sources_added']} URL source(s) ingested")
                        st.markdown(_r["answer"])
                    else:
                        st.error(f"Module failed: {_r['error']}")
                        if _r.get("notebook_id"):
                            st.caption(f"Notebook ID (may need manual cleanup in NotebookLM): {_r['notebook_id']}")

            _col_clr, _ = st.columns([1, 4])
            with _col_clr:
                if st.button("Clear all research results", key="btn_clear_research"):
                    st.session_state["deep_research_results"] = {}
                    st.rerun()
        else:
            st.caption("No research results yet. Select modules and click **Run Deep Research**.")

    # ---- Full context preview ----
    st.divider()
    with st.expander("Full LLM Context (raw text sent to curriculum generator)"):
        top_n_raw = st.session_state.get("top_n_ctx", 40)
        skills_ctx = build_skills_context(skills_df, top_n_raw) if skills_df is not None else "None"
        acc_ctx = build_accreditation_context(agencies)
        inst_ctx = build_institutional_context(
            st.session_state["consolidated_summary"],
            st.session_state["doc_summaries"],
        )
        rep_ctx = build_reputation_context(st.session_state["reputation_summary"])
        specs_ctx_prev = build_program_specs_context(st.session_state.get("program_specs_docs", []))
        dr_ctx_prev = build_deep_research_context(st.session_state.get("deep_research_results", {}))
        st.text_area("Skills context", skills_ctx, height=120)
        st.text_area("Accreditation context", acc_ctx, height=120)
        st.text_area("Institutional context (consolidated)", inst_ctx, height=120)
        st.text_area("Reputation context", rep_ctx, height=120)
        st.text_area("Program specifications context", specs_ctx_prev, height=120)
        st.text_area("Deep research context", dr_ctx_prev, height=120)


# ============================================================
# TAB 3 — GENERATE
# ============================================================
with tab_generate:
    st.header("Generate Curriculum")

    institution_name = st.session_state.get("_institution", "")
    program_name = st.session_state.get("_program", "")
    program_level = st.session_state.get("_program_level", "Undergraduate")
    course_hours = st.session_state.get("_course_hours")

    if not institution_name or not program_name:
        st.warning("Set institution name and program name in **Sources & Setup** first.")
        st.stop()

    # Model selector for this tab
    _gen_col1, _gen_col2 = st.columns([2, 5])
    with _gen_col1:
        if available_models:
            model_gen = st.selectbox("LLM model (generation)", options=available_models, key="model_gen")
        else:
            model_gen = st.text_input("LLM model (generation)", value="llama3", key="model_gen")

    hours_label = f" — {course_hours} contact hours" if program_level == "Continuous Education" and course_hours else ""
    st.caption(f"Generating for: **{program_name}** ({program_level}{hours_label}) — {institution_name}")
    st.caption(f"Model: `{model_gen}`  |  Language: {language_label}")

    skills_df = st.session_state["skills_df"]
    agencies = st.session_state["agencies"]

    top_n_gen = st.slider("Top N skills to include", 10, 80, 40, key="top_n_gen")
    skills_ctx = build_skills_context(skills_df, top_n_gen) if skills_df is not None else "None loaded."
    acc_ctx = build_accreditation_context(agencies)
    inst_ctx = build_institutional_context(
        st.session_state["consolidated_summary"],
        st.session_state["doc_summaries"],
    )
    rep_ctx = build_reputation_context(st.session_state["reputation_summary"])
    specs_ctx = build_program_specs_context(st.session_state.get("program_specs_docs", []))
    deep_research_ctx = build_deep_research_context(st.session_state.get("deep_research_results", {}))

    scope_labels = list({
        s for a in agencies for s in (
            a["program_scope"] if isinstance(a["program_scope"], list) else [a["program_scope"]]
        )
    })
    program_scope_str = ", ".join(scope_labels) if scope_labels else "general higher education"

    # ---- Overall progress indicator ----
    steps_done = sum([
        bool(st.session_state["learning_outcomes"]),
        bool(st.session_state["course_list"]),
        bool(st.session_state["competency_map"]),
        bool(st.session_state["syllabi"]),
    ])
    step_labels = ["Learning Outcomes", "Course List", "Competency Map", "Syllabi"]
    progress_cols = st.columns(4)
    for idx, (col, label) in enumerate(zip(progress_cols, step_labels)):
        is_done = idx < steps_done or (
            (idx == 0 and st.session_state["learning_outcomes"]) or
            (idx == 1 and st.session_state["course_list"]) or
            (idx == 2 and st.session_state["competency_map"]) or
            (idx == 3 and st.session_state["syllabi"])
        )
        col.metric(
            label=f"Step {idx + 1}",
            value="✅ Done" if is_done else "— Pending",
            delta=label,
            delta_color="off",
        )
    st.progress(steps_done / 4, text=f"{steps_done}/4 steps complete")

    st.divider()

    # --- Step 1: Learning Outcomes ---
    st.subheader("Step 1 — Program Overview & Learning Outcomes")
    if st.button("Generate Learning Outcomes", type="primary", key="btn_outcomes"):
        container = st.empty()
        full_text = ""
        with st.spinner("Generating..."):
            for chunk in generate_learning_outcomes(
                program_name, program_level, program_scope_str,
                skills_ctx, acc_ctx, inst_ctx, language, ollama_url, model_gen,
                course_hours=course_hours,
                reputation_context=rep_ctx,
                program_specs_context=specs_ctx,
                deep_research_context=deep_research_ctx,
            ):
                full_text += chunk
                container.markdown(full_text)
        st.session_state["learning_outcomes"] = full_text
        st.success("Learning outcomes generated.")

    elif st.session_state["learning_outcomes"]:
        with st.expander("Learning outcomes (generated)", expanded=False):
            st.markdown(st.session_state["learning_outcomes"])
        if st.button("Regenerate Learning Outcomes", key="btn_regen_outcomes"):
            st.session_state["learning_outcomes"] = ""
            st.session_state["course_list"] = ""
            st.session_state["competency_map"] = ""
            st.session_state["syllabi"] = {}
            st.rerun()

    st.divider()

    # --- Step 2: Course List ---
    st.subheader("Step 2 — Course List")
    if not st.session_state["learning_outcomes"]:
        st.info("Complete Step 1 first.")
    else:
        if st.button("Generate Course List", type="primary", key="btn_courses"):
            container2 = st.empty()
            full_text2 = ""
            with st.spinner("Generating course list..."):
                for chunk in generate_course_list(
                    program_name, program_level,
                    st.session_state["learning_outcomes"],
                    skills_ctx, acc_ctx, language, ollama_url, model_gen,
                    course_hours=course_hours,
                    program_specs_context=specs_ctx,
                    deep_research_context=deep_research_ctx,
                ):
                    full_text2 += chunk
                    container2.markdown(full_text2)
            st.session_state["course_list"] = full_text2
            st.success("Course list generated.")

        elif st.session_state["course_list"]:
            with st.expander("Course list (generated)", expanded=False):
                st.markdown(st.session_state["course_list"])
            if st.button("Regenerate Course List", key="btn_regen_courses"):
                st.session_state["course_list"] = ""
                st.session_state["competency_map"] = ""
                st.session_state["syllabi"] = {}
                st.rerun()

    st.divider()

    # --- Step 3: Competency Map ---
    st.subheader("Step 3 — Competency Map")
    if not st.session_state["course_list"]:
        st.info("Complete Step 2 first.")
    else:
        if st.button("Generate Competency Map", type="primary", key="btn_map"):
            container3 = st.empty()
            full_text3 = ""
            with st.spinner("Generating competency map..."):
                for chunk in generate_competency_map(
                    program_name,
                    st.session_state["learning_outcomes"],
                    st.session_state["course_list"],
                    language, ollama_url, model_gen,
                ):
                    full_text3 += chunk
                    container3.markdown(full_text3)
            st.session_state["competency_map"] = full_text3
            st.success("Competency map generated.")

        elif st.session_state["competency_map"]:
            st.caption(
                "The competency map table is rendered below. "
                "Cells: **I** = Introduced, **D** = Developed, **A** = Assessed."
            )
            with st.expander("Competency map (generated)", expanded=True):
                st.markdown(st.session_state["competency_map"])
            if st.button("Regenerate Competency Map", key="btn_regen_map"):
                st.session_state["competency_map"] = ""
                st.rerun()

    st.divider()

    # --- Step 4: Individual Syllabi ---
    st.subheader("Step 4 — Individual Course Syllabi")
    if not st.session_state["course_list"]:
        st.info("Complete Step 2 first.")
    else:
        st.caption(
            "Extract course codes and names from the generated list, "
            "select which ones to generate syllabi for, then click Generate."
        )

        course_pattern = re.compile(r"\*\*\[?([A-Z]{2,6}\d{3,4}[A-Z]?)\]?\s+([^\*\n]+)\*\*")
        found_courses = course_pattern.findall(st.session_state["course_list"])

        if not found_courses:
            st.info(
                "Could not auto-detect course codes. "
                "Enter them manually below (one per line, format: CODE Course Name)."
            )
            manual_input = st.text_area(
                "Manual course entries (CODE Course Name)",
                placeholder="CS101 Introduction to Programming\nCS102 Data Structures",
                height=150,
            )
            found_courses = []
            for line in manual_input.splitlines():
                line = line.strip()
                if line:
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        found_courses.append(tuple(parts))
        else:
            st.caption(f"Detected {len(found_courses)} courses from the generated list.")

        if found_courses:
            course_labels = [f"{code} — {name.strip()}" for code, name in found_courses]
            selected_labels = st.multiselect(
                "Select courses to generate syllabi for",
                options=course_labels,
                default=[],
                help="Select individual courses. Each requires one LLM call.",
            )

            if selected_labels:
                est_minutes = len(selected_labels) * 1.5
                st.caption(f"Estimated time: ~{est_minutes:.0f} min for {len(selected_labels)} syllabi.")

            if st.button(
                f"Generate {len(selected_labels)} Syllab{'us' if len(selected_labels)==1 else 'i'}",
                type="primary",
                disabled=not selected_labels,
                key="btn_syllabi",
            ):
                slo_excerpt = st.session_state["learning_outcomes"][:1500]
                skills_short = build_skills_context(skills_df, 20) if skills_df is not None else ""
                prog_bar = st.progress(0, "Starting...")
                syllabi = dict(st.session_state["syllabi"])

                for idx, label in enumerate(selected_labels):
                    code, name = label.split(" — ", 1)
                    prog_bar.progress((idx + 1) / len(selected_labels), f"Generating: {code}...")
                    syl_text = ""
                    syl_container = st.empty()
                    for chunk in generate_syllabus(
                        code, name, program_name, slo_excerpt,
                        skills_short, language, ollama_url, model_gen,
                    ):
                        syl_text += chunk
                        syl_container.markdown(syl_text)
                    syllabi[code] = syl_text
                    syl_container.empty()

                prog_bar.empty()
                st.session_state["syllabi"] = syllabi
                st.success(f"{len(selected_labels)} syllab{'us' if len(selected_labels)==1 else 'i'} generated.")

        if st.session_state["syllabi"]:
            st.subheader("Generated Syllabi")
            for code, content in st.session_state["syllabi"].items():
                with st.expander(f"Syllabus: {code}"):
                    st.markdown(content)


# ============================================================
# TAB 4 — EXPORT
# ============================================================
with tab_export:
    st.header("Export & Save")

    institution_name = st.session_state.get("_institution", "")
    program_name = st.session_state.get("_program", "")
    program_level = st.session_state.get("_program_level", "Undergraduate")

    outcomes = st.session_state["learning_outcomes"]
    courses = st.session_state["course_list"]
    cmap = st.session_state["competency_map"]
    syllabi = st.session_state["syllabi"]

    n_sections = sum(1 for t in [outcomes, courses, cmap] if t.strip())
    n_syllabi = len(syllabi)

    st.markdown(f"**Ready to export:** {n_sections} program section(s) + {n_syllabi} syllabus/syllabi")

    if not institution_name or not program_name:
        st.warning("Set institution and program name in **Sources & Setup** first.")
    elif n_sections == 0:
        st.info("Nothing generated yet — complete at least Step 1 in the Generate tab.")
    else:
        st.divider()

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Save Full Curriculum PDF")
            st.caption(
                "One PDF combining all generated sections and syllabi, "
                "saved to the output folder structure."
            )
            if st.button("Save Full Curriculum PDF", type="primary", key="save_full"):
                with st.spinner("Building PDF..."):
                    sections = {}
                    if outcomes:
                        sections["Program Overview & Learning Outcomes"] = outcomes
                    if courses:
                        sections["Course List"] = courses
                    if cmap:
                        sections["Competency Map"] = cmap

                    try:
                        out_path = save_full_curriculum_pdf(
                            sections=sections,
                            syllabi=syllabi,
                            institution=institution_name,
                            program_name=program_name,
                            program_level=program_level,
                            base_outputs=base_outputs,
                        )
                        st.success(f"Saved to:\n`{out_path}`")
                    except Exception as exc:
                        st.error(f"PDF generation failed: {exc}")

        with col_b:
            st.subheader("Save Individual Section PDFs")
            st.caption("Save each section as a separate PDF file.")
            if st.button("Save Section PDFs", key="save_sections"):
                saved = []
                with st.spinner("Building PDFs..."):
                    section_map = {
                        "01_Learning_Outcomes": outcomes,
                        "02_Course_List": courses,
                        "03_Competency_Map": cmap,
                    }
                    for name, content in section_map.items():
                        if content.strip():
                            try:
                                p = save_section_pdf(
                                    content, name, institution_name,
                                    program_name, program_level, base_outputs,
                                )
                                saved.append(str(p))
                            except Exception as exc:
                                st.warning(f"{name}: {exc}")
                    for code, content in syllabi.items():
                        if content.strip():
                            try:
                                p = save_syllabus_pdf(
                                    code, content, institution_name,
                                    program_name, program_level, base_outputs,
                                )
                                saved.append(str(p))
                            except Exception as exc:
                                st.warning(f"{code}: {exc}")
                if saved:
                    st.success(f"Saved {len(saved)} file(s).")
                    for p in saved:
                        st.caption(f"  `{p}`")

        st.divider()

        # ---- Plain text download ----
        st.subheader("Download as Plain Text / JSON")
        full_md = "\n\n---\n\n".join(filter(None, [outcomes, courses, cmap]))
        if syllabi:
            full_md += "\n\n---\n\n# Course Syllabi\n\n"
            full_md += "\n\n---\n\n".join(syllabi.values())

        safe_prog = program_name.replace(" ", "_")[:40]

        dl_col_md, dl_col_json = st.columns(2)
        with dl_col_md:
            st.download_button(
                label="Download full curriculum as Markdown",
                data=full_md.encode("utf-8"),
                file_name=f"curriculum_{safe_prog}.md",
                mime="text/markdown",
            )
        with dl_col_json:
            _top_n_export = st.session_state.get("top_n_gen", st.session_state.get("top_n_ctx", 40))
            _export_data = build_curriculum_export(
                institution_name=institution_name,
                program_name=program_name,
                program_level=program_level,
                language=language,
                course_hours=st.session_state.get("_course_hours"),
                skills_df=st.session_state["skills_df"],
                top_n=_top_n_export,
                agencies=st.session_state["agencies"],
                institutional_docs=st.session_state["institutional_docs"],
                consolidated_summary=st.session_state["consolidated_summary"],
                reputation_snippets=st.session_state["reputation_snippets"],
                reputation_summary=st.session_state["reputation_summary"],
                program_specs_docs=st.session_state.get("program_specs_docs", []),
                deep_research_results=st.session_state.get("deep_research_results", {}),
                learning_outcomes=outcomes,
                course_list=courses,
                competency_map=cmap,
                syllabi=syllabi,
            )
            st.download_button(
                label="Download curriculum_export.json",
                data=json.dumps(_export_data, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"curriculum_export_{safe_prog}.json",
                mime="application/json",
            )

        st.divider()

        st.subheader("Save JSON to Output Folder")
        st.caption(
            "Saves `curriculum_export.json` alongside the PDFs in the output folder. "
            "This is the machine-readable file for downstream applications."
        )
        if st.button("Save curriculum_export.json", key="save_json"):
            try:
                _json_path = save_curriculum_export(
                    _export_data, institution_name, program_name, base_outputs
                )
                st.success(f"Saved to:\n`{_json_path}`")
            except Exception as exc:
                st.error(f"JSON save failed: {exc}")

        # ---- Output folder info ----
        st.divider()
        st.subheader("Output Folder Structure")
        from datetime import datetime
        year_month = datetime.now().strftime("%Y-%m")
        safe_inst = re.sub(r"[^\w\s-]", "", institution_name).strip().replace(" ", "_")
        safe_prg = re.sub(r"[^\w\s-]", "", program_name).strip().replace(" ", "_")
        example_path = base_outputs / safe_inst / year_month / safe_prg
        st.code(str(example_path))
        st.caption("Syllabi are saved in a `syllabi/` subfolder within the program directory.")

