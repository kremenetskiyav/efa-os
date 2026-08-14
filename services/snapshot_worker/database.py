"""Read-only PostgreSQL access for Snapshot Worker v1.1 dry-run."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from config import DatabaseConfig


class DatabaseConnectionError(RuntimeError):
    """Raised when the worker cannot establish a PostgreSQL connection."""


class DatabaseQueryError(RuntimeError):
    """Raised when the read-only source query cannot be completed."""


@dataclass(frozen=True)
class ProductPriceHistory:
    """One product with its latest and immediately previous price point."""

    offer_id: str
    cost_price_used: Decimal | None
    current_price: Decimal | None
    price_updated_from_ozon: datetime | None
    previous_price: Decimal | None
    previous_price_updated_from_ozon: datetime | None


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
