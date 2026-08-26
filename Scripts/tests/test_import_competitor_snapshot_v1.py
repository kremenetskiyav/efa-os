"""Focused tests for the evidence-gated Competitor Monitor T1+ importer."""

from __future__ import annotations

import copy
import inspect
import json
import math
import sys
import tempfile
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import import_competitor_snapshot_v1 as importer  # noqa: E402


REFERENCE_AT = "2026-08-26T07:00:00Z"
SECOND_CAPTURE = "2026-08-26T07:00:01Z"
SEARCH_PHASE_STARTED_AT = "2026-08-26T06:59:50Z"
REGION_KEY = "OZON_RU:DISPLAY:TEST"


def _enrichment_evidence(product_id: str, *, old_price: int | None) -> dict[str, object]:
    old_status = (
        "OLD_PRICE_PRESENT" if old_price is not None else "OLD_PRICE_EXPLICITLY_ABSENT"
    )
    visible = [
        {"classification": "BANK_PRICE", "parsed_numeric_value": 900, "raw_visible_text": "900 ₽"},
        {"classification": "OTHER_PAYMENT_PRICE", "parsed_numeric_value": 1000, "raw_visible_text": "1000 ₽"},
    ]
    if old_price is not None:
        visible.append(
            {"classification": "OLD_PRICE", "parsed_numeric_value": old_price, "raw_visible_text": f"{old_price} ₽"}
        )
    return {
        "evidence_key": f"enrich:{product_id}",
        "ozon_product_id": product_id,
        "captured_at": "2026-08-26T07:02:00Z",
        "source_url": f"https://www.ozon.ru/product/{product_id}/",
        "extraction_status": "COMPLETE",
        "old_price_evidence_status": old_status,
        "price_evidence": {
            "extraction_status": "COMPLETE",
            "bank_price_parsed": 900,
            "other_payment_price_parsed": 1000,
            "old_price_parsed": old_price,
            "visible_price_elements": visible,
        },
        "seller": {"raw_visible_name": f"Seller {product_id}", "seller_id_parsed": f"S{product_id}"},
        "availability": {"raw_visible_text": "В наличии", "status": "AVAILABLE"},
        "purchase_indicator": {"raw_visible_text": "Купили 10", "parsed_count": 10},
        "oem": {"raw_visible_text": "OEM"},
        "dimensions": {
            "raw_visible_text": "200x100x30 мм",
            "parsed_length_mm": 200,
            "parsed_width_mm": 100,
            "parsed_height_mm": 30,
        },
        "carbon_claim": {"raw_visible_text": "Угольный"},
        "origin": {"raw_visible_text": "Россия"},
    }


def _normalized_enrichment(source: dict[str, object]) -> dict[str, object]:
    prices = source["price_evidence"]
    assert isinstance(prices, dict)
    return {
        "raw_ref": source["evidence_key"],
        "ozon_product_id": source["ozon_product_id"],
        "captured_at": source["captured_at"],
        "source_ref": source["source_url"],
        "extraction_status": source["extraction_status"],
        "price_evidence_status": source["old_price_evidence_status"],
        "bank_price": prices["bank_price_parsed"],
        "other_payment_price": prices["other_payment_price_parsed"],
        "old_price": prices["old_price_parsed"],
        "currency": "RUB",
        "seller_name_observed": source["seller"]["raw_visible_name"],
        "seller_id_observed": source["seller"]["seller_id_parsed"],
        "availability_raw": source["availability"]["raw_visible_text"],
        "availability_status": source["availability"]["status"],
        "purchase_indicator_raw": source["purchase_indicator"]["raw_visible_text"],
        "purchase_count_observed": source["purchase_indicator"]["parsed_count"],
        "observed_oem_raw": source["oem"]["raw_visible_text"],
        "observed_dimensions_raw": source["dimensions"]["raw_visible_text"],
        "observed_length_mm": source["dimensions"]["parsed_length_mm"],
        "observed_width_mm": source["dimensions"]["parsed_width_mm"],
        "observed_height_mm": source["dimensions"]["parsed_height_mm"],
        "carbon_claim_raw": source["carbon_claim"]["raw_visible_text"],
        "origin_raw": source["origin"]["raw_visible_text"],
    }


def base_artifacts() -> tuple[dict[str, object], dict[str, object]]:
    searches = [
        {
            "evidence_key": "search:A",
            "offer_id": "УФ 001Б",
            "query_kind": "OEM",
            "query_text_exact": "OEM-A",
            "captured_at": REFERENCE_AT,
            "region_key": REGION_KEY,
            "location_label": "Test",
            "status": "SUCCESS",
            "extraction_status": "COMPLETE",
            "source_url": "https://www.ozon.ru/search/?text=OEM-A",
            "scan_limit": 1,
            "cards_scanned": 1,
            "termination_reason": "MAX_RESULTS_1",
            "ordered_cards": [
                {
                    "ozon_product_id": "100",
                    "rank": 1,
                    "ordinal": 1,
                    "rating_parsed": 4.8,
                    "reviews_count_parsed": 12,
                    "ad_marker_raw": None,
                    "price_text": "900 ₽ | 1200 ₽",
                    "availability_raw": "В наличии",
                }
            ],
        },
        {
            "evidence_key": "search:B",
            "offer_id": "УФ 002Б",
            "query_kind": "OEM",
            "query_text_exact": "OEM-B",
            "captured_at": SECOND_CAPTURE,
            "region_key": REGION_KEY,
            "location_label": "Test",
            "status": "SUCCESS",
            "extraction_status": "COMPLETE",
            "source_url": "https://www.ozon.ru/search/?text=OEM-B",
            "scan_limit": 1,
            "cards_scanned": 1,
            "termination_reason": "MAX_RESULTS_1",
            "ordered_cards": [
                {
                    "ozon_product_id": "200",
                    "rank": 1,
                    "ordinal": 1,
                    "rating_parsed": 4.5,
                    "reviews_count_parsed": 5,
                    "ad_marker_raw": "Реклама",
                    "price_text": "900 ₽ | 1000 ₽",
                    "availability_raw": "В наличии",
                }
            ],
        },
    ]
    enrichment_sources = [
        _enrichment_evidence("100", old_price=1200),
        _enrichment_evidence("200", old_price=None),
    ]
    evidence: dict[str, object] = {
        "contract_version": importer.EVIDENCE_CONTRACT,
        "mode": "SNAPSHOT",
        "batch": {
            "batch_started_at": "2026-08-26T06:59:40Z",
            "batch_finished_at": "2026-08-26T07:03:00Z",
            "search_phase_started_at": SEARCH_PHASE_STARTED_AT,
            "search_phase_finished_at": "2026-08-26T07:00:10Z",
            "enrichment_phase_started_at": "2026-08-26T07:01:50Z",
            "enrichment_phase_finished_at": "2026-08-26T07:02:10Z",
            "region_key": REGION_KEY,
            "location_label": "Test",
            "batch_status": "SUCCESS",
            "source": "SYNTHETIC_TEST",
            "collection_method": "TEST",
            "scan_limit": 1,
            "product_pages_opened": 2,
        },
        "search_evidence": searches,
        "enrichment_evidence": enrichment_sources,
    }
    runs = [
        {
            "offer_id": row["offer_id"],
            "query_kind": row["query_kind"],
            "query_text_exact": row["query_text_exact"],
            "query_normalized": row["query_text_exact"],
            "region_key": row["region_key"],
            "location_label": row["location_label"],
            "captured_at": row["captured_at"],
            "status": row["status"],
            "cards_scanned": row["cards_scanned"],
            "result_count_observed": len(row["ordered_cards"]),
            "termination_reason": row["termination_reason"],
            "source_url": row["source_url"],
            "raw_source_ref": row["evidence_key"],
        }
        for row in searches
    ]
    normalized = [_normalized_enrichment(row) for row in enrichment_sources]
    found: list[dict[str, object]] = []
    for offer, query, product, membership, enrichment, card, captured in (
        ("УФ 001Б", "OEM-A", "100", "PRIMARY", normalized[0], searches[0]["ordered_cards"][0], REFERENCE_AT),
        ("УФ 002Б", "OEM-B", "200", "RESERVE", normalized[1], searches[1]["ordered_cards"][0], SECOND_CAPTURE),
    ):
        found.append(
            {
                "offer_id": offer,
                "query_text_exact": query,
                "ozon_product_id": product,
                "membership_status": membership,
                "slot_status": "FOUND",
                "captured_at": captured,
                "enrichment_captured_at": enrichment["captured_at"],
                "rank": card["rank"],
                "page_number": 1,
                "position_on_page": card["ordinal"],
                "ad_flag": card["ad_marker_raw"] is not None,
                "rating": card["rating_parsed"],
                "reviews_count_observed": card["reviews_count_parsed"],
                "reviews_scope": "UNKNOWN",
                "bank_price": enrichment["bank_price"],
                "other_payment_price": enrichment["other_payment_price"],
                "old_price": enrichment["old_price"],
                "search_price_raw": card["price_text"],
                "search_availability_raw": card["availability_raw"],
                "purchase_count_observed": enrichment["purchase_count_observed"],
                "purchase_indicator_raw": enrichment["purchase_indicator_raw"],
                "availability_status": enrichment["availability_status"],
                "observed_oem_raw": enrichment["observed_oem_raw"],
                "observed_dimensions_raw": enrichment["observed_dimensions_raw"],
                "observed_length_mm": enrichment["observed_length_mm"],
                "observed_width_mm": enrichment["observed_width_mm"],
                "observed_height_mm": enrichment["observed_height_mm"],
                "carbon_claim_raw": enrichment["carbon_claim_raw"],
                "origin_raw": enrichment["origin_raw"],
                "seller_name_observed": enrichment["seller_name_observed"],
                "seller_id_observed": enrichment["seller_id_observed"],
                "quality_status": "VALID",
                "quality_flags": [],
                "raw_ref": enrichment["raw_ref"],
                "extraction_status": enrichment["extraction_status"],
                "price_evidence_status": enrichment["price_evidence_status"],
            }
        )
    not_found = {
        "offer_id": "УФ 001Б",
        "query_text_exact": "OEM-A",
        "ozon_product_id": "101",
        "membership_status": "CONTROL",
        "slot_status": "NOT_FOUND_WITHIN_SCAN_LIMIT",
        "captured_at": REFERENCE_AT,
        "reviews_scope": "UNKNOWN",
        "availability_status": "UNKNOWN",
        "quality_status": "NOT_FOUND",
        "quality_flags": ["NOT_FOUND_WITHIN_SCAN_LIMIT"],
    }
    for field in importer._not_found_null_fields():
        not_found[field] = None
    payload: dict[str, object] = {
        "contract_version": importer.PAYLOAD_CONTRACT,
        "mode": "SNAPSHOT",
        "batch_status": "SUCCESS",
        "batch": {**evidence["batch"], "evidence_file_sha256": "0" * 64},
        "region": {"region_key": REGION_KEY, "location_label": "Test"},
        "search_runs": runs,
        "enrichments": normalized,
        "observations": [found[0], not_found, found[1]],
        "signals": [],
        "findings": [],
    }
    return evidence, payload


def schema_fixture() -> dict[str, tuple[importer.SchemaColumn, ...]]:
    required_search = {
        "search_run_id",
        "offer_id",
        "query_kind",
        "query_text_exact",
        "query_normalized",
        "region_key",
        "captured_at",
        "status",
        "collection_ref",
    }
    required_observation = {
        "observation_id",
        "search_run_id",
        "listing_id",
        "membership_id",
        "captured_at",
        "reviews_scope",
        "availability_status",
        "quality_status",
        "quality_flags",
        "source_ref",
        "observation_ref",
    }

    def columns(names: tuple[str, ...], required: set[str]) -> tuple[importer.SchemaColumn, ...]:
        return tuple(
            importer.SchemaColumn(
                name=name,
                nullable=name not in required,
                has_default=False,
                data_type="uuid" if name in {"search_run_id", "observation_id"} else "text",
            )
            for name in names
        )

    return {
        "competitor_search_runs": columns(importer.SEARCH_INSERT_COLUMNS, required_search),
        "competitor_observations": columns(
            importer.OBSERVATION_INSERT_COLUMNS, required_observation
        ),
    }


def reference_snapshot() -> importer.ProductionSnapshot:
    reference = datetime.fromisoformat(REFERENCE_AT.replace("Z", "+00:00"))
    oems = tuple(
        importer.SkuOemReference(
            sku_oem_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"oem:{offer}:{query}")),
            offer_id=offer,
            oem_normalized=query,
            active=True,
            created_at=reference - timedelta(days=30),
        )
        for offer, query in (("УФ 001Б", "OEM-A"), ("УФ 002Б", "OEM-B"))
    )
    memberships = []
    for offer, product, status, oems_for_listing in (
        ("УФ 001Б", "100", "PRIMARY", ("OEM-A",)),
        ("УФ 001Б", "101", "CONTROL", ("OEM-A",)),
        ("УФ 002Б", "200", "RESERVE", ("OEM-B",)),
    ):
        memberships.append(
            importer.MembershipReference(
                membership_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"membership:{offer}:{product}")),
                offer_id=offer,
                membership_status=status,
                matched_oem_set=oems_for_listing,
                valid_from=reference - timedelta(days=20),
                valid_to=None,
                listing_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"listing:{offer}:{product}")),
                product_family_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"family:{offer}:{product}")),
                ozon_product_id=product,
                seller_id=f"S{product}" if product != "101" else None,
            )
        )
    return importer.ProductionSnapshot(
        profiles={"УФ 001Б": "ACTIVE", "УФ 002Б": "ACTIVE", "УФ 003Б": "HOLD"},
        oems=oems,
        memberships=tuple(memberships),
        history_counts={"search_runs": 9, "observations": 87, "reviews": 0, "findings": 0},
        search_rows=(),
        observation_rows=(),
        schema_columns=schema_fixture(),
        constraint_names=frozenset(importer.REQUIRED_CONSTRAINTS),
        index_names=frozenset(importer.REQUIRED_INDEXES),
    )


def write_artifacts(
    directory: Path,
    evidence: dict[str, object],
    payload: dict[str, object],
    *,
    update_embedded_hash: bool = True,
) -> tuple[Path, Path, str, str]:
    evidence_path = directory / "evidence.json"
    payload_path = directory / "payload.json"
    evidence_bytes = importer.canonical_json_bytes(evidence)
    evidence_hash = importer._sha256_bytes(evidence_bytes)
    if update_embedded_hash:
        payload["batch"]["evidence_file_sha256"] = evidence_hash
    payload_bytes = importer.canonical_json_bytes(payload)
    payload_hash = importer._sha256_bytes(payload_bytes)
    evidence_path.write_bytes(evidence_bytes)
    payload_path.write_bytes(payload_bytes)
    return payload_path, evidence_path, payload_hash, evidence_hash


class SnapshotImporterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.evidence, self.payload = base_artifacts()
        self.snapshot = reference_snapshot()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def load(
        self,
        evidence: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
        *,
        update_embedded_hash: bool = True,
    ) -> importer.ArtifactBundle:
        paths = write_artifacts(
            self.directory,
            copy.deepcopy(evidence or self.evidence),
            copy.deepcopy(payload or self.payload),
            update_embedded_hash=update_embedded_hash,
        )
        return importer.load_and_validate_artifacts(*paths)


class CanonicalAndReferenceTests(SnapshotImporterTestCase):
    def test_01_canonical_json_preserves_unicode(self) -> None:
        self.assertIn("УФ", importer.canonical_json_bytes({"x": "УФ"}).decode())

    def test_02_canonical_json_sorts_and_compacts(self) -> None:
        self.assertEqual(importer.canonical_json_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}')

    def test_03_canonical_json_rejects_nan(self) -> None:
        with self.assertRaises(ValueError):
            importer.canonical_json_bytes({"x": math.nan})

    def test_04_batch_ref_is_deterministic(self) -> None:
        value = importer.build_batch_ref("a" * 64, "b" * 64)
        self.assertEqual(value, importer.build_batch_ref("a" * 64, "b" * 64))

    def test_05_batch_ref_binds_both_hashes(self) -> None:
        self.assertNotEqual(
            importer.build_batch_ref("a" * 64, "b" * 64),
            importer.build_batch_ref("a" * 64, "c" * 64),
        )

    def test_06_collection_ref_is_deterministic(self) -> None:
        args = ("cm-snapshot-v1:batch:x", "УФ 001Б", "OEM", "OEM-A")
        self.assertEqual(importer.build_collection_ref(*args), importer.build_collection_ref(*args))

    def test_07_collection_ref_binds_exact_query(self) -> None:
        self.assertNotEqual(
            importer.build_collection_ref("batch", "A", "OEM", "x"),
            importer.build_collection_ref("batch", "A", "OEM", "X"),
        )

    def test_08_observation_ref_binds_product(self) -> None:
        self.assertNotEqual(
            importer.build_observation_ref("run", "1"),
            importer.build_observation_ref("run", "2"),
        )

    def test_09_uuidv5_ids_are_deterministic(self) -> None:
        ref = importer.build_collection_ref("batch", "A", "OEM", "x")
        self.assertEqual(importer.build_search_run_id(ref), importer.build_search_run_id(ref))
        self.assertEqual(uuid.UUID(importer.build_search_run_id(ref)).version, 5)

    def test_10_no_uuid4_usage(self) -> None:
        self.assertNotIn("uuid4", inspect.getsource(importer))


class ArtifactContractTests(SnapshotImporterTestCase):
    def test_11_valid_artifacts_load(self) -> None:
        self.assertEqual(self.load().reference_at.isoformat(), "2026-08-26T07:00:00+00:00")

    def test_12_evidence_hash_mismatch_rejected(self) -> None:
        paths = write_artifacts(self.directory, self.evidence, self.payload)
        with self.assertRaisesRegex(importer.ArtifactError, "Evidence SHA-256 mismatch"):
            importer.load_and_validate_artifacts(paths[0], paths[1], paths[2], "0" * 64)

    def test_13_payload_hash_mismatch_rejected(self) -> None:
        paths = write_artifacts(self.directory, self.evidence, self.payload)
        with self.assertRaisesRegex(importer.ArtifactError, "Payload SHA-256 mismatch"):
            importer.load_and_validate_artifacts(paths[0], paths[1], "0" * 64, paths[3])

    def test_14_embedded_evidence_hash_mismatch_rejected(self) -> None:
        self.payload["batch"]["evidence_file_sha256"] = "f" * 64
        with self.assertRaisesRegex(importer.ArtifactError, "Embedded evidence hash mismatch"):
            self.load(update_embedded_hash=False)

    def test_15_stored_reference_at_is_rejected_as_non_contract(self) -> None:
        self.payload["batch"]["reference_at"] = SECOND_CAPTURE
        with self.assertRaisesRegex(importer.ArtifactError, "derived"):
            self.load()

    def test_16_search_provenance_mismatch_rejected(self) -> None:
        self.payload["search_runs"][0]["source_url"] = "https://invalid.example/"
        with self.assertRaisesRegex(importer.ArtifactError, "Search evidence mismatch"):
            self.load()

    def test_17_signals_are_forbidden(self) -> None:
        self.payload["signals"] = [{"x": 1}]
        with self.assertRaisesRegex(importer.ArtifactError, "analytics"):
            self.load()

    def test_18_delta_fields_are_forbidden_recursively(self) -> None:
        self.payload["batch"]["price_delta"] = 1
        with self.assertRaisesRegex(importer.ArtifactError, "price_delta"):
            self.load()

    def test_19_ambiguous_old_price_cannot_back_found(self) -> None:
        source = self.evidence["enrichment_evidence"][0]
        source["old_price_evidence_status"] = "AMBIGUOUS_PRICE_SECTION"
        self.payload["enrichments"][0]["price_evidence_status"] = "AMBIGUOUS_PRICE_SECTION"
        with self.assertRaises(importer.ArtifactError):
            self.load()

    def test_20_explicitly_absent_old_price_is_accepted(self) -> None:
        bundle = self.load()
        self.assertIsNone(bundle.payload["enrichments"][1]["old_price"])

    def test_21_present_old_price_is_preserved(self) -> None:
        plan = importer.build_import_plan(self.load(), self.snapshot)
        self.assertEqual(plan.observation_rows[0]["old_price"], 1200)

    def test_22_found_product_must_exist_in_search_evidence(self) -> None:
        self.evidence["search_evidence"][0]["ordered_cards"] = []
        self.evidence["search_evidence"][0]["cards_scanned"] = 0
        self.payload["search_runs"][0]["cards_scanned"] = 0
        self.payload["search_runs"][0]["result_count_observed"] = 0
        with self.assertRaisesRegex(importer.ArtifactError, "absent"):
            self.load()

    def test_23_found_source_ref_must_match_enrichment(self) -> None:
        self.payload["enrichments"][0]["source_ref"] = "https://invalid.example/"
        with self.assertRaisesRegex(importer.ArtifactError, "provenance"):
            self.load()

    def test_24_not_found_contract_is_accepted(self) -> None:
        self.assertEqual(self.load().payload["observations"][1]["quality_status"], "NOT_FOUND")

    def test_25_not_found_price_must_be_null(self) -> None:
        self.payload["observations"][1]["bank_price"] = 1
        with self.assertRaisesRegex(importer.ArtifactError, "bank_price"):
            self.load()

    def test_26_not_found_ad_flag_must_be_null(self) -> None:
        self.payload["observations"][1]["ad_flag"] = False
        with self.assertRaisesRegex(importer.ArtifactError, "ad_flag"):
            self.load()

    def test_27_duplicate_logical_slot_rejected(self) -> None:
        self.payload["observations"].append(copy.deepcopy(self.payload["observations"][0]))
        with self.assertRaisesRegex(importer.ArtifactError, "Duplicate logical"):
            self.load()

    def test_28_unused_enrichment_rejected(self) -> None:
        extra = _enrichment_evidence("300", old_price=None)
        self.evidence["enrichment_evidence"].append(extra)
        self.payload["enrichments"].append(_normalized_enrichment(extra))
        with self.assertRaisesRegex(importer.ArtifactError, "must be used"):
            self.load()

    def test_29_wrong_contract_rejected(self) -> None:
        self.payload["contract_version"] = "wrong"
        with self.assertRaisesRegex(importer.ArtifactError, "contract"):
            self.load()

    def test_30_wrong_mode_rejected(self) -> None:
        self.evidence["mode"] = "BASELINE"
        with self.assertRaisesRegex(importer.ArtifactError, "SNAPSHOT"):
            self.load()

    def test_65_failed_price_section_cannot_back_found(self) -> None:
        source = self.evidence["enrichment_evidence"][0]
        source["old_price_evidence_status"] = "PRICE_SECTION_FAILED"
        self.payload["enrichments"][0]["price_evidence_status"] = "PRICE_SECTION_FAILED"
        with self.assertRaises(importer.ArtifactError):
            self.load()

    def test_66_raw_source_ref_must_resolve(self) -> None:
        self.payload["search_runs"][0]["raw_source_ref"] = "missing"
        with self.assertRaisesRegex(importer.ArtifactError, "Search evidence set mismatch"):
            self.load()

    def test_67_found_raw_ref_must_resolve(self) -> None:
        self.payload["observations"][0]["raw_ref"] = "missing"
        with self.assertRaisesRegex(importer.ArtifactError, "does not resolve"):
            self.load()

    def test_68_not_found_raw_ref_must_be_null(self) -> None:
        self.payload["observations"][1]["raw_ref"] = "enrich:100"
        with self.assertRaisesRegex(importer.ArtifactError, "raw_ref"):
            self.load()

    def test_69_found_rank_zero_is_rejected(self) -> None:
        self.payload["observations"][0]["rank"] = 0
        with self.assertRaisesRegex(importer.ArtifactError, "rank"):
            self.load()

    def test_78_found_enrichment_product_must_match(self) -> None:
        self.payload["observations"][0]["raw_ref"] = "enrich:200"
        with self.assertRaisesRegex(importer.ArtifactError, "product ID mismatch"):
            self.load()

    def test_79_reference_uses_first_actual_search_not_phase_start(self) -> None:
        bundle = self.load()
        self.assertLess(
            importer._timestamp(SEARCH_PHASE_STARTED_AT),
            bundle.reference_at,
        )
        self.assertEqual(bundle.reference_at, importer._timestamp(REFERENCE_AT))

    def test_80_shuffled_search_runs_still_use_minimum_timestamp(self) -> None:
        self.payload["search_runs"].reverse()
        bundle = self.load()
        self.assertEqual(bundle.reference_at, importer._timestamp(REFERENCE_AT))

    def test_81_batch_reference_at_is_not_required(self) -> None:
        self.assertNotIn("reference_at", self.payload["batch"])
        self.assertEqual(self.load().reference_at, importer._timestamp(REFERENCE_AT))

    def test_82_query_text_exact_is_the_only_canonical_search_field(self) -> None:
        search = self.evidence["search_evidence"][0]
        search["query"] = search.pop("query_text_exact")
        with self.assertRaisesRegex(importer.ArtifactError, "query_text_exact"):
            self.load()

    def test_83_actual_card_ordinal_and_ad_marker_map_to_observation(self) -> None:
        plan = importer.build_import_plan(self.load(), self.snapshot)
        row = next(row for row in plan.observation_rows if row["raw_ref"] == "enrich:200")
        self.assertEqual(row["position_on_page"], 1)
        self.assertTrue(row["ad_flag"])

    def test_84_top_level_signals_and_findings_are_required(self) -> None:
        del self.payload["signals"]
        with self.assertRaisesRegex(importer.ArtifactError, "analytics"):
            self.load()

    def test_85_db_only_fields_are_derived_from_immutable_refs(self) -> None:
        plan = importer.build_import_plan(self.load(), self.snapshot)
        found = next(row for row in plan.observation_rows if row["raw_ref"] == "enrich:100")
        not_found = next(row for row in plan.observation_rows if row["raw_ref"] is None)
        self.assertEqual(found["currency"], "RUB")
        self.assertEqual(found["source_ref"], "https://www.ozon.ru/product/100/")
        self.assertEqual(found["availability_raw"], "В наличии")
        self.assertIsNone(not_found["currency"])
        self.assertIsNone(not_found["availability_raw"])
        self.assertEqual(not_found["source_ref"], self.payload["search_runs"][0]["source_url"])

    def test_86_price_element_classification_is_canonical(self) -> None:
        element = self.evidence["enrichment_evidence"][0]["price_evidence"][
            "visible_price_elements"
        ][0]
        element["semantic_classification"] = element.pop("classification")
        with self.assertRaisesRegex(importer.ArtifactError, "BANK_PRICE"):
            self.load()


class ReferenceLayerTests(SnapshotImporterTestCase):
    def test_31_membership_before_valid_from_is_excluded(self) -> None:
        member = self.snapshot.memberships[0]
        self.assertFalse(importer.membership_valid_at(member, member.valid_from - timedelta(seconds=1)))

    def test_32_membership_at_valid_from_is_included(self) -> None:
        member = self.snapshot.memberships[0]
        self.assertTrue(importer.membership_valid_at(member, member.valid_from))

    def test_33_membership_before_valid_to_is_included(self) -> None:
        member = replace(self.snapshot.memberships[0], valid_to=datetime.now(timezone.utc))
        self.assertTrue(importer.membership_valid_at(member, member.valid_to - timedelta(microseconds=1)))

    def test_34_membership_at_valid_to_is_excluded(self) -> None:
        member = replace(self.snapshot.memberships[0], valid_to=datetime.now(timezone.utc))
        self.assertFalse(importer.membership_valid_at(member, member.valid_to))

    def test_35_historical_inactive_oem_is_accepted(self) -> None:
        snapshot = replace(self.snapshot, oems=(replace(self.snapshot.oems[0], active=False), self.snapshot.oems[1]))
        self.assertEqual(len(importer.derive_reference_layer(snapshot, self.load().reference_at).oem_by_query), 2)

    def test_36_oem_created_after_reference_is_rejected(self) -> None:
        snapshot = replace(
            self.snapshot,
            oems=(replace(self.snapshot.oems[0], created_at=datetime(2030, 1, 1, tzinfo=timezone.utc)), self.snapshot.oems[1]),
        )
        with self.assertRaisesRegex(importer.ReferenceConflictError, "historical SKU/OEM"):
            importer.derive_reference_layer(snapshot, self.load().reference_at)

    def test_37_exclude_membership_is_not_monitored(self) -> None:
        memberships = (replace(self.snapshot.memberships[0], membership_status="EXCLUDE"),) + self.snapshot.memberships[1:]
        layer = importer.derive_reference_layer(replace(self.snapshot, memberships=memberships), self.load().reference_at)
        self.assertNotIn(("УФ 001Б", "OEM-A", "100"), layer.membership_by_slot)

    def test_38_current_9_queries_87_slots_are_derived(self) -> None:
        reference = self.load().reference_at
        oems = []
        memberships = []
        slot_counts = (11, 9, 9, 9, 10, 10, 10, 10, 9)
        for index, slots in enumerate(slot_counts):
            offer = f"SKU-{index // 3}"
            query = f"OEM-{index}"
            oems.append(importer.SkuOemReference(str(uuid.uuid4()), offer, query, True, reference - timedelta(days=1)))
            for slot in range(slots):
                product = f"{index + 1}{slot:02d}"
                memberships.append(importer.MembershipReference(str(uuid.uuid4()), offer, "PRIMARY", (query,), reference - timedelta(days=1), None, str(uuid.uuid4()), str(uuid.uuid4()), product, None))
        layer = importer.derive_reference_layer(replace(self.snapshot, oems=tuple(oems), memberships=tuple(memberships)), reference)
        self.assertEqual((len(layer.oem_by_query), len(layer.membership_by_slot)), (9, 87))

    def test_39_future_slot_count_is_not_hardcoded(self) -> None:
        layer = importer.derive_reference_layer(self.snapshot, self.load().reference_at)
        self.assertEqual((len(layer.oem_by_query), len(layer.membership_by_slot)), (2, 3))

    def test_40_missing_oem_reference_is_conflict(self) -> None:
        with self.assertRaises(importer.ReferenceConflictError):
            importer.derive_reference_layer(replace(self.snapshot, oems=self.snapshot.oems[1:]), self.load().reference_at)

    def test_41_duplicate_historical_slot_is_conflict(self) -> None:
        duplicate = replace(self.snapshot.memberships[0], membership_id=str(uuid.uuid4()), listing_id=str(uuid.uuid4()))
        with self.assertRaisesRegex(importer.ReferenceConflictError, "duplicate historical"):
            importer.derive_reference_layer(replace(self.snapshot, memberships=self.snapshot.memberships + (duplicate,)), self.load().reference_at)

    def test_42_missing_product_family_is_conflict(self) -> None:
        members = (replace(self.snapshot.memberships[0], product_family_id=""),) + self.snapshot.memberships[1:]
        with self.assertRaisesRegex(importer.ReferenceConflictError, "family"):
            importer.derive_reference_layer(replace(self.snapshot, memberships=members), self.load().reference_at)

    def test_43_query_normalization_mismatch_is_conflict(self) -> None:
        self.payload["search_runs"][0]["query_normalized"] = "OTHER"
        with self.assertRaisesRegex(importer.ReferenceConflictError, "normalization"):
            importer.build_import_plan(self.load(), self.snapshot)

    def test_44_missing_slot_is_conflict(self) -> None:
        self.payload["observations"].pop(1)
        with self.assertRaisesRegex(importer.ReferenceConflictError, "slot reconciliation"):
            importer.build_import_plan(self.load(), self.snapshot)

    def test_45_membership_status_mismatch_is_conflict(self) -> None:
        self.payload["observations"][0]["membership_status"] = "RESERVE"
        with self.assertRaisesRegex(importer.ReferenceConflictError, "membership status"):
            importer.build_import_plan(self.load(), self.snapshot)

    def test_46_seller_mismatch_is_conflict(self) -> None:
        self.payload["observations"][0]["seller_id_observed"] = "OTHER"
        self.payload["enrichments"][0]["seller_id_observed"] = "OTHER"
        self.evidence["enrichment_evidence"][0]["seller"]["seller_id_parsed"] = "OTHER"
        with self.assertRaisesRegex(importer.ReferenceConflictError, "seller ID"):
            importer.build_import_plan(self.load(), self.snapshot)

    def test_70_expired_membership_is_excluded(self) -> None:
        reference = self.load().reference_at
        member = replace(self.snapshot.memberships[0], valid_to=reference)
        layer = importer.derive_reference_layer(
            replace(self.snapshot, memberships=(member,) + self.snapshot.memberships[1:]),
            reference,
        )
        self.assertNotIn(("УФ 001Б", "OEM-A", "100"), layer.membership_by_slot)

    def test_71_future_membership_is_excluded(self) -> None:
        reference = self.load().reference_at
        member = replace(self.snapshot.memberships[0], valid_from=reference + timedelta(seconds=1))
        layer = importer.derive_reference_layer(
            replace(self.snapshot, memberships=(member,) + self.snapshot.memberships[1:]),
            reference,
        )
        self.assertNotIn(("УФ 001Б", "OEM-A", "100"), layer.membership_by_slot)

    def test_72_hold_sku_without_memberships_is_excluded_by_references(self) -> None:
        layer = importer.derive_reference_layer(self.snapshot, self.load().reference_at)
        self.assertFalse(any(offer == "УФ 003Б" for offer, _ in layer.oem_by_query))


class PlanStateAndSafetyTests(SnapshotImporterTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bundle = self.load()
        self.plan = importer.build_import_plan(self.bundle, self.snapshot)

    def test_47_valid_plan_has_dynamic_counts(self) -> None:
        self.assertEqual((self.plan.expected_query_count, self.plan.expected_slot_count), (2, 3))
        self.assertEqual((self.plan.found, self.plan.not_found), (2, 1))

    def test_48_new_batch_state(self) -> None:
        self.assertEqual(importer.determine_history_state(self.plan, self.snapshot), "NEW_BATCH")

    def test_49_exact_already_applied_state(self) -> None:
        persisted = replace(self.snapshot, search_rows=self.plan.search_rows, observation_rows=self.plan.observation_rows)
        self.assertEqual(importer.determine_history_state(self.plan, persisted), "EXACT_ALREADY_APPLIED")

    def test_50_partial_batch_is_conflict(self) -> None:
        partial = replace(self.snapshot, search_rows=self.plan.search_rows[:1])
        with self.assertRaisesRegex(importer.BatchConflictError, "PARTIAL_BATCH_CONFLICT"):
            importer.determine_history_state(self.plan, partial)

    def test_51_unrelated_baseline_history_is_allowed(self) -> None:
        self.assertEqual(self.snapshot.history_counts["observations"], 87)
        self.assertEqual(importer.determine_history_state(self.plan, self.snapshot), "NEW_BATCH")

    def test_52_factually_different_same_refs_is_conflict(self) -> None:
        rows = [dict(row) for row in self.plan.observation_rows]
        rows[0]["bank_price"] = 901
        persisted = replace(self.snapshot, search_rows=self.plan.search_rows, observation_rows=tuple(rows))
        with self.assertRaises(importer.BatchConflictError):
            importer.determine_history_state(self.plan, persisted)

    def test_53_missing_schema_column_is_reference_conflict(self) -> None:
        schema = dict(self.snapshot.schema_columns)
        schema["competitor_observations"] = tuple(
            column for column in schema["competitor_observations"] if column.name != "raw_ref"
        )
        with self.assertRaisesRegex(importer.ReferenceConflictError, "missing"):
            importer.build_import_plan(self.bundle, replace(self.snapshot, schema_columns=schema))

    def test_54_repeat_plan_has_identical_refs_and_ids(self) -> None:
        second = importer.build_import_plan(self.bundle, self.snapshot)
        self.assertEqual(self.plan.search_rows, second.search_rows)
        self.assertEqual(self.plan.observation_rows, second.observation_rows)

    def test_55_not_found_maps_to_null_facts(self) -> None:
        row = next(row for row in self.plan.observation_rows if row["raw_ref"] is None)
        self.assertIsNone(row["bank_price"])
        self.assertIsNone(row["enrichment_captured_at"])
        self.assertIsNone(row["ad_flag"])

    def test_56_enrichment_timestamp_is_distinct_from_search_time(self) -> None:
        row = self.plan.observation_rows[0]
        self.assertNotEqual(row["captured_at"], row["enrichment_captured_at"])

    def test_57_write_gate_requires_both_controls(self) -> None:
        with self.assertRaises(importer.ConfigurationError):
            importer.validate_write_gate(True, {})
        importer.validate_write_gate(True, {importer.WRITE_GATE: "true"})

    def test_58_dry_run_needs_no_write_gate(self) -> None:
        importer.validate_write_gate(False, {})

    def test_59_cli_defaults_to_dry_run(self) -> None:
        args = importer.parse_arguments(["--payload", "p", "--evidence", "e", "--payload-sha256", "a" * 64, "--evidence-sha256", "b" * 64])
        self.assertFalse(args.write)

    def test_60_only_two_insert_targets_exist(self) -> None:
        source = inspect.getsource(importer)
        self.assertEqual(source.count("INSERT INTO public."), 2)
        self.assertIn("INSERT INTO public.competitor_search_runs", source)
        self.assertIn("INSERT INTO public.competitor_observations", source)

    def test_61_no_mutating_sql_variants(self) -> None:
        source = inspect.getsource(importer).upper()
        self.assertNotIn("ON CONFLICT", source)
        self.assertNotIn("UPDATE PUBLIC.", source)
        self.assertNotIn("DELETE FROM PUBLIC.", source)

    def test_62_no_runtime_baseline_or_collector_dependency(self) -> None:
        source = inspect.getsource(importer)
        self.assertNotIn("import_competitor_baseline", source)
        self.assertNotIn("competitor_collector", source)

    def test_63_insert_plan_executes_exactly_two_batches(self) -> None:
        class Cursor:
            def __init__(self) -> None:
                self.calls: list[tuple[str, object]] = []

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def executemany(self, sql, rows):
                self.calls.append((sql, rows))

        class Connection:
            def __init__(self) -> None:
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

        connection = Connection()
        importer._insert_plan(connection, self.plan)
        self.assertEqual(len(connection.cursor_instance.calls), 2)

    def test_64_exact_replay_performs_no_insert(self) -> None:
        class Connection:
            def __init__(self) -> None:
                self.rollbacks = 0

            def cursor(self):
                class Cursor:
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def execute(self, *args): return None
                return Cursor()

            def rollback(self): self.rollbacks += 1
            def commit(self): raise AssertionError("commit must not run")

        connection = Connection()
        exact = replace(self.snapshot, search_rows=self.plan.search_rows, observation_rows=self.plan.observation_rows)
        with patch.object(importer, "read_production_snapshot", return_value=self.snapshot), patch.object(importer, "read_batch_history", return_value=exact), patch.object(importer, "_insert_plan") as insert:
            result = importer.execute_write(connection, payload_path=self.bundle.payload_path, evidence_path=self.bundle.evidence_path, payload_sha256=self.bundle.payload_sha256, evidence_sha256=self.bundle.evidence_sha256)
        self.assertEqual(result.history_state, "EXACT_ALREADY_APPLIED")
        insert.assert_not_called()
        self.assertEqual(connection.rollbacks, 1)

    def test_73_run_and_observation_refs_are_unique(self) -> None:
        self.assertEqual(
            len({row["collection_ref"] for row in self.plan.search_rows}),
            len(self.plan.search_rows),
        )
        self.assertEqual(
            len({row["observation_ref"] for row in self.plan.observation_rows}),
            len(self.plan.observation_rows),
        )

    def test_74_previous_snapshot_history_is_allowed(self) -> None:
        counts = dict(self.snapshot.history_counts)
        counts.update(search_runs=18, observations=174)
        historical = replace(self.snapshot, history_counts=counts)
        self.assertEqual(importer.determine_history_state(self.plan, historical), "NEW_BATCH")

    def test_75_dry_run_reports_zero_writes(self) -> None:
        result = importer.run_dry_run(self.bundle, self.snapshot)
        self.assertEqual((result.inserts, result.updates, result.deletes), (0, 0, 0))

    def test_76_env_gate_alone_does_not_select_write_mode(self) -> None:
        args = importer.parse_arguments(["--payload", "p", "--evidence", "e", "--payload-sha256", "a" * 64, "--evidence-sha256", "b" * 64])
        importer.validate_write_gate(args.write, {importer.WRITE_GATE: "true"})
        self.assertFalse(args.write)

    def test_77_transaction_failure_rolls_back(self) -> None:
        class Connection:
            def __init__(self) -> None:
                self.rollbacks = 0

            def cursor(self):
                class Cursor:
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def execute(self, *args): return None
                return Cursor()

            def rollback(self): self.rollbacks += 1
            def commit(self): raise AssertionError("commit must not run")

        connection = Connection()
        with patch.object(importer, "read_production_snapshot", return_value=self.snapshot), patch.object(importer, "read_batch_history", return_value=self.snapshot), patch.object(importer, "_insert_plan", side_effect=RuntimeError("test failure")):
            with self.assertRaisesRegex(RuntimeError, "test failure"):
                importer.execute_write(connection, payload_path=self.bundle.payload_path, evidence_path=self.bundle.evidence_path, payload_sha256=self.bundle.payload_sha256, evidence_sha256=self.bundle.evidence_sha256)
        self.assertEqual(connection.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
