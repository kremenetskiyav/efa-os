import unittest

from commercial_baseline_collector.normalization import PayloadError, normalize_cpc, normalize_prices, normalize_seller_demand


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

    def test_prices_confirmed_contract(self):
        result = normalize_prices({"collection_ref":"p1","collected_at":"2026-08-16T00:00:00Z","persist":True,"items":[
            {"product_id":4861934525,"offer_id":"УФ 001Б","price":{"price":"757","old_price":"2900","min_price":"700","marketing_price":"624","marketing_seller_price":"757"}}
        ]})
        self.assertEqual(result["rows"][0]["product_id"],4861934525)
        self.assertEqual(str(result["rows"][0]["marketing_price"]),"624")

    def test_prices_duplicate_product_rejected(self):
        item={"product_id":1,"offer_id":"x","price":{"price":1,"old_price":1,"min_price":1,"marketing_price":1,"marketing_seller_price":1}}
        with self.assertRaises(PayloadError):
            normalize_prices({"collection_ref":"p","collected_at":"x","items":[item,item]})

    def test_real_price_contract_allows_absent_marketing_price_and_sku(self):
        result = normalize_prices({"collection_ref":"real","collected_at":"2026-08-16T10:44:39Z","items":[{
            "product_id":4861934525,"offer_id":"УФ 001Б",
            "price":{"price":757,"old_price":2900,"min_price":700,"marketing_seller_price":624},
        }]})
        self.assertIsNone(result["rows"][0]["marketing_price"])
        self.assertNotIn("sku", result["rows"][0])
