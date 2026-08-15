import unittest
from promotion_collector.collector import normalize

class PromotionParsingTests(unittest.TestCase):
    def test_normalizes_confirmed_fields_and_missing_prices(self):
        row=normalize({"id":7,"title":"A","date_start":"s","date_end":"e"},{"id":1,"action_price":500},"participating")
        self.assertEqual((row.action_id,row.product_id,row.action_price,row.source_kind),(7,1,"500","participating"))
    def test_missing_product_fields_remain_null(self):
        row=normalize({"id":7},{},"candidate")
        self.assertIsNone(row.product_id)
