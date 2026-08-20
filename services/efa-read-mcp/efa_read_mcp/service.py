"""Tool-facing business boundary, row mapping, and metadata-only audit logging."""

from __future__ import annotations

import logging
import time
from base64 import b64encode
from collections.abc import Awaitable, Mapping, Sequence
from datetime import date, datetime, time as datetime_time
from decimal import Decimal
from typing import Any, TypeVar
from uuid import UUID, uuid4

from .database import EfaReadRepository
from .models import (
    AnalyticsInput,
    AnalyticsResponse,
    CpcDailyInput,
    CpcDailyItem,
    CpcDailyResponse,
    DailyPerformanceItem,
    DailyPerformanceResponse,
    HistoryInput,
    ListProductsInput,
    ListProductsResponse,
    OutputModel,
    PriceHistoryItem,
    PriceHistoryResponse,
    ProductInput,
    ProductListItem,
    ProductOverviewItem,
    ProductOverviewResponse,
    PromotionInput,
    PromotionStateItem,
    PromotionStateResponse,
    RegionLogisticsInput,
    RegionLogisticsItem,
    RegionLogisticsResponse,
    StockHistoryItem,
    StockHistoryResponse,
)
from .sql_validation import AnalyticsQueryRejected, validate_analytics_query


LOGGER = logging.getLogger("efa_read_mcp.audit")
ItemT = TypeVar("ItemT", bound=OutputModel)


class SafeServiceError(RuntimeError):
    """A client-safe failure without database or credential details."""


class EfaReadService:
    def __init__(self, repository: EfaReadRepository) -> None:
        self._repository = repository

    async def list_products(self, request: ListProductsInput) -> ListProductsResponse:
        correlation_id, items = await self._run(
            "list_products",
            self._repository.list_products(request.include_archived),
            ProductListItem,
        )
        return ListProductsResponse(
            correlation_id=correlation_id,
            result_status=_status(items),
            row_count=len(items),
            items=items,
            known_limitations=[
                "This is a compact discovery view; use get_product_overview for price and stock values.",
                "A missing freshness timestamp remains null and does not imply current data.",
            ],
        )

    async def get_product_overview(self, request: ProductInput) -> ProductOverviewResponse:
        correlation_id, items = await self._run(
            "get_product_overview",
            self._repository.get_product_overview(request.offer_id),
            ProductOverviewItem,
        )
        item = items[0] if items else None
        return ProductOverviewResponse(
            correlation_id=correlation_id,
            result_status="ok" if item is not None else "empty",
            row_count=1 if item is not None else 0,
            item=item,
            known_limitations=[
                "cost_price is the current product cost basis and must not be treated as historical cost.",
                "Null stock fields mean no confirmed snapshot; they must not be converted to zero.",
                "Current-price economics include explicit quality and unmatched-unit indicators.",
            ],
        )

    async def get_price_history(self, request: HistoryInput) -> PriceHistoryResponse:
        correlation_id, items = await self._run(
            "get_price_history",
            self._repository.get_price_history(
                request.offer_id, request.date_from, request.date_to, request.limit
            ),
            PriceHistoryItem,
        )
        return PriceHistoryResponse(
            correlation_id=correlation_id,
            result_status=_status(items),
            row_count=len(items),
            items=items,
            known_limitations=[
                "Rows are observations, ordered newest first; absence of a row is not a zero price.",
            ],
        )

    async def get_stock_history(self, request: HistoryInput) -> StockHistoryResponse:
        correlation_id, items = await self._run(
            "get_stock_history",
            self._repository.get_stock_history(
                request.offer_id, request.date_from, request.date_to, request.limit
            ),
            StockHistoryItem,
        )
        return StockHistoryResponse(
            correlation_id=correlation_id,
            result_status=_status(items),
            row_count=len(items),
            items=items,
            known_limitations=[
                "Null quantities and a missing snapshot remain unknown and must not be converted to zero.",
                "Rows are observations ordered newest first; is_latest is evaluated per offer_id.",
            ],
        )

    async def get_daily_performance(self, request: HistoryInput) -> DailyPerformanceResponse:
        correlation_id, items = await self._run(
            "get_daily_performance",
            self._repository.get_daily_performance(
                request.offer_id, request.date_from, request.date_to, request.limit
            ),
            DailyPerformanceItem,
        )
        return DailyPerformanceResponse(
            correlation_id=correlation_id,
            result_status=_status(items),
            row_count=len(items),
            items=items,
            known_limitations=[
                "ordered_* is demand while delivered and financial fields are delivery-date economics; do not combine their units.",
                "cost_of_goods uses the current product cost basis and is not historical cost.",
                "Quality and collection statuses must be evaluated before using financial metrics.",
            ],
        )

    async def get_region_logistics(
        self, request: RegionLogisticsInput
    ) -> RegionLogisticsResponse:
        correlation_id, items = await self._run(
            "get_region_logistics",
            self._repository.get_region_logistics(
                request.offer_id, request.minimum_confidence, request.limit
            ),
            RegionLogisticsItem,
        )
        return RegionLogisticsResponse(
            correlation_id=correlation_id,
            result_status=_status(items),
            row_count=len(items),
            items=items,
            known_limitations=[
                "Confidence, data_from, data_through, and rule_version define the evidence window.",
                "Low-confidence rows are not conclusions and remain visible unless explicitly filtered.",
            ],
        )

    async def get_promotion_state(self, request: PromotionInput) -> PromotionStateResponse:
        correlation_id, items = await self._run(
            "get_promotion_state",
            self._repository.get_promotion_state(request.offer_id, request.active_only),
            PromotionStateItem,
        )
        return PromotionStateResponse(
            correlation_id=correlation_id,
            result_status=_status(items),
            row_count=len(items),
            items=items,
            known_limitations=[
                "The view contains only the latest successful valid promotion collection.",
                "active_only uses the database clock and promotion start/end timestamps; participation_state remains authoritative.",
            ],
        )

    async def get_cpc_daily(self, request: CpcDailyInput) -> CpcDailyResponse:
        correlation_id, items = await self._run(
            "get_cpc_daily",
            self._repository.get_cpc_daily(
                request.offer_id,
                request.date_from,
                request.date_to,
                request.data_scope,
                request.limit,
            ),
            CpcDailyItem,
        )
        return CpcDailyResponse(
            correlation_id=correlation_id,
            result_status=_status(items),
            row_count=len(items),
            items=items,
            known_limitations=[
                "ACCOUNT rows have offer_id=null and are never synthesized into product-level facts.",
                "SUCCESS_ZERO is an explicit successful zero observation; no row is an empty result, not SUCCESS_ZERO.",
                "CTR and DRR are ratios of aggregated totals from the curated view, not averages of percentages.",
            ],
        )

    async def query_analytics(self, request: AnalyticsInput) -> AnalyticsResponse:
        correlation_id = str(uuid4())
        started = time.perf_counter()
        try:
            validated = validate_analytics_query(request.query)
            result = await self._repository.query_analytics(validated.sql, request.max_rows)
            rows = [[_json_safe(cell) for cell in row] for row in result.rows]
            response = AnalyticsResponse(
                columns=result.columns,
                rows=rows,
                row_count=len(rows),
                truncated=result.truncated,
            )
        except AnalyticsQueryRejected:
            _log_call("query_analytics", started, 0, False, correlation_id)
            raise SafeServiceError("The analytics query was rejected") from None
        except Exception:
            _log_call("query_analytics", started, 0, False, correlation_id)
            raise SafeServiceError("The analytics read operation failed") from None
        _log_call("query_analytics", started, response.row_count, True, correlation_id)
        return response

    async def _run(
        self,
        tool_name: str,
        operation: Awaitable[Sequence[Mapping[str, Any]]],
        model: type[ItemT],
    ) -> tuple[str, list[ItemT]]:
        correlation_id = str(uuid4())
        started = time.perf_counter()
        try:
            rows = await operation
            items = [model.model_validate(row) for row in rows]
        except Exception:
            _log_call(tool_name, started, 0, False, correlation_id)
            raise SafeServiceError("The curated read operation failed") from None
        _log_call(tool_name, started, len(items), True, correlation_id)
        return correlation_id, items


def _status(items: Sequence[object]) -> str:
    return "ok" if items else "empty"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime, datetime_time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return b64encode(value).decode("ascii")
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    return str(value)


def _log_call(
    tool_name: str,
    started: float,
    row_count: int,
    success: bool,
    correlation_id: str,
) -> None:
    duration_ms = round((time.perf_counter() - started) * 1000)
    LOGGER.info(
        "tool=%s duration_ms=%d row_count=%d success=%s correlation_id=%s",
        tool_name,
        duration_ms,
        row_count,
        success,
        correlation_id,
    )
