"""Read models for the confirmed, read-only v0.2 economics pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PriceWindow:
    effective_price: Decimal
    units: int
    orders: int
    revenue: Decimal
    commission: Decimal
    logistics: Decimal
    other_expenses: Decimal
    cost: Decimal
    payout: Decimal
    profit: Decimal
    period_start: datetime
    period_end: datetime


@dataclass(frozen=True)
class ProductEconomics:
    offer_id: str
    current_price: Decimal | None
    cost_price: Decimal | None
    windows: tuple[PriceWindow, ...]
    data_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    offer_id: str
    current_price: Decimal | None
    current_effective_price: Decimal | None
    revenue: Decimal | None
    profit: Decimal | None
    profit_per_unit: Decimal | None
    profit_margin_percent: Decimal | None
    commission: Decimal | None
    logistics: Decimal | None
    other_expenses: Decimal | None
    period_start: datetime | None
    period_end: datetime | None
    action: str
    priority: str
    proposed_price: Decimal | None
    expected_profit_per_unit: Decimal | None
    expected_margin_percent: Decimal | None
    confidence: str
    data_quality_status: str
    reasons: tuple[str, ...]
