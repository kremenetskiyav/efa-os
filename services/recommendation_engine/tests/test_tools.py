from datetime import datetime
from decimal import Decimal
import json
import unittest

from config import DatabaseConfig, RecommendationConfig
from models import PriceWindow, ProductEconomics
from tools import GET_PRICE_PROFIT_RECOMMENDATIONS_TOOL, get_price_profit_recommendations

DB = DatabaseConfig("localhost", 5432, "efa", "efa", "not-used")
CONFIG = RecommendationConfig(Decimal("15"), 10, Decimal("20"))

def product(offer_id: str) -> ProductEconomics:
    w = PriceWindow(Decimal("100"), 12, 12, Decimal("1200"), Decimal("-240"), Decimal("-120"), Decimal("0"), Decimal("480"), Decimal("0"), Decimal("360"), datetime(2026, 8, 1), datetime(2026, 8, 2))
    return ProductEconomics(offer_id, Decimal("100"), Decimal("40"), (w,))

class ToolV2Tests(unittest.TestCase):
    def test_schema_includes_lower_action(self) -> None:
        self.assertIn("CONSIDER_LOWER", GET_PRICE_PROFIT_RECOMMENDATIONS_TOOL["parameters"]["properties"]["action"]["enum"])

    def test_result_is_json_safe_and_read_only(self) -> None:
        result = get_price_profit_recommendations({"offer_id": None, "action": None}, DB, CONFIG, lambda _: [product("УФ 001Б")])
        json.dumps(result, ensure_ascii=False)
        self.assertEqual((result["read_only"], result["count"]), (True, 1))
        self.assertEqual(result["recommendations"][0]["current_effective_price"], "100")
