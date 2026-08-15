import unittest
from pathlib import Path
from promotion_collector.server import PayloadError, collect

def payload(): return {"collection_ref":"r1","collected_at":"2026-08-15T00:00:00Z","actions":[{"id":1}],"action_details":[{"action_id":1,"products":[{"id":10}],"candidates":[{"id":10},{"id":11}]}]}
class BridgeTests(unittest.TestCase):
 def test_collector_has_no_direct_ozon_credentials_or_transport(self):
  source=Path(__file__).parents[1].joinpath("collector.py").read_text()
  self.assertNotIn("OZON_CLIENT_ID",source); self.assertNotIn("OZON_API_KEY",source); self.assertNotIn("urlopen",source)
 def test_valid_and_unique(self):
  result=collect(payload()); self.assertEqual((result["participating_records"],result["candidate_records"],result["unique_product_ids"]),(1,2,2))
 def test_rejects_malformed(self):
  with self.assertRaises(PayloadError): collect({})
 def test_preserves_action_association(self): self.assertEqual(collect(payload())["errors"],[])
 def test_unknown_action_is_not_mixed(self):
  p=payload(); p["action_details"][0]["action_id"]=2; self.assertEqual(collect(p)["errors"],["unknown_action_id:2"])
