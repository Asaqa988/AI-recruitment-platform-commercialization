"""CV text extraction. Uploads are parsed on the server; the CV is never fetched from a URL
(a public service that fetches user-supplied URLs can be pointed at internal addresses)."""
import io
import re
import zipfile

MAX_TEXT = 30_000
MAX_PDF_PAGES = 20


class CVError(ValueError):
    pass


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    if not data.startswith(b"%PDF"):
        raise CVError("This file is not a valid PDF")
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise CVError("This PDF is password protected")
    return "\n".join((p.extract_text() or "") for p in reader.pages[:MAX_PDF_PAGES])


def _docx(data: bytes) -> str:
    from docx import Document

    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise CVError("This file is not a valid DOCX")
    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts)


def extract_text(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            text = _pdf(data)
        elif name.endswith(".docx"):
            text = _docx(data)
        elif name.endswith((".txt", ".md")):
            text = data.decode("utf-8", errors="replace")
        else:
            raise CVError("Upload a PDF, DOCX or TXT file, or paste the CV text")
    except CVError:
        raise
    except Exception as exc:  # noqa: BLE001 - any parser failure is a bad file from the user's point of view
        raise CVError("Could not read this file. Paste the CV text instead") from exc
    text = _clean(text)
    if len(text) < 40:
        raise CVError("No readable text found (scanned image?). Paste the CV text instead")
    return text[:MAX_TEXT]
