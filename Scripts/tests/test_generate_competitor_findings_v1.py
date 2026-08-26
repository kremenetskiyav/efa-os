from __future__ import annotations

import copy
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "Scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_competitor_findings_v1 as engine  # noqa: E402


SOURCE_HASH = "a" * 64


def comparison(
    *,
    query: str = "OEM-A",
    product: str = "100",
    membership: str = "PRIMARY",
    previous_status: str = "FOUND",
    current_status: str = "FOUND",
    visibility: str = "STILL_VISIBLE",
    previous_rank: int | None = 10,
    current_rank: int | None = 10,
    bank_previous: int | float | None = 100,
    bank_current: int | float | None = 100,
    other_previous: int | float | None = 110,
    other_current: int | float | None = 110,
    bank_direction: str = "UNCHANGED",
    reviews_delta: int | None = 0,
    product_fact_drift: bool = False,
    slot_classification: str = "CONTINUING_SLOT",
) -> dict:
    rank_delta = None
    if previous_rank is not None and current_rank is not None and visibility == "STILL_VISIBLE":
        rank_delta = current_rank - previous_rank
    bank_delta = None
    bank_pct = None
    if bank_previous is not None and bank_current is not None and visibility == "STILL_VISIBLE":
        bank_delta = bank_current - bank_previous
        if bank_previous > 0:
            bank_pct = bank_delta / bank_previous * 100
    return {
        "offer_id": "УФ 001Б",
        "query_text_exact": query,
        "ozon_product_id": product,
        "slot_classification": slot_classification,
        "membership_status": membership,
        "previous_status": previous_status,
        "current_status": current_status,
        "visibility_transition": visibility,
        "previous_rank": previous_rank,
        "current_rank": current_rank,
        "rank_delta": rank_delta,
        "rank_direction": "NOT_COMPARABLE" if rank_delta is None else "IMPROVED" if rank_delta < 0 else "WORSENED" if rank_delta > 0 else "UNCHANGED",
        "previous_bank_price": bank_previous,
        "current_bank_price": bank_current,
        "bank_price_delta": bank_delta,
        "bank_price_delta_pct": bank_pct,
        "bank_price_direction": bank_direction if visibility == "STILL_VISIBLE" else "NOT_COMPARABLE",
        "previous_other_payment_price": other_previous,
        "current_other_payment_price": other_current,
        "other_payment_price_delta": None if visibility != "STILL_VISIBLE" or other_previous is None or other_current is None else other_current - other_previous,
        "other_payment_price_delta_pct": None,
        "other_payment_price_direction": "NOT_COMPARABLE" if visibility != "STILL_VISIBLE" else "UNCHANGED" if other_previous == other_current else "INCREASED" if other_current > other_previous else "DECREASED",
        "previous_old_price": 120 if visibility == "STILL_VISIBLE" else None,
        "current_old_price": 120 if visibility == "STILL_VISIBLE" else None,
        "previous_reviews_count_observed": 10 if previous_status == "FOUND" else None,
        "current_reviews_count_observed": None if current_status != "FOUND" else 10 + (reviews_delta or 0),
        "reviews_delta": reviews_delta if visibility == "STILL_VISIBLE" else None,
        "reviews_direction": "INCREASED" if reviews_delta and reviews_delta > 0 else "UNCHANGED" if visibility == "STILL_VISIBLE" else "NOT_COMPARABLE",
        "product_fact_drift": product_fact_drift,
        "product_fact_changes": [{"field": "observed_length_mm", "previous": 1, "current": None}] if product_fact_drift else [],
        "comparison_quality": "VALID" if visibility == "STILL_VISIBLE" else "VISIBILITY_ONLY",
    }


def analysis(rows: list[dict]) -> dict:
    return {
        "contract_version": "competitor_snapshot_analysis.v1",
        "previous_snapshot": {
            "source_kind": "BASELINE_V1",
            "derived_batch_id": "previous-batch",
            "reference_at": "2026-08-25T00:00:00.000Z",
            "captured_through": "2026-08-25T00:01:00.000Z",
            "region_key": "REGION",
            "search_runs": 9,
            "observations": len(rows),
        },
        "current_snapshot": {
            "source_kind": "SNAPSHOT_V1",
            "derived_batch_id": "current-batch",
            "reference_at": "2026-08-26T00:00:00.000Z",
            "captured_through": "2026-08-26T00:01:00.000Z",
            "region_key": "REGION",
            "search_runs": 9,
            "observations": len(rows),
        },
        "summary": {"slots_total": len(rows)},
        "comparisons": rows,
    }


def evidence_row(row: dict, side: str, index: int, observation_id: str | None = None) -> dict:
    return {
        "offer_id": row["offer_id"],
        "query_text_exact": row["query_text_exact"],
        "ozon_product_id": row["ozon_product_id"],
        "observation_id": observation_id or f"{side}-observation-{index}",
        "observation_ref": f"{side}-ref-{index}",
        "listing_id": f"listing-{row['ozon_product_id']}",
        "membership_status": row["membership_status"],
        "currency": "RUB",
        "reviews_scope": "UNKNOWN",
        "quality_status": "VALID" if row[f"{side}_status"] == "FOUND" else "NOT_FOUND",
        "quality_flags": [],
        "source_ref": f"{side}-source-{index}",
        "raw_ref": f"{side}-raw-{index}",
        "raw_source_ref": f"{side}-run-raw-{index}",
    }


def evidence_rows(a: dict) -> tuple[list[dict], list[dict]]:
    previous: list[dict] = []
    current: list[dict] = []
    for index, row in enumerate(a["comparisons"]):
        if row["slot_classification"] != "NEW_SLOT":
            previous.append(evidence_row(row, "previous", index))
        if row["slot_classification"] != "RETIRED_SLOT":
            current.append(evidence_row(row, "current", index))
    return previous, current


def generate(rows: list[dict]) -> dict:
    source = analysis(rows)
    previous, current = evidence_rows(source)
    index = engine.build_evidence_index(source, previous, current)
    return engine.generate_finding_set(source, SOURCE_HASH, index)


def findings_of(report: dict, finding_type: str) -> list[dict]:
    return [row for row in report["findings"] if row["finding_type"] == finding_type]


class VisibilityRuleTests(unittest.TestCase):
    def test_01_competitor_listing_lost_across_all_queries(self) -> None:
        rows = [
            comparison(query="OEM-A", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
            comparison(query="OEM-B", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
        ]
        report = generate(rows)
        found = findings_of(report, "COMPETITOR_VISIBILITY_LOST")
        self.assertEqual(1, len(found))
        self.assertEqual(2, len(found[0]["query_context"]))

    def test_02_partial_competitor_query_loss_suppressed(self) -> None:
        rows = [
            comparison(query="OEM-A", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
            comparison(query="OEM-B"),
        ]
        report = generate(rows)
        self.assertFalse(findings_of(report, "COMPETITOR_VISIBILITY_LOST"))
        self.assertEqual("COMPETITOR_LISTING_STILL_VISIBLE_IN_OTHER_QUERY", report["suppressed_events"][0]["reason"])

    def test_03_competitor_restored(self) -> None:
        rows = [comparison(previous_status="NOT_FOUND_WITHIN_SCAN_LIMIT", previous_rank=None, visibility="REAPPEARED")]
        self.assertEqual(1, len(findings_of(generate(rows), "COMPETITOR_VISIBILITY_RESTORED")))

    def test_04_query_swap_suppressed(self) -> None:
        rows = [
            comparison(query="OEM-A", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
            comparison(query="OEM-B", previous_status="NOT_FOUND_WITHIN_SCAN_LIMIT", previous_rank=None, visibility="REAPPEARED"),
        ]
        report = generate(rows)
        self.assertFalse(report["findings"])
        self.assertEqual("COMPETITOR_QUERY_SWAP_WITHOUT_LISTING_TRANSITION", report["suppressed_events"][0]["reason"])

    def test_05_own_full_visibility_lost_important(self) -> None:
        rows = [comparison(membership="CONTROL", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None)]
        finding = findings_of(generate(rows), "OWN_SEARCH_VISIBILITY_LOST")[0]
        self.assertEqual(("IMPORTANT", "HIGH", "ISSUE"), (finding["severity"], finding["confidence"], finding["finding_kind"]))

    def test_06_own_partial_query_loss_watch(self) -> None:
        rows = [
            comparison(query="OEM-A", membership="CONTROL", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
            comparison(query="OEM-B", membership="CONTROL"),
        ]
        finding = findings_of(generate(rows), "OWN_SEARCH_VISIBILITY_LOST")[0]
        self.assertEqual(("WATCH", "MEDIUM"), (finding["severity"], finding["confidence"]))

    def test_07_own_restored_info(self) -> None:
        rows = [comparison(membership="CONTROL", previous_status="NOT_FOUND_WITHIN_SCAN_LIMIT", previous_rank=None, visibility="REAPPEARED")]
        finding = findings_of(generate(rows), "OWN_SEARCH_VISIBILITY_RESTORED")[0]
        self.assertEqual(("INFO", "HIGH"), (finding["severity"], finding["confidence"]))


class PriceAndScopeTests(unittest.TestCase):
    def test_08_price_increase(self) -> None:
        row = comparison(bank_previous=100, bank_current=110, other_previous=120, other_current=130, bank_direction="INCREASED")
        finding = findings_of(generate([row]), "COMPETITOR_PRICE_INCREASED")[0]
        self.assertEqual((10, 10, "HIGH"), (finding["delta"], finding["delta_pct"], finding["confidence"]))

    def test_09_price_decrease(self) -> None:
        row = comparison(bank_previous=100, bank_current=90, other_previous=120, other_current=110, bank_direction="DECREASED")
        finding = findings_of(generate([row]), "COMPETITOR_PRICE_DECREASED")[0]
        self.assertEqual((-10, -10), (finding["delta"], finding["delta_pct"]))

    def test_10_multi_query_price_dedup(self) -> None:
        rows = [
            comparison(query="OEM-A", bank_previous=100, bank_current=110, bank_direction="INCREASED"),
            comparison(query="OEM-B", bank_previous=100, bank_current=110, bank_direction="INCREASED"),
        ]
        found = findings_of(generate(rows), "COMPETITOR_PRICE_INCREASED")
        self.assertEqual(1, len(found))
        self.assertEqual(2, len(found[0]["query_context"]))

    def test_11_conflicting_query_price_suppressed(self) -> None:
        rows = [
            comparison(query="OEM-A", bank_previous=100, bank_current=110, bank_direction="INCREASED"),
            comparison(query="OEM-B", bank_previous=100, bank_current=120, bank_direction="INCREASED"),
        ]
        report = generate(rows)
        self.assertFalse(findings_of(report, "COMPETITOR_PRICE_INCREASED"))
        self.assertEqual("CONFLICTING_QUERY_BANK_PRICE_MOVEMENT", report["suppressed_events"][0]["reason"])

    def test_12_control_price_ignored(self) -> None:
        row = comparison(membership="CONTROL", bank_previous=100, bank_current=110, bank_direction="INCREASED")
        report = generate([row])
        self.assertFalse(findings_of(report, "COMPETITOR_PRICE_INCREASED"))
        self.assertEqual("CONTROL_PRICE_CHANGE_OUT_OF_SCOPE", report["suppressed_events"][0]["reason"])

    def test_13_rank_event_ignored(self) -> None:
        row = comparison(previous_rank=20, current_rank=1)
        self.assertFalse(generate([row])["findings"])

    def test_14_reviews_event_ignored(self) -> None:
        row = comparison(reviews_delta=100)
        self.assertFalse(generate([row])["findings"])

    def test_15_product_fact_drift_ignored(self) -> None:
        row = comparison(product_fact_drift=True)
        self.assertFalse(generate([row])["findings"])

    def test_16_not_found_wording_safe(self) -> None:
        row = comparison(visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None)
        summary = generate([row])["findings"][0]["summary"].lower()
        for phrase in ("listing removed", "product delisted", "product unavailable", "seller stopped selling"):
            self.assertNotIn(phrase, summary)
        self.assertIn("scan limit", summary)


class IdentityAndEvidenceTests(unittest.TestCase):
    def test_17_dedup_key_excludes_query(self) -> None:
        row = comparison(query="SECRET-OEM", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None)
        key = generate([row])["findings"][0]["dedup_key"]
        self.assertEqual("COMPETITOR_VISIBILITY_LOST|УФ 001Б|100", key)
        self.assertNotIn("SECRET-OEM", key)

    def test_18_query_context_retains_all_queries(self) -> None:
        rows = [
            comparison(query="OEM-A", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
            comparison(query="OEM-B", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
        ]
        contexts = findings_of(generate(rows), "COMPETITOR_VISIBILITY_LOST")[0]["query_context"]
        self.assertEqual(["OEM-A", "OEM-B"], [item["query_text_exact"] for item in contexts])

    def test_19_mixed_rank_direction_retained(self) -> None:
        rows = [
            comparison(query="OEM-A", previous_rank=10, current_rank=5, bank_previous=100, bank_current=110, bank_direction="INCREASED"),
            comparison(query="OEM-B", previous_rank=5, current_rank=10, bank_previous=100, bank_current=110, bank_direction="INCREASED"),
        ]
        contexts = findings_of(generate(rows), "COMPETITOR_PRICE_INCREASED")[0]["query_context"]
        self.assertEqual([-5, 5], [item["rank_delta"] for item in contexts])

    def test_20_observation_uuid_exact_resolution(self) -> None:
        source = analysis([comparison()])
        previous, current = evidence_rows(source)
        index = engine.build_evidence_index(source, previous, current)
        record = index[("УФ 001Б", "OEM-A", "100")]
        self.assertEqual(("previous-observation-0", "current-observation-0"), (record["previous"]["observation_id"], record["current"]["observation_id"]))

    def test_21_missing_uuid_resolution_fails(self) -> None:
        source = analysis([comparison()])
        previous, _ = evidence_rows(source)
        with self.assertRaises(engine.EvidenceResolutionError):
            engine.build_evidence_index(source, previous, [])

    def test_22_duplicate_uuid_resolution_fails(self) -> None:
        source = analysis([comparison(query="OEM-A", product="100"), comparison(query="OEM-B", product="200")])
        previous, current = evidence_rows(source)
        current[1]["observation_id"] = current[0]["observation_id"]
        with self.assertRaisesRegex(engine.EvidenceResolutionError, "Duplicate current observation UUID"):
            engine.build_evidence_index(source, previous, current)

    def test_23_evidence_refs_retained(self) -> None:
        row = comparison(visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None)
        finding = generate([row])["findings"][0]
        self.assertEqual("previous-raw-0", finding["evidence_refs"][0]["previous"]["raw_ref"])
        self.assertEqual("current-run-raw-0", finding["evidence_refs"][0]["current"]["raw_source_ref"])

    def test_24_summary_totals(self) -> None:
        rows = [
            comparison(product="100", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
            comparison(product="200", previous_status="NOT_FOUND_WITHIN_SCAN_LIMIT", previous_rank=None, visibility="REAPPEARED"),
        ]
        report = generate(rows)
        self.assertEqual(2, report["summary"]["findings_total"])
        self.assertEqual(2, sum(report["summary"]["by_type"].values()))
        self.assertEqual(2, sum(report["summary"]["by_severity"].values()))

    def test_25_no_duplicate_findings(self) -> None:
        rows = [
            comparison(query="OEM-A", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
            comparison(query="OEM-B", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
        ]
        report = generate(rows)
        keys = [item["dedup_key"] for item in report["findings"]]
        self.assertEqual(len(keys), len(set(keys)))


class SafetyAndContractTests(unittest.TestCase):
    @classmethod
    def source(cls) -> str:
        return (SCRIPTS / "generate_competitor_findings_v1.py").read_text(encoding="utf-8")

    def test_26_no_insert_statement(self) -> None:
        self.assertIsNone(re.search(r"\bINSERT\b", self.source(), re.I))

    def test_27_no_update_statement(self) -> None:
        self.assertIsNone(re.search(r"\bUPDATE\b", self.source(), re.I))

    def test_28_no_delete_statement(self) -> None:
        self.assertIsNone(re.search(r"\bDELETE\b", self.source(), re.I))

    def test_29_read_only_database_mode(self) -> None:
        analyzer_source = (SCRIPTS / "analyze_competitor_snapshots_v1.py").read_text(encoding="utf-8")
        self.assertIn("snapshot_analyzer.connect_database", self.source())
        self.assertIn("default_transaction_read_only=on", analyzer_source)
        self.assertNotIn("--write", self.source())

    def test_30_source_analysis_unchanged(self) -> None:
        source = analysis([comparison(visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None)])
        original = copy.deepcopy(source)
        previous, current = evidence_rows(source)
        index = engine.build_evidence_index(source, previous, current)
        engine.generate_finding_set(source, SOURCE_HASH, index)
        self.assertEqual(original, source)

    def test_31_competitor_lost_deduplicates_queries(self) -> None:
        rows = [
            comparison(query="A", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
            comparison(query="B", visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None),
            comparison(query="C", visibility="STILL_NOT_FOUND", previous_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", previous_rank=None, current_rank=None),
        ]
        self.assertEqual(1, len(findings_of(generate(rows), "COMPETITOR_VISIBILITY_LOST")))

    def test_32_previous_zero_price_is_ignored(self) -> None:
        row = comparison(bank_previous=0, bank_current=10, bank_direction="INCREASED")
        self.assertFalse(generate([row])["findings"])

    def test_33_low_confidence_is_never_emitted(self) -> None:
        report = generate([comparison(visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None)])
        self.assertNotIn("LOW", {item["confidence"] for item in report["findings"]})

    def test_34_status_is_proposed(self) -> None:
        report = generate([comparison(visibility="DROPPED_OUT", current_status="NOT_FOUND_WITHIN_SCAN_LIMIT", current_rank=None)])
        self.assertEqual({"PROPOSED"}, {item["status"] for item in report["findings"]})

    def test_35_output_contract(self) -> None:
        report = generate([comparison()])
        self.assertEqual("competitor_finding_set.v1", report["contract_version"])
        self.assertEqual("competitor_snapshot_analysis.v1", report["source_analysis_contract"])

    def test_36_no_collector_dependency(self) -> None:
        self.assertNotIn("competitor_collector", self.source())

    def test_37_no_on_conflict(self) -> None:
        self.assertNotIn("ON CONFLICT", self.source().upper())


if __name__ == "__main__":
    unittest.main()
