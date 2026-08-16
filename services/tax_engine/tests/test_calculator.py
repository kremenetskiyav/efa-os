import json
import unittest
from decimal import Decimal
from pathlib import Path

from services.tax_engine.calculator import additional_contribution, calculate_tax_state, marginal_tax_burden_per_ruble
from services.tax_engine.integration import after_tax_management_economics
from services.tax_engine.models import TaxRevenueEvent, TaxpayerConfig


def config(**overrides):
    raw=json.loads(Path("config/taxpayer.2026.json").read_text(encoding="utf-8")); raw.update(overrides)
    return TaxpayerConfig.from_dict(raw)


def event(kind="REALIZATION", amount="100000", period="2026-07", semantics="CONFIRMED"):
    return TaxRevenueEvent("id",2026,period,kind,Decimal(amount),"report.xlsx","ref",semantics,"PERIOD_ONLY","valid")


class CalculatorTests(unittest.TestCase):
    def test_usn_six_percent_and_below_300k(self):
        state=calculate_tax_state([event(amount="100000")],config())
        self.assertEqual(state["usn_gross_ytd"],Decimal("6000.00"))
        self.assertEqual(state["additional_contribution_ytd"],Decimal("0.00"))

    def test_additional_above_threshold_and_cap(self):
        self.assertEqual(additional_contribution(Decimal("400000"),config()),Decimal("1000.00"))
        self.assertEqual(additional_contribution(Decimal("100000000"),config()),Decimal("321818.00"))

    def test_no_employee_reduction_has_no_fifty_percent_limit(self):
        state=calculate_tax_state([event(amount="500000")],config())
        self.assertEqual(state["eligible_usn_reduction"],Decimal("30000.00"))
        self.assertEqual(state["usn_payable_estimate_ytd"],Decimal("0.00"))

    def test_fixed_obligation_is_not_marginal_rate(self):
        self.assertEqual(marginal_tax_burden_per_ruble(Decimal("100000"),config()),Decimal("0.000000"))
        self.assertNotEqual(config().fixed_insurance_contribution,Decimal("0"))

    def test_return_and_loyalty_reversal_are_separate_negative_events(self):
        rows=[event(amount="1000"),event("RETURN","-100"),event("PARTNER_LOYALTY_PAYMENT","50",semantics="PARTIAL"),event("PARTNER_LOYALTY_REVERSAL","-5",semantics="PARTIAL")]
        state=calculate_tax_state(rows,config())
        self.assertEqual(state["taxable_revenue_ytd"],Decimal("945.00"))
        self.assertEqual(state["partner_loyalty_confidence"],"PARTIAL")

    def test_period_only_dates_are_partial(self):
        self.assertEqual(calculate_tax_state([event()],config())["tax_date_confidence"],"PARTIAL")

    def test_january_to_may_are_confirmed_zero_not_missing(self):
        periods=[f"2026-{m:02d}" for m in range(1,8)]
        state=calculate_tax_state([],config(),periods[:5],periods)
        self.assertEqual(state["income_periods_available"],periods[:5])
        self.assertEqual(state["income_periods_missing"],periods[5:])
        self.assertEqual(state["overall_tax_quality"],"PARTIAL")

    def test_vat_states_without_automatic_tax_rate(self):
        low=calculate_tax_state([event(amount="100000")],config())
        warning=calculate_tax_state([event(amount="16000000")],config())
        exceeded=calculate_tax_state([event(amount="20000001")],config())
        self.assertEqual(low["vat_status"],"EXEMPT_UNDER_THRESHOLD")
        self.assertEqual(warning["vat_status"],"THRESHOLD_APPROACHING")
        self.assertEqual(exceeded["vat_status"],"REQUIRES_REGIME_DECISION")
        self.assertIsNone(exceeded["vat_tax"])

    def test_marginal_burden_is_state_dependent_and_never_seven_percent_shortcut(self):
        at_400k=marginal_tax_burden_per_ruble(Decimal("400000"),config())
        self.assertEqual(at_400k,Decimal("0.010000"))
        self.assertNotEqual(at_400k,Decimal("0.070000"))

    def test_profit_before_tax_is_preserved(self):
        result=after_tax_management_economics(Decimal("100"),Decimal("500"),Decimal("0.06"),"CONFIRMED")
        self.assertEqual(result["profit_before_tax"],Decimal("100"))
        self.assertEqual(result["profit_after_tax_estimate"],Decimal("70.00"))
