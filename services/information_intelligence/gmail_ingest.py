"""One manual Gmail read followed by optional Information Intelligence persistence."""

from __future__ import annotations

import argparse
import json

from .gmail_persistence import persist_collection
from .gmail_readonly import load_token, read_recent_messages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    messages = read_recent_messages(load_token(), args.days)
    first = persist_collection(messages)
    print(json.dumps({"candidate_message_count": len(messages), "confirmed_ozon_message_count": sum(x.confirmed_ozon for x in messages), "persistence": first}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
