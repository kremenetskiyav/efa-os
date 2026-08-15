"""Create local, non-delivery previews from the verified Daily Brief payload."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .brief import build_brief, last_completed_business_date
from .config import load_database_config
from .database import fetch_brief_sources
from .renderers import render_email_html, render_pdf, render_telegram_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    business_date = args.date or last_completed_business_date()
    payload = build_brief(fetch_brief_sources(load_database_config(), business_date), business_date)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"ozon-daily-commercial-brief-{business_date.isoformat()}"
    pdf = render_pdf(payload, args.output_dir / f"{stem}.pdf")
    html = args.output_dir / f"{stem}.html"
    telegram = args.output_dir / f"{stem}-telegram.txt"
    html.write_text(render_email_html(payload), encoding="utf-8")
    telegram.write_text(render_telegram_text(payload), encoding="utf-8")
    print(json.dumps({"pdf": str(pdf), "html": str(html), "telegram": str(telegram),
                      "business_date": payload["business_date"], "summary": payload["summary"],
                      "latest_confirmed_economics": payload["latest_confirmed_economics"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
