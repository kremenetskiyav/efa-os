import unittest

from commercial_baseline_collector.repository import PersistenceError, persist_prices


def payload():
    return {"collection_ref":"price-1","collected_at":"2026-08-16T00:00:00Z","rows":[{
        "product_id":4861934525,"offer_id":"УФ 001Б","price":757,"old_price":2900,
        "min_price":700,"marketing_price":624,"marketing_seller_price":757}]}


class Cursor:
    def __init__(self, current=True, existing=None, fail=False):
        self.current=current; self.existing=existing; self.fail=fail; self.last=""; self.calls=[]; self.rowcount=1
    def execute(self, sql, params):
        self.last=sql; self.calls.append((sql,params))
        if self.fail and "INSERT INTO ozon_price_history" in sql: raise RuntimeError("history failure")
    def fetchone(self):
        if "SELECT run_id" in self.last: return self.existing
        if "RETURNING run_id" in self.last: return ("run-1",)
        return None
    def fetchall(self):
        return [(4861934525,"УФ 001Б",757,2900,700,624,757)] if self.current else []


class Connection:
    def __init__(self, cursor): self.cur=cursor; self.events=[]
    def cursor(self): return self.cur
    def commit(self): self.events.append("commit")
    def rollback(self): self.events.append("rollback")
    def close(self): self.events.append("close")


class PriceRepositoryTests(unittest.TestCase):
    def test_unchanged_updates_freshness_without_history_insert(self):
        cur=Cursor(); conn=Connection(cur); result=persist_prices(payload(),lambda:conn)
        self.assertEqual(result["collection_status"],"SUCCESS_UNCHANGED")
        self.assertFalse(any("INSERT INTO ozon_price_history" in sql for sql,_ in cur.calls))
        self.assertEqual(conn.events[-2:],["commit","close"])

    def test_changed_inserts_one_history_row(self):
        cur=Cursor(); cur.fetchall=lambda:[(4861934525,"УФ 001Б",700,2900,700,624,757)]
        conn=Connection(cur); result=persist_prices(payload(),lambda:conn)
        self.assertEqual(result["changed_records"],1)
        self.assertEqual(sum("INSERT INTO ozon_price_history" in sql for sql,_ in cur.calls),1)

    def test_exact_mapping_required(self):
        cur=Cursor(current=False); conn=Connection(cur)
        with self.assertRaises(PersistenceError): persist_prices(payload(),lambda:conn)
        self.assertEqual(conn.events[-2:],["rollback","close"])

    def test_idempotent_replay_writes_nothing(self):
        cur=Cursor(existing=("old","success",1,0,1)); conn=Connection(cur)
        result=persist_prices(payload(),lambda:conn)
        self.assertTrue(result["idempotent_replay"])
        self.assertFalse(any("INSERT INTO" in sql for sql,_ in cur.calls))

    def test_failure_rolls_back_all(self):
        cur=Cursor(fail=True); cur.fetchall=lambda:[(4861934525,"УФ 001Б",700,2900,700,624,757)]
        conn=Connection(cur)
        with self.assertRaises(RuntimeError): persist_prices(payload(),lambda:conn)
        self.assertEqual(conn.events[-2:],["rollback","close"])

    def test_marketing_seller_change_is_not_a_new_seller_price_interval(self):
        cur=Cursor(); cur.fetchall=lambda:[(4861934525,"УФ 001Б",757,2900,700,624,700)]
        conn=Connection(cur); result=persist_prices(payload(),lambda:conn)
        self.assertEqual(result["changed_records"],1)
        history=[sql for sql,_ in cur.calls if "INSERT INTO ozon_price_history" in sql]
        self.assertEqual(len(history),1)
        self.assertNotIn("UPDATE ozon_price_history", "\n".join(sql for sql,_ in cur.calls))
