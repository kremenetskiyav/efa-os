"""Pure input-resolution tests for EFA Ozon Price Calculator V1."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from config import load_price_calculator_config
from input_resolver import (
    CalculatorSourceRow,
    InputResolutionError,
    resolve_calculator_inputs,
)


D = Decimal
ROOT = Path(__file__).parents[3]
CONFIG = load_price_calculator_config(ROOT / "config/ozon_price_calculator_v1.json")
CALCULATION_AT = datetime(2026, 8, 29, 9, 0, tzinfo=timezone(timedelta(hours=3)))


def source_row(offer_id: str = "УФ 001Б", **changes) -> CalculatorSourceRow:
    product_id = 4861934525 if offer_id == "УФ 001Б" else 4861934527
    values = {
        "offer_id": offer_id,
        "product_id": product_id,
        "seller_price": D("910"),
        "cost_price": D("166"),
        "price_observed_at": CALCULATION_AT - timedelta(hours=2),
        "price_checked_at": CALCULATION_AT - timedelta(hours=1),
        "snapshot_id": "snapshot-1",
        "price_collection_run_id": "run-1",
        "snapshot_product_id": product_id,
        "snapshot_offer_id": offer_id,
        "observed_at": CALCULATION_AT - timedelta(hours=1),
        "run_status": "success",
        "sales_percent_fbs": D("47"),
        "fbs_deliv_to_customer_amount": D("25"),
        "raw_acquiring": D("6.24"),
        "direct_flow_min": D("74"),
        "direct_flow_max": D("218"),
        "raw_return_flow": D("218"),
    }
    values.update(changes)
    return CalculatorSourceRow(**values)


def resolve(source: CalculatorSourceRow | None = None, **changes):
    values = {
        "source": source or source_row(),
        "config": CONFIG,
        "tax_rate": D("0.06"),
        "calculation_at": CALCULATION_AT,
        "taxpayer_config_version": "v0.1",
    }
    values.update(changes)
    return resolve_calculator_inputs(**values)


class InputResolverTests(unittest.TestCase):
    def test_fresh_ozon_price_replaces_stale_products_price(self):
        stale_products_price = D("910")
        result = resolve(source_row(seller_price=D("1290")))

        self.assertNotEqual(result.seller_price, stale_products_price)
        self.assertEqual(result.seller_price, D("1290"))
        self.assertEqual(
            result.provenance["seller_price"],
            "mcp_read.product_overview.current_price",
        )

    def test_golden_resolution_applies_policy_once_and_ignores_raw_diagnostics(self):
        result = resolve()

        self.assertEqual(result.commission_rate, D("0.44"))
        self.assertEqual(result.acquiring_rate, D("0.015"))
        self.assertEqual(result.processing_amount, D("10"))
        self.assertEqual(result.forward_logistics_amount, D("95"))
        self.assertEqual(result.delivery_to_customer_amount, D("25"))
        self.assertEqual(result.return_logistics_amount, D("95"))
        self.assertEqual(result.return_processing_amount, D("15"))
        self.assertEqual(result.buyout_rate, D("0.92"))
        self.assertEqual(result.tax_rate, D("0.06"))
        self.assertEqual(result.other_expenses, D("0"))
        self.assertEqual(result.calculator_config_version, "v1.1")
        self.assertEqual(result.tariff_profile_version, "2026-08-28-revision-2026-08-24")
        self.assertEqual(result.taxpayer_config_version, "v0.1")

    def test_uf003_uses_approved_forward_for_both_flows(self):
        result = resolve(source_row("УФ 003Б"))

        self.assertEqual(result.forward_logistics_amount, D("88"))
        self.assertEqual(result.return_logistics_amount, D("88"))

    def test_snapshot_presence_status_identity_and_freshness_fail_closed(self):
        invalid_sources = (
            source_row(snapshot_id=None),
            source_row(run_status="running"),
            source_row(snapshot_product_id=1),
            source_row(snapshot_offer_id="УФ 002Б"),
            source_row(observed_at=CALCULATION_AT - timedelta(hours=12, seconds=1)),
            source_row(observed_at=CALCULATION_AT + timedelta(seconds=1)),
            source_row(observed_at=CALCULATION_AT.replace(tzinfo=None)),
        )
        for source in invalid_sources:
            with self.subTest(source=source), self.assertRaises(InputResolutionError):
                resolve(source)

        exact_boundary = resolve(
            source_row(observed_at=CALCULATION_AT - timedelta(hours=12))
        )
        self.assertEqual(exact_boundary.observed_at, CALCULATION_AT - timedelta(hours=12))

    def test_price_presence_identity_and_freshness_fail_closed(self):
        invalid_sources = (
            source_row(seller_price=None),
            source_row(price_observed_at=None),
            source_row(price_checked_at=None),
            source_row(price_checked_at=CALCULATION_AT - timedelta(hours=12, seconds=1)),
            source_row(price_checked_at=CALCULATION_AT + timedelta(seconds=1)),
            source_row(price_checked_at=CALCULATION_AT.replace(tzinfo=None)),
            source_row(price_observed_at=CALCULATION_AT + timedelta(seconds=1)),
            source_row(price_observed_at=CALCULATION_AT.replace(tzinfo=None)),
            source_row(
                price_observed_at=CALCULATION_AT - timedelta(minutes=30),
                price_checked_at=CALCULATION_AT - timedelta(hours=1),
            ),
        )
        for source in invalid_sources:
            with self.subTest(source=source), self.assertRaises(InputResolutionError):
                resolve(source)

        exact_boundary = resolve(
            source_row(
                price_observed_at=CALCULATION_AT - timedelta(hours=12),
                price_checked_at=CALCULATION_AT - timedelta(hours=12),
            )
        )
        self.assertEqual(
            exact_boundary.price_checked_at,
            CALCULATION_AT - timedelta(hours=12),
        )

    def test_price_cost_commission_delivery_and_profile_fail_closed(self):
        invalid_sources = (
            source_row(seller_price=D("0")),
            source_row(seller_price=D("300")),
            source_row(cost_price=None),
            source_row(cost_price=D("-1")),
            source_row(sales_percent_fbs=D("-1")),
            source_row(sales_percent_fbs=D("101")),
            source_row(fbs_deliv_to_customer_amount=None),
            source_row(fbs_deliv_to_customer_amount=D("-1")),
            source_row("УФ 999Б"),
        )
        for source in invalid_sources:
            with self.subTest(source=source), self.assertRaises(InputResolutionError):
                resolve(source)

        invalid_adjustment_config = replace(CONFIG, recommended_slot_adjustment_pp=D("-48"))
        with self.assertRaises(InputResolutionError):
            resolve(config=invalid_adjustment_config)

    def test_config_tariff_time_and_tax_fail_closed(self):
        with self.assertRaises(InputResolutionError):
            resolve(calculation_at=CALCULATION_AT.replace(tzinfo=None))
        with self.assertRaises(InputResolutionError):
            resolve(calculation_at=CONFIG.effective_from - timedelta(seconds=1))

        future_profile = replace(
            CONFIG.logistics_profile,
            tariff_effective_from=CALCULATION_AT.date() + timedelta(days=1),
        )
        with self.assertRaises(InputResolutionError):
            resolve(config=replace(CONFIG, logistics_profile=future_profile))

        for tax_rate in (D("-0.01"), D("1.01"), D("NaN")):
            with self.subTest(tax_rate=tax_rate), self.assertRaises(InputResolutionError):
                resolve(tax_rate=tax_rate)


if __name__ == "__main__":
    unittest.main()
