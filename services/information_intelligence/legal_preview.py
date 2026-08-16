"""One-shot live preview for confirmed official Ozon legal sources."""

from __future__ import annotations

import json

from .fetch import fetch_once
from .legal import LegalDocumentError, canonicalize_legal, structural_preview
from .legal_sources import LEGAL_SOURCES


def run() -> list[dict]:
    results: list[dict] = []
    for source in LEGAL_SOURCES:
        if not source.canonical_url:
            results.append({"source_id": source.source_id, "status": "NEEDS_SOURCE_CONFIRMATION", "persisted": False})
            continue
        fetched = fetch_once(source)
        summary = fetched.summary()
        summary["persisted"] = False
        if fetched.status == "SUCCESS" and fetched.body is not None:
            try:
                document = canonicalize_legal(fetched.body, content_type=fetched.content_type)
                summary.update({
                    "status": "BASELINE_PREVIEW_READY",
                    "canonical_sha256": document.canonical_sha256,
                    **structural_preview(document),
                })
            except LegalDocumentError as error:
                summary.update({"status": "PARSE_FAILED", "error": str(error)})
        results.append(summary)
    return results


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
