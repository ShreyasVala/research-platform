# tools/document_tool.py
# Reads files from the uploads/ folder and returns their text.
# Supports PDF, TXT, MD, CSV.
# All processing is local — zero cost, no API needed.

from pathlib import Path
from config import get_settings

settings = get_settings()


async def read_document(filename: str, max_chars: int = 8000) -> dict:
    """
    Reads a file and returns its text content.
    max_chars prevents sending huge files that overflow the LLM context window.
    """
    path = Path(settings.uploads_dir) / filename

    if not path.exists():
        return {"error": f"File not found: {filename}"}

    try:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            text = _read_pdf(path)
        else:
            # Plain text for .txt, .md, .csv
            text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    truncated = len(text) > max_chars
    return {
        "filename": filename,
        "content": text[:max_chars],
        "truncated": truncated,      # tells the agent if content was cut
        "char_count": min(len(text), max_chars),
    }


def _read_pdf(path: Path) -> str:
    """Extracts all text from a PDF using PyMuPDF (installed as 'fitz')."""
    import fitz  # PyMuPDF
    doc = fitz.open(str(path))
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n\n".join(pages)