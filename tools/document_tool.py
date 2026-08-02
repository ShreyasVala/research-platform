# tools/document_tool.py
# Reads files from local or S3 upload storage and returns their text.
# Supports PDF, TXT, MD, CSV.

import asyncio
from pathlib import Path
from tools.storage import read_upload_bytes, safe_filename


async def read_document(filename: str, max_chars: int = 8000) -> dict:
    """
    Reads a file and returns its text content.
    max_chars prevents sending huge files that overflow the LLM context window.
    """
    name = safe_filename(filename)
    if name is None:
        return {"error": f"Invalid filename: {filename}"}

    content, error = await asyncio.to_thread(read_upload_bytes, name)
    if error:
        return {"error": error}

    try:
        suffix = Path(name).suffix.lower()
        if suffix == ".pdf":
            text = _read_pdf_bytes(content)
        else:
            # Plain text for .txt, .md, .csv
            text = content.decode("utf-8", errors="replace")
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    truncated = len(text) > max_chars
    return {
        "filename": name,
        "content": text[:max_chars],
        "truncated": truncated,      # tells the agent if content was cut
        "char_count": min(len(text), max_chars),
    }


def _read_pdf_bytes(content: bytes) -> str:
    """Extracts text from PDF bytes stored locally or in S3."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=content, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n\n".join(pages)
