from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from .models import TaxRevenueEvent, TaxpayerConfig

MONEY = Decimal("0.01")
RATE = Decimal("0.000001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def additional_contribution(income: Decimal, config: TaxpayerConfig) -> Decimal:
    excess = max(income - config.additional_contribution_threshold, Decimal("0"))
    return _money(min(excess * config.additional_contribution_rate, config.additional_contribution_cap))


def _statutory(income: Decimal, config: TaxpayerConfig) -> dict[str, Decimal]:
    gross = _money(income * config.usn_rate)
    additional = additional_contribution(income, config)
    eligible = config.fixed_insurance_contribution + additional
    if config.has_employees:
        eligible = min(config.insurance_contributions_paid_ytd, gross / Decimal("2"))
    reduction = min(gross, eligible)
    payable = _money(max(gross - reduction, Decimal("0")))
    return {"usn_gross_ytd": gross, "additional_contribution_ytd": additional,
            "eligible_usn_reduction": _money(reduction), "usn_payable_estimate_ytd": payable}


def marginal_tax_burden_per_ruble(income: Decimal, config: TaxpayerConfig) -> Decimal:
    before, after = _statutory(income, config), _statutory(income + Decimal("1"), config)
    total_before = before["usn_payable_estimate_ytd"] + before["additional_contribution_ytd"]
    total_after = after["usn_payable_estimate_ytd"] + after["additional_contribution_ytd"]
    return max(total_after - total_before, Decimal("0")).quantize(RATE)


def calculate_tax_state(events: Iterable[TaxRevenueEvent], config: TaxpayerConfig,
                        zero_periods: Iterable[str] = (), expected_periods: Iterable[str] = ()) -> dict[str, object]:
    rows = list(events)
    ozon_income = sum((row.amount for row in rows), Decimal("0"))
    income = ozon_income + config.non_ozon_income_ytd
    statutory = _statutory(income, config)
    vat_income = income
    usage = Decimal("0") if config.vat_threshold == 0 else vat_income / config.vat_threshold
    if vat_income > config.vat_threshold:
        vat_status = "REQUIRES_REGIME_DECISION"
    elif usage >= config.vat_warning_ratio:
        vat_status = "THRESHOLD_APPROACHING"
    else:
        vat_status = "EXEMPT_UNDER_THRESHOLD"
    marginal = marginal_tax_burden_per_ruble(income, config)
    variable_statutory_reserve = (
        statutory["usn_payable_estimate_ytd"] + statutory["additional_contribution_ytd"]
    )
    available = sorted(set(zero_periods) | {row.source_period for row in rows})
    missing = sorted(set(expected_periods) - set(available))
    date_states = {row.tax_date_status for row in rows}
    semantics = {row.tax_semantics_status for row in rows}
    quality = "PARTIAL" if missing or "PERIOD_ONLY" in date_states or "PARTIAL" in semantics else "CONFIRMED"
    return {
        "tax_year": config.tax_year, "taxable_revenue_ytd": _money(income),
        **statutory, "fixed_contribution_annual": config.fixed_insurance_contribution,
        "fixed_contribution_paid_ytd": config.insurance_contributions_paid_ytd,
        "vat_status": vat_status, "vat_tax": None, "vat_threshold": config.vat_threshold,
        "vat_income_ytd": _money(vat_income),
        "vat_threshold_remaining": _money(max(config.vat_threshold - vat_income, Decimal("0"))),
        "vat_threshold_usage_percent": (usage * Decimal("100")).quantize(Decimal("0.01")),
        "marginal_tax_burden_per_ruble": marginal,
        "marginal_tax_burden_status": "ESTIMATED" if quality == "CONFIRMED" else "PARTIAL",
        "management_tax_reserve_rate": marginal,
        "management_tax_reserve_amount": _money(variable_statutory_reserve),
        "management_tax_reserve_status": "ESTIMATED" if quality == "CONFIRMED" else "PARTIAL",
        "income_periods_available": available,
        "income_periods_missing": missing,
        "tax_date_confidence": quality,
        "partner_loyalty_confidence": "PARTIAL" if any(r.event_type.startswith("PARTNER_LOYALTY") for r in rows) else "NOT_AVAILABLE",
        "vat_confidence": "CONFIRMED" if quality == "CONFIRMED" and config.prior_year_business_income == 0 and config.non_ozon_income_ytd == 0 else "PARTIAL",
        "overall_tax_quality": quality,
        "explanation": "Reserve is current variable statutory burden (USN payable plus additional contribution); the state-dependent marginal rate excludes the fixed annual contribution.",
    }
