"""Strict MCP input and structured output contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


MAX_DATE_RANGE_DAYS = 366
DEFAULT_ROW_LIMIT = 100
MAX_ROW_LIMIT = 500
MAX_REGION_LIMIT = 200
DEFAULT_ANALYTICS_ROW_LIMIT = 200
MAX_ANALYTICS_ROW_LIMIT = 500
MAX_ANALYTICS_QUERY_LENGTH = 50_000
_OFFER_ID_PUNCTUATION = frozenset("-_./ ()+")


def validate_offer_id(value: str) -> str:
    """Accept compact Unicode identifiers and reject controls/query punctuation."""
    if not isinstance(value, str):
        raise ValueError("offer_id must be a string")
    if value != value.strip():
        raise ValueError("offer_id must not contain leading or trailing whitespace")
    if not 1 <= len(value) <= 64:
        raise ValueError("offer_id length must be between 1 and 64 characters")
    if not any(character.isalnum() for character in value):
        raise ValueError("offer_id must contain at least one letter or digit")
    if any(not character.isalnum() and character not in _OFFER_ID_PUNCTUATION for character in value):
        raise ValueError("offer_id contains unsupported characters")
    return value


OfferId = Annotated[str, AfterValidator(validate_offer_id), Field(description="Exact EFA offer_id")]
HistoryLimit = Annotated[int, Field(ge=1, le=MAX_ROW_LIMIT)]
RegionLimit = Annotated[int, Field(ge=1, le=MAX_REGION_LIMIT)]
AnalyticsLimit = Annotated[int, Field(ge=1, le=MAX_ANALYTICS_ROW_LIMIT)]
AnalyticsQuery = Annotated[str, Field(min_length=1, max_length=MAX_ANALYTICS_QUERY_LENGTH)]
Confidence = Literal["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
DataScope = Literal["ACCOUNT", "PRODUCT"]
ResultStatus = Literal["ok", "empty"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ListProductsInput(StrictInput):
    include_archived: bool = False


class ProductInput(StrictInput):
    offer_id: OfferId


class HistoryInput(ProductInput):
    date_from: date
    date_to: date
    limit: HistoryLimit = DEFAULT_ROW_LIMIT

    @model_validator(mode="after")
    def validate_date_range(self) -> "HistoryInput":
        _validate_date_range(self.date_from, self.date_to)
        return self


class RegionLogisticsInput(ProductInput):
    minimum_confidence: Confidence | None = None
    limit: RegionLimit = DEFAULT_ROW_LIMIT


class PromotionInput(ProductInput):
    active_only: bool = False


class CpcDailyInput(StrictInput):
    offer_id: OfferId | None = None
    date_from: date
    date_to: date
    data_scope: DataScope | None = None
    limit: HistoryLimit = DEFAULT_ROW_LIMIT

    @model_validator(mode="after")
    def validate_date_range(self) -> "CpcDailyInput":
        _validate_date_range(self.date_from, self.date_to)
        return self


class AnalyticsInput(StrictInput):
    query: AnalyticsQuery
    max_rows: AnalyticsLimit = DEFAULT_ANALYTICS_ROW_LIMIT


def _validate_date_range(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise ValueError("date_from must be on or before date_to")
    inclusive_days = (date_to - date_from).days + 1
    if inclusive_days > MAX_DATE_RANGE_DAYS:
        raise ValueError(f"date range must not exceed {MAX_DATE_RANGE_DAYS} calendar days")


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProductListItem(OutputModel):
    offer_id: str
    sku: int | None
    product_name: str | None
    brand: str | None
    is_archived: bool | None
    price_observed_at: datetime | None
    stock_snapshot_at: datetime | None


class ProductOverviewItem(OutputModel):
    offer_id: str
    sku: int | None
    ozon_product_id: int | None
    product_name: str | None
    brand: str | None
    is_archived: bool | None
    product_observed_at: datetime | None
    current_price: Decimal | None
    current_price_since: datetime | None
    price_observed_at: datetime | None
    price_checked_at: datetime | None
    cost_price: Decimal | None
    cost_basis: str | None
    stock_snapshot_at: datetime | None
    fbo_present: int | None
    fbs_present: int | None
    rfbs_present: int | None
    total_present: int | None
    total_reserved: int | None
    out_of_stock: bool | None
    stock_data_quality_status: str | None
    confirmed_units_at_current_price: int | None
    multi_line_units_excluded_at_current_price: int | None
    unmatched_finance_units_at_current_price: int | None
    current_price_economics_status: str | None
    regional_logistics_status: str | None
    regional_signal: str | None
    regional_data_quality: str | None


class PriceHistoryItem(OutputModel):
    offer_id: str
    observed_at: datetime
    price: Decimal | None
    previous_price: Decimal | None
    absolute_change: Decimal | None
    change_percent: Decimal | None
    min_price: Decimal | None
    marketing_price: Decimal | None
    marketing_seller_price: Decimal | None
    is_latest: bool | None


class StockHistoryItem(OutputModel):
    offer_id: str
    snapshot_at: datetime
    fbo_present: int | None
    fbo_reserved: int | None
    fbs_present: int | None
    fbs_reserved: int | None
    rfbs_present: int | None
    rfbs_reserved: int | None
    total_present: int | None
    total_reserved: int | None
    previous_total_present: int | None
    previous_total_reserved: int | None
    total_present_change: int | None
    total_reserved_change: int | None
    data_quality_status: str | None
    is_latest: bool | None


class DailyPerformanceItem(OutputModel):
    offer_id: str
    business_date: date
    ordered_units: int | None
    ordered_revenue: Decimal | None
    demand_collected_at: datetime | None
    demand_quality_status: str | None
    delivered_units: int | None
    return_events: int | None
    returned_units: int | None
    finance_matched_lines: int | None
    finance_matched_delivered_units: int | None
    multi_line_excluded_units: int | None
    unmatched_finance_units: int | None
    confirmed_revenue: Decimal | None
    commission_expense: Decimal | None
    logistics_expense: Decimal | None
    other_expenses: Decimal | None
    cost_of_goods: Decimal | None
    payout: Decimal | None
    profit_before_tax: Decimal | None
    profit_per_unit: Decimal | None
    profit_margin_percent: Decimal | None
    cost_basis: str | None
    economics_quality_status: str | None
    postings_collection_status: str | None
    postings_collected_at: datetime | None
    returns_collection_status: str | None
    returns_collected_at: datetime | None
    finance_collection_status: str | None
    finance_collected_at: datetime | None


class RegionLogisticsItem(OutputModel):
    offer_id: str
    cluster_from: str | None
    cluster_to: str | None
    orders_count: int | None
    avg_logistics: Decimal | None
    baseline_logistics: Decimal | None
    logistics_delta: Decimal | None
    logistics_delta_percent: Decimal | None
    avg_revenue: Decimal | None
    baseline_revenue: Decimal | None
    logistics_rate_percent: Decimal | None
    baseline_logistics_rate_percent: Decimal | None
    logistics_rate_delta_pp: Decimal | None
    confidence: Confidence | None
    data_from: datetime | None
    data_through: datetime | None
    rule_version: str | None


class PromotionStateItem(OutputModel):
    offer_id: str
    ozon_promotion_id: int | None
    promotion_title: str | None
    promotion_type: str | None
    participation_state: str | None
    add_mode: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    observed_price: Decimal | None
    promotion_price: Decimal | None
    max_promotion_price: Decimal | None
    current_boost: Decimal | None
    min_boost: Decimal | None
    max_boost: Decimal | None
    observed_at: datetime | None
    data_quality_status: str | None


class CpcDailyItem(OutputModel):
    business_date: date
    data_scope: DataScope
    offer_id: str | None
    campaigns_count: int | None
    active_campaigns_count: int | None
    views: int | None
    clicks: int | None
    ctr_percent: Decimal | None
    spend: Decimal | None
    attributed_orders: int | None
    attributed_revenue: Decimal | None
    product_gmv: Decimal | None
    drr_percent: Decimal | None
    general_drr_percent: Decimal | None
    average_bid: Decimal | None
    data_quality_status: str | None
    collection_status: str | None
    observed_at: datetime | None


class ListProductsResponse(OutputModel):
    tool: Literal["list_products"] = "list_products"
    correlation_id: str
    result_status: ResultStatus
    row_count: int
    items: list[ProductListItem]
    known_limitations: list[str]


class ProductOverviewResponse(OutputModel):
    tool: Literal["get_product_overview"] = "get_product_overview"
    correlation_id: str
    result_status: ResultStatus
    row_count: int
    item: ProductOverviewItem | None
    known_limitations: list[str]


class PriceHistoryResponse(OutputModel):
    tool: Literal["get_price_history"] = "get_price_history"
    correlation_id: str
    result_status: ResultStatus
    row_count: int
    items: list[PriceHistoryItem]
    known_limitations: list[str]


class StockHistoryResponse(OutputModel):
    tool: Literal["get_stock_history"] = "get_stock_history"
    correlation_id: str
    result_status: ResultStatus
    row_count: int
    items: list[StockHistoryItem]
    known_limitations: list[str]


class DailyPerformanceResponse(OutputModel):
    tool: Literal["get_daily_performance"] = "get_daily_performance"
    correlation_id: str
    result_status: ResultStatus
    row_count: int
    items: list[DailyPerformanceItem]
    known_limitations: list[str]


class RegionLogisticsResponse(OutputModel):
    tool: Literal["get_region_logistics"] = "get_region_logistics"
    correlation_id: str
    result_status: ResultStatus
    row_count: int
    items: list[RegionLogisticsItem]
    known_limitations: list[str]


class PromotionStateResponse(OutputModel):
    tool: Literal["get_promotion_state"] = "get_promotion_state"
    correlation_id: str
    result_status: ResultStatus
    row_count: int
    items: list[PromotionStateItem]
    known_limitations: list[str]


class CpcDailyResponse(OutputModel):
    tool: Literal["get_cpc_daily"] = "get_cpc_daily"
    correlation_id: str
    result_status: ResultStatus
    row_count: int
    items: list[CpcDailyItem]
    known_limitations: list[str]


class AnalyticsResponse(OutputModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
