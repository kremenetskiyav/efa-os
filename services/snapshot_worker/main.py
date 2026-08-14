"""Command entry point for read-only Snapshot Worker v1.1 dry-run."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from config import ConfigurationError, load_batch_size, load_database_config
from database import (
    DatabaseConnectionError,
    DatabaseQueryError,
    check_connection,
    fetch_products_with_recent_prices,
)
from events import build_price_change_candidate
from snapshot import build_snapshot_candidates


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the intentionally small command-line contract for the worker."""

    parser = argparse.ArgumentParser(description="Snapshot Worker v1.1")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read sources with SELECT only and report candidates without writes",
    )
    return parser.parse_args(argv)


def _format_value(value: object) -> str:
    """Format optional numeric values for a compact dry-run report."""

    return "null" if value is None else str(value)


def run_dry_run() -> int:
    """Read current sources and report candidates without PostgreSQL writes."""

    print("[CONFIG]")
    print("Checking environment configuration")
    try:
        config = load_database_config()
        batch_size = load_batch_size()
    except ConfigurationError as error:
        print(f"ERROR: {error}")
        print("[DATABASE] SKIPPED: configuration is invalid")
        return 2

    print("OK")
    print("[DATABASE]")
    print("Checking read-only PostgreSQL connection")
    try:
        check_connection(config)
    except DatabaseConnectionError as error:
        print(f"ERROR: {error}")
        return 3

    print("OK")
    try:
        products = fetch_products_with_recent_prices(config, batch_size)
    except (DatabaseConnectionError, DatabaseQueryError) as error:
        print(f"ERROR: {error}")
        return 4

    print("[PRODUCTS]")
    print(f"Products found: {len(products)}")

    snapshots = build_snapshot_candidates(products)
    snapshots_with_price = sum(snapshot.current_price is not None for snapshot in snapshots)
    print("[SNAPSHOTS]")
    print(f"Snapshot candidates: {len(snapshots)}")
    print(f"Candidates with current price: {snapshots_with_price}")

    candidates = [
        candidate
        for product in products
        if (
            candidate := build_price_change_candidate(
                product.offer_id, product.previous_price, product.current_price
            )
        )
        is not None
    ]
    print("[PRICE EVENTS]")
    print(f"PRICE_CHANGED candidates: {len(candidates)}")
    for candidate in candidates:
        print(
            "offer_id={offer_id} old_value={old_value} new_value={new_value} "
            "absolute_change={absolute_change} change_percent={change_percent} "
            "severity={severity} rule_id={rule_id}".format(
                offer_id=candidate.offer_id,
                old_value=_format_value(candidate.old_value),
                new_value=_format_value(candidate.new_value),
                absolute_change=_format_value(candidate.absolute_change),
                change_percent=_format_value(candidate.change_percent),
                severity=candidate.severity,
                rule_id=candidate.rule_id,
            )
        )

    print("[RESULT]")
    print("Snapshot Worker v1.1 dry-run completed")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run only the supported read-only dry-run behaviour."""

    args = parse_args(argv)
    if args.dry_run:
        return run_dry_run()

    print("Snapshot Worker v1.1 supports read-only validation with --dry-run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
