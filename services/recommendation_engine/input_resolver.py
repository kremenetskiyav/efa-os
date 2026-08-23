"""Pure fail-closed input resolution for EFA Ozon Price Calculator V1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

try:
    from .config import PriceCalculatorConfig
except ImportError:
    from config import PriceCalculatorConfig


ZERO = Decimal("0")
ONE = Decimal("1")
PERCENT = Decimal("100")
MAX_TARIFF_SNAPSHOT_AGE = timedelta(hours=12)


class InputResolutionError(ValueError):
    """Raised when observed and configured inputs cannot be resolved safely."""


@dataclass(frozen=True)
class CalculatorSourceRow:
    offer_id: str
    product_id: int
    seller_price: Decimal | None
    cost_price: Decimal | None
    snapshot_id: str | None
    price_collection_run_id: str | None
    snapshot_product_id: int | None
    snapshot_offer_id: str | None
    observed_at: datetime | None
    run_status: str | None
    sales_percent_fbs: Decimal | None
    fbs_deliv_to_customer_amount: Decimal | None
    raw_acquiring: Decimal | None = None
    direct_flow_min: Decimal | None = None
    direct_flow_max: Decimal | None = None
    raw_return_flow: Decimal | None = None


@dataclass(frozen=True)
class ResolvedCalculatorInputs:
    offer_id: str
    product_id: int
    seller_price: Decimal
    cost_price: Decimal
    commission_rate: Decimal
    acquiring_rate: Decimal
    processing_amount: Decimal
    forward_logistics_amount: Decimal
    delivery_to_customer_amount: Decimal
    return_logistics_amount: Decimal
    return_processing_amount: Decimal
    buyout_rate: Decimal
    tax_rate: Decimal
    other_expenses: Decimal
    snapshot_id: str
    price_collection_run_id: str
    observed_at: datetime
    calculator_config_version: str
    tariff_profile_version: str
    taxpayer_config_version: str
    provenance: Mapping[str, str]

    def calculator_arguments(self) -> dict[str, Decimal]:
        return {
            "cost_price": self.cost_price,
            "commission_rate": self.commission_rate,
            "acquiring_rate": self.acquiring_rate,
            "processing_amount": self.processing_amount,
            "forward_logistics_amount": self.forward_logistics_amount,
            "delivery_to_customer_amount": self.delivery_to_customer_amount,
            "return_logistics_amount": self.return_logistics_amount,
            "return_processing_amount": self.return_processing_amount,
            "buyout_rate": self.buyout_rate,
            "tax_rate": self.tax_rate,
            "other_expenses": self.other_expenses,
        }


def resolve_calculator_inputs(
    source: CalculatorSourceRow,
    config: PriceCalculatorConfig,
    tax_rate: Decimal,
    calculation_at: datetime,
    taxpayer_config_version: str,
) -> ResolvedCalculatorInputs:
    """Resolve observed/configured inputs without I/O or calculator formulas."""

    _aware_datetime("calculation_at", calculation_at)
    _aware_datetime("config.effective_from", config.effective_from)
    if calculation_at < config.effective_from:
        raise InputResolutionError("calculator config is not effective at calculation_at")
    if calculation_at.date() < config.logistics_profile.tariff_effective_from:
        raise InputResolutionError("tariff profile is not effective at calculation_at")

    offer_id = source.offer_id.strip() if isinstance(source.offer_id, str) else ""
    if not offer_id:
        raise InputResolutionError("offer_id must be non-empty")
    if isinstance(source.product_id, bool) or not isinstance(source.product_id, int) or source.product_id <= 0:
        raise InputResolutionError("product_id must be a positive integer")

    if not source.snapshot_id or not source.price_collection_run_id:
        raise InputResolutionError("successful tariff snapshot is required")
    if source.run_status != "success":
        raise InputResolutionError("tariff snapshot run must be successful")
    if source.snapshot_product_id != source.product_id:
        raise InputResolutionError("snapshot product_id does not match canonical product")
    if source.snapshot_offer_id != offer_id:
        raise InputResolutionError("snapshot offer_id does not match canonical product")
    if source.observed_at is None:
        raise InputResolutionError("snapshot observed_at is required")
    _aware_datetime("snapshot observed_at", source.observed_at)
    if source.observed_at > calculation_at:
        raise InputResolutionError("tariff snapshot cannot be observed in the future")
    if calculation_at - source.observed_at > MAX_TARIFF_SNAPSHOT_AGE:
        raise InputResolutionError("tariff snapshot is older than 12 hours")

    seller_price = _positive_decimal("seller_price", source.seller_price)
    cost_price = _nonnegative_decimal("cost_price", source.cost_price)
    product_profile = config.logistics_profile.products.get(offer_id)
    if product_profile is None:
        raise InputResolutionError("offer_id is absent from the approved logistics profile")
    _validate_seller_price_band(seller_price, config)

    raw_commission = _bounded_decimal(
        "sales_percent_fbs", source.sales_percent_fbs, ZERO, PERCENT
    )
    commission_adjustment = _decimal(
        "recommended_slot_adjustment_pp", config.recommended_slot_adjustment_pp
    )
    effective_commission_percent = raw_commission + commission_adjustment
    if not effective_commission_percent.is_finite() or not ZERO <= effective_commission_percent <= PERCENT:
        raise InputResolutionError("effective commission percent must be between 0 and 100")
    commission_rate = effective_commission_percent / PERCENT
    if not ZERO <= commission_rate <= ONE:
        raise InputResolutionError("commission_rate must be between 0 and 1")

    acquiring_rate = _bounded_decimal("acquiring_rate", config.acquiring_rate, ZERO, ONE)
    delivery_amount = _nonnegative_decimal(
        "fbs_deliv_to_customer_amount", source.fbs_deliv_to_customer_amount
    )
    resolved_tax_rate = _bounded_decimal("tax_rate", tax_rate, ZERO, ONE)
    if not isinstance(taxpayer_config_version, str) or not taxpayer_config_version.strip():
        raise InputResolutionError("taxpayer_config_version must be non-empty")
    if config.logistics_profile.route.return_scenario != "return_to_seller":
        raise InputResolutionError("unsupported return logistics scenario")

    forward_amount = product_profile.forward_logistics_amount
    provenance = MappingProxyType({
        "seller_price": "products.price",
        "cost_price": "products.cost_price",
        "base_commission_percent": "ozon_fbs_tariff_snapshots.sales_percent_fbs",
        "commission_adjustment_pp": "calculator_config.recommended_slot_adjustment_pp",
        "acquiring_rate": "calculator_config.acquiring_rate",
        "processing_amount": "calculator_config.processing_amount",
        "forward_logistics_amount": "calculator_config.logistics_profile.products[offer_id]",
        "delivery_to_customer_amount": "ozon_fbs_tariff_snapshots.fbs_deliv_to_customer_amount",
        "return_logistics_amount": "derived:forward_logistics_amount(return_to_seller)",
        "return_processing_amount": "calculator_config.return_processing_amount",
        "buyout_rate": "calculator_config.buyout_rate",
        "tax_rate": "taxpayer_config.usn_rate",
        "other_expenses": "calculator_config.other_expenses",
    })
    return ResolvedCalculatorInputs(
        offer_id=offer_id,
        product_id=source.product_id,
        seller_price=seller_price,
        cost_price=cost_price,
        commission_rate=commission_rate,
        acquiring_rate=acquiring_rate,
        processing_amount=config.processing_amount,
        forward_logistics_amount=forward_amount,
        delivery_to_customer_amount=delivery_amount,
        return_logistics_amount=forward_amount,
        return_processing_amount=config.return_processing_amount,
        buyout_rate=config.buyout_rate,
        tax_rate=resolved_tax_rate,
        other_expenses=config.other_expenses,
        snapshot_id=str(source.snapshot_id),
        price_collection_run_id=str(source.price_collection_run_id),
        observed_at=source.observed_at,
        calculator_config_version=config.version,
        tariff_profile_version=config.logistics_profile.tariff_version,
        taxpayer_config_version=taxpayer_config_version.strip(),
        provenance=provenance,
    )


def _aware_datetime(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InputResolutionError(f"{name} must be timezone-aware")


def _decimal(name: str, value: Decimal | None) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise InputResolutionError(f"{name} must be a finite Decimal")
    return value


def _positive_decimal(name: str, value: Decimal | None) -> Decimal:
    parsed = _decimal(name, value)
    if parsed <= ZERO:
        raise InputResolutionError(f"{name} must be greater than 0")
    return parsed


def _nonnegative_decimal(name: str, value: Decimal | None) -> Decimal:
    parsed = _decimal(name, value)
    if parsed < ZERO:
        raise InputResolutionError(f"{name} must be greater than or equal to 0")
    return parsed


def _bounded_decimal(
    name: str,
    value: Decimal | None,
    lower: Decimal,
    upper: Decimal,
) -> Decimal:
    parsed = _decimal(name, value)
    if not lower <= parsed <= upper:
        raise InputResolutionError(f"{name} must be between {lower} and {upper}")
    return parsed


def _validate_seller_price_band(seller_price: Decimal, config: PriceCalculatorConfig) -> None:
    band = config.logistics_profile.seller_price_band
    if seller_price <= band.lower_exclusive:
        raise InputResolutionError("seller_price is below or equal to the approved lower-exclusive bound")
    if band.upper_inclusive is not None and seller_price > band.upper_inclusive:
        raise InputResolutionError("seller_price exceeds the approved upper-inclusive bound")
