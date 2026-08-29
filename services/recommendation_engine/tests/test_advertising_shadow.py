"""Function-level tests for the read-only CPC overlay shadow."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from advertising_overlay import CpcObservation
from advertising_shadow import generate_advertising_shadow_report
from config import DatabaseConfig, load_price_calculator_config
from input_resolver import CalculatorSourceRow


D = Decimal
ROOT = Path(__file__).parents[3]
CONFIG = load_price_calculator_config(ROOT / "config/ozon_price_calculator_v1.json")
CALCULATION_AT = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
SELLER_PRICES = {
    "УФ 001Б": D("1290"),
    "УФ 002Б": D("1350"),
    "УФ 003Б": D("1220"),
    "УФ 004Б": D("1350"),
    "УФ 005Б": D("1290"),
}


def source_row(offer_id: str) -> CalculatorSourceRow:
    suffix = int(offer_id[3:6])
    product_id = 4861934524 + suffix
    fresh_at = CALCULATION_AT - timedelta(hours=1)
    return CalculatorSourceRow(
        offer_id=offer_id,
        product_id=product_id,
        seller_price=SELLER_PRICES[offer_id],
        cost_price=D("166"),
        price_observed_at=fresh_at,
        price_checked_at=fresh_at,
        snapshot_id=f"snapshot-{product_id}",
        price_collection_run_id="run-1",
        snapshot_product_id=product_id,
        snapshot_offer_id=offer_id,
        observed_at=fresh_at,
        run_status="success",
        sales_percent_fbs=D("47"),
        fbs_deliv_to_customer_amount=D("25"),
        raw_acquiring=D("6.24"),
        direct_flow_min=D("74"),
        direct_flow_max=D("218"),
        raw_return_flow=D("218"),
    )


def stale_uf004_observation() -> CpcObservation:
    return CpcObservation(
        business_date=date(2026, 8, 24),
        data_scope="PRODUCT",
        offer_id="УФ 004Б",
        campaigns_count=1,
        active_campaigns_count=0,
        views=0,
        clicks=0,
        ctr_percent=None,
        spend=D("0.00"),
        attributed_orders=1,
        attributed_revenue=D("805.00"),
        product_gmv=D("0.00"),
        drr_percent=D("0.00"),
        general_drr_percent=None,
        average_bid=None,
        data_quality_status="valid",
        collection_status="SUCCESS_NONZERO",
        observed_at=datetime(2026, 8, 25, 4, 40, tzinfo=timezone.utc),
    )


class AdvertisingShadowTests(unittest.TestCase):
    def test_report_separates_core_planning_and_observed_cpc(self):
        calls = []

        def load_sources(database_config, offer_ids):
            calls.append(("core", database_config, tuple(offer_ids)))
            return [source_row(offer_id) for offer_id in offer_ids]

        def load_cpc(database_config, offer_ids):
            calls.append(("cpc", database_config, tuple(offer_ids)))
            return [stale_uf004_observation()]

        report = generate_advertising_shadow_report(
            calculator_config=CONFIG,
            database_config=DatabaseConfig("host", 5432, "db", "user", "password"),
            tax_rate=D("0.06"),
            taxpayer_config_version="v0.1",
            calculation_at=CALCULATION_AT,
            source_loader=load_sources,
            cpc_loader=load_cpc,
        )

        self.assertEqual((report["mode"], report["read_only"]), (
            "ADVERTISING_SHADOW", True
        ))
        self.assertEqual(len(report["items"]), 5)
        self.assertEqual([call[0] for call in calls], ["core", "cpc"])

        golden = next(item for item in report["items"] if item["offer_id"] == "УФ 001Б")
        self.assertEqual(golden["core"]["profit"], "308.78")
        self.assertEqual(
            golden["advertising_planning"]["max_ad_cost_at_target"],
            "115.28",
        )
        scenario = golden["advertising_planning"]["five_percent_scenario"]
        self.assertEqual(scenario["advertising_cost"], "64.50")
        self.assertEqual(scenario["forecast_status"], "SAFE_AT_5_PERCENT")
        self.assertEqual(
            scenario["margin_classification"],
            "TARGET_OR_ABOVE",
        )
        self.assertEqual(
            golden["advertising_observed"],
            {
                "business_date": None,
                "observed_at": None,
                "active_campaigns_count": None,
                "spend": None,
                "attributed_orders": None,
                "attributed_revenue": None,
                "product_gmv": None,
                "drr_percent": None,
                "general_drr_percent": None,
                "average_bid": None,
                "data_quality_status": None,
                "collection_status": None,
                "observed_status": "NO_CPC_DATA",
            },
        )

        uf004 = next(item for item in report["items"] if item["offer_id"] == "УФ 004Б")
        self.assertEqual(uf004["advertising_observed"]["spend"], "0.00")
        self.assertEqual(
            uf004["advertising_observed"]["observed_status"],
            "CPC_DATA_STALE",
        )
        self._assert_no_float_or_decimal(report)

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
