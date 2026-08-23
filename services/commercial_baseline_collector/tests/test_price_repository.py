from decimal import Decimal
import unittest

from commercial_baseline_collector.repository import PersistenceError, persist_prices


def payload(collection_ref="price-1"):
    return {"collection_ref":collection_ref,"collected_at":"2026-08-16T00:00:00Z","rows":[{
        "product_id":4861934525,"offer_id":"УФ 001Б","price":757,"old_price":2900,
        "min_price":700,"marketing_price":624,"marketing_seller_price":757,
        "sales_percent_fbs":Decimal("44"),"fbs_deliv_to_customer_amount":Decimal("25"),
        "acquiring":Decimal("6.24"),"fbs_direct_flow_trans_min_amount":Decimal("74"),
        "fbs_direct_flow_trans_max_amount":Decimal("218"),
        "fbs_return_flow_amount":Decimal("218")}]}


class Cursor:
    def __init__(self, current=True, existing=None, fail_on=None, run_id="run-1"):
        self.current=current; self.existing=existing; self.fail_on=fail_on; self.run_id=run_id; self.last=""; self.calls=[]; self.rowcount=1
    def execute(self, sql, params):
        self.last=sql; self.calls.append((sql,params))
        if self.fail_on == "history" and "INSERT INTO ozon_price_history" in sql: raise RuntimeError("history failure")
        if self.fail_on == "tariff" and "INSERT INTO ozon_fbs_tariff_snapshots" in sql: raise RuntimeError("tariff failure")
    def fetchone(self):
        if "SELECT run_id" in self.last: return self.existing
        if "RETURNING run_id" in self.last: return (self.run_id,)
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
        self.assertEqual(sum("UPDATE products SET" in sql for sql,_ in cur.calls),1)
        self.assertFalse(any("INSERT INTO ozon_price_history" in sql for sql,_ in cur.calls))
        self.assertEqual(sum("INSERT INTO ozon_fbs_tariff_snapshots" in sql for sql,_ in cur.calls),1)
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
        cur=Cursor(fail_on="history"); cur.fetchall=lambda:[(4861934525,"УФ 001Б",700,2900,700,624,757)]
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

    def test_tariff_snapshot_contains_canonical_identity_run_time_and_raw_fields(self):
        cur=Cursor(); conn=Connection(cur); persist_prices(payload(),lambda:conn)
        snapshots=[params for sql,params in cur.calls if "INSERT INTO ozon_fbs_tariff_snapshots" in sql]
        self.assertEqual(snapshots,[
            ("run-1",4861934525,"УФ 001Б","2026-08-16T00:00:00Z",Decimal("44"),
             Decimal("25"),Decimal("6.24"),Decimal("74"),Decimal("218"),Decimal("218"))
        ])

    def test_tariff_snapshot_is_inserted_for_each_canonical_product(self):
        collection=payload(); second=dict(collection["rows"][0]); second.update({"product_id":4861934526,"offer_id":"УФ 002Б"}); collection["rows"].append(second)
        cur=Cursor(); cur.fetchall=lambda:[
            (4861934525,"УФ 001Б",757,2900,700,624,757),
            (4861934526,"УФ 002Б",757,2900,700,624,757),
        ]
        conn=Connection(cur); persist_prices(collection,lambda:conn)
        self.assertEqual(sum("INSERT INTO ozon_fbs_tariff_snapshots" in sql for sql,_ in cur.calls),2)

    def test_new_runs_create_new_observations_when_price_and_tariffs_are_unchanged(self):
        cursors=[Cursor(run_id="run-a"),Cursor(run_id="run-b")]
        connections=[Connection(cursor) for cursor in cursors]
        persist_prices(payload("price-a"),lambda:connections[0])
        persist_prices(payload("price-b"),lambda:connections[1])
        snapshots=[
            params for cursor in cursors for sql,params in cursor.calls
            if "INSERT INTO ozon_fbs_tariff_snapshots" in sql
        ]
        self.assertEqual([snapshot[0] for snapshot in snapshots],["run-a","run-b"])
        self.assertFalse(any("INSERT INTO ozon_price_history" in sql for cursor in cursors for sql,_ in cursor.calls))

    def test_product_and_offer_mismatch_rolls_back_before_run_creation(self):
        collection=payload(); collection["rows"][0]["offer_id"]="УФ 002Б"
        cur=Cursor(); conn=Connection(cur)
        with self.assertRaises(PersistenceError): persist_prices(collection,lambda:conn)
        self.assertFalse(any("INSERT INTO price_collection_runs" in sql for sql,_ in cur.calls))
        self.assertEqual(conn.events[-2:],["rollback","close"])

    def test_tariff_insert_failure_rolls_back_without_successful_run_finalization(self):
        cur=Cursor(fail_on="tariff"); conn=Connection(cur)
        with self.assertRaises(RuntimeError): persist_prices(payload(),lambda:conn)
        self.assertFalse(any("UPDATE price_collection_runs SET status='success'" in sql for sql,_ in cur.calls))
        self.assertEqual(conn.events[-2:],["rollback","close"])

    def test_optional_tariff_diagnostics_are_persisted_as_null(self):
        collection=payload()
        for name in ("acquiring","fbs_direct_flow_trans_min_amount","fbs_direct_flow_trans_max_amount","fbs_return_flow_amount"):
            collection["rows"][0][name]=None
        cur=Cursor(); conn=Connection(cur); persist_prices(collection,lambda:conn)
        snapshot=next(params for sql,params in cur.calls if "INSERT INTO ozon_fbs_tariff_snapshots" in sql)
        self.assertEqual(snapshot[6:],(None,None,None,None))
