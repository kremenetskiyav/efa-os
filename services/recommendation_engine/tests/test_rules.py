from datetime import datetime
from decimal import Decimal
import unittest

from config import RecommendationConfig
from models import PriceWindow, ProductEconomics
from rules import build_recommendation

CONFIG = RecommendationConfig(Decimal("15"), 10, Decimal("20"))

def window(price: str, profit: str, *, units: int = 12, end: int = 2) -> PriceWindow:
    revenue = Decimal(price) * units
    return PriceWindow(Decimal(price), units, units, revenue, Decimal("-20") * units, Decimal("-10") * units, Decimal("0"), Decimal("40") * units, Decimal("0"), Decimal(profit) * units, datetime(2026, 8, 1), datetime(2026, 8, end))

def product(*windows: PriceWindow, issues: tuple[str, ...] = ()) -> ProductEconomics:
    return ProductEconomics("УФ 005Б", Decimal("100"), Decimal("40"), windows, issues)

class RulesV2Tests(unittest.TestCase):
    def test_review_for_quality_gate(self) -> None:
        result = build_recommendation(product(window("80", "10"), issues=("unallocated_other_expenses",)), CONFIG)
        self.assertEqual(result.action, "REVIEW_DATA")

    def test_keep_with_adequate_current_window(self) -> None:
        result = build_recommendation(product(window("100", "20")), CONFIG)
        self.assertEqual((result.action, result.proposed_price), ("KEEP", None))

    def test_raise_uses_only_observed_better_price(self) -> None:
        result = build_recommendation(product(window("100", "10", end=2), window("110", "20", end=1)), CONFIG)
        self.assertEqual((result.action, result.proposed_price), ("CONSIDER_RAISE", Decimal("110")))

    def test_lower_requires_better_observed_economics(self) -> None:
        result = build_recommendation(product(window("100", "10", end=2), window("90", "20", end=1)), CONFIG)
        self.assertEqual((result.action, result.proposed_price), ("CONSIDER_LOWER", Decimal("90")))

    def test_no_extrapolation_when_step_exceeds_limit(self) -> None:
        result = build_recommendation(product(window("100", "10", end=2), window("150", "30", end=1)), CONFIG)
        self.assertIsNone(result.proposed_price)
        self.assertEqual(result.action, "CONSIDER_RAISE")

    def test_low_sample_never_becomes_numeric_candidate(self) -> None:
        result = build_recommendation(product(window("100", "10", end=2), window("110", "30", units=2, end=1)), CONFIG)
        self.assertIsNone(result.proposed_price)
