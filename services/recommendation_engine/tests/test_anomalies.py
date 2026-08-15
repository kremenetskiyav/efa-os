from datetime import datetime
from decimal import Decimal
import json
import unittest

from anomalies import build_profit_cost_anomaly
from config import AnomalyConfig, DatabaseConfig
from models import PeriodEconomics
from tools import get_profit_cost_anomalies

C = AnomalyConfig(5, Decimal("20"), Decimal("5"), Decimal("20"), Decimal("20"))
DB = DatabaseConfig("localhost", 5432, "efa", "efa", "not-used")


def period(*, profit="100", revenue="1000", commission="-200", logistics="-100", other="0", units=10, unallocated=0):
    return PeriodEconomics(datetime(2026, 8, 1), datetime(2026, 8, 7), units, units, Decimal(revenue), Decimal(profit), Decimal(commission), Decimal(logistics), Decimal(other), unallocated)


def result(current, baseline):
    return build_profit_cost_anomaly("УФ 001Б", {"current": current, "baseline": baseline}, C)


class ProfitCostAnomalyTests(unittest.TestCase):
    def test_profit_dropped(self): self.assertIn("PROFIT_DROPPED", result(period(profit="70"), period()).anomalies)
    def test_margin_dropped(self): self.assertIn("MARGIN_DROPPED", result(period(profit="100", revenue="2000"), period()).anomalies)
    def test_logistics_increased(self): self.assertIn("LOGISTICS_INCREASED", result(period(logistics="-130"), period()).anomalies)
    def test_commission_increased(self): self.assertIn("COMMISSION_INCREASED", result(period(commission="-250"), period()).anomalies)
    def test_other_expenses_appeared(self): self.assertIn("OTHER_EXPENSES_APPEARED", result(period(other="-30"), period()).anomalies)
    def test_no_anomaly(self): self.assertEqual(result(period(), period()).anomalies, ())
    def test_incomplete_period_is_quality_issue(self):
        r = result(period(units=4), period())
        self.assertEqual(r.anomalies, ("DATA_QUALITY_ISSUE",))
        self.assertEqual(r.data_quality_status, "review")
    def test_no_duplicate_signals(self):
        r = result(period(profit="70", revenue="2000", logistics="-130", commission="-250"), period())
        self.assertEqual(len(r.anomalies), len(set(r.anomalies)))

    def test_tool_filters_and_json_safety(self):
        data = {"УФ 001Б": {"current": period(profit="70"), "baseline": period()}, "УФ 002Б": {"current": period(), "baseline": period()}}
        output = get_profit_cost_anomalies({"offer_id": None, "severity": None, "anomaly_type": "PROFIT_DROPPED"}, DB, C, lambda _: data)
        json.dumps(output, ensure_ascii=False)
        self.assertEqual((output["read_only"], output["count"], output["anomalies"][0]["offer_id"]), (True, 1, "УФ 001Б"))
