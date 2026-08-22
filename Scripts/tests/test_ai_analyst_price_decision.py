import sys
import types
import unittest
from collections import defaultdict
from datetime import date
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

try:
    import asyncpg  # noqa: F401
except ModuleNotFoundError:
    sys.modules["asyncpg"] = types.ModuleType("asyncpg")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_analyst_v1 as analyst  # noqa: E402


AS_OF = date(2026, 8, 20)


def product(
    *,
    current_price: str,
    actual_price: str,
    profit: str,
    confirmed_units: int,
    rank: int,
    active_price: str | None = None,
    active_mode: str = "MANUAL",
    sales_change: Decimal | None = None,
) -> dict:
    period = analyst._empty_period()
    revenue = Decimal(actual_price) * confirmed_units
    period_profit = Decimal(profit)
    period.update(
        {
            "days": {date(2026, 8, day) for day in range(15, 21)},
            "units": Decimal("12") if rank == 1 else Decimal("5"),
            "delivered": Decimal(confirmed_units),
            "matched": Decimal(confirmed_units),
            "net_sold": Decimal(confirmed_units),
            "confirmed_revenue": revenue,
            "commission": Decimal(actual_price) * Decimal("0.20") * confirmed_units,
            "logistics": Decimal("100") * confirmed_units,
            "cost": (
                revenue
                - Decimal(actual_price) * Decimal("0.20") * confirmed_units
                - Decimal("100") * confirmed_units
                - period_profit
            ),
            "profit": period_profit,
            "profit_per_unit": period_profit / confirmed_units if confirmed_units else None,
            "profit_margin_percent": (
                (period_profit / revenue * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_DOWN
                )
                if revenue
                else None
            ),
            "economics_loaded": True,
        }
    )
    active = [] if active_price is None else [{"promotion_price": Decimal(active_price), "add_mode": active_mode}]
    return {
        "current_price": Decimal(current_price),
        "price_checked_at": AS_OF,
        "stock_snapshot_at": AS_OF,
        "stock_data_quality_status": "VALID",
        "total_present": 300,
        "performance": {"current": period, "previous": analyst._empty_period()},
        "promotions": {"active": active, "candidates": [], "observed_at": AS_OF},
        "logistics": {},
        "sales_rank": rank,
        "sales_product_count": 5,
        "sales_change": sales_change,
        "daily": {"signal": "НАБЛЮДАТЬ", "yesterday": None, "day_before": None},
    }


class PriceDecisionTests(unittest.TestCase):
    def test_period_economics_mapping_uses_range_function_fields(self):
        periods = defaultdict(
            lambda: {"current": analyst._empty_period(), "previous": analyst._empty_period()}
        )
        analyst._apply_period_economics(
            periods,
            [{
                "offer_id": "УФ 003Б",
                "delivered_units": 1,
                "returned_units": 0,
                "net_sold_units": 1,
                "gross_sales": Decimal("599"),
                "commission": Decimal("251.58"),
                "acquiring": Decimal("37.14"),
                "services": Decimal("127.36"),
                "return_operations": Decimal("0"),
                "cogs": Decimal("158"),
                "profit_before_tax": Decimal("24.92"),
                "profit_per_unit": Decimal("24.9200"),
                "margin_before_tax": Decimal("4.16"),
            }],
            "current",
        )

        economics = analyst._economics(periods["УФ 003Б"]["current"])

        self.assertEqual(economics["profit"], Decimal("24.92"))
        self.assertEqual(economics["profit_per_unit"], Decimal("24.9200"))
        self.assertEqual(economics["margin"], Decimal("4.16"))
        self.assertEqual(periods["УФ 003Б"]["current"]["other_expenses"], Decimal("37.14"))

    def test_uf001_fixed_promo_uses_reconciled_economics(self):
        item = product(
            current_price="757",
            actual_price="624",
            profit="193.54",
            confirmed_units=3,
            rank=2,
            active_price="624",
        )

        decision = analyst._commercial_recommendation(item, AS_OF)

        self.assertEqual(decision["price"], "ОСТАВИТЬ")
        self.assertEqual(decision["test_price"], Decimal("757"))
        self.assertEqual(decision["promotion"], "ОСТАВИТЬ")
        self.assertEqual(decision["actual_price"], Decimal("624"))
        self.assertEqual(decision["margin"], Decimal("10.33"))
        self.assertEqual(decision["confidence"], "ВЫСОКАЯ")

    def test_incomplete_previous_window_does_not_block_strong_sku_test(self):
        item = product(
            current_price="697",
            actual_price="697",
            profit="140",
            confirmed_units=1,
            rank=1,
        )

        decision = analyst._commercial_recommendation(item, AS_OF)

        self.assertEqual(decision["price"], "ПОДНЯТЬ")
        self.assertEqual(decision["test_price"], Decimal("720"))
        self.assertEqual(decision["confidence"], "НИЗКАЯ")

    def test_confirmed_demand_drop_can_lower_only_above_margin_floor(self):
        item = product(
            current_price="700",
            actual_price="700",
            profit="210",
            confirmed_units=2,
            rank=5,
            sales_change=Decimal("-40"),
        )

        decision = analyst._commercial_recommendation(item, AS_OF)

        self.assertEqual(decision["price"], "СНИЗИТЬ")
        self.assertEqual(decision["test_price"], Decimal("680"))
        self.assertGreaterEqual(decision["test_margin"], analyst.MIN_MARGIN_PERCENT)
        self.assertEqual(decision["confidence"], "СРЕДНЯЯ")

    def test_zero_confirmed_deliveries_holds_with_unavailable_confidence(self):
        item = product(
            current_price="667",
            actual_price="667",
            profit="0",
            confirmed_units=0,
            rank=3,
        )

        decision = analyst._commercial_recommendation(item, AS_OF)

        self.assertEqual(decision["price"], "ОСТАВИТЬ")
        self.assertEqual(decision["confidence"], "Н/Д")
        self.assertIsNone(decision["margin"])

    def test_candidate_promo_uses_ten_percent_estimated_margin_floor(self):
        item = product(
            current_price="700",
            actual_price="700",
            profit="210",
            confirmed_units=2,
            rank=4,
        )
        item["promotions"]["candidates"] = [
            {
                "observed_price": Decimal("700"),
                "promotion_price": Decimal("650"),
                "max_promotion_price": Decimal("700"),
            }
        ]
        self.assertEqual(analyst._commercial_recommendation(item, AS_OF)["promotion"], "ВОЙТИ")

        item["promotions"]["candidates"][0]["promotion_price"] = Decimal("645")
        self.assertEqual(analyst._commercial_recommendation(item, AS_OF)["promotion"], "НЕ ВХОДИТЬ")

    def test_partial_window_uses_confirmed_subset_and_marks_confidence(self):
        item = product(
            current_price="700",
            actual_price="700",
            profit="210",
            confirmed_units=2,
            rank=4,
        )
        period = item["performance"]["current"]
        period["delivered"] = Decimal("3")
        period["unmatched"] = Decimal("1")

        decision = analyst._commercial_recommendation(item, AS_OF)

        self.assertEqual(decision["confidence"], "СРЕДНЯЯ")
        self.assertEqual(decision["margin"], Decimal("15.0"))
        self.assertTrue(decision["partial_economics"])

    def test_low_margin_raise_never_exceeds_five_percent(self):
        item = product(
            current_price="757",
            actual_price="757",
            profit="50",
            confirmed_units=1,
            rank=4,
        )

        decision = analyst._commercial_recommendation(item, AS_OF)

        self.assertEqual(decision["price"], "ПОДНЯТЬ")
        self.assertEqual(decision["test_price"], Decimal("790"))
        self.assertLessEqual(decision["delta_percent"], analyst.MAX_PRICE_STEP_PERCENT)

    def test_unconfirmed_manual_promo_blocks_base_raise(self):
        item = product(
            current_price="700",
            actual_price="700",
            profit="210",
            confirmed_units=1,
            rank=1,
            active_price="650",
            active_mode="MANUAL",
        )

        decision = analyst._commercial_recommendation(item, AS_OF)

        self.assertEqual(decision["price"], "ОСТАВИТЬ")
        self.assertEqual(decision["promotion"], "ОСТАВИТЬ")

    def test_auto_promo_requires_confirmed_price_limit_for_base_test(self):
        item = product(
            current_price="700",
            actual_price="700",
            profit="210",
            confirmed_units=1,
            rank=1,
            active_price="650",
            active_mode="AUTO",
        )
        self.assertEqual(analyst._commercial_recommendation(item, AS_OF)["price"], "ОСТАВИТЬ")

        item["promotions"]["active"][0]["max_promotion_price"] = Decimal("800")
        decision = analyst._commercial_recommendation(item, AS_OF)
        self.assertEqual(decision["price"], "ПОДНЯТЬ")
        self.assertEqual(decision["test_price"], Decimal("720"))


if __name__ == "__main__":
    unittest.main()
