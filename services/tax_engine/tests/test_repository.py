import unittest
from decimal import Decimal
from pathlib import Path

from services.tax_engine.models import TaxRevenueEvent
from services.tax_engine.repository import PersistenceError, persist_import


class Cursor:
    def __init__(self,existing=None,period_existing=None,fail=False,persisted=(1,Decimal("10"))): self.existing=existing; self.period_existing=period_existing; self.fail=fail; self.persisted=persisted; self.last=""; self.calls=[]; self.rowcount=1
    def execute(self,sql,params):
        self.last=sql; self.calls.append((sql,params))
        if self.fail and "UPDATE tax_revenue_import_runs" in sql: raise RuntimeError("failed")
    def executemany(self,sql,rows): self.calls.append((sql,rows))
    def fetchone(self):
        if "WHERE source_reference" in self.last:return self.existing
        if "WHERE source_period" in self.last:return self.period_existing
        if "SELECT COUNT(*)" in self.last:return self.persisted
        if "RETURNING run_id" in self.last:return ("run-1",)


class Connection:
    def __init__(self,cursor):self.cur=cursor;self.events=[]
    def cursor(self):return self.cur
    def commit(self):self.events.append("commit")
    def rollback(self):self.events.append("rollback")
    def close(self):self.events.append("close")


def preview():
    row=TaxRevenueEvent("e1",2026,"2026-07","REALIZATION",Decimal("10"),"r.xlsx","ref","CONFIRMED","PERIOD_ONLY","valid")
    return {"source_document":"r.xlsx","source_reference":"ref","source_checksum":"sum","source_period":"2026-07","events":[row],"accounting_income":Decimal("10")}


class RepositoryTests(unittest.TestCase):
    def test_transaction_success_and_idempotent_replay(self):
        cur=Cursor();conn=Connection(cur);result=persist_import(preview(),lambda:conn)
        self.assertFalse(result["idempotent_replay"]);self.assertEqual(conn.events[-2:],["commit","close"])
        cur2=Cursor(("old","success",1,Decimal("10")));conn2=Connection(cur2);result2=persist_import(preview(),lambda:conn2)
        self.assertTrue(result2["idempotent_replay"]);self.assertFalse(any("INSERT" in c[0] for c in cur2.calls))

    def test_failure_rolls_back(self):
        cur=Cursor(fail=True);conn=Connection(cur)
        with self.assertRaises(RuntimeError):persist_import(preview(),lambda:conn)
        self.assertEqual(conn.events[-2:],["rollback","close"])

    def test_modified_workbook_for_imported_period_requires_review(self):
        cur=Cursor(period_existing=("old","old-reference"));conn=Connection(cur)
        with self.assertRaises(PersistenceError):persist_import(preview(),lambda:conn)
        self.assertFalse(any("INSERT" in call[0] for call in cur.calls))
        self.assertEqual(conn.events[-2:],["rollback","close"])

    def test_persisted_reconciliation_failure_rolls_back(self):
        cur=Cursor(persisted=(0,Decimal("0")));conn=Connection(cur)
        with self.assertRaises(PersistenceError):persist_import(preview(),lambda:conn)
        self.assertEqual(conn.events[-2:],["rollback","close"])

    def test_no_delete_or_event_update(self):
        from services.tax_engine import repository
        source=Path(repository.__file__).read_text(encoding="utf-8")
        self.assertNotIn("DELETE",source);self.assertNotIn("UPDATE tax_revenue_events",source)
