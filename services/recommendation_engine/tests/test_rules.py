"""Unit tests for conservative, deterministic recommendation rules."""

from datetime import datetime
from decimal import Decimal
import unittest

from config import RecommendationConfig
from models import ProductEconomics
from rules import build_recommendation


CONFIG = RecommendationConfig(low_margin_percent=Decimal("15"))


def economics(**overrides: object) -> ProductEconomics:
    values: dict[str, object] = {"offer_id": "УФ 005Б", "current_price": Decimal("667"), "cost_price": Decimal("166"), "revenue": Decimal("1000"), "profit": Decimal("200"), "commission": Decimal("-300"), "logistics": Decimal("-100"), "period_start": datetime(2026, 8, 1), "period_end": datetime(2026, 8, 13), "delivered_units": 10, "analytics_revenue": Decimal("1000"), "analytics_profit": Decimal("200")}
    values.update(overrides)
    return ProductEconomics(**values)  # type: ignore[arg-type]


class RecommendationRuleTests(unittest.TestCase):
    def test_negative_profit_is_high_priority_consider_raise(self) -> None:
        result = build_recommendation(economics(profit=Decimal("-1"), analytics_profit=Decimal("-1")), CONFIG)
        self.assertEqual((result.action, result.priority), ("CONSIDER_RAISE", "high"))

    def test_low_margin_considers_raise(self) -> None:
        result = build_recommendation(economics(profit=Decimal("100"), analytics_profit=Decimal("100")), CONFIG)
        self.assertEqual((result.action, result.priority), ("CONSIDER_RAISE", "medium"))

    def test_normal_margin_keeps_price(self) -> None:
        result = build_recommendation(economics(), CONFIG)
        self.assertEqual((result.action, result.priority), ("KEEP", "low"))
        self.assertEqual(result.profit_per_unit, Decimal("20.00"))

    def test_missing_data_requires_review(self) -> None:
        result = build_recommendation(economics(current_price=None), CONFIG)
        self.assertEqual(result.action, "REVIEW_DATA")
        self.assertIn("missing_current_price", result.reasons)

    def test_zero_units_requires_review_and_no_profit_per_unit(self) -> None:
        result = build_recommendation(economics(delivered_units=0), CONFIG)
        self.assertEqual(result.action, "REVIEW_DATA")
        self.assertIsNone(result.profit_per_unit)

    def test_conflicting_confirmed_views_require_review(self) -> None:
        result = build_recommendation(economics(analytics_profit=Decimal("199")), CONFIG)
        self.assertEqual(result.action, "REVIEW_DATA")
        self.assertIn("profit_mismatch_between_confirmed_views", result.reasons)

    def test_target_price_stays_null_without_confirmed_variable_cost_model(self) -> None:
        result = build_recommendation(economics(), CONFIG)
        self.assertIsNone(result.proposed_price)
        self.assertIsNone(result.proposed_price_range)
        self.assertIn("no confirmed marginal commission", result.proposal_reason or "")


if __name__ == "__main__":
    unittest.main()
