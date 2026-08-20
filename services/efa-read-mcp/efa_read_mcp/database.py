"""Bounded asyncpg access to fixed and AST-validated mcp_read queries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import asyncpg

from . import queries
from .config import Settings
from .models import Confidence, DataScope


ANALYTICS_STATEMENT_TIMEOUT_MS = 10_000
ANALYTICS_LOCK_TIMEOUT_MS = 3_000


@dataclass(frozen=True)
class AnalyticsQueryResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool


class SafeDatabaseError(RuntimeError):
    """Database failure whose public message contains no server details."""


class EfaReadRepository:
    """Expose eight fixed operations and one validated analytics operation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is not None:
            return
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._settings.asyncpg_dsn(),
                min_size=self._settings.pool_min_size,
                max_size=self._settings.pool_max_size,
                command_timeout=(
                    max(self._settings.statement_timeout_ms, ANALYTICS_STATEMENT_TIMEOUT_MS)
                    / 1000
                )
                + 1,
                max_inactive_connection_lifetime=60,
                server_settings={
                    "application_name": "efa_read_mcp",
                    "default_transaction_read_only": "on",
                    "statement_timeout": f"{self._settings.statement_timeout_ms}ms",
                    "lock_timeout": f"{self._settings.lock_timeout_ms}ms",
                    "search_path": "mcp_read,pg_catalog",
                },
            )
        except Exception:
            raise SafeDatabaseError("Unable to initialize the curated read connection") from None

    async def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            await pool.close()

    async def list_products(self, include_archived: bool) -> Sequence[Mapping[str, Any]]:
        return await self._fetch(queries.LIST_PRODUCTS, include_archived)

    async def get_product_overview(self, offer_id: str) -> Sequence[Mapping[str, Any]]:
        return await self._fetch(queries.GET_PRODUCT_OVERVIEW, offer_id)

    async def get_price_history(
        self, offer_id: str, date_from: date, date_to: date, limit: int
    ) -> Sequence[Mapping[str, Any]]:
        return await self._fetch(queries.GET_PRICE_HISTORY, offer_id, date_from, date_to, limit)

    async def get_stock_history(
        self, offer_id: str, date_from: date, date_to: date, limit: int
    ) -> Sequence[Mapping[str, Any]]:
        return await self._fetch(queries.GET_STOCK_HISTORY, offer_id, date_from, date_to, limit)

    async def get_daily_performance(
        self, offer_id: str, date_from: date, date_to: date, limit: int
    ) -> Sequence[Mapping[str, Any]]:
        return await self._fetch(queries.GET_DAILY_PERFORMANCE, offer_id, date_from, date_to, limit)

    async def get_region_logistics(
        self, offer_id: str, minimum_confidence: Confidence | None, limit: int
    ) -> Sequence[Mapping[str, Any]]:
        return await self._fetch(queries.GET_REGION_LOGISTICS, offer_id, minimum_confidence, limit)

    async def get_promotion_state(
        self, offer_id: str, active_only: bool
    ) -> Sequence[Mapping[str, Any]]:
        return await self._fetch(queries.GET_PROMOTION_STATE, offer_id, active_only)

    async def get_cpc_daily(
        self,
        offer_id: str | None,
        date_from: date,
        date_to: date,
        data_scope: DataScope | None,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]:
        return await self._fetch(
            queries.GET_CPC_DAILY,
            offer_id,
            date_from,
            date_to,
            data_scope,
            limit,
        )

    async def query_analytics(self, query: str, max_rows: int) -> AnalyticsQueryResult:
        pool = self._pool
        if pool is None:
            raise SafeDatabaseError("Curated read connection is not initialized")

        bounded_query = (
            "SELECT * FROM (" + query + ") AS efa_analytics_result LIMIT $1"
        )
        try:
            async with pool.acquire() as connection:
                async with connection.transaction(readonly=True):
                    await connection.fetchval(
                        "SELECT pg_catalog.set_config('statement_timeout', $1, true)",
                        f"{ANALYTICS_STATEMENT_TIMEOUT_MS}ms",
                    )
                    await connection.fetchval(
                        "SELECT pg_catalog.set_config('lock_timeout', $1, true)",
                        f"{ANALYTICS_LOCK_TIMEOUT_MS}ms",
                    )
                    statement = await connection.prepare(bounded_query)
                    columns = [attribute.name for attribute in statement.get_attributes()]
                    records = await statement.fetch(max_rows + 1)
                    truncated = len(records) > max_rows
                    rows = [list(record.values()) for record in records[:max_rows]]
                    return AnalyticsQueryResult(
                        columns=columns,
                        rows=rows,
                        truncated=truncated,
                    )
        except Exception:
            raise SafeDatabaseError("Analytics read query failed") from None

    async def _fetch(self, query: str, *parameters: object) -> Sequence[Mapping[str, Any]]:
        pool = self._pool
        if pool is None:
            raise SafeDatabaseError("Curated read connection is not initialized")

        try:
            async with pool.acquire() as connection:
                async with connection.transaction(readonly=True):
                    await connection.fetchval(
                        "SELECT pg_catalog.set_config('statement_timeout', $1, true)",
                        f"{self._settings.statement_timeout_ms}ms",
                    )
                    await connection.fetchval(
                        "SELECT pg_catalog.set_config('lock_timeout', $1, true)",
                        f"{self._settings.lock_timeout_ms}ms",
                    )
                    records = await connection.fetch(query, *parameters)
                    return [dict(record) for record in records]
        except Exception:
            raise SafeDatabaseError("Curated read query failed") from None
