"""Deterministic, read-only comparison of equal confirmed delivery periods."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from config import AnomalyConfig
from models import PeriodEconomics, ProfitCostAnomaly

MONEY = Decimal("0.01")


def _round(value: Decimal | None) -> Decimal | None:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP) if value is not None else None


def _metrics(period: PeriodEconomics | None) -> dict[str, Decimal | int | object | None]:
    if period is None:
        return {key: None for key in ("period_start", "period_end", "units", "orders", "revenue", "profit", "profit_per_unit", "profit_margin_percent", "commission", "commission_per_unit", "commission_rate", "logistics", "logistics_per_unit", "logistics_rate", "other_expenses")}
    units, revenue = period.units, period.revenue
    abs_commission, abs_logistics = abs(period.commission), abs(period.logistics)
    return {"period_start": period.period_start, "period_end": period.period_end, "units": units, "orders": period.orders, "revenue": _round(revenue), "profit": _round(period.profit), "profit_per_unit": _round(period.profit / units) if units else None, "profit_margin_percent": _round(period.profit / revenue * 100) if revenue else None, "commission": _round(period.commission), "commission_per_unit": _round(abs_commission / units) if units else None, "commission_rate": _round(abs_commission / revenue * 100) if revenue else None, "logistics": _round(period.logistics), "logistics_per_unit": _round(abs_logistics / units) if units else None, "logistics_rate": _round(abs_logistics / revenue * 100) if revenue else None, "other_expenses": _round(period.other_expenses)}


def _percent_change(current: Decimal | None, baseline: Decimal | None) -> Decimal | None:
    if current is None or baseline is None or baseline == 0:
        return None
    return _round((current - baseline) / abs(baseline) * 100)


def build_profit_cost_anomaly(offer_id: str, periods: dict[str, PeriodEconomics], config: AnomalyConfig) -> ProfitCostAnomaly:
    current_period, baseline_period = periods.get("current"), periods.get("baseline")
    current, baseline = _metrics(current_period), _metrics(baseline_period)
    quality_reasons: list[str] = []
    for name, period in (("current", current_period), ("baseline", baseline_period)):
        if period is None or period.units < config.min_period_units:
            quality_reasons.append(f"{name}_period_has_insufficient_confirmed_units")
        elif period.unallocated_expense_lines:
            quality_reasons.append(f"{name}_period_has_unallocated_other_expenses")
    anomalies: list[str] = []
    reasons: list[str] = []
    if quality_reasons:
        anomalies.append("DATA_QUALITY_ISSUE"); reasons.extend(quality_reasons)
    else:
        profit_change = _percent_change(current["profit"], baseline["profit"])
        if profit_change is not None and profit_change <= -config.profit_drop_percent:
            anomalies.append("PROFIT_DROPPED"); reasons.append("confirmed_profit_declined_beyond_threshold")
        margin_change = (current["profit_margin_percent"] - baseline["profit_margin_percent"]) if current["profit_margin_percent"] is not None and baseline["profit_margin_percent"] is not None else None
        if margin_change is not None and margin_change <= -config.margin_drop_percentage_points:
            anomalies.append("MARGIN_DROPPED"); reasons.append("confirmed_profit_margin_declined_beyond_threshold")
        logistics_change = _percent_change(current["logistics_per_unit"], baseline["logistics_per_unit"])
        if logistics_change is not None and logistics_change >= config.logistics_increase_percent:
            anomalies.append("LOGISTICS_INCREASED"); reasons.append("confirmed_logistics_per_unit_increased_beyond_threshold")
        commission_change = _percent_change(current["commission_per_unit"], baseline["commission_per_unit"])
        if commission_change is not None and commission_change >= config.commission_increase_percent:
            anomalies.append("COMMISSION_INCREASED"); reasons.append("confirmed_commission_per_unit_increased_beyond_threshold")
        if current["other_expenses"] is not None and baseline["other_expenses"] == Decimal("0") and current["other_expenses"] != Decimal("0"):
            anomalies.append("OTHER_EXPENSES_APPEARED"); reasons.append("allocatable_other_expenses_appeared_in_current_period")
    changes = {"profit_absolute": _round(current["profit"] - baseline["profit"]) if current["profit"] is not None and baseline["profit"] is not None else None, "profit_percent": _percent_change(current["profit"], baseline["profit"]), "margin_percentage_points": _round(current["profit_margin_percent"] - baseline["profit_margin_percent"]) if current["profit_margin_percent"] is not None and baseline["profit_margin_percent"] is not None else None, "logistics_per_unit_percent": _percent_change(current["logistics_per_unit"], baseline["logistics_per_unit"]), "commission_per_unit_percent": _percent_change(current["commission_per_unit"], baseline["commission_per_unit"]), "other_expenses_absolute": _round(current["other_expenses"] - baseline["other_expenses"]) if current["other_expenses"] is not None and baseline["other_expenses"] is not None else None}
    severity = "high" if "DATA_QUALITY_ISSUE" in anomalies else "high" if len(anomalies) >= 2 else "medium" if anomalies else "low"
    attention = "review_confirmed_data_before_action" if "DATA_QUALITY_ISSUE" in anomalies else "review_confirmed_economics" if anomalies else "no_anomaly_detected"
    return ProfitCostAnomaly(offer_id, severity, tuple(anomalies), current, baseline, changes, "review" if quality_reasons else "valid", tuple(dict.fromkeys(reasons)), attention)
