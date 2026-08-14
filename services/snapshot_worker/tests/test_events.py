"""Unit tests for pure PRICE_CHANGED candidate calculation."""

from decimal import Decimal
import unittest

from events import build_price_change_candidate, evaluate_price_change


class PriceChangedRuleTests(unittest.TestCase):
    """Verify price_change_v1 thresholds without a database connection."""

    def test_901_to_667_is_high(self) -> None:
        candidate = build_price_change_candidate(
            "УФ 005Б", Decimal("901"), Decimal("667")
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.absolute_change, Decimal("-234.00"))
        self.assertEqual(candidate.change_percent, Decimal("-25.97"))
        self.assertEqual(candidate.severity, "high")
        self.assertEqual(candidate.rule_id, "price_change_v1")

    def test_change_below_20_rub_is_not_an_event(self) -> None:
        candidate = build_price_change_candidate("A", Decimal("100"), Decimal("119"))

        self.assertIsNone(candidate)

    def test_change_below_5_percent_is_not_an_event(self) -> None:
        candidate = build_price_change_candidate(
            "A", Decimal("1000"), Decimal("1020")
        )

        self.assertIsNone(candidate)

    def test_change_of_30_percent_is_critical(self) -> None:
        candidate = build_price_change_candidate("A", Decimal("100"), Decimal("70"))

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.change_percent, Decimal("-30.00"))
        self.assertEqual(candidate.severity, "critical")

    def test_identical_price_is_not_an_event(self) -> None:
        candidate = build_price_change_candidate("A", Decimal("100"), Decimal("100"))

        self.assertIsNone(candidate)

    def test_zero_old_price_returns_null_percent_without_event(self) -> None:
        evaluation = evaluate_price_change("A", Decimal("0"), Decimal("100"))

        self.assertIsNone(evaluation.change_percent)
        self.assertFalse(evaluation.is_candidate)


if __name__ == "__main__":
    unittest.main()
