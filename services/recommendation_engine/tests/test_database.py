"""Guardrails for the read-only v0.2 source query."""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from config import DatabaseConfig
from database import (
    ANOMALY_ECONOMICS_QUERY,
    CALCULATOR_SOURCE_QUERY,
    PRODUCT_ECONOMICS_QUERY,
    PROMOTION_MONITORING_QUERY,
    fetch_calculator_source_rows,
)


class UnitEconomicsQueryTests(unittest.TestCase):
    def test_cost_uses_confirmed_posting_quantity(self) -> None:
        self.assertIn("cost_price * quantity", PRODUCT_ECONOMICS_QUERY)
        self.assertIn("p.status = 'delivered'", PRODUCT_ECONOMICS_QUERY)

    def test_unattributed_advertising_is_not_included(self) -> None:
        self.assertNotIn("OperationMarketplaceCostPerClick", PRODUCT_ECONOMICS_QUERY)
        self.assertNotIn("InsuranceServiceSellerItem", PRODUCT_ECONOMICS_QUERY)
        self.assertNotIn("DisposalOfGoods", PRODUCT_ECONOMICS_QUERY)

    def test_windows_use_observed_effective_revenue_per_unit(self) -> None:
        self.assertIn("SUM(revenue) AS revenue", PRODUCT_ECONOMICS_QUERY)

    def test_price_intervals_use_delivery_not_finance_date(self) -> None:
        self.assertIn("r.delivery_at >= i.price_since", PRODUCT_ECONOMICS_QUERY)
        self.assertNotIn("operation_date >= i.price_since", PRODUCT_ECONOMICS_QUERY)

    def test_anomaly_periods_use_delivery_and_confirmed_financial_view(self) -> None:
        self.assertIn("vw_orders_profit_final", ANOMALY_ECONOMICS_QUERY)
        self.assertIn("delivery_at::date", ANOMALY_ECONOMICS_QUERY)
        self.assertNotIn("operation_date", ANOMALY_ECONOMICS_QUERY)

    def test_promotions_use_only_latest_successful_run(self) -> None:
        self.assertIn("WHERE status = 'success'", PROMOTION_MONITORING_QUERY)
        self.assertIn("LIMIT 1", PROMOTION_MONITORING_QUERY)
        self.assertIn("JOIN latest_successful_run", PROMOTION_MONITORING_QUERY)

    def test_calculator_query_uses_latest_successful_identity_matched_snapshot(self) -> None:
        self.assertIn("FROM ozon_fbs_tariff_snapshots", CALCULATOR_SOURCE_QUERY)
        self.assertIn("JOIN price_collection_runs", CALCULATOR_SOURCE_QUERY)
        self.assertIn("r.status = 'success'", CALCULATOR_SOURCE_QUERY)
        self.assertIn("t.product_id = p.product_id", CALCULATOR_SOURCE_QUERY)
        self.assertIn("t.offer_id = p.offer_id", CALCULATOR_SOURCE_QUERY)
        self.assertIn("ORDER BY t.observed_at DESC", CALCULATOR_SOURCE_QUERY)
        self.assertIn("LIMIT 1", CALCULATOR_SOURCE_QUERY)
        self.assertIn("p.price, p.cost_price", CALCULATOR_SOURCE_QUERY)
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "ALTER ", "DROP "):
            self.assertNotIn(forbidden, CALCULATOR_SOURCE_QUERY.upper())

    def test_calculator_adapter_returns_raw_source_contract(self) -> None:
        observed_at = datetime(2026, 8, 23, 15, 0, tzinfo=timezone.utc)
        rows = [(
            "УФ 001Б", 4861934525, Decimal("910"), Decimal("166"),
            "snapshot-1", "run-1", 4861934525, "УФ 001Б", observed_at,
            "success", Decimal("44"), Decimal("25"), Decimal("6.24"),
            Decimal("74"), Decimal("218"), Decimal("218"),
        )]

        class Cursor:
            def __init__(self):
                self.executed = None

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def execute(self, query, params):
                self.executed = (query, params)

            def fetchall(self):
                return rows

        class Connection:
            def __init__(self, cursor):
                self._cursor = cursor

            def cursor(self):
                return self._cursor

        cursor = Cursor()

        @contextmanager
        def connection_factory(_config):
            yield Connection(cursor)

        with patch("database.open_read_only_connection", side_effect=connection_factory):
            result = fetch_calculator_source_rows(
                DatabaseConfig("host", 5432, "db", "user", "password"),
                {"УФ 001Б"},
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].product_id, 4861934525)
        self.assertEqual(result[0].snapshot_product_id, 4861934525)
        self.assertEqual(result[0].sales_percent_fbs, Decimal("44"))
        self.assertEqual(result[0].raw_acquiring, Decimal("6.24"))
        self.assertEqual(cursor.executed[0], CALCULATOR_SOURCE_QUERY)
        self.assertEqual(cursor.executed[1], (["УФ 001Б"],))
