"""Read-only posting-level economics query for Recommendation Engine v0.2."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Iterator

from config import DatabaseConfig
from models import PriceWindow, ProductEconomics


class DatabaseError(RuntimeError):
    pass


# Delivery operations supply revenue/commission/logistics/payout. Quantity comes
# only from delivered postings, so cost is never inferred from an order count.
# Other expenses are included only when one delivered product line owns the
# normalized posting key; CPC, insurance and disposal remain excluded.
PRODUCT_ECONOMICS_QUERY = """
WITH delivered_postings AS (
    SELECT p.posting_number, p.sku, MAX(p.offer_id) AS offer_id,
           MAX(p.quantity) AS quantity
    FROM postings p
    WHERE p.status = 'delivered' AND p.quantity > 0 AND p.offer_id IS NOT NULL
    GROUP BY p.posting_number, p.sku
), delivery_finance AS (
    SELECT f.posting_number, f.sku, MIN(f.operation_date) AS operation_date,
           SUM(f.accruals_for_sale) AS revenue,
           SUM(f.sale_commission) AS commission,
           SUM(f.service_amount) AS logistics,
           SUM(f.amount) AS payout
    FROM finance_operations f
    WHERE f.operation_type = 'OperationAgentDeliveredToCustomer'
      AND f.posting_number IS NOT NULL AND f.sku IS NOT NULL
    GROUP BY f.posting_number, f.sku
), base AS (
    SELECT regexp_replace(d.posting_number, '-[0-9]+$', '') AS posting_key,
           d.posting_number, d.sku, d.offer_id, d.quantity, f.operation_date,
           f.revenue, f.commission, f.logistics, f.payout, p.cost_price
    FROM delivery_finance f
    JOIN delivered_postings d ON d.posting_number = f.posting_number AND d.sku = f.sku
    JOIN products p ON p.offer_id = d.offer_id
), line_counts AS (
    SELECT posting_key, COUNT(*) AS line_count FROM base GROUP BY posting_key
), expense_by_key AS (
    SELECT regexp_replace(f.posting_number, '-[0-9]+$', '') AS posting_key,
           SUM(f.amount) AS other_expenses
    FROM finance_operations f
    WHERE f.operation_type = ANY (ARRAY[
        'OperationReturnGoodsFBSofRMS', 'OperationMarketplacePackageMaterialsProvision',
        'OperationMarketplacePackageRedistribution', 'ClientReturnAgentOperation'
    ]) AND f.posting_number IS NOT NULL
    GROUP BY regexp_replace(f.posting_number, '-[0-9]+$', '')
), unit_rows AS (
    SELECT b.*, CASE WHEN lc.line_count = 1 THEN COALESCE(e.other_expenses, 0) ELSE 0 END AS other_expenses,
           CASE WHEN lc.line_count > 1 AND COALESCE(e.other_expenses, 0) <> 0 THEN 1 ELSE 0 END AS unallocated_expense_line
    FROM base b JOIN line_counts lc USING (posting_key)
    LEFT JOIN expense_by_key e USING (posting_key)
), windows AS (
    SELECT offer_id, ROUND(revenue / NULLIF(quantity, 0), 2) AS effective_price,
           SUM(quantity)::integer AS units, COUNT(DISTINCT posting_number)::integer AS orders,
           SUM(revenue) AS revenue, SUM(commission) AS commission, SUM(logistics) AS logistics,
           SUM(other_expenses) AS other_expenses, SUM(cost_price * quantity) AS cost,
           SUM(payout) AS payout,
           SUM(payout + other_expenses - cost_price * quantity) AS profit,
           MIN(operation_date) AS period_start, MAX(operation_date) AS period_end,
           SUM(unallocated_expense_line)::integer AS unallocated_expense_lines
    FROM unit_rows
    GROUP BY offer_id, ROUND(revenue / NULLIF(quantity, 0), 2)
)
SELECT p.offer_id, lp.price AS current_price, p.cost_price,
       w.effective_price, w.units, w.orders, w.revenue, w.commission, w.logistics,
       w.other_expenses, w.cost, w.payout, w.profit, w.period_start, w.period_end,
       w.unallocated_expense_lines
FROM products p
LEFT JOIN LATERAL (
    SELECT h.price FROM ozon_price_history h
    WHERE h.offer_id = p.offer_id AND h.price IS NOT NULL
    ORDER BY h.updated_from_ozon DESC, h.created_at DESC, h.id DESC LIMIT 1
) lp ON TRUE
LEFT JOIN windows w ON w.offer_id = p.offer_id
ORDER BY p.offer_id, w.period_end, w.effective_price
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
    try:
        with open_read_only_connection(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(PRODUCT_ECONOMICS_QUERY)
                rows = cursor.fetchall()
    except DatabaseError:
        raise
    except Exception as error:
        raise DatabaseError("Read-only unit economics query failed") from error
    grouped: dict[str, dict[str, object]] = defaultdict(lambda: {"windows": [], "issues": []})
    for row in rows:
        record = grouped[row[0]]
        record["current_price"] = row[1]
        record["cost_price"] = row[2]
        if row[3] is None:
            continue
        if row[15]:
            record["issues"].append("unallocated_other_expenses")
        record["windows"].append(PriceWindow(*row[3:15]))
    return [ProductEconomics(offer_id, value.get("current_price"), value.get("cost_price"), tuple(value["windows"]), tuple(sorted(set(value["issues"])))) for offer_id, value in sorted(grouped.items())]
