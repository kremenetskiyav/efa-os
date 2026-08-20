from __future__ import annotations

import unittest
from datetime import date

from pydantic import ValidationError

from efa_read_mcp.models import (
    AnalyticsInput,
    CpcDailyInput,
    HistoryInput,
    ProductInput,
    RegionLogisticsInput,
)


class InputValidationTests(unittest.TestCase):
    def test_offer_id_accepts_realistic_unicode_identifier(self) -> None:
        request = ProductInput(offer_id="УФ 005Б")
        self.assertEqual("УФ 005Б", request.offer_id)

    def test_offer_id_rejects_query_punctuation_and_surrounding_space(self) -> None:
        for value in (" SKU", "SKU ", "SKU;DROP", "SKU' OR 1=1", "", "x" * 65):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ProductInput(offer_id=value)

    def test_history_allows_366_inclusive_days(self) -> None:
        request = HistoryInput(
            offer_id="УФ 005Б",
            date_from=date(2024, 1, 1),
            date_to=date(2024, 12, 31),
            limit=500,
        )
        self.assertEqual(500, request.limit)

    def test_history_rejects_reverse_or_too_long_range(self) -> None:
        invalid_ranges = (
            (date(2026, 8, 2), date(2026, 8, 1)),
            (date(2024, 1, 1), date(2025, 1, 1)),
        )
        for date_from, date_to in invalid_ranges:
            with self.subTest(date_from=date_from, date_to=date_to), self.assertRaises(
                ValidationError
            ):
                HistoryInput(
                    offer_id="УФ 005Б", date_from=date_from, date_to=date_to, limit=100
                )

    def test_row_limits_are_bounded(self) -> None:
        for limit in (0, 501):
            with self.subTest(limit=limit), self.assertRaises(ValidationError):
                HistoryInput(
                    offer_id="УФ 005Б",
                    date_from=date(2026, 8, 1),
                    date_to=date(2026, 8, 2),
                    limit=limit,
                )
        with self.assertRaises(ValidationError):
            RegionLogisticsInput(offer_id="УФ 005Б", limit=201)
        self.assertEqual(200, AnalyticsInput(query="SELECT 1").max_rows)
        for max_rows in (0, 501):
            with self.subTest(max_rows=max_rows), self.assertRaises(ValidationError):
                AnalyticsInput(query="SELECT 1", max_rows=max_rows)

    def test_unknown_parameters_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ProductInput.model_validate({"offer_id": "УФ 005Б", "sql": "SELECT 1"})

    def test_cpc_scope_is_closed_and_dates_are_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            CpcDailyInput(
                date_from=date(2026, 8, 1),
                date_to=date(2026, 8, 2),
                data_scope="CAMPAIGN",
            )


if __name__ == "__main__":
    unittest.main()
