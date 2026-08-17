from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.premium_exit_baseline.checker import build_snapshot, compare_snapshots, redact, write_snapshot
from services.premium_exit_baseline.contracts import CRITICAL_CHECKS, CheckSpec, assert_read_only_contracts


def raw(check_id: str, status: int = 200, response=None, **more):
    return {"check_id": check_id, "http_status": status, "response": response if response is not None else {"result": {"data": []}}, **more}


class PremiumExitCheckerTests(unittest.TestCase):
    def test_unchanged_endpoints_are_deterministic(self):
        before = build_snapshot("BEFORE", [raw("seller_analytics")], "2026-08-17T00:00:00+00:00")
        after = build_snapshot("AFTER", [raw("seller_analytics")], "2026-08-20T00:00:00+00:00")
        comparison = compare_snapshots(before, after)
        self.assertEqual(comparison["checks"][0]["comparison"], "UNCHANGED")
        self.assertEqual(comparison["decision"], "KEEP_FREE_WITH_GAP")

    def test_missing_analytics_field_is_degraded(self):
        snapshot = build_snapshot("BEFORE", [raw("seller_analytics", response={"result": {}})])
        self.assertEqual(snapshot["checks"][0]["result"], "AVAILABLE_DEGRADED")

    def test_explicit_entitlement_denial(self):
        snapshot = build_snapshot("BEFORE", [raw("prices", 403, {}, ozon_error_message="Premium subscription access denied")])
        self.assertEqual(next(x for x in snapshot["checks"] if x["check_id"] == "prices")["result"], "ENTITLEMENT_DENIED")

    def test_401_is_auth_failed(self):
        snapshot = build_snapshot("BEFORE", [raw("prices", 401, {}, ozon_error_message="invalid credentials")])
        self.assertEqual(next(x for x in snapshot["checks"] if x["check_id"] == "prices")["result"], "AUTH_FAILED")

    def test_429_is_rate_limited(self):
        snapshot = build_snapshot("BEFORE", [raw("finance", 429, {})])
        self.assertEqual(next(x for x in snapshot["checks"] if x["check_id"] == "finance")["result"], "RATE_LIMITED")

    def test_500_is_transient(self):
        snapshot = build_snapshot("BEFORE", [raw("postings", 500, {})])
        self.assertEqual(next(x for x in snapshot["checks"] if x["check_id"] == "postings")["result"], "TRANSIENT_HTTP_FAILURE")

    def test_schema_change_is_degraded(self):
        before = build_snapshot("BEFORE", [raw("seller_analytics")])
        after = build_snapshot("AFTER", [raw("seller_analytics", response={"result": {"data": [{"changed": 1}]}})])
        self.assertEqual(compare_snapshots(before, after)["checks"][0]["comparison"], "DEGRADED")

    def test_partial_degradation_decision(self):
        before = build_snapshot("BEFORE", [raw("prices", response={"items": []})])
        after = build_snapshot("AFTER", [raw("prices", response={})])
        self.assertEqual(compare_snapshots(before, after)["decision"], "KEEP_FREE_WITH_GAP")

    def test_secret_redaction_and_evidence(self):
        snapshot = build_snapshot("BEFORE", [raw("finance", 400, {}, ozon_error_message="Authorization: Bearer abcdefghijklmnopqrstuvwxyz")])
        with tempfile.TemporaryDirectory() as directory:
            path = write_snapshot(snapshot, directory)
            text = path.read_text(encoding="utf-8")
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", text)
        self.assertIn("[REDACTED]", text)
        self.assertEqual(redact({"access_token": "x"}), {})

    def test_before_after_phase_protection(self):
        snapshot = build_snapshot("BEFORE", [])
        with self.assertRaises(ValueError):
            compare_snapshots(snapshot, snapshot)

    def test_comparison_is_deterministic(self):
        before = build_snapshot("BEFORE", [raw("prices", response={"items": []})])
        after = build_snapshot("AFTER", [raw("prices", response={"items": []})])
        self.assertEqual(compare_snapshots(before, after), compare_snapshots(before, after))

    def test_write_endpoint_blacklist(self):
        with self.assertRaises(ValueError):
            assert_read_only_contracts((CheckSpec("bad", "SELLER", "DELETE", "/v1/actions", (), ()),))
        self.assertEqual(len(CRITICAL_CHECKS), 8)
