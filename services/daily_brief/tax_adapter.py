"""Read-only adapter from the persisted tax ledger to Tax Engine v0.1."""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
from typing import Any

from services.tax_engine.calculator import calculate_tax_state
from services.tax_engine.models import TaxpayerConfig, TaxRevenueEvent


def calculate_persisted_tax_state(
    rows: list[tuple[Any, ...]],
    import_runs: list[tuple[Any, ...]],
    business_date: date,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Invoke the existing Tax Engine without copying its statutory formulas."""
    path = Path(config_path or os.environ.get("EFA_TAX_CONFIG_PATH", "config/taxpayer.2026.json"))
    config = TaxpayerConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
    events = [
        TaxRevenueEvent(
            event_id=row[0], tax_year=row[1], source_period=row[2], event_type=row[3],
            posting_number=row[4], offer_id=row[5], sku=row[6], event_date=row[7],
            amount=row[8], source_document=row[9], source_reference=row[10],
            tax_semantics_status=row[11], tax_date_status=row[12], data_quality_status=row[13],
        )
        for row in rows
    ]
    completed_month = business_date.month - 1
    expected = [f"{config.tax_year}-{month:02d}" for month in range(1, completed_month + 1)]
    confirmed_zero = [f"{config.tax_year}-{month:02d}" for month in range(1, min(5, completed_month) + 1)]
    state = calculate_tax_state(events, config, confirmed_zero, expected)
    successful_runs = [row for row in import_runs if row[1] == "success"]
    state.update({
        "engine_state": "ACTIVE",
        "latest_source_period": max((row[0] for row in successful_runs), default=None),
        "import_runs_count": len(successful_runs),
        "expected_through_period": expected[-1] if expected else None,
    })
    return state
