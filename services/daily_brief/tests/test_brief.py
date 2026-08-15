from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import unittest

from services.daily_brief.brief import build_brief, last_completed_business_date


UTC = timezone.utc


def sources(*, demand=True, finance=True, cpc_state="CAMPAIGN_STATE_RUNNING"):
    day = date(2026, 8, 14)
    return {
        "products": [("A", 1, 10, Decimal("100"), Decimal("40"), datetime(2026, 8, 14, tzinfo=UTC))],
        "demand": [("A", 1, Decimal("250"), 2, datetime(2026, 8, 15, tzinfo=UTC), "valid")] if demand else [],
        "deliveries": [("A", 2)], "returns": [("A", 1, 1)],
        "finance": [("A", Decimal("200"), Decimal("50"), 2, 0)] if finance else [],
        "promotions": [
            ("A", 1, "Action", None, "PARTICIPATING", Decimal("90"), Decimal("15"), Decimal("15"), Decimal("75"), "valid", datetime(2026, 8, 15, tzinfo=UTC)),
            ("A", 2, "Candidate", None, "CANDIDATE", Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), "valid", datetime(2026, 8, 15, tzinfo=UTC)),
        ],
        "cpc": [("A", 5, cpc_state, "SKU", Decimal("10"), 20, 2, 1, Decimal("90"), "valid")],
        "freshness": (day, datetime.now(UTC), day, datetime(2026, 8, 14, tzinfo=UTC), datetime(2026, 8, 14, tzinfo=UTC)),
        "current_price_status": [("A", "CONFIRMED")],
    }


class DailyBriefTests(unittest.TestCase):
    def test_default_business_date_uses_moscow_not_utc(self):
        instant = datetime(2026, 8, 15, 21, 30, tzinfo=UTC)  # Aug 16 in Moscow
        self.assertEqual(last_completed_business_date(instant), date(2026, 8, 15))

    def test_products_are_taken_from_source_not_hardcoded(self):
        payload = build_brief(sources(), date(2026, 8, 14))
        self.assertEqual([item["offer_id"] for item in payload["offers"]], ["A"])

    def test_ordered_revenue_is_separate_from_confirmed_revenue(self):
        item = build_brief(sources(), date(2026, 8, 14))["offers"][0]
        self.assertEqual((item["demand"]["ordered_revenue"], item["economics"]["confirmed_revenue"]), ("250", "200"))

    def test_zero_is_preserved_not_missing(self):
        value = sources(); value["demand"][0] = ("A", 1, Decimal("0"), 0, datetime(2026, 8, 15, tzinfo=UTC), "valid")
        item = build_brief(value, date(2026, 8, 14))["offers"][0]
        self.assertEqual((item["demand"]["ordered_revenue"], item["demand"]["ordered_units"]), ("0", 0))

    def test_missing_is_not_zero_and_warns(self):
        item = build_brief(sources(demand=False, finance=False), date(2026, 8, 14))["offers"][0]
        self.assertIsNone(item["demand"]["ordered_revenue"])
        self.assertIsNone(item["economics"]["profit_before_tax"])
        self.assertEqual(item["attention"]["level"], "WATCH")

    def test_no_fake_buyout_calculation(self):
        item = build_brief(sources(), date(2026, 8, 14))["offers"][0]
        self.assertEqual((item["fulfilment"]["buyout_units"], item["fulfilment"]["buyout_status"]), (None, "NOT_IMPLEMENTED"))

    def test_summary_margin_is_weighted(self):
        value = sources(); value["products"].append(("B", 2, 20, Decimal("100"), Decimal("40"), datetime(2026, 8, 14, tzinfo=UTC)))
        value["demand"].append(("B", 2, Decimal("100"), 1, datetime(2026, 8, 15, tzinfo=UTC), "valid"))
        value["finance"].append(("B", Decimal("100"), Decimal("10"), 1, 0))
        result = build_brief(value, date(2026, 8, 14))
        self.assertEqual(result["summary"]["margin_percent"], "20.0")

    def test_participating_and_candidate_are_separate(self):
        item = build_brief(sources(), date(2026, 8, 14))["offers"][0]
        self.assertEqual((len(item["promotions"]["participating"]), len(item["promotions"]["candidates"])), (1, 1))

    def test_inactive_cpc_orders_are_not_current_activity(self):
        item = build_brief(sources(cpc_state="CAMPAIGN_STATE_INACTIVE"), date(2026, 8, 14))["offers"][0]
        self.assertEqual(item["advertising"]["inactive_attribution_note"], "orders_are_attributed_history_not_current_activity")

    def test_tax_layer_is_explicitly_not_implemented(self):
        self.assertEqual(build_brief(sources(), date(2026, 8, 14))["tax_status"], "NOT_IMPLEMENTED")

    def test_compact_payload_is_deterministic_and_json_safe(self):
        first = build_brief(sources(), date(2026, 8, 14), datetime(2026, 8, 15, tzinfo=UTC))
        second = build_brief(sources(), date(2026, 8, 14), datetime(2026, 8, 15, tzinfo=UTC))
        self.assertEqual(first["compact_report_payload"], second["compact_report_payload"])
        json.dumps(first["compact_report_payload"], ensure_ascii=False, sort_keys=True)

    def test_extended_payload_is_deterministic(self):
        first = build_brief(sources(), date(2026, 8, 14), datetime(2026, 8, 15, tzinfo=UTC))
        second = build_brief(sources(), date(2026, 8, 14), datetime(2026, 8, 15, tzinfo=UTC))
        self.assertEqual(first["extended_report_payload"], second["extended_report_payload"])
