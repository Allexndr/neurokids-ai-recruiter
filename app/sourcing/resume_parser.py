from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def extract_text_from_bytes(data: bytes, filename: str = "") -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:4] == b"%PDF":
        return _pdf_text(data)
    if name.endswith(".docx") or data[:2] == b"PK":
        return _docx_text(data)
    try:
        return data.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n".join(parts).strip()
    except Exception as e:
        logger.warning("PDF parse error: %s", e)
        return ""


def _docx_text(data: bytes) -> str:
    try:
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text).strip()
    except Exception as e:
        logger.warning("DOCX parse error: %s", e)
        return ""
