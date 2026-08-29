"""Targeted tests for the read-only CPC economics overlay v1."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
import unittest

from advertising_overlay import (
    AdvertisingAnalyticalStatus,
    CpcObservation,
    apply_advertising_cost,
    calculate_advertising_planning_ceilings,
    calculate_five_percent_scenario,
    classify_cpc_observation,
)
from calculator import (
    MarginClassification,
    MarginPolicy,
    calculate_unit_economics,
)


D = Decimal
POLICY = MarginPolicy(D("0.10"), D("0.12"), D("0.15"))
CURRENT_INPUTS = {
    "cost_price": D("166"),
    "commission_rate": D("0.44"),
    "acquiring_rate": D("0.015"),
    "processing_amount": D("10"),
    "forward_logistics_amount": D("95"),
    "delivery_to_customer_amount": D("25"),
    "return_logistics_amount": D("95"),
    "return_processing_amount": D("15"),
    "buyout_rate": D("0.92"),
    "tax_rate": D("0.06"),
    "other_expenses": D("0"),
}
AS_OF = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def current_core():
    return calculate_unit_economics(seller_price=D("1290"), **CURRENT_INPUTS)


def cpc_observation(**changes):
    observation = CpcObservation(
        business_date=date(2026, 8, 28),
        data_scope="PRODUCT",
        offer_id="УФ 001Б",
        campaigns_count=1,
        active_campaigns_count=1,
        views=100,
        clicks=5,
        ctr_percent=D("5.00"),
        spend=D("50.00"),
        attributed_orders=2,
        attributed_revenue=D("1000.00"),
        product_gmv=D("1200.00"),
        drr_percent=D("5.00"),
        general_drr_percent=D("4.17"),
        average_bid=D("10.00"),
        data_quality_status="valid",
        collection_status="SUCCESS_NONZERO",
        observed_at=AS_OF - timedelta(hours=24),
    )
    return replace(observation, **changes)


class AdvertisingOverlayTests(unittest.TestCase):
    def test_zero_advertising_cost_preserves_core_result(self):
        core = current_core()
        result = apply_advertising_cost(core, D("1290"), D("0"), POLICY)

        self.assertEqual(result.after_ads_profit, core.profit)
        self.assertLess(abs(result.after_ads_margin - core.margin), D("1e-49"))

    def test_five_percent_scenario_remains_above_target(self):
        result = calculate_five_percent_scenario(current_core(), D("1290"), POLICY)

        self.assertEqual(result.advertising_cost, D("64.50"))
        self.assertEqual(result.after_ads_profit, D("244.28"))
        self.assertEqual(result.margin_classification, MarginClassification.TARGET_OR_ABOVE)
        self.assertEqual(
            result.analytical_status,
            AdvertisingAnalyticalStatus.SAFE_AT_5_PERCENT,
        )

    def test_target_ceiling_is_safe_after_currency_rounding(self):
        core = current_core()
        planning = calculate_advertising_planning_ceilings(core, D("1290"), POLICY)
        result = apply_advertising_cost(
            core,
            D("1290"),
            planning.max_ad_cost_at_target,
            POLICY,
        )

        self.assertEqual(planning.max_ad_cost_at_target, D("115.28"))
        with localcontext() as context:
            context.prec = 50
            self.assertEqual(
                planning.max_ad_rate_at_target,
                planning.max_ad_cost_at_target / D("1290"),
            )
        self.assertGreaterEqual(result.after_ads_margin, D("0.15"))

    def test_cost_above_hard_floor_ceiling_is_at_risk(self):
        core = current_core()
        planning = calculate_advertising_planning_ceilings(core, D("1290"), POLICY)
        result = apply_advertising_cost(
            core,
            D("1290"),
            planning.max_ad_cost_at_hard_floor + D("0.01"),
            POLICY,
        )

        self.assertEqual(
            result.analytical_status,
            AdvertisingAnalyticalStatus.HARD_FLOOR_AT_RISK,
        )

    def test_missing_cpc_is_not_synthetic_zero(self):
        self.assertEqual(
            classify_cpc_observation(None, AS_OF),
            AdvertisingAnalyticalStatus.NO_CPC_DATA,
        )

    def test_invalid_stale_and_unknown_cpc_states_are_explicit(self):
        self.assertEqual(
            classify_cpc_observation(
                cpc_observation(data_quality_status="review"), AS_OF
            ),
            AdvertisingAnalyticalStatus.CPC_DATA_REVIEW,
        )
        self.assertEqual(
            classify_cpc_observation(
                cpc_observation(observed_at=AS_OF - timedelta(hours=49)), AS_OF
            ),
            AdvertisingAnalyticalStatus.CPC_DATA_STALE,
        )
        self.assertEqual(
            classify_cpc_observation(
                cpc_observation(collection_status="UNKNOWN"), AS_OF
            ),
            AdvertisingAnalyticalStatus.CPC_DATA_REVIEW,
        )


if __name__ == "__main__":
    unittest.main()
