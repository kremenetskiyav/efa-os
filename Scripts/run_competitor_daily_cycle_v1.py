"""Semi-automated Competitor Monitor daily cycle v1 (dry-run only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import analyze_competitor_snapshots_v1 as analyzer
import build_competitor_snapshot_artifacts_v1 as builder
import generate_competitor_findings_v1 as finding_engine
import import_competitor_snapshot_v1 as snapshot_importer
import persist_competitor_findings_v1 as finding_writer


RESULT_CONTRACT = "competitor_daily_cycle_result.v1"
SUCCESS = "DRY_RUN_SUCCESS"
FAILURE_STATUSES = {
    "VALIDATION_FAILED",
    "IMPORT_CONFLICT",
    "ANALYSIS_FAILED",
    "ENGINE_FAILED",
    "PERSISTENCE_CONFLICT",
    "INTERNAL_ERROR",
}
FORBIDDEN_DATABASE_USERS = frozenset({"efa", "postgres"})


class DailyCycleError(RuntimeError):
    pass


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_json(path: Path, value: Mapping[str, Any], *, sorted_keys: bool = True) -> str:
    rendered = (
        json.dumps(value, ensure_ascii=False, sort_keys=sorted_keys, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    path.write_bytes(rendered)
    return hashlib.sha256(rendered).hexdigest()


def sanitize_failure(error: BaseException) -> str:
    message = str(error).replace("\r", " ").replace("\n", " ")
    message = re.sub(
        r"(?i)(password|token|secret|dsn|database_url|api[_-]?key)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        message,
    )
    message = re.sub(r"[A-Za-z]:\\[^\s]+", "[LOCAL_PATH]", message)
    return message[:500] or error.__class__.__name__


def deterministic_cycle_id(evidence_sha256: str, payload_sha256: str, batch_ref: str) -> str:
    identity = {
        "contract": RESULT_CONTRACT,
        "evidence_sha256": evidence_sha256,
        "payload_sha256": payload_sha256,
        "batch_ref": batch_ref,
    }
    digest = hashlib.sha256(builder.canonical_sorted_bytes(identity)).hexdigest()
    return f"cm-daily-cycle-v1:{digest}"


def blank_result(attempt_id: str, started_at: str) -> dict[str, Any]:
    return {
        "contract_version": RESULT_CONTRACT,
        "cycle_id": None,
        "attempt_id": attempt_id,
        "status": "INTERNAL_ERROR",
        "started_at": started_at,
        "finished_at": None,
        "region_label": None,
        "region_key": None,
        "expected_queries": 0,
        "completed_queries": 0,
        "expected_slots": 0,
        "captured_slots": 0,
        "found_count": 0,
        "not_found_count": 0,
        "unique_enrichments": 0,
        "evidence_sha256": None,
        "evidence_path": None,
        "evidence_size_bytes": 0,
        "evidence_contract": None,
        "collection_source": None,
        "collection_method": None,
        "payload_sha256": None,
        "batch_ref": None,
        "import_state": None,
        "current_snapshot_id": None,
        "current_reference_at": None,
        "previous_snapshot_id": None,
        "previous_reference_at": None,
        "analysis_sha256": None,
        "finding_set_key": None,
        "finding_count": 0,
        "persistence_state": None,
        "final_status": "INTERNAL_ERROR",
        "failure_category": None,
        "failure_message_sanitized": None,
        "db_writes": {"insert": 0, "update": 0, "delete": 0},
    }


def product_names_from_snapshot(
    snapshot: snapshot_importer.ProductionSnapshot,
) -> dict[str, str]:
    names: dict[str, str] = {}
    for membership in snapshot.memberships:
        if not membership.product_name:
            raise snapshot_importer.ReferenceConflictError(
                "Reference plan lacks a product name"
            )
        existing = names.setdefault(membership.listing_id, membership.product_name)
        if existing != membership.product_name:
            raise snapshot_importer.ReferenceConflictError(
                "Reference plan has inconsistent product names"
            )
    return names


def assert_read_only_identity(user: str, *, is_superuser: bool = False) -> None:
    if user.strip().lower() in FORBIDDEN_DATABASE_USERS or is_superuser:
        raise snapshot_importer.ConfigurationError(
            "Daily cycle refuses a PostgreSQL owner or superuser credential"
        )


def verify_connection_read_only(connection: Any) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT current_user, current_database(),
                      current_setting('transaction_read_only'), rolsuper
                 FROM pg_catalog.pg_roles
                WHERE rolname = current_user"""
        )
        user, database, read_only, is_superuser = cursor.fetchone()
    assert_read_only_identity(str(user), is_superuser=bool(is_superuser))
    if str(database) != "efa":
        raise snapshot_importer.ConfigurationError(
            "Daily cycle requires the efa database"
        )
    if str(read_only).lower() != "on":
        raise snapshot_importer.ConfigurationError(
            "PostgreSQL transaction is not read-only"
        )
    return str(user)


def expected_queries_resolver(
    snapshot: snapshot_importer.ProductionSnapshot,
):
    def resolve(reference_at: datetime) -> tuple[tuple[str, str], ...]:
        layer = snapshot_importer.derive_reference_layer(snapshot, reference_at)
        return tuple(layer.oem_by_query)

    return resolve


def planned_current_history_rows(
    plan: snapshot_importer.ImportPlan,
    snapshot: snapshot_importer.ProductionSnapshot,
) -> list[dict[str, Any]]:
    searches = {str(row["search_run_id"]): row for row in plan.search_rows}
    memberships = {reference.membership_id: reference for reference in snapshot.memberships}
    rows: list[dict[str, Any]] = []
    for observation in plan.observation_rows:
        search = searches[str(observation["search_run_id"])]
        membership = memberships[str(observation["membership_id"])]
        rows.append(
            {
                "search_run_id": str(search["search_run_id"]),
                "offer_id": search["offer_id"],
                "query_text_exact": search["query_text_exact"],
                "region_key": search["region_key"],
                "location_label": search.get("location_label"),
                "run_captured_at": search["captured_at"],
                "run_status": search["status"],
                "collection_ref": search["collection_ref"],
                "raw_source_ref": search["raw_source_ref"],
                "observation_id": str(observation["observation_id"]),
                "observation_ref": observation["observation_ref"],
                "listing_id": str(observation["listing_id"]),
                "source_ref": observation["source_ref"],
                "raw_ref": observation.get("raw_ref"),
                "ozon_product_id": membership.ozon_product_id,
                "membership_status": membership.membership_status,
                "captured_at": observation["captured_at"],
                "enrichment_captured_at": observation.get("enrichment_captured_at"),
                "page_number": observation.get("page_number"),
                "position_on_page": observation.get("position_on_page"),
                "rank": observation.get("rank"),
                "ad_flag": observation.get("ad_flag"),
                "bank_price": observation.get("bank_price"),
                "other_payment_price": observation.get("other_payment_price"),
                "old_price": observation.get("old_price"),
                "currency": observation.get("currency"),
                "rating": observation.get("rating"),
                "reviews_count_observed": observation.get("reviews_count_observed"),
                "reviews_scope": observation.get("reviews_scope"),
                "purchase_count_observed": observation.get("purchase_count_observed"),
                "purchase_indicator_raw": observation.get("purchase_indicator_raw"),
                "availability_status": observation.get("availability_status"),
                "availability_raw": observation.get("availability_raw"),
                "observed_oem_raw": observation.get("observed_oem_raw"),
                "observed_dimensions_raw": observation.get("observed_dimensions_raw"),
                "observed_length_mm": observation.get("observed_length_mm"),
                "observed_width_mm": observation.get("observed_width_mm"),
                "observed_height_mm": observation.get("observed_height_mm"),
                "carbon_claim_raw": observation.get("carbon_claim_raw"),
                "origin_raw": observation.get("origin_raw"),
                "quality_status": observation.get("quality_status"),
                "quality_flags": observation.get("quality_flags"),
            }
        )
    return rows


deterministic_source_counts = analyzer.deterministic_source_counts


def _emit_result(result: Mapping[str, Any], output_dir: Path | None) -> None:
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / "COMPETITOR_DAILY_CYCLE_RESULT_V1.json", result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


def run_cycle(
    evidence_path: Path,
    output_dir: Path | None,
    required_evidence_sha256: str | None,
    environment: Mapping[str, str],
) -> tuple[dict[str, Any], int]:
    started_at = utc_now_text()
    attempt_id = str(uuid.uuid4())
    result = blank_result(attempt_id, started_at)
    connection = None
    stage = "VALIDATION"
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        evidence, evidence_sha256, evidence_size = builder.load_immutable_evidence(
            evidence_path, required_evidence_sha256
        )
        reference_at = builder.validate_evidence(evidence)
        result.update(
            {
                "evidence_sha256": evidence_sha256,
                "evidence_path": str(evidence_path.resolve()),
                "evidence_size_bytes": evidence_size,
                "evidence_contract": evidence["contract_version"],
                "collection_source": evidence["batch"]["source"],
                "collection_method": evidence["batch"]["collection_method"],
                "region_label": evidence["batch"]["location_label"],
                "region_key": evidence["batch"]["region_key"],
                "completed_queries": len(evidence["search_evidence"]),
            }
        )

        config = snapshot_importer.load_database_config(environment)
        assert_read_only_identity(config.user)
        connection = snapshot_importer.connect_database(config, read_only=True)
        verify_connection_read_only(connection)
        snapshot = snapshot_importer.read_production_snapshot(connection, reference_at)
        product_names = product_names_from_snapshot(snapshot)
        reference_plan = builder.freeze_reference_plan(snapshot, reference_at, product_names)
        payload = builder.build_payload(evidence, evidence_sha256, reference_plan)
        payload_bytes, payload_sha256, batch_ref = builder.payload_identity(
            payload, evidence_sha256
        )
        result.update(
            {
                "cycle_id": deterministic_cycle_id(evidence_sha256, payload_sha256, batch_ref),
                "expected_queries": reference_plan["expected_queries"],
                "expected_slots": reference_plan["expected_slots"],
                "captured_slots": len(payload["observations"]),
                "found_count": sum(row["slot_status"] == "FOUND" for row in payload["observations"]),
                "not_found_count": sum(
                    row["slot_status"] == "NOT_FOUND_WITHIN_SCAN_LIMIT"
                    for row in payload["observations"]
                ),
                "unique_enrichments": len(payload["enrichments"]),
                "payload_sha256": payload_sha256,
                "batch_ref": batch_ref,
            }
        )

        artifact_dir: Path
        if output_dir is None:
            temporary = tempfile.TemporaryDirectory(prefix="efa-competitor-daily-cycle-")
            artifact_dir = Path(temporary.name)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            artifact_dir = output_dir
        plan_path = artifact_dir / "COMPETITOR_SNAPSHOT_REFERENCE_PLAN_V1.json"
        payload_path = artifact_dir / "COMPETITOR_SNAPSHOT_PAYLOAD_V1.json"
        write_json(plan_path, reference_plan)
        payload_path.write_bytes(payload_bytes)
        bundle = snapshot_importer.load_and_validate_artifacts(
            payload_path,
            evidence_path,
            payload_sha256,
            evidence_sha256,
        )

        stage = "IMPORT"
        import_plan = snapshot_importer.build_import_plan(bundle, snapshot)
        import_history = snapshot_importer.read_batch_history(connection, import_plan, snapshot)
        import_result = snapshot_importer.run_dry_run(bundle, import_history)
        if import_result.history_state not in {"NEW_BATCH", "EXACT_ALREADY_APPLIED"}:
            raise snapshot_importer.BatchConflictError(import_result.history_state)
        result["import_state"] = import_result.history_state
        connection.rollback()

        stage = "ANALYSIS"
        history_rows = analyzer.read_history(connection)
        if import_result.history_state == "NEW_BATCH":
            history_rows.extend(planned_current_history_rows(import_plan, snapshot))
        current_refs = tuple(str(row["collection_ref"]) for row in import_plan.search_rows)
        previous_batch, current_batch = analyzer.resolve_snapshot_pair(
            history_rows,
            current_collection_refs=current_refs,
            expected_queries_at=expected_queries_resolver(snapshot),
        )
        counts = deterministic_source_counts(history_rows, current_batch)
        analysis = analyzer.build_analysis(previous_batch, current_batch, counts)
        analysis_path = artifact_dir / "COMPETITOR_SNAPSHOT_ANALYSIS_V1.json"
        analysis_sha256 = write_json(analysis_path, analysis)
        result.update(
            {
                "current_snapshot_id": current_batch.derived_batch_id,
                "current_reference_at": current_batch.metadata()["reference_at"],
                "previous_snapshot_id": previous_batch.derived_batch_id,
                "previous_reference_at": previous_batch.metadata()["reference_at"],
                "analysis_sha256": analysis_sha256,
            }
        )
        connection.rollback()

        stage = "ENGINE"
        evidence_index = finding_engine.build_evidence_index(
            analysis, previous_batch.rows, current_batch.rows
        )
        finding_set = finding_engine.generate_finding_set(
            analysis, analysis_sha256, evidence_index
        )
        finding_set["production_read_only_check"] = {
            "before": counts,
            "after": counts,
        }
        findings_path = artifact_dir / "COMPETITOR_FINDING_SET_V1.json"
        findings_sha256 = write_json(findings_path, finding_set)

        stage = "PERSISTENCE"
        finding_bundle = finding_writer.load_artifact(
            findings_path, findings_sha256, analysis_sha256
        )
        base = finding_writer.read_reference_snapshot(connection, finding_bundle.report)
        persistence_plan = finding_writer.build_plan(finding_bundle, base)
        persisted = finding_writer.read_history(connection, persistence_plan, base)
        persistence_result = finding_writer.run_dry_run(finding_bundle, persisted)
        if persistence_result.history_state not in {
            "NEW_FINDING_SET",
            "EXACT_ALREADY_APPLIED",
        }:
            raise finding_writer.HistoryConflictError(persistence_result.history_state)
        result.update(
            {
                "finding_set_key": persistence_plan.manifest["set_key"],
                "finding_count": len(finding_set["findings"]),
                "persistence_state": persistence_result.history_state,
                "status": SUCCESS,
                "final_status": SUCCESS,
            }
        )
        connection.rollback()
        result["finished_at"] = utc_now_text()
        _emit_result(result, output_dir)
        return result, 0
    except Exception as error:
        categories = {
            "VALIDATION": "VALIDATION_FAILED",
            "IMPORT": "IMPORT_CONFLICT",
            "ANALYSIS": "ANALYSIS_FAILED",
            "ENGINE": "ENGINE_FAILED",
            "PERSISTENCE": "PERSISTENCE_CONFLICT",
        }
        status = categories.get(stage, "INTERNAL_ERROR")
        if status not in FAILURE_STATUSES:
            status = "INTERNAL_ERROR"
        result.update(
            {
                "status": status,
                "final_status": status,
                "failure_category": error.__class__.__name__,
                "failure_message_sanitized": sanitize_failure(error),
                "finished_at": utc_now_text(),
            }
        )
        _emit_result(result, output_dir)
        return result, 1
    finally:
        if connection is not None:
            connection.close()
        if temporary is not None:
            temporary.cleanup()


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Competitor Monitor daily cycle v1 dry-run")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--evidence-sha256")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> int:
    args = parse_arguments(argv)
    _, exit_code = run_cycle(
        args.evidence,
        args.output_dir,
        args.evidence_sha256,
        os.environ if environment is None else environment,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
