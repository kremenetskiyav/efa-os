"""Unit tests for the read-only function-tool adapter."""

from datetime import datetime
from decimal import Decimal
import json
import unittest

from config import DatabaseConfig, RecommendationConfig
from models import ProductEconomics
from tools import GET_PRICE_PROFIT_RECOMMENDATIONS_TOOL, ToolInputError, get_price_profit_recommendations


DATABASE_CONFIG = DatabaseConfig(host="localhost", port=5432, name="efa", user="efa", password="not-used")
RECOMMENDATION_CONFIG = RecommendationConfig(low_margin_percent=Decimal("15"))


def product(offer_id: str, profit: str, analytics_profit: str) -> ProductEconomics:
    return ProductEconomics(
        offer_id=offer_id,
        current_price=Decimal("667"),
        cost_price=Decimal("166"),
        revenue=Decimal("1000"),
        profit=Decimal(profit),
        commission=Decimal("-300"),
        logistics=Decimal("-100"),
        period_start=datetime(2026, 8, 1),
        period_end=datetime(2026, 8, 13),
        delivered_units=10,
        analytics_revenue=Decimal("1000"),
        analytics_profit=Decimal(analytics_profit),
    )


class ToolContractTests(unittest.TestCase):
    def test_openai_function_schema_is_strict_and_complete(self) -> None:
        self.assertEqual(GET_PRICE_PROFIT_RECOMMENDATIONS_TOOL["name"], "get_price_profit_recommendations")
        self.assertTrue(GET_PRICE_PROFIT_RECOMMENDATIONS_TOOL["strict"])
        parameters = GET_PRICE_PROFIT_RECOMMENDATIONS_TOOL["parameters"]
        self.assertEqual(parameters["required"], ["offer_id", "action"])
        self.assertFalse(parameters["additionalProperties"])

    def test_returns_json_safe_read_only_result(self) -> None:
        result = get_price_profit_recommendations(
            {"offer_id": None, "action": None},
            DATABASE_CONFIG,
            RECOMMENDATION_CONFIG,
            lambda _: [product("УФ 001Б", "100", "100")],
        )
        self.assertEqual((result["tool"], result["read_only"], result["count"]), ("get_price_profit_recommendations", True, 1))
        recommendation = result["recommendations"][0]
        json.dumps(result, ensure_ascii=False)
        self.assertEqual(recommendation["profit"], "100")
        self.assertEqual(recommendation["period_start"], "2026-08-01T00:00:00")
        self.assertIsNone(recommendation["proposed_price"])

    def test_filters_by_offer_id_and_action(self) -> None:
        result = get_price_profit_recommendations(
            {"offer_id": "УФ 002Б", "action": "CONSIDER_RAISE"},
            DATABASE_CONFIG,
            RECOMMENDATION_CONFIG,
            lambda _: [product("УФ 001Б", "200", "200"), product("УФ 002Б", "100", "100")],
        )
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["recommendations"][0]["offer_id"], "УФ 002Б")

    def test_rejects_arguments_outside_contract(self) -> None:
        with self.assertRaises(ToolInputError):
            get_price_profit_recommendations(
                {"offer_id": None}, DATABASE_CONFIG, RECOMMENDATION_CONFIG, lambda _: []
            )


if __name__ == "__main__":
    unittest.main()
