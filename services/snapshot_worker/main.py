"""Command entry point for Snapshot Worker v1.2."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from config import ConfigurationError, load_batch_size, load_database_config
from database import (
    DatabaseConnectionError,
    DatabaseQueryError,
    SnapshotWriteError,
    check_connection,
    fetch_products_with_recent_prices,
    write_daily_snapshot_run,
)
from events import build_price_change_candidate
from snapshot import (
    build_daily_idempotency_key,
    build_snapshot_candidates,
    calculate_business_date,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the intentionally small command-line contract for the worker."""

    parser = argparse.ArgumentParser(description="Snapshot Worker v1.2")
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
    for snapshot in snapshots:
        print(
            "offer_id={offer_id} current_price={current_price} "
            "price_updated_from_ozon={price_updated_from_ozon} "
            "cost_price_used={cost_price_used} data_quality_status={data_quality_status}".format(
                offer_id=snapshot.offer_id,
                current_price=_format_value(snapshot.current_price),
                price_updated_from_ozon=_format_value(
                    snapshot.price_updated_from_ozon
                ),
                cost_price_used=_format_value(snapshot.cost_price_used),
                data_quality_status=snapshot.data_quality_status,
            )
        )

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
    print("Snapshot Worker v1.2 dry-run completed")
    return 0


def run_snapshot_write() -> int:
    """Create one atomic, idempotent daily snapshot run without events."""

    print("[CONFIG]")
    print("Checking environment configuration")
    try:
        config = load_database_config()
        batch_size = load_batch_size()
    except ConfigurationError as error:
        print(f"ERROR: {error}")
        return 2

    print("OK")
    print("[DATABASE]")
    print("Checking PostgreSQL connection")
    try:
        check_connection(config)
        products = fetch_products_with_recent_prices(config, batch_size)
    except (DatabaseConnectionError, DatabaseQueryError) as error:
        print(f"ERROR: {error}")
        return 3

    print("OK")
    snapshots = build_snapshot_candidates(products)
    business_date = calculate_business_date()
    idempotency_key = build_daily_idempotency_key(business_date)

    print("[RUN]")
    print(f"business_date: {business_date.isoformat()}")
    print("run_type: daily")
    print("[PRODUCTS]")
    print(f"Products found: {len(products)}")
    print("[SNAPSHOTS]")
    print(f"Snapshot candidates: {len(snapshots)}")

    try:
        result = write_daily_snapshot_run(
            config,
            idempotency_key=idempotency_key,
            business_date=business_date,
            snapshots=snapshots,
        )
    except (DatabaseConnectionError, SnapshotWriteError) as error:
        print("[RESULT]")
        print(f"ERROR: {error}")
        return 4

    print("[RESULT]")
    if result.already_exists:
        print("No write: logical daily snapshot run already exists")
    print(f"snapshot_run: {result.run_id}")
    print(f"business_date: {business_date.isoformat()}")
    print(f"products_expected: {result.products_expected}")
    print(f"products_snapshotted: {result.products_snapshotted}")
    print(f"products_invalid: {result.products_invalid}")
    print(f"status: {result.status}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run a read-only dry-run or the transactional Snapshot Layer write mode."""

    args = parse_args(argv)
    if args.dry_run:
        return run_dry_run()

    return run_snapshot_write()


if __name__ == "__main__":
    raise SystemExit(main())
