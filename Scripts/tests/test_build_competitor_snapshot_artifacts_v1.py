from __future__ import annotations

import copy
import hashlib
import json
import random
import sys
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "Scripts"
TESTS = SCRIPTS / "tests"
for path in (SCRIPTS, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_competitor_snapshot_artifacts_v1 as builder
import test_import_competitor_snapshot_v1 as importer_tests


T1_DIR = (
    Path.home()
    / ".efa-os/archive/competitor-monitor/snapshot-v1/2026-08-26"
    / "961baa306c34ff7dc6c973e02b49d0c26226864709148fe6c128109e6a68138e"
)
T1_EVIDENCE = T1_DIR / "COMPETITOR_SNAPSHOT_T1_EVIDENCE_V1.json"
T1_PAYLOAD = T1_DIR / "COMPETITOR_SNAPSHOT_T1_PAYLOAD_V1.json"
T0_PAYLOAD = (
    Path.home()
    / ".efa-os/archive/competitor-monitor/baseline-v1/2026-08-25"
    / "0137d14ccf22ad244ea20c269b39aed642aa037ab089348dc216b95883bf8a9f"
    / "BASELINE_PAYLOAD_V1_PROVENANCE_R2.json"
)

LEGACY_MEMBERSHIP_ORDER = (
    ("УФ 001Б", "796591986"), ("УФ 001Б", "266328154"),
    ("УФ 001Б", "1356342041"), ("УФ 001Б", "924191375"),
    ("УФ 001Б", "3468256200"), ("УФ 001Б", "2698014827"),
    ("УФ 001Б", "215996486"), ("УФ 001Б", "1566524732"),
    ("УФ 001Б", "5540658609"), ("УФ 001Б", "2022731795"),
    ("УФ 001Б", "4601821825"), ("УФ 002Б", "1201513545"),
    ("УФ 002Б", "2936478004"), ("УФ 002Б", "618137426"),
    ("УФ 002Б", "1628467740"), ("УФ 002Б", "1480553506"),
    ("УФ 002Б", "1628774540"), ("УФ 002Б", "1624364470"),
    ("УФ 002Б", "266346879"), ("УФ 002Б", "4642158029"),
    ("УФ 004Б", "613048940"), ("УФ 004Б", "1324012918"),
    ("УФ 004Б", "519757297"), ("УФ 004Б", "1411048042"),
    ("УФ 004Б", "3011421926"), ("УФ 004Б", "3525756097"),
    ("УФ 004Б", "898384330"), ("УФ 004Б", "227576931"),
    ("УФ 004Б", "616223751"), ("УФ 004Б", "4642180551"),
    ("УФ 005Б", "332405695"), ("УФ 005Б", "268629078"),
    ("УФ 005Б", "4381338927"), ("УФ 005Б", "1086068777"),
    ("УФ 005Б", "215758125"), ("УФ 005Б", "3959121966"),
    ("УФ 005Б", "2666178947"), ("УФ 005Б", "2810830876"),
    ("УФ 005Б", "658313675"), ("УФ 005Б", "3968916713"),
    ("УФ 005Б", "4671328307"),
)


def fixture() -> tuple[dict, dict]:
    evidence, source_payload = importer_tests.base_artifacts()
    evidence = copy.deepcopy(evidence)
    source_payload = copy.deepcopy(source_payload)
    batch = evidence["batch"]
    batch.update(
        {
            "region_key": builder.EXPECTED_REGION_KEY,
            "location_label": builder.EXPECTED_LOCATION_LABEL,
            "source": builder.EXPECTED_SOURCE,
            "collection_method": builder.EXPECTED_COLLECTION_METHOD,
        }
    )
    for row in evidence["search_evidence"]:
        row["region_key"] = builder.EXPECTED_REGION_KEY
        row["location_label"] = builder.EXPECTED_LOCATION_LABEL
    queries = []
    for ordinal, run in enumerate(source_payload["search_runs"], 1):
        queries.append(
            {
                "ordinal": ordinal,
                "offer_id": run["offer_id"],
                "query_kind": "OEM",
                "query_text_exact": run["query_text_exact"],
                "query_normalized": run["query_normalized"],
                "sku_oem_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "oem:" + run["query_text_exact"])),
            }
        )
    slots = []
    for ordinal, row in enumerate(source_payload["observations"], 1):
        token = f"{row['offer_id']}:{row['query_text_exact']}:{row['ozon_product_id']}"
        slots.append(
            {
                "ordinal": ordinal,
                "offer_id": row["offer_id"],
                "query_text_exact": row["query_text_exact"],
                "ozon_product_id": str(row["ozon_product_id"]),
                "product_name": "Fixture " + str(row["ozon_product_id"]),
                "membership_status": row["membership_status"],
                "membership_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "membership:" + token)),
                "listing_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "listing:" + token)),
                "product_family_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "family:" + token)),
                "seller_id": None,
            }
        )
    plan = {
        "contract_version": builder.REFERENCE_PLAN_CONTRACT,
        "reference_at": importer_tests.REFERENCE_AT,
        "region_key": builder.EXPECTED_REGION_KEY,
        "location_label": builder.EXPECTED_LOCATION_LABEL,
        "source": builder.EXPECTED_SOURCE,
        "collection_method": builder.EXPECTED_COLLECTION_METHOD,
        "expected_queries": len(queries),
        "expected_slots": len(slots),
        "queries": queries,
        "slots": slots,
    }
    return evidence, plan


def evidence_hash(evidence: dict) -> str:
    return hashlib.sha256(builder.canonical_pretty_bytes(evidence)).hexdigest()


def snapshot_from_canonical_payload(
    payload: dict,
) -> tuple[builder.snapshot_importer.ProductionSnapshot, datetime, dict[str, str]]:
    reference_at = min(
        builder.parse_timestamp(row["captured_at"], "captured_at")
        for row in payload["search_runs"]
    )
    oems = tuple(
        builder.snapshot_importer.SkuOemReference(
            sku_oem_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "canonical-oem:" + row["offer_id"] + ":" + row["query_text_exact"])),
            offer_id=row["offer_id"],
            oem_normalized=row["query_normalized"],
            active=True,
            created_at=reference_at - timedelta(days=1),
        )
        for row in payload["search_runs"]
    )
    observations_by_membership: dict[tuple[str, str], list[dict]] = {}
    for row in payload["observations"]:
        key = (row["offer_id"], str(row["ozon_product_id"]))
        observations_by_membership.setdefault(key, []).append(row)
    query_order = [
        (row["offer_id"], row["query_text_exact"])
        for row in payload["search_runs"]
    ]
    memberships = []
    product_names: dict[str, str] = {}
    for reference_ordinal, key in enumerate(LEGACY_MEMBERSHIP_ORDER, 1):
        observations = observations_by_membership[key]
        first = observations[0]
        observed_queries = {row["query_text_exact"] for row in observations}
        matched_oem_set = tuple(
            query for offer, query in query_order
            if offer == key[0] and query in observed_queries
        )
        token = key[0] + ":" + key[1]
        listing_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "canonical-listing:" + token))
        product_names[listing_id] = first["product_name"]
        memberships.append(
            builder.snapshot_importer.MembershipReference(
                membership_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "canonical-membership:" + token)),
                offer_id=key[0],
                membership_status=first["membership_status"],
                matched_oem_set=matched_oem_set,
                valid_from=reference_at - timedelta(days=1),
                valid_to=None,
                listing_id=listing_id,
                product_family_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "canonical-family:" + token)),
                ozon_product_id=key[1],
                seller_id=None,
                reference_ordinal=reference_ordinal,
                product_name=first["product_name"],
            )
        )
    snapshot = builder.snapshot_importer.ProductionSnapshot(
        profiles={row["offer_id"]: "ACTIVE" for row in payload["search_runs"]},
        oems=oems,
        memberships=tuple(memberships),
        history_counts={},
        search_rows=(),
        observation_rows=(),
        schema_columns={},
        constraint_names=frozenset(),
        index_names=frozenset(),
    )
    return snapshot, reference_at, product_names


class BuilderContractTests(unittest.TestCase):
    def test_01_valid_evidence_builds_payload(self) -> None:
        evidence, plan = fixture()
        payload = builder.build_payload(evidence, evidence_hash(evidence), plan)
        self.assertEqual(payload["contract_version"], builder.PAYLOAD_CONTRACT)

    def test_02_same_input_same_payload_hash(self) -> None:
        evidence, plan = fixture()
        first = builder.payload_identity(builder.build_payload(evidence, evidence_hash(evidence), plan), evidence_hash(evidence))
        second = builder.payload_identity(builder.build_payload(evidence, evidence_hash(evidence), plan), evidence_hash(evidence))
        self.assertEqual(first[1:], second[1:])

    def test_03_reference_at_is_minimum_search_timestamp(self) -> None:
        evidence, plan = fixture()
        self.assertEqual(builder.validate_evidence(evidence).isoformat(), "2026-08-26T07:00:00+00:00")
        builder.validate_evidence_against_plan(evidence, plan)

    def test_04_plan_counts_are_dynamic(self) -> None:
        _, plan = fixture()
        self.assertEqual((plan["expected_queries"], plan["expected_slots"]), (2, 3))
        builder.validate_reference_plan(plan)

    def test_05_missing_query_rejected(self) -> None:
        evidence, plan = fixture()
        evidence["search_evidence"].pop()
        with self.assertRaises(builder.EvidenceValidationError):
            builder.build_payload(evidence, evidence_hash(evidence), plan)

    def test_06_extra_query_rejected(self) -> None:
        evidence, plan = fixture()
        extra = copy.deepcopy(evidence["search_evidence"][0])
        extra.update({"evidence_key": "search:extra", "offer_id": "УФ 005Б", "query_text_exact": "EXTRA", "source_url": "https://www.ozon.ru/search/?text=EXTRA"})
        evidence["search_evidence"].append(extra)
        with self.assertRaises(builder.EvidenceValidationError):
            builder.build_payload(evidence, evidence_hash(evidence), plan)

    def test_07_missing_slot_rejected_by_plan_count(self) -> None:
        evidence, plan = fixture()
        plan["slots"].pop()
        with self.assertRaises(builder.ReferencePlanError):
            builder.build_payload(evidence, evidence_hash(evidence), plan)

    def test_08_wrong_region_rejected(self) -> None:
        evidence, plan = fixture()
        evidence["batch"]["region_key"] = "OTHER"
        for row in evidence["search_evidence"]:
            row["region_key"] = "OTHER"
        with self.assertRaisesRegex(builder.EvidenceValidationError, "region_key"):
            builder.build_payload(evidence, evidence_hash(evidence), plan)

    def test_09_captcha_rejected(self) -> None:
        evidence, plan = fixture()
        evidence["captcha_detected"] = True
        with self.assertRaisesRegex(builder.EvidenceValidationError, "challenge"):
            builder.build_payload(evidence, evidence_hash(evidence), plan)

    def test_10_missing_enrichment_rejected(self) -> None:
        evidence, plan = fixture()
        evidence["enrichment_evidence"].pop()
        with self.assertRaisesRegex(builder.EvidenceValidationError, "enrichment"):
            builder.build_payload(evidence, evidence_hash(evidence), plan)

    def test_11_partial_search_rejected(self) -> None:
        evidence, plan = fixture()
        evidence["search_evidence"][0]["status"] = "PARTIAL"
        with self.assertRaises(builder.EvidenceValidationError):
            builder.build_payload(evidence, evidence_hash(evidence), plan)

    def test_12_raw_refs_resolve(self) -> None:
        evidence, plan = fixture()
        payload = builder.build_payload(evidence, evidence_hash(evidence), plan)
        raw_refs = {row["raw_ref"] for row in payload["enrichments"]}
        self.assertTrue(all(row["raw_ref"] in raw_refs for row in payload["observations"] if row["slot_status"] == "FOUND"))

    def test_13_found_and_not_found_are_preserved(self) -> None:
        evidence, plan = fixture()
        payload = builder.build_payload(evidence, evidence_hash(evidence), plan)
        self.assertEqual([row["slot_status"] for row in payload["observations"]].count("FOUND"), 2)
        self.assertEqual([row["slot_status"] for row in payload["observations"]].count("NOT_FOUND_WITHIN_SCAN_LIMIT"), 1)

    def test_14_product_fact_variance_not_blocking(self) -> None:
        evidence, plan = fixture()
        evidence["enrichment_evidence"][0]["dimensions"]["parsed_length_mm"] = None
        payload = builder.build_payload(evidence, evidence_hash(evidence), plan)
        self.assertIsNone(payload["enrichments"][0]["observed_length_mm"])

    def test_15_immutable_input(self) -> None:
        evidence, plan = fixture()
        before = copy.deepcopy((evidence, plan))
        builder.build_payload(evidence, evidence_hash(evidence), plan)
        self.assertEqual((evidence, plan), before)

    def test_16_load_hash_and_size(self) -> None:
        evidence, _ = fixture()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "evidence.json"
            raw = builder.canonical_pretty_bytes(evidence)
            path.write_bytes(raw)
            loaded, digest, size = builder.load_immutable_evidence(path, hashlib.sha256(raw).hexdigest())
        self.assertEqual((loaded, size), (evidence, len(raw)))
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())

    def test_17_wrong_file_hash_rejected(self) -> None:
        evidence, _ = fixture()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "evidence.json"
            path.write_bytes(builder.canonical_pretty_bytes(evidence))
            with self.assertRaisesRegex(builder.EvidenceValidationError, "SHA-256"):
                builder.load_immutable_evidence(path, "0" * 64)

    @unittest.skipUnless(T1_EVIDENCE.is_file() and T1_PAYLOAD.is_file(), "archived T1 artifacts unavailable")
    def test_18_real_t1_payload_is_byte_exact(self) -> None:
        evidence, digest, _ = builder.load_immutable_evidence(T1_EVIDENCE)
        canonical = json.loads(T1_PAYLOAD.read_bytes())
        snapshot, reference_at, product_names = snapshot_from_canonical_payload(canonical)
        plan = builder.freeze_reference_plan(snapshot, reference_at, product_names)
        rendered, payload_sha, batch_ref = builder.payload_identity(builder.build_payload(evidence, digest, plan), digest)
        self.assertEqual(rendered, T1_PAYLOAD.read_bytes())
        self.assertEqual(payload_sha, "6449a24a3a68809642b69bf043056fc4b9845c48a973e6d72852be2fbe499852")
        self.assertEqual(batch_ref, "cm-snapshot-v1:batch:961baa306c34ff7dc6c973e02b49d0c26226864709148fe6c128109e6a68138e")

    @unittest.skipUnless(T0_PAYLOAD.is_file() and T1_PAYLOAD.is_file(), "archived T0/T1 payloads unavailable")
    def test_19_t0_and_t1_query_and_slot_order_are_exact(self) -> None:
        for payload_path in (T0_PAYLOAD, T1_PAYLOAD):
            canonical = json.loads(payload_path.read_bytes())
            snapshot, reference_at, product_names = snapshot_from_canonical_payload(canonical)
            plan = builder.freeze_reference_plan(snapshot, reference_at, product_names)
            expected_queries = [
                (row["offer_id"], row["query_text_exact"])
                for row in canonical["search_runs"]
            ]
            expected_slots = [
                (row["offer_id"], row["query_text_exact"], str(row["ozon_product_id"]))
                for row in canonical["observations"]
            ]
            actual_queries = [
                (row["offer_id"], row["query_text_exact"])
                for row in plan["queries"]
            ]
            actual_slots = [
                (row["offer_id"], row["query_text_exact"], row["ozon_product_id"])
                for row in plan["slots"]
            ]
            self.assertEqual((len(actual_queries), len(actual_slots)), (9, 87))
            self.assertEqual(actual_queries, expected_queries)
            self.assertEqual(actual_slots, expected_slots)

    @unittest.skipUnless(T1_EVIDENCE.is_file() and T1_PAYLOAD.is_file(), "archived T1 artifacts unavailable")
    def test_20_shuffled_memberships_keep_t1_payload_bytes_and_hash(self) -> None:
        evidence, digest, _ = builder.load_immutable_evidence(T1_EVIDENCE)
        canonical = json.loads(T1_PAYLOAD.read_bytes())
        snapshot, reference_at, product_names = snapshot_from_canonical_payload(canonical)
        baseline_plan = builder.freeze_reference_plan(snapshot, reference_at, product_names)
        for seed in range(10):
            shuffled = importer_tests.membership_source_rows(snapshot)
            random.Random(seed).shuffle(shuffled)
            memberships = builder.snapshot_importer._membership_references_from_rows(shuffled)
            plan = builder.freeze_reference_plan(
                replace(snapshot, memberships=memberships),
                reference_at,
                product_names,
            )
            rendered, payload_sha, _ = builder.payload_identity(
                builder.build_payload(evidence, digest, plan), digest
            )
            self.assertEqual(plan["queries"], baseline_plan["queries"])
            self.assertEqual(plan["slots"], baseline_plan["slots"])
            self.assertEqual(rendered, T1_PAYLOAD.read_bytes())
            self.assertEqual(payload_sha, "6449a24a3a68809642b69bf043056fc4b9845c48a973e6d72852be2fbe499852")

    def test_21_future_membership_uses_higher_ordinal_without_compaction(self) -> None:
        snapshot = importer_tests.reference_snapshot()
        reference_at = datetime.fromisoformat(importer_tests.REFERENCE_AT.replace("Z", "+00:00"))
        product_names = {
            membership.listing_id: "Fixture " + membership.ozon_product_id
            for membership in snapshot.memberships
        }
        baseline = builder.freeze_reference_plan(snapshot, reference_at, product_names)
        future = replace(
            snapshot.memberships[0],
            membership_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "future-membership")),
            listing_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "future-listing")),
            product_family_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "future-family")),
            ozon_product_id="999",
            reference_ordinal=50,
        )
        product_names[future.listing_id] = "Fixture 999"
        expanded_snapshot = replace(snapshot, memberships=(future,) + snapshot.memberships)
        expanded = builder.freeze_reference_plan(expanded_snapshot, reference_at, product_names)
        existing_slots = [
            (row["offer_id"], row["query_text_exact"], row["ozon_product_id"])
            for row in expanded["slots"] if row["ozon_product_id"] != "999"
        ]
        baseline_slots = [
            (row["offer_id"], row["query_text_exact"], row["ozon_product_id"])
            for row in baseline["slots"]
        ]
        ordered_ordinals = [
            membership.reference_ordinal
            for membership in builder.snapshot_importer.order_memberships_by_reference_ordinal(
                expanded_snapshot.memberships
            )
        ]
        self.assertEqual(existing_slots, baseline_slots)
        self.assertEqual(ordered_ordinals, [1, 2, 3, 50])
        self.assertEqual(
            [row["ozon_product_id"] for row in expanded["slots"]],
            ["100", "101", "999", "200"],
        )


if __name__ == "__main__":
    unittest.main()
