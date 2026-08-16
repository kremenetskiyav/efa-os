from __future__ import annotations

from typing import Any, Callable


class PersistenceError(RuntimeError):
    pass


def persist_import(preview: dict[str, Any], connection_factory: Callable[[], Any]) -> dict[str, Any]:
    connection = connection_factory()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT run_id,status,events_count,accounting_income FROM tax_revenue_import_runs WHERE source_reference=%s", (preview["source_reference"],))
        existing = cursor.fetchone()
        if existing is not None:
            if existing[1] != "success":
                raise PersistenceError("source_reference belongs to incomplete import")
            connection.rollback()
            return {"run_id":existing[0],"idempotent_replay":True,"events_count":existing[2],"accounting_income":existing[3]}
        cursor.execute("SELECT run_id,source_reference FROM tax_revenue_import_runs WHERE source_period=%s", (preview["source_period"],))
        conflicting_period = cursor.fetchone()
        if conflicting_period is not None:
            raise PersistenceError("source period already belongs to a different workbook; explicit review required")
        cursor.execute("""INSERT INTO tax_revenue_import_runs
            (source_document,source_reference,source_checksum,source_period,status,events_count,accounting_income,data_quality_status)
            VALUES (%s,%s,%s,%s,'running',%s,%s,%s) RETURNING run_id""",
            (preview["source_document"],preview["source_reference"],preview["source_checksum"],preview["source_period"],
             len(preview["events"]),preview["accounting_income"],
             "partial" if any(e.data_quality_status == "partial" for e in preview["events"]) else "valid"))
        run_id = cursor.fetchone()[0]
        rows = [(e.event_id,run_id,e.tax_year,e.source_period,e.event_type,e.posting_number,e.offer_id,e.sku,
                 e.event_date,e.amount,e.source_document,e.source_reference,e.tax_semantics_status,e.tax_date_status,
                 e.data_quality_status) for e in preview["events"]]
        cursor.executemany("""INSERT INTO tax_revenue_events
            (event_id,run_id,tax_year,source_period,event_type,posting_number,offer_id,sku,event_date,amount,
             source_document,source_reference,tax_semantics_status,tax_date_status,data_quality_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", rows)
        cursor.execute("SELECT COUNT(*),COALESCE(SUM(amount),0) FROM tax_revenue_events WHERE run_id=%s", (run_id,))
        persisted_count, persisted_income = cursor.fetchone()
        if persisted_count != len(rows) or persisted_income != preview["accounting_income"]:
            raise PersistenceError("persisted tax events do not reconcile with validated preview")
        cursor.execute("UPDATE tax_revenue_import_runs SET status='success' WHERE run_id=%s AND status='running'", (run_id,))
        if cursor.rowcount != 1:
            raise PersistenceError("tax import lifecycle update failed")
        connection.commit()
        return {"run_id":run_id,"idempotent_replay":False,"events_count":len(rows),"accounting_income":preview["accounting_income"]}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
