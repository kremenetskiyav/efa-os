"""Official MCP SDK server exposing exactly nine curated read tools."""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from .config import Settings
from .database import EfaReadRepository
from .models import (
    DEFAULT_ANALYTICS_ROW_LIMIT,
    DEFAULT_ROW_LIMIT,
    AnalyticsInput,
    AnalyticsLimit,
    AnalyticsQuery,
    AnalyticsResponse,
    CpcDailyInput,
    CpcDailyResponse,
    Confidence,
    DataScope,
    DailyPerformanceResponse,
    HistoryInput,
    HistoryLimit,
    ListProductsInput,
    ListProductsResponse,
    OfferId,
    PriceHistoryResponse,
    ProductInput,
    ProductOverviewResponse,
    PromotionInput,
    PromotionStateResponse,
    RegionLimit,
    RegionLogisticsInput,
    RegionLogisticsResponse,
    StockHistoryResponse,
)
from .service import EfaReadService, LOGGER


@dataclass(frozen=True)
class AppContext:
    service: EfaReadService


@asynccontextmanager
async def app_lifespan(_server: MCPServer) -> AsyncIterator[AppContext]:
    _configure_logging()
    settings = Settings.from_environment()
    repository = EfaReadRepository(settings)
    await repository.connect()
    try:
        yield AppContext(service=EfaReadService(repository))
    finally:
        await repository.close()


READ_TOOL_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)

mcp = MCPServer(
    "EFA Read MCP",
    lifespan=app_lifespan,
    log_level="WARNING",
)


@mcp.tool(annotations=READ_TOOL_ANNOTATIONS)
async def list_products(
    ctx: Context[AppContext], include_archived: bool = False
) -> ListProductsResponse:
    """List compact curated product identities and their freshness timestamps."""
    return await _service(ctx).list_products(ListProductsInput(include_archived=include_archived))


@mcp.tool(annotations=READ_TOOL_ANNOTATIONS)
async def get_product_overview(
    ctx: Context[AppContext], offer_id: OfferId
) -> ProductOverviewResponse:
    """Return at most one curated product overview for an exact offer_id."""
    return await _service(ctx).get_product_overview(ProductInput(offer_id=offer_id))


@mcp.tool(annotations=READ_TOOL_ANNOTATIONS)
async def get_price_history(
    ctx: Context[AppContext],
    offer_id: OfferId,
    date_from: date,
    date_to: date,
    limit: HistoryLimit = DEFAULT_ROW_LIMIT,
) -> PriceHistoryResponse:
    """Return price observations for one offer over at most 366 calendar days."""
    return await _service(ctx).get_price_history(
        HistoryInput(offer_id=offer_id, date_from=date_from, date_to=date_to, limit=limit)
    )


@mcp.tool(annotations=READ_TOOL_ANNOTATIONS)
async def get_stock_history(
    ctx: Context[AppContext],
    offer_id: OfferId,
    date_from: date,
    date_to: date,
    limit: HistoryLimit = DEFAULT_ROW_LIMIT,
) -> StockHistoryResponse:
    """Return stock snapshots without converting missing observations to zero."""
    return await _service(ctx).get_stock_history(
        HistoryInput(offer_id=offer_id, date_from=date_from, date_to=date_to, limit=limit)
    )


@mcp.tool(annotations=READ_TOOL_ANNOTATIONS)
async def get_daily_performance(
    ctx: Context[AppContext],
    offer_id: OfferId,
    date_from: date,
    date_to: date,
    limit: HistoryLimit = DEFAULT_ROW_LIMIT,
) -> DailyPerformanceResponse:
    """Return daily demand and delivered economics with their separate quality states."""
    return await _service(ctx).get_daily_performance(
        HistoryInput(offer_id=offer_id, date_from=date_from, date_to=date_to, limit=limit)
    )


@mcp.tool(annotations=READ_TOOL_ANNOTATIONS)
async def get_region_logistics(
    ctx: Context[AppContext],
    offer_id: OfferId,
    minimum_confidence: Confidence | None = None,
    limit: RegionLimit = DEFAULT_ROW_LIMIT,
) -> RegionLogisticsResponse:
    """Return curated regional logistics signals, optionally filtering confidence."""
    return await _service(ctx).get_region_logistics(
        RegionLogisticsInput(
            offer_id=offer_id,
            minimum_confidence=minimum_confidence,
            limit=limit,
        )
    )


@mcp.tool(annotations=READ_TOOL_ANNOTATIONS)
async def get_promotion_state(
    ctx: Context[AppContext], offer_id: OfferId, active_only: bool = False
) -> PromotionStateResponse:
    """Return latest valid promotion observations for an exact offer_id."""
    return await _service(ctx).get_promotion_state(
        PromotionInput(offer_id=offer_id, active_only=active_only)
    )


@mcp.tool(annotations=READ_TOOL_ANNOTATIONS)
async def get_cpc_daily(
    ctx: Context[AppContext],
    date_from: date,
    date_to: date,
    offer_id: OfferId | None = None,
    data_scope: DataScope | None = None,
    limit: HistoryLimit = DEFAULT_ROW_LIMIT,
) -> CpcDailyResponse:
    """Return CPC daily facts while retaining ACCOUNT and PRODUCT scopes separately."""
    return await _service(ctx).get_cpc_daily(
        CpcDailyInput(
            offer_id=offer_id,
            date_from=date_from,
            date_to=date_to,
            data_scope=data_scope,
            limit=limit,
        )
    )


@mcp.tool(annotations=READ_TOOL_ANNOTATIONS)
async def query_analytics(
    ctx: Context[AppContext],
    query: AnalyticsQuery,
    max_rows: AnalyticsLimit = DEFAULT_ANALYTICS_ROW_LIMIT,
) -> AnalyticsResponse:
    """Run one bounded, AST-validated SELECT over mcp_read relations only."""
    return await _service(ctx).query_analytics(
        AnalyticsInput(query=query, max_rows=max_rows)
    )


def _service(ctx: Context[AppContext]) -> EfaReadService:
    return ctx.request_context.lifespan_context.service


def _configure_logging() -> None:
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def _enforce_closed_tool_inputs() -> None:
    """Reject unknown arguments despite the pinned SDK's permissive generated model.

    MCP Python SDK 2.0.0 generates argument models with Pydantic's default
    ``extra='ignore'``. The package is pinned and this compatibility guard is
    covered by contract tests so an SDK upgrade fails closed if internals move.
    """
    for tool_name in (
        "list_products",
        "get_product_overview",
        "get_price_history",
        "get_stock_history",
        "get_daily_performance",
        "get_region_logistics",
        "get_promotion_state",
        "get_cpc_daily",
        "query_analytics",
    ):
        tool = mcp._tool_manager.get_tool(tool_name)
        if tool is None:
            raise RuntimeError("EFA Read MCP tool registration is incomplete")
        argument_model = tool.fn_metadata.arg_model
        argument_model.model_config = {**argument_model.model_config, "extra": "forbid"}
        argument_model.model_rebuild(force=True)
        tool.parameters = argument_model.model_json_schema()


_enforce_closed_tool_inputs()
