import unittest

from commercial_baseline_collector.normalization import PayloadError, normalize_cpc, normalize_seller_demand


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
