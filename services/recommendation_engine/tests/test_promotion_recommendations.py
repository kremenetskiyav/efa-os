from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from config import RecommendationConfig
from models import PriceWindow, ProductEconomics, PromotionState
from promotion_recommendations import build_promotion_recommendation


NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)
CONFIG = RecommendationConfig(Decimal("15"), 5, Decimal("20"))


def state(source: str = "PARTICIPATING", quality: str = "valid") -> PromotionState:
    return PromotionState("УФ 001Б", 4861934525, 1977747, "Elastic", "ELASTIC_BOOSTING", NOW, None, source, "MANUAL", Decimal("757"), Decimal("624"), Decimal("624"), NOW, quality, ())


def economics(*, current_price: Decimal = Decimal("757"), units: int = 5, profit: Decimal = Decimal("1000")) -> ProductEconomics:
    window = PriceWindow(current_price, Decimal("757"), units, units, Decimal("3785"), Decimal("-700"), Decimal("-100"), Decimal("0"), Decimal("830"), profit + Decimal("830"), profit, NOW, NOW)
    return ProductEconomics("УФ 001Б", current_price, NOW, Decimal("166"), (window,), window)


class PromotionRecommendationTests(unittest.TestCase):
    def test_participating_with_confirmed_economics_without_historical_match_is_review(self):
        result = build_promotion_recommendation(state(), economics(), CONFIG)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIn("no_confirmed_promotion_delivery_economics_match", result.reasons)

    def test_participating_with_confirmed_historical_match_can_keep(self):
        result = build_promotion_recommendation(state(), economics(), CONFIG, historical_promotion_match=True)
        self.assertEqual(result.recommendation, "KEEP")

    def test_candidate_is_not_automatically_consider_join(self):
        result = build_promotion_recommendation(state("CANDIDATE"), economics(), CONFIG)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertNotEqual(result.recommendation, "CONSIDER_JOIN")

    def test_candidate_consider_join_requires_explicit_historical_match_and_safe_margin(self):
        result = build_promotion_recommendation(state("CANDIDATE"), economics(), CONFIG, historical_promotion_match=True)
        self.assertEqual(result.recommendation, "CONSIDER_JOIN")

    def test_participating_consider_leave_requires_historical_match_and_failed_margin_gate(self):
        result = build_promotion_recommendation(state(), economics(profit=Decimal("100")), CONFIG, historical_promotion_match=True)
        self.assertEqual(result.recommendation, "CONSIDER_LEAVE")

    def test_insufficient_sample_is_review(self):
        result = build_promotion_recommendation(state(), economics(units=4), CONFIG)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIn("current_price_economics_not_confirmed", result.reasons)

    def test_data_quality_issue_is_review(self):
        result = build_promotion_recommendation(state(quality="review"), economics(), CONFIG)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertEqual(result.data_quality_status, "review")

    def test_no_numeric_projection_is_ever_returned(self):
        result = build_promotion_recommendation(state(), economics(), CONFIG, historical_promotion_match=True)
        self.assertFalse(result.numeric_projection_allowed)
        self.assertEqual(result.confirmed_profit_per_unit, Decimal("200.00"))

    def test_module_has_no_write_or_ozon_operations(self):
        with open("promotion_recommendations.py", encoding="utf-8") as file:
            source = file.read().lower()
        for forbidden in ("insert ", "update ", "delete ", "requests.", "api-seller"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
