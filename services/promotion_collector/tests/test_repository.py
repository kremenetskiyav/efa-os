import unittest
from promotion_collector.repository import PersistenceError, get_run_by_collection_ref, persist_collection
from promotion_collector.database import map_product_ids_with_cursor


class Cursor:
    def __init__(self, existing=None, fail_insert=False):
        self.existing=existing; self.fail_insert=fail_insert; self.calls=[]; self.rowcount=1; self._last=""
    def execute(self,sql,params):
        self._last=sql; self.calls.append(("execute",sql,params))
    def executemany(self,sql,rows):
        self.calls.append(("executemany",sql,rows))
        if self.fail_insert: raise RuntimeError("insert failed")
    def fetchone(self):
        if "WHERE collection_ref" in self._last: return self.existing
        if "RETURNING run_id" in self._last: return ("run-1",)
        return None
    def fetchall(self): return [(10,"УФ 001Б")]

class Connection:
    def __init__(self,cursor): self.cur=cursor; self.events=[]
    def cursor(self): self.events.append("cursor"); return self.cur
    def commit(self): self.events.append("commit")
    def rollback(self): self.events.append("rollback")
    def close(self): self.events.append("close")

def collection():
    return {"collection_ref":"r1","collected_at":"2026-08-15T00:00:00Z","mapping_status":"valid","actions_count":1,"participating_records":1,"candidate_records":0,"unique_product_ids":1,"mapped_offer_ids":1,"unmapped_product_ids_count":0,"error_summary":None,"snapshots":[{"action_id":1,"source_list_type":"PARTICIPATING","product_id":10,"offer_id":"УФ 001Б","data_quality_status":"valid"}]}

class RepositoryTests(unittest.TestCase):
    def test_batch_mapping_contract_for_five_known_products(self):
        expected={4861934500:"УФ 004Б",4861934525:"УФ 001Б",4861934539:"УФ 002Б",4861934541:"УФ 003Б",4861934542:"УФ 005Б"}
        cur=Cursor(); cur.fetchall=lambda:list(expected.items())
        self.assertEqual(map_product_ids_with_cursor(cur,set(expected)),expected)
        self.assertEqual(sum("SELECT product_id" in call[1] for call in cur.calls),1)
    def test_success_commits_in_order(self):
        cur=Cursor(); conn=Connection(cur); result=persist_collection(collection(),lambda:conn)
        sql=" ".join(call[1] for call in cur.calls)
        self.assertLess(sql.index("INSERT INTO promotion_runs"),sql.index("SELECT product_id")); self.assertLess(sql.index("SELECT product_id"),sql.index("INSERT INTO promotion_snapshots")); self.assertLess(sql.index("INSERT INTO promotion_snapshots"),sql.index("UPDATE promotion_runs"))
        self.assertEqual((result["idempotent_replay"],conn.events[-2:]),(False,["commit","close"]))
    def test_insert_failure_rolls_back(self):
        cur=Cursor(fail_insert=True); conn=Connection(cur)
        with self.assertRaises(RuntimeError): persist_collection(collection(),lambda:conn)
        self.assertEqual(conn.events[-2:],["rollback","close"])
    def test_successful_existing_run_is_replayed_without_writes(self):
        existing=("old","r1",None,"success",1,1,0,1,1,0,"valid",None,None); cur=Cursor(existing); conn=Connection(cur)
        result=persist_collection(collection(),lambda:conn)
        self.assertTrue(result["idempotent_replay"]); self.assertFalse(any("INSERT" in c[1] or "UPDATE" in c[1] for c in cur.calls))
    def test_non_success_existing_run_is_not_modified(self):
        existing=("old","r1",None,"running",0,0,0,0,0,0,"invalid",None,None); cur=Cursor(existing); conn=Connection(cur)
        with self.assertRaises(PersistenceError): persist_collection(collection(),lambda:conn)
        self.assertFalse(any("UPDATE" in c[1] for c in cur.calls))
    def test_get_run_uses_select(self):
        cur=Cursor(); get_run_by_collection_ref(cur,"r1"); self.assertIn("SELECT run_id",cur.calls[0][1])
    def test_repository_has_no_destructive_or_snapshot_update_sql(self):
        from pathlib import Path
        source=Path(__file__).parents[1].joinpath("repository.py").read_text()
        self.assertNotIn("DELETE FROM",source); self.assertNotIn("UPDATE promotion_snapshots",source); self.assertNotIn("CREATE TABLE",source)
