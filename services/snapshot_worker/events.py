"""Pure, read-only PRICE_CHANGED candidate calculation for Snapshot Worker v1.1."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


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
