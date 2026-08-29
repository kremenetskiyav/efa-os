"""Function-level tests for read-only Calculator V1 shadow orchestration."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import unittest

from calculator_shadow import _load_taxpayer_context, generate_shadow_report
from config import DatabaseConfig, load_price_calculator_config
from input_resolver import CalculatorSourceRow, InputResolutionError


D = Decimal
ROOT = Path(__file__).parents[3]
CONFIG = load_price_calculator_config(ROOT / "config/ozon_price_calculator_v1.json")
CALCULATION_AT = datetime(2026, 8, 29, 9, 0, tzinfo=timezone(timedelta(hours=3)))
PRODUCT_IDS = {
    "УФ 001Б": 4861934525,
    "УФ 002Б": 4861934526,
    "УФ 003Б": 4861934527,
    "УФ 004Б": 4861934528,
    "УФ 005Б": 4861934529,
}


def source_row(offer_id: str) -> CalculatorSourceRow:
    product_id = PRODUCT_IDS[offer_id]
    return CalculatorSourceRow(
        offer_id=offer_id,
        product_id=product_id,
        seller_price=D("910"),
        cost_price=D("166"),
        snapshot_id=f"snapshot-{product_id}",
        price_collection_run_id="run-1",
        snapshot_product_id=product_id,
        snapshot_offer_id=offer_id,
        observed_at=CALCULATION_AT - timedelta(hours=1),
        run_status="success",
        sales_percent_fbs=D("47"),
        fbs_deliv_to_customer_amount=D("25"),
        raw_acquiring=D("6.24"),
        direct_flow_min=D("74"),
        direct_flow_max=D("218"),
        raw_return_flow=D("218"),
    )


class CalculatorShadowTests(unittest.TestCase):
    def test_five_item_shadow_report_matches_golden_uf001b(self):
        calls = []

        def load_sources(database_config, offer_ids):
            calls.append((database_config, tuple(offer_ids)))
            return [source_row(offer_id) for offer_id in offer_ids]

        report = generate_shadow_report(
            calculator_config=CONFIG,
            database_config=DatabaseConfig("host", 5432, "db", "user", "password"),
            tax_rate=D("0.06"),
            taxpayer_config_version="v0.1",
            calculation_at=CALCULATION_AT,
            source_loader=load_sources,
        )

        self.assertEqual((report["mode"], report["read_only"]), ("SHADOW", True))
        self.assertEqual(report["calculation_at"], CALCULATION_AT.isoformat())
        self.assertEqual(report["calculator_config_version"], "v1.1")
        self.assertEqual(len(report["items"]), 5)
        self.assertEqual(len(calls), 1)

        golden = next(item for item in report["items"] if item["offer_id"] == "УФ 001Б")
        self.assertEqual(golden["resolved_inputs"], {
            "commission_rate": "0.44",
            "acquiring_rate": "0.015",
            "processing_amount": "10",
            "forward_logistics_amount": "95",
            "delivery_to_customer_amount": "25",
            "return_logistics_amount": "95",
            "return_processing_amount": "15",
            "buyout_rate": "0.92",
            "tax_rate": "0.06",
            "other_expenses": "0",
        })
        self.assertEqual(golden["results"]["profit"], "124.48")
        self.assertTrue(golden["results"]["margin"].startswith("0.136791686574"))
        self.assertEqual(
            (golden["results"]["p10"], golden["results"]["p12"], golden["results"]["p15"]),
            ("824", "869", "946"),
        )
        self.assertEqual(golden["search"], {
            "search_from": "301",
            "search_to": "9100",
            "price_step": "1",
            "ceiling_policy": "technical:current_seller_price_x10",
        })
        uf003 = next(item for item in report["items"] if item["offer_id"] == "УФ 003Б")
        self.assertEqual(
            (
                uf003["resolved_inputs"]["forward_logistics_amount"],
                uf003["resolved_inputs"]["return_logistics_amount"],
            ),
            ("88", "88"),
        )
        self._assert_no_float_or_decimal(report)

    def test_missing_approved_source_fails_closed(self):
        with self.assertRaises(InputResolutionError):
            generate_shadow_report(
                calculator_config=CONFIG,
                database_config=DatabaseConfig("host", 5432, "db", "user", "password"),
                tax_rate=D("0.06"),
                taxpayer_config_version="v0.1",
                calculation_at=CALCULATION_AT,
                source_loader=lambda _config, offer_ids: [
                    source_row(offer_id) for offer_id in tuple(offer_ids)[:-1]
                ],
            )

    def test_existing_taxpayer_loader_supplies_rate_and_version(self):
        services_path = str(ROOT / "services")
        sys.path.insert(0, services_path)
        try:
            tax_rate, version = _load_taxpayer_context(
                ROOT / "config/taxpayer.2026.json", 2026
            )
        finally:
            sys.path.remove(services_path)

        self.assertEqual((tax_rate, version), (D("0.06"), "v0.1"))

    def _assert_no_float_or_decimal(self, value):
        if isinstance(value, dict):
            for nested in value.values():
                self._assert_no_float_or_decimal(nested)
        elif isinstance(value, list):
            for nested in value:
                self._assert_no_float_or_decimal(nested)
        else:
            self.assertNotIsInstance(value, (float, Decimal))


if __name__ == "__main__":
    unittest.main()
