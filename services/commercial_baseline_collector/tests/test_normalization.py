from decimal import Decimal
import json
from pathlib import Path
import unittest

from commercial_baseline_collector.normalization import PayloadError, normalize_cpc, normalize_prices, normalize_seller_demand


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ozon_product_prices_v5_uf001b.json"
OMITTED = object()


def cpc_row(*, sku=1001, orders=OMITTED):
    row = {
        "date": "29.08.2026",
        "sku": str(sku),
        "views": 0,
        "clicks": 0,
        "ctr": "0,00",
        "avgBid": "0,00",
        "moneySpent": "0,00",
        "ordersMoney": "0,00",
        "drr": "0,0",
        "general_drr": "0,0",
        "product_gmv": "0,00",
        "price": "600,00",
    }
    if orders is not OMITTED:
        row["orders"] = orders
    return row


def cpc_payload(rows):
    campaigns = []
    report = {}
    for offset, row in enumerate(rows):
        campaign_id = 101 + offset
        campaigns.append({
            "id": campaign_id,
            "state": "CAMPAIGN_STATE_INACTIVE",
            "advObjectType": "SKU",
        })
        report[str(campaign_id)] = {"report": {"rows": [row]}}
    return {
        "collection_ref": "cpc-2026-08-29-sanitized",
        "collected_at": "2026-08-30T04:40:00Z",
        "business_date": "2026-08-29",
        "report_uuid": "6a1fd928-6116-4c35-94e7-bbb999e26635",
        "campaigns": campaigns,
        "report": report,
    }


def price_item():
    return {
        "product_id": 4861934525,
        "offer_id": "УФ 001Б",
        "acquiring": 6.24,
        "commissions": {
            "sales_percent_fbs": 44,
            "fbs_deliv_to_customer_amount": 25,
            "fbs_direct_flow_trans_min_amount": 74,
            "fbs_direct_flow_trans_max_amount": 218,
            "fbs_return_flow_amount": 218,
        },
        "price": {
            "price": 757,
            "old_price": 2900,
            "min_price": 700,
            "marketing_price": 624,
            "marketing_seller_price": 757,
        },
    }


class NormalizationTests(unittest.TestCase):
    def test_seller_keeps_only_confirmed_metrics(self):
        result = normalize_seller_demand({
            "collection_ref": "seller-2026-08-10", "collected_at": "2026-08-11T04:00:00Z",
            "business_date": "2026-08-10", "persist": True,
            "rows": [{"sku": 4601821825, "ordered_revenue": 2424, "ordered_units": 4, "hits_view": 999}],
        })
        self.assertEqual(set(result["rows"][0]), {"sku", "business_date", "ordered_revenue", "ordered_units", "collected_at", "collection_ref", "source"})

    def test_seller_duplicate_sku_rejected(self):
        payload = {"collection_ref":"x","collected_at":"x","business_date":"2026-08-10","rows":[{"sku":1,"ordered_revenue":1,"ordered_units":1},{"sku":1,"ordered_revenue":1,"ordered_units":1}]}
        with self.assertRaises(PayloadError):
            normalize_seller_demand(payload)

    def test_cpc_real_contract_and_comma_decimals(self):
        result = normalize_cpc({
            "collection_ref":"cpc-2026-08-10", "collected_at":"2026-08-11T05:00:00Z",
            "business_date":"2026-08-10", "report_uuid":"6a1fd928-6116-4c35-94e7-bbb999e26635",
            "campaigns":[{"id":29798564,"state":"CAMPAIGN_STATE_INACTIVE","advObjectType":"SKU"}],
            "report":{"29798564":{"report":{"rows":[{"date":"10.08.2026","sku":"4601821825","views":61,"clicks":2,"ctr":"3,28","avgBid":"6,50","moneySpent":"13,00","orders":1,"ordersMoney":"606,00","drr":"2,1","general_drr":"0,5","product_gmv":"2424,00","price":"624,00"}]}}},
        })
        self.assertEqual((result["rows"][0]["sku"], str(result["rows"][0]["money_spent"])), (4601821825, "13.00"))

    def test_cpc_unknown_campaign_rejected(self):
        with self.assertRaises(PayloadError):
            normalize_cpc({"collection_ref":"x","collected_at":"x","business_date":"2026-08-10","report_uuid":"x","campaigns":[],"report":{"1":{"report":{"rows":[]}}}})

    def test_cpc_omitted_zero_counters_are_zero(self):
        result = normalize_cpc({
            "collection_ref":"cpc-2026-08-14", "collected_at":"2026-08-15T05:00:00Z",
            "business_date":"2026-08-14", "report_uuid":"6a1fd928-6116-4c35-94e7-bbb999e26635",
            "campaigns":[{"id":29798536,"state":"CAMPAIGN_STATE_INACTIVE","advObjectType":"SKU"}],
            "report":{"29798536":{"report":{"rows":[{"date":"14.08.2026","sku":"4671345564","price":"599,00","ctr":"0,00","avgBid":"0,00","moneySpent":"0,00","orders":1,"ordersMoney":"598,00","drr":"0,0","general_drr":"0,0","product_gmv":"599,00"}]}}},
        })
        self.assertEqual((result["rows"][0]["views"], result["rows"][0]["clicks"]), (0, 0))

    def test_cpc_failed_shape_defaults_all_five_omitted_orders_to_zero(self):
        result = normalize_cpc(cpc_payload([
            cpc_row(sku=1001),
            cpc_row(sku=1002),
            cpc_row(sku=1003),
            cpc_row(sku=1004),
            cpc_row(sku=1005),
        ]))
        self.assertEqual(len(result["rows"]), 5)
        self.assertEqual([row["orders"] for row in result["rows"]], [0] * 5)

    def test_cpc_explicit_order_values_preserve_integer_policy(self):
        for supplied, expected in ((0, 0), (3, 3), ("2", 2)):
            with self.subTest(supplied=supplied):
                result = normalize_cpc(cpc_payload([cpc_row(orders=supplied)]))
                self.assertEqual(result["rows"][0]["orders"], expected)

    def test_cpc_malformed_supplied_orders_are_rejected(self):
        for supplied in (None, -1, 1.0, 1.5, "abc", True):
            with self.subTest(supplied=supplied), self.assertRaises(PayloadError):
                normalize_cpc(cpc_payload([cpc_row(orders=supplied)]))

    def test_cpc_unrelated_required_field_remains_strict(self):
        row = cpc_row()
        row.pop("ordersMoney")
        with self.assertRaises(PayloadError):
            normalize_cpc(cpc_payload([row]))

    def test_prices_confirmed_contract(self):
        result = normalize_prices({"collection_ref":"p1","collected_at":"2026-08-16T00:00:00Z","persist":True,"items":[price_item()]})
        self.assertEqual(result["rows"][0]["product_id"],4861934525)
        self.assertEqual(str(result["rows"][0]["marketing_price"]),"624")

    def test_prices_duplicate_product_rejected(self):
        item=price_item()
        with self.assertRaises(PayloadError):
            normalize_prices({"collection_ref":"p","collected_at":"x","items":[item,item]})

    def test_real_price_contract_allows_absent_marketing_price_and_sku(self):
        item=price_item(); item["price"].pop("marketing_price")
        result = normalize_prices({"collection_ref":"real","collected_at":"2026-08-16T10:44:39Z","items":[item]})
        self.assertIsNone(result["rows"][0]["marketing_price"])
        self.assertNotIn("sku", result["rows"][0])

    def test_production_fixture_preserves_raw_tariff_observation(self):
        item = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        result = normalize_prices({
            "collection_ref": "ozon-prices-execution-1806",
            "collected_at": "2026-08-23T06:20:00+03:00",
            "items": [item],
        })
        row = result["rows"][0]
        self.assertEqual(
            {
                "sales_percent_fbs": row["sales_percent_fbs"],
                "fbs_deliv_to_customer_amount": row["fbs_deliv_to_customer_amount"],
                "acquiring": row["acquiring"],
                "fbs_direct_flow_trans_min_amount": row["fbs_direct_flow_trans_min_amount"],
                "fbs_direct_flow_trans_max_amount": row["fbs_direct_flow_trans_max_amount"],
                "fbs_return_flow_amount": row["fbs_return_flow_amount"],
            },
            {
                "sales_percent_fbs": Decimal("44"),
                "fbs_deliv_to_customer_amount": Decimal("25"),
                "acquiring": Decimal("6.24"),
                "fbs_direct_flow_trans_min_amount": Decimal("74"),
                "fbs_direct_flow_trans_max_amount": Decimal("218"),
                "fbs_return_flow_amount": Decimal("218"),
            },
        )
        self.assertEqual(result["collected_at"], "2026-08-23T06:20:00+03:00")
        self.assertNotIn("volume_weight", row)
        self.assertFalse(any("first_mile" in name for name in row))

    def test_required_tariff_fields_are_not_nullable(self):
        for missing in ("sales_percent_fbs", "fbs_deliv_to_customer_amount"):
            item = price_item(); item["commissions"].pop(missing)
            with self.subTest(missing=missing), self.assertRaises(PayloadError):
                normalize_prices({"collection_ref":"p","collected_at":"x","items":[item]})

    def test_invalid_tariff_numbers_are_rejected(self):
        invalid_values = (
            ("sales_percent_fbs", True),
            ("sales_percent_fbs", "44"),
            ("sales_percent_fbs", float("nan")),
            ("sales_percent_fbs", float("inf")),
            ("sales_percent_fbs", float("-inf")),
            ("sales_percent_fbs", 101),
            ("fbs_deliv_to_customer_amount", -1),
        )
        for field, invalid in invalid_values:
            item = price_item(); item["commissions"][field] = invalid
            with self.subTest(field=field, invalid=invalid), self.assertRaises(PayloadError):
                normalize_prices({"collection_ref":"p","collected_at":"x","items":[item]})

    def test_optional_tariff_diagnostics_may_be_absent(self):
        item = price_item(); item.pop("acquiring")
        for name in (
            "fbs_direct_flow_trans_min_amount",
            "fbs_direct_flow_trans_max_amount",
            "fbs_return_flow_amount",
        ):
            item["commissions"].pop(name)
        row = normalize_prices({"collection_ref":"p","collected_at":"x","items":[item]})["rows"][0]
        self.assertIsNone(row["acquiring"])
        self.assertIsNone(row["fbs_direct_flow_trans_min_amount"])
        self.assertIsNone(row["fbs_direct_flow_trans_max_amount"])
        self.assertIsNone(row["fbs_return_flow_amount"])

    def test_direct_flow_minimum_cannot_exceed_maximum(self):
        item = price_item()
        item["commissions"]["fbs_direct_flow_trans_min_amount"] = 219
        with self.assertRaises(PayloadError):
            normalize_prices({"collection_ref":"p","collected_at":"x","items":[item]})
