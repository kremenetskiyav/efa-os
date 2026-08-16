"""Local read-only preview for public official OpenAPI sources."""

from __future__ import annotations

import json

from .fetch import fetch_once
from .openapi import OpenAPIContractError, canonicalize_openapi, structural_contract
from .sources import SOURCES


def preview_sources() -> list[dict]:
    results = []
    for source in SOURCES:
        fetched = fetch_once(source)
        summary = fetched.summary()
        if fetched.body is not None:
            try:
                canonical = canonicalize_openapi(fetched.body)
                structural = structural_contract(canonical.document)
                summary.update({
                    "status": "BASELINE_CREATED",
                    "canonical_sha256": canonical.canonical_sha256,
                    "spec_version": structural["spec_version"],
                    "api_version": structural["api_version"],
                    "paths_count": len(structural["paths"]),
                })
            except OpenAPIContractError as error:
                summary.update({"status": "PARSE_FAILED", "error": str(error)})
        results.append(summary)
    return results


if __name__ == "__main__":
    print(json.dumps(preview_sources(), ensure_ascii=False, indent=2))
