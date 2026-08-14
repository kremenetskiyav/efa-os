"""Typed read models for Price & Profit Recommendation Engine v0.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ProductEconomics:
    offer_id: str
    current_price: Decimal | None
    cost_price: Decimal | None
    revenue: Decimal | None
    profit: Decimal | None
    commission: Decimal | None
    logistics: Decimal | None
    period_start: datetime | None
    period_end: datetime | None
    delivered_units: int | None
    analytics_revenue: Decimal | None
    analytics_profit: Decimal | None


@dataclass(frozen=True)
class Recommendation:
    offer_id: str
    current_price: Decimal | None
    cost_price: Decimal | None
    revenue: Decimal | None
    profit: Decimal | None
    profit_per_unit: Decimal | None
    profit_margin_percent: Decimal | None
    commission: Decimal | None
    logistics: Decimal | None
    period_start: datetime | None
    period_end: datetime | None
    data_quality_status: str
    action: str
    priority: str
    reasons: tuple[str, ...]
    proposed_price: Decimal | None
    proposed_price_range: str | None
    proposal_reason: str | None
