"""Unit tests for the private HTTP transport adapter."""

import unittest

from server import ANOMALY_TOOL_PATH, TOOL_PATH, normalize_transport_arguments
from tools import ToolInputError


class ServerAdapterTests(unittest.TestCase):
    def test_normalizes_n8n_null_placeholders(self) -> None:
        self.assertEqual(
            normalize_transport_arguments({"offer_id": "null", "action": "CONSIDER_RAISE"}),
            {"offer_id": None, "action": "CONSIDER_RAISE"},
        )

    def test_preserves_concrete_arguments(self) -> None:
        self.assertEqual(
            normalize_transport_arguments({"offer_id": "УФ 005Б", "action": "null"}),
            {"offer_id": "УФ 005Б", "action": None},
        )

    def test_rejects_non_object_request_body(self) -> None:
        with self.assertRaises(ToolInputError):
            normalize_transport_arguments([])

    def test_endpoint_path_is_stable(self) -> None:
        self.assertEqual(TOOL_PATH, "/v1/get_price_profit_recommendations")
        self.assertEqual(ANOMALY_TOOL_PATH, "/v1/get_profit_cost_anomalies")


if __name__ == "__main__":
    unittest.main()
