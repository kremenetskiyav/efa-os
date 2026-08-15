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

    def test_current_price_status_uses_confirmed_delivery_not_finance_operation_date(self):
        self.assertIn("vw_orders_profit_final", database.CURRENT_PRICE_STATUS_QUERY)
        self.assertIn("delivering_date >= cp.price_since", database.CURRENT_PRICE_STATUS_QUERY)
        self.assertNotIn("operation_date", database.CURRENT_PRICE_STATUS_QUERY)
