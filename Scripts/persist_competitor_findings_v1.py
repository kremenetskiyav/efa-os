"""Deterministic, fail-closed persistence writer for Competitor Finding Engine v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


PERSISTENCE_CONTRACT = "competitor-finding-persistence.v1"
SET_IDENTITY_CONTRACT = "competitor-finding-set-persistence.v1"
FINDING_SET_CONTRACT = "competitor_finding_set.v1"
ANALYSIS_CONTRACT = "competitor_snapshot_analysis.v1"
DETAILS_CONTRACT = "competitor_finding_details.v1"
WRITE_GATE = "COMPETITOR_FINDINGS_WRITE_ENABLED"
ADVISORY_LOCK_KEY = "efa-os:competitor-findings-persist:v1"

APPROVED_FINDINGS_SHA256 = "3202131a109e04c1a05dcb735f33190b75a76ab596bd6921fbafd7b7e0c8fbcd"
APPROVED_SEMANTIC_SHA256 = "7fbf7c23a285749733d6beaaba7602701c3d47af04d793f0978a600fd5919e47"
APPROVED_ANALYSIS_SHA256 = "99483c51928b7073f00cfc2f93c2fcafd52e25a94676774091b21740f24e03dd"
APPROVED_SET_KEY = "cm-finding-set-v1:097963f537b2a32a919d325698ca099889aa8ab08b4dbc8367e1e0684f520f7b"

MANIFEST_COLUMNS = (
    "finding_set_id", "set_key", "persistence_contract_version",
    "finding_set_contract_version", "source_analysis_contract_version",
    "source_findings_sha256", "source_findings_semantic_sha256",
    "source_analysis_sha256", "previous_source_kind",
    "previous_derived_batch_id", "previous_reference_at",
    "previous_captured_through", "current_source_kind",
    "current_derived_batch_id", "current_reference_at",
    "current_captured_through", "expected_findings_count",
)
FINDING_COLUMNS = (
    "finding_id", "finding_set_id", "finding_kind", "offer_id",
    "product_family_id", "listing_id", "old_observation_id",
    "new_observation_id", "topic", "metric", "severity", "confidence",
    "status", "evidence", "details", "finding_key", "first_detected_at",
    "last_detected_at",
)
REQUIRED_SCHEMA_COLUMNS = {
    "competitor_finding_sets": frozenset((*MANIFEST_COLUMNS, "applied_at", "created_at")),
    "competitor_findings": frozenset((*FINDING_COLUMNS, "created_at", "updated_at")),
}
REQUIRED_CONSTRAINTS = frozenset(
    {
        "competitor_finding_sets_pkey",
        "competitor_finding_sets_set_key_key",
        "competitor_finding_sets_snapshot_pair_key",
        "competitor_finding_sets_values_check",
        "competitor_finding_sets_hashes_check",
        "competitor_finding_sets_timestamps_check",
        "competitor_finding_sets_expected_count_check",
        "competitor_findings_pkey",
        "competitor_findings_finding_key_key",
        "competitor_findings_finding_set_id_fkey",
        "competitor_findings_offer_id_fkey",
        "competitor_findings_product_family_id_fkey",
        "competitor_findings_listing_id_fkey",
        "competitor_findings_old_observation_id_fkey",
        "competitor_findings_new_observation_id_fkey",
        "competitor_findings_kind_check",
        "competitor_findings_values_check",
        "competitor_findings_observations_check",
        "competitor_findings_timestamps_check",
    }
)
REQUIRED_INDEXES = frozenset(
    {
        "competitor_finding_sets_pkey",
        "competitor_finding_sets_set_key_key",
        "competitor_finding_sets_snapshot_pair_key",
        "competitor_finding_sets_current_reference_at_idx",
        "competitor_findings_pkey",
        "competitor_findings_finding_key_key",
        "competitor_findings_offer_kind_status_last_idx",
        "competitor_findings_finding_set_id_idx",
    }
)


class PersistenceError(RuntimeError):
    pass


class InputContractError(PersistenceError):
    pass


class ReferenceConflictError(PersistenceError):
    pass


class HistoryConflictError(PersistenceError):
    pass


class ConfigurationError(PersistenceError):
    pass


class DatabaseError(PersistenceError):
    pass


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class ArtifactBundle:
    report: Mapping[str, Any]
    findings_sha256: str
    semantic_sha256: str
    analysis_sha256: str


@dataclass(frozen=True)
class ProductionSnapshot:
    observations: Mapping[str, Mapping[str, Any]]
    listings: Mapping[str, Mapping[str, Any]]
    offers: frozenset[str]
    schema_columns: Mapping[str, frozenset[str]]
    constraint_names: frozenset[str]
    index_names: frozenset[str]
    manifests: tuple[Mapping[str, Any], ...] = ()
    finding_rows: tuple[Mapping[str, Any], ...] = ()
    history_counts: Mapping[str, int] | None = None


@dataclass(frozen=True)
class PersistencePlan:
    manifest: Mapping[str, Any]
    findings: tuple[Mapping[str, Any], ...]
    query_contexts: int
    observation_sides_resolved: int
    single_query_findings: int
    multi_query_findings: int
    fk_failures: int = 0
    constraint_violations: int = 0
    missing_required_values: int = 0
    unique_conflicts: int = 0


@dataclass(frozen=True)
class PersistenceResult:
    history_state: str
    plan: PersistencePlan
    inserts: int = 0
    updates: int = 0
    deletes: int = 0


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def semantic_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    names = (
        "contract_version", "source_analysis_contract", "source_analysis_sha256",
        "previous_snapshot", "current_snapshot", "summary", "findings",
        "suppressed_events",
    )
    if any(name not in report for name in names):
        raise InputContractError("Finding artifact lacks semantic projection fields")
    return {name: report[name] for name in names}


def semantic_sha256(report: Mapping[str, Any]) -> str:
    return _sha256(semantic_projection(report))


def _snapshot_identity(snapshot: Mapping[str, Any]) -> dict[str, str]:
    try:
        return {
            "source_kind": str(snapshot["source_kind"]),
            "derived_batch_id": str(snapshot["derived_batch_id"]),
        }
    except KeyError as error:
        raise InputContractError("Snapshot identity is incomplete") from error


def set_identity_document(report: Mapping[str, Any], semantic_digest: str) -> dict[str, Any]:
    return {
        "contract": SET_IDENTITY_CONTRACT,
        "finding_contract": report["contract_version"],
        "previous_snapshot": _snapshot_identity(report["previous_snapshot"]),
        "current_snapshot": _snapshot_identity(report["current_snapshot"]),
        "source_analysis_sha256": report["source_analysis_sha256"],
        "finding_set_semantic_sha256": semantic_digest,
    }


def build_set_key(report: Mapping[str, Any], semantic_digest: str) -> str:
    return "cm-finding-set-v1:" + _sha256(set_identity_document(report, semantic_digest))


def finding_identity_document(report: Mapping[str, Any], finding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract": PERSISTENCE_CONTRACT,
        "finding_contract": report["contract_version"],
        "previous_snapshot": _snapshot_identity(report["previous_snapshot"]),
        "current_snapshot": _snapshot_identity(report["current_snapshot"]),
        "engine_dedup_key": finding["dedup_key"],
    }


def build_finding_key(report: Mapping[str, Any], finding: Mapping[str, Any]) -> str:
    return "cm-finding-v1:" + _sha256(finding_identity_document(report, finding))


def deterministic_uuid(key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, key)


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise InputContractError(f"{field} must be an RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InputContractError(f"{field} is malformed") from error
    if parsed.tzinfo is None:
        raise InputContractError(f"{field} lacks timezone")
    return parsed.astimezone(timezone.utc)


def _validate_report(report: Mapping[str, Any]) -> None:
    if report.get("contract_version") != FINDING_SET_CONTRACT:
        raise InputContractError("Finding-set contract mismatch")
    if report.get("source_analysis_contract") != ANALYSIS_CONTRACT:
        raise InputContractError("Analysis contract mismatch")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise InputContractError("Findings must be an array")
    dedup = []
    for finding in findings:
        required = (
            "finding_type", "finding_kind", "offer_id", "listing_id",
            "ozon_product_id", "membership_status", "query_context",
            "observation_refs", "evidence_refs", "metric", "severity",
            "confidence", "status", "summary", "dedup_key",
        )
        if any(name not in finding for name in required):
            raise InputContractError("Finding lacks required values")
        expected = f"{finding['finding_type']}|{finding['offer_id']}|{finding['ozon_product_id']}"
        if finding["dedup_key"] != expected:
            raise InputContractError("Engine dedup key mismatch")
        if finding["status"] != "PROPOSED":
            raise InputContractError("Finding status must remain PROPOSED")
        contexts = finding["query_context"]
        if not isinstance(contexts, list) or not contexts:
            raise InputContractError("Finding query context is empty")
        if len(contexts) != len(finding["observation_refs"]) or len(contexts) != len(finding["evidence_refs"]):
            raise InputContractError("Finding evidence cardinality mismatch")
        queries = [row.get("query_text_exact") for row in contexts]
        if len(queries) != len(set(queries)) or any(not value for value in queries):
            raise InputContractError("Finding query contexts are not unique")
        dedup.append(finding["dedup_key"])
    if len(dedup) != len(set(dedup)):
        raise InputContractError("Finding dedup keys are not unique")
    if report.get("summary", {}).get("findings_total") != len(findings):
        raise InputContractError("Finding summary total mismatch")


def load_artifact(path: Path, findings_sha256_gate: str, analysis_sha256_gate: str) -> ArtifactBundle:
    raw = path.read_bytes()
    raw_digest = hashlib.sha256(raw).hexdigest()
    if findings_sha256_gate.lower() != APPROVED_FINDINGS_SHA256 or raw_digest != findings_sha256_gate.lower():
        raise InputContractError("Finding artifact SHA-256 mismatch")
    if analysis_sha256_gate.lower() != APPROVED_ANALYSIS_SHA256:
        raise InputContractError("Canonical analysis SHA-256 gate mismatch")
    try:
        report = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InputContractError("Finding artifact is not readable UTF-8 JSON") from error
    _validate_report(report)
    if report["source_analysis_sha256"] != analysis_sha256_gate.lower():
        raise InputContractError("Finding artifact analysis SHA-256 mismatch")
    semantic_digest = semantic_sha256(report)
    if semantic_digest != APPROVED_SEMANTIC_SHA256:
        raise InputContractError("Finding-set semantic SHA-256 mismatch")
    if build_set_key(report, semantic_digest) != APPROVED_SET_KEY:
        raise InputContractError("Finding-set identity assertion mismatch")
    return ArtifactBundle(report, raw_digest, semantic_digest, report["source_analysis_sha256"])


def _query_map(rows: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    result = {str(row.get("query_text_exact")): row for row in rows}
    if len(result) != len(rows) or "None" in result:
        raise InputContractError(f"{label} query mapping is invalid")
    return result


def _validate_observation(
    expected: Mapping[str, Any], actual: Mapping[str, Any], *, side: str,
    finding: Mapping[str, Any], query: str,
) -> None:
    prefix = "cm-baseline-v1:run:" if side == "previous" else "cm-snapshot-v1:run:"
    checks = {
        "observation_id": expected[f"{side}_observation_id"],
        "observation_ref": expected[f"{side}_observation_ref"],
        "offer_id": finding["offer_id"],
        "query_text_exact": query,
        "ozon_product_id": str(finding["ozon_product_id"]),
        "listing_id": str(finding["listing_id"]),
    }
    for name, value in checks.items():
        if str(actual.get(name)) != str(value):
            raise ReferenceConflictError(f"Observation {side} {name} mismatch")
    if not str(actual.get("collection_ref", "")).startswith(prefix):
        raise ReferenceConflictError(f"Observation {side} snapshot mismatch")


def _evidence_item(
    query: str, observations: Mapping[str, Any], evidence: Mapping[str, Any]
) -> dict[str, Any]:
    previous = evidence["previous"]
    current = evidence["current"]
    return {
        "query_text_exact": query,
        "previous_observation_id": observations["previous_observation_id"],
        "current_observation_id": observations["current_observation_id"],
        "previous_observation_ref": observations["previous_observation_ref"],
        "current_observation_ref": observations["current_observation_ref"],
        "previous_source_ref": previous.get("source_ref"),
        "current_source_ref": current.get("source_ref"),
        "previous_raw_ref": previous.get("raw_ref"),
        "current_raw_ref": current.get("raw_ref"),
        "previous_raw_source_ref": previous.get("raw_source_ref"),
        "current_raw_source_ref": current.get("raw_source_ref"),
    }


def _normalise(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Mapping):
        return {key: _normalise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return value


def _rows_match(planned: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    return all(name in actual and _normalise(value) == _normalise(actual[name]) for name, value in planned.items())


def validate_schema(snapshot: ProductionSnapshot) -> None:
    for table, required in REQUIRED_SCHEMA_COLUMNS.items():
        if required != snapshot.schema_columns.get(table, frozenset()):
            raise ReferenceConflictError(f"Production schema has unexpected {table} columns")
    if REQUIRED_CONSTRAINTS != snapshot.constraint_names:
        raise ReferenceConflictError("Production schema constraint set differs from Migration 022")
    if REQUIRED_INDEXES != snapshot.index_names:
        raise ReferenceConflictError("Production schema index set differs from Migration 022")


def build_plan(bundle: ArtifactBundle, snapshot: ProductionSnapshot) -> PersistencePlan:
    validate_schema(snapshot)
    report = bundle.report
    set_key = build_set_key(report, bundle.semantic_sha256)
    set_id = deterministic_uuid(set_key)
    previous = report["previous_snapshot"]
    current = report["current_snapshot"]
    previous_at = _parse_timestamp(previous["reference_at"], "previous reference_at")
    previous_through = _parse_timestamp(previous["captured_through"], "previous captured_through")
    current_at = _parse_timestamp(current["reference_at"], "current reference_at")
    current_through = _parse_timestamp(current["captured_through"], "current captured_through")
    if previous_through < previous_at or current_through < current_at or current_at <= previous_at:
        raise InputContractError("Snapshot timestamp order mismatch")
    manifest = {
        "finding_set_id": set_id,
        "set_key": set_key,
        "persistence_contract_version": PERSISTENCE_CONTRACT,
        "finding_set_contract_version": report["contract_version"],
        "source_analysis_contract_version": report["source_analysis_contract"],
        "source_findings_sha256": bundle.findings_sha256,
        "source_findings_semantic_sha256": bundle.semantic_sha256,
        "source_analysis_sha256": bundle.analysis_sha256,
        "previous_source_kind": previous["source_kind"],
        "previous_derived_batch_id": previous["derived_batch_id"],
        "previous_reference_at": previous_at,
        "previous_captured_through": previous_through,
        "current_source_kind": current["source_kind"],
        "current_derived_batch_id": current["derived_batch_id"],
        "current_reference_at": current_at,
        "current_captured_through": current_through,
        "expected_findings_count": len(report["findings"]),
    }
    rows: list[dict[str, Any]] = []
    query_total = 0
    single = 0
    multi = 0
    for finding in report["findings"]:
        listing_id = str(finding["listing_id"])
        listing = snapshot.listings.get(listing_id)
        if listing is None or str(listing.get("ozon_product_id")) != str(finding["ozon_product_id"]):
            raise ReferenceConflictError("Listing/product resolution mismatch")
        if str(listing.get("offer_id")) != str(finding["offer_id"]):
            raise ReferenceConflictError("Listing/offer resolution mismatch")
        if listing.get("membership_status") != finding["membership_status"]:
            raise ReferenceConflictError("Listing membership resolution mismatch")
        if finding["offer_id"] not in snapshot.offers or not listing.get("product_family_id"):
            raise ReferenceConflictError("Offer/family resolution mismatch")
        contexts = _query_map(finding["query_context"], "context")
        observation_refs = _query_map(finding["observation_refs"], "observation")
        evidence_refs = _query_map(finding["evidence_refs"], "evidence")
        if set(contexts) != set(observation_refs) or set(contexts) != set(evidence_refs):
            raise InputContractError("Finding query evidence sets differ")
        evidence_items = []
        for query in sorted(contexts):
            expected = observation_refs[query]
            evidence = evidence_refs[query]
            for side in ("previous", "current"):
                observation_id = str(expected[f"{side}_observation_id"])
                actual = snapshot.observations.get(observation_id)
                if actual is None:
                    raise ReferenceConflictError(f"Observation {side} is missing")
                _validate_observation(expected, actual, side=side, finding=finding, query=query)
                side_evidence = evidence[side]
                for field, actual_field in (
                    ("source_ref", "source_ref"), ("raw_ref", "raw_ref"),
                    ("raw_source_ref", "raw_source_ref"),
                ):
                    if side_evidence.get(field) != actual.get(actual_field):
                        raise ReferenceConflictError(f"Observation {side} {field} mismatch")
            evidence_items.append(_evidence_item(query, expected, evidence))
        query_total += len(contexts)
        is_single = len(contexts) == 1
        single += int(is_single)
        multi += int(not is_single)
        old_id = uuid.UUID(evidence_items[0]["previous_observation_id"]) if is_single else None
        new_id = uuid.UUID(evidence_items[0]["current_observation_id"]) if is_single else None
        finding_key = build_finding_key(report, finding)
        details = {
            "contract_version": DETAILS_CONTRACT,
            "finding_set_key": set_key,
            "finding_type": finding["finding_type"],
            "engine_dedup_key": finding["dedup_key"],
            "ozon_product_id": str(finding["ozon_product_id"]),
            "membership_status": finding["membership_status"],
            "previous_snapshot": previous,
            "current_snapshot": current,
            "metric": finding["metric"],
            "previous_value": finding.get("previous_value"),
            "current_value": finding.get("current_value"),
            "delta": finding.get("delta"),
            "delta_pct": finding.get("delta_pct"),
            "query_context": [contexts[name] for name in sorted(contexts)],
            "summary": finding["summary"],
            "source_analysis_contract": report["source_analysis_contract"],
            "source_analysis_sha256": bundle.analysis_sha256,
            "source_finding_set_sha256": bundle.findings_sha256,
            "finding_set_semantic_sha256": bundle.semantic_sha256,
        }
        rows.append(
            {
                "finding_id": deterministic_uuid(finding_key),
                "finding_set_id": set_id,
                "finding_kind": finding["finding_kind"],
                "offer_id": finding["offer_id"],
                "product_family_id": uuid.UUID(str(listing["product_family_id"])),
                "listing_id": uuid.UUID(listing_id),
                "old_observation_id": old_id,
                "new_observation_id": new_id,
                "topic": finding["finding_type"],
                "metric": finding["metric"],
                "severity": finding["severity"],
                "confidence": finding["confidence"],
                "status": finding["status"],
                "evidence": evidence_items,
                "details": details,
                "finding_key": finding_key,
                "first_detected_at": current_at,
                "last_detected_at": current_at,
            }
        )
    keys = [row["finding_key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise InputContractError("Planned finding keys are not unique")
    return PersistencePlan(
        manifest=manifest,
        findings=tuple(rows),
        query_contexts=query_total,
        observation_sides_resolved=query_total * 2,
        single_query_findings=single,
        multi_query_findings=multi,
    )


def determine_history_state(plan: PersistencePlan, snapshot: ProductionSnapshot) -> str:
    exact_manifest = [row for row in snapshot.manifests if row.get("set_key") == plan.manifest["set_key"]]
    pair_manifest = [
        row for row in snapshot.manifests
        if all(
            row.get(name) == plan.manifest[name]
            for name in (
                "finding_set_contract_version", "previous_source_kind",
                "previous_derived_batch_id", "current_source_kind",
                "current_derived_batch_id",
            )
        )
    ]
    planned_keys = {row["finding_key"] for row in plan.findings}
    present = [row for row in snapshot.finding_rows if row.get("finding_key") in planned_keys]
    if not exact_manifest and not pair_manifest and not present:
        return "NEW_FINDING_SET"
    if len(exact_manifest) == 1 and len(pair_manifest) == 1 and exact_manifest[0] is pair_manifest[0]:
        manifest = exact_manifest[0]
        persisted = [row for row in snapshot.finding_rows if str(row.get("finding_set_id")) == str(plan.manifest["finding_set_id"])]
        by_key = {row.get("finding_key"): row for row in persisted}
        if _rows_match(plan.manifest, manifest) and len(persisted) == len(plan.findings) and set(by_key) == planned_keys:
            if all(_rows_match(row, by_key[row["finding_key"]]) for row in plan.findings):
                return "EXACT_ALREADY_APPLIED"
    raise HistoryConflictError("PARTIAL_FINDING_SET_CONFLICT")


def _fetch_dicts(cursor: Any, query: str, parameters: tuple[object, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(query, parameters)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def read_reference_snapshot(connection: Any, report: Mapping[str, Any]) -> ProductionSnapshot:
    observation_ids = sorted(
        {
            str(ref[f"{side}_observation_id"])
            for finding in report["findings"]
            for ref in finding["observation_refs"]
            for side in ("previous", "current")
        }
    )
    listing_ids = sorted({str(finding["listing_id"]) for finding in report["findings"]})
    try:
        with connection.cursor() as cursor:
            observations = _fetch_dicts(
                cursor,
                """SELECT o.observation_id::text,o.observation_ref,o.listing_id::text,
                          o.source_ref,o.raw_ref,r.raw_source_ref,r.offer_id,
                          r.query_text_exact,r.collection_ref,l.ozon_product_id::text
                     FROM public.competitor_observations o
                     JOIN public.competitor_search_runs r ON r.search_run_id=o.search_run_id
                     JOIN public.competitor_listings l ON l.listing_id=o.listing_id
                    WHERE o.observation_id=ANY(%s::uuid[])""",
                (observation_ids,),
            )
            listings = _fetch_dicts(
                cursor,
                """SELECT l.listing_id::text,l.product_family_id::text,
                          l.ozon_product_id::text,m.offer_id,m.membership_status
                     FROM public.competitor_listings l
                     JOIN public.competitor_watchlist_memberships m ON m.listing_id=l.listing_id
                    WHERE l.listing_id=ANY(%s::uuid[])""",
                (listing_ids,),
            )
            offers = _fetch_dicts(cursor, "SELECT offer_id FROM public.products")
            columns = _fetch_dicts(
                cursor,
                """SELECT table_name,column_name FROM information_schema.columns
                    WHERE table_schema='public'
                      AND table_name IN ('competitor_finding_sets','competitor_findings')""",
            )
            constraints = _fetch_dicts(
                cursor,
                """SELECT con.conname FROM pg_constraint con
                     JOIN pg_class rel ON rel.oid=con.conrelid
                     JOIN pg_namespace nsp ON nsp.oid=rel.relnamespace
                    WHERE nsp.nspname='public'
                      AND rel.relname IN ('competitor_finding_sets','competitor_findings')""",
            )
            indexes = _fetch_dicts(
                cursor,
                """SELECT indexname FROM pg_indexes WHERE schemaname='public'
                      AND tablename IN ('competitor_finding_sets','competitor_findings')""",
            )
            counts = _fetch_dicts(
                cursor,
                """SELECT
                    (SELECT count(*) FROM public.competitor_search_runs) search_runs,
                    (SELECT count(*) FROM public.competitor_observations) observations,
                    (SELECT count(*) FROM public.competitor_reviews) reviews,
                    (SELECT count(*) FROM public.competitor_findings) findings,
                    (SELECT count(*) FROM public.competitor_finding_sets) finding_sets""",
            )[0]
    except Exception as error:
        raise DatabaseError("Read-only production reconciliation failed") from error
    schema: dict[str, set[str]] = {"competitor_finding_sets": set(), "competitor_findings": set()}
    for row in columns:
        schema[row["table_name"]].add(row["column_name"])
    return ProductionSnapshot(
        observations={row["observation_id"]: row for row in observations},
        listings={row["listing_id"]: row for row in listings},
        offers=frozenset(row["offer_id"] for row in offers),
        schema_columns={key: frozenset(value) for key, value in schema.items()},
        constraint_names=frozenset(row["conname"] for row in constraints),
        index_names=frozenset(row["indexname"] for row in indexes),
        history_counts={key: int(value) for key, value in counts.items()},
    )


def read_history(connection: Any, plan: PersistencePlan, base: ProductionSnapshot) -> ProductionSnapshot:
    keys = [row["finding_key"] for row in plan.findings]
    manifest = plan.manifest
    try:
        with connection.cursor() as cursor:
            manifests = _fetch_dicts(
                cursor,
                """SELECT finding_set_id::text,set_key,persistence_contract_version,
                          finding_set_contract_version,source_analysis_contract_version,
                          source_findings_sha256,source_findings_semantic_sha256,
                          source_analysis_sha256,previous_source_kind,
                          previous_derived_batch_id,previous_reference_at,
                          previous_captured_through,current_source_kind,
                          current_derived_batch_id,current_reference_at,
                          current_captured_through,expected_findings_count
                     FROM public.competitor_finding_sets
                    WHERE set_key=%s OR (
                      finding_set_contract_version=%s AND previous_source_kind=%s
                      AND previous_derived_batch_id=%s AND current_source_kind=%s
                      AND current_derived_batch_id=%s)""",
                (
                    manifest["set_key"], manifest["finding_set_contract_version"],
                    manifest["previous_source_kind"], manifest["previous_derived_batch_id"],
                    manifest["current_source_kind"], manifest["current_derived_batch_id"],
                ),
            )
            findings = _fetch_dicts(
                cursor,
                """SELECT finding_id::text,finding_set_id::text,finding_kind,offer_id,
                          product_family_id::text,listing_id::text,
                          old_observation_id::text,new_observation_id::text,topic,metric,
                          severity,confidence,status,evidence,details,finding_key,
                          first_detected_at,last_detected_at
                     FROM public.competitor_findings
                    WHERE finding_set_id=%s OR finding_key=ANY(%s::text[])""",
                (str(manifest["finding_set_id"]), keys),
            )
    except Exception as error:
        raise DatabaseError("Finding history lookup failed") from error
    return ProductionSnapshot(
        observations=base.observations, listings=base.listings, offers=base.offers,
        schema_columns=base.schema_columns, constraint_names=base.constraint_names,
        index_names=base.index_names, manifests=tuple(manifests),
        finding_rows=tuple(findings), history_counts=base.history_counts,
    )


MANIFEST_INSERT_SQL = """
INSERT INTO public.competitor_finding_sets (
    finding_set_id,set_key,persistence_contract_version,finding_set_contract_version,
    source_analysis_contract_version,source_findings_sha256,
    source_findings_semantic_sha256,source_analysis_sha256,previous_source_kind,
    previous_derived_batch_id,previous_reference_at,previous_captured_through,
    current_source_kind,current_derived_batch_id,current_reference_at,
    current_captured_through,expected_findings_count
) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""
FINDING_INSERT_SQL = """
INSERT INTO public.competitor_findings (
    finding_id,finding_set_id,finding_kind,offer_id,product_family_id,listing_id,
    old_observation_id,new_observation_id,topic,metric,severity,confidence,status,
    evidence,details,finding_key,first_detected_at,last_detected_at
) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
"""


def _manifest_insert_parameters(plan: PersistencePlan) -> tuple[Any, ...]:
    return tuple(plan.manifest[name] for name in MANIFEST_COLUMNS)


def _finding_insert_parameters(plan: PersistencePlan) -> list[tuple[Any, ...]]:
    return [
        tuple(
            json.dumps(
                row[name],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            if name in {"evidence", "details"}
            else row[name]
            for name in FINDING_COLUMNS
        )
        for row in plan.findings
    ]


def _insert_plan(connection: Any, plan: PersistencePlan) -> None:
    with connection.cursor() as cursor:
        cursor.execute(MANIFEST_INSERT_SQL, _manifest_insert_parameters(plan))
        values = _finding_insert_parameters(plan)
        if values:
            cursor.executemany(FINDING_INSERT_SQL, values)


def run_dry_run(bundle: ArtifactBundle, snapshot: ProductionSnapshot) -> PersistenceResult:
    plan = build_plan(bundle, snapshot)
    return PersistenceResult(determine_history_state(plan, snapshot), plan)


def execute_write(connection: Any, artifact_path: Path, findings_sha: str, analysis_sha: str) -> PersistenceResult:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (ADVISORY_LOCK_KEY,))
        bundle = load_artifact(artifact_path, findings_sha, analysis_sha)
        base = read_reference_snapshot(connection, bundle.report)
        plan = build_plan(bundle, base)
        before = read_history(connection, plan, base)
        state = determine_history_state(plan, before)
        if state == "EXACT_ALREADY_APPLIED":
            connection.rollback()
            return PersistenceResult(state, plan)
        if state != "NEW_FINDING_SET":
            raise HistoryConflictError("PARTIAL_FINDING_SET_CONFLICT")
        _insert_plan(connection, plan)
        after_base = read_reference_snapshot(connection, bundle.report)
        after_plan = build_plan(bundle, after_base)
        if not _rows_match(plan.manifest, after_plan.manifest) or len(after_plan.findings) != len(plan.findings):
            raise ReferenceConflictError("Reference layer changed during persistence")
        after = read_history(connection, plan, after_base)
        if determine_history_state(plan, after) != "EXACT_ALREADY_APPLIED":
            raise HistoryConflictError("Post-insert exact validation failed")
        connection.commit()
        return PersistenceResult("APPLIED", plan, inserts=1 + len(plan.findings))
    except Exception:
        connection.rollback()
        raise


def load_database_config(environment: Mapping[str, str]) -> DatabaseConfig:
    names = ("EFA_DB_HOST", "EFA_DB_PORT", "EFA_DB_NAME", "EFA_DB_USER", "EFA_DB_PASSWORD")
    if any(not environment.get(name) for name in names):
        raise ConfigurationError("Required EFA database environment is incomplete")
    try:
        port = int(environment["EFA_DB_PORT"])
    except ValueError as error:
        raise ConfigurationError("EFA_DB_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError("EFA_DB_PORT is outside the valid range")
    return DatabaseConfig(
        environment["EFA_DB_HOST"].strip(), port, environment["EFA_DB_NAME"].strip(),
        environment["EFA_DB_USER"].strip(), environment["EFA_DB_PASSWORD"],
    )


def _register_psycopg2_uuid(connection: Any) -> None:
    from psycopg2.extras import register_uuid

    register_uuid(conn_or_curs=connection)


def connect_database(config: DatabaseConfig, *, read_only: bool) -> Any:
    connection = None
    try:
        import psycopg2
        options = "-c statement_timeout=30000"
        if read_only:
            options += " -c default_transaction_read_only=on"
        connection = psycopg2.connect(
            host=config.host, port=config.port, dbname=config.name, user=config.user,
            password=config.password, connect_timeout=10, options=options,
        )
        _register_psycopg2_uuid(connection)
        return connection
    except Exception as error:
        if connection is not None:
            connection.close()
        raise DatabaseError("PostgreSQL connection failed") from error


def validate_write_gate(write: bool, environment: Mapping[str, str]) -> None:
    if write and environment.get(WRITE_GATE, "").strip().lower() != "true":
        raise ConfigurationError("Write requires --write and COMPETITOR_FINDINGS_WRITE_ENABLED=true")


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Competitor Finding Persistence v1")
    parser.add_argument("--findings", type=Path, required=True)
    parser.add_argument("--findings-sha256", required=True)
    parser.add_argument("--analysis-sha256", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="SELECT-only validation; default")
    mode.add_argument("--write", action="store_true", help="perform gated atomic persistence")
    return parser.parse_args(argv)


def print_result(result: PersistenceResult, bundle: ArtifactBundle) -> None:
    plan = result.plan
    print(f"FINDINGS_SHA256={bundle.findings_sha256}")
    print(f"SEMANTIC_SHA256={bundle.semantic_sha256}")
    print(f"ANALYSIS_SHA256={bundle.analysis_sha256}")
    print(f"SET_KEY={plan.manifest['set_key']}")
    print(f"HISTORY_STATE={result.history_state}")
    print("FINDING_SETS_PLANNED=1")
    print(f"FINDINGS_PLANNED={len(plan.findings)}")
    print(f"QUERY_CONTEXTS={plan.query_contexts}")
    print(f"OBSERVATION_SIDES_RESOLVED={plan.observation_sides_resolved}")
    print(f"SINGLE_QUERY_FINDINGS={plan.single_query_findings}")
    print(f"MULTI_QUERY_FINDINGS={plan.multi_query_findings}")
    print(f"FK_FAILURES={plan.fk_failures}")
    print(f"CONSTRAINT_VIOLATIONS={plan.constraint_violations}")
    print(f"MISSING_REQUIRED_VALUES={plan.missing_required_values}")
    print(f"UNIQUE_CONFLICTS={plan.unique_conflicts}")
    print(f"DB_INSERTS={result.inserts}")
    print(f"DB_UPDATES={result.updates}")
    print(f"DB_DELETES={result.deletes}")


def main(
    argv: Sequence[str] | None = None, *, environment: Mapping[str, str] | None = None,
    connection_factory: Callable[[DatabaseConfig, bool], Any] | None = None,
) -> int:
    args = parse_arguments(argv)
    env = os.environ if environment is None else environment
    validate_write_gate(args.write, env)
    bundle = load_artifact(args.findings, args.findings_sha256, args.analysis_sha256)
    config = load_database_config(env)
    connection = (
        connect_database(config, read_only=not args.write)
        if connection_factory is None else connection_factory(config, not args.write)
    )
    try:
        if args.write:
            result = execute_write(connection, args.findings, args.findings_sha256, args.analysis_sha256)
        else:
            base = read_reference_snapshot(connection, bundle.report)
            plan = build_plan(bundle, base)
            history = read_history(connection, plan, base)
            result = PersistenceResult(determine_history_state(plan, history), plan)
            connection.rollback()
        print_result(result, bundle)
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PersistenceError as error:
        print(f"ERROR={error}")
        raise SystemExit(2) from error
