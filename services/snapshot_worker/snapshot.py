"""Snapshot preparation rules shared by dry-run and write modes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable
from zoneinfo import ZoneInfo

from database import ProductPriceHistory


BUSINESS_TIMEZONE = ZoneInfo("Europe/Moscow")
RUN_TYPE_DAILY = "daily"
SOURCE_NAME = "ozon_phase_a"


@dataclass(frozen=True)
class SnapshotCandidate:
    """A product_snapshots row prepared from existing Phase A sources."""

    offer_id: str
    current_price: Decimal | None
    price_updated_from_ozon: datetime | None
    cost_price_used: Decimal | None
    data_quality_status: str


def calculate_business_date(now: datetime | None = None) -> date:
    """Return the operational date in Europe/Moscow from a UTC instant."""

    instant = datetime.now(timezone.utc) if now is None else now
    if instant.tzinfo is None:
        raise ValueError("Business date requires a timezone-aware timestamp")
    return instant.astimezone(BUSINESS_TIMEZONE).date()


def build_daily_idempotency_key(business_date: date) -> str:
    """Build the deterministic key for exactly one daily logical run."""

    return f"snapshot_worker:v1:{RUN_TYPE_DAILY}:{business_date.isoformat()}"


def build_snapshot_candidates(
    products: Iterable[ProductPriceHistory],
) -> list[SnapshotCandidate]:
    """Map each product to an in-memory snapshot candidate for dry-run reporting."""

    return [
        SnapshotCandidate(
            offer_id=product.offer_id,
            current_price=product.current_price,
            price_updated_from_ozon=product.price_updated_from_ozon,
            cost_price_used=product.cost_price_used,
            data_quality_status=(
                "valid"
                if product.current_price is not None
                and product.price_updated_from_ozon is not None
                else "invalid"
            ),
        )
        for product in products
    ]
