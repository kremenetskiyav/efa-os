"""Read-only shadow orchestration for EFA Ozon Price Calculator V1."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Callable, Collection, Sequence

try:
    from .calculator import (
        CalculatorValidationError,
        calculate_unit_economics,
        find_price_for_margin,
    )
    from .config import (
        ConfigurationError,
        DatabaseConfig,
        PriceCalculatorConfig,
        load_database_config,
        load_price_calculator_config,
    )
    from .database import DatabaseError, fetch_calculator_source_rows
    from .input_resolver import (
        CalculatorSourceRow,
        InputResolutionError,
        ResolvedCalculatorInputs,
        resolve_calculator_inputs,
    )
except ImportError:
    from calculator import CalculatorValidationError, calculate_unit_economics, find_price_for_margin
    from config import (
        ConfigurationError,
        DatabaseConfig,
        PriceCalculatorConfig,
        load_database_config,
        load_price_calculator_config,
    )
    from database import DatabaseError, fetch_calculator_source_rows
    from input_resolver import (
        CalculatorSourceRow,
        InputResolutionError,
        ResolvedCalculatorInputs,
        resolve_calculator_inputs,
    )


PRICE_STEP = Decimal("1")
TECHNICAL_SEARCH_CEILING_MULTIPLIER = Decimal("10")
SourceLoader = Callable[[DatabaseConfig, Collection[str]], list[CalculatorSourceRow]]


def generate_shadow_report(
    *,
    calculator_config: PriceCalculatorConfig,
    database_config: DatabaseConfig,
    tax_rate: Decimal,
    taxpayer_config_version: str,
    calculation_at: datetime,
    source_loader: SourceLoader = fetch_calculator_source_rows,
) -> dict[str, object]:
    """Read sources once and calculate an in-memory shadow report."""

    offer_ids = tuple(sorted(calculator_config.logistics_profile.products))
    sources = source_loader(database_config, offer_ids)
    actual_offer_ids = [source.offer_id for source in sources]
    if len(sources) != len(offer_ids) or set(actual_offer_ids) != set(offer_ids):
        raise InputResolutionError("calculator source must contain exactly the approved offer_ids")
    if len(set(actual_offer_ids)) != len(actual_offer_ids):
        raise InputResolutionError("calculator source contains duplicate offer_id")

    items = []
    for source in sorted(sources, key=lambda item: item.offer_id):
        resolved = resolve_calculator_inputs(
            source,
            calculator_config,
            tax_rate,
            calculation_at,
            taxpayer_config_version,
        )
        items.append(_shadow_item(resolved, calculator_config))
    return {
        "mode": "SHADOW",
        "read_only": True,
        "calculation_at": calculation_at.isoformat(),
        "calculator_config_version": calculator_config.version,
        "items": items,
    }


def _shadow_item(
    resolved: ResolvedCalculatorInputs,
    config: PriceCalculatorConfig,
) -> dict[str, object]:
    arguments = resolved.calculator_arguments()
    result = calculate_unit_economics(seller_price=resolved.seller_price, **arguments)
    search_from, search_to = _search_bounds(resolved, config)
    targets = {
        "p10": config.margin_policy.hard_floor,
        "p12": config.margin_policy.working_minimum,
        "p15": config.margin_policy.target,
    }
    prices = {
        name: find_price_for_margin(
            target_margin=target,
            search_from=search_from,
            search_to=search_to,
            price_step=PRICE_STEP,
            **arguments,
        )
        for name, target in targets.items()
    }
    return {
        "offer_id": resolved.offer_id,
        "product_id": resolved.product_id,
        "seller_price": str(resolved.seller_price),
        "cost_price": str(resolved.cost_price),
        "resolved_inputs": {
            "commission_rate": str(resolved.commission_rate),
            "acquiring_rate": str(resolved.acquiring_rate),
            "processing_amount": str(resolved.processing_amount),
            "forward_logistics_amount": str(resolved.forward_logistics_amount),
            "delivery_to_customer_amount": str(resolved.delivery_to_customer_amount),
            "return_logistics_amount": str(resolved.return_logistics_amount),
            "return_processing_amount": str(resolved.return_processing_amount),
            "buyout_rate": str(resolved.buyout_rate),
            "tax_rate": str(resolved.tax_rate),
            "other_expenses": str(resolved.other_expenses),
        },
        "provenance": dict(resolved.provenance),
        "snapshot": {
            "snapshot_id": resolved.snapshot_id,
            "price_collection_run_id": resolved.price_collection_run_id,
            "observed_at": resolved.observed_at.isoformat(),
        },
        "versions": {
            "calculator_config": resolved.calculator_config_version,
            "tariff_profile": resolved.tariff_profile_version,
            "taxpayer_config": resolved.taxpayer_config_version,
        },
        "search": {
            "search_from": str(search_from),
            "search_to": str(search_to),
            "price_step": str(PRICE_STEP),
            "ceiling_policy": (
                "tariff_profile.upper_inclusive"
                if config.logistics_profile.seller_price_band.upper_inclusive is not None
                else "technical:current_seller_price_x10"
            ),
        },
        "results": {
            "profit": str(result.profit),
            "margin": str(result.margin),
            **{name: str(price) if price is not None else None for name, price in prices.items()},
        },
    }


def _search_bounds(
    resolved: ResolvedCalculatorInputs,
    config: PriceCalculatorConfig,
) -> tuple[Decimal, Decimal]:
    band = config.logistics_profile.seller_price_band
    search_from = band.lower_exclusive + PRICE_STEP
    if search_from <= band.lower_exclusive:
        raise InputResolutionError("price step cannot advance beyond the lower-exclusive bound")
    search_to = (
        band.upper_inclusive
        if band.upper_inclusive is not None
        else resolved.seller_price * TECHNICAL_SEARCH_CEILING_MULTIPLIER
    )
    if search_to < search_from:
        raise InputResolutionError("approved seller-price band contains no searchable candidate")
    return search_from, search_to


def _load_taxpayer_context(path: Path, calculation_year: int) -> tuple[Decimal, str]:
    try:
        try:
            from tax_engine.main import load_config as load_taxpayer_config
        except ImportError:
            from services.tax_engine.main import load_config as load_taxpayer_config

        taxpayer_config = load_taxpayer_config(str(path))
        raw = json.loads(path.read_text(encoding="utf-8"))
        version = raw.get("version") if isinstance(raw, dict) else None
    except Exception as error:
        raise ConfigurationError(f"Unable to load taxpayer config: {path}") from error
    if taxpayer_config.tax_year != calculation_year:
        raise ConfigurationError("taxpayer config year does not match calculation_at")
    if not isinstance(version, str) or not version.strip():
        raise ConfigurationError("taxpayer config version must be non-empty")
    return taxpayer_config.usn_rate, version.strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only EFA Ozon Price Calculator V1 shadow")
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
        report = generate_shadow_report(
            calculator_config=calculator_config,
            database_config=load_database_config(),
            tax_rate=tax_rate,
            taxpayer_config_version=taxpayer_version,
            calculation_at=calculation_at,
        )
    except (
        CalculatorValidationError,
        ConfigurationError,
        DatabaseError,
        InputResolutionError,
    ) as error:
        print(json.dumps({"mode": "SHADOW", "read_only": True, "error": str(error)}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
