"""One-shot, evidence-gated importer for the first Competitor Monitor baseline.

Dry-run is the default.  A write requires both ``--write`` and the exact
``COMPETITOR_BASELINE_WRITE_ENABLED=true`` environment gate.  The module is
independent from the experimental competitor collector package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


IDEMPOTENCY_CONTRACT = "cm-baseline-idempotency.v1"
EXPECTED_EVIDENCE_SHA256 = (
    "1f1e8abcc80b1a928b92df8cd65c19816dc5b7dbfbae928dfdbce6c9a8c6a3bc"
)
EXPECTED_PAYLOAD_SHA256 = (
    "2ec42948a93dc96db3e5bff320130ce00a88539171d2e8796a88c2a91689e711"
)
EXPECTED_BATCH_DIGEST = (
    "0137d14ccf22ad244ea20c269b39aed642aa037ab089348dc216b95883bf8a9f"
)
EXPECTED_BATCH_REF = f"cm-baseline-v1:batch:{EXPECTED_BATCH_DIGEST}"
WRITE_GATE = "COMPETITOR_BASELINE_WRITE_ENABLED"
ADVISORY_LOCK_KEY = "efa-os:competitor-baseline-import:v1"

EXPECTED_QUERIES = {
    ("УФ 001Б", "80292SLJ013"),
    ("УФ 002Б", "6R0820367"),
    ("УФ 002Б", "JZW819653F"),
    ("УФ 004Б", "5Q0819644A"),
    ("УФ 004Б", "5Q0819653"),
    ("УФ 004Б", "5Q0819669"),
    ("УФ 005Б", "647975"),
    ("УФ 005Б", "6479C2"),
    ("УФ 005Б", "647941"),
}

SEARCH_INSERT_COLUMNS = (
    "search_run_id",
    "offer_id",
    "sku_oem_id",
    "query_kind",
    "query_text_exact",
    "query_normalized",
    "region_key",
    "location_label",
    "captured_at",
    "status",
    "page_count_observed",
    "result_count_observed",
    "collection_ref",
    "raw_source_ref",
)
OBSERVATION_INSERT_COLUMNS = (
    "observation_id",
    "search_run_id",
    "listing_id",
    "membership_id",
    "captured_at",
    "enrichment_captured_at",
    "page_number",
    "position_on_page",
    "rank",
    "ad_flag",
    "bank_price",
    "other_payment_price",
    "old_price",
    "currency",
    "rating",
    "reviews_count_observed",
    "reviews_scope",
    "purchase_count_observed",
    "purchase_indicator_raw",
    "availability_status",
    "availability_raw",
    "observed_oem_raw",
    "observed_dimensions_raw",
    "observed_length_mm",
    "observed_width_mm",
    "observed_height_mm",
    "carbon_claim_raw",
    "origin_raw",
    "quality_status",
    "quality_flags",
    "source_ref",
    "raw_ref",
    "observation_ref",
)

REQUIRED_CONSTRAINTS = {
    "competitor_search_runs_collection_ref_key",
    "competitor_search_runs_counts_check",
    "competitor_search_runs_offer_id_fkey",
    "competitor_search_runs_offer_sku_oem_fkey",
    "competitor_search_runs_query_kind_check",
    "competitor_search_runs_values_check",
    "competitor_observations_dimensions_check",
    "competitor_observations_listing_id_fkey",
    "competitor_observations_membership_id_fkey",
    "competitor_observations_observation_ref_key",
    "competitor_observations_position_check",
    "competitor_observations_prices_check",
    "competitor_observations_rating_count_check",
    "competitor_observations_reviews_scope_check",
    "competitor_observations_search_run_id_fkey",
    "competitor_observations_values_check",
}
REQUIRED_INDEXES = {"competitor_observations_run_position_uidx"}


class ImporterError(RuntimeError):
    """Base class for safe, user-facing importer failures."""


class ConfigurationError(ImporterError):
    """The CLI or environment configuration is unsafe or incomplete."""


class ArtifactError(ImporterError):
    """An immutable artifact failed its hash or semantic contract."""


class ReconciliationError(ImporterError):
    """The payload does not match the production reference layer."""


class HistoryConflictError(ImporterError):
    """History is neither empty nor an exact replay of this baseline."""


class DatabaseError(ImporterError):
    """A database operation failed without exposing connection details."""


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class ArtifactBundle:
    evidence_path: Path
    payload_path: Path
    evidence_sha256: str
    payload_sha256: str
    evidence: dict[str, Any]
    payload: dict[str, Any]


@dataclass(frozen=True)
class SkuOemReference:
    sku_oem_id: str
    offer_id: str
    oem_normalized: str
    active: bool


@dataclass(frozen=True)
class MembershipReference:
    membership_id: str
    offer_id: str
    membership_status: str
    matched_oem_set: tuple[str, ...]
    listing_id: str
    ozon_product_id: str
    seller_id: str | None


@dataclass(frozen=True)
class SchemaColumn:
    name: str
    nullable: bool
    has_default: bool
    data_type: str


@dataclass(frozen=True)
class ProductionSnapshot:
    profiles: Mapping[str, str]
    oems: tuple[SkuOemReference, ...]
    memberships: tuple[MembershipReference, ...]
    history_counts: Mapping[str, int]
    search_rows: tuple[Mapping[str, Any], ...]
    observation_rows: tuple[Mapping[str, Any], ...]
    schema_columns: Mapping[str, tuple[SchemaColumn, ...]]
    constraint_names: frozenset[str]
    index_names: frozenset[str]


@dataclass(frozen=True)
class ImportPlan:
    batch_ref: str
    search_rows: tuple[Mapping[str, Any], ...]
    observation_rows: tuple[Mapping[str, Any], ...]
    found: int
    not_found: int
    enrichment_backed: int
    reference_mismatches: int
    constraint_violations: int
    missing_required_values: int
    fk_failures: int
    unique_conflicts: int


@dataclass(frozen=True)
class ImportResult:
    history_state: str
    plan: ImportPlan
    inserts: int = 0
    updates: int = 0
    deletes: int = 0


def canonical_json_bytes(value: object) -> bytes:
    """Return the exact canonical JSON representation for identity documents."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def build_batch_ref(evidence_sha256: str, payload_sha256: str) -> str:
    identity = {
        "contract": IDEMPOTENCY_CONTRACT,
        "evidence_sha256": evidence_sha256,
        "payload_sha256": payload_sha256,
    }
    digest = _sha256_bytes(canonical_json_bytes(identity))
    return f"cm-baseline-v1:batch:{digest}"


def build_collection_ref(
    batch_ref: str,
    offer_id: str,
    query_kind: str,
    query_text_exact: str,
) -> str:
    identity = {
        "batch_ref": batch_ref,
        "offer_id": offer_id,
        "query_kind": query_kind,
        "query_text_exact": query_text_exact,
    }
    return f"cm-baseline-v1:run:{_sha256_bytes(canonical_json_bytes(identity))}"


def build_observation_ref(collection_ref: str, ozon_product_id: str) -> str:
    if not isinstance(ozon_product_id, str) or not ozon_product_id.isdecimal():
        raise ArtifactError("Ozon product ID must be a decimal string")
    identity = {
        "collection_ref": collection_ref,
        "ozon_product_id": ozon_product_id,
    }
    digest = _sha256_bytes(canonical_json_bytes(identity))
    return f"cm-baseline-v1:observation:{digest}"


def build_search_run_id(collection_ref: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, collection_ref))


def build_observation_id(observation_ref: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, observation_ref))


def _strict_json_load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ArtifactError(f"Artifact has a UTF-8 BOM: {path.name}")
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {token}")
            ),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise ArtifactError(f"Artifact is not strict UTF-8 JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise ArtifactError(f"Artifact root must be an object: {path.name}")
    return value


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactError(message)


def _validate_evidence(evidence: Mapping[str, Any]) -> None:
    _require(
        evidence.get("contract_version") == "competitor_baseline_evidence.v1",
        "Evidence contract_version mismatch",
    )
    searches = evidence.get("search_evidence")
    enrichments = evidence.get("enrichment_evidence")
    _require(isinstance(searches, list) and len(searches) == 9, "Expected 9 search evidence rows")
    _require(
        isinstance(enrichments, list) and len(enrichments) == 30,
        "Expected 30 enrichment evidence rows",
    )
    keys = [item.get("evidence_key") for item in searches + enrichments]
    _require(all(isinstance(key, str) and key for key in keys), "Evidence key is missing")
    _require(len(keys) == len(set(keys)), "Evidence keys are not unique")


def _validate_payload(payload: Mapping[str, Any], evidence_sha256: str) -> None:
    _require(
        payload.get("contract_version") == "competitor_baseline_payload.v1",
        "Payload contract_version mismatch",
    )
    _require(payload.get("mode") == "BASELINE", "Payload mode must be BASELINE")
    batch = payload.get("batch")
    _require(isinstance(batch, dict) and batch.get("batch_status") == "SUCCESS", "Batch is not SUCCESS")
    _require(batch.get("evidence_file_sha256") == evidence_sha256, "Embedded evidence hash mismatch")
    runs = payload.get("search_runs")
    observations = payload.get("observations")
    enrichments = payload.get("enrichments")
    _require(isinstance(runs, list) and len(runs) == 9, "Expected 9 search runs")
    _require(isinstance(observations, list) and len(observations) == 87, "Expected 87 observations")
    _require(isinstance(enrichments, list) and len(enrichments) == 30, "Expected 30 enrichments")
    found = [row for row in observations if row.get("slot_status") == "FOUND"]
    not_found = [
        row for row in observations if row.get("slot_status") == "NOT_FOUND_WITHIN_SCAN_LIMIT"
    ]
    _require(len(found) == 50 and len(not_found) == 37, "Expected FOUND/NOT_FOUND = 50/37")
    _require(
        all(row.get("reviews_scope") == "UNKNOWN" for row in observations),
        "reviews_scope must be UNKNOWN for all observations",
    )
    _require(not _contains_key(payload, "comparison_price"), "comparison_price is forbidden")
    semantics = payload.get("baseline_semantics")
    _require(isinstance(semantics, dict), "baseline_semantics is missing")
    _require(semantics.get("signals") == [] and semantics.get("findings") == [], "Baseline analytics must be empty")
    _require(semantics.get("previous_observation") is None, "Baseline previous_observation must be null")
    _require(semantics.get("price_delta") == "NOT_CALCULATED", "price_delta contract mismatch")
    _require(semantics.get("rank_delta") == "NOT_CALCULATED", "rank_delta contract mismatch")
    query_set = {(row.get("offer_id"), row.get("query_text_exact")) for row in runs}
    _require(query_set == EXPECTED_QUERIES, "Canonical query set mismatch")
    _require(all(row.get("query_kind") == "OEM" for row in runs), "All queries must have query_kind=OEM")
    _require(not any(row.get("offer_id") == "УФ 003Б" for row in runs + observations), "УФ 003Б must have no rows")


def _validate_evidence_resolution(
    payload: Mapping[str, Any], evidence: Mapping[str, Any]
) -> None:
    search_evidence = {row["evidence_key"]: row for row in evidence["search_evidence"]}
    enrichment_evidence = {
        row["evidence_key"]: row for row in evidence["enrichment_evidence"]
    }
    run_by_key = {
        (row["offer_id"], row["query_text_exact"]): row for row in payload["search_runs"]
    }
    for run in payload["search_runs"]:
        source = search_evidence.get(run.get("raw_source_ref"))
        _require(source is not None, "Unresolved search raw_source_ref")
        _require(
            run["offer_id"] == source.get("offer_id")
            and run["query_text_exact"] == source.get("query")
            and run["captured_at"] == source.get("captured_at")
            and run["region_key"] == source.get("region_key")
            and run["location_label"] == source.get("location_label")
            and run["status"] == source.get("status")
            and run["termination_reason"] == source.get("termination_reason")
            and run["cards_scanned"] == source.get("cards_scanned")
            and run["result_count_observed"] == len(source.get("ordered_cards", [])),
            "Search evidence mismatch",
        )

    old_statuses: list[str] = []
    for enrichment in payload["enrichments"]:
        source = enrichment_evidence.get(enrichment.get("raw_ref"))
        _require(source is not None, "Unresolved enrichment raw_ref")
        prices = source.get("price_evidence", {})
        _require(
            str(enrichment["ozon_product_id"]) == str(source.get("ozon_product_id"))
            and enrichment["captured_at"] == source.get("captured_at")
            and enrichment["bank_price"] == prices.get("bank_price_parsed")
            and enrichment["other_payment_price"] == prices.get("other_payment_price_parsed")
            and enrichment["old_price"] == prices.get("old_price_parsed")
            and enrichment["price_evidence_status"] == source.get("old_price_evidence_status"),
            "Enrichment evidence mismatch",
        )
        _require(
            enrichment["seller_name_observed"] == source.get("seller", {}).get("raw_visible_name")
            and enrichment["seller_id_observed"] == source.get("seller", {}).get("seller_id_parsed")
            and enrichment["availability_raw"] == source.get("availability", {}).get("raw_visible_text")
            and enrichment["availability_status"] == source.get("availability", {}).get("status")
            and enrichment["purchase_indicator_raw"]
            == source.get("purchase_indicator", {}).get("raw_visible_text")
            and enrichment["purchase_count_observed"]
            == source.get("purchase_indicator", {}).get("parsed_count")
            and enrichment["observed_oem_raw"] == source.get("oem", {}).get("raw_visible_text")
            and enrichment["observed_dimensions_raw"]
            == source.get("dimensions", {}).get("raw_visible_text")
            and enrichment["observed_length_mm"]
            == source.get("dimensions", {}).get("parsed_length_mm")
            and enrichment["observed_width_mm"]
            == source.get("dimensions", {}).get("parsed_width_mm")
            and enrichment["observed_height_mm"]
            == source.get("dimensions", {}).get("parsed_height_mm")
            and enrichment["carbon_claim_raw"]
            == source.get("carbon_claim", {}).get("raw_visible_text")
            and enrichment["origin_raw"] == source.get("origin", {}).get("raw_visible_text"),
            "Enrichment product facts mismatch",
        )
        _require(
            source.get("extraction_status") == "COMPLETE"
            and prices.get("extraction_status") == "COMPLETE",
            "Price extraction is not COMPLETE",
        )
        old_elements = [
            element.get("parsed_numeric_value")
            for element in prices.get("visible_price_elements", [])
            if element.get("semantic_classification") == "OLD_PRICE"
        ]
        if enrichment["price_evidence_status"] == "OLD_PRICE_PRESENT":
            _require(enrichment["old_price"] in old_elements, "Old price lacks an OLD_PRICE element")
        else:
            _require(
                enrichment["price_evidence_status"] == "OLD_PRICE_EXPLICITLY_ABSENT"
                and enrichment["old_price"] is None
                and not old_elements,
                "Explicitly absent old price contract mismatch",
            )
        old_statuses.append(enrichment["price_evidence_status"])
    _require(old_statuses.count("OLD_PRICE_PRESENT") == 27, "Expected 27 proven old prices")
    _require(
        old_statuses.count("OLD_PRICE_EXPLICITLY_ABSENT") == 3,
        "Expected 3 explicitly absent old prices",
    )

    for observation in payload["observations"]:
        run = run_by_key[(observation["offer_id"], observation["query_text_exact"])]
        _require(observation["captured_at"] == run["captured_at"], "Observation search timestamp mismatch")
        if observation["slot_status"] == "FOUND":
            source = enrichment_evidence.get(observation.get("raw_ref"))
            _require(source is not None, "FOUND raw_ref does not resolve")
            search_source = search_evidence[run["raw_source_ref"]]
            card = next(
                (
                    item
                    for item in search_source.get("ordered_cards", [])
                    if str(item.get("ozon_product_id")) == str(observation["ozon_product_id"])
                ),
                None,
            )
            _require(card is not None, "FOUND product is absent from search evidence")
            _require(
                observation["enrichment_captured_at"] == source.get("captured_at")
                and str(observation["ozon_product_id"]) == str(source.get("ozon_product_id"))
                and observation["rank"] == card.get("rank")
                and observation["page_number"] == 1
                and observation["position_on_page"] == observation["rank"]
                and observation["rating"] == card.get("rating_parsed")
                and observation["reviews_count_observed"] == card.get("reviews_count_parsed"),
                "FOUND enrichment provenance mismatch",
            )
            normalized_enrichment = next(
                item for item in payload["enrichments"] if item["raw_ref"] == observation["raw_ref"]
            )
            for field in (
                "bank_price",
                "other_payment_price",
                "old_price",
                "seller_name_observed",
                "seller_id_observed",
                "availability_status",
                "purchase_count_observed",
                "purchase_indicator_raw",
                "observed_oem_raw",
                "observed_dimensions_raw",
                "observed_length_mm",
                "observed_width_mm",
                "observed_height_mm",
                "carbon_claim_raw",
                "origin_raw",
            ):
                _require(
                    observation[field] == normalized_enrichment[field],
                    f"FOUND normalized product fact mismatch: {field}",
                )
        else:
            _require(
                observation.get("raw_ref") is None
                and observation.get("enrichment_captured_at") is None,
                "NOT_FOUND must not have enrichment provenance",
            )
            for field in (
                "rank",
                "page_number",
                "position_on_page",
                "rating",
                "reviews_count_observed",
                "bank_price",
                "other_payment_price",
                "old_price",
                "purchase_count_observed",
                "purchase_indicator_raw",
                "observed_oem_raw",
                "observed_dimensions_raw",
                "observed_length_mm",
                "observed_width_mm",
                "observed_height_mm",
                "carbon_claim_raw",
                "origin_raw",
                "seller_id_observed",
                "seller_name_observed",
            ):
                _require(observation.get(field) is None, f"NOT_FOUND field must be null: {field}")
            _require(
                observation.get("availability_status") == "UNKNOWN"
                and observation.get("quality_status") == "NOT_FOUND"
                and "NOT_FOUND_WITHIN_SCAN_LIMIT" in observation.get("quality_flags", []),
                "NOT_FOUND quality contract mismatch",
            )


def load_and_validate_artifacts(
    payload_path: Path,
    evidence_path: Path,
    payload_sha256: str,
    evidence_sha256: str,
) -> ArtifactBundle:
    if payload_sha256 != EXPECTED_PAYLOAD_SHA256:
        raise ArtifactError("Expected payload SHA-256 argument is not the approved R2 hash")
    if evidence_sha256 != EXPECTED_EVIDENCE_SHA256:
        raise ArtifactError("Expected evidence SHA-256 argument is not the approved hash")
    if not payload_path.is_file() or not evidence_path.is_file():
        raise ArtifactError("Payload or evidence artifact was not found")
    actual_payload_hash = file_sha256(payload_path)
    actual_evidence_hash = file_sha256(evidence_path)
    if actual_payload_hash != payload_sha256:
        raise ArtifactError("Payload SHA-256 mismatch")
    if actual_evidence_hash != evidence_sha256:
        raise ArtifactError("Evidence SHA-256 mismatch")
    payload = _strict_json_load(payload_path)
    evidence = _strict_json_load(evidence_path)
    _validate_evidence(evidence)
    _validate_payload(payload, actual_evidence_hash)
    _validate_evidence_resolution(payload, evidence)
    batch_ref = build_batch_ref(actual_evidence_hash, actual_payload_hash)
    if batch_ref != EXPECTED_BATCH_REF:
        raise ArtifactError("Canonical batch_ref assertion failed")
    return ArtifactBundle(
        evidence_path=evidence_path,
        payload_path=payload_path,
        evidence_sha256=actual_evidence_hash,
        payload_sha256=actual_payload_hash,
        evidence=evidence,
        payload=payload,
    )


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _numeric(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _slot_key(offer_id: str, query: str, product_id: str) -> tuple[str, str, str]:
    return offer_id, query, product_id


def build_import_plan(bundle: ArtifactBundle, snapshot: ProductionSnapshot) -> ImportPlan:
    payload = bundle.payload
    batch_ref = build_batch_ref(bundle.evidence_sha256, bundle.payload_sha256)
    if batch_ref != EXPECTED_BATCH_REF:
        raise ArtifactError("Unexpected batch_ref")

    if len(snapshot.memberships) != 41:
        raise ReconciliationError("Expected 41 active production memberships")
    if snapshot.profiles.get("УФ 003Б") != "HOLD":
        raise ReconciliationError("УФ 003Б must remain HOLD")
    if any(reference.offer_id == "УФ 003Б" for reference in snapshot.memberships):
        raise ReconciliationError("УФ 003Б must have zero active memberships")

    oem_by_key = {
        (reference.offer_id, reference.oem_normalized): reference
        for reference in snapshot.oems
        if reference.active
    }
    membership_by_slot: dict[tuple[str, str, str], MembershipReference] = {}
    for reference in snapshot.memberships:
        for oem in reference.matched_oem_set:
            key = _slot_key(reference.offer_id, oem, reference.ozon_product_id)
            if key in membership_by_slot:
                raise ReconciliationError("Duplicate production logical slot")
            membership_by_slot[key] = reference

    actual_slots = [
        _slot_key(row["offer_id"], row["query_text_exact"], str(row["ozon_product_id"]))
        for row in payload["observations"]
    ]
    actual_slot_set = set(actual_slots)
    expected_slot_set = set(membership_by_slot)
    missing = expected_slot_set - actual_slot_set
    extra = actual_slot_set - expected_slot_set
    duplicates = len(actual_slots) - len(actual_slot_set)
    if len(expected_slot_set) != 87 or missing or extra or duplicates:
        raise ReconciliationError(
            "Production slot reconciliation failed: "
            f"expected={len(expected_slot_set)} payload={len(actual_slots)} "
            f"missing={len(missing)} extra={len(extra)} duplicates={duplicates}"
        )

    search_rows: list[dict[str, Any]] = []
    run_by_query: dict[tuple[str, str], dict[str, Any]] = {}
    for source in payload["search_runs"]:
        oem = oem_by_key.get((source["offer_id"], source["query_normalized"]))
        if oem is None:
            raise ReconciliationError("Search query has no active SKU OEM lookup")
        collection_ref = build_collection_ref(
            batch_ref,
            source["offer_id"],
            source["query_kind"],
            source["query_text_exact"],
        )
        row = {
            "search_run_id": build_search_run_id(collection_ref),
            "offer_id": source["offer_id"],
            "sku_oem_id": oem.sku_oem_id,
            "query_kind": source["query_kind"],
            "query_text_exact": source["query_text_exact"],
            "query_normalized": source["query_normalized"],
            "region_key": source["region_key"],
            "location_label": source["location_label"],
            "captured_at": _timestamp(source["captured_at"]),
            "status": source["status"],
            "page_count_observed": None,
            "result_count_observed": source["result_count_observed"],
            "collection_ref": collection_ref,
            "raw_source_ref": source["raw_source_ref"],
        }
        search_rows.append(row)
        run_by_query[(source["offer_id"], source["query_text_exact"])] = row

    enrichments = {row["raw_ref"]: row for row in payload["enrichments"]}
    observations: list[dict[str, Any]] = []
    for source in payload["observations"]:
        product_id = str(source["ozon_product_id"])
        slot = _slot_key(source["offer_id"], source["query_text_exact"], product_id)
        reference = membership_by_slot[slot]
        if reference.membership_status != source["membership_status"]:
            raise ReconciliationError("Membership status mismatch")
        if (
            source.get("seller_id_observed") is not None
            and source["seller_id_observed"] != reference.seller_id
        ):
            raise ReconciliationError("Observed seller ID conflicts with production listing")
        run = run_by_query[(source["offer_id"], source["query_text_exact"])]
        enrichment = enrichments.get(source["raw_ref"]) if source["raw_ref"] else None
        found = source["slot_status"] == "FOUND"
        if found != (enrichment is not None):
            raise ReconciliationError("Observation enrichment mapping mismatch")
        observation_ref = build_observation_ref(run["collection_ref"], product_id)
        row = {
            "observation_id": build_observation_id(observation_ref),
            "search_run_id": run["search_run_id"],
            "listing_id": reference.listing_id,
            "membership_id": reference.membership_id,
            "captured_at": _timestamp(source["captured_at"]),
            "enrichment_captured_at": _timestamp(source["enrichment_captured_at"]),
            "page_number": source["page_number"],
            "position_on_page": source["position_on_page"],
            "rank": source["rank"],
            "ad_flag": source["ad_flag"],
            "bank_price": _numeric(source["bank_price"]),
            "other_payment_price": _numeric(source["other_payment_price"]),
            "old_price": _numeric(source["old_price"]),
            "currency": enrichment["currency"] if enrichment else None,
            "rating": _numeric(source["rating"]),
            "reviews_count_observed": source["reviews_count_observed"],
            "reviews_scope": source["reviews_scope"],
            "purchase_count_observed": source["purchase_count_observed"],
            "purchase_indicator_raw": source["purchase_indicator_raw"],
            "availability_status": source["availability_status"],
            "availability_raw": enrichment["availability_raw"] if enrichment else None,
            "observed_oem_raw": source["observed_oem_raw"],
            "observed_dimensions_raw": source["observed_dimensions_raw"],
            "observed_length_mm": _numeric(source["observed_length_mm"]),
            "observed_width_mm": _numeric(source["observed_width_mm"]),
            "observed_height_mm": _numeric(source["observed_height_mm"]),
            "carbon_claim_raw": source["carbon_claim_raw"],
            "origin_raw": source["origin_raw"],
            "quality_status": source["quality_status"],
            "quality_flags": tuple(source["quality_flags"]),
            "source_ref": enrichment["source_ref"] if enrichment else run_source_url(payload, source),
            "raw_ref": source["raw_ref"],
            "observation_ref": observation_ref,
        }
        observations.append(row)

    validation = validate_planned_rows(tuple(search_rows), tuple(observations), snapshot)
    return ImportPlan(
        batch_ref=batch_ref,
        search_rows=tuple(search_rows),
        observation_rows=tuple(observations),
        found=sum(row["slot_status"] == "FOUND" for row in payload["observations"]),
        not_found=sum(
            row["slot_status"] == "NOT_FOUND_WITHIN_SCAN_LIMIT"
            for row in payload["observations"]
        ),
        enrichment_backed=sum(row["raw_ref"] is not None for row in payload["observations"]),
        reference_mismatches=0,
        constraint_violations=validation["constraint_violations"],
        missing_required_values=validation["missing_required_values"],
        fk_failures=validation["fk_failures"],
        unique_conflicts=validation["unique_conflicts"],
    )


def run_source_url(payload: Mapping[str, Any], observation: Mapping[str, Any]) -> str:
    for run in payload["search_runs"]:
        if (
            run["offer_id"] == observation["offer_id"]
            and run["query_text_exact"] == observation["query_text_exact"]
        ):
            return run["source_url"]
    raise ReconciliationError("Search source URL lookup failed")


def validate_schema(snapshot: ProductionSnapshot) -> None:
    for table, insert_columns in (
        ("competitor_search_runs", SEARCH_INSERT_COLUMNS),
        ("competitor_observations", OBSERVATION_INSERT_COLUMNS),
    ):
        columns = {column.name: column for column in snapshot.schema_columns.get(table, ())}
        missing = set(insert_columns) - set(columns)
        if missing:
            raise ReconciliationError(f"Production schema is missing {table} columns")
    search_id = {c.name: c for c in snapshot.schema_columns["competitor_search_runs"]}[
        "search_run_id"
    ]
    observation_id = {
        c.name: c for c in snapshot.schema_columns["competitor_observations"]
    }["observation_id"]
    if search_id.data_type != "uuid" or observation_id.data_type != "uuid":
        raise ReconciliationError("Production PK types are not UUID")
    if not REQUIRED_CONSTRAINTS.issubset(snapshot.constraint_names):
        raise ReconciliationError("Required production constraints are missing")
    if not REQUIRED_INDEXES.issubset(snapshot.index_names):
        raise ReconciliationError("Required production indexes are missing")


def validate_planned_rows(
    search_rows: tuple[Mapping[str, Any], ...],
    observation_rows: tuple[Mapping[str, Any], ...],
    snapshot: ProductionSnapshot,
) -> dict[str, int]:
    validate_schema(snapshot)
    missing_required = 0
    constraint_violations = 0
    fk_failures = 0

    for table, rows in (
        ("competitor_search_runs", search_rows),
        ("competitor_observations", observation_rows),
    ):
        for column in snapshot.schema_columns[table]:
            if column.nullable or column.has_default:
                continue
            for row in rows:
                if column.name not in row or row[column.name] is None:
                    missing_required += 1

    oem_ids = {reference.sku_oem_id for reference in snapshot.oems if reference.active}
    listing_ids = {reference.listing_id for reference in snapshot.memberships}
    membership_ids = {reference.membership_id for reference in snapshot.memberships}
    run_ids = {row["search_run_id"] for row in search_rows}
    for row in search_rows:
        if row["sku_oem_id"] not in oem_ids:
            fk_failures += 1
        if row["query_kind"] not in {"OEM", "MARKET", "SCOUT"}:
            constraint_violations += 1
        if row["result_count_observed"] is not None and row["result_count_observed"] < 0:
            constraint_violations += 1
    for row in observation_rows:
        if row["search_run_id"] not in run_ids:
            fk_failures += 1
        if row["listing_id"] not in listing_ids or row["membership_id"] not in membership_ids:
            fk_failures += 1
        if row["reviews_scope"] not in {"LISTING", "PRODUCT_FAMILY", "UNKNOWN"}:
            constraint_violations += 1
        if any(
            row[name] is not None and row[name] <= 0
            for name in ("page_number", "position_on_page", "rank")
        ):
            constraint_violations += 1
        if any(
            row[name] is not None and row[name] < 0
            for name in ("bank_price", "other_payment_price", "old_price")
        ):
            constraint_violations += 1
        if any(row[name] is not None for name in ("bank_price", "other_payment_price", "old_price")) and not row["currency"]:
            constraint_violations += 1
        if row["rating"] is not None and not Decimal("0") <= row["rating"] <= Decimal("5"):
            constraint_violations += 1
        if any(
            row[name] is not None and row[name] < 0
            for name in ("reviews_count_observed", "purchase_count_observed")
        ):
            constraint_violations += 1
        if any(
            row[name] is not None and row[name] <= 0
            for name in ("observed_length_mm", "observed_width_mm", "observed_height_mm")
        ):
            constraint_violations += 1
        if any(flag is None for flag in row["quality_flags"]):
            constraint_violations += 1

    collection_refs = [row["collection_ref"] for row in search_rows]
    observation_refs = [row["observation_ref"] for row in observation_rows]
    positions = [
        (row["search_run_id"], row["page_number"], row["position_on_page"])
        for row in observation_rows
        if row["page_number"] is not None and row["position_on_page"] is not None
    ]
    unique_conflicts = (
        len(collection_refs) - len(set(collection_refs))
        + len(observation_refs) - len(set(observation_refs))
        + len(positions) - len(set(positions))
    )
    if any((missing_required, constraint_violations, fk_failures, unique_conflicts)):
        raise ReconciliationError(
            "Planned DB rows are incompatible with production schema: "
            f"missing={missing_required} constraints={constraint_violations} "
            f"fk={fk_failures} unique={unique_conflicts}"
        )
    return {
        "missing_required_values": missing_required,
        "constraint_violations": constraint_violations,
        "fk_failures": fk_failures,
        "unique_conflicts": unique_conflicts,
    }


def _normalise(value: object) -> object:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat()
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Decimal):
        return value.normalize()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return tuple(_normalise(item) for item in value)
    return value


def _rows_match(
    planned: tuple[Mapping[str, Any], ...],
    persisted: tuple[Mapping[str, Any], ...],
    key: str,
) -> bool:
    if len(planned) != len(persisted):
        return False
    planned_by_key = {str(row[key]): row for row in planned}
    persisted_by_key = {str(row[key]): row for row in persisted}
    if set(planned_by_key) != set(persisted_by_key):
        return False
    for identity, planned_row in planned_by_key.items():
        persisted_row = persisted_by_key[identity]
        for column, planned_value in planned_row.items():
            if column not in persisted_row:
                return False
            if _normalise(planned_value) != _normalise(persisted_row[column]):
                return False
    return True


def determine_history_state(plan: ImportPlan, snapshot: ProductionSnapshot) -> str:
    counts = snapshot.history_counts
    expected_keys = {"search_runs", "observations", "reviews", "findings"}
    if set(counts) != expected_keys:
        raise HistoryConflictError("Incomplete history count contract")
    if all(counts[name] == 0 for name in expected_keys):
        return "EMPTY_HISTORY"
    exact_counts = (
        counts["search_runs"] == 9
        and counts["observations"] == 87
        and counts["reviews"] == 0
        and counts["findings"] == 0
    )
    if exact_counts and _rows_match(
        plan.search_rows, snapshot.search_rows, "collection_ref"
    ) and _rows_match(
        plan.observation_rows, snapshot.observation_rows, "observation_ref"
    ):
        return "EXACT_ALREADY_APPLIED"
    raise HistoryConflictError("PARTIAL_HISTORY_CONFLICT")


def run_dry_run(bundle: ArtifactBundle, snapshot: ProductionSnapshot) -> ImportResult:
    plan = build_import_plan(bundle, snapshot)
    state = determine_history_state(plan, snapshot)
    return ImportResult(history_state=state, plan=plan)


def _fetch_dicts(cursor: Any, query: str, parameters: tuple[object, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(query, parameters)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def read_production_snapshot(connection: Any) -> ProductionSnapshot:
    """Read schema, static references, and complete baseline history with SELECT only."""

    try:
        with connection.cursor() as cursor:
            profile_rows = _fetch_dicts(
                cursor,
                "SELECT offer_id, watchlist_state FROM public.competitor_sku_profiles",
            )
            oem_rows = _fetch_dicts(
                cursor,
                """SELECT sku_oem_id::text, offer_id, oem_normalized, active
                     FROM public.competitor_sku_oems""",
            )
            membership_rows = _fetch_dicts(
                cursor,
                """SELECT m.membership_id::text, m.offer_id, m.membership_status,
                          m.matched_oem_set, l.listing_id::text,
                          l.ozon_product_id::text, l.seller_id
                     FROM public.competitor_watchlist_memberships m
                     JOIN public.competitor_listings l ON l.listing_id = m.listing_id
                     JOIN public.competitor_sku_profiles p ON p.offer_id = m.offer_id
                    WHERE m.valid_to IS NULL
                      AND m.membership_status IN ('PRIMARY', 'RESERVE', 'CONTROL')
                      AND p.watchlist_state = 'ACTIVE'""",
            )
            count_row = _fetch_dicts(
                cursor,
                """SELECT
                    (SELECT count(*) FROM public.competitor_search_runs) AS search_runs,
                    (SELECT count(*) FROM public.competitor_observations) AS observations,
                    (SELECT count(*) FROM public.competitor_reviews) AS reviews,
                    (SELECT count(*) FROM public.competitor_findings) AS findings""",
            )[0]
            search_rows = _fetch_dicts(
                cursor,
                """SELECT search_run_id::text, offer_id, sku_oem_id::text,
                          query_kind, query_text_exact, query_normalized,
                          region_key, location_label, captured_at, status,
                          page_count_observed, result_count_observed,
                          collection_ref, raw_source_ref
                     FROM public.competitor_search_runs""",
            )
            observation_rows = _fetch_dicts(
                cursor,
                """SELECT observation_id::text, search_run_id::text,
                          listing_id::text, membership_id::text, captured_at,
                          enrichment_captured_at, page_number, position_on_page,
                          rank, ad_flag, bank_price, other_payment_price,
                          old_price, currency, rating, reviews_count_observed,
                          reviews_scope, purchase_count_observed,
                          purchase_indicator_raw, availability_status,
                          availability_raw, observed_oem_raw,
                          observed_dimensions_raw, observed_length_mm,
                          observed_width_mm, observed_height_mm,
                          carbon_claim_raw, origin_raw, quality_status,
                          quality_flags, source_ref, raw_ref, observation_ref
                     FROM public.competitor_observations""",
            )
            column_rows = _fetch_dicts(
                cursor,
                """SELECT table_name, column_name, data_type, is_nullable,
                          column_default IS NOT NULL AS has_default
                     FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name IN ('competitor_search_runs', 'competitor_observations')""",
            )
            constraint_rows = _fetch_dicts(
                cursor,
                """SELECT con.conname
                     FROM pg_constraint con
                     JOIN pg_class rel ON rel.oid = con.conrelid
                     JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                    WHERE nsp.nspname = 'public'
                      AND rel.relname IN ('competitor_search_runs', 'competitor_observations')""",
            )
            index_rows = _fetch_dicts(
                cursor,
                """SELECT indexname
                     FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename IN ('competitor_search_runs', 'competitor_observations')""",
            )
    except Exception as error:
        raise DatabaseError("Read-only production reconciliation failed") from error

    schema: dict[str, list[SchemaColumn]] = {
        "competitor_search_runs": [],
        "competitor_observations": [],
    }
    for row in column_rows:
        schema[row["table_name"]].append(
            SchemaColumn(
                name=row["column_name"],
                nullable=row["is_nullable"] == "YES",
                has_default=bool(row["has_default"]),
                data_type=row["data_type"],
            )
        )
    return ProductionSnapshot(
        profiles={row["offer_id"]: row["watchlist_state"] for row in profile_rows},
        oems=tuple(
            SkuOemReference(
                sku_oem_id=row["sku_oem_id"],
                offer_id=row["offer_id"],
                oem_normalized=row["oem_normalized"],
                active=bool(row["active"]),
            )
            for row in oem_rows
        ),
        memberships=tuple(
            MembershipReference(
                membership_id=row["membership_id"],
                offer_id=row["offer_id"],
                membership_status=row["membership_status"],
                matched_oem_set=tuple(row["matched_oem_set"]),
                listing_id=row["listing_id"],
                ozon_product_id=row["ozon_product_id"],
                seller_id=row["seller_id"],
            )
            for row in membership_rows
        ),
        history_counts={name: int(count_row[name]) for name in count_row},
        search_rows=tuple(search_rows),
        observation_rows=tuple(observation_rows),
        schema_columns={table: tuple(columns) for table, columns in schema.items()},
        constraint_names=frozenset(row["conname"] for row in constraint_rows),
        index_names=frozenset(row["indexname"] for row in index_rows),
    )


def load_database_config(environment: Mapping[str, str]) -> DatabaseConfig:
    names = ("EFA_DB_HOST", "EFA_DB_PORT", "EFA_DB_NAME", "EFA_DB_USER", "EFA_DB_PASSWORD")
    missing = [name for name in names if not environment.get(name)]
    if missing:
        raise ConfigurationError("Required EFA database environment is incomplete")
    try:
        port = int(environment["EFA_DB_PORT"])
    except ValueError as error:
        raise ConfigurationError("EFA_DB_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError("EFA_DB_PORT is outside the valid range")
    return DatabaseConfig(
        host=environment["EFA_DB_HOST"].strip(),
        port=port,
        name=environment["EFA_DB_NAME"].strip(),
        user=environment["EFA_DB_USER"].strip(),
        password=environment["EFA_DB_PASSWORD"],
    )


def connect_database(config: DatabaseConfig, *, read_only: bool) -> Any:
    try:
        import psycopg2

        options = "-c default_transaction_read_only=on -c statement_timeout=15000" if read_only else "-c statement_timeout=60000"
        return psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.name,
            user=config.user,
            password=config.password,
            connect_timeout=10,
            options=options,
        )
    except Exception as error:
        raise DatabaseError("PostgreSQL connection failed") from error


SEARCH_INSERT_SQL = """
INSERT INTO public.competitor_search_runs (
    search_run_id, offer_id, sku_oem_id, query_kind, query_text_exact,
    query_normalized, region_key, location_label, captured_at, status,
    page_count_observed, result_count_observed, collection_ref, raw_source_ref
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

OBSERVATION_INSERT_SQL = """
INSERT INTO public.competitor_observations (
    observation_id, search_run_id, listing_id, membership_id, captured_at,
    enrichment_captured_at, page_number, position_on_page, rank, ad_flag,
    bank_price, other_payment_price, old_price, currency, rating,
    reviews_count_observed, reviews_scope, purchase_count_observed,
    purchase_indicator_raw, availability_status, availability_raw,
    observed_oem_raw, observed_dimensions_raw, observed_length_mm,
    observed_width_mm, observed_height_mm, carbon_claim_raw, origin_raw,
    quality_status, quality_flags, source_ref, raw_ref, observation_ref
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""


def _insert_plan(connection: Any, plan: ImportPlan) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(
            SEARCH_INSERT_SQL,
            [tuple(row[column] for column in SEARCH_INSERT_COLUMNS) for row in plan.search_rows],
        )
        cursor.executemany(
            OBSERVATION_INSERT_SQL,
            [
                tuple(
                    list(row[column]) if column == "quality_flags" else row[column]
                    for column in OBSERVATION_INSERT_COLUMNS
                )
                for row in plan.observation_rows
            ],
        )


def execute_write(
    connection: Any,
    *,
    payload_path: Path,
    evidence_path: Path,
    payload_sha256: str,
    evidence_sha256: str,
) -> ImportResult:
    """Execute the future atomic write path. Call only after both write gates pass."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (ADVISORY_LOCK_KEY,),
            )
        bundle = load_and_validate_artifacts(
            payload_path, evidence_path, payload_sha256, evidence_sha256
        )
        before = read_production_snapshot(connection)
        plan = build_import_plan(bundle, before)
        state = determine_history_state(plan, before)
        if state == "EXACT_ALREADY_APPLIED":
            connection.rollback()
            return ImportResult(history_state=state, plan=plan)
        if state != "EMPTY_HISTORY":
            raise HistoryConflictError("PARTIAL_HISTORY_CONFLICT")
        _insert_plan(connection, plan)
        after = read_production_snapshot(connection)
        if determine_history_state(plan, after) != "EXACT_ALREADY_APPLIED":
            raise HistoryConflictError("Post-insert exact validation failed")
        connection.commit()
        return ImportResult(history_state="APPLIED", plan=plan, inserts=96)
    except Exception:
        connection.rollback()
        raise


def validate_write_gate(write: bool, environment: Mapping[str, str]) -> None:
    if write and environment.get(WRITE_GATE, "").strip().lower() != "true":
        raise ConfigurationError(
            "Write requires both --write and COMPETITOR_BASELINE_WRITE_ENABLED=true"
        )


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-shot Competitor Monitor baseline importer v1")
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--payload-sha256", required=True)
    parser.add_argument("--evidence-sha256", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="SELECT-only validation; the default")
    mode.add_argument("--write", action="store_true", help="perform the gated atomic import")
    return parser.parse_args(argv)


def print_result(result: ImportResult, bundle: ArtifactBundle) -> None:
    print(f"PAYLOAD_HASH={bundle.payload_sha256}")
    print(f"EVIDENCE_HASH={bundle.evidence_sha256}")
    print(f"BATCH_REF={result.plan.batch_ref}")
    print(f"HISTORY_STATE={result.history_state}")
    print(f"SEARCH_RUNS_PLANNED={len(result.plan.search_rows)}")
    print(f"OBSERVATIONS_PLANNED={len(result.plan.observation_rows)}")
    print(f"FOUND={result.plan.found}")
    print(f"NOT_FOUND={result.plan.not_found}")
    print(f"ENRICHMENT_BACKED={result.plan.enrichment_backed}")
    print(f"REFERENCE_MISMATCHES={result.plan.reference_mismatches}")
    print(f"CONSTRAINT_VIOLATIONS={result.plan.constraint_violations}")
    print(f"DB_INSERTS={result.inserts}")
    print(f"DB_UPDATES={result.updates}")
    print(f"DB_DELETES={result.deletes}")


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    connection_factory: Callable[[DatabaseConfig], Any] | None = None,
) -> int:
    args = parse_arguments(argv)
    env = os.environ if environment is None else environment
    validate_write_gate(args.write, env)
    bundle = load_and_validate_artifacts(
        args.payload,
        args.evidence,
        args.payload_sha256,
        args.evidence_sha256,
    )
    config = load_database_config(env)
    if connection_factory is None:
        connection = connect_database(config, read_only=not args.write)
    else:
        connection = connection_factory(config)
    try:
        if args.write:
            result = execute_write(
                connection,
                payload_path=args.payload,
                evidence_path=args.evidence,
                payload_sha256=args.payload_sha256,
                evidence_sha256=args.evidence_sha256,
            )
        else:
            snapshot = read_production_snapshot(connection)
            result = run_dry_run(bundle, snapshot)
            connection.rollback()
        print_result(result, bundle)
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ImporterError as error:
        print(f"ERROR={error}")
        raise SystemExit(1)
