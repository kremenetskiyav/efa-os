"""Evidence-gated importer for Competitor Monitor factual snapshots T1+.

Dry-run is the default. A future write requires both ``--write`` and the exact
``COMPETITOR_SNAPSHOT_WRITE_ENABLED=true`` process gate. The importer writes
only search runs and observations and has no runtime dependency on Collector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


EVIDENCE_CONTRACT = "competitor_snapshot_evidence.v1"
PAYLOAD_CONTRACT = "competitor_snapshot_payload.v1"
IDEMPOTENCY_CONTRACT = "cm-snapshot-idempotency.v1"
MODE = "SNAPSHOT"
WRITE_GATE = "COMPETITOR_SNAPSHOT_WRITE_ENABLED"
ADVISORY_LOCK_KEY = "efa-os:competitor-snapshot-import:v1"

COMPLETE_OLD_PRICE_STATUSES = {
    "OLD_PRICE_PRESENT",
    "OLD_PRICE_EXPLICITLY_ABSENT",
}
KNOWN_OLD_PRICE_STATUSES = COMPLETE_OLD_PRICE_STATUSES | {
    "AMBIGUOUS_PRICE_SECTION",
    "PRICE_SECTION_FAILED",
}
MONITORED_MEMBERSHIP_STATUSES = {"PRIMARY", "RESERVE", "CONTROL"}

REFERENCE_PLAN_SQL = """
SELECT
    record_kind,
    offer_id,
    watchlist_state,
    sku_oem_id::text,
    query_normalized,
    oem_active,
    oem_created_at,
    membership_id::text,
    membership_status,
    matched_oem_set,
    valid_from,
    valid_to,
    listing_id::text,
    product_family_id::text,
    ozon_product_id::text,
    seller_id,
    product_name,
    reference_ordinal
FROM mcp_read.competitor_reference_plan_source
"""

SNAPSHOT_COUNTS_SQL = """
SELECT
    (SELECT count(*) FROM mcp_read.competitor_snapshot_runs) AS search_runs,
    (SELECT count(*) FROM mcp_read.competitor_snapshot_observations) AS observations,
    0::bigint AS reviews,
    (SELECT count(*) FROM mcp_read.competitor_findings) AS findings
"""

WRITE_TARGET_COLUMNS_SQL = """
SELECT
    rel.relname AS table_name,
    att.attname AS column_name,
    format_type(att.atttypid, att.atttypmod) AS data_type,
    CASE WHEN att.attnotnull THEN 'NO' ELSE 'YES' END AS is_nullable,
    att.atthasdef AS has_default
FROM pg_catalog.pg_class rel
JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace
JOIN pg_catalog.pg_attribute att ON att.attrelid = rel.oid
WHERE nsp.nspname = 'public'
  AND rel.relname IN ('competitor_search_runs', 'competitor_observations')
  AND rel.relkind IN ('r', 'p')
  AND att.attnum > 0
  AND NOT att.attisdropped
ORDER BY rel.relname, att.attnum
"""

WRITE_TARGET_CONSTRAINTS_SQL = """
SELECT con.conname
FROM pg_catalog.pg_constraint con
JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace
WHERE nsp.nspname = 'public'
  AND rel.relname IN ('competitor_search_runs', 'competitor_observations')
"""

WRITE_TARGET_INDEXES_SQL = """
SELECT idx.relname AS indexname
FROM pg_catalog.pg_index link
JOIN pg_catalog.pg_class rel ON rel.oid = link.indrelid
JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace
JOIN pg_catalog.pg_class idx ON idx.oid = link.indexrelid
WHERE nsp.nspname = 'public'
  AND rel.relname IN ('competitor_search_runs', 'competitor_observations')
"""

SNAPSHOT_RUNS_SQL = """
SELECT
    search_run_id::text,
    offer_id,
    sku_oem_id::text,
    query_kind,
    query_text_exact,
    query_normalized,
    region_key,
    location_label,
    captured_at,
    status,
    page_count_observed,
    result_count_observed,
    collection_ref,
    raw_source_ref
FROM mcp_read.competitor_snapshot_runs
WHERE collection_ref = ANY(%s::text[])
"""

SNAPSHOT_OBSERVATIONS_SQL = """
SELECT
    observation_id::text,
    search_run_id::text,
    listing_id::text,
    membership_id::text,
    captured_at,
    enrichment_captured_at,
    page_number,
    position_on_page,
    rank,
    ad_flag,
    bank_price,
    other_payment_price,
    old_price,
    currency,
    rating,
    reviews_count_observed,
    reviews_scope,
    purchase_count_observed,
    purchase_indicator_raw,
    availability_status,
    availability_raw,
    observed_oem_raw,
    observed_dimensions_raw,
    observed_length_mm,
    observed_width_mm,
    observed_height_mm,
    carbon_claim_raw,
    origin_raw,
    quality_status,
    quality_flags,
    source_ref,
    raw_ref,
    observation_ref
FROM mcp_read.competitor_snapshot_observations
WHERE search_run_id = ANY(%s::uuid[])
"""

APPROVED_READ_SQL = (
    REFERENCE_PLAN_SQL,
    SNAPSHOT_COUNTS_SQL,
    SNAPSHOT_RUNS_SQL,
    SNAPSHOT_OBSERVATIONS_SQL,
)

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
    """Base class for safe importer failures."""


class ConfigurationError(ImporterError):
    """The CLI or environment configuration is unsafe or incomplete."""


class ArtifactError(ImporterError):
    """An immutable artifact failed its hash or semantic contract."""


class ReferenceConflictError(ImporterError):
    """The payload does not match the reference layer at snapshot time."""


class BatchConflictError(ImporterError):
    """The current batch is partially persisted or factually different."""


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
    reference_at: datetime


@dataclass(frozen=True)
class SkuOemReference:
    sku_oem_id: str
    offer_id: str
    oem_normalized: str
    active: bool
    created_at: datetime


@dataclass(frozen=True)
class MembershipReference:
    membership_id: str
    offer_id: str
    membership_status: str
    matched_oem_set: tuple[str, ...]
    valid_from: datetime
    valid_to: datetime | None
    listing_id: str
    product_family_id: str
    ozon_product_id: str
    seller_id: str | None
    reference_ordinal: int
    product_name: str | None = None


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
class ReferenceLayer:
    oem_by_query: Mapping[tuple[str, str], SkuOemReference]
    membership_by_slot: Mapping[tuple[str, str, str], MembershipReference]


@dataclass(frozen=True)
class ImportPlan:
    batch_ref: str
    reference_at: datetime
    search_rows: tuple[Mapping[str, Any], ...]
    observation_rows: tuple[Mapping[str, Any], ...]
    expected_query_count: int
    expected_slot_count: int
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


def _validate_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ArtifactError(f"{label} must be a lowercase SHA-256 digest")


def build_batch_ref(evidence_sha256: str, payload_sha256: str) -> str:
    identity = {
        "contract": IDEMPOTENCY_CONTRACT,
        "evidence_sha256": evidence_sha256,
        "payload_sha256": payload_sha256,
    }
    return f"cm-snapshot-v1:batch:{_sha256_bytes(canonical_json_bytes(identity))}"


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
    return f"cm-snapshot-v1:run:{_sha256_bytes(canonical_json_bytes(identity))}"


def build_observation_ref(collection_ref: str, ozon_product_id: str) -> str:
    if not isinstance(ozon_product_id, str) or not ozon_product_id.isdecimal():
        raise ArtifactError("Ozon product ID must be a decimal string")
    identity = {"collection_ref": collection_ref, "ozon_product_id": ozon_product_id}
    return f"cm-snapshot-v1:observation:{_sha256_bytes(canonical_json_bytes(identity))}"


def build_search_run_id(collection_ref: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, collection_ref))


def build_observation_id(observation_ref: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, observation_ref))


def _strict_json_load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ArtifactError(f"Artifact has a UTF-8 BOM: {path.name}")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
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


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactError(f"{label} must be a non-empty string")
    return value


def _timestamp(value: object, label: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not value:
        raise ArtifactError(f"{label} is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ArtifactError(f"{label} is not ISO-8601") from error
    if parsed.tzinfo is None:
        raise ArtifactError(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _optional_timestamp(value: object, label: str) -> datetime | None:
    return None if value is None else _timestamp(value, label)


def _numeric(value: object, label: str = "numeric value") -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ArtifactError(f"{label} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ArtifactError(f"{label} must be numeric") from error
    if not result.is_finite():
        raise ArtifactError(f"{label} must be finite")
    return result


def _decimal_product_id(value: object, label: str) -> str:
    text = str(value)
    if not text.isdecimal() or int(text) <= 0:
        raise ArtifactError(f"{label} must be a positive decimal string")
    return text


def _validate_card(card: Mapping[str, Any], search_label: str) -> None:
    _decimal_product_id(card.get("ozon_product_id"), f"{search_label} card product ID")
    for field in ("rank", "ordinal"):
        _require(isinstance(card.get(field), int) and card[field] > 0, f"Invalid card {field}")
    _require(card["rank"] == card["ordinal"], "Card rank/ordinal mismatch")
    ad_marker = card.get("ad_marker_raw")
    _require(
        ad_marker is None or isinstance(ad_marker, str) and ad_marker.strip(),
        "Invalid card ad_marker_raw",
    )
    rating = _numeric(card.get("rating_parsed"), "card rating")
    _require(rating is None or Decimal("0") <= rating <= Decimal("5"), "Invalid card rating")
    reviews = card.get("reviews_count_parsed")
    _require(reviews is None or isinstance(reviews, int) and reviews >= 0, "Invalid reviews count")


def _validate_evidence(evidence: Mapping[str, Any]) -> None:
    _require(evidence.get("contract_version") == EVIDENCE_CONTRACT, "Evidence contract mismatch")
    _require(evidence.get("mode") == MODE, "Evidence mode must be SNAPSHOT")
    batch = evidence.get("batch")
    _require(isinstance(batch, dict) and batch.get("batch_status") == "SUCCESS", "Evidence batch is not SUCCESS")
    searches = evidence.get("search_evidence")
    enrichments = evidence.get("enrichment_evidence")
    _require(isinstance(searches, list) and searches, "Evidence must contain search records")
    _require(isinstance(enrichments, list), "Evidence enrichments must be a list")

    all_keys: list[str] = []
    search_identities: set[tuple[str, str]] = set()
    search_times: list[datetime] = []
    search_urls: list[str] = []
    for index, search in enumerate(searches):
        _require(isinstance(search, dict), "Search evidence row must be an object")
        key = _text(search.get("evidence_key"), "search evidence_key")
        all_keys.append(key)
        offer_id = _text(search.get("offer_id"), "search offer_id")
        query = _text(search.get("query_text_exact"), "search query_text_exact")
        _require(search.get("query_kind") == "OEM", "Snapshot search query_kind must be OEM")
        search_times.append(_timestamp(search.get("captured_at"), "search captured_at"))
        _text(search.get("region_key"), "search region_key")
        _text(search.get("location_label"), "search location_label")
        search_urls.append(_text(search.get("source_url"), "search source_url"))
        _require(search.get("status") == "SUCCESS", "Search evidence status must be SUCCESS")
        _require(
            search.get("extraction_status") == "COMPLETE",
            "Search evidence extraction must be COMPLETE",
        )
        cards = search.get("ordered_cards")
        _require(isinstance(cards, list), "ordered_cards must be a list")
        product_ids: list[str] = []
        for card in cards:
            _require(isinstance(card, dict), "Search card must be an object")
            _validate_card(card, f"search[{index}]")
            product_ids.append(str(card["ozon_product_id"]))
        _require(len(product_ids) == len(set(product_ids)), "Duplicate product in ordered_cards")
        cards_scanned = search.get("cards_scanned")
        _require(isinstance(cards_scanned, int) and cards_scanned == len(cards), "Invalid cards_scanned")
        identity = (offer_id, query)
        _require(identity not in search_identities, "Duplicate search evidence identity")
        search_identities.add(identity)

    enrichment_products: set[str] = set()
    enrichment_times: list[datetime] = []
    enrichment_urls: list[str] = []
    for enrichment in enrichments:
        _require(isinstance(enrichment, dict), "Enrichment evidence row must be an object")
        key = _text(enrichment.get("evidence_key"), "enrichment evidence_key")
        all_keys.append(key)
        product_id = _decimal_product_id(
            enrichment.get("ozon_product_id"), "enrichment product ID"
        )
        _require(product_id not in enrichment_products, "Duplicate enrichment product ID")
        enrichment_products.add(product_id)
        enrichment_times.append(_timestamp(enrichment.get("captured_at"), "enrichment captured_at"))
        enrichment_urls.append(_text(enrichment.get("source_url"), "enrichment source_url"))
        status = enrichment.get("old_price_evidence_status")
        _require(status in KNOWN_OLD_PRICE_STATUSES, "Unknown old price evidence status")
        prices = enrichment.get("price_evidence")
        _require(isinstance(prices, dict), "price_evidence must be an object")
        _require(
            prices.get("extraction_status") == "COMPLETE",
            "Structured price evidence must be COMPLETE",
        )
        elements = prices.get("visible_price_elements")
        _require(isinstance(elements, list), "visible_price_elements must be a list")
        bank_price = _numeric(prices.get("bank_price_parsed"), "bank price")
        other_price = _numeric(prices.get("other_payment_price_parsed"), "other payment price")
        bank_elements = [
            _numeric(element.get("parsed_numeric_value"), "BANK_PRICE element")
            for element in elements
            if isinstance(element, dict) and element.get("classification") == "BANK_PRICE"
        ]
        other_elements = [
            _numeric(element.get("parsed_numeric_value"), "OTHER_PAYMENT_PRICE element")
            for element in elements
            if isinstance(element, dict)
            and element.get("classification") == "OTHER_PAYMENT_PRICE"
        ]
        _require(
            bank_price is not None and bank_price in bank_elements,
            "BANK_PRICE structured evidence is incomplete",
        )
        _require(
            other_price is not None and other_price in other_elements,
            "OTHER_PAYMENT_PRICE structured evidence is incomplete",
        )
        _require(_price_currency(prices) == "RUB", "Structured price currency is not provable")
        old_price = _numeric(prices.get("old_price_parsed"), "old price")
        old_elements = [
            _numeric(element.get("parsed_numeric_value"), "OLD_PRICE element")
            for element in elements
            if isinstance(element, dict) and element.get("classification") == "OLD_PRICE"
        ]
        if status == "OLD_PRICE_PRESENT":
            _require(
                enrichment.get("extraction_status") == "COMPLETE"
                and prices.get("extraction_status") == "COMPLETE"
                and old_price is not None
                and old_price in old_elements,
                "OLD_PRICE_PRESENT evidence is incomplete",
            )
        elif status == "OLD_PRICE_EXPLICITLY_ABSENT":
            _require(
                enrichment.get("extraction_status") == "COMPLETE"
                and prices.get("extraction_status") == "COMPLETE"
                and old_price is None
                and not old_elements,
                "OLD_PRICE_EXPLICITLY_ABSENT evidence is inconsistent",
            )

    _require(len(all_keys) == len(set(all_keys)), "Evidence keys are not unique")
    _require(len(search_urls) == len(set(search_urls)), "Search source URLs are not unique")
    _require(
        len(enrichment_urls) == len(set(enrichment_urls)),
        "Enrichment source URLs are not unique",
    )
    batch_start = _timestamp(batch.get("batch_started_at"), "batch_started_at")
    batch_end = _timestamp(batch.get("batch_finished_at"), "batch_finished_at")
    search_start = _timestamp(batch.get("search_phase_started_at"), "search_phase_started_at")
    search_end = _timestamp(batch.get("search_phase_finished_at"), "search_phase_finished_at")
    enrichment_start = _timestamp(
        batch.get("enrichment_phase_started_at"), "enrichment_phase_started_at"
    )
    enrichment_end = _timestamp(
        batch.get("enrichment_phase_finished_at"), "enrichment_phase_finished_at"
    )
    _require(
        batch_start
        <= search_start
        <= min(search_times)
        <= max(search_times)
        <= search_end
        <= enrichment_start
        <= min(enrichment_times)
        <= max(enrichment_times)
        <= enrichment_end
        <= batch_end,
        "Evidence collection phase timestamps are inconsistent",
    )
    _require(
        all(search.get("region_key") == batch.get("region_key") for search in searches)
        and all(
            search.get("location_label") == batch.get("location_label")
            for search in searches
        ),
        "Evidence region/location mismatch",
    )


def _not_found_null_fields() -> tuple[str, ...]:
    return (
        "rank",
        "page_number",
        "position_on_page",
        "ad_flag",
        "search_price_raw",
        "search_availability_raw",
        "rating",
        "reviews_count_observed",
        "enrichment_captured_at",
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
        "extraction_status",
        "price_evidence_status",
        "seller_id_observed",
        "seller_name_observed",
        "raw_ref",
    )


def _price_currency(prices: Mapping[str, Any]) -> str | None:
    classified = [
        element
        for element in prices.get("visible_price_elements", [])
        if isinstance(element, dict)
        and element.get("classification")
        in {"BANK_PRICE", "OTHER_PAYMENT_PRICE", "OLD_PRICE"}
    ]
    if classified and all("₽" in str(element.get("raw_visible_text", "")) for element in classified):
        return "RUB"
    return None


def _card_ad_flag(card: Mapping[str, Any]) -> bool:
    return card.get("ad_marker_raw") is not None


def _validate_payload(payload: Mapping[str, Any], evidence_sha256: str) -> datetime:
    _require(payload.get("contract_version") == PAYLOAD_CONTRACT, "Payload contract mismatch")
    _require(payload.get("mode") == MODE, "Payload mode must be SNAPSHOT")
    batch = payload.get("batch")
    _require(
        payload.get("batch_status") == "SUCCESS"
        and isinstance(batch, dict)
        and batch.get("batch_status") == "SUCCESS",
        "Payload batch is not SUCCESS",
    )
    _require(batch.get("evidence_file_sha256") == evidence_sha256, "Embedded evidence hash mismatch")
    _require("reference_at" not in batch, "batch reference_at is forbidden; reference_at is derived")

    runs = payload.get("search_runs")
    observations = payload.get("observations")
    enrichments = payload.get("enrichments")
    _require(isinstance(runs, list) and runs, "Payload must contain search runs")
    _require(isinstance(observations, list) and observations, "Payload must contain observations")
    _require(isinstance(enrichments, list), "Payload enrichments must be a list")

    _require(
        payload.get("signals") == [] and payload.get("findings") == [],
        "Snapshot analytics must be empty",
    )
    _require("snapshot_semantics" not in payload, "snapshot_semantics is not part of snapshot v1")
    for key in ("comparison_price", "price_delta", "rank_delta"):
        _require(not _contains_key(payload, key), f"{key} is forbidden in snapshot payload")

    run_by_query: dict[tuple[str, str], Mapping[str, Any]] = {}
    captured_times: list[datetime] = []
    raw_source_refs: list[str] = []
    for run in runs:
        _require(isinstance(run, dict), "Search run must be an object")
        offer_id = _text(run.get("offer_id"), "run offer_id")
        query = _text(run.get("query_text_exact"), "run query_text_exact")
        _require(run.get("query_kind") == "OEM", "Snapshot query_kind must be OEM")
        _text(run.get("query_normalized"), "run query_normalized")
        _text(run.get("region_key"), "run region_key")
        _text(run.get("source_url"), "run source_url")
        raw_source_refs.append(_text(run.get("raw_source_ref"), "run raw_source_ref"))
        captured_times.append(_timestamp(run.get("captured_at"), "run captured_at"))
        cards_scanned = run.get("cards_scanned")
        result_count = run.get("result_count_observed")
        _require(isinstance(cards_scanned, int) and cards_scanned >= 0, "Invalid cards_scanned")
        _require(isinstance(result_count, int) and result_count >= 0, "Invalid result_count_observed")
        key = (offer_id, query)
        _require(key not in run_by_query, "Duplicate payload search run")
        run_by_query[key] = run
    _require(len(raw_source_refs) == len(set(raw_source_refs)), "Duplicate search raw_source_ref")
    reference_at = min(captured_times)

    enrichment_by_ref: dict[str, Mapping[str, Any]] = {}
    for enrichment in enrichments:
        _require(isinstance(enrichment, dict), "Normalized enrichment must be an object")
        raw_ref = _text(enrichment.get("raw_ref"), "normalized enrichment raw_ref")
        _require(raw_ref not in enrichment_by_ref, "Duplicate normalized enrichment raw_ref")
        enrichment_by_ref[raw_ref] = enrichment
        _decimal_product_id(enrichment.get("ozon_product_id"), "normalized enrichment product ID")
        _timestamp(enrichment.get("captured_at"), "normalized enrichment captured_at")
        _text(enrichment.get("source_ref"), "normalized enrichment source_ref")
        _require(
            enrichment.get("extraction_status") == "COMPLETE",
            "Normalized enrichment extraction is not COMPLETE",
        )
        _require(
            enrichment.get("price_evidence_status") in COMPLETE_OLD_PRICE_STATUSES,
            "Normalized enrichment price evidence is not COMPLETE",
        )
        _require(_numeric(enrichment.get("bank_price"), "bank price") is not None, "bank_price is required")
        _require(
            _numeric(enrichment.get("other_payment_price"), "other payment price") is not None,
            "other_payment_price is required",
        )
        _text(enrichment.get("currency"), "enrichment currency")
        if enrichment.get("price_evidence_status") == "OLD_PRICE_PRESENT":
            _require(_numeric(enrichment.get("old_price"), "old price") is not None, "old_price is required")
        else:
            _require(enrichment.get("old_price") is None, "Explicitly absent old_price must be null")

    slots: list[tuple[str, str, str]] = []
    used_enrichments: set[str] = set()
    for observation in observations:
        _require(isinstance(observation, dict), "Observation must be an object")
        offer_id = _text(observation.get("offer_id"), "observation offer_id")
        query = _text(observation.get("query_text_exact"), "observation query")
        product_id = _decimal_product_id(observation.get("ozon_product_id"), "observation product ID")
        _require((offer_id, query) in run_by_query, "Observation has no search run")
        run = run_by_query[(offer_id, query)]
        _require(observation.get("captured_at") == run.get("captured_at"), "Observation search timestamp mismatch")
        _require(observation.get("reviews_scope") == "UNKNOWN", "reviews_scope must be UNKNOWN")
        for field in ("currency", "source_ref", "availability_raw"):
            _require(field not in observation, f"Observation field is derived-only: {field}")
        slots.append((offer_id, query, product_id))
        status = observation.get("slot_status")
        _require(status in {"FOUND", "NOT_FOUND_WITHIN_SCAN_LIMIT"}, "Unknown slot_status")
        if status == "FOUND":
            for field in ("rank", "page_number", "position_on_page"):
                _require(isinstance(observation.get(field), int) and observation[field] > 0, f"FOUND {field} is invalid")
            raw_ref = _text(observation.get("raw_ref"), "FOUND raw_ref")
            _require(raw_ref in enrichment_by_ref, "FOUND raw_ref does not resolve in payload")
            _require(
                str(enrichment_by_ref[raw_ref].get("ozon_product_id")) == product_id,
                "FOUND enrichment product ID mismatch",
            )
            used_enrichments.add(raw_ref)
            _timestamp(observation.get("enrichment_captured_at"), "FOUND enrichment_captured_at")
            _require(observation.get("quality_status") == "VALID", "FOUND quality_status must be VALID")
            _require(_numeric(observation.get("bank_price"), "FOUND bank price") is not None, "FOUND bank_price is required")
            _require(_numeric(observation.get("other_payment_price"), "FOUND other payment price") is not None, "FOUND other_payment_price is required")
        else:
            for field in _not_found_null_fields():
                _require(observation.get(field) is None, f"NOT_FOUND field must be null: {field}")
            _require(observation.get("availability_status") == "UNKNOWN", "NOT_FOUND availability must be UNKNOWN")
            _require(observation.get("quality_status") == "NOT_FOUND", "NOT_FOUND quality_status mismatch")
            _require("NOT_FOUND_WITHIN_SCAN_LIMIT" in observation.get("quality_flags", []), "NOT_FOUND quality flag is missing")
    _require(len(slots) == len(set(slots)), "Duplicate logical observation slot")
    _require(used_enrichments == set(enrichment_by_ref), "Normalized enrichments must be used by FOUND observations")
    return reference_at


def _validate_evidence_resolution(payload: Mapping[str, Any], evidence: Mapping[str, Any]) -> None:
    search_evidence = {row["evidence_key"]: row for row in evidence["search_evidence"]}
    enrichment_evidence = {row["evidence_key"]: row for row in evidence["enrichment_evidence"]}
    run_by_query = {(row["offer_id"], row["query_text_exact"]): row for row in payload["search_runs"]}
    normalized_enrichments = {row["raw_ref"]: row for row in payload["enrichments"]}
    _require(
        {row["raw_source_ref"] for row in payload["search_runs"]} == set(search_evidence),
        "Search evidence set mismatch",
    )
    _require(
        set(normalized_enrichments) == set(enrichment_evidence),
        "Enrichment evidence set mismatch",
    )
    evidence_batch = evidence["batch"]
    payload_batch = payload["batch"]
    _require(
        all(payload_batch.get(key) == value for key, value in evidence_batch.items()),
        "Evidence/Payload batch metadata mismatch",
    )
    region = payload.get("region")
    _require(
        isinstance(region, dict)
        and region.get("region_key") == evidence_batch.get("region_key")
        and region.get("location_label") == evidence_batch.get("location_label"),
        "Payload region metadata mismatch",
    )

    for run in payload["search_runs"]:
        source = search_evidence.get(run.get("raw_source_ref"))
        _require(source is not None, "Unresolved search raw_source_ref")
        _require(
            run["offer_id"] == source.get("offer_id")
            and run["query_kind"] == source.get("query_kind")
            and run["query_text_exact"] == source.get("query_text_exact")
            and run["captured_at"] == source.get("captured_at")
            and run["region_key"] == source.get("region_key")
            and run["location_label"] == source.get("location_label")
            and run["status"] == source.get("status")
            and run["source_url"] == source.get("source_url")
            and run["cards_scanned"] == source.get("cards_scanned")
            and run["termination_reason"] == source.get("termination_reason")
            and run["result_count_observed"] == len(source.get("ordered_cards", [])),
            "Search evidence mismatch",
        )

    for enrichment in payload["enrichments"]:
        source = enrichment_evidence.get(enrichment["raw_ref"])
        _require(source is not None, "Unresolved enrichment raw_ref")
        prices = source.get("price_evidence", {})
        _require(
            source.get("extraction_status") == "COMPLETE"
            and prices.get("extraction_status") == "COMPLETE"
            and source.get("old_price_evidence_status") in COMPLETE_OLD_PRICE_STATUSES,
            "FOUND enrichment price evidence is incomplete",
        )
        _require(
            str(enrichment["ozon_product_id"]) == str(source.get("ozon_product_id"))
            and enrichment["captured_at"] == source.get("captured_at")
            and enrichment["source_ref"] == source.get("source_url")
            and enrichment["bank_price"] == prices.get("bank_price_parsed")
            and enrichment["other_payment_price"] == prices.get("other_payment_price_parsed")
            and enrichment["old_price"] == prices.get("old_price_parsed")
            and enrichment["currency"] == _price_currency(prices)
            and enrichment["extraction_status"] == source.get("extraction_status")
            and enrichment["price_evidence_status"] == source.get("old_price_evidence_status"),
            "Enrichment price provenance mismatch",
        )
        product_pairs = (
            ("seller_name_observed", source.get("seller", {}).get("raw_visible_name")),
            ("seller_id_observed", source.get("seller", {}).get("seller_id_parsed")),
            ("availability_raw", source.get("availability", {}).get("raw_visible_text")),
            ("availability_status", source.get("availability", {}).get("status")),
            ("purchase_indicator_raw", source.get("purchase_indicator", {}).get("raw_visible_text")),
            ("purchase_count_observed", source.get("purchase_indicator", {}).get("parsed_count")),
            ("observed_oem_raw", source.get("oem", {}).get("raw_visible_text")),
            ("observed_dimensions_raw", source.get("dimensions", {}).get("raw_visible_text")),
            ("observed_length_mm", source.get("dimensions", {}).get("parsed_length_mm")),
            ("observed_width_mm", source.get("dimensions", {}).get("parsed_width_mm")),
            ("observed_height_mm", source.get("dimensions", {}).get("parsed_height_mm")),
            ("carbon_claim_raw", source.get("carbon_claim", {}).get("raw_visible_text")),
            ("origin_raw", source.get("origin", {}).get("raw_visible_text")),
        )
        _require(all(enrichment[field] == expected for field, expected in product_pairs), "Enrichment product facts mismatch")

    for observation in payload["observations"]:
        run = run_by_query[(observation["offer_id"], observation["query_text_exact"])]
        if observation["slot_status"] != "FOUND":
            continue
        source = enrichment_evidence.get(observation["raw_ref"])
        _require(source is not None, "FOUND raw_ref does not resolve in evidence")
        search = search_evidence[run["raw_source_ref"]]
        card = next(
            (item for item in search["ordered_cards"] if str(item["ozon_product_id"]) == str(observation["ozon_product_id"])),
            None,
        )
        _require(card is not None, "FOUND product is absent from ordered search evidence")
        _require(
            observation["enrichment_captured_at"] == source.get("captured_at")
            and observation["rank"] == card.get("rank")
            and observation["position_on_page"] == card.get("ordinal")
            and observation["rating"] == card.get("rating_parsed")
            and observation["reviews_count_observed"] == card.get("reviews_count_parsed")
            and observation["ad_flag"] == _card_ad_flag(card)
            and observation.get("search_price_raw") == card.get("price_text")
            and observation.get("search_availability_raw") == card.get("availability_raw"),
            "FOUND search/enrichment provenance mismatch",
        )
        normalized = normalized_enrichments[observation["raw_ref"]]
        _require(
            str(observation["ozon_product_id"])
            == str(normalized["ozon_product_id"])
            == str(source.get("ozon_product_id")),
            "FOUND enrichment product ID mismatch",
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
            "extraction_status",
            "price_evidence_status",
        ):
            _require(observation[field] == normalized[field], f"FOUND normalized fact mismatch: {field}")


def load_and_validate_artifacts(
    payload_path: Path,
    evidence_path: Path,
    payload_sha256: str,
    evidence_sha256: str,
) -> ArtifactBundle:
    _validate_sha256(payload_sha256, "Payload hash argument")
    _validate_sha256(evidence_sha256, "Evidence hash argument")
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
    reference_at = _validate_payload(payload, actual_evidence_hash)
    _validate_evidence_resolution(payload, evidence)
    return ArtifactBundle(
        evidence_path=evidence_path,
        payload_path=payload_path,
        evidence_sha256=actual_evidence_hash,
        payload_sha256=actual_payload_hash,
        evidence=evidence,
        payload=payload,
        reference_at=reference_at,
    )


def _slot_key(offer_id: str, query: str, product_id: str) -> tuple[str, str, str]:
    return offer_id, query, product_id


def membership_valid_at(reference: MembershipReference, reference_at: datetime) -> bool:
    return reference.valid_from <= reference_at and (
        reference.valid_to is None or reference_at < reference.valid_to
    )


def order_memberships_by_reference_ordinal(
    memberships: Sequence[MembershipReference],
) -> tuple[MembershipReference, ...]:
    ordinal_by_membership: dict[str, int] = {}
    membership_by_ordinal: dict[int, str] = {}
    for membership in memberships:
        ordinal = membership.reference_ordinal
        if type(ordinal) is not int or ordinal <= 0:
            raise ReferenceConflictError(
                "REFERENCE_CONFLICT: membership reference_ordinal must be a positive integer"
            )
        existing_ordinal = ordinal_by_membership.setdefault(membership.membership_id, ordinal)
        if existing_ordinal != ordinal:
            raise ReferenceConflictError(
                "REFERENCE_CONFLICT: membership reference_ordinal is inconsistent"
            )
        existing_membership = membership_by_ordinal.setdefault(ordinal, membership.membership_id)
        if existing_membership != membership.membership_id:
            raise ReferenceConflictError(
                "REFERENCE_CONFLICT: duplicate reference_ordinal across memberships"
            )
    return tuple(sorted(memberships, key=lambda membership: membership.reference_ordinal))


def derive_reference_layer(snapshot: ProductionSnapshot, reference_at: datetime) -> ReferenceLayer:
    memberships = [
        reference
        for reference in order_memberships_by_reference_ordinal(snapshot.memberships)
        if reference.membership_status in MONITORED_MEMBERSHIP_STATUSES
        and membership_valid_at(reference, reference_at)
    ]
    oem_candidates: dict[tuple[str, str], list[SkuOemReference]] = {}
    for reference in snapshot.oems:
        if reference.created_at <= reference_at:
            oem_candidates.setdefault((reference.offer_id, reference.oem_normalized), []).append(reference)

    oem_by_query: dict[tuple[str, str], SkuOemReference] = {}
    membership_by_slot: dict[tuple[str, str, str], MembershipReference] = {}
    for membership in memberships:
        if not membership.product_family_id:
            raise ReferenceConflictError("REFERENCE_CONFLICT: listing family relationship is missing")
        matched = tuple(membership.matched_oem_set)
        if not matched or len(matched) != len(set(matched)) or any(not item for item in matched):
            raise ReferenceConflictError("REFERENCE_CONFLICT: matched_oem_set is invalid")
        for oem in matched:
            query_key = (membership.offer_id, oem)
            candidates = oem_candidates.get(query_key, [])
            if len(candidates) != 1:
                raise ReferenceConflictError("REFERENCE_CONFLICT: historical SKU/OEM reference is ambiguous or missing")
            oem_by_query[query_key] = candidates[0]
            slot = _slot_key(membership.offer_id, oem, membership.ozon_product_id)
            if slot in membership_by_slot:
                raise ReferenceConflictError("REFERENCE_CONFLICT: duplicate historical logical slot")
            membership_by_slot[slot] = membership
    if not oem_by_query or not membership_by_slot:
        raise ReferenceConflictError("REFERENCE_CONFLICT: no monitored reference slots at reference time")
    return ReferenceLayer(oem_by_query=oem_by_query, membership_by_slot=membership_by_slot)


def build_import_plan(bundle: ArtifactBundle, snapshot: ProductionSnapshot) -> ImportPlan:
    payload = bundle.payload
    batch_ref = build_batch_ref(bundle.evidence_sha256, bundle.payload_sha256)
    references = derive_reference_layer(snapshot, bundle.reference_at)

    payload_queries = {
        (row["offer_id"], row["query_text_exact"]): row for row in payload["search_runs"]
    }
    if set(payload_queries) != set(references.oem_by_query):
        raise ReferenceConflictError(
            f"REFERENCE_CONFLICT: expected queries={len(references.oem_by_query)} payload={len(payload_queries)}"
        )

    actual_slots = [
        _slot_key(row["offer_id"], row["query_text_exact"], str(row["ozon_product_id"]))
        for row in payload["observations"]
    ]
    actual_slot_set = set(actual_slots)
    expected_slot_set = set(references.membership_by_slot)
    if actual_slot_set != expected_slot_set or len(actual_slots) != len(actual_slot_set):
        raise ReferenceConflictError(
            "REFERENCE_CONFLICT: slot reconciliation failed: "
            f"expected={len(expected_slot_set)} payload={len(actual_slots)} "
            f"missing={len(expected_slot_set-actual_slot_set)} "
            f"extra={len(actual_slot_set-expected_slot_set)}"
        )

    search_rows: list[dict[str, Any]] = []
    run_by_query: dict[tuple[str, str], dict[str, Any]] = {}
    for source in payload["search_runs"]:
        query_key = (source["offer_id"], source["query_text_exact"])
        oem = references.oem_by_query[query_key]
        if source["query_normalized"] != oem.oem_normalized:
            raise ReferenceConflictError("REFERENCE_CONFLICT: query normalization mismatch")
        collection_ref = build_collection_ref(
            batch_ref, source["offer_id"], source["query_kind"], source["query_text_exact"]
        )
        row = {
            "search_run_id": build_search_run_id(collection_ref),
            "offer_id": source["offer_id"],
            "sku_oem_id": oem.sku_oem_id,
            "query_kind": source["query_kind"],
            "query_text_exact": source["query_text_exact"],
            "query_normalized": source["query_normalized"],
            "region_key": source["region_key"],
            "location_label": source.get("location_label"),
            "captured_at": _timestamp(source["captured_at"], "run captured_at"),
            "status": source["status"],
            "page_count_observed": source.get("page_count_observed"),
            "result_count_observed": source["result_count_observed"],
            "collection_ref": collection_ref,
            "raw_source_ref": source["raw_source_ref"],
        }
        search_rows.append(row)
        run_by_query[query_key] = row

    enrichments = {row["raw_ref"]: row for row in payload["enrichments"]}
    observation_rows: list[dict[str, Any]] = []
    for source in payload["observations"]:
        product_id = str(source["ozon_product_id"])
        slot = _slot_key(source["offer_id"], source["query_text_exact"], product_id)
        membership = references.membership_by_slot[slot]
        if source["membership_status"] != membership.membership_status:
            raise ReferenceConflictError("REFERENCE_CONFLICT: membership status mismatch")
        if source.get("seller_id_observed") is not None and source["seller_id_observed"] != membership.seller_id:
            raise ReferenceConflictError("REFERENCE_CONFLICT: seller ID mismatch")
        run = run_by_query[(source["offer_id"], source["query_text_exact"])]
        enrichment = enrichments.get(source.get("raw_ref")) if source.get("raw_ref") else None
        found = source["slot_status"] == "FOUND"
        if found != (enrichment is not None):
            raise ReferenceConflictError("REFERENCE_CONFLICT: enrichment mapping mismatch")
        observation_ref = build_observation_ref(run["collection_ref"], product_id)
        row = {
            "observation_id": build_observation_id(observation_ref),
            "search_run_id": run["search_run_id"],
            "listing_id": membership.listing_id,
            "membership_id": membership.membership_id,
            "captured_at": _timestamp(source["captured_at"], "observation captured_at"),
            "enrichment_captured_at": _optional_timestamp(source.get("enrichment_captured_at"), "enrichment_captured_at"),
            "page_number": source.get("page_number"),
            "position_on_page": source.get("position_on_page"),
            "rank": source.get("rank"),
            "ad_flag": source.get("ad_flag"),
            "bank_price": _numeric(source.get("bank_price"), "bank_price"),
            "other_payment_price": _numeric(source.get("other_payment_price"), "other_payment_price"),
            "old_price": _numeric(source.get("old_price"), "old_price"),
            "currency": enrichment.get("currency") if enrichment else None,
            "rating": _numeric(source.get("rating"), "rating"),
            "reviews_count_observed": source.get("reviews_count_observed"),
            "reviews_scope": source["reviews_scope"],
            "purchase_count_observed": source.get("purchase_count_observed"),
            "purchase_indicator_raw": source.get("purchase_indicator_raw"),
            "availability_status": source["availability_status"],
            "availability_raw": enrichment.get("availability_raw") if enrichment else None,
            "observed_oem_raw": source.get("observed_oem_raw"),
            "observed_dimensions_raw": source.get("observed_dimensions_raw"),
            "observed_length_mm": _numeric(source.get("observed_length_mm"), "length"),
            "observed_width_mm": _numeric(source.get("observed_width_mm"), "width"),
            "observed_height_mm": _numeric(source.get("observed_height_mm"), "height"),
            "carbon_claim_raw": source.get("carbon_claim_raw"),
            "origin_raw": source.get("origin_raw"),
            "quality_status": source["quality_status"],
            "quality_flags": tuple(source.get("quality_flags", [])),
            "source_ref": (
                enrichment["source_ref"]
                if enrichment
                else payload_queries[(source["offer_id"], source["query_text_exact"])][
                    "source_url"
                ]
            ),
            "raw_ref": source.get("raw_ref"),
            "observation_ref": observation_ref,
        }
        observation_rows.append(row)

    validation = validate_planned_rows(tuple(search_rows), tuple(observation_rows), snapshot)
    found_count = sum(row["slot_status"] == "FOUND" for row in payload["observations"])
    return ImportPlan(
        batch_ref=batch_ref,
        reference_at=bundle.reference_at,
        search_rows=tuple(search_rows),
        observation_rows=tuple(observation_rows),
        expected_query_count=len(references.oem_by_query),
        expected_slot_count=len(references.membership_by_slot),
        found=found_count,
        not_found=len(payload["observations"]) - found_count,
        enrichment_backed=sum(row.get("raw_ref") is not None for row in payload["observations"]),
        reference_mismatches=0,
        constraint_violations=validation["constraint_violations"],
        missing_required_values=validation["missing_required_values"],
        fk_failures=validation["fk_failures"],
        unique_conflicts=validation["unique_conflicts"],
    )


def validate_schema(snapshot: ProductionSnapshot) -> None:
    for table, insert_columns in (
        ("competitor_search_runs", SEARCH_INSERT_COLUMNS),
        ("competitor_observations", OBSERVATION_INSERT_COLUMNS),
    ):
        columns = {column.name: column for column in snapshot.schema_columns.get(table, ())}
        if set(insert_columns) - set(columns):
            raise ReferenceConflictError(f"REFERENCE_CONFLICT: production schema is missing {table} columns")
    search_id = {c.name: c for c in snapshot.schema_columns["competitor_search_runs"]}["search_run_id"]
    observation_id = {c.name: c for c in snapshot.schema_columns["competitor_observations"]}["observation_id"]
    if search_id.data_type != "uuid" or observation_id.data_type != "uuid":
        raise ReferenceConflictError("REFERENCE_CONFLICT: production PK types are not UUID")
    if not REQUIRED_CONSTRAINTS.issubset(snapshot.constraint_names):
        raise ReferenceConflictError("REFERENCE_CONFLICT: required production constraints are missing")
    if not REQUIRED_INDEXES.issubset(snapshot.index_names):
        raise ReferenceConflictError("REFERENCE_CONFLICT: required production indexes are missing")


def validate_planned_rows(
    search_rows: tuple[Mapping[str, Any], ...],
    observation_rows: tuple[Mapping[str, Any], ...],
    snapshot: ProductionSnapshot,
) -> dict[str, int]:
    validate_schema(snapshot)
    missing_required = 0
    constraint_violations = 0
    fk_failures = 0
    for table, rows in (("competitor_search_runs", search_rows), ("competitor_observations", observation_rows)):
        for column in snapshot.schema_columns[table]:
            if column.nullable or column.has_default:
                continue
            missing_required += sum(column.name not in row or row[column.name] is None for row in rows)

    oem_ids = {reference.sku_oem_id for reference in snapshot.oems}
    listing_ids = {reference.listing_id for reference in snapshot.memberships}
    membership_ids = {reference.membership_id for reference in snapshot.memberships}
    run_ids = {row["search_run_id"] for row in search_rows}
    for row in search_rows:
        if row["sku_oem_id"] not in oem_ids:
            fk_failures += 1
        if row["query_kind"] != "OEM" or row["result_count_observed"] < 0:
            constraint_violations += 1
    for row in observation_rows:
        if row["search_run_id"] not in run_ids:
            fk_failures += 1
        if row["listing_id"] not in listing_ids or row["membership_id"] not in membership_ids:
            fk_failures += 1
        if row["reviews_scope"] != "UNKNOWN":
            constraint_violations += 1
        if any(row[name] is not None and row[name] <= 0 for name in ("page_number", "position_on_page", "rank")):
            constraint_violations += 1
        if any(row[name] is not None and row[name] < 0 for name in ("bank_price", "other_payment_price", "old_price")):
            constraint_violations += 1
        if any(row[name] is not None for name in ("bank_price", "other_payment_price", "old_price")) and not row["currency"]:
            constraint_violations += 1
        if row["rating"] is not None and not Decimal("0") <= row["rating"] <= Decimal("5"):
            constraint_violations += 1
        if any(row[name] is not None and row[name] < 0 for name in ("reviews_count_observed", "purchase_count_observed")):
            constraint_violations += 1
        if any(row[name] is not None and row[name] <= 0 for name in ("observed_length_mm", "observed_width_mm", "observed_height_mm")):
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
        raise ReferenceConflictError(
            "REFERENCE_CONFLICT: planned rows violate schema: "
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
    if len(planned_by_key) != len(planned) or len(persisted_by_key) != len(persisted):
        return False
    if set(planned_by_key) != set(persisted_by_key):
        return False
    for identity, planned_row in planned_by_key.items():
        persisted_row = persisted_by_key[identity]
        for column, planned_value in planned_row.items():
            if column not in persisted_row or _normalise(planned_value) != _normalise(persisted_row[column]):
                return False
    return True


def determine_history_state(plan: ImportPlan, snapshot: ProductionSnapshot) -> str:
    if not snapshot.search_rows and not snapshot.observation_rows:
        return "NEW_BATCH"
    if _rows_match(plan.search_rows, snapshot.search_rows, "collection_ref") and _rows_match(
        plan.observation_rows, snapshot.observation_rows, "observation_ref"
    ):
        return "EXACT_ALREADY_APPLIED"
    raise BatchConflictError("PARTIAL_BATCH_CONFLICT")


def run_dry_run(bundle: ArtifactBundle, snapshot: ProductionSnapshot) -> ImportResult:
    plan = build_import_plan(bundle, snapshot)
    return ImportResult(history_state=determine_history_state(plan, snapshot), plan=plan)


def _fetch_dicts(cursor: Any, query: str, parameters: tuple[object, ...] = ()) -> list[dict[str, Any]]:
    cursor.execute(query, parameters)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _membership_references_from_rows(
    reference_rows: Sequence[Mapping[str, Any]],
) -> tuple[MembershipReference, ...]:
    membership_by_id: dict[str, MembershipReference] = {}
    membership_by_ordinal: dict[int, str] = {}
    for row in reference_rows:
        record_kind = row["record_kind"]
        reference_ordinal = row.get("reference_ordinal")
        if record_kind in {"PROFILE", "SKU_OEM"}:
            if reference_ordinal is not None:
                raise DatabaseError(
                    "Non-membership reference-plan row has a non-NULL reference_ordinal"
                )
            continue
        if record_kind != "MEMBERSHIP_QUERY":
            continue
        if type(reference_ordinal) is not int or reference_ordinal <= 0:
            raise DatabaseError(
                "Membership reference-plan row has an invalid reference_ordinal"
            )
        membership_id = row["membership_id"]
        ordinal_owner = membership_by_ordinal.setdefault(reference_ordinal, membership_id)
        if ordinal_owner != membership_id:
            raise DatabaseError(
                "Reference-plan reference_ordinal belongs to multiple memberships"
            )
        membership = MembershipReference(
            membership_id=membership_id,
            offer_id=row["offer_id"],
            membership_status=row["membership_status"],
            matched_oem_set=tuple(row["matched_oem_set"]),
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            listing_id=row["listing_id"],
            product_family_id=row["product_family_id"],
            ozon_product_id=row["ozon_product_id"],
            seller_id=row["seller_id"],
            reference_ordinal=reference_ordinal,
            product_name=row["product_name"],
        )
        existing = membership_by_id.setdefault(membership.membership_id, membership)
        if existing != membership:
            raise DatabaseError("Reference-plan membership rows are inconsistent")
    return order_memberships_by_reference_ordinal(tuple(membership_by_id.values()))


def read_production_snapshot(connection: Any, reference_at: datetime) -> ProductionSnapshot:
    """Read schema and all versioned references; no history facts are changed."""

    try:
        with connection.cursor() as cursor:
            reference_rows = _fetch_dicts(cursor, REFERENCE_PLAN_SQL)
            count_row = _fetch_dicts(cursor, SNAPSHOT_COUNTS_SQL)[0]
            column_rows = _fetch_dicts(cursor, WRITE_TARGET_COLUMNS_SQL)
            constraint_rows = _fetch_dicts(cursor, WRITE_TARGET_CONSTRAINTS_SQL)
            index_rows = _fetch_dicts(cursor, WRITE_TARGET_INDEXES_SQL)
    except Exception as error:
        raise DatabaseError("Read-only production reference reconciliation failed") from error

    profile_rows = [row for row in reference_rows if row["record_kind"] == "PROFILE"]
    oem_rows = [row for row in reference_rows if row["record_kind"] == "SKU_OEM"]
    memberships = _membership_references_from_rows(reference_rows)

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
                oem_normalized=row["query_normalized"],
                active=bool(row["oem_active"]),
                created_at=row["oem_created_at"],
            )
            for row in oem_rows
        ),
        memberships=memberships,
        history_counts={name: int(count_row[name]) for name in count_row},
        search_rows=(),
        observation_rows=(),
        schema_columns={table: tuple(columns) for table, columns in schema.items()},
        constraint_names=frozenset(row["conname"] for row in constraint_rows),
        index_names=frozenset(row["indexname"] for row in index_rows),
    )


def read_batch_history(
    connection: Any, plan: ImportPlan, snapshot: ProductionSnapshot
) -> ProductionSnapshot:
    collection_refs = [row["collection_ref"] for row in plan.search_rows]
    search_run_ids = [row["search_run_id"] for row in plan.search_rows]
    try:
        with connection.cursor() as cursor:
            search_rows = _fetch_dicts(
                cursor,
                SNAPSHOT_RUNS_SQL,
                (collection_refs,),
            )
            observation_rows = _fetch_dicts(
                cursor,
                SNAPSHOT_OBSERVATIONS_SQL,
                (search_run_ids,),
            )
    except Exception as error:
        raise DatabaseError("Read-only current-batch history lookup failed") from error
    return replace(snapshot, search_rows=tuple(search_rows), observation_rows=tuple(observation_rows))


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
        host=environment["EFA_DB_HOST"].strip(),
        port=port,
        name=environment["EFA_DB_NAME"].strip(),
        user=environment["EFA_DB_USER"].strip(),
        password=environment["EFA_DB_PASSWORD"],
    )


def connect_database(config: DatabaseConfig, *, read_only: bool) -> Any:
    try:
        import psycopg2

        options = (
            "-c default_transaction_read_only=on -c statement_timeout=15000"
            if read_only
            else "-c statement_timeout=60000"
        )
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
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (ADVISORY_LOCK_KEY,),
            )
        bundle = load_and_validate_artifacts(
            payload_path, evidence_path, payload_sha256, evidence_sha256
        )
        reference_snapshot = read_production_snapshot(connection, bundle.reference_at)
        plan = build_import_plan(bundle, reference_snapshot)
        before = read_batch_history(connection, plan, reference_snapshot)
        state = determine_history_state(plan, before)
        if state == "EXACT_ALREADY_APPLIED":
            connection.rollback()
            return ImportResult(history_state=state, plan=plan)
        if state != "NEW_BATCH":
            raise BatchConflictError("PARTIAL_BATCH_CONFLICT")
        _insert_plan(connection, plan)

        after_references = read_production_snapshot(connection, bundle.reference_at)
        after_plan = build_import_plan(bundle, after_references)
        if not _rows_match(plan.search_rows, after_plan.search_rows, "collection_ref") or not _rows_match(
            plan.observation_rows, after_plan.observation_rows, "observation_ref"
        ):
            raise ReferenceConflictError("REFERENCE_CONFLICT: reference layer changed during import")
        after = read_batch_history(connection, plan, after_references)
        if determine_history_state(plan, after) != "EXACT_ALREADY_APPLIED":
            raise BatchConflictError("PARTIAL_BATCH_CONFLICT: post-insert exact validation failed")
        connection.commit()
        return ImportResult(
            history_state="APPLIED",
            plan=plan,
            inserts=len(plan.search_rows) + len(plan.observation_rows),
        )
    except Exception:
        connection.rollback()
        raise


def validate_write_gate(write: bool, environment: Mapping[str, str]) -> None:
    if write and environment.get(WRITE_GATE, "").strip().lower() != "true":
        raise ConfigurationError(
            "Write requires both --write and COMPETITOR_SNAPSHOT_WRITE_ENABLED=true"
        )


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evidence-first Competitor Monitor snapshot importer v1")
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
    reference_at = result.plan.reference_at.astimezone(timezone.utc)
    reference_text = reference_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    print(f"REFERENCE_AT={reference_text}")
    print(f"HISTORY_STATE={result.history_state}")
    print(f"SEARCH_RUNS_PLANNED={len(result.plan.search_rows)}")
    print(f"OBSERVATIONS_PLANNED={len(result.plan.observation_rows)}")
    print(f"EXPECTED_QUERIES={result.plan.expected_query_count}")
    print(f"EXPECTED_SLOTS={result.plan.expected_slot_count}")
    print(f"FOUND={result.plan.found}")
    print(f"NOT_FOUND={result.plan.not_found}")
    print(f"ENRICHMENT_BACKED={result.plan.enrichment_backed}")
    print(f"REFERENCE_MISMATCHES={result.plan.reference_mismatches}")
    print(f"CONSTRAINT_VIOLATIONS={result.plan.constraint_violations}")
    print(f"MISSING_REQUIRED_VALUES={result.plan.missing_required_values}")
    print(f"FK_FAILURES={result.plan.fk_failures}")
    print(f"UNIQUE_CONFLICTS={result.plan.unique_conflicts}")
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
        args.payload, args.evidence, args.payload_sha256, args.evidence_sha256
    )
    config = load_database_config(env)
    connection = (
        connect_database(config, read_only=not args.write)
        if connection_factory is None
        else connection_factory(config)
    )
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
            reference_snapshot = read_production_snapshot(connection, bundle.reference_at)
            plan = build_import_plan(bundle, reference_snapshot)
            batch_snapshot = read_batch_history(connection, plan, reference_snapshot)
            result = ImportResult(
                history_state=determine_history_state(plan, batch_snapshot), plan=plan
            )
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
