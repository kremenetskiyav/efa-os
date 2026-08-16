"""Preview operator-supplied official Seller News evidence without persistence."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .news import NewsEvidence, canonicalize_news


def preview_news_file(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("news fallback manifest must be a JSON array")
    articles = []
    for item in value:
        evidence = NewsEvidence(
            canonical_url=item["canonical_url"],
            stable_id=item.get("stable_id"),
            title=item["title"],
            published_at=item["published_at"],
            updated_at=item.get("updated_at"),
            category=item.get("category"),
            body=item["body"],
            content_type=item.get("content_type", "text/html"),
            official_links=tuple(item.get("official_links", ())),
        )
        article = canonicalize_news(evidence)
        articles.append({
            "identity": article.identity,
            "canonical_url": article.canonical_url,
            "title": article.title,
            "published_at": article.published_at,
            "updated_at": article.updated_at,
            "raw_sha256": article.raw_sha256,
            "canonical_sha256": article.canonical_sha256,
            "domains": article.domains,
            "watch_concepts": article.watch_concepts,
            "effective_date": article.effective_date,
            "effective_context": article.effective_context,
        })
    return {"status": "MANUAL_BOOTSTRAP_PREVIEW", "persisted": False, "articles": articles}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(preview_news_file(args.file), ensure_ascii=False, indent=2))
