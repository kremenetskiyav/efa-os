"""Validate an operator-supplied official snapshot without persisting it."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from .openapi import canonicalize_openapi, structural_contract
from .sources import SOURCES


def preview_local_snapshot(source_id: str, source_file: Path) -> dict:
    source = next((item for item in SOURCES if item.source_id == source_id), None)
    if source is None:
        raise ValueError("unknown source_id")
    file_bytes = source_file.read_bytes()
    raw = gzip.decompress(file_bytes) if source_file.suffix.lower() == ".gz" else file_bytes
    canonical = canonicalize_openapi(raw)
    structure = structural_contract(canonical.document)
    return {
        "source_id": source.source_id,
        "canonical_url": source.canonical_url,
        "status": "BASELINE_CREATED",
        "raw_bytes": len(raw),
        "raw_sha256": canonical.raw_sha256,
        "canonical_sha256": canonical.canonical_sha256,
        "spec_version": structure["spec_version"],
        "api_version": structure["api_version"],
        "paths_count": len(structure["paths"]),
        "evidence_reference": str(source_file.resolve()),
        "persisted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preview an approved official OpenAPI file")
    parser.add_argument("--source-id", required=True, choices=[item.source_id for item in SOURCES])
    parser.add_argument("--file", required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(preview_local_snapshot(arguments.source_id, arguments.file), ensure_ascii=False, indent=2))
