"""Read models for the confirmed, read-only v0.2 economics pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PriceWindow:
    seller_price: Decimal | None
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
    delivery_start: datetime
    delivery_end: datetime


@dataclass(frozen=True)
class ProductEconomics:
    offer_id: str
    current_price: Decimal | None
    current_price_since: datetime | None
    cost_price: Decimal | None
    windows: tuple[PriceWindow, ...]
    last_confirmed: PriceWindow | None = None
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
    last_confirmed_effective_price: Decimal | None
    last_confirmed_delivery_date: datetime | None
    last_confirmed_profit_per_unit: Decimal | None
    last_confirmed_margin: Decimal | None
    current_price_economics_status: str
    current_price_since: datetime | None


@dataclass(frozen=True)
class PeriodEconomics:
    period_start: datetime | None
    period_end: datetime | None
    units: int
    orders: int
    revenue: Decimal
    profit: Decimal
    commission: Decimal
    logistics: Decimal
    other_expenses: Decimal
    unallocated_expense_lines: int


@dataclass(frozen=True)
class ProfitCostAnomaly:
    offer_id: str
    severity: str
    anomalies: tuple[str, ...]
    current: dict[str, Decimal | int | datetime | None]
    baseline: dict[str, Decimal | int | datetime | None]
    changes: dict[str, Decimal | None]
    data_quality_status: str
    reasons: tuple[str, ...]
    recommended_attention: str


@dataclass(frozen=True)
class PromotionState:
    offer_id: str | None
    product_id: int
    action_id: int
    action_title: str | None
    action_type: str | None
    action_start_at: datetime | None
    action_end_at: datetime | None
    source_list_type: str
    add_mode: str | None
    price: Decimal | None
    action_price: Decimal | None
    max_action_price: Decimal | None
    collected_at: datetime
    data_quality_status: str
    signals: tuple[str, ...]


@dataclass(frozen=True)
class PromotionRecommendation:
    """Read-only recommendation context; no promotion action is performed."""

    offer_id: str | None
    action_id: int
    action_title: str | None
    action_type: str | None
    source_list_type: str
    current_price: Decimal | None
    action_price: Decimal | None
    max_action_price: Decimal | None
    confirmed_effective_price: Decimal | None
    confirmed_profit_per_unit: Decimal | None
    confirmed_margin_percent: Decimal | None
    economics_confidence: str
    current_price_economics_status: str
    data_quality_status: str
    recommendation: str
    reasons: tuple[str, ...]
    numeric_projection_allowed: bool
