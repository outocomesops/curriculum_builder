"""
Curriculum Builder
==================
Streamlit app that synthesises job market demand, accreditation quality standards,
and institutional documentation into a fully generated academic curriculum.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import OLLAMA_DEFAULT_URL, OUTPUTS_DIR, SUPPORTED_LANGUAGES, PROGRAM_LEVELS
from loaders.job_loader import get_available_queries, load_skills_from_db, load_skills_from_csv
from loaders.quality_loader import get_all_scopes, load_agencies_with_quality
from loaders.doc_loader import load_institutional_docs
from generator.doc_summarizer import batch_summarize
from generator.prompt_builder import (
    build_skills_context,
    build_accreditation_context,
    build_institutional_context,
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
)

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
    st.caption("Job Market × Accreditation × Institution")
    st.divider()

    st.subheader("Ollama Settings")
    ollama_url = st.text_input(
        "Ollama URL",
        value=OLLAMA_DEFAULT_URL,
        help="URL of the local Ollama instance (default: http://localhost:11434)",
    )

    available_models = list_ollama_models(ollama_url)
    if available_models:
        model = st.selectbox("Model", options=available_models)
        st.caption(f"{len(available_models)} model(s) found.")
    else:
        model = st.text_input(
            "Model name",
            value="llama3",
            help="Ollama is not reachable or has no models pulled. Enter a model name manually.",
        )
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


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_sources, tab_context, tab_generate, tab_export = st.tabs([
    "1  Sources & Setup",
    "2  Context Preview",
    "3  Generate",
    "4  Export",
])


# ============================================================
# TAB 1 — SOURCES & SETUP
# ============================================================
with tab_sources:
    st.header("Sources & Program Setup")

    col_left, col_right = st.columns(2)

    # ---- Institution ----
    with col_left:
        st.subheader("Institution")
        institution_name = st.text_input("Institution name", placeholder="e.g. Universidad Nacional")
        program_name = st.text_input("Program name", placeholder="e.g. Bachelor of Software Engineering")
        program_level = st.selectbox("Program level", options=PROGRAM_LEVELS)

        course_hours: int | None = None
        if program_level == "Continuous Education":
            course_hours = st.number_input(
                "Total course hours",
                min_value=8,
                max_value=1000,
                value=40,
                step=8,
                help="Total contact/instructional hours for the continuing education program.",
            )

    # ---- Job market data ----
    with col_right:
        st.subheader("Job Market Data")
        job_source = st.radio("Input type", ["SQLite DB (jobs.db)", "CSV export"], horizontal=True)

        if job_source == "SQLite DB (jobs.db)":
            db_path = st.text_input(
                "Path to jobs.db",
                placeholder=r"C:\Users\...\job_market_search\jobs.db",
            )
            if db_path:
                queries = get_available_queries(db_path)
                if queries:
                    selected_queries = st.multiselect(
                        "Filter by job title queries",
                        options=queries,
                        default=queries,
                        help="Select which job title queries to include in the skill analysis.",
                    )
                else:
                    selected_queries = []
                    st.warning("No queries found in this database.")
            else:
                db_path = ""
                selected_queries = []

            if st.button("Load Skills from DB", disabled=not db_path):
                with st.spinner("Loading skills..."):
                    df = load_skills_from_db(db_path, selected_queries or None)
                if df.empty:
                    st.error("No skills found. Check the path and that analysis has been run.")
                else:
                    st.session_state["skills_df"] = df
                    st.success(f"Loaded {len(df)} unique skills.")

        else:
            csv_path = st.text_input("Path to skills CSV", placeholder=r"C:\Users\...\skills_*.csv")
            if st.button("Load Skills from CSV", disabled=not csv_path):
                with st.spinner("Loading..."):
                    df = load_skills_from_csv(csv_path)
                if df.empty:
                    st.error("Could not load CSV.")
                else:
                    st.session_state["skills_df"] = df
                    st.success(f"Loaded {len(df)} unique skills.")

    st.divider()

    col_qa, col_inst = st.columns(2)

    # ---- Quality standards ----
    with col_qa:
        st.subheader("Quality Standards")
        qa_path = st.text_input(
            "Path to quality_assurance/sources/",
            placeholder=r"C:\Users\...\quality_assurance\sources",
        )

        if qa_path:
            scopes = get_all_scopes(qa_path)
            if scopes:
                selected_scopes = st.multiselect(
                    "Program scope filter",
                    options=scopes,
                    help="Filter agencies to those covering your program type.",
                )
                agencies_preview = load_agencies_with_quality(qa_path, selected_scopes or None)

                if agencies_preview:
                    agency_options = {
                        f"{a['agency_name']} ({a['jurisdiction'].upper()})": a
                        for a in agencies_preview
                    }
                    selected_agency_labels = st.multiselect(
                        f"Select agencies ({len(agencies_preview)} available)",
                        options=list(agency_options.keys()),
                        default=list(agency_options.keys()),
                    )
                else:
                    selected_agency_labels = []
                    st.info("No agencies match the selected scopes.")
            else:
                selected_scopes = []
                selected_agency_labels = []
                st.warning("Could not read catalog. Check the path.")

        if st.button("Load Quality Standards", disabled=not qa_path):
            with st.spinner("Loading agency data..."):
                all_agencies = load_agencies_with_quality(qa_path, selected_scopes or None)
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

    # ---- Institutional docs ----
    with col_inst:
        st.subheader("Institutional Documentation")
        docs_folder = st.text_input(
            "Path to institutional documents folder",
            placeholder=r"C:\Users\...\institution_docs",
            help="Folder with PDFs, DOCX, or TXT files (policies, mission, strategic plan, etc.)",
        )

        if st.button("Load Documents", disabled=not docs_folder):
            with st.spinner("Scanning folder..."):
                docs = load_institutional_docs(docs_folder)
            if not docs:
                st.warning(
                    f"No files found in `{docs_folder}`. "
                    "Check the path and make sure it contains PDF, DOCX, or TXT files."
                )
            else:
                ok = [d for d in docs if not d["error"] and d["char_count"] > 0]
                empty = [d for d in docs if not d["error"] and d["char_count"] == 0]
                errors = [d for d in docs if d["error"]]

                st.session_state["institutional_docs"] = ok
                st.session_state["doc_summaries"] = []

                if ok:
                    st.success(f"Loaded {len(ok)} document(s) with text.")
                    for d in ok:
                        st.caption(f"  ✅ {d['filename']}  ({d['char_count']:,} chars)")
                if empty:
                    st.warning(f"{len(empty)} file(s) found but contained no extractable text (may be scanned images):")
                    for d in empty:
                        st.caption(f"  ⚠️ {d['filename']}")
                if errors:
                    st.error(f"{len(errors)} file(s) failed to read:")
                    for d in errors:
                        st.caption(f"  ❌ {d['filename']} — {d['error']}")

    # ---- Status summary ----
    st.divider()
    st.subheader("Setup Status")
    c1, c2, c3 = st.columns(3)
    skills_df: pd.DataFrame | None = st.session_state["skills_df"]
    c1.metric("Skills loaded", len(skills_df) if skills_df is not None and not skills_df.empty else 0)
    c2.metric("Agencies loaded", len(st.session_state["agencies"]))
    c3.metric("Documents loaded", len(st.session_state["institutional_docs"]))

    st.session_state["_institution"] = institution_name
    st.session_state["_program"] = program_name
    st.session_state["_program_level"] = program_level
    st.session_state["_course_hours"] = course_hours


# ============================================================
# TAB 2 — CONTEXT PREVIEW
# ============================================================
with tab_context:
    st.header("Context Preview")
    st.caption("Review what will be fed to the LLM before generating.")

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
    with st.expander("Institutional Documents", expanded=bool(docs)):
        if docs:
            st.write(f"{len(docs)} document(s) loaded:")
            for d in docs:
                st.markdown(f"- **{d['filename']}** ({d['char_count']:,} chars)")

            st.divider()
            if st.button("Summarise Documents with LLM", type="primary"):
                summaries = []
                prog = st.progress(0, text="Starting...")
                for i, doc in enumerate(docs):
                    prog.progress((i + 1) / len(docs), text=f"Summarising: {doc['filename']}")
                    from generator.doc_summarizer import summarize_doc
                    result = summarize_doc(doc["text"], doc["filename"], ollama_url, model)
                    summaries.append(result)
                prog.empty()
                st.session_state["doc_summaries"] = summaries
                useful = sum(1 for s in summaries if s["has_content"])
                st.success(f"Done. {useful}/{len(docs)} documents contained usable content.")

            if st.session_state["doc_summaries"]:
                st.divider()
                st.subheader("Extracted Summaries")
                for s in st.session_state["doc_summaries"]:
                    icon = "✅" if s["has_content"] else "⚠️"
                    with st.expander(f"{icon} {s['filename']}"):
                        if s["has_content"]:
                            st.markdown(s["summary"])
                        elif s.get("error"):
                            st.error(f"Error: {s['error']}")
                        else:
                            st.warning("No relevant institutional content found in this document.")
        else:
            st.info("No documents loaded yet.")

    # ---- Full context preview ----
    with st.expander("Full LLM Context (raw text)"):
        top_n_raw = st.session_state.get("top_n_ctx", 40)
        skills_ctx = build_skills_context(skills_df, top_n_raw) if skills_df is not None else "None"
        acc_ctx = build_accreditation_context(agencies)
        inst_ctx = build_institutional_context(st.session_state["doc_summaries"])
        st.text_area("Skills context", skills_ctx, height=150)
        st.text_area("Accreditation context", acc_ctx, height=150)
        st.text_area("Institutional context", inst_ctx, height=150)


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

    hours_label = f" — {course_hours} contact hours" if program_level == "Continuous Education" and course_hours else ""
    st.caption(f"Generating for: **{program_name}** ({program_level}{hours_label}) — {institution_name}")
    st.caption(f"Model: `{model}`  |  Language: {language_label}")

    skills_df = st.session_state["skills_df"]
    agencies = st.session_state["agencies"]

    top_n_gen = st.slider("Top N skills to include", 10, 80, 40, key="top_n_gen")
    skills_ctx = build_skills_context(skills_df, top_n_gen) if skills_df is not None else "None loaded."
    acc_ctx = build_accreditation_context(agencies)
    inst_ctx = build_institutional_context(st.session_state["doc_summaries"])

    # ---- Program scope label ----
    scope_labels = list({
        s for a in agencies for s in (
            a["program_scope"] if isinstance(a["program_scope"], list) else [a["program_scope"]]
        )
    })
    program_scope_str = ", ".join(scope_labels) if scope_labels else "general higher education"

    st.divider()

    # --- Step 1: Learning Outcomes ---
    st.subheader("Step 1 — Program Overview & Learning Outcomes")
    if st.button("Generate Learning Outcomes", type="primary", key="btn_outcomes"):
        container = st.empty()
        full_text = ""
        with st.spinner("Generating..."):
            for chunk in generate_learning_outcomes(
                program_name, program_level, program_scope_str,
                skills_ctx, acc_ctx, inst_ctx, language, ollama_url, model,
                course_hours=course_hours,
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
                    skills_ctx, acc_ctx, language, ollama_url, model,
                    course_hours=course_hours,
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
                    language, ollama_url, model,
                ):
                    full_text3 += chunk
                    container3.markdown(full_text3)
            st.session_state["competency_map"] = full_text3
            st.success("Competency map generated.")

        elif st.session_state["competency_map"]:
            with st.expander("Competency map (generated)", expanded=False):
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

        # Parse course entries from course_list (look for **[CODE] Name** patterns)
        import re
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
                        skills_short, language, ollama_url, model,
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
        st.subheader("Download as Plain Text")
        full_md = "\n\n---\n\n".join(filter(None, [outcomes, courses, cmap]))
        if syllabi:
            full_md += "\n\n---\n\n# Course Syllabi\n\n"
            full_md += "\n\n---\n\n".join(syllabi.values())

        safe_prog = program_name.replace(" ", "_")[:40]
        st.download_button(
            label="Download full curriculum as Markdown",
            data=full_md.encode("utf-8"),
            file_name=f"curriculum_{safe_prog}.md",
            mime="text/markdown",
        )

        # ---- Output folder info ----
        st.divider()
        st.subheader("Output Folder Structure")
        from datetime import datetime
        import re
        year_month = datetime.now().strftime("%Y-%m")
        safe_inst = re.sub(r"[^\w\s-]", "", institution_name).strip().replace(" ", "_")
        safe_prg = re.sub(r"[^\w\s-]", "", program_name).strip().replace(" ", "_")
        example_path = base_outputs / safe_inst / year_month / safe_prg
        st.code(str(example_path))
        st.caption("Syllabi are saved in a `syllabi/` subfolder within the program directory.")
