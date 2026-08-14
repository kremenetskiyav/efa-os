"""PostgreSQL access for Snapshot Worker v1.2."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from config import DatabaseConfig

if TYPE_CHECKING:
    from snapshot import SnapshotCandidate


class DatabaseConnectionError(RuntimeError):
    """Raised when the worker cannot establish a PostgreSQL connection."""


class DatabaseQueryError(RuntimeError):
    """Raised when the read-only source query cannot be completed."""


class SnapshotWriteError(RuntimeError):
    """Raised when an atomic Snapshot Layer write cannot be completed."""


@dataclass(frozen=True)
class ProductPriceHistory:
    """One product with its latest and immediately previous price point."""

    offer_id: str
    cost_price_used: Decimal | None
    current_price: Decimal | None
    price_updated_from_ozon: datetime | None
    previous_price: Decimal | None
    previous_price_updated_from_ozon: datetime | None


@dataclass(frozen=True)
class SnapshotRunWriteResult:
    """Safe outcome of one attempted daily logical snapshot run."""

    run_id: UUID
    status: str
    already_exists: bool
    products_expected: int
    products_snapshotted: int
    products_invalid: int


# One batch query for all products. ROW_NUMBER ranks each offer_id by Ozon's
# source timestamp and uses created_at as a deterministic tie-breaker.
RECENT_PRODUCT_PRICES_QUERY = """
WITH ranked_price_points AS (
    SELECT
        offer_id,
        price,
        updated_from_ozon,
        ROW_NUMBER() OVER (
            PARTITION BY offer_id
            ORDER BY
                updated_from_ozon DESC NULLS LAST,
                created_at DESC NULLS LAST,
                price DESC NULLS LAST
        ) AS price_rank
    FROM ozon_price_history
    WHERE offer_id IS NOT NULL
      AND price IS NOT NULL
      AND updated_from_ozon IS NOT NULL
),
two_latest_price_points AS (
    SELECT offer_id, price, updated_from_ozon, price_rank
    FROM ranked_price_points
    WHERE price_rank <= 2
)
SELECT
    p.offer_id,
    p.cost_price,
    MAX(r.price) FILTER (WHERE r.price_rank = 1) AS current_price,
    MAX(r.updated_from_ozon) FILTER (WHERE r.price_rank = 1)
        AS price_updated_from_ozon,
    MAX(r.price) FILTER (WHERE r.price_rank = 2) AS previous_price,
    MAX(r.updated_from_ozon) FILTER (WHERE r.price_rank = 2)
        AS previous_price_updated_from_ozon
FROM products AS p
LEFT JOIN two_latest_price_points AS r ON r.offer_id = p.offer_id
GROUP BY p.offer_id, p.cost_price
ORDER BY p.offer_id ASC
"""


SELECT_SNAPSHOT_RUN_QUERY = """
SELECT run_id, status, products_expected, products_snapshotted, products_invalid
FROM snapshot_runs
WHERE idempotency_key = %s
"""

INSERT_SNAPSHOT_RUN_QUERY = """
INSERT INTO snapshot_runs (
    idempotency_key,
    run_type,
    business_date,
    started_at,
    status,
    source_watermark,
    products_expected,
    products_snapshotted,
    products_invalid
)
VALUES (%s, 'daily', %s, %s, 'running', %s, %s, 0, 0)
RETURNING run_id
"""

INSERT_PRODUCT_SNAPSHOT_QUERY = """
INSERT INTO product_snapshots (
    run_id,
    offer_id,
    snapshot_at,
    business_date,
    current_price,
    price_updated_from_ozon,
    cost_price_used,
    source_name,
    data_quality_status
)
VALUES (%s, %s, %s, %s, %s, %s, %s, 'ozon_phase_a', %s)
"""

COMPLETE_SNAPSHOT_RUN_QUERY = """
UPDATE snapshot_runs
SET completed_at = %s,
    status = %s,
    products_snapshotted = %s,
    products_invalid = %s
WHERE run_id = %s
  AND status = 'running'
"""

INSERT_FAILED_SNAPSHOT_RUN_QUERY = """
INSERT INTO snapshot_runs (
    idempotency_key,
    run_type,
    business_date,
    started_at,
    completed_at,
    status,
    source_watermark,
    products_expected,
    products_snapshotted,
    products_invalid,
    error_summary
)
VALUES (%s, 'daily', %s, %s, %s, 'failed', %s, %s, 0, 0, %s)
RETURNING run_id
"""


@contextmanager
def open_read_only_connection(config: DatabaseConfig) -> Iterator[object]:
    """Open a PostgreSQL connection configured as read-only and close it safely."""

    try:
        import psycopg2

        connection = psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.name,
            user=config.user,
            password=config.password,
            connect_timeout=5,
            options="-c default_transaction_read_only=on",
        )
    except Exception as error:  # Driver exceptions are intentionally not exposed.
        raise DatabaseConnectionError("PostgreSQL connection check failed") from error

    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def open_write_connection(config: DatabaseConfig) -> Iterator[object]:
    """Open a write-capable connection used only by the normal worker mode."""

    try:
        import psycopg2

        connection = psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.name,
            user=config.user,
            password=config.password,
            connect_timeout=5,
        )
    except Exception as error:
        raise DatabaseConnectionError("PostgreSQL connection check failed") from error

    try:
        yield connection
    finally:
        connection.close()


def check_connection(config: DatabaseConfig) -> None:
    """Open and close PostgreSQL connectivity without executing any SQL statement."""

    with open_read_only_connection(config):
        return None


def fetch_products_with_recent_prices(
    config: DatabaseConfig, batch_size: int
) -> list[ProductPriceHistory]:
    """Fetch products and their two latest price points with one batched SELECT."""

    products: list[ProductPriceHistory] = []
    try:
        with open_read_only_connection(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(RECENT_PRODUCT_PRICES_QUERY)
                while rows := cursor.fetchmany(batch_size):
                    products.extend(
                        ProductPriceHistory(
                            offer_id=row[0],
                            cost_price_used=row[1],
                            current_price=row[2],
                            price_updated_from_ozon=row[3],
                            previous_price=row[4],
                            previous_price_updated_from_ozon=row[5],
                        )
                        for row in rows
                    )
    except DatabaseConnectionError:
        raise
    except Exception as error:
        raise DatabaseQueryError("Read-only product and price query failed") from error

    return products


def _row_to_run_result(row: tuple[object, ...]) -> SnapshotRunWriteResult:
    return SnapshotRunWriteResult(
        run_id=row[0],
        status=str(row[1]),
        already_exists=True,
        products_expected=int(row[2] or 0),
        products_snapshotted=int(row[3] or 0),
        products_invalid=int(row[4] or 0),
    )


def _find_snapshot_run(connection: object, idempotency_key: str) -> SnapshotRunWriteResult | None:
    with connection.cursor() as cursor:
        cursor.execute(SELECT_SNAPSHOT_RUN_QUERY, (idempotency_key,))
        row = cursor.fetchone()
    return None if row is None else _row_to_run_result(row)


def _source_watermark(snapshots: list[SnapshotCandidate]) -> datetime | None:
    timestamps = [
        snapshot.price_updated_from_ozon
        for snapshot in snapshots
        if snapshot.price_updated_from_ozon is not None
    ]
    return max(timestamps) if timestamps else None


def _is_unique_violation(error: Exception) -> bool:
    return getattr(error, "pgcode", None) == "23505"


def _persist_failed_run(
    config: DatabaseConfig,
    *,
    idempotency_key: str,
    business_date: date,
    started_at: datetime,
    source_watermark: datetime | None,
    products_expected: int,
    error: Exception,
) -> None:
    """Record a terminal failure only after the atomic write was rolled back."""

    safe_error = type(error).__name__
    try:
        with open_write_connection(config) as connection:
            existing = _find_snapshot_run(connection, idempotency_key)
            if existing is not None:
                connection.rollback()
                return
            with connection.cursor() as cursor:
                cursor.execute(
                    INSERT_FAILED_SNAPSHOT_RUN_QUERY,
                    (
                        idempotency_key,
                        business_date,
                        started_at,
                        datetime.now(timezone.utc),
                        source_watermark,
                        products_expected,
                        safe_error,
                    ),
                )
                cursor.fetchone()
            connection.commit()
    except Exception:
        # Preserve the original write error and never expose credentials in logs.
        return


def write_daily_snapshot_run(
    config: DatabaseConfig,
    *,
    idempotency_key: str,
    business_date: date,
    snapshots: list[SnapshotCandidate],
) -> SnapshotRunWriteResult:
    """Atomically create one daily run and its immutable product snapshots."""

    started_at = datetime.now(timezone.utc)
    products_expected = len(snapshots)
    products_invalid = sum(
        snapshot.data_quality_status != "valid" for snapshot in snapshots
    )
    products_snapshotted = products_expected - products_invalid
    status = "partial" if products_invalid else "success"
    watermark = _source_watermark(snapshots)

    try:
        with open_write_connection(config) as connection:
            existing = _find_snapshot_run(connection, idempotency_key)
            if existing is not None:
                connection.rollback()
                return existing

            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        INSERT_SNAPSHOT_RUN_QUERY,
                        (
                            idempotency_key,
                            business_date,
                            started_at,
                            watermark,
                            products_expected,
                        ),
                    )
                    run_row = cursor.fetchone()
                    if run_row is None:
                        raise SnapshotWriteError("Snapshot run identifier was not returned")
                    run_id = run_row[0]

                    cursor.executemany(
                        INSERT_PRODUCT_SNAPSHOT_QUERY,
                        [
                            (
                                run_id,
                                snapshot.offer_id,
                                started_at,
                                business_date,
                                snapshot.current_price,
                                snapshot.price_updated_from_ozon,
                                snapshot.cost_price_used,
                                snapshot.data_quality_status,
                            )
                            for snapshot in snapshots
                        ],
                    )
                    cursor.execute(
                        COMPLETE_SNAPSHOT_RUN_QUERY,
                        (
                            datetime.now(timezone.utc),
                            status,
                            products_snapshotted,
                            products_invalid,
                            run_id,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise SnapshotWriteError("Snapshot run could not be completed")
                connection.commit()
            except Exception as error:
                connection.rollback()
                if _is_unique_violation(error):
                    existing = _find_snapshot_run(connection, idempotency_key)
                    if existing is not None:
                        connection.rollback()
                        return existing
                raise
    except Exception as error:
        _persist_failed_run(
            config,
            idempotency_key=idempotency_key,
            business_date=business_date,
            started_at=started_at,
            source_watermark=watermark,
            products_expected=products_expected,
            error=error,
        )
        raise SnapshotWriteError("Snapshot run was rolled back") from error

    return SnapshotRunWriteResult(
        run_id=run_id,
        status=status,
        already_exists=False,
        products_expected=products_expected,
        products_snapshotted=products_snapshotted,
        products_invalid=products_invalid,
    )
