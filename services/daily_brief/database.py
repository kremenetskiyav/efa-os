"""Read-only source queries for Daily Commercial Brief v1.1."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator

from .config import DatabaseConfig
from .tax_adapter import calculate_persisted_tax_state


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
SELECT offer_id, sku, ordered_revenue, ordered_units, collected_at,
       data_quality_status, collection_ref
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

STATE_FRESHNESS_QUERY = """
SELECT
  (SELECT MAX(collected_at) FROM promotion_runs WHERE status = 'success'),
  -- Current-price freshness is a collection-success signal. Change history
  -- may legitimately be older when the seller price is unchanged.
  (SELECT MAX(collected_at) FROM price_collection_runs WHERE status = 'success')
"""

CPC_COLLECTION_QUERY = """
SELECT status, records_count, campaigns_count, mapping_status, collected_at,
       lifecycle_state, report_state, error_code, error_message,
       attention_reason, completed_at, collection_ref
FROM cpc_collection_runs
WHERE business_date = %s
ORDER BY collected_at DESC, created_at DESC
LIMIT 1
"""

OPERATIONAL_RUNS_QUERY = """
WITH required(source) AS (VALUES ('POSTINGS'), ('RETURNS'), ('FINANCE'))
SELECT r.source, x.business_date, x.status, x.records_count, x.pages_count,
       x.completed_at, x.collection_ref, x.error_message
FROM required r
LEFT JOIN LATERAL (
  SELECT business_date, status, records_count, pages_count, completed_at,
         collection_ref, error_message
  FROM operational_collection_runs
  WHERE source = r.source AND business_date <= %s
  ORDER BY business_date DESC, completed_at DESC
  LIMIT 1
) x ON TRUE
ORDER BY r.source
"""

INFORMATION_EVENTS_QUERY = """
SELECT e.event_id::text, e.source_id, s.title, e.event_kind, e.classification,
       e.severity, e.requires_action, e.confidence, e.review_status,
       e.event_metadata, e.business_domains, e.affected_components, e.created_at
FROM information_change_events e
JOIN information_sources s ON s.source_id = e.source_id
WHERE e.review_status IN ('PENDING', 'REVIEWED')
ORDER BY CASE e.severity
           WHEN 'CRITICAL' THEN 1 WHEN 'ACTION_REQUIRED' THEN 2
           WHEN 'WATCH' THEN 3 ELSE 4 END,
         e.created_at DESC, e.event_id
"""

INFORMATION_FRESHNESS_QUERY = """
SELECT source_id, status, checked_at, error_summary
FROM information_source_checks
ORDER BY checked_at DESC, created_at DESC
LIMIT 1
"""

TAX_EVENTS_QUERY = """
SELECT event_id, tax_year, source_period, event_type, posting_number, offer_id,
       sku, event_date, amount, source_document, source_reference,
       tax_semantics_status, tax_date_status, data_quality_status
FROM tax_revenue_events
WHERE tax_year = %s
ORDER BY source_period, event_type, event_id
"""

TAX_IMPORT_RUNS_QUERY = """
SELECT source_period, status, events_count, accounting_income,
       data_quality_status, created_at
FROM tax_revenue_import_runs
WHERE source_period LIKE %s
ORDER BY source_period
"""

EXPERIMENTS_QUERY = """
SELECT experiment_id, offer_id, experiment_type, status, started_at, ended_at,
       target_config, unit_limit, duration_limit_days, loss_limit, notes,
       created_at, updated_at
FROM commercial_experiments
WHERE status IN ('PLANNED', 'ACTIVE', 'PAUSED')
ORDER BY created_at, experiment_id
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

LATEST_CONFIRMED_ECONOMICS_QUERY = """
WITH delivered AS (
  SELECT p.posting_number, p.sku, MAX(p.offer_id) AS offer_id,
         MAX(p.quantity) AS quantity, MAX(p.delivering_date) AS delivery_at,
         (MAX(p.delivering_date) AT TIME ZONE 'Europe/Moscow')::date AS business_date
  FROM postings p
  WHERE p.status = 'delivered' AND p.quantity > 0 AND p.offer_id IS NOT NULL
  GROUP BY p.posting_number, p.sku
), base AS (
  SELECT regexp_replace(d.posting_number, '-[0-9]+$', '') AS posting_key,
         d.offer_id, d.quantity, d.business_date, f.revenue, f.payout,
         f.other_expenses, p.cost_price
  FROM delivered d
  JOIN vw_orders_profit_final f ON f.posting_key = regexp_replace(d.posting_number, '-[0-9]+$', '')
  JOIN products p ON p.offer_id = d.offer_id
), keyed AS (
  SELECT *, COUNT(*) OVER (PARTITION BY posting_key) AS line_count FROM base
), economics AS (
  SELECT k.offer_id, k.business_date AS confirmed_through_date, SUM(k.revenue) AS confirmed_revenue,
         SUM(k.payout + CASE WHEN k.line_count = 1 THEN k.other_expenses ELSE 0 END - k.cost_price * k.quantity)
           AS profit_before_tax,
         SUM(k.quantity)::integer AS delivered_units,
         SUM(CASE WHEN k.line_count > 1 AND k.other_expenses <> 0 THEN 1 ELSE 0 END)::integer
           AS unallocated_other_expense_lines
  FROM keyed k
  GROUP BY k.offer_id, k.business_date
), returned AS (
  SELECT r.offer_id, r.logistic_return_date::date AS business_date,
         COUNT(*)::integer AS return_events,
         COALESCE(SUM(r.quantity), 0)::integer AS returned_units
  FROM returns r
  WHERE r.logistic_return_date IS NOT NULL
  GROUP BY r.offer_id, r.logistic_return_date::date
), ranked AS (
  SELECT e.*, COALESCE(r.return_events, 0) AS return_events,
         COALESCE(r.returned_units, 0) AS returned_units,
         ROW_NUMBER() OVER (PARTITION BY e.offer_id ORDER BY e.confirmed_through_date DESC) AS rn
  FROM economics e
  LEFT JOIN returned r ON r.offer_id = e.offer_id
    AND r.business_date = e.confirmed_through_date
)
SELECT offer_id, confirmed_through_date, confirmed_revenue, profit_before_tax,
       delivered_units, return_events, returned_units,
       unallocated_other_expense_lines
FROM ranked
WHERE rn = 1
ORDER BY offer_id
"""

LATEST_CONFIRMED_SUMMARY_QUERY = """
WITH delivered AS (
  SELECT p.posting_number, p.sku, MAX(p.offer_id) AS offer_id,
         MAX(p.quantity) AS quantity,
         (MAX(p.delivering_date) AT TIME ZONE 'Europe/Moscow')::date AS business_date
  FROM postings p
  WHERE p.status = 'delivered' AND p.quantity > 0 AND p.offer_id IS NOT NULL
  GROUP BY p.posting_number, p.sku
), base AS (
  SELECT regexp_replace(d.posting_number, '-[0-9]+$', '') AS posting_key,
         d.offer_id, d.quantity, d.business_date, f.revenue, f.payout,
         f.other_expenses, p.cost_price
  FROM delivered d
  JOIN vw_orders_profit_final f
    ON f.posting_key = regexp_replace(d.posting_number, '-[0-9]+$', '')
  JOIN products p ON p.offer_id = d.offer_id
), keyed AS (
  SELECT *, COUNT(*) OVER (PARTITION BY posting_key) AS line_count FROM base
), boundary AS (
  SELECT MAX(business_date) AS confirmed_through_date FROM keyed
)
SELECT b.confirmed_through_date, SUM(k.revenue) AS confirmed_revenue,
       SUM(k.payout + CASE WHEN k.line_count = 1 THEN k.other_expenses ELSE 0 END
           - k.cost_price * k.quantity) AS profit_before_tax,
       SUM(k.quantity)::integer AS delivered_units,
       SUM(CASE WHEN k.line_count > 1 AND k.other_expenses <> 0 THEN 1 ELSE 0 END)::integer
         AS unallocated_other_expense_lines
FROM keyed k CROSS JOIN boundary b
WHERE k.business_date = b.confirmed_through_date
GROUP BY b.confirmed_through_date
"""

DEMAND_TREND_QUERY = """
SELECT offer_id, business_date, ordered_revenue, ordered_units
FROM seller_product_demand_daily
WHERE business_date BETWEEN %s - 29 AND %s AND data_quality_status = 'valid'
ORDER BY business_date, offer_id
"""

PRICE_TREND_QUERY = """
SELECT offer_id, updated_from_ozon, price
FROM ozon_price_history
WHERE updated_from_ozon >= (%s::date - 29)
ORDER BY updated_from_ozon, offer_id, id
"""

BOOST_TREND_QUERY = """
SELECT s.offer_id, r.collected_at, s.current_boost
FROM promotion_snapshots s
JOIN promotion_runs r ON r.run_id = s.run_id
WHERE r.status = 'success' AND s.source_list_type = 'PARTICIPATING'
  AND s.current_boost IS NOT NULL AND s.data_quality_status = 'valid'
  AND r.collected_at >= (%s::date - 29)
ORDER BY r.collected_at, s.offer_id
"""

FINANCE_TREND_QUERY = """
WITH delivered AS (
  SELECT p.posting_number, p.sku, MAX(p.offer_id) AS offer_id,
         MAX(p.quantity) AS quantity,
         (MAX(p.delivering_date) AT TIME ZONE 'Europe/Moscow')::date AS business_date
  FROM postings p
  WHERE p.status = 'delivered' AND p.quantity > 0 AND p.offer_id IS NOT NULL
  GROUP BY p.posting_number, p.sku
), base AS (
  SELECT regexp_replace(d.posting_number, '-[0-9]+$', '') AS posting_key,
         d.offer_id, d.quantity, d.business_date, f.revenue, f.payout,
         f.other_expenses, p.cost_price
  FROM delivered d
  JOIN vw_orders_profit_final f ON f.posting_key = regexp_replace(d.posting_number, '-[0-9]+$', '')
  JOIN products p ON p.offer_id = d.offer_id
  WHERE d.business_date BETWEEN %s - 29 AND %s
), keyed AS (
  SELECT *, COUNT(*) OVER (PARTITION BY posting_key) AS line_count FROM base
)
SELECT offer_id, business_date, SUM(revenue) AS confirmed_revenue,
       SUM(payout + CASE WHEN line_count = 1 THEN other_expenses ELSE 0 END - cost_price * quantity)
         AS profit_before_tax
FROM keyed
GROUP BY offer_id, business_date
ORDER BY business_date, offer_id
"""


def fetch_brief_sources(config: DatabaseConfig, business_date: date) -> dict[str, Any]:
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
                cursor.execute(STATE_FRESHNESS_QUERY); state_freshness = cursor.fetchone()
                cursor.execute(CPC_COLLECTION_QUERY, (business_date,)); cpc_collection = cursor.fetchone()
                cursor.execute(OPERATIONAL_RUNS_QUERY, (business_date,)); operational_runs = cursor.fetchall()
                cursor.execute(INFORMATION_EVENTS_QUERY); information_events = cursor.fetchall()
                cursor.execute(INFORMATION_FRESHNESS_QUERY); information_freshness = cursor.fetchone()
                cursor.execute(TAX_EVENTS_QUERY, (business_date.year,)); tax_events = cursor.fetchall()
                cursor.execute(TAX_IMPORT_RUNS_QUERY, (f"{business_date.year}-%",)); tax_runs = cursor.fetchall()
                cursor.execute(EXPERIMENTS_QUERY); experiments = cursor.fetchall()
                cursor.execute(CURRENT_PRICE_STATUS_QUERY); current_price_status = cursor.fetchall()
                cursor.execute(LATEST_CONFIRMED_ECONOMICS_QUERY); latest_economics = cursor.fetchall()
                cursor.execute(LATEST_CONFIRMED_SUMMARY_QUERY); latest_economics_summary = cursor.fetchone()
                cursor.execute(DEMAND_TREND_QUERY, (business_date, business_date)); demand_trend = cursor.fetchall()
                cursor.execute(PRICE_TREND_QUERY, (business_date,)); price_trend = cursor.fetchall()
                cursor.execute(BOOST_TREND_QUERY, (business_date,)); boost_trend = cursor.fetchall()
                cursor.execute(FINANCE_TREND_QUERY, (business_date, business_date)); finance_trend = cursor.fetchall()
    except DatabaseError:
        raise
    except Exception as error:
        raise DatabaseError("Daily brief read-only query failed") from error
    try:
        tax_state = calculate_persisted_tax_state(tax_events, tax_runs, business_date)
    except Exception as error:
        raise DatabaseError("Tax Engine state calculation failed") from error
    return {"products": products, "demand": demand, "deliveries": deliveries, "returns": returns,
            "finance": finance, "promotions": promotions, "cpc": cpc,
            "state_freshness": state_freshness, "cpc_collection": cpc_collection,
            "operational_runs": operational_runs,
            "information_events": information_events,
            "information_freshness": information_freshness,
            "tax_state": tax_state, "experiments": experiments,
            "current_price_status": current_price_status, "latest_economics": latest_economics,
            "latest_economics_summary": latest_economics_summary,
            "trends": {"demand": demand_trend, "price": price_trend,
                       "boost": boost_trend, "finance": finance_trend}}
