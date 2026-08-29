"""Read-only CPC economics shadow over the existing Calculator V1 core."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Collection, Sequence
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

try:
    from .advertising_overlay import (
        AdvertisingOverlayError,
        CpcObservation,
        calculate_advertising_planning_ceilings,
        calculate_five_percent_scenario,
        classify_cpc_observation,
    )
    from .calculator import CalculatorValidationError, MarginPolicy, calculate_unit_economics
    from .calculator_shadow import _load_taxpayer_context
    from .config import (
        ConfigurationError,
        DatabaseConfig,
        PriceCalculatorConfig,
        load_database_config,
        load_price_calculator_config,
    )
    from .database import (
        DatabaseError,
        fetch_calculator_source_rows,
        fetch_latest_product_cpc_observations,
    )
    from .input_resolver import (
        CalculatorSourceRow,
        InputResolutionError,
        resolve_calculator_inputs,
    )
except ImportError:
    from advertising_overlay import (
        AdvertisingOverlayError,
        CpcObservation,
        calculate_advertising_planning_ceilings,
        calculate_five_percent_scenario,
        classify_cpc_observation,
    )
    from calculator import CalculatorValidationError, MarginPolicy, calculate_unit_economics
    from calculator_shadow import _load_taxpayer_context
    from config import (
        ConfigurationError,
        DatabaseConfig,
        PriceCalculatorConfig,
        load_database_config,
        load_price_calculator_config,
    )
    from database import (
        DatabaseError,
        fetch_calculator_source_rows,
        fetch_latest_product_cpc_observations,
    )
    from input_resolver import (
        CalculatorSourceRow,
        InputResolutionError,
        resolve_calculator_inputs,
    )


SourceLoader = Callable[[DatabaseConfig, Collection[str]], list[CalculatorSourceRow]]
CpcLoader = Callable[[DatabaseConfig, Collection[str]], list[CpcObservation]]


def generate_advertising_shadow_report(
    *,
    calculator_config: PriceCalculatorConfig,
    database_config: DatabaseConfig,
    tax_rate: Decimal,
    taxpayer_config_version: str,
    calculation_at: datetime,
    source_loader: SourceLoader = fetch_calculator_source_rows,
    cpc_loader: CpcLoader = fetch_latest_product_cpc_observations,
) -> dict[str, object]:
    """Read Calculator and product CPC sources once and calculate in memory."""

    offer_ids = tuple(sorted(calculator_config.logistics_profile.products))
    sources = source_loader(database_config, offer_ids)
    _validate_exact_source_scope(offer_ids, [source.offer_id for source in sources])
    observations = cpc_loader(database_config, offer_ids)
    _validate_cpc_scope(offer_ids, observations)
    observation_by_offer = {row.offer_id: row for row in observations}
    margin_policy = MarginPolicy(
        calculator_config.margin_policy.hard_floor,
        calculator_config.margin_policy.working_minimum,
        calculator_config.margin_policy.target,
    )

    items = []
    for source in sorted(sources, key=lambda item: item.offer_id):
        resolved = resolve_calculator_inputs(
            source,
            calculator_config,
            tax_rate,
            calculation_at,
            taxpayer_config_version,
        )
        core = calculate_unit_economics(
            seller_price=resolved.seller_price,
            **resolved.calculator_arguments(),
        )
        planning = calculate_advertising_planning_ceilings(
            core, resolved.seller_price, margin_policy
        )
        scenario = calculate_five_percent_scenario(
            core, resolved.seller_price, margin_policy
        )
        observation = observation_by_offer.get(resolved.offer_id)
        observed_status = classify_cpc_observation(observation, calculation_at)
        items.append({
            "offer_id": resolved.offer_id,
            "core": {
                "seller_price": str(core.seller_price),
                "profit": str(core.profit),
                "margin": str(core.margin),
            },
            "advertising_planning": {
                "rate_basis": "per-unit cost / current seller_price",
                "max_ad_cost_at_target": str(planning.max_ad_cost_at_target),
                "max_ad_rate_at_target": str(planning.max_ad_rate_at_target),
                "max_ad_cost_at_working_min": str(
                    planning.max_ad_cost_at_working_min
                ),
                "max_ad_rate_at_working_min": str(
                    planning.max_ad_rate_at_working_min
                ),
                "max_ad_cost_at_hard_floor": str(
                    planning.max_ad_cost_at_hard_floor
                ),
                "max_ad_rate_at_hard_floor": str(
                    planning.max_ad_rate_at_hard_floor
                ),
                "five_percent_scenario": {
                    "advertising_rate": "0.05",
                    "advertising_cost": str(scenario.advertising_cost),
                    "after_ads_profit": str(scenario.after_ads_profit),
                    "after_ads_margin": str(scenario.after_ads_margin),
                    "margin_classification": scenario.margin_classification.value,
                    "forecast_status": scenario.analytical_status.value,
                },
            },
            "advertising_observed": _observed_payload(
                observation,
                observed_status.value if observed_status is not None else None,
            ),
        })
    return {
        "mode": "ADVERTISING_SHADOW",
        "read_only": True,
        "calculation_at": calculation_at.isoformat(),
        "calculator_config_version": calculator_config.version,
        "observed_drr_basis": "spend / attributed_revenue * 100",
        "observed_general_drr_basis": "spend / product_gmv * 100",
        "items": items,
    }


def _observed_payload(
    observation: CpcObservation | None,
    status: str | None,
) -> dict[str, object]:
    if observation is None:
        return {
            "business_date": None,
            "observed_at": None,
            "active_campaigns_count": None,
            "spend": None,
            "attributed_orders": None,
            "attributed_revenue": None,
            "product_gmv": None,
            "drr_percent": None,
            "general_drr_percent": None,
            "average_bid": None,
            "data_quality_status": None,
            "collection_status": None,
            "observed_status": status,
        }
    return {
        "business_date": observation.business_date.isoformat(),
        "observed_at": observation.observed_at.isoformat(),
        "active_campaigns_count": observation.active_campaigns_count,
        "spend": _optional_string(observation.spend),
        "attributed_orders": observation.attributed_orders,
        "attributed_revenue": _optional_string(observation.attributed_revenue),
        "product_gmv": _optional_string(observation.product_gmv),
        "drr_percent": _optional_string(observation.drr_percent),
        "general_drr_percent": _optional_string(observation.general_drr_percent),
        "average_bid": _optional_string(observation.average_bid),
        "data_quality_status": observation.data_quality_status,
        "collection_status": observation.collection_status,
        "observed_status": status,
    }


def _optional_string(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _validate_exact_source_scope(
    offer_ids: Collection[str],
    actual_offer_ids: list[str],
) -> None:
    if len(actual_offer_ids) != len(offer_ids) or set(actual_offer_ids) != set(offer_ids):
        raise InputResolutionError(
            "calculator source must contain exactly the approved offer_ids"
        )
    if len(set(actual_offer_ids)) != len(actual_offer_ids):
        raise InputResolutionError("calculator source contains duplicate offer_id")


def _validate_cpc_scope(
    offer_ids: Collection[str],
    observations: list[CpcObservation],
) -> None:
    actual_offer_ids = [row.offer_id for row in observations]
    if not set(actual_offer_ids).issubset(set(offer_ids)):
        raise InputResolutionError("CPC source contains an unapproved offer_id")
    if len(set(actual_offer_ids)) != len(actual_offer_ids):
        raise InputResolutionError("CPC source contains duplicate offer_id")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only EFA Ozon CPC economics overlay v1 shadow"
    )
    parser.add_argument(
        "--calculator-config",
        default="config/ozon_price_calculator_v1.json",
    )
    parser.add_argument("--taxpayer-config")
    args = parser.parse_args(argv)
    calculation_at = datetime.now(timezone.utc)
    taxpayer_path = Path(
        args.taxpayer_config or f"config/taxpayer.{calculation_at.year}.json"
    )
    try:
        calculator_config = load_price_calculator_config(args.calculator_config)
        tax_rate, taxpayer_version = _load_taxpayer_context(
            taxpayer_path, calculation_at.year
        )
        report = generate_advertising_shadow_report(
            calculator_config=calculator_config,
            database_config=load_database_config(),
            tax_rate=tax_rate,
            taxpayer_config_version=taxpayer_version,
            calculation_at=calculation_at,
        )
    except (
        AdvertisingOverlayError,
        CalculatorValidationError,
        ConfigurationError,
        DatabaseError,
        InputResolutionError,
    ) as error:
        print(json.dumps({
            "mode": "ADVERTISING_SHADOW",
            "read_only": True,
            "error": str(error),
        }))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
