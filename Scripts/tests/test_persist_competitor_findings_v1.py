from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
import uuid
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "Scripts"
TESTS = SCRIPTS / "tests"
for path in (SCRIPTS, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import analyze_competitor_snapshots_v1 as analyzer
import build_competitor_snapshot_artifacts_v1 as builder
import import_competitor_snapshot_v1 as snapshot_importer
import persist_competitor_findings_v1 as writer
import run_competitor_daily_cycle_v1 as cycle
import test_build_competitor_snapshot_artifacts_v1 as builder_tests
import test_import_competitor_snapshot_v1 as importer_tests


ARTIFACT = (
    Path.home()
    / ".efa-os/archive/competitor-monitor/finding-set-v1/2026-08-27"
    / "097963f537b2a32a919d325698ca099889aa8ab08b4dbc8367e1e0684f520f7b"
    / "COMPETITOR_T1_VS_T0_FINDINGS_V1.json"
)
LEGACY_FINDINGS_SHA256 = "3202131a109e04c1a05dcb735f33190b75a76ab596bd6921fbafd7b7e0c8fbcd"
LEGACY_SEMANTIC_SHA256 = "7fbf7c23a285749733d6beaaba7602701c3d47af04d793f0978a600fd5919e47"
LEGACY_ANALYSIS_SHA256 = "99483c51928b7073f00cfc2f93c2fcafd52e25a94676774091b21740f24e03dd"
LEGACY_SET_KEY = "cm-finding-set-v1:097963f537b2a32a919d325698ca099889aa8ab08b4dbc8367e1e0684f520f7b"


def load_bundle() -> writer.ArtifactBundle:
    return writer.load_artifact(
        ARTIFACT, LEGACY_FINDINGS_SHA256, LEGACY_ANALYSIS_SHA256
    )


def fake_snapshot(bundle: writer.ArtifactBundle | None = None) -> writer.ProductionSnapshot:
    bundle = bundle or load_bundle()
    report = bundle.report
    observations: dict[str, dict[str, object]] = {}
    listings: dict[str, dict[str, object]] = {}
    offers: set[str] = set()
    for finding in report["findings"]:
        listing_id = str(finding["listing_id"])
        listings[listing_id] = {
            "listing_id": listing_id,
            "product_family_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "family:" + listing_id)),
            "ozon_product_id": str(finding["ozon_product_id"]),
            "offer_id": finding["offer_id"],
            "membership_status": finding["membership_status"],
        }
        offers.add(finding["offer_id"])
        evidence = {row["query_text_exact"]: row for row in finding["evidence_refs"]}
        for reference in finding["observation_refs"]:
            query = reference["query_text_exact"]
            for side, prefix in (("previous", "cm-baseline-v1:run:"), ("current", "cm-snapshot-v1:run:")):
                source = evidence[query][side]
                observation_id = str(reference[f"{side}_observation_id"])
                observations[observation_id] = {
                    "observation_id": observation_id,
                    "observation_ref": reference[f"{side}_observation_ref"],
                    "listing_id": listing_id,
                    "source_ref": source["source_ref"],
                    "raw_ref": source["raw_ref"],
                    "raw_source_ref": source["raw_source_ref"],
                    "offer_id": finding["offer_id"],
                    "query_text_exact": query,
                    "collection_ref": prefix + hashlib.sha256((observation_id + side).encode()).hexdigest(),
                    "ozon_product_id": str(finding["ozon_product_id"]),
                }
    return writer.ProductionSnapshot(
        observations=observations,
        listings=listings,
        offers=frozenset(offers),
        schema_columns={
            table: frozenset(columns)
            for table, columns in writer.REQUIRED_SCHEMA_COLUMNS.items()
        },
        constraint_names=writer.REQUIRED_CONSTRAINTS,
        index_names=writer.REQUIRED_INDEXES,
        history_counts={
            "search_runs": 18,
            "observations": 174,
            "reviews": 0,
            "findings": 0,
            "finding_sets": 0,
        },
    )


def built() -> tuple[writer.ArtifactBundle, writer.ProductionSnapshot, writer.PersistencePlan]:
    bundle = load_bundle()
    snapshot = fake_snapshot(bundle)
    return bundle, snapshot, writer.build_plan(bundle, snapshot)


def persisted_snapshot(
    snapshot: writer.ProductionSnapshot, plan: writer.PersistencePlan
) -> writer.ProductionSnapshot:
    manifest = {name: writer._normalise(value) for name, value in plan.manifest.items()}
    rows = tuple(
        {name: writer._normalise(value) for name, value in row.items()}
        for row in plan.findings
    )
    return replace(snapshot, manifests=(manifest,), finding_rows=rows)


def canonical_source_inputs(
    folder: str,
) -> tuple[
    snapshot_importer.ArtifactBundle,
    snapshot_importer.ImportPlan,
    snapshot_importer.ProductionSnapshot,
    analyzer.SnapshotBatch,
]:
    evidence, reference_plan = builder_tests.fixture()
    evidence_sha = builder_tests.evidence_hash(evidence)
    payload = builder.build_payload(evidence, evidence_sha, reference_plan)
    snapshot = importer_tests.reference_snapshot()
    evidence_path = Path(folder) / "evidence.json"
    payload_path = Path(folder) / "payload.json"
    evidence_path.write_bytes(builder.canonical_pretty_bytes(evidence))
    payload_bytes, payload_sha, _ = builder.payload_identity(payload, evidence_sha)
    payload_path.write_bytes(payload_bytes)
    artifact = snapshot_importer.load_and_validate_artifacts(
        payload_path, evidence_path, payload_sha, evidence_sha
    )
    import_plan = snapshot_importer.build_import_plan(artifact, snapshot)
    current_rows = cycle.planned_current_history_rows(import_plan, snapshot)
    current = analyzer.resolve_snapshot_batches(
        current_rows,
        expected_runs=import_plan.expected_query_count,
        expected_queries_at=lambda _at: tuple(
            (str(row["offer_id"]), str(row["query_text_exact"]))
            for row in import_plan.search_rows
        ),
    )[0]
    return artifact, import_plan, snapshot, current


def new_batch_boundary_fixture(
    *,
    duplicate_current: bool = False,
    identity_mismatch: bool = False,
    batch_mismatch: bool = False,
) -> tuple[
    writer.ArtifactBundle,
    writer.ProductionSnapshot,
    writer.ValidatedCurrentObservationSource,
]:
    with TemporaryDirectory() as folder:
        artifact, import_plan, snapshot, current = canonical_source_inputs(folder)
        if batch_mismatch:
            import_plan = replace(import_plan, batch_ref="cm-snapshot-v1:batch:mismatch")
        if duplicate_current:
            import_plan = replace(
                import_plan,
                observation_rows=(
                    *import_plan.observation_rows,
                    import_plan.observation_rows[0],
                ),
            )
        if identity_mismatch:
            current = replace(
                current,
                rows=(
                    {**current.rows[0], "listing_id": str(uuid.uuid4())},
                    *current.rows[1:],
                ),
            )
        source = writer.build_validated_current_observation_source(
            artifact, import_plan, snapshot, current
        )

    current_row = current.rows[0]
    membership = next(
        row
        for row in snapshot.memberships
        if row.listing_id == current_row["listing_id"]
    )
    previous_at = import_plan.reference_at - timedelta(days=1)
    previous_observation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "previous-observation"))
    previous_observation_ref = "cm-baseline-v1:observation:previous"
    previous_row = {
        "observation_id": previous_observation_id,
        "observation_ref": previous_observation_ref,
        "listing_id": str(current_row["listing_id"]),
        "source_ref": "fixture:previous-source",
        "raw_ref": "fixture:previous-raw",
        "raw_source_ref": "fixture:previous-search",
        "offer_id": current_row["offer_id"],
        "query_text_exact": current_row["query_text_exact"],
        "collection_ref": "cm-baseline-v1:run:previous",
        "ozon_product_id": str(current_row["ozon_product_id"]),
    }
    finding_type = "COMPETITOR_PRICE_DECREASED"
    finding = {
        "finding_type": finding_type,
        "finding_kind": "SIGNAL",
        "offer_id": current_row["offer_id"],
        "listing_id": str(current_row["listing_id"]),
        "ozon_product_id": str(current_row["ozon_product_id"]),
        "membership_status": membership.membership_status,
        "query_context": [{"query_text_exact": current_row["query_text_exact"]}],
        "observation_refs": [
            {
                "query_text_exact": current_row["query_text_exact"],
                "previous_observation_id": previous_observation_id,
                "previous_observation_ref": previous_observation_ref,
                "current_observation_id": current_row["observation_id"],
                "current_observation_ref": current_row["observation_ref"],
            }
        ],
        "evidence_refs": [
            {
                "query_text_exact": current_row["query_text_exact"],
                "previous": {
                    "source_ref": previous_row["source_ref"],
                    "raw_ref": previous_row["raw_ref"],
                    "raw_source_ref": previous_row["raw_source_ref"],
                },
                "current": {
                    "source_ref": current_row["source_ref"],
                    "raw_ref": current_row["raw_ref"],
                    "raw_source_ref": current_row["raw_source_ref"],
                },
            }
        ],
        "metric": "bank_price",
        "severity": "INFO",
        "confidence": "HIGH",
        "status": "PROPOSED",
        "summary": "Fixture price comparison.",
        "dedup_key": (
            f"{finding_type}|{current_row['offer_id']}|"
            f"{current_row['ozon_product_id']}"
        ),
    }
    report = {
        "contract_version": writer.FINDING_SET_CONTRACT,
        "source_analysis_contract": writer.ANALYSIS_CONTRACT,
        "source_analysis_sha256": "a" * 64,
        "previous_snapshot": {
            "source_kind": "BASELINE_V1",
            "derived_batch_id": "fixture-previous",
            "reference_at": previous_at.isoformat().replace("+00:00", "Z"),
            "captured_through": previous_at.isoformat().replace("+00:00", "Z"),
            "region_key": builder.EXPECTED_REGION_KEY,
        },
        "current_snapshot": current.metadata(),
        "summary": {"findings_total": 1},
        "findings": [finding],
        "suppressed_events": [],
    }
    finding_bundle = writer.ArtifactBundle(
        report=report,
        findings_sha256="b" * 64,
        semantic_sha256=writer.semantic_sha256(report),
        analysis_sha256="a" * 64,
    )
    base = writer.ProductionSnapshot(
        observations={previous_observation_id: previous_row},
        listings={
            str(current_row["listing_id"]): {
                "listing_id": str(current_row["listing_id"]),
                "product_family_id": membership.product_family_id,
                "ozon_product_id": membership.ozon_product_id,
                "offer_id": membership.offer_id,
                "membership_status": membership.membership_status,
            }
        },
        offers=frozenset({membership.offer_id}),
        schema_columns={
            table: frozenset(columns)
            for table, columns in writer.REQUIRED_SCHEMA_COLUMNS.items()
        },
        constraint_names=writer.REQUIRED_CONSTRAINTS,
        index_names=writer.REQUIRED_INDEXES,
    )
    return finding_bundle, base, source


class HashAndIdentityTests(unittest.TestCase):
    def test_01_exact_finding_artifact_hash_accepted(self) -> None:
        self.assertEqual(load_bundle().findings_sha256, LEGACY_FINDINGS_SHA256)

    def test_02_wrong_finding_artifact_hash_rejected(self) -> None:
        with self.assertRaises(writer.InputContractError):
            writer.load_artifact(ARTIFACT, "0" * 64, LEGACY_ANALYSIS_SHA256)

    def test_03_wrong_analysis_hash_rejected(self) -> None:
        with self.assertRaises(writer.InputContractError):
            writer.load_artifact(ARTIFACT, LEGACY_FINDINGS_SHA256, "0" * 64)

    def test_04_semantic_hash_exact(self) -> None:
        bundle = load_bundle()
        self.assertEqual(writer.semantic_sha256(bundle.report), LEGACY_SEMANTIC_SHA256)

    def test_05_semantic_hash_mismatch_rejected(self) -> None:
        raw = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        raw["summary"]["findings_total"] += 1
        with TemporaryDirectory() as folder:
            path = Path(folder) / "changed.json"
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(writer.InputContractError):
                writer.load_artifact(path, digest, LEGACY_ANALYSIS_SHA256)

    def test_06_deterministic_set_key(self) -> None:
        bundle = load_bundle()
        first = writer.build_set_key(bundle.report, bundle.semantic_sha256)
        self.assertEqual(first, LEGACY_SET_KEY)
        self.assertEqual(first, writer.build_set_key(bundle.report, bundle.semantic_sha256))

    def test_07_set_identity_contract_exact(self) -> None:
        bundle = load_bundle()
        identity = writer.set_identity_document(bundle.report, bundle.semantic_sha256)
        self.assertEqual(identity["contract"], writer.SET_IDENTITY_CONTRACT)
        self.assertEqual(set(identity["previous_snapshot"]), {"source_kind", "derived_batch_id"})

    def test_08_deterministic_finding_keys(self) -> None:
        bundle = load_bundle()
        keys = [writer.build_finding_key(bundle.report, row) for row in bundle.report["findings"]]
        self.assertEqual(keys, [writer.build_finding_key(bundle.report, row) for row in bundle.report["findings"]])

    def test_09_ten_finding_keys_unique(self) -> None:
        bundle = load_bundle()
        keys = {writer.build_finding_key(bundle.report, row) for row in bundle.report["findings"]}
        self.assertEqual(len(keys), 10)

    def test_10_finding_identity_has_no_query(self) -> None:
        bundle = load_bundle()
        identity = writer.finding_identity_document(bundle.report, bundle.report["findings"][0])
        self.assertNotIn("query_text_exact", json.dumps(identity))

    def test_11_uuidv5_deterministic(self) -> None:
        value = writer.deterministic_uuid(LEGACY_SET_KEY)
        self.assertEqual(value, writer.deterministic_uuid(LEGACY_SET_KEY))
        self.assertEqual(value.version, 5)

    def test_12_source_artifact_unchanged(self) -> None:
        before = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
        load_bundle()
        self.assertEqual(hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(), before)

    def test_12a_generic_valid_analysis_hash_is_accepted(self) -> None:
        report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        report["source_analysis_sha256"] = "a" * 64
        with TemporaryDirectory() as folder:
            path = Path(folder) / "generic.json"
            path.write_bytes(writer.canonical_json_bytes(report))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            bundle = writer.load_artifact(path, digest, "a" * 64)
        self.assertEqual(bundle.analysis_sha256, "a" * 64)

    def test_12b_writer_has_no_t1_approved_constants(self) -> None:
        source = (SCRIPTS / "persist_competitor_findings_v1.py").read_text(encoding="utf-8")
        self.assertNotIn("APPROVED_FINDINGS_SHA256", source)
        self.assertNotIn(LEGACY_SET_KEY, source)


class PlanTests(unittest.TestCase):
    def test_13_manifest_mapping(self) -> None:
        _, _, plan = built()
        self.assertEqual(plan.manifest["set_key"], LEGACY_SET_KEY)
        self.assertEqual(plan.manifest["expected_findings_count"], 10)
        self.assertEqual(plan.manifest["persistence_contract_version"], writer.PERSISTENCE_CONTRACT)

    def test_14_manifest_uuidv5(self) -> None:
        _, _, plan = built()
        self.assertEqual(plan.manifest["finding_set_id"], writer.deterministic_uuid(LEGACY_SET_KEY))

    def test_15_single_query_scalar_observation_ids(self) -> None:
        _, _, plan = built()
        rows = [row for row in plan.findings if len(row["details"]["query_context"]) == 1]
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["old_observation_id"] and row["new_observation_id"] for row in rows))

    def test_16_multi_query_scalar_ids_null(self) -> None:
        _, _, plan = built()
        rows = [row for row in plan.findings if len(row["details"]["query_context"]) > 1]
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["old_observation_id"] is None and row["new_observation_id"] is None for row in rows))

    def test_17_evidence_contains_all_query_contexts(self) -> None:
        _, _, plan = built()
        self.assertEqual(sum(len(row["evidence"]) for row in plan.findings), 21)

    def test_17a_snapshot_to_snapshot_previous_prefix_supported(self) -> None:
        report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        report["previous_snapshot"]["source_kind"] = "SNAPSHOT_V1"
        report["source_analysis_sha256"] = "b" * 64
        with TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot-pair.json"
            path.write_bytes(writer.canonical_json_bytes(report))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            bundle = writer.load_artifact(path, digest, "b" * 64)
        snapshot = fake_snapshot(bundle)
        observations = {
            key: {
                **row,
                "collection_ref": str(row["collection_ref"]).replace(
                    "cm-baseline-v1:run:", "cm-snapshot-v1:run:"
                ),
            }
            for key, row in snapshot.observations.items()
        }
        plan = writer.build_plan(bundle, replace(snapshot, observations=observations))
        self.assertEqual(plan.manifest["previous_source_kind"], "SNAPSHOT_V1")

    def test_18_details_contract(self) -> None:
        _, _, plan = built()
        self.assertTrue(all(row["details"]["contract_version"] == writer.DETAILS_CONTRACT for row in plan.findings))
        self.assertTrue(all(row["details"]["finding_set_semantic_sha256"] == LEGACY_SEMANTIC_SHA256 for row in plan.findings))

    def test_19_observation_resolution_exact(self) -> None:
        _, _, plan = built()
        self.assertEqual(plan.query_contexts, 21)
        self.assertEqual(plan.observation_sides_resolved, 42)

    def test_20_observation_mismatch_aborts(self) -> None:
        bundle = load_bundle()
        snapshot = fake_snapshot(bundle)
        observations = dict(snapshot.observations)
        key = next(iter(observations))
        observations[key] = dict(observations[key], source_ref="mismatch")
        with self.assertRaises(writer.ReferenceConflictError):
            writer.build_plan(bundle, replace(snapshot, observations=observations))

    def test_21_listing_mismatch_aborts(self) -> None:
        bundle = load_bundle()
        snapshot = fake_snapshot(bundle)
        listings = dict(snapshot.listings)
        key = next(iter(listings))
        listings[key] = dict(listings[key], ozon_product_id="wrong")
        with self.assertRaises(writer.ReferenceConflictError):
            writer.build_plan(bundle, replace(snapshot, listings=listings))

    def test_22_family_resolution(self) -> None:
        _, snapshot, plan = built()
        expected = {uuid.UUID(str(row["product_family_id"])) for row in snapshot.listings.values()}
        self.assertTrue({row["product_family_id"] for row in plan.findings}.issubset(expected))

    def test_23_finding_set_fk_attached_to_each_row(self) -> None:
        _, _, plan = built()
        self.assertTrue(all(row["finding_set_id"] == plan.manifest["finding_set_id"] for row in plan.findings))

    def test_24_status_remains_proposed(self) -> None:
        _, _, plan = built()
        self.assertEqual({row["status"] for row in plan.findings}, {"PROPOSED"})

    def test_25_no_arbitrary_primary_query(self) -> None:
        _, _, plan = built()
        multi = [row for row in plan.findings if len(row["evidence"]) > 1]
        self.assertTrue(all(row["old_observation_id"] is None for row in multi))

    def test_26_required_values_present(self) -> None:
        _, _, plan = built()
        for row in plan.findings:
            for name in writer.FINDING_COLUMNS:
                if name not in {"old_observation_id", "new_observation_id"}:
                    self.assertIsNotNone(row[name])

    def test_27_schema_mismatch_aborts(self) -> None:
        bundle = load_bundle()
        snapshot = fake_snapshot(bundle)
        schema = dict(snapshot.schema_columns)
        schema["competitor_findings"] = frozenset()
        with self.assertRaises(writer.ReferenceConflictError):
            writer.build_plan(bundle, replace(snapshot, schema_columns=schema))


class ObservationBoundaryTests(unittest.TestCase):
    def _assert_factory_rejects(self, mutation) -> None:
        with TemporaryDirectory() as folder:
            artifact, plan, history, current = canonical_source_inputs(folder)
            artifact, plan, history, current = mutation(
                artifact, plan, history, current
            )
            with self.assertRaises(writer.ReferenceConflictError):
                writer.build_validated_current_observation_source(
                    artifact, plan, history, current
                )

    @staticmethod
    def _change_plan_row(plan, attribute: str, **changes):
        rows = [dict(row) for row in getattr(plan, attribute)]
        rows[0] = {**rows[0], **changes}
        return replace(plan, **{attribute: tuple(rows)})

    def test_27a_new_batch_uses_persisted_previous_and_planned_current(self) -> None:
        bundle, base, source = new_batch_boundary_fixture()
        resolved = writer._resolve_observation_sources(
            tuple(base.observations.values()), bundle.report, source
        )
        plan = writer.build_plan(bundle, replace(base, observations=resolved))
        reference = bundle.report["findings"][0]["observation_refs"][0]
        self.assertIn(reference["previous_observation_id"], resolved)
        self.assertIn(reference["current_observation_id"], resolved)
        self.assertEqual(plan.query_contexts, 1)
        self.assertEqual(plan.observation_sides_resolved, 2)

    def test_27b_missing_current_ref_fails_closed(self) -> None:
        bundle, base, source = new_batch_boundary_fixture()
        report = copy.deepcopy(bundle.report)
        report["findings"][0]["observation_refs"][0][
            "current_observation_id"
        ] = str(uuid.uuid4())
        with self.assertRaisesRegex(
            writer.ReferenceConflictError, "validated import plan"
        ):
            writer._resolve_observation_sources(
                tuple(base.observations.values()), report, source
            )

    def test_27c_duplicate_current_identity_fails_closed(self) -> None:
        with self.assertRaisesRegex(writer.ReferenceConflictError, "canonical Payload plan"):
            new_batch_boundary_fixture(duplicate_current=True)

    def test_27d_analyzed_current_identity_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            writer.ReferenceConflictError, "canonical Import Plan"
        ):
            new_batch_boundary_fixture(identity_mismatch=True)

    def test_27e_persisted_current_row_fails_new_batch(self) -> None:
        bundle, base, source = new_batch_boundary_fixture()
        current_id = bundle.report["findings"][0]["observation_refs"][0][
            "current_observation_id"
        ]
        rows = (*base.observations.values(), source.observations[current_id])
        with self.assertRaisesRegex(
            writer.ReferenceConflictError, "incompatible with NEW_BATCH"
        ):
            writer._resolve_observation_sources(rows, bundle.report, source)

    def test_27f_cloned_source_with_preserved_stamp_is_rejected(self) -> None:
        bundle, base, source = new_batch_boundary_fixture()
        observation_id = next(iter(source.observations))
        observations = dict(source.observations)
        observations[observation_id] = MappingProxyType(
            {**observations[observation_id], "search_run_id": "forged-run"}
        )
        untrusted = replace(source, observations=MappingProxyType(observations))
        with self.assertRaisesRegex(writer.InputContractError, "changed after validation"):
            writer._resolve_observation_sources(
                tuple(base.observations.values()), bundle.report, untrusted
            )

    def test_27g_zero_finding_requires_no_observation_source(self) -> None:
        bundle, _, _ = new_batch_boundary_fixture()
        report = copy.deepcopy(bundle.report)
        report["findings"] = []
        report["summary"]["findings_total"] = 0
        self.assertEqual(writer._resolve_observation_sources((), report, None), {})

    def test_27h_missing_previous_ref_fails_closed(self) -> None:
        bundle, _, source = new_batch_boundary_fixture()
        with self.assertRaisesRegex(writer.ReferenceConflictError, "previous"):
            writer._resolve_observation_sources((), bundle.report, source)

    def test_27i_batch_identity_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(writer.ReferenceConflictError, "batch identity"):
            new_batch_boundary_fixture(batch_mismatch=True)

    def test_27j_changed_source_payload_sha_is_rejected(self) -> None:
        bundle, base, source = new_batch_boundary_fixture()
        changed = replace(source, payload_sha256="0" * 64)
        with self.assertRaises(writer.InputContractError):
            writer._resolve_observation_sources(
                tuple(base.observations.values()), bundle.report, changed
            )

    def test_27k_changed_source_batch_ref_is_rejected(self) -> None:
        bundle, base, source = new_batch_boundary_fixture()
        changed = replace(source, batch_ref="cm-snapshot-v1:batch:forged")
        with self.assertRaises(writer.InputContractError):
            writer._resolve_observation_sources(
                tuple(base.observations.values()), bundle.report, changed
            )

    def test_27l_changed_source_reference_at_is_rejected(self) -> None:
        bundle, base, source = new_batch_boundary_fixture()
        identity = MappingProxyType(
            {**source.snapshot_identity, "reference_at": "2026-01-01T00:00:00.000Z"}
        )
        changed = replace(source, snapshot_identity=identity)
        with self.assertRaises(writer.InputContractError):
            writer._resolve_observation_sources(
                tuple(base.observations.values()), bundle.report, changed
            )

    def test_27m_changed_derived_batch_id_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                plan,
                history,
                replace(current, derived_batch_id="cm-analysis-derived-batch:v1:forged"),
            )
        )

    def test_27n_changed_search_run_id_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                self._change_plan_row(
                    plan, "observation_rows", search_run_id=str(uuid.uuid4())
                ),
                history,
                current,
            )
        )

    def test_27o_changed_observation_id_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                self._change_plan_row(
                    plan, "observation_rows", observation_id=str(uuid.uuid4())
                ),
                history,
                current,
            )
        )

    def test_27p_changed_observation_ref_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                self._change_plan_row(
                    plan,
                    "observation_rows",
                    observation_ref="cm-snapshot-v1:observation:forged",
                ),
                history,
                current,
            )
        )

    def test_27q_changed_listing_id_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                self._change_plan_row(
                    plan, "observation_rows", listing_id=str(uuid.uuid4())
                ),
                history,
                current,
            )
        )

    def test_27r_changed_membership_id_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                self._change_plan_row(
                    plan, "observation_rows", membership_id=str(uuid.uuid4())
                ),
                history,
                current,
            )
        )

    def test_27s_changed_source_ref_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                self._change_plan_row(
                    plan, "observation_rows", source_ref="forged:source"
                ),
                history,
                current,
            )
        )

    def test_27t_changed_raw_ref_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                self._change_plan_row(
                    plan, "observation_rows", raw_ref="forged:raw"
                ),
                history,
                current,
            )
        )

    def test_27u_changed_query_context_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                self._change_plan_row(
                    plan, "search_rows", query_text_exact="FORGED_QUERY"
                ),
                history,
                current,
            )
        )

    def test_27v_removed_current_observation_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                replace(plan, observation_rows=plan.observation_rows[:-1]),
                history,
                current,
            )
        )

    def test_27w_extra_current_observation_is_rejected(self) -> None:
        def mutation(artifact, plan, history, current):
            extra = {
                **plan.observation_rows[0],
                "observation_id": str(uuid.uuid4()),
                "observation_ref": "cm-snapshot-v1:observation:extra",
            }
            return (
                artifact,
                replace(plan, observation_rows=(*plan.observation_rows, extra)),
                history,
                current,
            )

        self._assert_factory_rejects(mutation)

    def test_27x_import_plan_not_matching_artifact_is_rejected(self) -> None:
        self._assert_factory_rejects(
            lambda artifact, plan, history, current: (
                artifact,
                replace(plan, found=plan.found + 1),
                history,
                current,
            )
        )

    def test_27y_snapshot_batch_not_matching_plan_is_rejected(self) -> None:
        def mutation(artifact, plan, history, current):
            rows = [dict(row) for row in current.rows]
            rows[0]["raw_ref"] = "forged:raw"
            return artifact, plan, history, replace(current, rows=tuple(rows))

        self._assert_factory_rejects(mutation)

    def test_27z_source_lookup_is_immutable(self) -> None:
        _, _, source = new_batch_boundary_fixture()
        observation_id = next(iter(source.observations))
        with self.assertRaises(TypeError):
            source.observations[observation_id]["source_ref"] = "forged"

    def test_27za_new_batch_to_persisted_exact_lifecycle(self) -> None:
        with TemporaryDirectory() as folder:
            artifact, import_plan, import_history, _ = canonical_source_inputs(folder)
            exact_import_history = replace(
                import_history,
                search_rows=import_plan.search_rows,
                observation_rows=import_plan.observation_rows,
            )
            self.assertEqual(
                snapshot_importer.run_dry_run(
                    artifact, exact_import_history
                ).history_state,
                "EXACT_ALREADY_APPLIED",
            )

        bundle, base, source = new_batch_boundary_fixture()
        new_observations = writer._resolve_observation_sources(
            tuple(base.observations.values()), bundle.report, source
        )
        new_base = replace(base, observations=new_observations)
        new_plan = writer.build_plan(bundle, new_base)
        self.assertEqual(
            writer.run_dry_run(bundle, new_base).history_state,
            "NEW_FINDING_SET",
        )

        persisted_observations = writer._resolve_observation_sources(
            tuple(new_observations.values()), bundle.report, None
        )
        after_write = persisted_snapshot(
            replace(base, observations=persisted_observations), new_plan
        )
        self.assertEqual(
            writer.run_dry_run(bundle, after_write).history_state,
            "EXACT_ALREADY_APPLIED",
        )


class HistoryTests(unittest.TestCase):
    def test_28_new_finding_set(self) -> None:
        _, snapshot, plan = built()
        self.assertEqual(writer.determine_history_state(plan, snapshot), "NEW_FINDING_SET")

    def test_29_exact_already_applied(self) -> None:
        _, snapshot, plan = built()
        self.assertEqual(writer.determine_history_state(plan, persisted_snapshot(snapshot, plan)), "EXACT_ALREADY_APPLIED")

    def test_30_partial_finding_set_conflict(self) -> None:
        _, snapshot, plan = built()
        persisted = persisted_snapshot(snapshot, plan)
        persisted = replace(persisted, finding_rows=persisted.finding_rows[:-1])
        with self.assertRaises(writer.HistoryConflictError):
            writer.determine_history_state(plan, persisted)

    def test_31_unrelated_history_allowed(self) -> None:
        _, snapshot, plan = built()
        unrelated = ({"set_key": "cm-finding-set-v1:" + "a" * 64},)
        self.assertEqual(writer.determine_history_state(plan, replace(snapshot, manifests=unrelated)), "NEW_FINDING_SET")

    def test_32_finding_key_tied_to_other_set_conflicts(self) -> None:
        _, snapshot, plan = built()
        row = {"finding_key": plan.findings[0]["finding_key"], "finding_set_id": str(uuid.uuid4())}
        with self.assertRaises(writer.HistoryConflictError):
            writer.determine_history_state(plan, replace(snapshot, finding_rows=(row,)))

    def test_33_zero_finding_new_set(self) -> None:
        _, snapshot, plan = built()
        zero_manifest = dict(plan.manifest, expected_findings_count=0)
        zero = replace(plan, manifest=zero_manifest, findings=(), query_contexts=0, observation_sides_resolved=0, single_query_findings=0, multi_query_findings=0)
        self.assertEqual(writer.determine_history_state(zero, snapshot), "NEW_FINDING_SET")

    def test_34_zero_finding_already_applied(self) -> None:
        _, snapshot, plan = built()
        zero_manifest = dict(plan.manifest, expected_findings_count=0)
        zero = replace(plan, manifest=zero_manifest, findings=(), query_contexts=0, observation_sides_resolved=0, single_query_findings=0, multi_query_findings=0)
        existing = replace(snapshot, manifests=({name: writer._normalise(value) for name, value in zero_manifest.items()},))
        self.assertEqual(writer.determine_history_state(zero, existing), "EXACT_ALREADY_APPLIED")


class SafetyAndTransactionTests(unittest.TestCase):
    def test_35_write_without_env_gate_rejected(self) -> None:
        with self.assertRaises(writer.ConfigurationError):
            writer.validate_write_gate(True, {})

    def test_36_env_gate_without_write_does_not_enable_write(self) -> None:
        writer.validate_write_gate(False, {writer.WRITE_GATE: "true"})
        args = writer.parse_arguments(["--findings", str(ARTIFACT), "--findings-sha256", LEGACY_FINDINGS_SHA256, "--analysis-sha256", LEGACY_ANALYSIS_SHA256])
        self.assertFalse(args.write)

    def test_37_dry_run_zero_inserts(self) -> None:
        bundle, snapshot, _ = built()
        result = writer.run_dry_run(bundle, snapshot)
        self.assertEqual((result.inserts, result.updates, result.deletes), (0, 0, 0))

    def test_38_no_mutating_sql_constructs(self) -> None:
        source = (ROOT / "Scripts" / "persist_competitor_findings_v1.py").read_text(encoding="utf-8")
        self.assertNotIn("ON " + "CONFLICT", source.upper())
        self.assertNotIn("\nUPDATE ", source.upper())
        self.assertNotIn("\nDELETE ", source.upper())
        self.assertNotIn("uuid4", source)

    def test_39_insert_sql_is_exact_scope(self) -> None:
        self.assertIn("competitor_finding_sets", writer.MANIFEST_INSERT_SQL)
        self.assertIn("competitor_findings", writer.FINDING_INSERT_SQL)

    def test_40_post_write_count_validation_via_exact_history(self) -> None:
        _, snapshot, plan = built()
        exact = persisted_snapshot(snapshot, plan)
        self.assertEqual(writer.determine_history_state(plan, exact), "EXACT_ALREADY_APPLIED")

    def test_41_write_transaction_rollback_on_failure(self) -> None:
        class Connection:
            def __init__(self) -> None:
                self.rolled_back = False

            def cursor(self):
                class Cursor:
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def execute(self, *args): return None
                return Cursor()

            def rollback(self) -> None: self.rolled_back = True
            def commit(self) -> None: raise AssertionError("commit must not happen")

        connection = Connection()
        with patch.object(writer, "load_artifact", side_effect=writer.InputContractError("stop")):
            with self.assertRaises(writer.InputContractError):
                writer.execute_write(connection, ARTIFACT, LEGACY_FINDINGS_SHA256, LEGACY_ANALYSIS_SHA256)
        self.assertTrue(connection.rolled_back)

    def test_42_already_applied_causes_zero_inserts(self) -> None:
        bundle, snapshot, plan = built()
        existing = persisted_snapshot(snapshot, plan)

        class Connection:
            def __init__(self) -> None: self.rolled_back = False
            def cursor(self):
                class Cursor:
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def execute(self, *args): return None
                return Cursor()
            def rollback(self) -> None: self.rolled_back = True
            def commit(self) -> None: raise AssertionError("commit must not happen")

        connection = Connection()
        with patch.object(writer, "load_artifact", return_value=bundle), patch.object(writer, "read_reference_snapshot", return_value=snapshot), patch.object(writer, "build_plan", return_value=plan), patch.object(writer, "read_history", return_value=existing), patch.object(writer, "_insert_plan") as insert:
            result = writer.execute_write(connection, ARTIFACT, LEGACY_FINDINGS_SHA256, LEGACY_ANALYSIS_SHA256)
        insert.assert_not_called()
        self.assertEqual(result.inserts, 0)
        self.assertTrue(connection.rolled_back)

    def test_43_real_psycopg2_uuid_adapter(self) -> None:
        from psycopg2.extensions import adapt

        writer._register_psycopg2_uuid(None)
        value = writer.deterministic_uuid(LEGACY_SET_KEY)
        quoted = adapt(value).getquoted()
        self.assertIn(str(value).encode("ascii"), quoted)
        self.assertTrue(quoted.endswith(b"::uuid"))

    def test_44_actual_insert_uuid_parameters_are_psycopg2_adaptable(self) -> None:
        from psycopg2.extensions import adapt

        writer._register_psycopg2_uuid(None)
        _, _, plan = built()
        manifest_values = writer._manifest_insert_parameters(plan)
        finding_values = writer._finding_insert_parameters(plan)
        manifest_uuids = [value for value in manifest_values if isinstance(value, uuid.UUID)]
        finding_uuids = [
            value
            for values in finding_values
            for value in values
            if isinstance(value, uuid.UUID)
        ]

        self.assertEqual(len(finding_values), 10)
        self.assertEqual(len(manifest_uuids), 1)
        self.assertEqual(len(finding_uuids), 48)
        self.assertTrue(all(adapt(value).getquoted() for value in manifest_uuids))
        self.assertTrue(all(adapt(value).getquoted() for value in finding_uuids))

    def test_45_production_reads_use_only_approved_mcp_surfaces(self) -> None:
        source = "\n".join(writer.APPROVED_READ_SQL)
        self.assertNotRegex(source, r"(?i)\b(?:FROM|JOIN)\s+public\.competitor_")
        self.assertIn("mcp_read.competitor_snapshot_observations", source)
        self.assertIn("mcp_read.competitor_snapshot_runs", source)
        self.assertIn("mcp_read.competitor_reference_plan_source", source)
        self.assertIn("mcp_read.competitor_finding_sets_reconciliation", source)
        self.assertIn("mcp_read.competitor_findings", source)

    def test_46_history_reads_all_reconciliation_manifests(self) -> None:
        self.assertNotIn("WHERE", writer.FINDING_SET_RECONCILIATION_SQL.upper())
        self.assertTrue(all("INSERT INTO" not in query.upper() for query in writer.APPROVED_READ_SQL))


if __name__ == "__main__":
    unittest.main()
