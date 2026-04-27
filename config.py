from pathlib import Path

OLLAMA_DEFAULT_URL = "http://localhost:11434"
OUTPUTS_DIR = Path(__file__).parent / "outputs"

# Bloom's Revised Taxonomy (Anderson & Krathwohl, 2001)
BLOOM_LEVEL_ORDER = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
BLOOM_LEVEL_COLORS = {
    "remember": "#6B7280",
    "understand": "#3B82F6",
    "apply": "#10B981",
    "analyze": "#F59E0B",
    "evaluate": "#EF4444",
    "create": "#8B5CF6",
}
OUTCOME_TYPE_LABELS = {
    "PEO": "Program Educational Objective",
    "SLO": "Student Learning Outcome",
    "course_obj": "Course Objective",
}

_DATA_DIR = Path(__file__).parent / "data"
BLOOM_VERBS_FILE = _DATA_DIR / "bloom_verbs.json"
WEAK_VERBS_FILE = _DATA_DIR / "weak_verbs.json"

# Sibling-project paths — fixed, no user input required
_ROOT = Path(__file__).parent.parent
JOB_MARKET_DB = _ROOT / "job_market_search" / "jobs.db"
QUALITY_SOURCES_DIR = _ROOT / "quality_assurance" / "sources"

# Default folder for downloaded / local institutional documents
INSTITUTIONAL_DOCS_DIR = Path(__file__).parent / "institutional_docs"

# Shared institutions folder — cached summaries stored here per institution
INSTITUTIONS_DIR = _ROOT / "outcomesops_institutions"

SUPPORTED_LANGUAGES = {
    "English": "English",
    "Spanish (Español)": "Spanish",
    "Portuguese (Português)": "Portuguese",
    "French (Français)": "French",
}

PROGRAM_LEVELS = [
    "Undergraduate",
    "Graduate (Master's)",
    "Graduate (Doctoral)",
    "Postgraduate Diploma",
    "Technical/Vocational",
    "Continuous Education",
]
