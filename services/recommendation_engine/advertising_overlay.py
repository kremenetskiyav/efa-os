"""Read-only advertising economics overlay for Calculator V1 results."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, localcontext
from enum import Enum

try:
    from .calculator import (
        CALCULATION_PRECISION,
        MONEY_QUANTUM,
        MarginClassification,
        MarginPolicy,
        UnitEconomicsResult,
        classify_margin,
    )
except ImportError:
    from calculator import (
        CALCULATION_PRECISION,
        MONEY_QUANTUM,
        MarginClassification,
        MarginPolicy,
        UnitEconomicsResult,
        classify_margin,
    )


ZERO = Decimal("0")
FIVE_PERCENT = Decimal("0.05")
DEFAULT_CPC_MAX_AGE = timedelta(hours=48)


class AdvertisingOverlayError(ValueError):
    """Raised when advertising overlay inputs violate the read-only contract."""


class AdvertisingAnalyticalStatus(str, Enum):
    SAFE_AT_5_PERCENT = "SAFE_AT_5_PERCENT"
    TARGET_MARGIN_AT_RISK = "TARGET_MARGIN_AT_RISK"
    WORKING_MARGIN_AT_RISK = "WORKING_MARGIN_AT_RISK"
    HARD_FLOOR_AT_RISK = "HARD_FLOOR_AT_RISK"
    NO_CPC_DATA = "NO_CPC_DATA"
    CPC_DATA_STALE = "CPC_DATA_STALE"
    CPC_DATA_REVIEW = "CPC_DATA_REVIEW"


@dataclass(frozen=True)
class AdvertisingPlanningCeilings:
    max_ad_cost_at_target: Decimal
    max_ad_rate_at_target: Decimal
    max_ad_cost_at_working_min: Decimal
    max_ad_rate_at_working_min: Decimal
    max_ad_cost_at_hard_floor: Decimal
    max_ad_rate_at_hard_floor: Decimal


@dataclass(frozen=True)
class AdvertisingEconomicsResult:
    advertising_cost: Decimal
    after_ads_profit: Decimal
    after_ads_margin: Decimal
    margin_classification: MarginClassification
    analytical_status: AdvertisingAnalyticalStatus | None


@dataclass(frozen=True)
class CpcObservation:
    business_date: date
    data_scope: str
    offer_id: str
    campaigns_count: int | None
    active_campaigns_count: int | None
    views: int | None
    clicks: int | None
    ctr_percent: Decimal | None
    spend: Decimal | None
    attributed_orders: int | None
    attributed_revenue: Decimal | None
    product_gmv: Decimal | None
    drr_percent: Decimal | None
    general_drr_percent: Decimal | None
    average_bid: Decimal | None
    data_quality_status: str
    collection_status: str
    observed_at: datetime


def calculate_advertising_planning_ceilings(
    core_result: UnitEconomicsResult,
    seller_price: Decimal,
    policy: MarginPolicy,
) -> AdvertisingPlanningCeilings:
    """Calculate safe per-unit planning ceilings; these are not Ozon DRR."""

    _validate_core_result(core_result, seller_price)
    if not isinstance(policy, MarginPolicy):
        raise AdvertisingOverlayError("policy must be a MarginPolicy")
    exact_core_profit = core_result.margin * seller_price
    target_cost, target_rate = _planning_ceiling(
        exact_core_profit, seller_price, policy.target_margin
    )
    working_cost, working_rate = _planning_ceiling(
        exact_core_profit, seller_price, policy.working_min_margin
    )
    hard_cost, hard_rate = _planning_ceiling(
        exact_core_profit, seller_price, policy.hard_floor_margin
    )
    return AdvertisingPlanningCeilings(
        max_ad_cost_at_target=target_cost,
        max_ad_rate_at_target=target_rate,
        max_ad_cost_at_working_min=working_cost,
        max_ad_rate_at_working_min=working_rate,
        max_ad_cost_at_hard_floor=hard_cost,
        max_ad_rate_at_hard_floor=hard_rate,
    )


def apply_advertising_cost(
    core_result: UnitEconomicsResult,
    seller_price: Decimal,
    advertising_cost: Decimal,
    policy: MarginPolicy,
) -> AdvertisingEconomicsResult:
    """Apply a forecast per-unit advertising cost without changing Calculator Core."""

    _validate_core_result(core_result, seller_price)
    _validate_nonnegative_decimal("advertising_cost", advertising_cost)
    if not isinstance(policy, MarginPolicy):
        raise AdvertisingOverlayError("policy must be a MarginPolicy")
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        exact_core_profit = core_result.margin * seller_price
        after_ads_profit = exact_core_profit - advertising_cost
        after_ads_margin = after_ads_profit / seller_price
    margin_classification = classify_margin(after_ads_margin, policy)
    return AdvertisingEconomicsResult(
        advertising_cost=_money(advertising_cost),
        after_ads_profit=_money(after_ads_profit),
        after_ads_margin=after_ads_margin,
        margin_classification=margin_classification,
        analytical_status=_forecast_status(margin_classification),
    )


def calculate_five_percent_scenario(
    core_result: UnitEconomicsResult,
    seller_price: Decimal,
    policy: MarginPolicy,
) -> AdvertisingEconomicsResult:
    """Apply the controlled five-percent-of-seller-price planning scenario."""

    _validate_positive_decimal("seller_price", seller_price)
    result = apply_advertising_cost(
        core_result,
        seller_price,
        seller_price * FIVE_PERCENT,
        policy,
    )
    if result.analytical_status is None:
        return replace(
            result,
            analytical_status=AdvertisingAnalyticalStatus.SAFE_AT_5_PERCENT,
        )
    return result


def classify_cpc_observation(
    observation: CpcObservation | None,
    as_of: datetime,
    max_age: timedelta = DEFAULT_CPC_MAX_AGE,
) -> AdvertisingAnalyticalStatus | None:
    """Classify observed CPC provenance without interpreting its DRR as a ceiling."""

    _validate_aware_datetime("as_of", as_of)
    if max_age <= timedelta(0):
        raise AdvertisingOverlayError("max_age must be greater than zero")
    if observation is None:
        return AdvertisingAnalyticalStatus.NO_CPC_DATA
    if not _valid_cpc_observation(observation, as_of):
        return AdvertisingAnalyticalStatus.CPC_DATA_REVIEW
    if as_of - observation.observed_at > max_age:
        return AdvertisingAnalyticalStatus.CPC_DATA_STALE
    return None


def _planning_ceiling(
    core_profit: Decimal,
    seller_price: Decimal,
    threshold: Decimal,
) -> tuple[Decimal, Decimal]:
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        exact_cost = max(ZERO, core_profit - seller_price * threshold)
        safe_cost = exact_cost.quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)
        return safe_cost, safe_cost / seller_price


def _forecast_status(
    classification: MarginClassification,
) -> AdvertisingAnalyticalStatus | None:
    if classification is MarginClassification.HARD_FLOOR_VIOLATION:
        return AdvertisingAnalyticalStatus.HARD_FLOOR_AT_RISK
    if classification is MarginClassification.BELOW_WORKING_MINIMUM:
        return AdvertisingAnalyticalStatus.WORKING_MARGIN_AT_RISK
    if classification is MarginClassification.BELOW_TARGET:
        return AdvertisingAnalyticalStatus.TARGET_MARGIN_AT_RISK
    return None


def _valid_cpc_observation(observation: CpcObservation, as_of: datetime) -> bool:
    if observation.data_scope != "PRODUCT":
        return False
    if not isinstance(observation.offer_id, str) or not observation.offer_id.strip():
        return False
    if observation.data_quality_status != "valid":
        return False
    if observation.collection_status != "SUCCESS_NONZERO":
        return False
    if not isinstance(observation.business_date, date):
        return False
    if not _is_aware_datetime(observation.observed_at):
        return False
    if observation.observed_at > as_of:
        return False
    integer_values = (
        observation.campaigns_count,
        observation.active_campaigns_count,
        observation.views,
        observation.clicks,
        observation.attributed_orders,
    )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in integer_values
    ):
        return False
    if observation.active_campaigns_count > observation.campaigns_count:
        return False
    if observation.clicks > observation.views:
        return False
    decimal_values = (
        observation.ctr_percent,
        observation.spend,
        observation.attributed_revenue,
        observation.product_gmv,
        observation.drr_percent,
        observation.general_drr_percent,
        observation.average_bid,
    )
    return all(
        value is None
        or (isinstance(value, Decimal) and value.is_finite() and value >= ZERO)
        for value in decimal_values
    ) and observation.spend is not None


def _validate_core_result(
    core_result: UnitEconomicsResult,
    seller_price: Decimal,
) -> None:
    if not isinstance(core_result, UnitEconomicsResult):
        raise AdvertisingOverlayError("core_result must be a UnitEconomicsResult")
    _validate_positive_decimal("seller_price", seller_price)
    _validate_decimal("core_result.profit", core_result.profit)
    _validate_decimal("core_result.margin", core_result.margin)
    if core_result.seller_price != seller_price:
        raise AdvertisingOverlayError("seller_price must match core_result.seller_price")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _validate_decimal(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise AdvertisingOverlayError(f"{name} must be a finite Decimal")


def _validate_nonnegative_decimal(name: str, value: Decimal) -> None:
    _validate_decimal(name, value)
    if value < ZERO:
        raise AdvertisingOverlayError(f"{name} must be greater than or equal to zero")


def _validate_positive_decimal(name: str, value: Decimal) -> None:
    _validate_decimal(name, value)
    if value <= ZERO:
        raise AdvertisingOverlayError(f"{name} must be greater than zero")


def _is_aware_datetime(value: object) -> bool:
    return isinstance(value, datetime) and value.utcoffset() is not None


def _validate_aware_datetime(name: str, value: datetime) -> None:
    if not _is_aware_datetime(value):
        raise AdvertisingOverlayError(f"{name} must be timezone-aware")
