"""Command entry point for the Snapshot Worker v1 skeleton."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from config import ConfigurationError, load_database_config
from database import DatabaseConnectionError, check_connection


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the intentionally small command-line contract for the skeleton."""

    parser = argparse.ArgumentParser(description="Snapshot Worker v1 skeleton")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate configuration and PostgreSQL connectivity without SQL or writes",
    )
    return parser.parse_args(argv)


def run_dry_run() -> int:
    """Report configuration and connection status without business queries."""

    print("[CONFIG] Checking environment configuration")
    try:
        config = load_database_config()
    except ConfigurationError as error:
        print(f"[CONFIG] ERROR: {error}")
        print("[DATABASE] SKIPPED: configuration is invalid")
        return 2

    print("[CONFIG] OK")
    print("[DATABASE] Checking PostgreSQL connection (no SQL queries)")
    try:
        check_connection(config)
    except DatabaseConnectionError as error:
        print(f"[DATABASE] ERROR: {error}")
        return 3

    print("[DATABASE] OK")
    print("Snapshot Worker v1 skeleton ready")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run only the supported skeleton behaviour."""

    args = parse_args(argv)
    if args.dry_run:
        return run_dry_run()

    print("Snapshot Worker v1 skeleton only. Use --dry-run to validate readiness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
