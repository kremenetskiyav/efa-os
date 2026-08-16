"""Validate and preview an operator-supplied official legal document."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from .legal import canonicalize_legal, canonicalize_legal_pdf, structural_preview
from .legal_sources import LEGAL_SOURCES


def preview_legal_snapshot(source_id: str, source_file: Path) -> dict:
    source = next((item for item in LEGAL_SOURCES if item.source_id == source_id), None)
    if source is None:
        raise ValueError("unknown legal source_id")
    file_bytes = source_file.read_bytes()
    compressed = source_file.suffix.lower() == ".gz"
    raw = gzip.decompress(file_bytes) if compressed else file_bytes
    inner_name = source_file.stem if compressed else source_file.name
    extraction = None
    if inner_name.lower().endswith(".pdf"):
        document, extraction = canonicalize_legal_pdf(raw)
    else:
        document = canonicalize_legal(raw, filename=inner_name)
    structure = structural_preview(document)
    result = {
        "source_id": source.source_id,
        "canonical_url": source.canonical_url,
        "status": "BASELINE_PREVIEW_READY",
        "raw_bytes": len(raw),
        "raw_sha256": document.raw_sha256,
        "canonical_sha256": document.canonical_sha256,
        "unit_count": structure["unit_count"],
        "watch_concepts": structure["watch_concepts"],
        "watch_matches": structure["watch_matches"],
        "numeric_facts": structure["numeric_facts"],
        "evidence_reference": str(source_file.resolve()),
        "persisted": False,
    }
    if extraction is not None:
        result["pdf_extraction"] = {
            "page_count": extraction.page_count,
            "text_extractable": extraction.nonempty_pages == extraction.page_count,
            "nonempty_pages": extraction.nonempty_pages,
            "extracted_text_bytes": extraction.text_bytes,
            "metadata": extraction.metadata,
            "table_units_detected": sum(unit.kind == "table_row" for unit in document.units),
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preview an approved official Ozon legal file")
    parser.add_argument("--source-id", required=True, choices=[item.source_id for item in LEGAL_SOURCES])
    parser.add_argument("--file", required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(preview_legal_snapshot(arguments.source_id, arguments.file), ensure_ascii=False, indent=2))
