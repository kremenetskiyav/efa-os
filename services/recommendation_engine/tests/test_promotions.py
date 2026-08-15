from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import unittest

from config import DatabaseConfig, PromotionMonitoringConfig
from models import PromotionState
from promotions import build_promotion_state
from tools import get_promotion_monitoring


DB = DatabaseConfig("localhost", 5432, "efa", "efa", "not-used")
CONFIG = PromotionMonitoringConfig(7)
NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)


def state(*, offer_id="УФ 001Б", source="PARTICIPATING", end=None, price="757", action_price="624", quality="valid"):
    return PromotionState(offer_id, 4861934525, 1977747, "Action", "ELASTIC_BOOSTING", NOW - timedelta(days=1), end, source, "MANUAL", Decimal(price), Decimal(action_price), Decimal("624"), NOW, quality, ())


class PromotionMonitoringTests(unittest.TestCase):
    def test_participating_signal(self): self.assertIn("ACTIVE_PARTICIPATION", build_promotion_state(state(), CONFIG, NOW).signals)
    def test_candidate_signal(self): self.assertIn("AVAILABLE_CANDIDATE", build_promotion_state(state(source="CANDIDATE", action_price="0"), CONFIG, NOW).signals)
    def test_ending_soon_signal(self): self.assertIn("PROMOTION_ENDING_SOON", build_promotion_state(state(end=NOW + timedelta(days=3)), CONFIG, NOW).signals)
    def test_action_price_below_current_price(self): self.assertIn("ACTION_PRICE_BELOW_CURRENT_PRICE", build_promotion_state(state(), CONFIG, NOW).signals)
    def test_zero_candidate_price_is_not_discount_signal(self): self.assertNotIn("ACTION_PRICE_BELOW_CURRENT_PRICE", build_promotion_state(state(source="CANDIDATE", action_price="0"), CONFIG, NOW).signals)
    def test_data_quality_issue(self): self.assertIn("DATA_QUALITY_ISSUE", build_promotion_state(state(offer_id=None, quality="review"), CONFIG, NOW).signals)
    def test_tool_filters_and_is_json_safe(self):
        data = [state(), state(offer_id="УФ 002Б", source="CANDIDATE", action_price="0")]
        output = get_promotion_monitoring({"offer_id": None, "state": "CANDIDATE", "signal": "AVAILABLE_CANDIDATE"}, DB, CONFIG, lambda _: data)
        json.dumps(output, ensure_ascii=False)
        self.assertEqual((output["read_only"], output["count"], output["promotions"][0]["offer_id"]), (True, 1, "УФ 002Б"))
    def test_no_write_operations_in_monitoring_layer(self):
        from pathlib import Path
        source = Path(__file__).parents[1].joinpath("promotions.py").read_text() + Path(__file__).parents[1].joinpath("database.py").read_text()
        self.assertNotIn("INSERT INTO promotion", source)
        self.assertNotIn("UPDATE promotion", source)
        self.assertNotIn("DELETE FROM promotion", source)
