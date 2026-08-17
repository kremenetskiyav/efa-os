"""Failure-classified, read-only polling entry point for the Gmail adapter."""

from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError

from .gmail_persistence import persist_collection
from .gmail_readonly import load_token, read_recent_messages


def run(days: int) -> dict:
    try:
        messages = read_recent_messages(load_token(), days)
    except HTTPError as error:
        return {"status": "AUTH_FAILED" if error.code in {401, 403} else "GMAIL_API_FAILED"}
    except (URLError, TimeoutError, OSError):
        return {"status": "GMAIL_API_FAILED"}
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return {"status": "PARSE_FAILED"}
    try:
        persisted = persist_collection(messages)
    except Exception:
        return {"status": "DB_FAILED"}
    return {
        "status": persisted.get("status", "SUCCESS_ZERO" if not persisted.get("events_created") else "SUCCESS"),
        "candidate_message_count": len(messages),
        "confirmed_ozon_message_count": sum(item.confirmed_ozon for item in messages),
        **persisted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only hourly Ozon Gmail polling")
    parser.add_argument("--days", type=int, default=2)
    args = parser.parse_args()
    result = run(args.days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] in {"AUTH_FAILED", "GMAIL_API_FAILED", "PARSE_FAILED", "DB_FAILED"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
