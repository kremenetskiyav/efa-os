from __future__ import annotations

import unittest

from pydantic import ValidationError

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

FORBIDDEN_TOOLS = {
    "execute_sql",
    "query_database",
    "connect_to_database",
    "list_arbitrary_tables",
    "describe_arbitrary_table",
    "write_database",
}

FORBIDDEN_OUTPUT_FIELDS = {
    "order_number",
    "order_id",
    "posting_number",
    "posting_key",
    "campaign_id",
    "run_id",
    "report_uuid",
    "collection_ref",
    "poll_lease_token",
    "error_message",
}


class ServerContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_tool_registration_and_read_only_annotations(self) -> None:
        tools = await mcp.list_tools()
        names = {tool.name for tool in tools}
        self.assertEqual(EXPECTED_TOOLS, names)
        self.assertTrue(names.isdisjoint(FORBIDDEN_TOOLS))
        self.assertFalse(any("write" in name for name in names))
        for tool in tools:
            with self.subTest(tool=tool.name):
                self.assertTrue(tool.annotations.read_only_hint)
                self.assertFalse(tool.annotations.destructive_hint)
                self.assertTrue(tool.annotations.idempotent_hint)
                self.assertFalse(tool.annotations.open_world_hint)
                self.assertFalse(tool.input_schema.get("additionalProperties", True))
                self.assertNotIn("sql", tool.input_schema.get("properties", {}))
                self.assertNotIn("database_url", tool.input_schema.get("properties", {}))

    async def test_output_contract_contains_no_forbidden_fields(self) -> None:
        for tool in await mcp.list_tools():
            field_names = _schema_property_names(tool.output_schema or {})
            with self.subTest(tool=tool.name):
                self.assertTrue(field_names.isdisjoint(FORBIDDEN_OUTPUT_FIELDS))

    async def test_history_schema_contains_limits_and_no_context_argument(self) -> None:
        tools = {tool.name: tool for tool in await mcp.list_tools()}
        schema = tools["get_price_history"].input_schema
        self.assertNotIn("ctx", schema["properties"])
        self.assertEqual(500, schema["properties"]["limit"]["maximum"])

        analytics_schema = tools["query_analytics"].input_schema
        self.assertEqual({"query", "max_rows"}, set(analytics_schema["properties"]))
        self.assertEqual(["query"], analytics_schema["required"])
        self.assertEqual(200, analytics_schema["properties"]["max_rows"]["default"])
        self.assertEqual(500, analytics_schema["properties"]["max_rows"]["maximum"])

    async def test_unknown_argument_is_rejected_before_tool_execution(self) -> None:
        tool = mcp._tool_manager.get_tool("list_products")
        with self.assertRaises(ValidationError):
            tool.fn_metadata.arg_model.model_validate(
                {"include_archived": False, "unknown_parameter": "value"}
            )

def _schema_property_names(schema: object) -> set[str]:
    if isinstance(schema, dict):
        names = set(schema.get("properties", {}))
        for value in schema.values():
            names.update(_schema_property_names(value))
        return names
    if isinstance(schema, list):
        names: set[str] = set()
        for value in schema:
            names.update(_schema_property_names(value))
        return names
    return set()


if __name__ == "__main__":
    unittest.main()
