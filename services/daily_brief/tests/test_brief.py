from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import unittest

from services.daily_brief.brief import ATTENTION_CLASSES, build_brief, last_completed_business_date

UTC = timezone.utc
DAY = date(2026, 8, 17)


def sources(*, current_economics=False, cpc_state="SUCCESS_NONZERO", trend_days=6):
    cpc = {
        "SUCCESS_ZERO": ("success", 0, 5, "valid", datetime(2026,8,18,tzinfo=UTC), "COMPLETED", "OK", None, None, None, datetime(2026,8,18,tzinfo=UTC), "cpc:zero"),
        "SUCCESS_NONZERO": ("success", 1, 5, "valid", datetime(2026,8,18,tzinfo=UTC), "COMPLETED", "OK", None, None, None, datetime(2026,8,18,tzinfo=UTC), "cpc:one"),
        "PENDING": ("pending", 0, 5, "valid", datetime(2026,8,18,tzinfo=UTC), "PENDING", "IN_PROGRESS", None, None, None, None, "cpc:pending"),
        "STUCK": ("stuck", 0, 5, "invalid", datetime(2026,8,18,tzinfo=UTC), "STUCK", "NOT_STARTED", "REPORT_STUCK", "pending beyond two hours", "owner review", None, "cpc:stuck"),
        "FAILED": ("failed", 0, 5, "invalid", datetime(2026,8,18,tzinfo=UTC), "FAILED", "ERROR", "API_ERROR", "failed", None, None, "cpc:failed"),
        "MISSING": None,
    }[cpc_state]
    cpc_rows = [] if cpc_state != "SUCCESS_NONZERO" else [("A", 5, "CAMPAIGN_STATE_RUNNING", "SKU", Decimal("10"), 20, 2, 1, Decimal("90"), "valid")]
    trend = [("A", DAY-timedelta(days=index), Decimal("100"), 1) for index in range(trend_days)]
    return {
        "products": [("A", 1, 10, Decimal("100"), Decimal("40"), datetime(2026,8,1))],
        "demand": [("A", 1, Decimal("250"), 2, datetime(2026,8,18,tzinfo=UTC), "valid", "seller:17")],
        "deliveries": [], "returns": [],
        "finance": [("A", Decimal("200"), Decimal("50"), 2, 0)] if current_economics else [],
        "promotions": [("A", 1, "Action", None, "PARTICIPATING", Decimal("90"), Decimal("15"), Decimal("15"), Decimal("75"), "valid", datetime(2026,8,18,tzinfo=UTC))],
        "cpc": cpc_rows, "cpc_collection": cpc,
        "state_freshness": (datetime(2026,8,18,tzinfo=UTC), datetime(2026,8,18,tzinfo=UTC)),
        "operational_runs": [
            (name, DAY, "SUCCESS", count, 1, datetime(2026,8,18,tzinfo=UTC), f"{name}:17", None)
            for name, count in (("POSTINGS",256),("RETURNS",16),("FINANCE",39))
        ],
        "information_events": [("event-1", "manual", "Seller Main", "MANUAL_EVIDENCE", "INFO_ONLY", "ACTION_REQUIRED", True, "MEDIUM", "PENDING", {"effective_date":"2026-08-14"}, ["FBS"], ["daily_brief"], datetime(2026,8,16,tzinfo=UTC))],
        "information_freshness": ("gmail", "SUCCESS_ZERO", datetime(2026,8,18,tzinfo=UTC), None),
        "tax_state": {"engine_state":"ACTIVE","tax_year":2026,"taxable_revenue_ytd":Decimal("156074.83"),"usn_gross_ytd":Decimal("9364.49"),"usn_payable_estimate_ytd":Decimal("0"),"additional_contribution_ytd":Decimal("0"),"fixed_contribution_annual":Decimal("57390"),"fixed_contribution_paid_ytd":Decimal("0"),"overall_tax_quality":"PARTIAL","tax_date_confidence":"PARTIAL","latest_source_period":"2026-07","expected_through_period":"2026-07","income_periods_missing":[],"vat_status":"EXEMPT_UNDER_THRESHOLD"},
        "experiments": [("EXP-1","A","OZON_ACTION_FBS","ACTIVE",None,None,{"action_id":"4118344","seller_price_rub":899,"action_ui_price_rub":865,"elastic_boost_pct":15,"cpc_enabled":False},5,5,Decimal("500"),"unknown start",datetime(2026,8,18,tzinfo=UTC),datetime(2026,8,18,tzinfo=UTC))],
        "current_price_status": [("A","NOT_YET_CONFIRMED")],
        "latest_economics": [("A",date(2026,8,14),Decimal("624"),Decimal("92.11"),1,0,0,0)],
        "latest_economics_summary": (date(2026,8,14),Decimal("624"),Decimal("92.11"),1,0),
        "trends": {"demand":trend,"price":[],"boost":[],"finance":[]},
    }


class DailyBriefV11Tests(unittest.TestCase):
    def test_default_business_date_uses_moscow(self):
        self.assertEqual(last_completed_business_date(datetime(2026,8,17,21,30,tzinfo=UTC)), DAY)

    def test_current_economics_unavailable_and_historical_separate(self):
        payload = build_brief(sources(cpc_state="STUCK"), DAY)
        self.assertEqual(payload["current_day_economics"]["confirmation_state"], "UNAVAILABLE")
        self.assertIsNone(payload["current_day_economics"]["contribution_profit"])
        self.assertEqual(payload["latest_confirmed_economics"]["confirmed_through_date"], "2026-08-14")
        self.assertEqual(payload["latest_confirmed_economics"]["contribution_profit"], "92.11")
        self.assertIsNone(payload["offers"][0]["current_day"]["economics"]["revenue"])

    def test_current_economics_populates_only_from_current_rows(self):
        payload = build_brief(sources(current_economics=True), DAY)
        self.assertEqual(payload["current_day_economics"]["confirmation_state"], "CONFIRMED")
        self.assertEqual(payload["current_day_economics"]["confirmed_through_date"], "2026-08-17")
        self.assertEqual(payload["current_day_economics"]["contribution_profit"], "50")

    def test_null_and_zero_are_distinct(self):
        unavailable = build_brief(sources(cpc_state="STUCK"), DAY)
        zero = build_brief(sources(cpc_state="SUCCESS_ZERO"), DAY)
        self.assertIsNone(unavailable["summary"]["cpc_spend"])
        self.assertEqual(zero["summary"]["cpc_spend"], "0")
        self.assertEqual(zero["summary"]["cpc_orders"], 0)

    def test_all_cpc_lifecycle_states(self):
        for state in ("SUCCESS_ZERO","SUCCESS_NONZERO","PENDING","STUCK","FAILED","MISSING"):
            with self.subTest(state=state):
                self.assertEqual(build_brief(sources(cpc_state=state), DAY)["advertising"]["cpc"]["state"], state)

    def test_run_level_freshness(self):
        payload = build_brief(sources(), DAY)
        self.assertEqual(payload["source_freshness"]["postings"]["state"], "fresh")
        self.assertEqual(payload["source_freshness"]["returns"]["collection_ref"], "RETURNS:17")
        self.assertEqual(payload["source_freshness"]["information_intelligence"]["state"], "success_zero")

    def test_information_action_required_is_not_hidden(self):
        payload = build_brief(sources(), DAY)
        self.assertEqual(payload["information_intelligence"]["counts"]["ACTION_REQUIRED"], 1)
        self.assertTrue(any(item["class"] == "ACTION_REQUIRED" for item in payload["attention_items"]))

    def test_tax_engine_active_and_fixed_obligation_not_allocated(self):
        payload = build_brief(sources(), DAY)
        self.assertEqual(payload["tax_status"], "ACTIVE")
        self.assertEqual(payload["tax"]["gross_usn"], "9364.49")
        self.assertEqual(payload["tax"]["fixed_obligation_allocation"], "BUSINESS_LEVEL_ONLY_NOT_ALLOCATED_TO_OFFERS")
        self.assertNotIn("tax", payload["offers"][0]["economics"])

    def test_trend_requires_seven_distinct_valid_days(self):
        self.assertEqual(build_brief(sources(trend_days=6), DAY)["extended_report_payload"]["trends"]["demand"]["status"], "INSUFFICIENT_DATA")
        self.assertEqual(build_brief(sources(trend_days=7), DAY)["extended_report_payload"]["trends"]["demand"]["status"], "READY")

    def test_experiment_unknown_start_has_no_fake_attribution(self):
        experiment = build_brief(sources(), DAY)["experiments"][0]
        self.assertIsNone(experiment["started_at"])
        self.assertEqual(experiment["attribution_state"], "UNAVAILABLE_START_TIMESTAMP")
        self.assertIsNone(experiment["performance_attribution"])
        self.assertEqual(experiment["deterministic_alerts"], [])

    def test_attention_taxonomy_and_json_safety(self):
        payload = build_brief(sources(cpc_state="STUCK"), DAY, datetime(2026,8,18,tzinfo=UTC))
        self.assertEqual(tuple(payload["attention_taxonomy"]), ATTENTION_CLASSES)
        json.dumps(payload, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
