"""Offline evidence normaliser; API execution stays inside approved n8n nodes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .checker import build_snapshot, compare_snapshots, write_snapshot

DEFAULT_EVIDENCE_DIR = Path.home() / ".efa-os" / "evidence" / "premium_exit"


def main() -> None:
    parser = argparse.ArgumentParser(description="Premium exit baseline evidence normaliser")
    parser.add_argument("phase", choices=("BEFORE", "AFTER", "COMPARE"))
    parser.add_argument("--input", type=Path, help="Sanitised n8n response summary JSON")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    if args.phase == "COMPARE":
        before = json.loads((args.evidence_dir / "before.json").read_text(encoding="utf-8"))
        after = json.loads((args.evidence_dir / "after.json").read_text(encoding="utf-8"))
        target = args.evidence_dir / "comparison.json"
        target.write_text(json.dumps(compare_snapshots(before, after), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(target)
        return
    if args.input is None:
        raise SystemExit("--input is required for BEFORE or AFTER")
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    print(write_snapshot(build_snapshot(args.phase, raw["checks"], raw.get("checked_at")), args.evidence_dir))


if __name__ == "__main__":
    main()
