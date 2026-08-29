"""Canonical Work Evidence to Competitor Snapshot Payload builder v1.

This module has no browser or database dependency.  It accepts one immutable
Work Evidence document and one already-frozen reference plan, validates their
exact reconciliation, and produces a deterministic snapshot payload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import import_competitor_snapshot_v1 as snapshot_importer


EVIDENCE_CONTRACT = "competitor_snapshot_evidence.v1"
PAYLOAD_CONTRACT = "competitor_snapshot_payload.v1"
REFERENCE_PLAN_CONTRACT = "competitor_snapshot_reference_plan.v1"
EXPECTED_REGION_KEY = "OZON_RU:DISPLAY:ПОЧТА_РОССИИ|ВЕНЁВСКАЯ_УЛ_3А"
EXPECTED_LOCATION_LABEL = "Почта России • Венёвская ул., 3а"
EXPECTED_SOURCE = "OZON_BUYER_WORK"
EXPECTED_COLLECTION_METHOD = "MANUAL_CONTROLLED_WORK_BROWSER"
PAYLOAD_BATCH_FIELDS = (
    "batch_started_at",
    "batch_finished_at",
    "search_phase_started_at",
    "search_phase_finished_at",
    "enrichment_phase_started_at",
    "enrichment_phase_finished_at",
    "region_key",
    "location_label",
    "batch_status",
    "source",
    "collection_method",
    "scan_limit",
    "product_pages_opened",
)


class BuilderError(RuntimeError):
    pass


class EvidenceValidationError(BuilderError):
    pass


class ReferencePlanError(BuilderError):
    pass


def canonical_pretty_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def canonical_sorted_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise EvidenceValidationError(f"{label} must be an RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceValidationError(f"{label} is malformed") from error
    if parsed.tzinfo is None:
        raise EvidenceValidationError(f"{label} lacks timezone")
    return parsed.astimezone(timezone.utc)


def load_immutable_evidence(path: Path, required_sha256: str | None = None) -> tuple[dict[str, Any], str, int]:
    if not path.is_file():
        raise EvidenceValidationError("Evidence artifact was not found")
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    if required_sha256 is not None and digest != required_sha256.lower():
        raise EvidenceValidationError("Evidence SHA-256 mismatch")
    try:
        evidence = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceValidationError("Evidence is not readable UTF-8 JSON") from error
    if not isinstance(evidence, dict):
        raise EvidenceValidationError("Evidence root must be an object")
    return evidence, digest, len(raw)


def _challenge_detected(value: object, *, path: str = "$") -> bool:
    challenge_keys = {
        "captcha",
        "captcha_detected",
        "antibot",
        "antibot_detected",
        "login_challenge",
        "incident_state",
        "challenge_detected",
    }
    challenge_phrases = (
        "antibot challenge",
        "captcha challenge",
        "login challenge",
        "incident/system page",
        "доступ ограничен",
        "проверка, что вы не робот",
    )
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in challenge_keys and item not in (None, False, "", "NONE", "NOT_DETECTED"):
                return True
            if _challenge_detected(item, path=f"{path}.{key}"):
                return True
    elif isinstance(value, list):
        return any(_challenge_detected(item, path=f"{path}[]") for item in value)
    elif isinstance(value, str):
        lowered = value.casefold()
        return any(phrase in lowered for phrase in challenge_phrases)
    return False


def validate_evidence(evidence: Mapping[str, Any]) -> datetime:
    try:
        snapshot_importer._validate_evidence(evidence)
    except snapshot_importer.ImporterError as error:
        raise EvidenceValidationError(str(error)) from error
    batch = evidence["batch"]
    exact = {
        "region_key": EXPECTED_REGION_KEY,
        "location_label": EXPECTED_LOCATION_LABEL,
        "source": EXPECTED_SOURCE,
        "collection_method": EXPECTED_COLLECTION_METHOD,
    }
    for name, expected in exact.items():
        if batch.get(name) != expected:
            raise EvidenceValidationError(f"Evidence {name} mismatch")
    if _challenge_detected(evidence):
        raise EvidenceValidationError("Evidence contains a challenge or incident marker")
    searches = evidence["search_evidence"]
    if any(
        row.get("status") != "SUCCESS" or row.get("extraction_status") != "COMPLETE"
        for row in searches
    ):
        raise EvidenceValidationError("Evidence contains an incomplete search query")
    reference_at = min(
        parse_timestamp(row["captured_at"], "search captured_at") for row in searches
    )
    if "reference_at" in batch:
        supplied_reference_at = parse_timestamp(
            batch["reference_at"], "evidence batch reference_at"
        )
        if supplied_reference_at != reference_at:
            raise EvidenceValidationError(
                "Evidence batch reference_at differs from derived reference_at"
            )
    return reference_at


def freeze_reference_plan(
    snapshot: snapshot_importer.ProductionSnapshot,
    reference_at: datetime,
    product_names: Mapping[str, str],
) -> dict[str, Any]:
    references = snapshot_importer.derive_reference_layer(snapshot, reference_at)
    memberships = [
        membership
        for membership in snapshot_importer.order_memberships_by_reference_ordinal(
            snapshot.memberships
        )
        if membership.membership_status in snapshot_importer.MONITORED_MEMBERSHIP_STATUSES
        and snapshot_importer.membership_valid_at(membership, reference_at)
    ]
    queries: list[dict[str, Any]] = []
    seen_queries: set[tuple[str, str]] = set()
    for membership in memberships:
        for query_text in membership.matched_oem_set:
            key = (membership.offer_id, query_text)
            if key in seen_queries:
                continue
            seen_queries.add(key)
            oem = references.oem_by_query[key]
            queries.append(
                {
                    "ordinal": len(queries) + 1,
                    "offer_id": membership.offer_id,
                    "query_kind": "OEM",
                    "query_text_exact": query_text,
                    "query_normalized": oem.oem_normalized,
                    "sku_oem_id": oem.sku_oem_id,
                }
            )
    slots: list[dict[str, Any]] = []
    for query in queries:
        offer_id = query["offer_id"]
        query_text = query["query_text_exact"]
        for membership in memberships:
            if membership.offer_id != offer_id or query_text not in membership.matched_oem_set:
                continue
            product_name = product_names.get(membership.listing_id)
            if not product_name:
                raise ReferencePlanError("Reference listing product_name is missing")
            slots.append(
                {
                    "ordinal": len(slots) + 1,
                    "offer_id": offer_id,
                    "query_text_exact": query_text,
                    "ozon_product_id": membership.ozon_product_id,
                    "product_name": product_name,
                    "membership_status": membership.membership_status,
                    "membership_id": membership.membership_id,
                    "listing_id": membership.listing_id,
                    "product_family_id": membership.product_family_id,
                    "seller_id": membership.seller_id,
                }
            )
    plan = {
        "contract_version": REFERENCE_PLAN_CONTRACT,
        "reference_at": reference_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "region_key": EXPECTED_REGION_KEY,
        "location_label": EXPECTED_LOCATION_LABEL,
        "source": EXPECTED_SOURCE,
        "collection_method": EXPECTED_COLLECTION_METHOD,
        "expected_queries": len(queries),
        "expected_slots": len(slots),
        "queries": queries,
        "slots": slots,
    }
    validate_reference_plan(plan)
    return plan


def validate_reference_plan(plan: Mapping[str, Any]) -> None:
    if plan.get("contract_version") != REFERENCE_PLAN_CONTRACT:
        raise ReferencePlanError("Reference plan contract mismatch")
    for name, expected in (
        ("region_key", EXPECTED_REGION_KEY),
        ("location_label", EXPECTED_LOCATION_LABEL),
        ("source", EXPECTED_SOURCE),
        ("collection_method", EXPECTED_COLLECTION_METHOD),
    ):
        if plan.get(name) != expected:
            raise ReferencePlanError(f"Reference plan {name} mismatch")
    parse_timestamp(plan.get("reference_at"), "reference plan reference_at")
    queries = plan.get("queries")
    slots = plan.get("slots")
    if not isinstance(queries, list) or not queries or not isinstance(slots, list) or not slots:
        raise ReferencePlanError("Reference plan queries/slots are empty")
    query_keys = [(row.get("offer_id"), row.get("query_text_exact")) for row in queries]
    slot_keys = [
        (row.get("offer_id"), row.get("query_text_exact"), str(row.get("ozon_product_id")))
        for row in slots
    ]
    if len(query_keys) != len(set(query_keys)):
        raise ReferencePlanError("Reference plan queries are not unique")
    if len(slot_keys) != len(set(slot_keys)):
        raise ReferencePlanError("Reference plan slots are not unique")
    if any((slot[0], slot[1]) not in set(query_keys) for slot in slot_keys):
        raise ReferencePlanError("Reference plan slot has no query")
    if plan.get("expected_queries") != len(queries) or plan.get("expected_slots") != len(slots):
        raise ReferencePlanError("Reference plan counts mismatch")
    if [row.get("ordinal") for row in queries] != list(range(1, len(queries) + 1)):
        raise ReferencePlanError("Reference query ordinals are invalid")
    if [row.get("ordinal") for row in slots] != list(range(1, len(slots) + 1)):
        raise ReferencePlanError("Reference slot ordinals are invalid")


def validate_evidence_against_plan(evidence: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    validate_reference_plan(plan)
    reference_at = validate_evidence(evidence)
    if parse_timestamp(plan["reference_at"], "reference plan reference_at") != reference_at:
        raise EvidenceValidationError("Evidence reference_at differs from frozen plan")
    searches = evidence["search_evidence"]
    actual_queries = {(row["offer_id"], row["query_text_exact"]) for row in searches}
    expected_queries = {(row["offer_id"], row["query_text_exact"]) for row in plan["queries"]}
    if actual_queries != expected_queries or len(searches) != len(expected_queries):
        raise EvidenceValidationError(
            "Evidence query reconciliation failed: "
            f"expected={len(expected_queries)} actual={len(searches)}"
        )
    searches_by_key = {(row["offer_id"], row["query_text_exact"]): row for row in searches}
    found_products: set[str] = set()
    for slot in plan["slots"]:
        search = searches_by_key[(slot["offer_id"], slot["query_text_exact"])]
        cards = {
            str(card["ozon_product_id"]): card for card in search["ordered_cards"]
        }
        product_id = str(slot["ozon_product_id"])
        if product_id in cards:
            found_products.add(product_id)
    enrichments = evidence["enrichment_evidence"]
    enrichment_products = {str(row["ozon_product_id"]) for row in enrichments}
    if enrichment_products != found_products or len(enrichments) != len(enrichment_products):
        raise EvidenceValidationError(
            "Evidence enrichment reconciliation failed: "
            f"expected={len(found_products)} actual={len(enrichments)}"
        )


def _normalized_enrichment(source: Mapping[str, Any]) -> dict[str, Any]:
    prices = source["price_evidence"]
    return {
        "enrichment_key": source.get("enrichment_key", f"OZON:{source['ozon_product_id']}"),
        "ozon_product_id": str(source["ozon_product_id"]),
        "captured_at": source["captured_at"],
        "source_ref": source["source_url"],
        "raw_ref": source["evidence_key"],
        "extraction_status": source["extraction_status"],
        "price_evidence_status": source["old_price_evidence_status"],
        "seller_name_observed": source["seller"]["raw_visible_name"],
        "seller_id_observed": source["seller"]["seller_id_parsed"],
        "bank_price": prices["bank_price_parsed"],
        "other_payment_price": prices["other_payment_price_parsed"],
        "old_price": prices["old_price_parsed"],
        "currency": "RUB",
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


def _not_found_observation(slot: Mapping[str, Any], captured_at: str) -> dict[str, Any]:
    return {
        "offer_id": slot["offer_id"],
        "product_name": slot["product_name"],
        "query_text_exact": slot["query_text_exact"],
        "ozon_product_id": str(slot["ozon_product_id"]),
        "membership_status": slot["membership_status"],
        "slot_status": "NOT_FOUND_WITHIN_SCAN_LIMIT",
        "captured_at": captured_at,
        "page_number": None,
        "position_on_page": None,
        "rank": None,
        "ad_flag": None,
        "rating": None,
        "reviews_count_observed": None,
        "reviews_scope": "UNKNOWN",
        "search_price_raw": None,
        "search_availability_raw": None,
        "enrichment_captured_at": None,
        "bank_price": None,
        "other_payment_price": None,
        "old_price": None,
        "availability_status": "UNKNOWN",
        "seller_name_observed": None,
        "seller_id_observed": None,
        "quality_status": "NOT_FOUND",
        "quality_flags": ["NOT_FOUND_WITHIN_SCAN_LIMIT"],
        "raw_ref": None,
        "purchase_indicator_raw": None,
        "purchase_count_observed": None,
        "observed_oem_raw": None,
        "observed_dimensions_raw": None,
        "observed_length_mm": None,
        "observed_width_mm": None,
        "observed_height_mm": None,
        "carbon_claim_raw": None,
        "origin_raw": None,
        "extraction_status": None,
        "price_evidence_status": None,
    }


def _found_observation(
    slot: Mapping[str, Any], search: Mapping[str, Any], card: Mapping[str, Any],
    enrichment: Mapping[str, Any],
) -> dict[str, Any]:
    row = _not_found_observation(slot, str(search["captured_at"]))
    row.update(
        {
            "slot_status": "FOUND",
            "page_number": 1,
            "position_on_page": card["rank"],
            "rank": card["rank"],
            "ad_flag": card.get("ad_marker_raw") is not None,
            "rating": card.get("rating_parsed"),
            "reviews_count_observed": card.get("reviews_count_parsed"),
            "search_price_raw": card.get("price_text"),
            "search_availability_raw": card.get("availability_raw"),
            "enrichment_captured_at": enrichment["captured_at"],
            "bank_price": enrichment["bank_price"],
            "other_payment_price": enrichment["other_payment_price"],
            "old_price": enrichment["old_price"],
            "availability_status": enrichment["availability_status"],
            "seller_name_observed": enrichment["seller_name_observed"],
            "seller_id_observed": enrichment["seller_id_observed"],
            "quality_status": "VALID",
            "quality_flags": [],
            "raw_ref": enrichment["raw_ref"],
            "purchase_indicator_raw": enrichment["purchase_indicator_raw"],
            "purchase_count_observed": enrichment["purchase_count_observed"],
            "observed_oem_raw": enrichment["observed_oem_raw"],
            "observed_dimensions_raw": enrichment["observed_dimensions_raw"],
            "observed_length_mm": enrichment["observed_length_mm"],
            "observed_width_mm": enrichment["observed_width_mm"],
            "observed_height_mm": enrichment["observed_height_mm"],
            "carbon_claim_raw": enrichment["carbon_claim_raw"],
            "origin_raw": enrichment["origin_raw"],
            "extraction_status": enrichment["extraction_status"],
            "price_evidence_status": enrichment["price_evidence_status"],
        }
    )
    return row


def build_payload(
    evidence: Mapping[str, Any], evidence_sha256: str, plan: Mapping[str, Any]
) -> dict[str, Any]:
    validate_evidence_against_plan(evidence, plan)
    query_plan = {
        (row["offer_id"], row["query_text_exact"]): row for row in plan["queries"]
    }
    searches = {
        (row["offer_id"], row["query_text_exact"]): row
        for row in evidence["search_evidence"]
    }
    search_runs = []
    for source in evidence["search_evidence"]:
        query = query_plan[(source["offer_id"], source["query_text_exact"])]
        search_runs.append(
            {
                "offer_id": source["offer_id"],
                "query_kind": source["query_kind"],
                "query_text_exact": source["query_text_exact"],
                "query_normalized": query["query_normalized"],
                "captured_at": source["captured_at"],
                "status": source["status"],
                "cards_scanned": source["cards_scanned"],
                "result_count_observed": len(source["ordered_cards"]),
                "termination_reason": source["termination_reason"],
                "region_key": source["region_key"],
                "location_label": source["location_label"],
                "source_url": source["source_url"],
                "raw_source_ref": source["evidence_key"],
            }
        )
    enrichments = [_normalized_enrichment(row) for row in evidence["enrichment_evidence"]]
    enrichment_by_product = {row["ozon_product_id"]: row for row in enrichments}
    observations = []
    for slot in plan["slots"]:
        search = searches[(slot["offer_id"], slot["query_text_exact"])]
        cards = {str(row["ozon_product_id"]): row for row in search["ordered_cards"]}
        product_id = str(slot["ozon_product_id"])
        card = cards.get(product_id)
        observations.append(
            _not_found_observation(slot, str(search["captured_at"]))
            if card is None
            else _found_observation(slot, search, card, enrichment_by_product[product_id])
        )
    projected_batch = {
        name: evidence["batch"][name]
        for name in PAYLOAD_BATCH_FIELDS
        if name in evidence["batch"]
    }
    batch = dict(projected_batch)
    batch["evidence_file_sha256"] = evidence_sha256
    payload = {
        "contract_version": PAYLOAD_CONTRACT,
        "mode": "SNAPSHOT",
        "batch_status": "SUCCESS",
        "batch": batch,
        "region": {
            "region_key": batch["region_key"],
            "location_label": batch["location_label"],
        },
        "search_runs": search_runs,
        "observations": observations,
        "enrichments": enrichments,
        "signals": [],
        "findings": [],
    }
    try:
        snapshot_importer._validate_payload(payload, evidence_sha256)
        snapshot_importer._validate_evidence_resolution(payload, evidence)
    except snapshot_importer.ImporterError as error:
        raise EvidenceValidationError(str(error)) from error
    return payload


def payload_identity(payload: Mapping[str, Any], evidence_sha256: str) -> tuple[bytes, str, str]:
    rendered = canonical_pretty_bytes(payload)
    payload_sha256 = sha256_bytes(rendered)
    batch_ref = snapshot_importer.build_batch_ref(evidence_sha256, payload_sha256)
    return rendered, payload_sha256, batch_ref


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canonical Competitor Snapshot artifact builder v1")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--evidence-sha256")
    parser.add_argument("--reference-plan", type=Path, required=True)
    parser.add_argument("--payload-output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    evidence, evidence_sha256, evidence_size = load_immutable_evidence(
        args.evidence, args.evidence_sha256
    )
    try:
        plan = json.loads(args.reference_plan.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReferencePlanError("Reference plan is not readable UTF-8 JSON") from error
    payload = build_payload(evidence, evidence_sha256, plan)
    rendered, payload_sha256, batch_ref = payload_identity(payload, evidence_sha256)
    args.payload_output.write_bytes(rendered)
    print(f"EVIDENCE_SHA256={evidence_sha256}")
    print(f"EVIDENCE_SIZE={evidence_size}")
    print(f"PAYLOAD_SHA256={payload_sha256}")
    print(f"BATCH_REF={batch_ref}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuilderError as error:
        print(f"ERROR={error}")
        raise SystemExit(1)
