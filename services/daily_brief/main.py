"""CLI entry point: python -m services.daily_brief.main [--date YYYY-MM-DD]."""
from __future__ import annotations

import argparse
import json
from datetime import date

from .brief import build_brief, last_completed_business_date
from .config import ConfigurationError, load_database_config
from .database import DatabaseError, fetch_brief_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Daily Commercial Brief")
    parser.add_argument("--date", type=date.fromisoformat, default=None, help="Europe/Moscow business date (YYYY-MM-DD)")
    parser.add_argument("--table", action="store_true", help="Print compact human-readable offer table")
    args = parser.parse_args()
    business_date = args.date or last_completed_business_date()
    try:
        brief = build_brief(fetch_brief_sources(load_database_config(), business_date), business_date)
    except (ConfigurationError, DatabaseError) as error:
        print(f"ERROR: {error}")
        return 2
    if args.table:
        print("offer_id | ordered_units | delivered_units | returned_units | ordered_revenue | profit_before_tax | margin | boost | promotion | cpc_spend | attention")
        for item in brief["offers"]:
            active = item["promotions"]["participating"]
            boost = active[0]["current_boost"] if active else None
            promotion = active[0]["action_title"] if active else None
            spend = sum((float(entry["spend"]) for entry in item["advertising"]["cpc"]), 0) if item["advertising"]["cpc"] else None
            print(" | ".join(str(value) if value is not None else "NULL" for value in (item["offer_id"], item["demand"]["ordered_units"], item["fulfilment"]["delivered_units"], item["fulfilment"]["returned_units"], item["demand"]["ordered_revenue"], item["economics"]["profit_before_tax"], item["economics"]["confirmed_margin_percent"], boost, promotion, spend, item["attention"]["level"])))
        print("summary: " + json.dumps(brief["summary"], ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(brief, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
