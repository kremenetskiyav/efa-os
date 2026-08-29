"""Phase 2A contract tests for Calculator V1 config and tariff snapshot DDL."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from config import (
    APPROVED_CALCULATOR_OFFER_IDS,
    ConfigurationError,
    load_price_calculator_config,
)


ROOT = Path(__file__).parents[3]
CONFIG_PATH = ROOT / "config/ozon_price_calculator_v1.json"
MIGRATION_PATH = ROOT / "database/migrations/016_ozon_fbs_tariff_snapshots_v1.sql"


def approved_raw() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_modified(update) -> object:
    value = deepcopy(approved_raw())
    update(value)
    with TemporaryDirectory() as directory:
        path = Path(directory) / "calculator.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return load_price_calculator_config(path)


class PriceCalculatorConfigTests(unittest.TestCase):
    def test_approved_config_loads_as_exact_immutable_values(self) -> None:
        config = load_price_calculator_config(CONFIG_PATH)

        self.assertEqual(config.version, "v1.1")
        self.assertEqual(
            config.effective_from,
            datetime(2026, 8, 28, 0, 0, tzinfo=timezone(timedelta(hours=3))),
        )
        self.assertEqual(
            config.logistics_profile.tariff_version,
            "2026-08-28-revision-2026-08-24",
        )
        self.assertEqual(config.logistics_profile.tariff_effective_from, date(2026, 8, 28))
        self.assertEqual(config.recommended_slot_adjustment_pp, Decimal("-3"))
        self.assertEqual(set(config.logistics_profile.products), APPROVED_CALCULATOR_OFFER_IDS)
        self.assertEqual(
            {
                offer_id: product.forward_logistics_amount
                for offer_id, product in config.logistics_profile.products.items()
            },
            {
                "УФ 001Б": Decimal("95"),
                "УФ 002Б": Decimal("95"),
                "УФ 003Б": Decimal("88"),
                "УФ 004Б": Decimal("95"),
                "УФ 005Б": Decimal("95"),
            },
        )
        with self.assertRaises(TypeError):
            config.logistics_profile.products["УФ 006Б"] = config.logistics_profile.products["УФ 001Б"]

    def test_unknown_and_missing_fields_are_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_modified(lambda value: value.update({"unexpected": "x"}))

        def remove_required(value):
            value.pop("buyout_rate")

        with self.assertRaises(ConfigurationError):
            load_modified(remove_required)

    def test_decimal_fields_must_be_strings(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_modified(lambda value: value.update({"buyout_rate": 0.92}))

    def test_non_finite_decimals_are_rejected(self) -> None:
        for invalid in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(invalid=invalid), self.assertRaises(ConfigurationError):
                load_modified(lambda value, invalid=invalid: value.update({"buyout_rate": invalid}))

    def test_bad_margin_ordering_is_rejected(self) -> None:
        def invalidate(value):
            value["margin_policy"]["working_minimum"] = "0.10"

        with self.assertRaises(ConfigurationError):
            load_modified(invalidate)

    def test_invalid_buyout_rate_is_rejected(self) -> None:
        for invalid in ("0", "1.01"):
            with self.subTest(invalid=invalid), self.assertRaises(ConfigurationError):
                load_modified(lambda value, invalid=invalid: value.update({"buyout_rate": invalid}))

    def test_negative_money_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_modified(lambda value: value.update({"processing_amount": "-0.01"}))

    def test_unknown_scheme_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_modified(lambda value: value.update({"scheme": "FBO"}))

    def test_unsupported_return_scenario_is_rejected(self) -> None:
        def invalidate(value):
            value["logistics_profile"]["route"]["return_scenario"] = "return_to_warehouse"

        with self.assertRaises(ConfigurationError):
            load_modified(invalidate)

    def test_unknown_missing_and_empty_offer_ids_are_rejected(self) -> None:
        def remove_offer(value):
            value["logistics_profile"]["products"].pop("УФ 005Б")

        def add_unknown(value):
            value["logistics_profile"]["products"]["УФ 006Б"] = {
                "volume_l": "1",
                "forward_logistics_amount": "1",
            }

        def add_empty(value):
            value["logistics_profile"]["products"].pop("УФ 005Б")
            value["logistics_profile"]["products"][""] = {
                "volume_l": "1",
                "forward_logistics_amount": "1",
            }

        for mutation in (remove_offer, add_unknown, add_empty):
            with self.subTest(mutation=mutation.__name__), self.assertRaises(ConfigurationError):
                load_modified(mutation)

    def test_non_positive_volume_is_rejected(self) -> None:
        def invalidate(value):
            value["logistics_profile"]["products"]["УФ 001Б"]["volume_l"] = "0"

        with self.assertRaises(ConfigurationError):
            load_modified(invalidate)

    def test_invalid_seller_price_band_is_rejected(self) -> None:
        def invalidate(value):
            value["logistics_profile"]["seller_price_band"]["upper_inclusive"] = "300"

        with self.assertRaises(ConfigurationError):
            load_modified(invalidate)


class TariffSnapshotMigrationTests(unittest.TestCase):
    def test_migration_number_is_unique_and_next_in_order(self) -> None:
        migrations = sorted(path.name for path in MIGRATION_PATH.parent.glob("*.sql"))
        self.assertEqual([name for name in migrations if name.startswith("016_")], [MIGRATION_PATH.name])
        self.assertTrue(any(name.startswith("015_") for name in migrations))

    def test_migration_contains_minimal_immutable_observation_contract(self) -> None:
        migration = MIGRATION_PATH.read_text(encoding="utf-8")
        required = (
            "CREATE TABLE ozon_fbs_tariff_snapshots",
            "snapshot_id uuid PRIMARY KEY",
            "price_collection_run_id uuid NOT NULL",
            "REFERENCES price_collection_runs(run_id) ON DELETE RESTRICT",
            "product_id bigint NOT NULL",
            "offer_id text NOT NULL REFERENCES products(offer_id) ON DELETE RESTRICT",
            "observed_at timestamptz NOT NULL",
            "sales_percent_fbs numeric NOT NULL",
            "sales_percent_fbs >= 0 AND sales_percent_fbs <= 100",
            "fbs_deliv_to_customer_amount numeric NOT NULL",
            "fbs_deliv_to_customer_amount >= 0",
            "acquiring numeric",
            "acquiring IS NULL OR acquiring >= 0",
            "fbs_direct_flow_trans_min_amount numeric",
            "fbs_direct_flow_trans_max_amount numeric",
            "fbs_return_flow_amount numeric",
            "fbs_return_flow_amount IS NULL OR fbs_return_flow_amount >= 0",
            "created_at timestamptz NOT NULL DEFAULT now()",
            "UNIQUE (price_collection_run_id, product_id)",
            "fbs_direct_flow_trans_min_amount <= fbs_direct_flow_trans_max_amount",
            "NOT change-only history",
            "one row per product on every successful price collection",
            "(product_id, observed_at DESC)",
        )
        for expected in required:
            with self.subTest(expected=expected):
                self.assertIn(expected, migration)

        for forbidden in (
            "volume_weight",
            "first_mile",
            "seller_price",
            "cost_price",
            "effective_commission",
            "selected_forward_logistics",
            "selected_return_logistics",
            "calculator_result",
            "config_version",
            "raw_json",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, migration)


if __name__ == "__main__":
    unittest.main()
