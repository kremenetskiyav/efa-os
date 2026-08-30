from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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


UTC = timezone.utc


class Connection:
    def __init__(self) -> None:
        self.closed = False
        self.rollbacks = 0

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def writer_snapshot() -> writer.ProductionSnapshot:
    return writer.ProductionSnapshot(
        observations={},
        listings={},
        offers=frozenset(),
        schema_columns={key: frozenset(value) for key, value in writer.REQUIRED_SCHEMA_COLUMNS.items()},
        constraint_names=writer.REQUIRED_CONSTRAINTS,
        index_names=writer.REQUIRED_INDEXES,
        history_counts={"search_runs": 0, "observations": 0, "reviews": 0, "findings": 0, "finding_sets": 0},
    )


def empty_batch(kind: str, reference: datetime) -> analyzer.SnapshotBatch:
    ref = "cm-baseline-v1:run:a" if kind == "BASELINE_V1" else "cm-snapshot-v1:run:b"
    return analyzer.SnapshotBatch(
        source_kind=kind,
        derived_batch_id=analyzer._derived_batch_id((ref,)),
        reference_at=reference,
        captured_through=reference,
        region_key=builder.EXPECTED_REGION_KEY,
        run_ids=(kind,),
        collection_refs=(ref,),
        rows=(),
    )


def empty_analysis(previous: analyzer.SnapshotBatch, current: analyzer.SnapshotBatch) -> dict:
    return {
        "contract_version": analyzer.CONTRACT_VERSION,
        "current_snapshot": current.metadata(),
        "previous_snapshot": previous.metadata(),
        "source_table_counts": {"search_runs": 0, "observations": 0, "reviews": 0, "findings": 0},
        "summary": {"slots_total": 0},
        "per_sku_summary": {},
        "control_listings_summary": {},
        "comparisons": [],
    }


class DailyCycleTests(unittest.TestCase):
    def test_01_result_contract_has_required_fields(self) -> None:
        result = cycle.blank_result("attempt", "2026-08-28T00:00:00.000Z")
        required = {
            "cycle_id", "attempt_id", "status", "started_at", "finished_at",
            "region_label", "region_key", "expected_queries", "completed_queries",
            "expected_slots", "captured_slots", "found_count", "not_found_count",
            "unique_enrichments", "evidence_sha256", "payload_sha256", "batch_ref",
            "import_state", "current_snapshot_id", "current_reference_at",
            "previous_snapshot_id", "previous_reference_at", "analysis_sha256",
            "finding_set_key", "finding_count", "persistence_state", "final_status",
            "failure_category", "failure_message_sanitized",
        }
        self.assertTrue(required.issubset(result))
        self.assertEqual(result["contract_version"], cycle.RESULT_CONTRACT)

    def test_02_cycle_id_is_deterministic(self) -> None:
        args = ("a" * 64, "b" * 64, "cm-snapshot-v1:batch:x")
        self.assertEqual(cycle.deterministic_cycle_id(*args), cycle.deterministic_cycle_id(*args))

    def test_03_attempt_id_is_not_part_of_cycle_identity(self) -> None:
        identity = cycle.deterministic_cycle_id("a" * 64, "b" * 64, "batch")
        first = cycle.blank_result("one", "x")
        second = cycle.blank_result("two", "y")
        first["cycle_id"] = second["cycle_id"] = identity
        self.assertEqual(first["cycle_id"], second["cycle_id"])

    def test_04_failure_message_is_sanitized(self) -> None:
        message = cycle.sanitize_failure(RuntimeError("password=hunter2 DATABASE_URL=postgres://secret"))
        self.assertNotIn("hunter2", message)
        self.assertNotIn("postgres://secret", message)

    def test_05_owner_database_role_rejected(self) -> None:
        with self.assertRaises(snapshot_importer.ConfigurationError):
            cycle.assert_read_only_identity("efa")

    def test_06_non_owner_role_accepted_for_connection_verification(self) -> None:
        cycle.assert_read_only_identity("efa_mcp_readonly")

    def test_07_dynamic_expected_queries(self) -> None:
        snapshot = importer_tests.reference_snapshot()
        resolver = cycle.expected_queries_resolver(snapshot)
        reference = datetime.fromisoformat(importer_tests.REFERENCE_AT.replace("Z", "+00:00"))
        self.assertEqual(set(resolver(reference)), {("УФ 001Б", "OEM-A"), ("УФ 002Б", "OEM-B")})

    def test_08_planned_current_rows_keep_exact_batch_identity(self) -> None:
        evidence, plan = builder_tests.fixture()
        evidence_sha = builder_tests.evidence_hash(evidence)
        payload = builder.build_payload(evidence, evidence_sha, plan)
        with TemporaryDirectory() as folder:
            evidence_path = Path(folder) / "e.json"
            payload_path = Path(folder) / "p.json"
            evidence_path.write_bytes(builder.canonical_pretty_bytes(evidence))
            payload_bytes, payload_sha, _ = builder.payload_identity(payload, evidence_sha)
            payload_path.write_bytes(payload_bytes)
            bundle = snapshot_importer.load_and_validate_artifacts(payload_path, evidence_path, payload_sha, evidence_sha)
        import_plan = snapshot_importer.build_import_plan(bundle, importer_tests.reference_snapshot())
        rows = cycle.planned_current_history_rows(import_plan, importer_tests.reference_snapshot())
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["collection_ref"] for row in rows}, {row["collection_ref"] for row in import_plan.search_rows})

    def test_09_source_counts_are_stable_for_selected_current(self) -> None:
        self.assertIs(cycle.deterministic_source_counts, analyzer.deterministic_source_counts)
        current = empty_batch("SNAPSHOT_V1", datetime(2026, 8, 26, tzinfo=UTC))
        rows = [
            {"run_captured_at": datetime(2026, 8, 25, tzinfo=UTC), "search_run_id": "a", "observation_id": "1"},
            {"run_captured_at": datetime(2026, 8, 27, tzinfo=UTC), "search_run_id": "b", "observation_id": "2"},
        ]
        self.assertEqual(cycle.deterministic_source_counts(rows, current)["search_runs"], 1)
        self.assertEqual(cycle.deterministic_source_counts(rows, current)["findings"], 0)

    def test_10_calendar_gap_is_not_a_failure(self) -> None:
        rows = []
        for kind, start in (("BASELINE_V1", datetime(2026, 8, 1, tzinfo=UTC)), ("SNAPSHOT_V1", datetime(2026, 8, 20, tzinfo=UTC))):
            for index in range(2):
                rows.append({
                    "search_run_id": f"{kind}-{index}", "offer_id": "УФ 001Б", "query_text_exact": f"Q{index}",
                    "region_key": builder.EXPECTED_REGION_KEY, "location_label": builder.EXPECTED_LOCATION_LABEL,
                    "run_captured_at": start + timedelta(seconds=index), "run_status": "SUCCESS",
                    "collection_ref": ("cm-baseline-v1:run:" if kind == "BASELINE_V1" else "cm-snapshot-v1:run:") + str(index),
                    "observation_id": f"{kind}-obs-{index}", "ozon_product_id": str(index + 1), "captured_at": start + timedelta(seconds=index),
                    "quality_status": "NOT_FOUND", "quality_flags": ["NOT_FOUND_WITHIN_SCAN_LIMIT"], "membership_status": "PRIMARY",
                })
        previous, current = analyzer.resolve_snapshot_pair(rows, current_collection_refs=("cm-snapshot-v1:run:0", "cm-snapshot-v1:run:1"), expected_queries_at=lambda _at: (("УФ 001Б", "Q0"), ("УФ 001Б", "Q1")))
        self.assertGreater(current.reference_at - previous.reference_at, timedelta(days=18))

    def test_11_no_write_flag_exists(self) -> None:
        source = (SCRIPTS / "run_competitor_daily_cycle_v1.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"add_argument\([^\n]*--write")
        self.assertNotIn("COMPETITOR_SNAPSHOT_WRITE_ENABLED", source)

    def test_12_no_browser_work_or_collector_dependency(self) -> None:
        source = (SCRIPTS / "run_competitor_daily_cycle_v1.py").read_text(encoding="utf-8")
        imports = "\n".join(line for line in source.splitlines() if line.startswith(("import ", "from ")))
        self.assertNotRegex(imports, r"playwright|selenium|browser|competitor_collector")

    def test_13_orchestrator_runtime_has_no_mutating_sql(self) -> None:
        source = (SCRIPTS / "run_competitor_daily_cycle_v1.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b(?:INSERT\s+INTO|UPDATE\s+public|DELETE\s+FROM)\b", source, re.I))
        self.assertNotIn("ON CONFLICT", source.upper())

    def test_14_invalid_evidence_returns_nonzero_and_result(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            result, exit_code = cycle.run_cycle(path, None, None, {})
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(result["final_status"], "VALIDATION_FAILED")
        self.assertEqual(result["db_writes"], {"insert": 0, "update": 0, "delete": 0})

    def test_15_full_dry_run_invokes_importer_engine_and_writer(self) -> None:
        evidence, _ = builder_tests.fixture()
        snapshot = importer_tests.reference_snapshot()
        product_names = {membership.listing_id: "Fixture " + membership.ozon_product_id for membership in snapshot.memberships}
        previous = empty_batch("BASELINE_V1", datetime(2026, 8, 25, tzinfo=UTC))
        current = empty_batch("SNAPSHOT_V1", datetime(2026, 8, 26, tzinfo=UTC))
        database = Connection()
        config = snapshot_importer.DatabaseConfig("localhost", 5432, "efa", "efa_mcp_readonly", "unused")
        base_writer = writer_snapshot()
        with TemporaryDirectory() as folder:
            evidence_path = Path(folder) / "evidence.json"
            output_dir = Path(folder) / "out"
            evidence_path.write_bytes(builder.canonical_pretty_bytes(evidence))
            with (
                patch.object(snapshot_importer, "load_database_config", return_value=config),
                patch.object(snapshot_importer, "connect_database", return_value=database),
                patch.object(cycle, "verify_connection_read_only", return_value="efa_mcp_readonly"),
                patch.object(snapshot_importer, "read_production_snapshot", return_value=snapshot),
                patch.object(cycle, "product_names_from_snapshot", return_value=product_names),
                patch.object(snapshot_importer, "read_batch_history", return_value=snapshot),
                patch.object(snapshot_importer, "run_dry_run", wraps=snapshot_importer.run_dry_run) as importer_dry,
                patch.object(analyzer, "read_history", return_value=[]),
                patch.object(analyzer, "resolve_snapshot_pair", return_value=(previous, current)),
                patch.object(analyzer, "build_analysis", return_value=empty_analysis(previous, current)),
                patch.object(
                    writer, "read_reference_snapshot", return_value=base_writer
                ) as writer_read,
                patch.object(writer, "read_history", return_value=base_writer),
                patch.object(writer, "run_dry_run", wraps=writer.run_dry_run) as writer_dry,
            ):
                result, exit_code = cycle.run_cycle(evidence_path, output_dir, None, {})
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["final_status"], cycle.SUCCESS)
        importer_dry.assert_called_once()
        writer_dry.assert_called_once()
        self.assertIsNone(writer_read.call_args.args[2])
        self.assertEqual(result["finding_count"], 0)

    def test_16_same_evidence_semantic_result_is_stable(self) -> None:
        evidence, plan = builder_tests.fixture()
        digest = builder_tests.evidence_hash(evidence)
        payload = builder.build_payload(evidence, digest, plan)
        _, payload_sha, batch_ref = builder.payload_identity(payload, digest)
        identity = cycle.deterministic_cycle_id(digest, payload_sha, batch_ref)
        self.assertEqual(identity, cycle.deterministic_cycle_id(digest, payload_sha, batch_ref))

    def test_17_runtime_read_path_has_no_raw_competitor_sql(self) -> None:
        queries = (
            *snapshot_importer.APPROVED_READ_SQL,
            *analyzer.APPROVED_READ_SQL,
            *writer.APPROVED_READ_SQL,
        )
        source = "\n".join(queries)
        self.assertNotRegex(source, r"(?i)\b(?:FROM|JOIN)\s+public\.competitor_")
        orchestrator = (SCRIPTS / "run_competitor_daily_cycle_v1.py").read_text(
            encoding="utf-8"
        )
        self.assertNotRegex(
            orchestrator, r"(?i)\b(?:FROM|JOIN)\s+public\.competitor_"
        )

    def test_18_mcp_read_failure_has_no_raw_fallback_or_next_stage(self) -> None:
        evidence, _ = builder_tests.fixture()
        database = Connection()
        config = snapshot_importer.DatabaseConfig(
            "localhost", 5432, "efa", "efa_mcp_readonly", "unused"
        )
        with TemporaryDirectory() as folder:
            evidence_path = Path(folder) / "evidence.json"
            evidence_path.write_bytes(builder.canonical_pretty_bytes(evidence))
            with (
                patch.object(snapshot_importer, "load_database_config", return_value=config),
                patch.object(snapshot_importer, "connect_database", return_value=database),
                patch.object(cycle, "verify_connection_read_only", return_value="efa_mcp_readonly"),
                patch.object(
                    snapshot_importer,
                    "read_production_snapshot",
                    side_effect=snapshot_importer.DatabaseError("mcp_read unavailable"),
                ) as failed_read,
                patch.object(snapshot_importer, "read_batch_history") as import_history,
                patch.object(analyzer, "read_history") as analysis_history,
                patch.object(writer, "read_reference_snapshot") as writer_read,
            ):
                result, exit_code = cycle.run_cycle(evidence_path, None, None, {})
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(result["final_status"], "VALIDATION_FAILED")
        self.assertEqual(result["db_writes"], {"insert": 0, "update": 0, "delete": 0})
        self.assertNotIn("password", result["failure_message_sanitized"].lower())
        failed_read.assert_called_once()
        import_history.assert_not_called()
        analysis_history.assert_not_called()
        writer_read.assert_not_called()

    def test_19_superuser_identity_is_rejected(self) -> None:
        with self.assertRaises(snapshot_importer.ConfigurationError):
            cycle.assert_read_only_identity("runtime", is_superuser=True)

    def test_20_new_batch_passes_exact_import_plan_to_writer(self) -> None:
        evidence, _ = builder_tests.fixture()
        snapshot = importer_tests.reference_snapshot()
        product_names = {
            membership.listing_id: "Fixture " + membership.ozon_product_id
            for membership in snapshot.memberships
        }
        previous = empty_batch("BASELINE_V1", datetime(2026, 8, 25, tzinfo=UTC))
        current = empty_batch("SNAPSHOT_V1", datetime(2026, 8, 26, tzinfo=UTC))
        database = Connection()
        config = snapshot_importer.DatabaseConfig(
            "localhost", 5432, "efa", "efa_mcp_readonly", "unused"
        )
        base_writer = writer_snapshot()
        finding_set = {
            "contract_version": "fixture",
            "findings": [{"fixture": True}],
        }
        finding_bundle = writer.ArtifactBundle(
            report=finding_set,
            findings_sha256="b" * 64,
            semantic_sha256="c" * 64,
            analysis_sha256="a" * 64,
        )
        persistence_plan = writer.PersistencePlan(
            manifest={"set_key": "cm-finding-set-v1:fixture"},
            findings=({"fixture": True},),
            query_contexts=1,
            observation_sides_resolved=2,
            single_query_findings=1,
            multi_query_findings=0,
        )
        persistence_result = writer.PersistenceResult(
            "NEW_FINDING_SET", persistence_plan
        )
        with TemporaryDirectory() as folder:
            evidence_path = Path(folder) / "evidence.json"
            output_dir = Path(folder) / "out"
            evidence_path.write_bytes(builder.canonical_pretty_bytes(evidence))
            with (
                patch.object(snapshot_importer, "load_database_config", return_value=config),
                patch.object(snapshot_importer, "connect_database", return_value=database),
                patch.object(cycle, "verify_connection_read_only", return_value="efa_mcp_readonly"),
                patch.object(snapshot_importer, "read_production_snapshot", return_value=snapshot),
                patch.object(cycle, "product_names_from_snapshot", return_value=product_names),
                patch.object(snapshot_importer, "read_batch_history", return_value=snapshot),
                patch.object(analyzer, "read_history", return_value=[]),
                patch.object(analyzer, "resolve_snapshot_pair", return_value=(previous, current)),
                patch.object(analyzer, "build_analysis", return_value=empty_analysis(previous, current)),
                patch.object(cycle.finding_engine, "build_evidence_index", return_value={}),
                patch.object(cycle.finding_engine, "generate_finding_set", return_value=finding_set),
                patch.object(writer, "load_artifact", return_value=finding_bundle),
                patch.object(writer, "read_reference_snapshot", return_value=base_writer) as writer_read,
                patch.object(writer, "build_plan", return_value=persistence_plan),
                patch.object(writer, "read_history", return_value=base_writer),
                patch.object(writer, "run_dry_run", return_value=persistence_result),
            ):
                result, exit_code = cycle.run_cycle(
                    evidence_path, output_dir, None, {}
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["final_status"], cycle.SUCCESS)
        inputs = writer_read.call_args.args[2]
        self.assertIsInstance(inputs, writer.CurrentObservationInputs)
        self.assertIsInstance(inputs.artifact, snapshot_importer.ArtifactBundle)
        self.assertIsInstance(inputs.import_plan, snapshot_importer.ImportPlan)
        self.assertIs(inputs.import_history, snapshot)
        self.assertIs(inputs.current_snapshot, current)

    def test_21_exact_import_uses_persisted_current_without_inputs(self) -> None:
        evidence, _ = builder_tests.fixture()
        snapshot = importer_tests.reference_snapshot()
        product_names = {
            membership.listing_id: "Fixture " + membership.ozon_product_id
            for membership in snapshot.memberships
        }
        previous = empty_batch("BASELINE_V1", datetime(2026, 8, 25, tzinfo=UTC))
        current = empty_batch("SNAPSHOT_V1", datetime(2026, 8, 26, tzinfo=UTC))
        database = Connection()
        config = snapshot_importer.DatabaseConfig(
            "localhost", 5432, "efa", "efa_mcp_readonly", "unused"
        )
        base_writer = writer_snapshot()
        finding_set = {
            "contract_version": "fixture",
            "findings": [{"fixture": True}],
        }
        finding_bundle = writer.ArtifactBundle(
            report=finding_set,
            findings_sha256="b" * 64,
            semantic_sha256="c" * 64,
            analysis_sha256="a" * 64,
        )
        persistence_plan = writer.PersistencePlan(
            manifest={"set_key": "cm-finding-set-v1:fixture"},
            findings=({"fixture": True},),
            query_contexts=1,
            observation_sides_resolved=2,
            single_query_findings=1,
            multi_query_findings=0,
        )
        persistence_result = writer.PersistenceResult(
            "EXACT_ALREADY_APPLIED", persistence_plan
        )
        with TemporaryDirectory() as folder:
            evidence_path = Path(folder) / "evidence.json"
            output_dir = Path(folder) / "out"
            evidence_path.write_bytes(builder.canonical_pretty_bytes(evidence))
            with (
                patch.object(snapshot_importer, "load_database_config", return_value=config),
                patch.object(snapshot_importer, "connect_database", return_value=database),
                patch.object(cycle, "verify_connection_read_only", return_value="efa_mcp_readonly"),
                patch.object(snapshot_importer, "read_production_snapshot", return_value=snapshot),
                patch.object(cycle, "product_names_from_snapshot", return_value=product_names),
                patch.object(snapshot_importer, "read_batch_history", return_value=snapshot),
                patch.object(
                    snapshot_importer,
                    "run_dry_run",
                    return_value=SimpleNamespace(history_state="EXACT_ALREADY_APPLIED"),
                ),
                patch.object(analyzer, "read_history", return_value=[]),
                patch.object(analyzer, "resolve_snapshot_pair", return_value=(previous, current)),
                patch.object(analyzer, "build_analysis", return_value=empty_analysis(previous, current)),
                patch.object(cycle.finding_engine, "build_evidence_index", return_value={}),
                patch.object(cycle.finding_engine, "generate_finding_set", return_value=finding_set),
                patch.object(writer, "load_artifact", return_value=finding_bundle),
                patch.object(
                    writer, "read_reference_snapshot", return_value=base_writer
                ) as writer_read,
                patch.object(writer, "build_plan", return_value=persistence_plan),
                patch.object(writer, "read_history", return_value=base_writer),
                patch.object(writer, "run_dry_run", return_value=persistence_result),
            ):
                result, exit_code = cycle.run_cycle(
                    evidence_path, output_dir, None, {}
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["final_status"], cycle.SUCCESS)
        self.assertEqual(result["import_state"], "EXACT_ALREADY_APPLIED")
        self.assertIsNone(writer_read.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
