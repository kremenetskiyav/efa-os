"""Read-only PostgreSQL query for existing EFA product economics views."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from config import DatabaseConfig
from models import ProductEconomics


class DatabaseError(RuntimeError):
    """Raised without exposing database credentials or DSN details."""


PRODUCT_ECONOMICS_QUERY = """
WITH latest_price AS (
    SELECT DISTINCT ON (offer_id) offer_id, price
    FROM ozon_price_history
    WHERE offer_id IS NOT NULL AND price IS NOT NULL AND updated_from_ozon IS NOT NULL
    ORDER BY offer_id, updated_from_ozon DESC, created_at DESC, id DESC
),
profit_period AS (
    SELECT offer_id, MIN(operation_date) AS period_start, MAX(operation_date) AS period_end,
           SUM(revenue) AS revenue, SUM(profit) AS profit, SUM(commission) AS commission,
           SUM(logistics) AS logistics
    FROM vw_orders_profit_final
    GROUP BY offer_id
)
SELECT p.offer_id, lp.price AS current_price, p.cost_price, pp.revenue, pp.profit,
       pp.commission, pp.logistics, pp.period_start, pp.period_end,
       analytics.delivered_units, analytics.revenue AS analytics_revenue,
       analytics.profit AS analytics_profit
FROM products AS p
LEFT JOIN latest_price AS lp ON lp.offer_id = p.offer_id
LEFT JOIN profit_period AS pp ON pp.offer_id = p.offer_id
LEFT JOIN vw_product_analytics AS analytics ON analytics.offer_id = p.offer_id
ORDER BY p.offer_id ASC
"""


@contextmanager
def open_read_only_connection(config: DatabaseConfig) -> Iterator[object]:
    try:
        import psycopg2
        connection = psycopg2.connect(host=config.host, port=config.port, dbname=config.name, user=config.user, password=config.password, connect_timeout=5, options="-c default_transaction_read_only=on")
    except Exception as error:
        raise DatabaseError("PostgreSQL connection check failed") from error
    try:
        yield connection
    finally:
        connection.close()


def fetch_product_economics(config: DatabaseConfig) -> list[ProductEconomics]:
    """Load all product economics through existing canonical sources and views."""
    try:
        with open_read_only_connection(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(PRODUCT_ECONOMICS_QUERY)
                rows = cursor.fetchall()
    except DatabaseError:
        raise
    except Exception as error:
        raise DatabaseError("Read-only product economics query failed") from error
    return [ProductEconomics(offer_id=row[0], current_price=row[1], cost_price=row[2], revenue=row[3], profit=row[4], commission=row[5], logistics=row[6], period_start=row[7], period_end=row[8], delivered_units=row[9], analytics_revenue=row[10], analytics_profit=row[11]) for row in rows]
