from __future__ import annotations

import unittest

from efa_read_mcp.sql_validation import (
    AnalyticsQueryRejected,
    validate_analytics_query,
)


class AnalyticsSqlValidationTests(unittest.TestCase):
    def test_allowed_analytics_queries(self) -> None:
        queries = (
            "SELECT offer_id FROM mcp_read.product_overview",
            "SELECT p.offer_id, s.total_present "
            "FROM mcp_read.product_overview AS p "
            "JOIN mcp_read.product_stock_history AS s USING (offer_id)",
            "SELECT offer_id, count(*) FROM mcp_read.product_daily_performance "
            "GROUP BY offer_id",
            "WITH recent AS (SELECT offer_id FROM mcp_read.product_overview) "
            "SELECT offer_id FROM recent",
            "SELECT count(*), sum(ordered_units), avg(ordered_revenue) "
            "FROM mcp_read.product_daily_performance",
            "SELECT offer_id FROM mcp_read.product_price_history "
            "WHERE observed_at >= DATE '2026-08-01'",
            "SELECT offer_id FROM mcp_read.product_overview ORDER BY offer_id LIMIT 5",
            "SELECT 'DELETE FROM public.products' AS label "
            "FROM mcp_read.product_overview LIMIT 1",
        )
        for query in queries:
            with self.subTest(query=query):
                validated = validate_analytics_query(query)
                self.assertTrue(validated.sql.startswith(("SELECT", "WITH")))
                self.assertNotIn(";", validated.sql)

    def test_forbidden_analytics_queries(self) -> None:
        queries = (
            "SELECT * FROM public.products",
            "SELECT * FROM information_schema.tables",
            "UPDATE mcp_read.product_overview SET brand = 'x'",
            "DELETE FROM mcp_read.product_overview",
            "INSERT INTO mcp_read.product_overview (offer_id) VALUES ('x')",
            "MERGE INTO mcp_read.product_overview AS p "
            "USING mcp_read.product_stock_history AS s ON p.offer_id = s.offer_id "
            "WHEN MATCHED THEN DELETE",
            "TRUNCATE mcp_read.product_overview",
            "CREATE TABLE mcp_read.x (id integer)",
            "ALTER TABLE mcp_read.product_overview ADD COLUMN x integer",
            "DROP VIEW mcp_read.product_overview",
            "COPY mcp_read.product_overview TO STDOUT",
            "CALL mcp_read.refresh()",
            "DO $$ BEGIN NULL; END $$",
            "SELECT offer_id INTO TEMP TABLE x FROM mcp_read.product_overview",
            "SELECT * FROM mcp_read.product_overview FOR UPDATE",
            "SELECT * FROM mcp_read.product_overview FOR SHARE",
            "WITH changed AS (DELETE FROM mcp_read.product_overview RETURNING *) "
            "SELECT * FROM changed",
            "SELECT * FROM mcp_read.product_overview; "
            "SELECT * FROM mcp_read.product_stock_history",
            "SELECT * FROM product_overview",
            "SELECT * FROM product_overview WHERE EXISTS ("
            "WITH product_overview AS (SELECT * FROM mcp_read.product_overview) "
            "SELECT 1 FROM product_overview)",
            "SELECT * FROM other.product_overview",
            "SET statement_timeout = '1h'",
            "RESET ALL",
            "BEGIN",
            "COMMIT",
            "SELECT * FROM mcp_read.product_overview WHERE offer_id = $1",
            "SELECT * FROM pg_catalog.generate_series(1, 10)",
            "SELECT public.some_function(offer_id) FROM mcp_read.product_overview",
            "SELECT 1",
        )
        for query in queries:
            with self.subTest(query=query), self.assertRaises(AnalyticsQueryRejected):
                validate_analytics_query(query)

    def test_semicolon_terminated_single_select_is_normalized(self) -> None:
        validated = validate_analytics_query(
            "SELECT offer_id FROM mcp_read.product_overview;"
        )
        self.assertNotIn(";", validated.sql)


if __name__ == "__main__":
    unittest.main()
