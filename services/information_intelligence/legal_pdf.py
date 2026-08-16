"""Text-layer extraction for operator-supplied legal PDFs; OCR is out of scope."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

from .legal import LegalDocumentError


@dataclass(frozen=True)
class PDFExtraction:
    page_count: int
    text: str
    text_bytes: int
    metadata: dict[str, str]
    nonempty_pages: int


def extract_pdf_text(raw: bytes) -> PDFExtraction:
    if not raw.startswith(b"%PDF-"):
        raise LegalDocumentError("source is not a PDF")
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(raw))
    except ModuleNotFoundError as error:
        raise LegalDocumentError("PDF extraction dependency is unavailable") from error
    except Exception as error:
        raise LegalDocumentError("PDF cannot be read") from error
    if reader.is_encrypted:
        raise LegalDocumentError("encrypted PDF is not supported for deterministic bootstrap")
    try:
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as error:
        raise LegalDocumentError("PDF text layer cannot be extracted") from error
    text = "\n\f\n".join(pages)
    if not text.strip():
        raise LegalDocumentError("PDF has no usable text layer; OCR is not enabled")
    metadata = {
        str(key): str(value)
        for key, value in (reader.metadata or {}).items()
        if key in {"/Title", "/Author", "/CreationDate", "/ModDate", "/Producer"}
    }
    return PDFExtraction(
        page_count=len(pages),
        text=text,
        text_bytes=len(text.encode("utf-8")),
        metadata=metadata,
        nonempty_pages=sum(bool(page.strip()) for page in pages),
    )
