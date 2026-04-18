from pathlib import Path

OLLAMA_DEFAULT_URL = "http://localhost:11434"
OUTPUTS_DIR = Path(__file__).parent / "outputs"

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
