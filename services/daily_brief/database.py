"""Read-only source queries for Daily Commercial Brief v0.1."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator

from .config import DatabaseConfig


class DatabaseError(RuntimeError):
    pass


@contextmanager
def open_read_only_connection(config: DatabaseConfig) -> Iterator[Any]:
    try:
        import psycopg2

        connection = psycopg2.connect(
            host=config.host, port=config.port, dbname=config.name, user=config.user,
            password=config.password, connect_timeout=5,
            options="-c default_transaction_read_only=on",
        )
    except Exception as error:
        raise DatabaseError("PostgreSQL connection check failed") from error
    try:
        yield connection
    finally:
        connection.close()


# State, daily flow, delivery outcome and confirmed finance deliberately remain
# separate result sets; only their shared offer_id/business_date is presented.
PRODUCTS_QUERY = """
SELECT offer_id, sku, product_id, price, cost_price, updated_from_ozon
FROM products
ORDER BY offer_id
"""

DEMAND_QUERY = """
SELECT offer_id, sku, ordered_revenue, ordered_units, collected_at, data_quality_status
FROM seller_product_demand_daily
WHERE business_date = %s
ORDER BY offer_id
"""

DELIVERIES_QUERY = """
SELECT offer_id, COALESCE(SUM(quantity), 0)::integer AS delivered_units
FROM postings
WHERE status = 'delivered'
  AND (delivering_date AT TIME ZONE 'Europe/Moscow')::date = %s
GROUP BY offer_id
"""

RETURNS_QUERY = """
SELECT offer_id, COUNT(*)::integer AS return_events, COALESCE(SUM(quantity), 0)::integer AS returned_units
FROM returns
WHERE logistic_return_date IS NOT NULL
  AND logistic_return_date::date = %s
GROUP BY offer_id
"""

# This is explicitly delivery-date confirmed finance, not ordered flow and not a
# tax date. It preserves the established vw_orders_profit_final source of truth.
CONFIRMED_FINANCE_QUERY = """
WITH delivered AS (
  SELECT posting_number, sku, MAX(offer_id) AS offer_id, MAX(quantity) AS quantity
  FROM postings
  WHERE status = 'delivered'
    AND (delivering_date AT TIME ZONE 'Europe/Moscow')::date = %s
    AND quantity > 0 AND offer_id IS NOT NULL
  GROUP BY posting_number, sku
), base AS (
  SELECT regexp_replace(d.posting_number, '-[0-9]+$', '') AS posting_key,
         d.posting_number, d.offer_id, d.quantity, f.revenue, f.payout,
         f.other_expenses, p.cost_price
  FROM delivered d
  JOIN vw_orders_profit_final f ON f.posting_key = regexp_replace(d.posting_number, '-[0-9]+$', '')
  JOIN products p ON p.offer_id = d.offer_id
), keyed AS (
  SELECT *, COUNT(*) OVER (PARTITION BY posting_key) AS line_count FROM base
)
SELECT offer_id, SUM(revenue) AS confirmed_revenue,
       SUM(payout + CASE WHEN line_count = 1 THEN other_expenses ELSE 0 END - cost_price * quantity)
         AS profit_before_tax,
       SUM(quantity)::integer AS confirmed_units,
       SUM(CASE WHEN line_count > 1 AND other_expenses <> 0 THEN 1 ELSE 0 END)::integer
         AS unallocated_other_expense_lines
FROM keyed
GROUP BY offer_id
"""

PROMOTIONS_QUERY = """
WITH latest_successful_run AS (
  SELECT run_id, collected_at
  FROM promotion_runs WHERE status = 'success'
  ORDER BY collected_at DESC, created_at DESC LIMIT 1
)
SELECT s.offer_id, s.action_id, s.action_title, s.action_type, s.source_list_type,
       s.action_price, s.current_boost, s.min_boost, s.max_boost,
       s.data_quality_status, r.collected_at
FROM promotion_snapshots s
JOIN latest_successful_run r ON r.run_id = s.run_id
WHERE s.offer_id IS NOT NULL
ORDER BY s.offer_id, s.source_list_type, s.action_id
"""

CPC_QUERY = """
SELECT offer_id, campaign_id, campaign_state, campaign_type, money_spent,
       views, clicks, orders, orders_money, data_quality_status
FROM cpc_advertising_daily
WHERE business_date = %s AND offer_id IS NOT NULL
ORDER BY offer_id, campaign_id
"""

FRESHNESS_QUERY = """
SELECT
  (SELECT MAX(business_date) FROM seller_product_demand_daily),
  (SELECT MAX(collected_at) FROM promotion_runs WHERE status = 'success'),
  (SELECT MAX(business_date) FROM cpc_advertising_daily),
  (SELECT MAX(delivering_date) FROM postings WHERE status = 'delivered'),
  (SELECT MAX(updated_from_ozon) FROM products)
"""

# Mirrors the established Price Recommendation v0.2 confirmation criterion:
# confirmed deliveries must occur after the current price entered force. The
# brief reads the status only; it makes no price recommendation.
CURRENT_PRICE_STATUS_QUERY = """
WITH raw_prices AS (
  SELECT offer_id, price, updated_from_ozon,
         LAG(price) OVER (PARTITION BY offer_id ORDER BY updated_from_ozon, id) AS previous_price
  FROM ozon_price_history WHERE price IS NOT NULL
), current_prices AS (
  SELECT DISTINCT ON (offer_id) offer_id, price, updated_from_ozon AS price_since
  FROM raw_prices WHERE price IS DISTINCT FROM previous_price
  ORDER BY offer_id, updated_from_ozon DESC
), confirmed_deliveries AS (
  SELECT p.offer_id, p.quantity, p.delivering_date
  FROM postings p JOIN vw_orders_profit_final f
    ON f.posting_key = regexp_replace(p.posting_number, '-[0-9]+$', '')
  WHERE p.status = 'delivered' AND p.quantity > 0
)
SELECT p.offer_id,
  CASE WHEN cp.price IS NULL OR p.cost_price IS NULL THEN 'REVIEW_DATA'
       WHEN COALESCE(SUM(d.quantity) FILTER (WHERE d.delivering_date >= cp.price_since), 0) >= 10 THEN 'CONFIRMED'
       ELSE 'NOT_YET_CONFIRMED' END AS current_price_economics_status
FROM products p LEFT JOIN current_prices cp ON cp.offer_id = p.offer_id
LEFT JOIN confirmed_deliveries d ON d.offer_id = p.offer_id
GROUP BY p.offer_id, cp.price, cp.price_since, p.cost_price
ORDER BY p.offer_id
"""


def fetch_brief_sources(config: DatabaseConfig, business_date: date) -> dict[str, list[tuple[Any, ...]] | tuple[Any, ...]]:
    try:
        with open_read_only_connection(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(PRODUCTS_QUERY); products = cursor.fetchall()
                cursor.execute(DEMAND_QUERY, (business_date,)); demand = cursor.fetchall()
                cursor.execute(DELIVERIES_QUERY, (business_date,)); deliveries = cursor.fetchall()
                cursor.execute(RETURNS_QUERY, (business_date,)); returns = cursor.fetchall()
                cursor.execute(CONFIRMED_FINANCE_QUERY, (business_date,)); finance = cursor.fetchall()
                cursor.execute(PROMOTIONS_QUERY); promotions = cursor.fetchall()
                cursor.execute(CPC_QUERY, (business_date,)); cpc = cursor.fetchall()
                cursor.execute(FRESHNESS_QUERY); freshness = cursor.fetchone()
                cursor.execute(CURRENT_PRICE_STATUS_QUERY); current_price_status = cursor.fetchall()
    except DatabaseError:
        raise
    except Exception as error:
        raise DatabaseError("Daily brief read-only query failed") from error
    return {"products": products, "demand": demand, "deliveries": deliveries, "returns": returns,
            "finance": finance, "promotions": promotions, "cpc": cpc, "freshness": freshness,
            "current_price_status": current_price_status}
