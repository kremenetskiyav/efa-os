import unittest
from promotion_collector.collector import normalize

class PromotionParsingTests(unittest.TestCase):
    def test_normalizes_confirmed_fields_and_missing_prices(self):
        row=normalize({"id":7,"title":"A","date_start":"s","date_end":"e"},{"id":1,"action_price":500},"participating")
        self.assertEqual((row.action_id,row.product_id,row.action_price,row.source_kind),(7,1,"500","participating"))
    def test_missing_product_fields_remain_null(self):
        row=normalize({"id":7},{},"candidate")
        self.assertIsNone(row.product_id)
    def test_confirmed_elastic_fields_are_preserved_and_missing_is_null(self):
        action={"id":1,"title":"Elastic","action_type":"ELASTIC_BOOSTING"}
        row=normalize(action,{"id":10,"current_boost":15,"min_boost":10,"max_boost":75},"participating")
        self.assertEqual((row.current_boost,row.min_boost,row.max_boost),("15","10","75"))
        missing=normalize(action,{"id":10},"participating")
        self.assertEqual((missing.current_boost,missing.min_boost,missing.max_boost),(None,None,None))
