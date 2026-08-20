"""Production-read-only MCP smoke test. Run only with approved secret injection."""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

import asyncpg
from mcp import Client

from efa_read_mcp.config import EXPECTED_DATABASE, EXPECTED_ROLE, Settings
from efa_read_mcp.server import mcp


EXPECTED_TOOLS = {
    "list_products",
    "get_product_overview",
    "get_price_history",
    "get_stock_history",
    "get_daily_performance",
    "get_region_logistics",
    "get_promotion_state",
    "get_cpc_daily",
    "query_analytics",
}


async def main() -> None:
    settings = Settings.from_environment()
    today = date.today()
    date_from = today - timedelta(days=365)
    summary: dict[str, object] = {"tools": {}, "acl": {}}

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        if tool_names != EXPECTED_TOOLS:
            raise RuntimeError("Unexpected MCP tool registration")

        listed = await _call(client, "list_products", {"include_archived": False})
        items = listed.get("items", [])
        if not items:
            raise RuntimeError("No curated products are available for integration testing")
        offer_id = items[0]["offer_id"]
        summary["tools"]["list_products"] = _shape(listed)

        calls = {
            "get_product_overview": {"offer_id": offer_id},
            "get_price_history": {
                "offer_id": offer_id,
                "date_from": date_from.isoformat(),
                "date_to": today.isoformat(),
                "limit": 500,
            },
            "get_stock_history": {
                "offer_id": offer_id,
                "date_from": date_from.isoformat(),
                "date_to": today.isoformat(),
                "limit": 500,
            },
            "get_daily_performance": {
                "offer_id": offer_id,
                "date_from": date_from.isoformat(),
                "date_to": today.isoformat(),
                "limit": 500,
            },
            "get_region_logistics": {
                "offer_id": offer_id,
                "minimum_confidence": None,
                "limit": 200,
            },
            "get_promotion_state": {"offer_id": offer_id, "active_only": False},
            "get_cpc_daily": {
                "offer_id": offer_id,
                "date_from": date_from.isoformat(),
                "date_to": today.isoformat(),
                "data_scope": None,
                "limit": 500,
            },
        }
        for tool_name, arguments in calls.items():
            result = await _call(client, tool_name, arguments)
            summary["tools"][tool_name] = _shape(result)

        analytics = await _call_analytics(
            client,
            {
                "query": (
                    "SELECT offer_id FROM mcp_read.product_overview "
                    "ORDER BY offer_id LIMIT 1"
                ),
                "max_rows": 5,
            },
        )
        summary["tools"]["query_analytics"] = {
            "row_count": analytics["row_count"],
            "truncated": analytics["truncated"],
            "columns": analytics["columns"],
        }

    connection = await asyncpg.connect(
        dsn=settings.asyncpg_dsn(),
        server_settings={"default_transaction_read_only": "on"},
    )
    try:
        async with connection.transaction(readonly=True):
            identity = await connection.fetchrow(
                "SELECT current_user AS current_user, current_database() AS current_database, "
                "current_setting('transaction_read_only') AS transaction_read_only"
            )
            if identity["current_user"] != EXPECTED_ROLE:
                raise RuntimeError("Unexpected integration role")
            if identity["current_database"] != EXPECTED_DATABASE:
                raise RuntimeError("Unexpected integration database")
            if identity["transaction_read_only"] != "on":
                raise RuntimeError("Integration transaction is not read-only")

            raw_denied = False
            try:
                await connection.fetchval("SELECT 1 FROM public.products LIMIT 1")
            except asyncpg.InsufficientPrivilegeError:
                raw_denied = True
            if not raw_denied:
                raise RuntimeError("Raw public access was not denied")
            summary["acl"] = {
                "role": "expected_readonly_role",
                "database": "expected_database",
                "transaction_read_only": True,
                "raw_public_select_denied": True,
            }
    finally:
        await connection.close()

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


async def _call(client: Client, tool_name: str, arguments: dict[str, object]) -> dict:
    result = await client.call_tool(tool_name, arguments)
    if result.is_error or not isinstance(result.structured_content, dict):
        raise RuntimeError(f"MCP tool failed: {tool_name}")
    payload = result.structured_content
    if payload.get("tool") != tool_name:
        raise RuntimeError(f"Unexpected structured output: {tool_name}")
    if payload.get("row_count") is None or payload.get("result_status") not in {"ok", "empty"}:
        raise RuntimeError(f"Incomplete structured output: {tool_name}")
    return payload


async def _call_analytics(client: Client, arguments: dict[str, object]) -> dict:
    result = await client.call_tool("query_analytics", arguments)
    if result.is_error or not isinstance(result.structured_content, dict):
        raise RuntimeError("MCP tool failed: query_analytics")
    payload = result.structured_content
    if set(payload) != {"columns", "rows", "row_count", "truncated"}:
        raise RuntimeError("Unexpected query_analytics structured output")
    return payload


def _shape(payload: dict) -> dict[str, object]:
    return {
        "result_status": payload["result_status"],
        "row_count": payload["row_count"],
        "keys": sorted(payload),
    }


if __name__ == "__main__":
    asyncio.run(main())
