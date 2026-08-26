from __future__ import annotations

import copy
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "Scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analyze_competitor_snapshots_v1 as analyzer  # noqa: E402


UTC = timezone.utc
T0 = datetime(2026, 8, 25, 18, 22, 30, tzinfo=UTC)
T1 = datetime(2026, 8, 26, 6, 14, 43, tzinfo=UTC)


def observation(
    *,
    offer_id: str = "УФ 001Б",
    query: str = "80292SLJ013",
    product_id: str = "100",
    status: str = "FOUND",
    rank: int | None = 10,
    bank_price: object = 900,
    other_price: object = 950,
    old_price: object = 1000,
    rating: object = 4.5,
    reviews: int | None = 10,
    purchase_count: int | None = 5,
    purchase_raw: str | None = "Купили 5 раз",
    availability: str = "AVAILABLE",
    membership: str = "PRIMARY",
    captured_at: datetime = T0,
    run_no: int = 0,
    source_kind: str = "BASELINE_V1",
) -> dict:
    found = status == "FOUND"
    prefix = "cm-baseline-v1:run:" if source_kind == "BASELINE_V1" else "cm-snapshot-v1:run:"
    return {
        "search_run_id": f"run-{source_kind}-{run_no}",
        "offer_id": offer_id,
        "query_text_exact": query,
        "region_key": "OZON_RU:DISPLAY:TEST",
        "location_label": "Test",
        "run_captured_at": captured_at,
        "run_status": "SUCCESS",
        "collection_ref": f"{prefix}{run_no:064x}",
        "observation_id": f"obs-{source_kind}-{run_no}-{product_id}",
        "ozon_product_id": product_id,
        "membership_status": membership,
        "captured_at": captured_at,
        "enrichment_captured_at": captured_at + timedelta(minutes=1) if found else None,
        "page_number": 1 if found else None,
        "position_on_page": rank if found else None,
        "rank": rank if found else None,
        "ad_flag": False if found else None,
        "bank_price": Decimal(str(bank_price)) if found and bank_price is not None else None,
        "other_payment_price": Decimal(str(other_price)) if found and other_price is not None else None,
        "old_price": Decimal(str(old_price)) if found and old_price is not None else None,
        "currency": "RUB" if found else None,
        "rating": Decimal(str(rating)) if found and rating is not None else None,
        "reviews_count_observed": reviews if found else None,
        "reviews_scope": "UNKNOWN",
        "purchase_count_observed": purchase_count if found else None,
        "purchase_indicator_raw": purchase_raw if found else None,
        "availability_status": availability if found else "UNKNOWN",
        "availability_raw": availability if found else None,
        "observed_oem_raw": query if found else None,
        "observed_dimensions_raw": "100x100x10" if found else None,
        "observed_length_mm": Decimal("100") if found else None,
        "observed_width_mm": Decimal("100") if found else None,
        "observed_height_mm": Decimal("10") if found else None,
        "carbon_claim_raw": "carbon" if found else None,
        "origin_raw": "RU" if found else None,
        "quality_status": "VALID" if found else "NOT_FOUND",
        "quality_flags": [] if found else ["NOT_FOUND_WITHIN_SCAN_LIMIT"],
    }


def pair(previous: dict | None, current: dict | None) -> dict:
    source = current or previous
    return analyzer.compare_slot(
        (source["offer_id"], source["query_text_exact"], source["ozon_product_id"]),
        previous,
        current,
    )


def snapshot(rows: list[dict], kind: str, reference: datetime) -> analyzer.SnapshotBatch:
    run_ids = tuple(dict.fromkeys(row["search_run_id"] for row in rows))
    refs = tuple(dict.fromkeys(row["collection_ref"] for row in rows))
    return analyzer.SnapshotBatch(
        source_kind=kind,
        derived_batch_id=f"derived-{kind}",
        reference_at=reference,
        captured_through=reference + timedelta(minutes=1),
        region_key="OZON_RU:DISPLAY:TEST",
        run_ids=run_ids,
        collection_refs=refs,
        rows=tuple(rows),
    )


class DeltaTests(unittest.TestCase):
    def test_01_found_to_found_rank_improved(self) -> None:
        result = pair(observation(rank=10), observation(rank=5, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual((-5, "IMPROVED"), (result["rank_delta"], result["rank_direction"]))

    def test_02_rank_worsened(self) -> None:
        result = pair(observation(rank=5), observation(rank=10, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual((5, "WORSENED"), (result["rank_delta"], result["rank_direction"]))

    def test_03_rank_unchanged(self) -> None:
        result = pair(observation(rank=5), observation(rank=5, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual((0, "UNCHANGED"), (result["rank_delta"], result["rank_direction"]))

    def test_04_found_to_not_found(self) -> None:
        result = pair(observation(), observation(status="NOT_FOUND", captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual("DROPPED_OUT", result["visibility_transition"])

    def test_05_not_found_to_found(self) -> None:
        result = pair(observation(status="NOT_FOUND"), observation(captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual("REAPPEARED", result["visibility_transition"])

    def test_06_not_found_to_not_found(self) -> None:
        result = pair(observation(status="NOT_FOUND"), observation(status="NOT_FOUND", captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual("STILL_NOT_FOUND", result["visibility_transition"])

    def test_07_no_synthetic_rank(self) -> None:
        result = pair(observation(rank=10), observation(status="NOT_FOUND", captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertIsNone(result["current_rank"])
        self.assertIsNone(result["rank_delta"])

    def test_08_bank_price_increase(self) -> None:
        result = pair(observation(bank_price=100), observation(bank_price=120, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual((20, "INCREASED"), (result["bank_price_delta"], result["bank_price_direction"]))

    def test_09_bank_price_decrease(self) -> None:
        result = pair(observation(bank_price=120), observation(bank_price=100, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual((-20, "DECREASED"), (result["bank_price_delta"], result["bank_price_direction"]))

    def test_10_bank_price_unchanged(self) -> None:
        result = pair(observation(bank_price=100), observation(bank_price=100, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual("UNCHANGED", result["bank_price_direction"])

    def test_11_percent_price_delta(self) -> None:
        result = pair(observation(bank_price=100), observation(bank_price=110, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual(10, result["bank_price_delta_pct"])

    def test_12_previous_zero_is_safe(self) -> None:
        result = pair(observation(bank_price=0), observation(bank_price=10, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertIsNone(result["bank_price_delta_pct"])
        self.assertEqual("INCREASED", result["bank_price_direction"])

    def test_13_old_price_null_is_not_zero(self) -> None:
        result = pair(observation(old_price=None), observation(old_price=100, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertIsNone(result["old_price_delta"])
        self.assertEqual("NOT_COMPARABLE", result["old_price_direction"])

    def test_14_rating_delta(self) -> None:
        result = pair(observation(rating=4.4), observation(rating=4.5, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertAlmostEqual(0.1, result["rating_delta"])

    def test_15_reviews_delta(self) -> None:
        result = pair(observation(reviews=10), observation(reviews=12, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual((2, "INCREASED"), (result["reviews_delta"], result["reviews_direction"]))

    def test_16_reviews_null_is_safe(self) -> None:
        result = pair(observation(reviews=None), observation(reviews=12, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual("NOT_COMPARABLE", result["reviews_direction"])

    def test_17_availability_transition(self) -> None:
        result = pair(observation(availability="AVAILABLE"), observation(availability="UNAVAILABLE", captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual("BECAME_UNAVAILABLE", result["availability_transition"])

    def test_18_not_found_is_not_unavailable(self) -> None:
        result = pair(observation(), observation(status="NOT_FOUND", captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual("UNKNOWN", result["availability_transition"])

    def test_19_product_fact_drift(self) -> None:
        before = observation()
        after = observation(captured_at=T1, source_kind="SNAPSHOT_V1")
        after["origin_raw"] = "CN"
        result = pair(before, after)
        self.assertTrue(result["product_fact_drift"])
        self.assertEqual("origin_raw", result["product_fact_changes"][0]["field"])

    def test_20_comparison_quality(self) -> None:
        valid = pair(observation(), observation(captured_at=T1, source_kind="SNAPSHOT_V1"))
        visibility = pair(observation(), observation(status="NOT_FOUND", captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual(("VALID", "VISIBILITY_ONLY"), (valid["comparison_quality"], visibility["comparison_quality"]))

    def test_21_purchase_numeric_delta(self) -> None:
        result = pair(observation(purchase_count=5), observation(purchase_count=8, captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual((3, "INCREASED"), (result["purchase_indicator"]["delta"], result["purchase_indicator"]["classification"]))

    def test_22_purchase_raw_changed_without_numeric_delta(self) -> None:
        result = pair(observation(purchase_count=None, purchase_raw="A"), observation(purchase_count=None, purchase_raw="B", captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual("RAW_CHANGED", result["purchase_indicator"]["classification"])


class ReconciliationTests(unittest.TestCase):
    def test_23_slot_intersection(self) -> None:
        before = observation()
        after = observation(captured_at=T1, source_kind="SNAPSHOT_V1")
        report = analyzer.build_analysis(snapshot([before], "BASELINE_V1", T0), snapshot([after], "SNAPSHOT_V1", T1), {"search_runs": 2, "observations": 2, "reviews": 0, "findings": 0})
        self.assertEqual((1, 0, 0), (report["summary"]["continuing_slots"], report["summary"]["new_slots"], report["summary"]["retired_slots"]))

    def test_24_new_slot(self) -> None:
        current = observation(product_id="200", captured_at=T1, source_kind="SNAPSHOT_V1")
        report = analyzer.build_analysis(snapshot([], "BASELINE_V1", T0), snapshot([current], "SNAPSHOT_V1", T1), {})
        self.assertEqual("NEW_SLOT", report["comparisons"][0]["slot_classification"])

    def test_25_retired_slot(self) -> None:
        previous = observation(product_id="200")
        report = analyzer.build_analysis(snapshot([previous], "BASELINE_V1", T0), snapshot([], "SNAPSHOT_V1", T1), {})
        self.assertEqual("RETIRED_SLOT", report["comparisons"][0]["slot_classification"])

    def test_26_duplicate_slot_rejected(self) -> None:
        first = observation()
        duplicate = copy.deepcopy(first)
        duplicate["observation_id"] = "other"
        with self.assertRaisesRegex(analyzer.DataContractError, "Duplicate logical"):
            analyzer.build_analysis(snapshot([first, duplicate], "BASELINE_V1", T0), snapshot([], "SNAPSHOT_V1", T1), {})

    def test_27_control_membership_preserved(self) -> None:
        result = pair(observation(membership="CONTROL"), observation(membership="CONTROL", captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertEqual("CONTROL", result["membership_status"])

    def test_28_per_sku_aggregation(self) -> None:
        before = [observation(offer_id="УФ 001Б", product_id="100"), observation(offer_id="УФ 002Б", query="OEM2", product_id="200", run_no=1)]
        after = [observation(offer_id="УФ 001Б", product_id="100", captured_at=T1, source_kind="SNAPSHOT_V1"), observation(offer_id="УФ 002Б", query="OEM2", product_id="200", captured_at=T1, source_kind="SNAPSHOT_V1", run_no=1)]
        report = analyzer.build_analysis(snapshot(before, "BASELINE_V1", T0), snapshot(after, "SNAPSHOT_V1", T1), {})
        self.assertEqual(1, report["per_sku_summary"]["УФ 001Б"]["slots"])
        self.assertEqual("NO_ACTIVE_MONITORING", report["per_sku_summary"]["УФ 003Б"]["status"])

    def test_29_summary_totals(self) -> None:
        before = observation()
        after = observation(captured_at=T1, source_kind="SNAPSHOT_V1")
        report = analyzer.build_analysis(snapshot([before], "BASELINE_V1", T0), snapshot([after], "SNAPSHOT_V1", T1), {})
        for name in ("visibility", "rank", "bank_price", "other_payment_price", "old_price", "rating", "reviews", "availability"):
            self.assertEqual(1, sum(report["summary"][name].values()))

    def test_30_no_comparison_price(self) -> None:
        result = pair(observation(), observation(captured_at=T1, source_kind="SNAPSHOT_V1"))
        self.assertNotIn("comparison_price", result)

    def test_31_source_rows_untouched(self) -> None:
        before = observation()
        after = observation(captured_at=T1, source_kind="SNAPSHOT_V1")
        originals = copy.deepcopy((before, after))
        analyzer.build_analysis(snapshot([before], "BASELINE_V1", T0), snapshot([after], "SNAPSHOT_V1", T1), {})
        self.assertEqual(originals, (before, after))


class BatchAndSafetyTests(unittest.TestCase):
    def history(self) -> list[dict]:
        rows = []
        offers = ("УФ 001Б", "УФ 002Б", "УФ 004Б", "УФ 005Б")
        for kind, start in (("BASELINE_V1", T0), ("SNAPSHOT_V1", T1)):
            for index in range(9):
                rows.append(observation(offer_id=offers[index % 4], query=f"OEM-{index}", product_id=str(100 + index), captured_at=start + timedelta(seconds=index), run_no=index, source_kind=kind))
        return rows

    def test_32_resolves_immediately_previous_complete_pair(self) -> None:
        previous, current = analyzer.resolve_snapshot_pair(self.history())
        self.assertEqual(("BASELINE_V1", "SNAPSHOT_V1"), (previous.source_kind, current.source_kind))
        self.assertEqual((9, 9), (len(previous.run_ids), len(current.run_ids)))

    def test_33_incomplete_batch_rejected(self) -> None:
        with self.assertRaisesRegex(analyzer.BatchResolutionError, "Incomplete"):
            analyzer.resolve_snapshot_batches(self.history()[:-1])

    def test_34_duplicate_query_in_batch_rejected(self) -> None:
        rows = self.history()
        rows[1]["offer_id"] = rows[0]["offer_id"]
        rows[1]["query_text_exact"] = rows[0]["query_text_exact"]
        with self.assertRaisesRegex(analyzer.BatchResolutionError, "not unique"):
            analyzer.resolve_snapshot_batches(rows)

    def test_35_multiple_regions_rejected(self) -> None:
        rows = self.history()
        rows[0]["region_key"] = "OTHER"
        with self.assertRaisesRegex(analyzer.BatchResolutionError, "multiple regions"):
            analyzer.resolve_snapshot_batches(rows)

    def test_36_no_mutating_sql_or_write_mode(self) -> None:
        source = (SCRIPTS / "analyze_competitor_snapshots_v1.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b(?:INSERT|UPDATE|DELETE)\b", source, re.I))
        self.assertNotIn("ON CONFLICT", source.upper())
        self.assertIn("default_transaction_read_only=on", source)
        self.assertNotIn("competitor_collector", source)

    def test_37_contract_version(self) -> None:
        before = observation()
        after = observation(captured_at=T1, source_kind="SNAPSHOT_V1")
        report = analyzer.build_analysis(snapshot([before], "BASELINE_V1", T0), snapshot([after], "SNAPSHOT_V1", T1), {})
        self.assertEqual("competitor_snapshot_analysis.v1", report["contract_version"])


if __name__ == "__main__":
    unittest.main()
