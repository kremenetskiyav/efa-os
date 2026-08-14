"""Unit tests for pure PRICE_CHANGED candidate calculation."""

from datetime import date
from decimal import Decimal
import unittest
from uuid import UUID

from events import (
    ProductSnapshotState,
    build_event_idempotency_key,
    build_price_change_candidate,
    build_price_change_event,
    evaluate_price_change,
)


OLD_ID = UUID("11111111-1111-1111-1111-111111111111")
NEW_ID = UUID("22222222-2222-2222-2222-222222222222")


def snapshot(
    snapshot_id: UUID,
    price: str | None,
    *,
    quality: str = "valid",
) -> ProductSnapshotState:
    return ProductSnapshotState(
        snapshot_id=snapshot_id,
        offer_id="УФ 005Б",
        business_date=date(2026, 8, 15),
        current_price=None if price is None else Decimal(price),
        data_quality_status=quality,
    )


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


class ProductSnapshotEventLayerTests(unittest.TestCase):
    """Verify Event Layer comparisons use modelled product snapshots."""

    def test_previous_valid_snapshot_absent_creates_no_event(self) -> None:
        self.assertIsNone(build_price_change_event(None, snapshot(NEW_ID, "667")))

    def test_901_to_667_snapshots_create_high_event(self) -> None:
        event = build_price_change_event(
            snapshot(OLD_ID, "901"),
            snapshot(NEW_ID, "667"),
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.old_snapshot_id, OLD_ID)
        self.assertEqual(event.new_snapshot_id, NEW_ID)
        self.assertEqual(event.absolute_change, Decimal("-234.00"))
        self.assertEqual(event.change_percent, Decimal("-25.97"))
        self.assertEqual(event.severity, "high")

    def test_identical_snapshot_prices_create_no_event(self) -> None:
        self.assertIsNone(
            build_price_change_event(
                snapshot(OLD_ID, "667"), snapshot(NEW_ID, "667")
            )
        )

    def test_snapshot_change_below_threshold_creates_no_event(self) -> None:
        self.assertIsNone(
            build_price_change_event(
                snapshot(OLD_ID, "667"), snapshot(NEW_ID, "680")
            )
        )

    def test_invalid_snapshot_is_ignored(self) -> None:
        self.assertIsNone(
            build_price_change_event(
                snapshot(OLD_ID, "901"),
                snapshot(NEW_ID, "667", quality="invalid"),
            )
        )

    def test_event_key_is_deterministic_for_snapshot_pair(self) -> None:
        first = build_event_idempotency_key(
            offer_id="УФ 005Б",
            old_snapshot_id=OLD_ID,
            new_snapshot_id=NEW_ID,
        )
        second = build_event_idempotency_key(
            offer_id="УФ 005Б",
            old_snapshot_id=OLD_ID,
            new_snapshot_id=NEW_ID,
        )
        self.assertEqual(first, second)

    def test_snapshot_cannot_compare_with_itself(self) -> None:
        state = snapshot(OLD_ID, "667")
        self.assertIsNone(build_price_change_event(state, state))


if __name__ == "__main__":
    unittest.main()
