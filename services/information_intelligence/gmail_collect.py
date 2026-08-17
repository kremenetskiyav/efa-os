"""Manual read-only Gmail collection command; it never persists data."""

from __future__ import annotations

import argparse
import json

from .gmail_readonly import collect_recent, load_token


def main() -> None:
    parser = argparse.ArgumentParser(description="Read recent Gmail messages without mailbox or database writes")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(collect_recent(load_token(), args.days), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
