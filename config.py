from pathlib import Path

OLLAMA_DEFAULT_URL = "http://localhost:11434"
OUTPUTS_DIR = Path(__file__).parent / "outputs"

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
