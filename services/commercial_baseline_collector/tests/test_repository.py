import unittest

from commercial_baseline_collector.repository import PersistenceError, persist_cpc, persist_seller_demand


class Cursor:
    def __init__(self, existing=None, fail=False):
        self.calls=[]; self._last=""; self.existing=existing; self.fail=fail; self.rowcount=1
    def execute(self, sql, params):
        self._last=sql; self.calls.append(("execute",sql,params))
        if self.fail and "INSERT INTO" in sql: raise RuntimeError("insert failed")
    def executemany(self, sql, rows):
        self.calls.append(("executemany",sql,rows))
        if self.fail: raise RuntimeError("insert failed")
    def fetchone(self):
        if "SELECT run_id" in self._last: return self.existing
        if "RETURNING run_id" in self._last: return ("run-1",)
        return None
    def fetchall(self): return [(4601821825,"УФ 001Б")]


class Connection:
    def __init__(self, cursor): self.cur=cursor; self.events=[]
    def cursor(self): return self.cur
    def commit(self): self.events.append("commit")
    def rollback(self): self.events.append("rollback")
    def close(self): self.events.append("close")


def seller():
    return {"rows":[{"sku":4601821825,"business_date":"2026-08-10","ordered_revenue":2424,"ordered_units":4,"collected_at":"2026-08-11T04:00:00Z","collection_ref":"s1","source":"ozon_seller_analytics_v1"}]}


def cpc():
    row={"business_date":"2026-08-10","campaign_id":29798564,"campaign_state":"INACTIVE","campaign_type":"SKU","sku":4601821825,"views":61,"clicks":2,"ctr":3.28,"avg_bid":6.5,"money_spent":13,"orders":1,"orders_money":606,"drr":2.1,"general_drr":0.5,"product_gmv":2424,"price":624,"report_uuid":"6a1fd928-6116-4c35-94e7-bbb999e26635","source":"ozon_performance_statistics_v1"}
    return {"collection_ref":"c1","collected_at":"2026-08-11T05:00:00Z","business_date":"2026-08-10","report_uuid":row["report_uuid"],"campaigns_count":1,"rows":[row]}


class RepositoryTests(unittest.TestCase):
    def test_seller_success_and_exact_batch_mapping(self):
        cur=Cursor(); conn=Connection(cur); result=persist_seller_demand(seller(),lambda:conn)
        self.assertEqual((result["inserted_records"],conn.events[-2:]),(1,["commit","close"]))
        self.assertEqual(sum("SELECT sku, offer_id" in call[1] for call in cur.calls),1)

    def test_seller_unmapped_rolls_back(self):
        cur=Cursor(); cur.fetchall=lambda:[]; conn=Connection(cur)
        with self.assertRaises(PersistenceError): persist_seller_demand(seller(),lambda:conn)
        self.assertEqual(conn.events[-2:],["rollback","close"])

    def test_cpc_transaction_and_mapping_degradation(self):
        cur=Cursor(); cur.fetchall=lambda:[]; conn=Connection(cur); result=persist_cpc(cpc(),lambda:conn)
        self.assertEqual((result["mapping_status"],result["unmapped_skus"]),("invalid",[4601821825]))
        self.assertEqual(conn.events[-2:],["commit","close"])

    def test_cpc_idempotent_replay_has_no_insert(self):
        cur=Cursor(existing=("old-run","success")); conn=Connection(cur); result=persist_cpc(cpc(),lambda:conn)
        self.assertTrue(result["idempotent_replay"])
        self.assertFalse(any("INSERT" in call[1] for call in cur.calls))

    def test_failure_rolls_back(self):
        cur=Cursor(fail=True); conn=Connection(cur)
        with self.assertRaises(RuntimeError): persist_seller_demand(seller(),lambda:conn)
        self.assertEqual(conn.events[-2:],["rollback","close"])

    def test_no_destructive_sql(self):
        from pathlib import Path
        source=Path(__file__).parents[1].joinpath("repository.py").read_text()
        self.assertNotIn("DELETE FROM",source); self.assertNotIn("UPDATE seller_product_demand_daily",source); self.assertNotIn("UPDATE cpc_advertising_daily",source)
