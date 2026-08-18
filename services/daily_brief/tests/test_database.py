import unittest

from services.daily_brief import database


class DailyBriefQueryTests(unittest.TestCase):
    def test_uses_established_confirmed_profit_view_and_delivery_date(self):
        self.assertIn("vw_orders_profit_final", database.CONFIRMED_FINANCE_QUERY)
        self.assertIn("delivering_date", database.CONFIRMED_FINANCE_QUERY)
        self.assertNotIn("operation_date", database.CONFIRMED_FINANCE_QUERY)

    def test_queries_are_read_only(self):
        source = "\n".join(value for name, value in vars(database).items() if name.endswith("_QUERY"))
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP "):
            self.assertNotIn(forbidden, source.upper())

    def test_promotions_use_latest_successful_run(self):
        self.assertIn("WHERE status = 'success'", database.PROMOTIONS_QUERY)
        self.assertIn("LIMIT 1", database.PROMOTIONS_QUERY)

    def test_cpc_uses_durable_lifecycle_not_detail_rows(self):
        self.assertIn("lifecycle_state", database.CPC_COLLECTION_QUERY)
        self.assertIn("report_state", database.CPC_COLLECTION_QUERY)
        self.assertIn("records_count", database.CPC_COLLECTION_QUERY)

    def test_operational_freshness_uses_run_metadata(self):
        self.assertIn("operational_collection_runs", database.OPERATIONAL_RUNS_QUERY)
        self.assertIn("POSTINGS", database.OPERATIONAL_RUNS_QUERY)
        self.assertIn("RETURNS", database.OPERATIONAL_RUNS_QUERY)
        self.assertIn("FINANCE", database.OPERATIONAL_RUNS_QUERY)

    def test_price_freshness_uses_successful_runs_not_change_history(self):
        self.assertIn("price_collection_runs", database.STATE_FRESHNESS_QUERY)
        self.assertIn("status = 'success'", database.STATE_FRESHNESS_QUERY)

    def test_current_price_status_uses_confirmed_delivery_not_finance_operation_date(self):
        self.assertIn("vw_orders_profit_final", database.CURRENT_PRICE_STATUS_QUERY)
        self.assertIn("delivering_date >= cp.price_since", database.CURRENT_PRICE_STATUS_QUERY)
        self.assertNotIn("operation_date", database.CURRENT_PRICE_STATUS_QUERY)

    def test_tax_information_and_experiment_queries_reuse_existing_tables(self):
        self.assertIn("tax_revenue_events", database.TAX_EVENTS_QUERY)
        self.assertIn("information_change_events", database.INFORMATION_EVENTS_QUERY)
        self.assertIn("commercial_experiments", database.EXPERIMENTS_QUERY)
