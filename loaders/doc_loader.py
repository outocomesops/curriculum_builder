from pathlib import Path

_SUPPORTED = {".pdf", ".txt", ".docx", ".doc"}


def _extract_pdf(path: Path) -> tuple[str, str | None]:
    """Returns (text, error_message). error_message is None on success."""
    try:
        import pdfplumber
    except ImportError:
        return "", "pdfplumber not installed — run: pip install pdfplumber"
    try:
        with pdfplumber.open(str(path)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages[:25])
        return text, None
    except Exception as exc:
        return "", str(exc)


def _extract_docx(path: Path) -> tuple[str, str | None]:
    try:
        import docx
    except ImportError:
        return "", "python-docx not installed — run: pip install python-docx"
    try:
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs), None
    except Exception as exc:
        return "", str(exc)


def extract_text_from_file(path: Path) -> tuple[str, str | None]:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        try:
            return path.read_text(encoding="utf-8", errors="ignore"), None
        except Exception as exc:
            return "", str(exc)
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix in (".docx", ".doc"):
        return _extract_docx(path)
    return "", f"Unsupported file type: {suffix}"


def load_institutional_docs(folder_path: str) -> list[dict]:
    """
    Recursively scan a folder and return all found documents as
    list of {filename, path, text, char_count, error}.
    Files with extraction errors are included with error set and text="".
    """
    folder = Path(folder_path)
    if not folder.exists():
        return []

    docs = []
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() in _SUPPORTED and path.is_file():
            text, error = extract_text_from_file(path)
            docs.append({
                "filename": path.name,
                "path": str(path),
                "text": text,
                "char_count": len(text),
                "error": error,
            })
    return docs
