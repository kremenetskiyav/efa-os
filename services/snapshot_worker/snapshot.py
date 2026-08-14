"""In-memory dry-run snapshot candidates without PostgreSQL writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from database import ProductPriceHistory


@dataclass(frozen=True)
class SnapshotCandidate:
    """The future product_snapshots fields available from existing sources."""

    offer_id: str
    current_price: Decimal | None
    price_updated_from_ozon: datetime | None
    cost_price_used: Decimal | None


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
        )
        for product in products
    ]
