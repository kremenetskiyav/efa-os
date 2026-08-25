"""Focused tests for the one-shot Competitor Monitor baseline importer."""

from __future__ import annotations

import copy
import inspect
import io
import sys
import unittest
import uuid
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import import_competitor_baseline_v1 as importer  # noqa: E402


PAYLOAD_PATH = REPOSITORY_ROOT / "BASELINE_PAYLOAD_V1_PROVENANCE_R2.json"
EVIDENCE_PATH = REPOSITORY_ROOT / "BASELINE_EVIDENCE_V1.json"
ARTIFACTS_AVAILABLE = PAYLOAD_PATH.is_file() and EVIDENCE_PATH.is_file()


def load_bundle() -> importer.ArtifactBundle:
    return importer.load_and_validate_artifacts(
        PAYLOAD_PATH,
        EVIDENCE_PATH,
        importer.EXPECTED_PAYLOAD_SHA256,
        importer.EXPECTED_EVIDENCE_SHA256,
    )


def schema_fixture() -> dict[str, tuple[importer.SchemaColumn, ...]]:
    search_required = {
        "offer_id",
        "query_kind",
        "query_text_exact",
        "query_normalized",
        "region_key",
        "captured_at",
        "status",
        "collection_ref",
    }
    observation_required = {
        "search_run_id",
        "listing_id",
        "captured_at",
        "reviews_scope",
        "availability_status",
        "quality_status",
        "source_ref",
        "observation_ref",
    }

    def columns(names: tuple[str, ...], required: set[str]) -> tuple[importer.SchemaColumn, ...]:
        result = []
        for name in names:
            result.append(
                importer.SchemaColumn(
                    name=name,
                    nullable=name not in required,
                    has_default=False,
                    data_type="uuid" if name in {"search_run_id", "observation_id"} else "text",
                )
            )
        result.append(importer.SchemaColumn("created_at", False, True, "timestamp with time zone"))
        return tuple(result)

    return {
        "competitor_search_runs": columns(importer.SEARCH_INSERT_COLUMNS, search_required),
        "competitor_observations": columns(
            importer.OBSERVATION_INSERT_COLUMNS, observation_required
        ),
    }


def empty_snapshot(bundle: importer.ArtifactBundle) -> importer.ProductionSnapshot:
    payload = bundle.payload
    profiles = {offer: "ACTIVE" for offer, _ in importer.EXPECTED_QUERIES}
    profiles["УФ 003Б"] = "HOLD"
    oems = tuple(
        importer.SkuOemReference(
            sku_oem_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"oem:{offer}:{query}")),
            offer_id=offer,
            oem_normalized=query,
            active=True,
        )
        for offer, query in sorted(importer.EXPECTED_QUERIES)
    )
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in payload["observations"]:
        grouped.setdefault((row["offer_id"], str(row["ozon_product_id"])), []).append(row)
    memberships = []
    for (offer_id, product_id), rows in sorted(grouped.items()):
        statuses = {str(row["membership_status"]) for row in rows}
        assert len(statuses) == 1
        observed_sellers = {
            str(row["seller_id_observed"])
            for row in rows
            if row["seller_id_observed"] is not None
        }
        memberships.append(
            importer.MembershipReference(
                membership_id=str(
                    uuid.uuid5(uuid.NAMESPACE_URL, f"membership:{offer_id}:{product_id}")
                ),
                offer_id=offer_id,
                membership_status=statuses.pop(),
                matched_oem_set=tuple(sorted({str(row["query_text_exact"]) for row in rows})),
                listing_id=str(
                    uuid.uuid5(uuid.NAMESPACE_URL, f"listing:{offer_id}:{product_id}")
                ),
                ozon_product_id=product_id,
                seller_id=next(iter(observed_sellers), None),
            )
        )
    assert len(memberships) == 41
    return importer.ProductionSnapshot(
        profiles=profiles,
        oems=oems,
        memberships=tuple(memberships),
        history_counts={"search_runs": 0, "observations": 0, "reviews": 0, "findings": 0},
        search_rows=(),
        observation_rows=(),
        schema_columns=schema_fixture(),
        constraint_names=frozenset(importer.REQUIRED_CONSTRAINTS),
        index_names=frozenset(importer.REQUIRED_INDEXES),
    )


class _Cursor:
    def __init__(self, connection: "_Connection") -> None:
        self.connection = connection

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, parameters: tuple[object, ...] = ()) -> None:
        self.connection.queries.append(query)


class _Connection:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


@unittest.skipUnless(ARTIFACTS_AVAILABLE, "external immutable baseline artifacts are absent")
class ArtifactAndPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_bundle()
        cls.snapshot = empty_snapshot(cls.bundle)
        cls.plan = importer.build_import_plan(cls.bundle, cls.snapshot)

    def test_canonical_batch_digest_exact(self) -> None:
        self.assertEqual(
            importer.build_batch_ref(
                importer.EXPECTED_EVIDENCE_SHA256,
                importer.EXPECTED_PAYLOAD_SHA256,
            ),
            importer.EXPECTED_BATCH_REF,
        )

    def test_nine_collection_refs_are_unique(self) -> None:
        refs = [row["collection_ref"] for row in self.plan.search_rows]
        self.assertEqual((len(refs), len(set(refs))), (9, 9))

    def test_eighty_seven_observation_refs_are_unique(self) -> None:
        refs = [row["observation_ref"] for row in self.plan.observation_rows]
        self.assertEqual((len(refs), len(set(refs))), (87, 87))

    def test_uuid5_is_deterministic(self) -> None:
        ref = self.plan.search_rows[0]["collection_ref"]
        self.assertEqual(importer.build_search_run_id(ref), importer.build_search_run_id(ref))
        self.assertEqual(importer.build_search_run_id(ref), str(uuid.uuid5(uuid.NAMESPACE_URL, ref)))

    def test_wrong_payload_hash_is_rejected(self) -> None:
        with self.assertRaises(importer.ArtifactError):
            importer.load_and_validate_artifacts(
                PAYLOAD_PATH, EVIDENCE_PATH, "0" * 64, importer.EXPECTED_EVIDENCE_SHA256
            )

    def test_wrong_evidence_hash_is_rejected(self) -> None:
        with self.assertRaises(importer.ArtifactError):
            importer.load_and_validate_artifacts(
                PAYLOAD_PATH, EVIDENCE_PATH, importer.EXPECTED_PAYLOAD_SHA256, "0" * 64
            )

    def test_payload_evidence_mismatch_is_rejected(self) -> None:
        payload = copy.deepcopy(self.bundle.payload)
        payload["observations"][0]["enrichment_captured_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaises(importer.ArtifactError):
            importer._validate_evidence_resolution(payload, self.bundle.evidence)

    def test_reviews_scope_contract_is_enforced(self) -> None:
        payload = copy.deepcopy(self.bundle.payload)
        payload["observations"][0]["reviews_scope"] = "SEARCH"
        with self.assertRaises(importer.ArtifactError):
            importer._validate_payload(payload, importer.EXPECTED_EVIDENCE_SHA256)

    def test_exact_counts(self) -> None:
        self.assertEqual(len(self.plan.search_rows), 9)
        self.assertEqual(len(self.plan.observation_rows), 87)
        self.assertEqual((self.plan.found, self.plan.not_found), (50, 37))

    def test_not_found_mapping(self) -> None:
        rows = [row for row in self.plan.observation_rows if row["rank"] is None]
        self.assertEqual(len(rows), 37)
        for row in rows:
            self.assertIsNone(row["enrichment_captured_at"])
            self.assertIsNone(row["raw_ref"])
            self.assertEqual(row["reviews_scope"], "UNKNOWN")
            self.assertEqual(row["availability_status"], "UNKNOWN")
            self.assertIn("NOT_FOUND_WITHIN_SCAN_LIMIT", row["quality_flags"])

    def test_found_dual_timestamps(self) -> None:
        rows = [row for row in self.plan.observation_rows if row["raw_ref"] is not None]
        self.assertEqual(len(rows), 50)
        self.assertTrue(all(row["captured_at"] is not None for row in rows))
        self.assertTrue(all(row["enrichment_captured_at"] is not None for row in rows))

    def test_raw_ref_resolution(self) -> None:
        importer._validate_evidence_resolution(self.bundle.payload, self.bundle.evidence)

    def test_static_reference_mismatch_aborts(self) -> None:
        broken = replace(self.snapshot, memberships=self.snapshot.memberships[:-1])
        with self.assertRaises(importer.ReconciliationError):
            importer.build_import_plan(self.bundle, broken)

    def test_empty_history_state(self) -> None:
        self.assertEqual(
            importer.determine_history_state(self.plan, self.snapshot), "EMPTY_HISTORY"
        )

    def test_exact_already_applied_state(self) -> None:
        applied = replace(
            self.snapshot,
            history_counts={"search_runs": 9, "observations": 87, "reviews": 0, "findings": 0},
            search_rows=self.plan.search_rows,
            observation_rows=self.plan.observation_rows,
        )
        self.assertEqual(
            importer.determine_history_state(self.plan, applied),
            "EXACT_ALREADY_APPLIED",
        )

    def test_partial_history_conflict(self) -> None:
        partial = replace(
            self.snapshot,
            history_counts={"search_runs": 1, "observations": 0, "reviews": 0, "findings": 0},
        )
        with self.assertRaises(importer.HistoryConflictError):
            importer.determine_history_state(self.plan, partial)

    def test_dry_run_executes_zero_writes(self) -> None:
        result = importer.run_dry_run(self.bundle, self.snapshot)
        self.assertEqual((result.inserts, result.updates, result.deletes), (0, 0, 0))

    def test_transaction_failure_rolls_back(self) -> None:
        connection = _Connection()
        with patch.object(importer, "read_production_snapshot", return_value=self.snapshot), patch.object(
            importer, "_insert_plan", side_effect=RuntimeError("simulated insert failure")
        ):
            with self.assertRaises(RuntimeError):
                importer.execute_write(
                    connection,
                    payload_path=PAYLOAD_PATH,
                    evidence_path=EVIDENCE_PATH,
                    payload_sha256=importer.EXPECTED_PAYLOAD_SHA256,
                    evidence_sha256=importer.EXPECTED_EVIDENCE_SHA256,
                )
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_exact_already_applied_write_is_noop(self) -> None:
        connection = _Connection()
        applied = replace(
            self.snapshot,
            history_counts={"search_runs": 9, "observations": 87, "reviews": 0, "findings": 0},
            search_rows=self.plan.search_rows,
            observation_rows=self.plan.observation_rows,
        )
        with patch.object(importer, "read_production_snapshot", return_value=applied), patch.object(
            importer, "_insert_plan"
        ) as insert_plan:
            result = importer.execute_write(
                connection,
                payload_path=PAYLOAD_PATH,
                evidence_path=EVIDENCE_PATH,
                payload_sha256=importer.EXPECTED_PAYLOAD_SHA256,
                evidence_sha256=importer.EXPECTED_EVIDENCE_SHA256,
            )
        self.assertEqual(result.history_state, "EXACT_ALREADY_APPLIED")
        insert_plan.assert_not_called()
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_successful_write_commits_only_after_exact_postcheck(self) -> None:
        connection = _Connection()
        applied = replace(
            self.snapshot,
            history_counts={"search_runs": 9, "observations": 87, "reviews": 0, "findings": 0},
            search_rows=self.plan.search_rows,
            observation_rows=self.plan.observation_rows,
        )
        with patch.object(
            importer, "read_production_snapshot", side_effect=[self.snapshot, applied]
        ), patch.object(importer, "_insert_plan") as insert_plan:
            result = importer.execute_write(
                connection,
                payload_path=PAYLOAD_PATH,
                evidence_path=EVIDENCE_PATH,
                payload_sha256=importer.EXPECTED_PAYLOAD_SHA256,
                evidence_sha256=importer.EXPECTED_EVIDENCE_SHA256,
            )
        self.assertEqual(result.history_state, "APPLIED")
        self.assertEqual(result.inserts, 96)
        insert_plan.assert_called_once()
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)

    def test_evidence_only_fields_are_not_inserted(self) -> None:
        forbidden = {
            "search_price_raw",
            "search_availability_raw",
            "seller_name_observed",
            "seller_id_observed",
            "price_evidence_status",
            "termination_reason",
        }
        self.assertTrue(forbidden.isdisjoint(importer.SEARCH_INSERT_COLUMNS))
        self.assertTrue(forbidden.isdisjoint(importer.OBSERVATION_INSERT_COLUMNS))


class GateAndImplementationTests(unittest.TestCase):
    def test_write_without_env_gate_is_rejected(self) -> None:
        with self.assertRaises(importer.ConfigurationError):
            importer.validate_write_gate(True, {})

    def test_env_gate_without_write_does_not_authorize_write(self) -> None:
        importer.validate_write_gate(False, {importer.WRITE_GATE: "true"})

    def test_default_cli_mode_is_dry_run(self) -> None:
        args = importer.parse_arguments(
            [
                "--payload",
                "payload.json",
                "--evidence",
                "evidence.json",
                "--payload-sha256",
                "a",
                "--evidence-sha256",
                "b",
            ]
        )
        self.assertFalse(args.write)

    def test_no_random_uuid_in_importer(self) -> None:
        source = inspect.getsource(importer)
        self.assertNotIn("uuid.uuid4(", source)
        self.assertIn("uuid.uuid5(", source)


@unittest.skipUnless(ARTIFACTS_AVAILABLE, "external immutable baseline artifacts are absent")
class MainDryRunTests(unittest.TestCase):
    def test_env_gate_without_write_runs_read_only(self) -> None:
        bundle = load_bundle()
        snapshot = empty_snapshot(bundle)
        connection = _Connection()
        environment = {
            "EFA_DB_HOST": "localhost",
            "EFA_DB_PORT": "5432",
            "EFA_DB_NAME": "efa",
            "EFA_DB_USER": "readonly-test",
            "EFA_DB_PASSWORD": "test-only",
            importer.WRITE_GATE: "true",
        }
        argv = [
            "--payload",
            str(PAYLOAD_PATH),
            "--evidence",
            str(EVIDENCE_PATH),
            "--payload-sha256",
            importer.EXPECTED_PAYLOAD_SHA256,
            "--evidence-sha256",
            importer.EXPECTED_EVIDENCE_SHA256,
            "--dry-run",
        ]
        with patch.object(importer, "read_production_snapshot", return_value=snapshot), redirect_stdout(
            io.StringIO()
        ):
            exit_code = importer.main(
                argv,
                environment=environment,
                connection_factory=lambda _: connection,
            )
        self.assertEqual(exit_code, 0)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertFalse(any("INSERT" in query.upper() for query in connection.queries))


if __name__ == "__main__":
    unittest.main()
