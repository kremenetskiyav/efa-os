from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from efa_read_mcp.models import (
    AnalyticsInput,
    CpcDailyInput,
    CpcDailyItem,
    DailyPerformanceItem,
    HistoryInput,
    ListProductsInput,
    PriceHistoryItem,
    ProductInput,
    ProductOverviewItem,
    PromotionInput,
    PromotionStateItem,
    RegionLogisticsItem,
    RegionLogisticsInput,
    StockHistoryItem,
)
from efa_read_mcp.database import AnalyticsQueryResult
from efa_read_mcp.service import SafeServiceError
from efa_read_mcp.service import EfaReadService
from fakes import FakeRepository


def nullable_row(model, **values):
    row = {name: None for name in model.model_fields}
    row.update(values)
    return row


class ServiceMappingTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_result_is_not_an_error(self) -> None:
        service = EfaReadService(FakeRepository())
        response = await service.get_product_overview(ProductInput(offer_id="УФ 005Б"))
        self.assertEqual("empty", response.result_status)
        self.assertEqual(0, response.row_count)
        self.assertIsNone(response.item)

    async def test_list_mapping_and_parameter_forwarding(self) -> None:
        rows = {
            "list_products": [
                {
                    "offer_id": "УФ 005Б",
                    "sku": 123,
                    "product_name": "Filter",
                    "brand": "EFA",
                    "is_archived": False,
                    "price_observed_at": None,
                    "stock_snapshot_at": None,
                }
            ]
        }
        repository = FakeRepository(rows)
        response = await EfaReadService(repository).list_products(
            ListProductsInput(include_archived=True)
        )
        self.assertEqual("ok", response.result_status)
        self.assertEqual(1, response.row_count)
        self.assertEqual("УФ 005Б", response.items[0].offer_id)
        self.assertEqual(("list_products", (True,)), repository.calls[0])

    async def test_overview_preserves_null_stock_and_current_cost_limitation(self) -> None:
        row = nullable_row(
            ProductOverviewItem,
            offer_id="УФ 005Б",
            current_price=Decimal("999.90"),
            cost_price=Decimal("450.00"),
        )
        service = EfaReadService(FakeRepository({"get_product_overview": [row]}))
        response = await service.get_product_overview(ProductInput(offer_id="УФ 005Б"))
        self.assertIsNone(response.item.total_present)
        self.assertIsNone(response.item.stock_snapshot_at)
        self.assertTrue(any("current product cost" in text for text in response.known_limitations))

    async def test_stock_mapping_keeps_null_quantities(self) -> None:
        snapshot_at = datetime(2026, 8, 13, tzinfo=timezone.utc)
        row = nullable_row(
            StockHistoryItem,
            offer_id="УФ 005Б",
            snapshot_at=snapshot_at,
        )
        service = EfaReadService(FakeRepository({"get_stock_history": [row]}))
        response = await service.get_stock_history(
            HistoryInput(
                offer_id="УФ 005Б",
                date_from=date(2026, 8, 1),
                date_to=date(2026, 8, 20),
                limit=17,
            )
        )
        self.assertIsNone(response.items[0].total_present)
        self.assertEqual(17, service._repository.calls[0][1][-1])

    async def test_cpc_missing_rows_remain_empty_not_success_zero(self) -> None:
        service = EfaReadService(FakeRepository())
        response = await service.get_cpc_daily(
            CpcDailyInput(
                offer_id="УФ 005Б",
                date_from=date(2026, 8, 1),
                date_to=date(2026, 8, 20),
            )
        )
        self.assertEqual("empty", response.result_status)
        self.assertEqual([], response.items)

    async def test_region_limit_and_confidence_are_forwarded(self) -> None:
        repository = FakeRepository()
        await EfaReadService(repository).get_region_logistics(
            RegionLogisticsInput(offer_id="УФ 005Б", minimum_confidence="HIGH", limit=23)
        )
        self.assertEqual(
            ("get_region_logistics", ("УФ 005Б", "HIGH", 23)), repository.calls[0]
        )

    async def test_all_remaining_view_rows_map_to_typed_outputs(self) -> None:
        observed_at = datetime(2026, 8, 19, tzinfo=timezone.utc)
        repository = FakeRepository(
            {
                "get_price_history": [
                    nullable_row(
                        PriceHistoryItem,
                        offer_id="УФ 005Б",
                        observed_at=observed_at,
                        price=Decimal("1010.50"),
                    )
                ],
                "get_daily_performance": [
                    nullable_row(
                        DailyPerformanceItem,
                        offer_id="УФ 005Б",
                        business_date=date(2026, 8, 19),
                        ordered_units=2,
                        delivered_units=1,
                        economics_quality_status="CURRENT_COST_BASIS",
                    )
                ],
                "get_region_logistics": [
                    nullable_row(
                        RegionLogisticsItem,
                        offer_id="УФ 005Б",
                        confidence="HIGH",
                        data_through=datetime(2026, 8, 19),
                    )
                ],
                "get_promotion_state": [
                    nullable_row(
                        PromotionStateItem,
                        offer_id="УФ 005Б",
                        participation_state="PARTICIPATING",
                        observed_at=observed_at,
                    )
                ],
                "get_cpc_daily": [
                    nullable_row(
                        CpcDailyItem,
                        business_date=date(2026, 8, 19),
                        data_scope="ACCOUNT",
                        offer_id=None,
                        collection_status="SUCCESS_ZERO",
                        observed_at=observed_at,
                    )
                ],
            }
        )
        service = EfaReadService(repository)
        history = HistoryInput(
            offer_id="УФ 005Б",
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 20),
        )

        price = await service.get_price_history(history)
        performance = await service.get_daily_performance(history)
        region = await service.get_region_logistics(RegionLogisticsInput(offer_id="УФ 005Б"))
        promotion = await service.get_promotion_state(PromotionInput(offer_id="УФ 005Б"))
        cpc = await service.get_cpc_daily(
            CpcDailyInput(date_from=date(2026, 8, 1), date_to=date(2026, 8, 20))
        )

        self.assertEqual(Decimal("1010.50"), price.items[0].price)
        self.assertEqual(2, performance.items[0].ordered_units)
        self.assertEqual(1, performance.items[0].delivered_units)
        self.assertEqual("HIGH", region.items[0].confidence)
        self.assertEqual("PARTICIPATING", promotion.items[0].participation_state)
        self.assertEqual("ACCOUNT", cpc.items[0].data_scope)
        self.assertIsNone(cpc.items[0].offer_id)
        self.assertEqual("SUCCESS_ZERO", cpc.items[0].collection_status)

    async def test_analytics_maps_json_safe_rows_and_truncation(self) -> None:
        repository = FakeRepository(
            analytics_result=AnalyticsQueryResult(
                columns=["offer_id", "price", "business_date"],
                rows=[["УФ 005Б", Decimal("1010.50"), date(2026, 8, 19)]],
                truncated=True,
            )
        )
        submitted = (
            "SELECT offer_id, current_price, CURRENT_DATE "
            "FROM mcp_read.product_overview"
        )
        with self.assertLogs("efa_read_mcp.audit", level="INFO") as captured:
            response = await EfaReadService(repository).query_analytics(
                AnalyticsInput(
                    query=submitted,
                    max_rows=200,
                )
            )
        self.assertEqual(["offer_id", "price", "business_date"], response.columns)
        self.assertEqual([["УФ 005Б", "1010.50", "2026-08-19"]], response.rows)
        self.assertEqual(1, response.row_count)
        self.assertTrue(response.truncated)
        self.assertEqual("query_analytics", repository.calls[0][0])
        self.assertEqual(200, repository.calls[0][1][1])
        log_output = "\n".join(captured.output)
        self.assertNotIn(submitted, log_output)
        self.assertNotIn("УФ 005Б", log_output)

    async def test_analytics_rejection_logs_no_query_text(self) -> None:
        submitted = "DELETE FROM public.products"
        service = EfaReadService(FakeRepository())
        with self.assertLogs("efa_read_mcp.audit", level="INFO") as captured:
            with self.assertRaises(SafeServiceError):
                await service.query_analytics(AnalyticsInput(query=submitted))
        self.assertNotIn(submitted, "\n".join(captured.output))
        self.assertIn("tool=query_analytics", captured.output[0])


if __name__ == "__main__":
    unittest.main()
