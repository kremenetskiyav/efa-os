from __future__ import annotations

import ast
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "Scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_competitor_monitor_summary_v1 as summary


SET_ID = "f269d85a-e438-5cf7-b711-de76054598b2"
REFERENCE_AT = datetime(2026, 8, 26, 6, 14, 43, tzinfo=timezone.utc)
GENERATED_AT = datetime(2026, 8, 27, 6, 14, 43, tzinfo=timezone.utc)


def manifest(expected: int = 10) -> dict[str, object]:
    return {
        "finding_set_id": SET_ID,
        "set_key": "cm-finding-set-v1:" + "a" * 64,
        "persistence_contract_version": "competitor-finding-persistence.v1",
        "finding_set_contract_version": "competitor_finding_set.v1",
        "source_analysis_contract_version": "competitor_snapshot_analysis.v1",
        "source_findings_sha256": "1" * 64,
        "source_findings_semantic_sha256": "2" * 64,
        "source_analysis_sha256": "3" * 64,
        "previous_source_kind": "BASELINE_V1",
        "previous_derived_batch_id": "previous-batch",
        "previous_reference_at": datetime(2026, 8, 25, 18, 22, tzinfo=timezone.utc),
        "previous_captured_through": datetime(2026, 8, 25, 18, 24, tzinfo=timezone.utc),
        "current_source_kind": "SNAPSHOT_V1",
        "current_derived_batch_id": "current-batch",
        "current_reference_at": REFERENCE_AT,
        "current_captured_through": datetime(2026, 8, 26, 6, 16, tzinfo=timezone.utc),
        "expected_findings_count": expected,
        "applied_at": datetime(2026, 8, 27, tzinfo=timezone.utc),
    }


def contexts(*rows: tuple[str, str, str]) -> list[dict[str, object]]:
    return [
        {
            "query_text_exact": query,
            "visibility_transition": transition,
            "current_status": current_status,
        }
        for query, transition, current_status in rows
    ]


def finding(
    key: str,
    topic: str,
    severity: str,
    membership: str,
    offer_id: str,
    *,
    query_context: list[dict[str, object]] | None = None,
    previous_value: object = None,
    current_value: object = None,
    delta: object = None,
    delta_pct: object = None,
) -> dict[str, object]:
    return {
        "finding_id": "id-" + key,
        "finding_set_id": SET_ID,
        "finding_kind": "ISSUE" if severity in {"WATCH", "IMPORTANT"} else "SIGNAL",
        "offer_id": offer_id,
        "product_family_id": "family-" + key,
        "listing_id": "listing-" + key,
        "old_observation_id": None,
        "new_observation_id": None,
        "topic": topic,
        "metric": "bank_price" if "PRICE" in topic else "search_visibility",
        "severity": severity,
        "confidence": "MEDIUM",
        "status": "PROPOSED",
        "evidence": [],
        "details": {
            "finding_type": topic,
            "membership_status": membership,
            "ozon_product_id": "100" + key,
            "query_context": query_context or [],
            "previous_value": previous_value,
            "current_value": current_value,
            "delta": delta,
            "delta_pct": delta_pct,
        },
        "finding_key": "cm-finding-v1:" + key,
    }


def ten_findings() -> tuple[dict[str, object], ...]:
    return (
        finding(
            "01",
            "OWN_SEARCH_VISIBILITY_LOST",
            "WATCH",
            "CONTROL",
            "УФ 005Б",
            query_context=contexts(
                ("647941", "DROPPED_OUT", "NOT_FOUND_WITHIN_SCAN_LIMIT"),
                ("647975", "STILL_VISIBLE", "FOUND"),
                ("6479C2", "STILL_NOT_FOUND", "NOT_FOUND_WITHIN_SCAN_LIMIT"),
            ),
        ),
        finding(
            "02",
            "OWN_SEARCH_VISIBILITY_RESTORED",
            "INFO",
            "CONTROL",
            "УФ 004Б",
            query_context=contexts(
                ("5Q0819653", "STILL_VISIBLE", "FOUND"),
                ("5Q0819669", "APPEARED", "FOUND"),
            ),
        ),
        finding("03", "COMPETITOR_VISIBILITY_LOST", "INFO", "PRIMARY", "УФ 001Б", query_context=contexts(("80292SLJ013", "DROPPED_OUT", "NOT_FOUND_WITHIN_SCAN_LIMIT"))),
        finding("04", "COMPETITOR_VISIBILITY_LOST", "INFO", "RESERVE", "УФ 001Б", query_context=contexts(("80292SLJ013", "DROPPED_OUT", "NOT_FOUND_WITHIN_SCAN_LIMIT"))),
        finding("05", "COMPETITOR_VISIBILITY_LOST", "INFO", "PRIMARY", "УФ 004Б", query_context=contexts(("5Q0819644A", "DROPPED_OUT", "NOT_FOUND_WITHIN_SCAN_LIMIT"))),
        finding("06", "COMPETITOR_VISIBILITY_LOST", "INFO", "RESERVE", "УФ 005Б", query_context=contexts(("647975", "DROPPED_OUT", "NOT_FOUND_WITHIN_SCAN_LIMIT"))),
        finding("07", "COMPETITOR_VISIBILITY_RESTORED", "INFO", "PRIMARY", "УФ 001Б", query_context=contexts(("80292SLJ013", "APPEARED", "FOUND"))),
        finding("08", "COMPETITOR_VISIBILITY_RESTORED", "INFO", "PRIMARY", "УФ 001Б", query_context=contexts(("80292SLJ013", "APPEARED", "FOUND"))),
        finding("09", "COMPETITOR_VISIBILITY_RESTORED", "INFO", "PRIMARY", "УФ 002Б", query_context=contexts(("6R0820367", "APPEARED", "FOUND"))),
        finding(
            "10",
            "COMPETITOR_PRICE_INCREASED",
            "INFO",
            "RESERVE",
            "УФ 005Б",
            query_context=contexts(("647941", "STILL_VISIBLE", "FOUND")),
            previous_value={"amount": 689, "currency": "RUB"},
            current_value={"amount": 698, "currency": "RUB"},
            delta=9,
            delta_pct=1.3062,
        ),
    )


def coverage() -> tuple[dict[str, object], ...]:
    return (
        {"offer_id": "УФ 001Б", "watchlist_state": "ACTIVE", "source_reason": None, "active_monitored": True},
        {"offer_id": "УФ 002Б", "watchlist_state": "ACTIVE", "source_reason": None, "active_monitored": True},
        {"offer_id": "УФ 003Б", "watchlist_state": "HOLD", "source_reason": None, "active_monitored": False},
        {"offer_id": "УФ 004Б", "watchlist_state": "ACTIVE", "source_reason": None, "active_monitored": True},
        {"offer_id": "УФ 005Б", "watchlist_state": "ACTIVE", "source_reason": None, "active_monitored": True},
    )


def source(
    *,
    source_manifest: dict[str, object] | None = None,
    source_findings: tuple[dict[str, object], ...] | None = None,
    source_coverage: tuple[dict[str, object], ...] | None = None,
) -> summary.SourceData:
    return summary.SourceData(
        manifest() if source_manifest is None else source_manifest,
        ten_findings() if source_findings is None else source_findings,
        coverage() if source_coverage is None else source_coverage,
    )


def build(value: summary.SourceData | None = None, **kwargs: object) -> dict[str, object]:
    return summary.build_summary(value or source(), generated_at=GENERATED_AT, **kwargs)


class SummaryContractTests(unittest.TestCase):
    def test_01_latest_set_deterministic_selection(self) -> None:
        normalized = " ".join(summary.LATEST_FINDING_SET_SQL.split())
        self.assertIn("ORDER BY current_reference_at DESC, applied_at DESC, finding_set_id DESC", normalized)
        self.assertTrue(normalized.endswith("LIMIT 1"))

    def test_02_contract_version_filtering(self) -> None:
        self.assertIn("finding_set_contract_version = 'competitor_finding_set.v1'", summary.LATEST_FINDING_SET_SQL)

    def test_03_valid_ten_finding_set(self) -> None:
        result = build()
        self.assertTrue(result["available"])
        self.assertEqual(10, result["counts"]["total_findings"])

    def test_04_zero_finding_valid_set(self) -> None:
        result = build(source(source_manifest=manifest(0), source_findings=()))
        self.assertTrue(result["available"])
        self.assertEqual("NORMAL", result["status"])
        self.assertEqual(0, result["counts"]["total_findings"])

    def test_05_missing_set_degraded(self) -> None:
        result = build(summary.SourceData(None, (), coverage()))
        self.assertFalse(result["available"])
        self.assertEqual("FINDING_SET_MISSING", result["degraded_reason"])
        self.assertIsNone(result["counts"]["total_findings"])

    def test_06_expected_actual_count_mismatch_degraded(self) -> None:
        result = build(source(source_manifest=manifest(11)))
        self.assertEqual("FINDING_SET_INVALID", result["degraded_reason"])

    def test_07_duplicate_finding_key_degraded(self) -> None:
        rows = list(ten_findings())
        rows[1]["finding_key"] = rows[0]["finding_key"]
        result = build(source(source_findings=tuple(rows)))
        self.assertEqual("FINDING_SET_INVALID", result["degraded_reason"])

    def test_08_malformed_details_degraded(self) -> None:
        rows = list(ten_findings())
        rows[0]["details"] = "not-an-object"
        self.assertEqual("FINDING_SET_INVALID", build(source(source_findings=tuple(rows)))["degraded_reason"])

    def test_09_malformed_evidence_degraded(self) -> None:
        rows = list(ten_findings())
        rows[0]["evidence"] = {"not": "an-array"}
        self.assertEqual("FINDING_SET_INVALID", build(source(source_findings=tuple(rows)))["degraded_reason"])

    def test_10_info_only_status_normal(self) -> None:
        rows = (finding("a", "COMPETITOR_VISIBILITY_LOST", "INFO", "PRIMARY", "УФ 001Б"),)
        result = build(source(source_manifest=manifest(1), source_findings=rows))
        self.assertEqual("NORMAL", result["status"])

    def test_11_watch_status(self) -> None:
        self.assertEqual("WATCH", build()["status"])

    def test_12_important_status(self) -> None:
        rows = list(ten_findings())
        rows[0]["severity"] = "IMPORTANT"
        result = build(source(source_findings=tuple(rows)))
        self.assertEqual("IMPORTANT", result["status"])

    def test_13_own_findings_separated(self) -> None:
        result = build()
        self.assertEqual(2, len(result["own"]["own_findings"]))
        self.assertEqual({"Наша карточка"}, {row["role_label"] for row in result["own"]["own_findings"]})

    def test_14_competitor_findings_separated(self) -> None:
        result = build()
        self.assertEqual(7, len(result["competitors"]["findings"]))

    def test_15_primary_reserve_breakdown(self) -> None:
        competitors = build()["competitors"]
        self.assertEqual((2, 2, 3, 0), (competitors["primary_lost_count"], competitors["reserve_lost_count"], competitors["primary_restored_count"], competitors["reserve_restored_count"]))

    def test_16_price_summary(self) -> None:
        prices = build()["prices"]
        self.assertEqual((1, 1), (prices["price_changes_count"], prices["price_increased_count"]))
        self.assertEqual((689, 698, "RUB"), (prices["price_changes"][0]["previous_price"], prices["price_changes"][0]["current_price"], prices["price_changes"][0]["currency"]))

    def test_17_no_competitor_price_decrease(self) -> None:
        self.assertEqual(0, build()["prices"]["price_decreased_count"])

    def test_18_deterministic_headline(self) -> None:
        first = build()["headline"]
        shuffled = tuple(reversed(ten_findings()))
        second = build(source(source_findings=shuffled))["headline"]
        self.assertEqual(first, second)

    def test_19_own_watch_headline_priority(self) -> None:
        result = build()
        self.assertEqual("cm-finding-v1:01", result["headline"]["finding_key"])
        self.assertIn("УФ 005Б", result["headline"]["message"])

    def test_20_top_findings_severity_ordering(self) -> None:
        top = build()["top_findings"]
        self.assertEqual("WATCH", top[0]["severity"])
        self.assertEqual("Наша карточка", top[0]["role_label"])

    def test_21_top_findings_max_five(self) -> None:
        self.assertEqual(5, len(build()["top_findings"]))

    def test_22_role_labels(self) -> None:
        labels = {row["role_label"] for row in build()["top_findings"]}
        self.assertIn("Наша карточка", labels)
        self.assertTrue(labels.issubset(set(summary.ROLE_LABELS.values())))

    def test_23_safe_not_found_wording(self) -> None:
        message = build()["headline"]["message"].lower()
        self.assertIn("в пределах лимита текущего снимка", message)
        for unsafe in ("исчезла", "товар удалён", "товар недоступен", "продажи остановлены"):
            self.assertNotIn(unsafe, message)

    def test_24_query_affected_remaining_extraction(self) -> None:
        own = build()["own"]["own_findings"][0]
        self.assertEqual(["647941"], own["affected_queries"])
        self.assertEqual(["647975"], own["remaining_queries"])

    def test_25_details_ref_stable(self) -> None:
        row = build()["top_findings"][0]
        self.assertEqual("finding:" + row["finding_key"], row["details_ref"])

    def test_26_portfolio_coverage_dynamic(self) -> None:
        result = build()["coverage"]
        self.assertEqual((5, 4), (result["portfolio_sku_count"], result["active_monitored_sku_count"]))

    def test_27_hold_sku_unmonitored(self) -> None:
        items = build()["coverage"]["unmonitored_skus"]
        self.assertEqual([{"offer_id": "УФ 003Б", "watchlist_state": "HOLD", "reason": None}], items)

    def test_28_no_hardcoded_five_four_dependency(self) -> None:
        rows = coverage() + ({"offer_id": "УФ 006Б", "watchlist_state": "ACTIVE", "source_reason": None, "active_monitored": True},)
        result = build(source(source_coverage=rows))["coverage"]
        self.assertEqual((6, 5), (result["portfolio_sku_count"], result["active_monitored_sku_count"]))

    def test_29_freshness_unknown_without_policy(self) -> None:
        self.assertEqual("UNKNOWN", build()["snapshot"]["freshness_status"])

    def test_30_freshness_fresh_with_policy(self) -> None:
        result = build(freshness_threshold_seconds=90_000)
        self.assertEqual("FRESH", result["snapshot"]["freshness_status"])
        self.assertTrue(result["available"])

    def test_31_freshness_stale_with_policy(self) -> None:
        result = build(freshness_threshold_seconds=80_000)
        self.assertEqual("STALE", result["snapshot"]["freshness_status"])
        self.assertEqual("FINDING_SET_STALE", result["degraded_reason"])
        self.assertFalse(result["available"])

    def test_32_age_seconds(self) -> None:
        self.assertEqual(86_400, build()["snapshot"]["age_seconds"])

    def test_33_read_only_sql_only(self) -> None:
        for statement in (summary.LATEST_FINDING_SET_SQL, summary.FINDINGS_SQL, summary.COVERAGE_SQL):
            self.assertTrue(statement.lstrip().upper().startswith("SELECT"))

    def test_34_no_dml(self) -> None:
        sql = "\n".join((summary.LATEST_FINDING_SET_SQL, summary.FINDINGS_SQL, summary.COVERAGE_SQL)).upper()
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "ON CONFLICT"):
            self.assertNotIn(forbidden, sql)

    def test_35_source_db_unchanged(self) -> None:
        source_data = source()
        responses = [
            (list(source_data.manifest), [tuple(source_data.manifest.values())]),
            (list(source_data.findings[0]), [tuple(row.values()) for row in source_data.findings]),
            (list(source_data.coverage_rows[0]), [tuple(row.values()) for row in source_data.coverage_rows]),
        ]

        class Cursor:
            def __init__(self) -> None:
                self.description = []
                self.rows = []
                self.queries: list[str] = []
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, query, params=None):
                self.queries.append(query)
                columns, self.rows = responses[len(self.queries) - 1]
                self.description = [(name,) for name in columns]
            def fetchone(self): return self.rows[0] if self.rows else None
            def fetchall(self): return self.rows

        class Connection:
            def __init__(self) -> None:
                self.cursor_value = Cursor()
                self.readonly = False
                self.rollbacks = 0
            def set_session(self, *, readonly, autocommit): self.readonly = readonly and not autocommit
            def cursor(self): return self.cursor_value
            def rollback(self): self.rollbacks += 1

        connection = Connection()
        before = copy.deepcopy(source_data)
        actual = summary.read_source(connection)
        self.assertEqual(before, actual)
        self.assertTrue(connection.readonly)
        self.assertEqual(1, connection.rollbacks)
        self.assertEqual(3, len(connection.cursor_value.queries))

    def test_36_snapshot_unavailable(self) -> None:
        broken = manifest()
        broken["current_reference_at"] = None
        result = build(source(source_manifest=broken))
        self.assertEqual("SNAPSHOT_UNAVAILABLE", result["degraded_reason"])

    def test_37_source_compiles_as_ast(self) -> None:
        path = ROOT / "Scripts" / "build_competitor_monitor_summary_v1.py"
        ast.parse(path.read_text(encoding="utf-8"))

    def test_38_competitor_restored_wording(self) -> None:
        row = next(
            item
            for item in build()["competitors"]["findings"]
            if item["finding_type"] == "COMPETITOR_VISIBILITY_RESTORED"
        )
        self.assertIn("снова найден по OEM", row["message"])

    def test_39_runtime_sources_are_only_approved_mcp_read_views(self) -> None:
        sql = "\n".join(
            (summary.LATEST_FINDING_SET_SQL, summary.FINDINGS_SQL, summary.COVERAGE_SQL)
        )
        self.assertNotIn("public.competitor_", sql)
        self.assertIn("mcp_read.competitor_latest_finding_set", sql)
        self.assertIn("mcp_read.competitor_findings", sql)
        self.assertIn("mcp_read.competitor_monitoring_coverage", sql)

    def test_40_exactly_three_bounded_source_queries_remain(self) -> None:
        statements = (
            summary.LATEST_FINDING_SET_SQL,
            summary.FINDINGS_SQL,
            summary.COVERAGE_SQL,
        )
        self.assertEqual(3, len(statements))
        self.assertTrue(all(value.lstrip().upper().startswith("SELECT") for value in statements))


if __name__ == "__main__":
    unittest.main()
