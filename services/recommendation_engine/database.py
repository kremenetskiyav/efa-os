"""Read-only delivery-date unit economics for Recommendation Engine v0.2."""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from typing import Collection, Iterator

from advertising_overlay import CpcObservation
from config import DatabaseConfig
from input_resolver import CalculatorSourceRow
from models import PriceWindow, ProductEconomics, PromotionState
from models import PeriodEconomics

class DatabaseError(RuntimeError):
    pass

# Price intervals use delivery time. Financial recognition time is deliberately
# absent from interval matching because it can lag delivery by days.
PRODUCT_ECONOMICS_QUERY = """
WITH delivered AS (
  SELECT p.posting_number, p.sku, MAX(p.offer_id) AS offer_id,
         MAX(p.quantity) AS quantity, MAX(p.delivering_date) AS delivery_at
  FROM postings p
  WHERE p.status = 'delivered' AND p.quantity > 0 AND p.offer_id IS NOT NULL
  GROUP BY p.posting_number, p.sku
), base AS (
  SELECT regexp_replace(d.posting_number, '-[0-9]+$', '') AS posting_key,
         d.posting_number, d.sku, d.offer_id, d.quantity, d.delivery_at,
         f.revenue, f.commission, f.logistics, f.other_expenses, f.payout,
         p.cost_price
  FROM delivered d
  JOIN vw_orders_profit_final f
    ON f.posting_key = regexp_replace(d.posting_number, '-[0-9]+$', '')
  JOIN products p ON p.offer_id = d.offer_id
), key_counts AS (SELECT posting_key, COUNT(*) AS line_count FROM base GROUP BY posting_key),
confirmed_rows AS (
  SELECT b.*, CASE WHEN k.line_count = 1 THEN b.other_expenses ELSE 0 END AS allocatable_other_expenses,
         CASE WHEN k.line_count > 1 AND b.other_expenses <> 0 THEN 1 ELSE 0 END AS unallocated_expense_line,
         b.payout + CASE WHEN k.line_count = 1 THEN b.other_expenses ELSE 0 END - b.cost_price * b.quantity AS confirmed_profit
  FROM base b JOIN key_counts k USING (posting_key)
), raw_prices AS (
  SELECT h.offer_id, h.price, h.updated_from_ozon,
         LAG(h.price) OVER (PARTITION BY h.offer_id ORDER BY h.updated_from_ozon, h.id) AS previous_price
  FROM ozon_price_history h WHERE h.price IS NOT NULL
), price_changes AS (
  SELECT offer_id, price, updated_from_ozon AS price_since
  FROM raw_prices WHERE price IS DISTINCT FROM previous_price
), price_intervals AS (
  SELECT offer_id, price, price_since,
         LEAD(price_since) OVER (PARTITION BY offer_id ORDER BY price_since) AS next_price_since
  FROM price_changes
), current_prices AS (
  SELECT DISTINCT ON (offer_id) offer_id, price AS current_price, price_since AS current_price_since
  FROM price_intervals ORDER BY offer_id, price_since DESC
), mapped AS (
  SELECT r.*, i.price AS seller_price, i.price_since
  FROM confirmed_rows r JOIN price_intervals i ON i.offer_id = r.offer_id
    AND r.delivery_at >= i.price_since
    AND (i.next_price_since IS NULL OR r.delivery_at < i.next_price_since)
), windows AS (
  SELECT offer_id, seller_price, price_since, SUM(quantity)::integer AS units,
         COUNT(DISTINCT posting_number)::integer AS orders, SUM(revenue) AS revenue,
         SUM(commission) AS commission, SUM(logistics) AS logistics,
         SUM(allocatable_other_expenses) AS other_expenses, SUM(cost_price * quantity) AS cost,
         SUM(payout) AS payout, SUM(confirmed_profit) AS profit,
         MIN(delivery_at) AS delivery_start, MAX(delivery_at) AS delivery_end,
         SUM(unallocated_expense_line)::integer AS unallocated_expense_lines
  FROM mapped GROUP BY offer_id, seller_price, price_since
), last_delivery AS (
  SELECT offer_id, MAX(delivery_at) AS last_delivery_at FROM confirmed_rows GROUP BY offer_id
), last_windows AS (
  SELECT r.offer_id, SUM(r.quantity)::integer AS units, COUNT(DISTINCT r.posting_number)::integer AS orders,
         SUM(r.revenue) AS revenue, SUM(r.commission) AS commission, SUM(r.logistics) AS logistics,
         SUM(r.allocatable_other_expenses) AS other_expenses, SUM(r.cost_price*r.quantity) AS cost,
         SUM(r.payout) AS payout, SUM(r.confirmed_profit) AS profit,
         MIN(r.delivery_at) AS delivery_start, MAX(r.delivery_at) AS delivery_end
  FROM confirmed_rows r JOIN last_delivery l ON l.offer_id=r.offer_id AND l.last_delivery_at=r.delivery_at
  GROUP BY r.offer_id
)
SELECT p.offer_id, cp.current_price, cp.current_price_since, p.cost_price,
       w.seller_price, w.price_since, w.units, w.orders, w.revenue, w.commission,
       w.logistics, w.other_expenses, w.cost, w.payout, w.profit, w.delivery_start,
       w.delivery_end, w.unallocated_expense_lines,
       lw.units, lw.orders, lw.revenue, lw.commission, lw.logistics, lw.other_expenses,
       lw.cost, lw.payout, lw.profit, lw.delivery_start, lw.delivery_end
FROM products p LEFT JOIN current_prices cp ON cp.offer_id=p.offer_id
LEFT JOIN windows w ON w.offer_id=p.offer_id LEFT JOIN last_windows lw ON lw.offer_id=p.offer_id
ORDER BY p.offer_id, w.price_since
"""

# Two equal delivery-date windows, based only on the established financial view.
# Financial operation date is deliberately not used as the sale-period timestamp.
ANOMALY_ECONOMICS_QUERY = """
WITH delivered AS (
  SELECT p.posting_number, p.sku, MAX(p.offer_id) AS offer_id,
         MAX(p.quantity) AS quantity, MAX(p.delivering_date) AS delivery_at
  FROM postings p
  WHERE p.status = 'delivered' AND p.quantity > 0 AND p.offer_id IS NOT NULL
  GROUP BY p.posting_number, p.sku
), base AS (
  SELECT regexp_replace(d.posting_number, '-[0-9]+$', '') AS posting_key,
         d.posting_number, d.sku, d.offer_id, d.quantity, d.delivery_at,
         f.revenue, f.commission, f.logistics, f.other_expenses, f.payout,
         p.cost_price
  FROM delivered d
  JOIN vw_orders_profit_final f ON f.posting_key = regexp_replace(d.posting_number, '-[0-9]+$', '')
  JOIN products p ON p.offer_id = d.offer_id
), key_counts AS (
  SELECT posting_key, COUNT(*) AS line_count FROM base GROUP BY posting_key
), confirmed AS (
  SELECT b.*, CASE WHEN k.line_count = 1 THEN b.other_expenses ELSE 0 END AS allocatable_other_expenses,
         CASE WHEN k.line_count > 1 AND b.other_expenses <> 0 THEN 1 ELSE 0 END AS unallocated_expense_line,
         b.payout + CASE WHEN k.line_count = 1 THEN b.other_expenses ELSE 0 END - b.cost_price * b.quantity AS profit
  FROM base b JOIN key_counts k USING (posting_key)
), bounds AS (
  SELECT MAX(delivery_at)::date AS current_end FROM confirmed
), classified AS (
  SELECT c.*, CASE
    WHEN c.delivery_at::date BETWEEN b.current_end - 6 AND b.current_end THEN 'current'
    WHEN c.delivery_at::date BETWEEN b.current_end - 13 AND b.current_end - 7 THEN 'baseline'
  END AS period_name
  FROM confirmed c CROSS JOIN bounds b
  WHERE c.delivery_at::date BETWEEN b.current_end - 13 AND b.current_end
)
SELECT p.offer_id, x.period_name,
       MIN(x.delivery_at) AS period_start, MAX(x.delivery_at) AS period_end,
       COALESCE(SUM(x.quantity), 0)::integer AS units,
       COUNT(DISTINCT x.posting_number)::integer AS orders,
       COALESCE(SUM(x.revenue), 0) AS revenue, COALESCE(SUM(x.profit), 0) AS profit,
       COALESCE(SUM(x.commission), 0) AS commission, COALESCE(SUM(x.logistics), 0) AS logistics,
       COALESCE(SUM(x.allocatable_other_expenses), 0) AS other_expenses,
       COALESCE(SUM(x.unallocated_expense_line), 0)::integer AS unallocated_expense_lines
FROM products p LEFT JOIN classified x ON x.offer_id = p.offer_id
GROUP BY p.offer_id, x.period_name ORDER BY p.offer_id, x.period_name
"""

PROMOTION_MONITORING_QUERY = """
WITH latest_successful_run AS (
  SELECT run_id, collected_at
  FROM promotion_runs
  WHERE status = 'success'
  ORDER BY collected_at DESC, created_at DESC
  LIMIT 1
)
SELECT s.offer_id, s.product_id, s.action_id, s.action_title, s.action_type,
       s.action_start_at, s.action_end_at, s.source_list_type, s.add_mode,
       s.price, s.action_price, s.max_action_price, r.collected_at,
       s.data_quality_status
FROM promotion_snapshots s
JOIN latest_successful_run r ON r.run_id = s.run_id
ORDER BY s.offer_id NULLS LAST, s.source_list_type, s.action_id, s.product_id
"""

CALCULATOR_SOURCE_QUERY = """
SELECT p.offer_id, p.ozon_product_id, p.current_price, p.cost_price,
       p.price_observed_at, p.price_checked_at,
       s.snapshot_id, s.price_collection_run_id,
       s.snapshot_product_id, s.snapshot_offer_id,
       s.observed_at, s.run_status, s.sales_percent_fbs,
       s.fbs_deliv_to_customer_amount, s.acquiring,
       s.fbs_direct_flow_trans_min_amount,
       s.fbs_direct_flow_trans_max_amount,
       s.fbs_return_flow_amount
FROM mcp_read.product_overview p
LEFT JOIN LATERAL (
  SELECT t.snapshot_id, t.price_collection_run_id,
         t.product_id AS snapshot_product_id,
         t.offer_id AS snapshot_offer_id,
         t.observed_at, r.status AS run_status,
         t.sales_percent_fbs, t.fbs_deliv_to_customer_amount,
         t.acquiring, t.fbs_direct_flow_trans_min_amount,
         t.fbs_direct_flow_trans_max_amount, t.fbs_return_flow_amount
  FROM ozon_fbs_tariff_snapshots t
  JOIN price_collection_runs r
    ON r.run_id = t.price_collection_run_id
   AND r.status = 'success'
  WHERE t.product_id = p.ozon_product_id
    AND t.offer_id = p.offer_id
  ORDER BY t.observed_at DESC, t.created_at DESC, t.snapshot_id DESC
  LIMIT 1
) s ON TRUE
WHERE p.offer_id = ANY(%s)
  AND p.is_archived IS NOT TRUE
ORDER BY p.offer_id
"""

CPC_LATEST_PRODUCT_QUERY = """
SELECT DISTINCT ON (offer_id)
       business_date, data_scope, offer_id, campaigns_count,
       active_campaigns_count, views, clicks, ctr_percent, spend,
       attributed_orders, attributed_revenue, product_gmv, drr_percent,
       general_drr_percent, average_bid, data_quality_status,
       collection_status, observed_at
FROM mcp_read.product_cpc_daily
WHERE data_scope = 'PRODUCT'
  AND offer_id = ANY(%s)
ORDER BY offer_id, business_date DESC, observed_at DESC
"""

@contextmanager
def open_read_only_connection(config: DatabaseConfig) -> Iterator[object]:
    try:
        import psycopg2
        connection = psycopg2.connect(host=config.host, port=config.port, dbname=config.name, user=config.user, password=config.password, connect_timeout=5, options="-c default_transaction_read_only=on")
    except Exception as error:
        raise DatabaseError("PostgreSQL connection check failed") from error
    try: yield connection
    finally: connection.close()

def _window(row: tuple[object, ...], start: int) -> PriceWindow:
    units, revenue = row[start+2], row[start+4]
    return PriceWindow(row[start], revenue / units, units, row[start+3], revenue, row[start+5], row[start+6], row[start+7], row[start+8], row[start+9], row[start+10], row[start+11], row[start+12])

def fetch_product_economics(config: DatabaseConfig) -> list[ProductEconomics]:
    try:
        with open_read_only_connection(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(PRODUCT_ECONOMICS_QUERY); rows = cursor.fetchall()
    except DatabaseError: raise
    except Exception as error: raise DatabaseError("Read-only delivery economics query failed") from error
    grouped: dict[str, dict[str, object]] = defaultdict(lambda: {"windows": [], "issues": []})
    for row in rows:
        item = grouped[row[0]]; item["current_price"], item["current_since"], item["cost"] = row[1], row[2], row[3]
        if row[4] is not None:
            item["windows"].append(_window(row, 4))
            if row[17]: item["issues"].append("unallocated_other_expenses")
        if row[18] is not None and "last" not in item:
            item["last"] = PriceWindow(None, row[20] / row[18], row[18], row[19], row[20], row[21], row[22], row[23], row[24], row[25], row[26], row[27], row[28])
    return [ProductEconomics(offer_id, value.get("current_price"), value.get("current_since"), value.get("cost"), tuple(value["windows"]), value.get("last"), tuple(sorted(set(value["issues"])))) for offer_id, value in sorted(grouped.items())]


def fetch_anomaly_economics(config: DatabaseConfig) -> dict[str, dict[str, PeriodEconomics]]:
    try:
        with open_read_only_connection(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(ANOMALY_ECONOMICS_QUERY); rows = cursor.fetchall()
    except DatabaseError: raise
    except Exception as error: raise DatabaseError("Read-only anomaly economics query failed") from error
    result: dict[str, dict[str, PeriodEconomics]] = defaultdict(dict)
    for row in rows:
        offer_id, name = row[0], row[1]
        if name is not None:
            result[offer_id][name] = PeriodEconomics(*row[2:])
        else:
            result.setdefault(offer_id, {})
    return dict(result)


def fetch_promotion_states(config: DatabaseConfig) -> list[PromotionState]:
    try:
        with open_read_only_connection(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(PROMOTION_MONITORING_QUERY)
                rows = cursor.fetchall()
    except DatabaseError:
        raise
    except Exception as error:
        raise DatabaseError("Read-only promotion monitoring query failed") from error
    return [PromotionState(*row, ()) for row in rows]


def fetch_calculator_source_rows(
    config: DatabaseConfig,
    offer_ids: Collection[str],
) -> list[CalculatorSourceRow]:
    requested_offer_ids = tuple(sorted(set(offer_ids)))
    if not requested_offer_ids:
        return []
    try:
        with open_read_only_connection(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(CALCULATOR_SOURCE_QUERY, (list(requested_offer_ids),))
                rows = cursor.fetchall()
    except DatabaseError:
        raise
    except Exception as error:
        raise DatabaseError("Read-only calculator source query failed") from error
    return [
        CalculatorSourceRow(
            offer_id=row[0],
            product_id=row[1],
            seller_price=row[2],
            cost_price=row[3],
            price_observed_at=row[4],
            price_checked_at=row[5],
            snapshot_id=str(row[6]) if row[6] is not None else None,
            price_collection_run_id=str(row[7]) if row[7] is not None else None,
            snapshot_product_id=row[8],
            snapshot_offer_id=row[9],
            observed_at=row[10],
            run_status=row[11],
            sales_percent_fbs=row[12],
            fbs_deliv_to_customer_amount=row[13],
            raw_acquiring=row[14],
            direct_flow_min=row[15],
            direct_flow_max=row[16],
            raw_return_flow=row[17],
        )
        for row in rows
    ]


def fetch_latest_product_cpc_observations(
    config: DatabaseConfig,
    offer_ids: Collection[str],
) -> list[CpcObservation]:
    requested_offer_ids = tuple(sorted(set(offer_ids)))
    if not requested_offer_ids:
        return []
    try:
        with open_read_only_connection(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    CPC_LATEST_PRODUCT_QUERY,
                    (list(requested_offer_ids),),
                )
                rows = cursor.fetchall()
    except DatabaseError:
        raise
    except Exception as error:
        raise DatabaseError("Read-only product CPC query failed") from error
    return [CpcObservation(*row) for row in rows]
