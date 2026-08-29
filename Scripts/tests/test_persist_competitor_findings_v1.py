from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "Scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import persist_competitor_findings_v1 as writer


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
