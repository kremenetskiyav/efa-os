"""Pure PRICE_CHANGED rules and event construction for Snapshot Worker v1.3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from uuid import UUID


PRICE_CHANGE_RULE_ID = "price_change_v1"
MINIMUM_ABSOLUTE_CHANGE = Decimal("20")
MINIMUM_PERCENT_CHANGE = Decimal("5")
PERCENT_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class PriceChangeEvaluation:
    """Calculated price movement; severity is set only for an event candidate."""

    offer_id: str
    old_value: Decimal
    new_value: Decimal
    absolute_change: Decimal
    change_percent: Decimal | None
    severity: str | None
    rule_id: str = PRICE_CHANGE_RULE_ID

    @property
    def is_candidate(self) -> bool:
        """Return whether the movement passes every price_change_v1 threshold."""

        return self.severity is not None


@dataclass(frozen=True)
class ProductSnapshotState:
    """The immutable snapshot fields required by the Event Layer."""

    snapshot_id: UUID
    offer_id: str
    business_date: date
    current_price: Decimal | None
    data_quality_status: str


@dataclass(frozen=True)
class PriceChangeEvent:
    """A complete change_events row derived from two valid snapshots."""

    offer_id: str
    business_date: date
    old_snapshot_id: UUID
    new_snapshot_id: UUID
    old_value: Decimal
    new_value: Decimal
    absolute_change: Decimal
    change_percent: Decimal
    severity: str
    idempotency_key: str
    event_type: str = "PRICE_CHANGED"
    metric: str = "current_price"
    rule_id: str = PRICE_CHANGE_RULE_ID
    status: str = "new"


def build_event_idempotency_key(
    *, offer_id: str, old_snapshot_id: UUID, new_snapshot_id: UUID
) -> str:
    """Build a stable key for one rule applied to one ordered snapshot pair."""

    identity = "\x1f".join(
        (
            "PRICE_CHANGED",
            PRICE_CHANGE_RULE_ID,
            offer_id,
            str(old_snapshot_id),
            str(new_snapshot_id),
        )
    )
    return f"price_changed:{sha256(identity.encode('utf-8')).hexdigest()}"


def evaluate_price_change(
    offer_id: str, old_price: Decimal, new_price: Decimal
) -> PriceChangeEvaluation:
    """Evaluate two consecutive prices without side effects or database access."""

    old_value = Decimal(old_price)
    new_value = Decimal(new_price)
    absolute_change = (new_value - old_value).quantize(
        PERCENT_QUANTUM, rounding=ROUND_HALF_UP
    )

    if old_value == 0:
        return PriceChangeEvaluation(
            offer_id=offer_id,
            old_value=old_value,
            new_value=new_value,
            absolute_change=absolute_change,
            change_percent=None,
            severity=None,
        )

    change_percent = ((new_value - old_value) / old_value * Decimal("100")).quantize(
        PERCENT_QUANTUM, rounding=ROUND_HALF_UP
    )
    absolute_percent = abs(change_percent)

    severity: str | None = None
    if (
        abs(absolute_change) >= MINIMUM_ABSOLUTE_CHANGE
        and absolute_percent >= MINIMUM_PERCENT_CHANGE
    ):
        if absolute_percent < Decimal("15"):
            severity = "medium"
        elif absolute_percent < Decimal("30"):
            severity = "high"
        else:
            severity = "critical"

    return PriceChangeEvaluation(
        offer_id=offer_id,
        old_value=old_value,
        new_value=new_value,
        absolute_change=absolute_change,
        change_percent=change_percent,
        severity=severity,
    )


def build_price_change_candidate(
    offer_id: str, old_price: Decimal | None, new_price: Decimal | None
) -> PriceChangeEvaluation | None:
    """Return an event candidate only when two prices pass the v1 rule."""

    if old_price is None or new_price is None:
        return None

    evaluation = evaluate_price_change(offer_id, old_price, new_price)
    return evaluation if evaluation.is_candidate else None


def build_price_change_event(
    previous: ProductSnapshotState | None,
    current: ProductSnapshotState,
) -> PriceChangeEvent | None:
    """Build an event only from two distinct valid snapshots of one product."""

    if previous is None:
        return None
    if previous.snapshot_id == current.snapshot_id:
        return None
    if previous.offer_id != current.offer_id:
        return None
    if (
        previous.data_quality_status != "valid"
        or current.data_quality_status != "valid"
    ):
        return None

    evaluation = build_price_change_candidate(
        current.offer_id,
        previous.current_price,
        current.current_price,
    )
    if evaluation is None or evaluation.change_percent is None:
        return None

    assert evaluation.severity is not None
    return PriceChangeEvent(
        offer_id=current.offer_id,
        business_date=current.business_date,
        old_snapshot_id=previous.snapshot_id,
        new_snapshot_id=current.snapshot_id,
        old_value=evaluation.old_value,
        new_value=evaluation.new_value,
        absolute_change=evaluation.absolute_change,
        change_percent=evaluation.change_percent,
        severity=evaluation.severity,
        idempotency_key=build_event_idempotency_key(
            offer_id=current.offer_id,
            old_snapshot_id=previous.snapshot_id,
            new_snapshot_id=current.snapshot_id,
        ),
    )
