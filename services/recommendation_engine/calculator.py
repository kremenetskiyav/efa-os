"""Pure EFA Ozon Price Calculator V1 business logic."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext
from enum import Enum


MONEY_QUANTUM = Decimal("0.01")
DEFAULT_PRICE_STEP = Decimal("1")
CALCULATION_PRECISION = 50
ZERO = Decimal("0")
ONE = Decimal("1")


class CalculatorValidationError(ValueError):
    """Raised when calculator inputs violate the V1 domain contract."""


class MarginClassification(str, Enum):
    HARD_FLOOR_VIOLATION = "HARD_FLOOR_VIOLATION"
    BELOW_WORKING_MINIMUM = "BELOW_WORKING_MINIMUM"
    BELOW_TARGET = "BELOW_TARGET"
    TARGET_OR_ABOVE = "TARGET_OR_ABOVE"


@dataclass(frozen=True)
class MarginPolicy:
    hard_floor_margin: Decimal = Decimal("0.10")
    working_min_margin: Decimal = Decimal("0.12")
    target_margin: Decimal = Decimal("0.15")

    def __post_init__(self) -> None:
        for name, value in (
            ("hard_floor_margin", self.hard_floor_margin),
            ("working_min_margin", self.working_min_margin),
            ("target_margin", self.target_margin),
        ):
            if not isinstance(value, Decimal) or not value.is_finite():
                raise CalculatorValidationError(f"{name} must be a finite Decimal")
        if not ZERO <= self.hard_floor_margin < self.working_min_margin < self.target_margin <= ONE:
            raise CalculatorValidationError(
                "margin policy must satisfy 0 <= hard floor < working minimum < target <= 1"
            )


DEFAULT_EFA_MARGIN_POLICY = MarginPolicy()


@dataclass(frozen=True)
class UnitEconomicsResult:
    seller_price: Decimal
    commission_amount: Decimal
    acquiring_amount: Decimal
    tax_amount: Decimal
    failed_order_cost: Decimal
    expected_nonbuyout_cost: Decimal
    profit: Decimal
    margin: Decimal


def calculate_unit_economics(
    *,
    seller_price: Decimal,
    cost_price: Decimal,
    commission_rate: Decimal,
    acquiring_rate: Decimal,
    processing_amount: Decimal,
    forward_logistics_amount: Decimal,
    delivery_to_customer_amount: Decimal,
    return_logistics_amount: Decimal,
    return_processing_amount: Decimal,
    buyout_rate: Decimal,
    tax_rate: Decimal,
    other_expenses: Decimal = ZERO,
) -> UnitEconomicsResult:
    """Calculate forecast unit economics without external dependencies."""

    _validate_economics_inputs(
        seller_price=seller_price,
        cost_price=cost_price,
        commission_rate=commission_rate,
        acquiring_rate=acquiring_rate,
        processing_amount=processing_amount,
        forward_logistics_amount=forward_logistics_amount,
        delivery_to_customer_amount=delivery_to_customer_amount,
        return_logistics_amount=return_logistics_amount,
        return_processing_amount=return_processing_amount,
        buyout_rate=buyout_rate,
        tax_rate=tax_rate,
        other_expenses=other_expenses,
    )

    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        commission_amount = seller_price * commission_rate
        acquiring_amount = seller_price * acquiring_rate
        tax_amount = seller_price * tax_rate
        failed_order_cost = (
            processing_amount
            + forward_logistics_amount
            + delivery_to_customer_amount
            + return_logistics_amount
            + return_processing_amount
        )
        expected_nonbuyout_cost = failed_order_cost * (ONE - buyout_rate) / buyout_rate
        profit = (
            seller_price
            - cost_price
            - commission_amount
            - acquiring_amount
            - processing_amount
            - forward_logistics_amount
            - delivery_to_customer_amount
            - expected_nonbuyout_cost
            - tax_amount
            - other_expenses
        )
        margin = profit / seller_price

    return UnitEconomicsResult(
        seller_price=seller_price,
        commission_amount=_money(commission_amount),
        acquiring_amount=_money(acquiring_amount),
        tax_amount=_money(tax_amount),
        failed_order_cost=_money(failed_order_cost),
        expected_nonbuyout_cost=_money(expected_nonbuyout_cost),
        profit=_money(profit),
        margin=margin,
    )


def find_price_for_margin(
    *,
    cost_price: Decimal,
    commission_rate: Decimal,
    acquiring_rate: Decimal,
    processing_amount: Decimal,
    forward_logistics_amount: Decimal,
    delivery_to_customer_amount: Decimal,
    return_logistics_amount: Decimal,
    return_processing_amount: Decimal,
    buyout_rate: Decimal,
    tax_rate: Decimal,
    target_margin: Decimal,
    search_from: Decimal,
    search_to: Decimal,
    price_step: Decimal = DEFAULT_PRICE_STEP,
    other_expenses: Decimal = ZERO,
) -> Decimal | None:
    """Return the first discrete seller price that meets the target margin."""

    _validate_rate("target_margin", target_margin)
    _validate_positive("search_from", search_from)
    _validate_positive("price_step", price_step)
    _validate_decimal("search_to", search_to)
    if search_to < search_from:
        raise CalculatorValidationError("search_to must be greater than or equal to search_from")

    seller_price = search_from
    while seller_price <= search_to:
        result = calculate_unit_economics(
            seller_price=seller_price,
            cost_price=cost_price,
            commission_rate=commission_rate,
            acquiring_rate=acquiring_rate,
            processing_amount=processing_amount,
            forward_logistics_amount=forward_logistics_amount,
            delivery_to_customer_amount=delivery_to_customer_amount,
            return_logistics_amount=return_logistics_amount,
            return_processing_amount=return_processing_amount,
            buyout_rate=buyout_rate,
            tax_rate=tax_rate,
            other_expenses=other_expenses,
        )
        if result.margin >= target_margin:
            return seller_price
        next_seller_price = seller_price + price_step
        if next_seller_price <= seller_price:
            raise CalculatorValidationError(
                "price_step must advance seller_price at the current Decimal precision"
            )
        seller_price = next_seller_price
    return None


def classify_margin(
    margin: Decimal,
    policy: MarginPolicy = DEFAULT_EFA_MARGIN_POLICY,
) -> MarginClassification:
    """Classify an exact margin fraction using an explicit threshold policy."""

    _validate_decimal("margin", margin)
    if not isinstance(policy, MarginPolicy):
        raise CalculatorValidationError("policy must be a MarginPolicy")
    if margin < policy.hard_floor_margin:
        return MarginClassification.HARD_FLOOR_VIOLATION
    if margin < policy.working_min_margin:
        return MarginClassification.BELOW_WORKING_MINIMUM
    if margin < policy.target_margin:
        return MarginClassification.BELOW_TARGET
    return MarginClassification.TARGET_OR_ABOVE


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _validate_economics_inputs(**values: Decimal) -> None:
    _validate_positive("seller_price", values["seller_price"])
    for name in (
        "cost_price",
        "processing_amount",
        "forward_logistics_amount",
        "delivery_to_customer_amount",
        "return_logistics_amount",
        "return_processing_amount",
        "other_expenses",
    ):
        _validate_nonnegative(name, values[name])
    for name in ("commission_rate", "acquiring_rate", "tax_rate"):
        _validate_rate(name, values[name])
    _validate_decimal("buyout_rate", values["buyout_rate"])
    if not ZERO < values["buyout_rate"] <= ONE:
        raise CalculatorValidationError("buyout_rate must be greater than 0 and less than or equal to 1")


def _validate_decimal(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CalculatorValidationError(f"{name} must be a finite Decimal")


def _validate_positive(name: str, value: Decimal) -> None:
    _validate_decimal(name, value)
    if value <= ZERO:
        raise CalculatorValidationError(f"{name} must be greater than 0")


def _validate_nonnegative(name: str, value: Decimal) -> None:
    _validate_decimal(name, value)
    if value < ZERO:
        raise CalculatorValidationError(f"{name} must be greater than or equal to 0")


def _validate_rate(name: str, value: Decimal) -> None:
    _validate_decimal(name, value)
    if not ZERO <= value <= ONE:
        raise CalculatorValidationError(f"{name} must be between 0 and 1")
