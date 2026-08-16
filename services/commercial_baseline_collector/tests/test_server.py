import unittest
from pathlib import Path

from commercial_baseline_collector.server import PRICE_PATH, SELLER_PATH, collect


class ServerTests(unittest.TestCase):
    def test_default_is_non_persistent(self):
        result=collect(SELLER_PATH,{"collection_ref":"s","collected_at":"2026-08-11T00:00:00Z","business_date":"2026-08-10","rows":[]},lambda:None)
        self.assertTrue(result["read_only_api"]); self.assertFalse(result["persisted"])

    def test_no_ozon_credentials_or_transport(self):
        source="\n".join(path.read_text() for path in Path(__file__).parents[1].glob("*.py"))
        for forbidden in ("OZON_CLIENT_ID","OZON_API_KEY","api-seller.ozon.ru","api-performance.ozon.ru","urlopen"):
            self.assertNotIn(forbidden,source)

    def test_price_default_is_non_persistent(self):
        result=collect(PRICE_PATH,{"collection_ref":"p","collected_at":"2026-08-16T00:00:00Z","items":[{"product_id":1,"offer_id":"x","price":{"price":1,"old_price":1,"min_price":1,"marketing_price":1,"marketing_seller_price":1}}]},lambda:None)
        self.assertFalse(result["persisted"])
