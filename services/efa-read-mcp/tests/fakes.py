"""Small repository double used by unit tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from efa_read_mcp.database import AnalyticsQueryResult


class FakeRepository:
    def __init__(
        self,
        rows: dict[str, Sequence[Mapping[str, Any]]] | None = None,
        analytics_result: AnalyticsQueryResult | None = None,
    ) -> None:
        self.rows = rows or {}
        self.analytics_result = analytics_result or AnalyticsQueryResult([], [], False)
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def list_products(self, include_archived: bool):
        return self._result("list_products", include_archived)

    async def get_product_overview(self, offer_id: str):
        return self._result("get_product_overview", offer_id)

    async def get_price_history(self, offer_id: str, date_from: date, date_to: date, limit: int):
        return self._result("get_price_history", offer_id, date_from, date_to, limit)

    async def get_stock_history(self, offer_id: str, date_from: date, date_to: date, limit: int):
        return self._result("get_stock_history", offer_id, date_from, date_to, limit)

    async def get_daily_performance(
        self, offer_id: str, date_from: date, date_to: date, limit: int
    ):
        return self._result("get_daily_performance", offer_id, date_from, date_to, limit)

    async def get_region_logistics(self, offer_id: str, minimum_confidence, limit: int):
        return self._result("get_region_logistics", offer_id, minimum_confidence, limit)

    async def get_promotion_state(self, offer_id: str, active_only: bool):
        return self._result("get_promotion_state", offer_id, active_only)

    async def get_cpc_daily(
        self, offer_id: str | None, date_from: date, date_to: date, data_scope, limit: int
    ):
        return self._result("get_cpc_daily", offer_id, date_from, date_to, data_scope, limit)

    async def query_analytics(self, query: str, max_rows: int):
        self.calls.append(("query_analytics", (query, max_rows)))
        return self.analytics_result

    def _result(self, name: str, *parameters: object):
        self.calls.append((name, parameters))
        return self.rows.get(name, [])
