"""Deterministic, conservative price recommendation rules."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from config import RecommendationConfig
from models import ProductEconomics, Recommendation


MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")


def _same_money(left: Decimal | None, right: Decimal | None) -> bool:
    if left is None or right is None:
        return False
    return left.quantize(MONEY_QUANTUM) == right.quantize(MONEY_QUANTUM)


def build_recommendation(economics: ProductEconomics, config: RecommendationConfig) -> Recommendation:
    """Recommend review/raise/keep without inventing a target-price formula."""

    quality_issues: list[str] = []
    required = {
        "current_price": economics.current_price,
        "cost_price": economics.cost_price,
        "revenue": economics.revenue,
        "profit": economics.profit,
        "commission": economics.commission,
        "logistics": economics.logistics,
        "period_start": economics.period_start,
        "period_end": economics.period_end,
    }
    quality_issues.extend(f"missing_{name}" for name, value in required.items() if value is None)
    if economics.revenue is not None and economics.revenue <= 0:
        quality_issues.append("revenue_is_not_positive")
    if economics.delivered_units is None or economics.delivered_units <= 0:
        quality_issues.append("confirmed_delivered_units_unavailable")
    if not _same_money(economics.revenue, economics.analytics_revenue):
        quality_issues.append("revenue_mismatch_between_confirmed_views")
    if not _same_money(economics.profit, economics.analytics_profit):
        quality_issues.append("profit_mismatch_between_confirmed_views")

    margin: Decimal | None = None
    if economics.revenue is not None and economics.revenue > 0 and economics.profit is not None:
        margin = (economics.profit / economics.revenue * Decimal("100")).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)

    profit_per_unit: Decimal | None = None
    if not quality_issues and economics.delivered_units is not None and economics.profit is not None:
        profit_per_unit = (economics.profit / Decimal(economics.delivered_units)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    proposal_reason = "proposed_price is null: no confirmed marginal commission and logistics model for a target-price calculation"
    if quality_issues:
        return Recommendation(**_fields(economics, profit_per_unit, margin), data_quality_status="review", action="REVIEW_DATA", priority="high", reasons=tuple(quality_issues), proposed_price=None, proposed_price_range=None, proposal_reason=proposal_reason)

    assert economics.profit is not None
    assert margin is not None
    if economics.profit <= 0:
        action, priority, reasons = "CONSIDER_RAISE", "high", ("non_positive_profit",)
    elif margin < config.low_margin_percent:
        action, priority, reasons = "CONSIDER_RAISE", "medium", ("margin_below_configured_threshold",)
    else:
        action, priority, reasons = "KEEP", "low", ("margin_meets_configured_threshold",)
    return Recommendation(**_fields(economics, profit_per_unit, margin), data_quality_status="valid", action=action, priority=priority, reasons=reasons, proposed_price=None, proposed_price_range=None, proposal_reason=proposal_reason)


def _fields(economics: ProductEconomics, profit_per_unit: Decimal | None, margin: Decimal | None) -> dict[str, object]:
    return {"offer_id": economics.offer_id, "current_price": economics.current_price, "cost_price": economics.cost_price, "revenue": economics.revenue, "profit": economics.profit, "profit_per_unit": profit_per_unit, "profit_margin_percent": margin, "commission": economics.commission, "logistics": economics.logistics, "period_start": economics.period_start, "period_end": economics.period_end}
