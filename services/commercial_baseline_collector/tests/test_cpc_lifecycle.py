import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from commercial_baseline_collector.cpc_lifecycle import (
    READY_STATES,
    classify_report_state,
    is_stuck,
    prepare_action,
    prepare_lifecycle,
    register_report,
)


ROOT = Path(__file__).parents[3]


class Cursor:
    def __init__(self, existing=None, inserted=None):
        self.existing = existing
        self.inserted = inserted
        self.last_sql = ""
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params):
        self.last_sql = sql
        self.calls.append((sql, params))

    def fetchone(self):
        if "INSERT INTO cpc_collection_runs" in self.last_sql:
            return self.inserted
        if "FROM cpc_collection_runs" in self.last_sql:
            return self.existing
        return None


class Connection:
    def __init__(self, cursor):
        self.cur = cursor
        self.events = []

    def cursor(self): return self.cur
    def commit(self): self.events.append("commit")
    def rollback(self): self.events.append("rollback")
    def close(self): self.events.append("close")


def lifecycle_row(state="PENDING", report_uuid=None):
    return (
        "11111111-1111-1111-1111-111111111111",
        "cpc-day-2026-08-17",
        "2026-08-17",
        report_uuid,
        state,
        "CREATE_RESERVED" if report_uuid is None else "NOT_STARTED",
        0,
        [],
        datetime(2026, 8, 18, 6, 41, tzinfo=timezone.utc),
    )


class CpcLifecycleContractTests(unittest.TestCase):
    def test_no_existing_run_creates_exactly_one_reservation(self):
        self.assertEqual(prepare_action(None), "CREATE")
        migration = (ROOT / "database/migrations/010_cpc_async_report_lifecycle_v1.sql").read_text(encoding="utf-8")
        self.assertIn("cpc_collection_runs_business_date_uq", migration)

        inserted = lifecycle_row()
        cursor = Cursor(existing=None, inserted=inserted)
        connection = Connection(cursor)
        result = prepare_lifecycle(
            {"business_date": "2026-08-17", "collection_ref": "cpc-day-2026-08-17", "requested_at": "2026-08-18T06:30:00Z"},
            lambda: connection,
        )
        self.assertTrue(result["should_create_report"])
        self.assertEqual(sum("INSERT INTO cpc_collection_runs" in sql for sql, _ in cursor.calls), 1)

    def test_existing_pending_or_success_never_creates(self):
        self.assertEqual(prepare_action("PENDING"), "PENDING")
        self.assertEqual(prepare_action("SUCCESS_ZERO"), "SUCCESS")
        self.assertEqual(prepare_action("SUCCESS_NONZERO"), "SUCCESS")
        for state in ("PENDING", "SUCCESS_ZERO", "SUCCESS_NONZERO"):
            cursor = Cursor(existing=lifecycle_row(state=state))
            connection = Connection(cursor)
            result = prepare_lifecycle(
                {"business_date": "2026-08-17", "collection_ref": "cpc-day-2026-08-17", "requested_at": "2026-08-18T06:30:00Z"},
                lambda: connection,
            )
            self.assertFalse(result["should_create_report"])
            self.assertFalse(any("INSERT INTO cpc_collection_runs" in sql for sql, _ in cursor.calls))

    def test_same_uuid_registration_is_idempotent(self):
        report_uuid = "191827e5-2c73-429a-9ce1-34b48f560a46"
        cursor = Cursor(existing=lifecycle_row(report_uuid=report_uuid))
        connection = Connection(cursor)
        result = register_report(
            {"business_date": "2026-08-17", "report_uuid": report_uuid, "campaigns": [{"id": "1"}], "campaigns_json": "[]"},
            lambda: connection,
        )
        self.assertTrue(result["idempotent"])
        self.assertFalse(any(sql.lstrip().startswith("UPDATE") for sql, _ in cursor.calls))

    def test_pending_external_states_remain_pending(self):
        self.assertEqual(classify_report_state("NOT_STARTED"), "PENDING")
        self.assertEqual(classify_report_state("IN_PROGRESS"), "PENDING")

    def test_ready_states_are_downloadable(self):
        self.assertEqual(READY_STATES, {"OK", "COMPLETE", "COMPLETED"})
        for state in READY_STATES:
            self.assertEqual(classify_report_state(state), "READY")

    def test_terminal_state_is_failed(self):
        for state in ("FAILED", "ERROR", "EXPIRED", "CANCELLED", "unknown"):
            self.assertEqual(classify_report_state(state), "FAILED")

    def test_two_hour_threshold_marks_stuck(self):
        now = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
        self.assertFalse(is_stuck(now - timedelta(hours=1, minutes=59), now))
        self.assertTrue(is_stuck(now - timedelta(hours=2), now))

    def test_workflows_have_separate_create_and_poll_responsibilities(self):
        create = json.loads((ROOT / "n8n/workflows/CPC_Daily_Collection.json").read_text(encoding="utf-8"))[0]
        poller = json.loads((ROOT / "n8n/workflows/CPC_Report_Poller_v1.json").read_text(encoding="utf-8"))[0]
        create_types = {node["type"] for node in create["nodes"]}
        create_names = {node["name"] for node in create["nodes"]}
        poller_names = {node["name"] for node in poller["nodes"]}
        self.assertNotIn("n8n-nodes-base.wait", create_types)
        self.assertNotIn("Get CPC Report Status", create_names)
        self.assertIn("Generate CPC Daily Report", create_names)
        self.assertIn("Get CPC Report Status", poller_names)
        self.assertNotIn("Generate CPC Daily Report", poller_names)
        self.assertFalse(poller["active"])

    def test_existing_uuid_is_retained_by_migration(self):
        migration = (ROOT / "database/migrations/010_cpc_async_report_lifecycle_v1.sql").read_text(encoding="utf-8")
        self.assertGreaterEqual(migration.count("191827e5-2c73-429a-9ce1-34b48f560a46"), 2)
        self.assertIn("ON CONFLICT (business_date) DO NOTHING", migration)


if __name__ == "__main__":
    unittest.main()
