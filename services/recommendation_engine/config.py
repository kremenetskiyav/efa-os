"""Secret-safe configuration for the read-only recommendation engine."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


class ConfigurationError(ValueError):
    pass


APPROVED_CALCULATOR_OFFER_IDS = frozenset({
    "УФ 001Б",
    "УФ 002Б",
    "УФ 003Б",
    "УФ 004Б",
    "УФ 005Б",
})


@dataclass(frozen=True)
class PriceCalculatorMarginPolicyConfig:
    hard_floor: Decimal
    working_minimum: Decimal
    target: Decimal


@dataclass(frozen=True)
class SellerPriceBandConfig:
    lower_exclusive: Decimal
    upper_inclusive: Decimal | None


@dataclass(frozen=True)
class LogisticsRouteConfig:
    origin_cluster: str
    destination_cluster: str
    return_scenario: str


@dataclass(frozen=True)
class ProductLogisticsConfig:
    volume_l: Decimal
    forward_logistics_amount: Decimal


@dataclass(frozen=True)
class LogisticsProfileConfig:
    tariff_source: str
    tariff_version: str
    tariff_effective_from: date
    seller_price_band: SellerPriceBandConfig
    route: LogisticsRouteConfig
    products: Mapping[str, ProductLogisticsConfig]


@dataclass(frozen=True)
class PriceCalculatorConfig:
    version: str
    effective_from: datetime
    scheme: str
    buyout_rate: Decimal
    acquiring_rate: Decimal
    processing_amount: Decimal
    return_processing_amount: Decimal
    other_expenses: Decimal
    handover_status: str
    recommended_slot_adjustment_pp: Decimal
    margin_policy: PriceCalculatorMarginPolicyConfig
    logistics_profile: LogisticsProfileConfig


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class RecommendationConfig:
    low_margin_percent: Decimal
    min_window_units: int
    max_price_step_percent: Decimal


@dataclass(frozen=True)
class AnomalyConfig:
    min_period_units: int
    profit_drop_percent: Decimal
    margin_drop_percentage_points: Decimal
    logistics_increase_percent: Decimal
    commission_increase_percent: Decimal


@dataclass(frozen=True)
class PromotionMonitoringConfig:
    ending_soon_days: int


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError(f"duplicate config field: {key}")
        result[key] = value
    return result


def _strict_object(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be an object")
    missing = sorted(fields - set(value))
    unknown = sorted(set(value) - fields)
    if missing:
        raise ConfigurationError(f"{name} missing fields: {', '.join(missing)}")
    if unknown:
        raise ConfigurationError(f"{name} unknown fields: {', '.join(unknown)}")
    return value


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{name} must be a non-empty string")
    return value.strip()


def _decimal_string(value: Any, name: str) -> Decimal:
    if not isinstance(value, str):
        raise ConfigurationError(f"{name} must be a Decimal string")
    try:
        parsed = Decimal(value.strip())
    except (InvalidOperation, ValueError) as error:
        raise ConfigurationError(f"{name} must be a Decimal string") from error
    if not parsed.is_finite():
        raise ConfigurationError(f"{name} must be finite")
    return parsed


def _nonnegative_decimal_string(value: Any, name: str) -> Decimal:
    parsed = _decimal_string(value, name)
    if parsed < 0:
        raise ConfigurationError(f"{name} must be greater than or equal to 0")
    return parsed


def _effective_datetime(value: Any, name: str) -> datetime:
    raw = _nonempty_string(value, name)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an RFC3339 timestamp") from error
    if "T" not in raw or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ConfigurationError(f"{name} must be an RFC3339 timestamp with offset")
    return parsed


def _effective_date(value: Any, name: str) -> date:
    raw = _nonempty_string(value, name)
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an ISO date") from error
    if len(raw) != 10:
        raise ConfigurationError(f"{name} must be an ISO date")
    return parsed


def _price_calculator_config(value: Any) -> PriceCalculatorConfig:
    data = _strict_object(value, {
        "version", "effective_from", "scheme", "buyout_rate", "acquiring_rate",
        "processing_amount", "return_processing_amount", "other_expenses",
        "handover_status", "recommended_slot_adjustment_pp", "margin_policy",
        "logistics_profile",
    }, "price calculator config")

    version = _nonempty_string(data["version"], "version")
    effective_from = _effective_datetime(data["effective_from"], "effective_from")
    scheme = _nonempty_string(data["scheme"], "scheme")
    if scheme != "FBS":
        raise ConfigurationError("scheme must be FBS")

    buyout_rate = _decimal_string(data["buyout_rate"], "buyout_rate")
    if not Decimal("0") < buyout_rate <= Decimal("1"):
        raise ConfigurationError("buyout_rate must be greater than 0 and less than or equal to 1")
    acquiring_rate = _decimal_string(data["acquiring_rate"], "acquiring_rate")
    if not Decimal("0") <= acquiring_rate <= Decimal("1"):
        raise ConfigurationError("acquiring_rate must be between 0 and 1")

    processing_amount = _nonnegative_decimal_string(data["processing_amount"], "processing_amount")
    return_processing_amount = _nonnegative_decimal_string(
        data["return_processing_amount"], "return_processing_amount"
    )
    other_expenses = _nonnegative_decimal_string(data["other_expenses"], "other_expenses")

    handover_status = _nonempty_string(data["handover_status"], "handover_status")
    if handover_status != "recommended_slot":
        raise ConfigurationError("handover_status must be recommended_slot")
    recommended_slot_adjustment_pp = _decimal_string(
        data["recommended_slot_adjustment_pp"], "recommended_slot_adjustment_pp"
    )

    margin_data = _strict_object(
        data["margin_policy"], {"hard_floor", "working_minimum", "target"}, "margin_policy"
    )
    margin_policy = PriceCalculatorMarginPolicyConfig(
        hard_floor=_decimal_string(margin_data["hard_floor"], "margin_policy.hard_floor"),
        working_minimum=_decimal_string(
            margin_data["working_minimum"], "margin_policy.working_minimum"
        ),
        target=_decimal_string(margin_data["target"], "margin_policy.target"),
    )
    if not (
        Decimal("0") <= margin_policy.hard_floor
        < margin_policy.working_minimum
        < margin_policy.target
        <= Decimal("1")
    ):
        raise ConfigurationError("margin_policy must satisfy 0 <= hard_floor < working_minimum < target <= 1")

    profile_data = _strict_object(data["logistics_profile"], {
        "tariff_source", "tariff_version", "tariff_effective_from",
        "seller_price_band", "route", "products",
    }, "logistics_profile")
    tariff_source = _nonempty_string(profile_data["tariff_source"], "logistics_profile.tariff_source")
    tariff_version = _nonempty_string(profile_data["tariff_version"], "logistics_profile.tariff_version")
    tariff_effective_from = _effective_date(
        profile_data["tariff_effective_from"], "logistics_profile.tariff_effective_from"
    )

    band_data = _strict_object(
        profile_data["seller_price_band"], {"lower_exclusive", "upper_inclusive"},
        "logistics_profile.seller_price_band",
    )
    lower_exclusive = _nonnegative_decimal_string(
        band_data["lower_exclusive"], "logistics_profile.seller_price_band.lower_exclusive"
    )
    upper_value = band_data["upper_inclusive"]
    upper_inclusive = None if upper_value is None else _nonnegative_decimal_string(
        upper_value, "logistics_profile.seller_price_band.upper_inclusive"
    )
    if upper_inclusive is not None and upper_inclusive <= lower_exclusive:
        raise ConfigurationError("seller price upper bound must be greater than lower bound")
    seller_price_band = SellerPriceBandConfig(lower_exclusive, upper_inclusive)

    route_data = _strict_object(
        profile_data["route"], {"origin_cluster", "destination_cluster", "return_scenario"},
        "logistics_profile.route",
    )
    route = LogisticsRouteConfig(
        origin_cluster=_nonempty_string(
            route_data["origin_cluster"], "logistics_profile.route.origin_cluster"
        ),
        destination_cluster=_nonempty_string(
            route_data["destination_cluster"], "logistics_profile.route.destination_cluster"
        ),
        return_scenario=_nonempty_string(
            route_data["return_scenario"], "logistics_profile.route.return_scenario"
        ),
    )
    if route.return_scenario != "return_to_seller":
        raise ConfigurationError("return_scenario must be return_to_seller")

    product_data = profile_data["products"]
    if not isinstance(product_data, dict):
        raise ConfigurationError("logistics_profile.products must be an object")
    if any(not isinstance(offer_id, str) or not offer_id.strip() for offer_id in product_data):
        raise ConfigurationError("logistics profile offer_id must be a non-empty string")
    actual_offer_ids = set(product_data)
    if actual_offer_ids != APPROVED_CALCULATOR_OFFER_IDS:
        missing = sorted(APPROVED_CALCULATOR_OFFER_IDS - actual_offer_ids)
        unknown = sorted(actual_offer_ids - APPROVED_CALCULATOR_OFFER_IDS)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unknown:
            details.append("unknown: " + ", ".join(unknown))
        raise ConfigurationError("logistics profile must contain exactly five approved offer_ids (" + "; ".join(details) + ")")

    products: dict[str, ProductLogisticsConfig] = {}
    for offer_id, product_value in product_data.items():
        product = _strict_object(
            product_value, {"volume_l", "forward_logistics_amount"},
            f"logistics_profile.products.{offer_id}",
        )
        volume_l = _decimal_string(product["volume_l"], f"{offer_id}.volume_l")
        if volume_l <= 0:
            raise ConfigurationError(f"{offer_id}.volume_l must be greater than 0")
        products[offer_id] = ProductLogisticsConfig(
            volume_l=volume_l,
            forward_logistics_amount=_nonnegative_decimal_string(
                product["forward_logistics_amount"], f"{offer_id}.forward_logistics_amount"
            ),
        )

    logistics_profile = LogisticsProfileConfig(
        tariff_source=tariff_source,
        tariff_version=tariff_version,
        tariff_effective_from=tariff_effective_from,
        seller_price_band=seller_price_band,
        route=route,
        products=MappingProxyType(products),
    )
    return PriceCalculatorConfig(
        version=version,
        effective_from=effective_from,
        scheme=scheme,
        buyout_rate=buyout_rate,
        acquiring_rate=acquiring_rate,
        processing_amount=processing_amount,
        return_processing_amount=return_processing_amount,
        other_expenses=other_expenses,
        handover_status=handover_status,
        recommended_slot_adjustment_pp=recommended_slot_adjustment_pp,
        margin_policy=margin_policy,
        logistics_profile=logistics_profile,
    )


def load_price_calculator_config(
    path: str | Path = "config/ozon_price_calculator_v1.json",
) -> PriceCalculatorConfig:
    config_path = Path(path)
    try:
        raw = json.loads(
            config_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except ConfigurationError:
        raise
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"Unable to read price calculator config: {config_path}") from error
    return _price_calculator_config(raw)


def load_database_config(environ: Mapping[str, str] | None = None) -> DatabaseConfig:
    environment = os.environ if environ is None else environ
    required = ("EFA_DB_HOST", "EFA_DB_PORT", "EFA_DB_NAME", "EFA_DB_USER", "EFA_DB_PASSWORD")
    missing = [name for name in required if not environment.get(name, "").strip()]
    if missing:
        raise ConfigurationError("Missing required environment variables: " + ", ".join(missing))
    try:
        port = int(environment["EFA_DB_PORT"])
    except ValueError as error:
        raise ConfigurationError("EFA_DB_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError("EFA_DB_PORT must be between 1 and 65535")
    return DatabaseConfig(environment["EFA_DB_HOST"].strip(), port, environment["EFA_DB_NAME"].strip(), environment["EFA_DB_USER"].strip(), environment["EFA_DB_PASSWORD"])


def load_recommendation_config(environ: Mapping[str, str] | None = None) -> RecommendationConfig:
    environment = os.environ if environ is None else environ
    try:
        margin = Decimal(environment.get("EFA_RECOMMENDATION_LOW_MARGIN_PERCENT", "15"))
        max_step = Decimal(environment.get("EFA_RECOMMENDATION_MAX_PRICE_STEP_PERCENT", "20"))
        min_units = int(environment.get("EFA_RECOMMENDATION_MIN_WINDOW_UNITS", "10"))
    except (InvalidOperation, ValueError) as error:
        raise ConfigurationError("Recommendation thresholds must be numeric") from error
    if not Decimal("0") < margin < Decimal("100") or not Decimal("0") < max_step <= Decimal("100") or min_units < 1:
        raise ConfigurationError("Recommendation thresholds are outside safe bounds")
    return RecommendationConfig(margin, min_units, max_step)


def load_anomaly_config(environ: Mapping[str, str] | None = None) -> AnomalyConfig:
    environment = os.environ if environ is None else environ
    try:
        min_units = int(environment.get("EFA_ANOMALY_MIN_PERIOD_UNITS", "5"))
        profit_drop = Decimal(environment.get("EFA_ANOMALY_PROFIT_DROP_PERCENT", "20"))
        margin_drop = Decimal(environment.get("EFA_ANOMALY_MARGIN_DROP_PERCENTAGE_POINTS", "5"))
        logistics_increase = Decimal(environment.get("EFA_ANOMALY_LOGISTICS_INCREASE_PERCENT", "20"))
        commission_increase = Decimal(environment.get("EFA_ANOMALY_COMMISSION_INCREASE_PERCENT", "20"))
    except (InvalidOperation, ValueError) as error:
        raise ConfigurationError("Anomaly thresholds must be numeric") from error
    thresholds = (profit_drop, margin_drop, logistics_increase, commission_increase)
    if min_units < 1 or any(value <= 0 or value > 100 for value in thresholds):
        raise ConfigurationError("Anomaly thresholds are outside safe bounds")
    return AnomalyConfig(min_units, profit_drop, margin_drop, logistics_increase, commission_increase)


def load_promotion_monitoring_config(environ: Mapping[str, str] | None = None) -> PromotionMonitoringConfig:
    environment = os.environ if environ is None else environ
    try:
        ending_soon_days = int(environment.get("EFA_PROMOTION_ENDING_SOON_DAYS", "7"))
    except ValueError as error:
        raise ConfigurationError("EFA_PROMOTION_ENDING_SOON_DAYS must be an integer") from error
    if not 1 <= ending_soon_days <= 90:
        raise ConfigurationError("EFA_PROMOTION_ENDING_SOON_DAYS must be between 1 and 90")
    return PromotionMonitoringConfig(ending_soon_days)
