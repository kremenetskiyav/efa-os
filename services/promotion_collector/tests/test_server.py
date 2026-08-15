import unittest
from pathlib import Path
from promotion_collector.server import PayloadError, collect

def payload(): return {"collection_ref":"r1","collected_at":"2026-08-15T00:00:00Z","actions":[{"id":1}],"action_details":[{"action_id":1,"products":[{"id":10}],"candidates":[{"id":10},{"id":11}]}]}
class BridgeTests(unittest.TestCase):
 def test_collector_has_no_direct_ozon_credentials_or_transport(self):
  source="\n".join(path.read_text() for path in Path(__file__).parents[1].glob("*.py"))
  self.assertNotIn("OZON_CLIENT_ID",source); self.assertNotIn("OZON_API_KEY",source); self.assertNotIn("urlopen",source)
 def test_valid_and_unique(self):
  result=collect(payload(),lambda ids:{10:"УФ 001Б",11:"УФ 002Б"}); self.assertEqual((result["participating_records"],result["candidate_records"],result["unique_product_ids"],result["mapped_offer_ids"]),(1,2,2,2))
 def test_rejects_malformed(self):
  with self.assertRaises(PayloadError): collect({},lambda _: {})
 def test_preserves_action_association(self): self.assertEqual(collect(payload(),lambda _: {10:"УФ",11:"УФ2"})["errors"],[])
 def test_unknown_action_is_not_mixed(self):
  p=payload(); p["action_details"][0]["action_id"]=2
  with self.assertRaises(PayloadError): collect(p,lambda _: {})
 def test_partial_mapping(self):
  result=collect(payload(),lambda _: {10:"УФ"}); self.assertEqual((result["unmapped_product_ids"],result["mapping_status"]),([11],"partial"))
 def test_default_request_is_non_persistent(self):
  called=[]; result=collect(payload(),lambda ids:{10:"УФ",11:"УФ2"},lambda *_:called.append(True))
  self.assertFalse(result["persisted"]); self.assertTrue(result["read_only"]); self.assertEqual(called,[])
 def test_explicit_persist_uses_repository(self):
  p=payload(); p["persist"]=True
  result=collect(p,lambda ids:{10:"УФ",11:"УФ2"},lambda data,factory:{"run_id":"r","idempotent_replay":False},lambda:None)
  self.assertTrue(result["persisted"]); self.assertFalse(result["read_only"])
 def test_duplicate_detail_is_rejected(self):
  p=payload(); p["action_details"][0]["products"].append({"id":10})
  with self.assertRaises(PayloadError): collect(p,lambda _: {})
 def test_unmapped_rows_are_degraded_and_lists_stay_separate(self):
  captured={}; p=payload(); p["persist"]=True
  collect(p,lambda ids:{10:"УФ"},lambda data,factory:captured.update(data) or {"run_id":"r","idempotent_replay":False},lambda:None)
  rows=captured["snapshots"]; self.assertEqual({r["source_list_type"] for r in rows},{"PARTICIPATING","CANDIDATE"})
  self.assertEqual(next(r for r in rows if r["product_id"]==11)["data_quality_status"],"review")
