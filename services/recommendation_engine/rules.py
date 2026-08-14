"""Conservative rules over observed, confirmed effective-price windows."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from config import RecommendationConfig
from models import PriceWindow, ProductEconomics, Recommendation


MONEY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _margin(window: PriceWindow) -> Decimal | None:
    return _money(window.profit / window.revenue * Decimal("100")) if window.revenue > 0 else None


def _profit_per_unit(window: PriceWindow) -> Decimal | None:
    return _money(window.profit / Decimal(window.units)) if window.units > 0 else None


def _confidence(window: PriceWindow, config: RecommendationConfig) -> str:
    if window.units >= config.min_window_units * 2:
        return "high"
    if window.units >= config.min_window_units:
        return "medium"
    return "low"


def _current_window(windows: tuple[PriceWindow, ...]) -> PriceWindow | None:
    if not windows:
        return None
    latest = max(item.period_end for item in windows)
    candidates = [item for item in windows if item.period_end == latest]
    return candidates[0] if len(candidates) == 1 else None


def build_recommendation(economics: ProductEconomics, config: RecommendationConfig) -> Recommendation:
    current = _current_window(economics.windows)
    issues = list(economics.data_issues)
    if economics.current_price is None:
        issues.append("missing_current_price_context")
    if economics.cost_price is None:
        issues.append("missing_cost_price")
    if current is None:
        issues.append("ambiguous_or_missing_current_effective_window")
    if issues:
        return _result(economics, current, "REVIEW_DATA", "high", None, "low", tuple(sorted(set(issues))))

    assert current is not None
    current_margin = _margin(current)
    current_profit_per_unit = _profit_per_unit(current)
    if current_margin is None or current_profit_per_unit is None:
        return _result(economics, current, "REVIEW_DATA", "high", None, "low", ("invalid_current_unit_economics",))

    valid = [item for item in economics.windows if _confidence(item, config) != "low" and _margin(item) is not None and _profit_per_unit(item) is not None]
    comparable: list[PriceWindow] = []
    for item in valid:
        if item.effective_price == current.effective_price:
            continue
        change = abs(item.effective_price / current.effective_price - Decimal("1")) * Decimal("100")
        if change <= config.max_price_step_percent:
            comparable.append(item)
    better = [item for item in comparable if _margin(item) >= config.low_margin_percent and _profit_per_unit(item) > current_profit_per_unit]
    if better:
        candidate = max(better, key=lambda item: (_profit_per_unit(item), -item.effective_price))
        action = "CONSIDER_RAISE" if candidate.effective_price > current.effective_price else "CONSIDER_LOWER"
        return _result(economics, current, action, "medium", candidate, _confidence(candidate, config), ("observed_price_window_has_better_confirmed_unit_economics",))
    if current_margin < config.low_margin_percent:
        return _result(economics, current, "CONSIDER_RAISE", "medium", None, _confidence(current, config), ("current_margin_below_configured_threshold", "no_confirmed_observed_price_candidate"))
    return _result(economics, current, "KEEP", "low", None, _confidence(current, config), ("current_effective_window_meets_configured_threshold",))


def _result(economics: ProductEconomics, current: PriceWindow | None, action: str, priority: str, candidate: PriceWindow | None, confidence: str, reasons: tuple[str, ...]) -> Recommendation:
    return Recommendation(
        economics.offer_id, economics.current_price, current.effective_price if current else None,
        current.revenue if current else None, current.profit if current else None,
        _profit_per_unit(current) if current else None, _margin(current) if current else None,
        current.commission if current else None, current.logistics if current else None,
        current.other_expenses if current else None, current.period_start if current else None,
        current.period_end if current else None, action, priority,
        candidate.effective_price if candidate else None,
        _profit_per_unit(candidate) if candidate else None, _margin(candidate) if candidate else None,
        confidence, "valid" if action != "REVIEW_DATA" else "review", reasons,
    )
