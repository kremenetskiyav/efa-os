from __future__ import annotations

import re
import unittest

from efa_read_mcp.queries import QUERY_BY_TOOL, SOURCE_BY_TOOL


EXPECTED_TOOLS = {
    "list_products",
    "get_product_overview",
    "get_price_history",
    "get_stock_history",
    "get_daily_performance",
    "get_region_logistics",
    "get_promotion_state",
    "get_cpc_daily",
}


class FixedQueryTests(unittest.TestCase):
    def test_exactly_eight_fixed_queries_exist(self) -> None:
        self.assertEqual(EXPECTED_TOOLS, set(QUERY_BY_TOOL))
        self.assertEqual(EXPECTED_TOOLS, set(SOURCE_BY_TOOL))

    def test_runtime_queries_are_single_curated_selects(self) -> None:
        forbidden_words = re.compile(
            r"\b(insert|update|delete|merge|alter|drop|create|grant|revoke|truncate|copy|call|execute)\b",
            re.IGNORECASE,
        )
        for tool, query in QUERY_BY_TOOL.items():
            normalized = query.strip()
            with self.subTest(tool=tool):
                self.assertTrue(normalized.upper().startswith("SELECT"))
                self.assertNotIn("public.", normalized.lower())
                self.assertNotRegex(normalized, forbidden_words)
                self.assertNotIn(";", normalized)
                self.assertIn(SOURCE_BY_TOOL[tool], normalized)
                self.assertEqual(1, len(re.findall(r"\bFROM\s+mcp_read\.", normalized, re.I)))
                self.assertNotIn("{", normalized)
                self.assertNotIn("%(", normalized)

    def test_cpc_query_retains_account_scope_without_synthetic_offer(self) -> None:
        query = QUERY_BY_TOOL["get_cpc_daily"]
        self.assertIn("data_scope = 'ACCOUNT' AND offer_id IS NULL", query)
        self.assertIn("data_scope = 'PRODUCT' AND offer_id = $1", query)

    def test_queries_have_deterministic_order_and_bound_limits(self) -> None:
        for tool in (
            "get_product_overview",
            "get_price_history",
            "get_stock_history",
            "get_daily_performance",
            "get_region_logistics",
            "get_cpc_daily",
        ):
            with self.subTest(tool=tool):
                self.assertIn("ORDER BY", QUERY_BY_TOOL[tool])
                self.assertIn("LIMIT", QUERY_BY_TOOL[tool])


if __name__ == "__main__":
    unittest.main()
