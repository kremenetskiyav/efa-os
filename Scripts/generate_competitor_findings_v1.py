"""Read-only factual Finding Engine v1 for Competitor Monitor analyses."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

import analyze_competitor_snapshots_v1 as snapshot_analyzer


CONTRACT_VERSION = "competitor_finding_set.v1"
SOURCE_CONTRACT_VERSION = "competitor_snapshot_analysis.v1"
STATUS = "PROPOSED"

FINDING_KINDS = {
    "OWN_SEARCH_VISIBILITY_LOST": "ISSUE",
    "OWN_SEARCH_VISIBILITY_RESTORED": "SIGNAL",
    "COMPETITOR_VISIBILITY_LOST": "SIGNAL",
    "COMPETITOR_VISIBILITY_RESTORED": "SIGNAL",
    "COMPETITOR_PRICE_INCREASED": "SIGNAL",
    "COMPETITOR_PRICE_DECREASED": "SIGNAL",
}
FINDING_TYPES = tuple(FINDING_KINDS)
SEVERITIES = ("INFO", "WATCH", "IMPORTANT")
MEMBERSHIPS = ("CONTROL", "PRIMARY", "RESERVE")
CONFIDENCES = ("HIGH", "MEDIUM")

RESOLUTION_QUERY = """
SELECT
    r.search_run_id::text,
    r.offer_id,
    r.query_text_exact,
    r.region_key,
    r.location_label,
    r.captured_at AS run_captured_at,
    r.status AS run_status,
    r.collection_ref,
    r.raw_source_ref,
    o.observation_id::text,
    o.listing_id::text,
    o.ozon_product_id::text,
    o.membership_status,
    o.captured_at,
    o.currency,
    o.reviews_scope,
    o.quality_status,
    o.quality_flags,
    o.source_ref,
    o.raw_ref,
    o.observation_ref
FROM mcp_read.competitor_snapshot_runs AS r
JOIN mcp_read.competitor_snapshot_observations AS o
  ON o.search_run_id = r.search_run_id
WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%'
   OR r.collection_ref LIKE 'cm-snapshot-v1:run:%'
ORDER BY r.captured_at, r.collection_ref, r.offer_id,
         r.query_text_exact, o.ozon_product_id
"""

COUNTS_QUERY = """
SELECT
  (SELECT count(*) FROM mcp_read.competitor_snapshot_runs) AS search_runs,
  (SELECT count(*) FROM mcp_read.competitor_snapshot_observations) AS observations,
  0::bigint AS reviews,
  0::bigint AS findings
"""

APPROVED_READ_SQL = (RESOLUTION_QUERY, COUNTS_QUERY)


class FindingEngineError(RuntimeError):
    pass


class InputContractError(FindingEngineError):
    pass


class EvidenceResolutionError(FindingEngineError):
    pass


class FindingContractError(FindingEngineError):
    pass


def _slot_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return str(row["offer_id"]), str(row["query_text_exact"]), str(row["ozon_product_id"])


def _listing_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row["offer_id"]), str(row["ozon_product_id"])


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _number(value: Decimal) -> int | float:
    integral = value.to_integral_value()
    return int(integral) if value == integral else float(value)


def _validate_source_analysis(analysis: Mapping[str, Any]) -> None:
    if analysis.get("contract_version") != SOURCE_CONTRACT_VERSION:
        raise InputContractError("Unsupported source analysis contract")
    comparisons = analysis.get("comparisons")
    if not isinstance(comparisons, list):
        raise InputContractError("Source comparisons must be an array")
    keys = [_slot_key(row) for row in comparisons]
    if len(keys) != len(set(keys)):
        raise InputContractError("Source analysis contains duplicate logical slots")
    for name in ("previous_snapshot", "current_snapshot"):
        snapshot = analysis.get(name)
        if not isinstance(snapshot, Mapping) or not snapshot.get("derived_batch_id"):
            raise InputContractError(f"Source analysis lacks {name} identity")
    summary = analysis.get("summary")
    if isinstance(summary, Mapping) and summary.get("slots_total") != len(comparisons):
        raise InputContractError("Source analysis slot total mismatch")


def load_source_analysis(path: Path, required_sha256: str | None = None) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if required_sha256 is not None and digest != required_sha256.lower():
        raise InputContractError("Source analysis SHA-256 mismatch")
    try:
        analysis = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InputContractError("Source analysis is not readable UTF-8 JSON") from error
    _validate_source_analysis(analysis)
    return analysis, digest


def _evidence_record(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "observation_id": str(row["observation_id"]),
        "observation_ref": str(row["observation_ref"]),
        "listing_id": str(row["listing_id"]),
        "membership_status": row.get("membership_status"),
        "currency": row.get("currency"),
        "reviews_scope": row.get("reviews_scope"),
        "quality_status": row.get("quality_status"),
        "quality_flags": list(row.get("quality_flags") or ()),
        "source_ref": str(row["source_ref"]),
        "raw_ref": row.get("raw_ref"),
        "raw_source_ref": row.get("raw_source_ref"),
    }


def _index_evidence_rows(rows: Sequence[Mapping[str, Any]], side: str) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    observation_ids: set[str] = set()
    for row in rows:
        key = _slot_key(row)
        observation_id = str(row["observation_id"])
        if key in result:
            raise EvidenceResolutionError(f"Duplicate {side} logical slot resolution")
        if observation_id in observation_ids:
            raise EvidenceResolutionError(f"Duplicate {side} observation UUID resolution")
        observation_ids.add(observation_id)
        result[key] = _evidence_record(row)
    return result


def build_evidence_index(
    analysis: Mapping[str, Any],
    previous_rows: Sequence[Mapping[str, Any]],
    current_rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    _validate_source_analysis(analysis)
    previous = _index_evidence_rows(previous_rows, "previous")
    current = _index_evidence_rows(current_rows, "current")
    expected_previous: set[tuple[str, str, str]] = set()
    expected_current: set[tuple[str, str, str]] = set()
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for comparison in analysis["comparisons"]:
        key = _slot_key(comparison)
        classification = comparison["slot_classification"]
        needs_previous = classification != "NEW_SLOT"
        needs_current = classification != "RETIRED_SLOT"
        if needs_previous:
            expected_previous.add(key)
        if needs_current:
            expected_current.add(key)
        previous_record = previous.get(key)
        current_record = current.get(key)
        if needs_previous and previous_record is None:
            raise EvidenceResolutionError("Missing previous observation resolution")
        if needs_current and current_record is None:
            raise EvidenceResolutionError("Missing current observation resolution")
        if not needs_previous and previous_record is not None:
            raise EvidenceResolutionError("Unexpected previous observation resolution")
        if not needs_current and current_record is not None:
            raise EvidenceResolutionError("Unexpected current observation resolution")
        listing_ids = {
            record["listing_id"]
            for record in (previous_record, current_record)
            if record is not None
        }
        if len(listing_ids) != 1:
            raise EvidenceResolutionError("Listing identity changed across snapshot observations")
        result[key] = {"previous": previous_record, "current": current_record}
    if set(previous) != expected_previous or set(current) != expected_current:
        raise EvidenceResolutionError("Resolved evidence contains slots outside the source analysis")
    return result


def _snapshot_metadata_matches(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    keys = (
        "source_kind",
        "derived_batch_id",
        "reference_at",
        "captured_through",
        "region_key",
        "search_runs",
        "observations",
    )
    return all(actual.get(key) == expected.get(key) for key in keys)


def resolve_production_evidence(
    analysis: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> dict[tuple[str, str, str], dict[str, Any]]:
    try:
        previous, current = snapshot_analyzer.resolve_snapshot_pair(rows)
    except snapshot_analyzer.AnalyzerError as error:
        raise EvidenceResolutionError("Production snapshot pair resolution failed") from error
    if not _snapshot_metadata_matches(previous.metadata(), analysis["previous_snapshot"]):
        raise EvidenceResolutionError("Previous production snapshot does not match source analysis")
    if not _snapshot_metadata_matches(current.metadata(), analysis["current_snapshot"]):
        raise EvidenceResolutionError("Current production snapshot does not match source analysis")
    return build_evidence_index(analysis, previous.rows, current.rows)


def _query_context(
    comparison: Mapping[str, Any], evidence: Mapping[str, Any]
) -> dict[str, Any]:
    previous = evidence.get("previous")
    current = evidence.get("current")
    return {
        "query_text_exact": comparison["query_text_exact"],
        "previous_status": comparison["previous_status"],
        "current_status": comparison["current_status"],
        "previous_rank": comparison.get("previous_rank"),
        "current_rank": comparison.get("current_rank"),
        "rank_delta": comparison.get("rank_delta"),
        "previous_bank_price": comparison.get("previous_bank_price"),
        "current_bank_price": comparison.get("current_bank_price"),
        "previous_other_payment_price": comparison.get("previous_other_payment_price"),
        "current_other_payment_price": comparison.get("current_other_payment_price"),
        "previous_old_price": comparison.get("previous_old_price"),
        "current_old_price": comparison.get("current_old_price"),
        "previous_reviews_count_observed": comparison.get("previous_reviews_count_observed"),
        "current_reviews_count_observed": comparison.get("current_reviews_count_observed"),
        "reviews_delta": comparison.get("reviews_delta"),
        "reviews_scope": (current or previous or {}).get("reviews_scope"),
        "previous_observation_id": None if previous is None else previous["observation_id"],
        "current_observation_id": None if current is None else current["observation_id"],
        "previous_observation_ref": None if previous is None else previous["observation_ref"],
        "current_observation_ref": None if current is None else current["observation_ref"],
        "visibility_transition": comparison["visibility_transition"],
        "comparison_quality": comparison["comparison_quality"],
    }


def _observation_refs(contexts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "query_text_exact": context["query_text_exact"],
            "previous_observation_id": context["previous_observation_id"],
            "current_observation_id": context["current_observation_id"],
            "previous_observation_ref": context["previous_observation_ref"],
            "current_observation_ref": context["current_observation_ref"],
        }
        for context in contexts
    ]


def _evidence_refs(
    rows: Sequence[Mapping[str, Any]], evidence_index: Mapping[tuple[str, str, str], Mapping[str, Any]]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        resolved = evidence_index[_slot_key(row)]
        item: dict[str, Any] = {"query_text_exact": row["query_text_exact"]}
        for side in ("previous", "current"):
            record = resolved.get(side)
            item[side] = None if record is None else {
                "source_ref": record["source_ref"],
                "raw_ref": record.get("raw_ref"),
                "raw_source_ref": record.get("raw_source_ref"),
            }
        result.append(item)
    return result


def _listing_id(
    rows: Sequence[Mapping[str, Any]], evidence_index: Mapping[tuple[str, str, str], Mapping[str, Any]]
) -> str:
    listing_ids = {
        record["listing_id"]
        for row in rows
        for record in evidence_index[_slot_key(row)].values()
        if record is not None
    }
    if len(listing_ids) != 1:
        raise EvidenceResolutionError("Listing-level group has conflicting listing UUIDs")
    return next(iter(listing_ids))


def _membership_status(rows: Sequence[Mapping[str, Any]]) -> str:
    memberships = {str(row.get("membership_status")) for row in rows}
    if len(memberships) != 1 or next(iter(memberships)) not in MEMBERSHIPS:
        raise FindingContractError("Listing-level group has conflicting membership status")
    return next(iter(memberships))


def _snapshot_ref(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": snapshot["source_kind"],
        "derived_batch_id": snapshot["derived_batch_id"],
        "reference_at": snapshot["reference_at"],
    }


def _base_finding(
    *,
    finding_type: str,
    severity: str,
    confidence: str,
    rows: Sequence[Mapping[str, Any]],
    evidence_index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    analysis: Mapping[str, Any],
    metric: str,
    previous_value: Any,
    current_value: Any,
    delta: Any,
    delta_pct: Any,
    summary: str,
) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: row["query_text_exact"])
    contexts = [_query_context(row, evidence_index[_slot_key(row)]) for row in ordered]
    offer_id, product_id = _listing_key(ordered[0])
    return {
        "finding_type": finding_type,
        "finding_kind": FINDING_KINDS[finding_type],
        "severity": severity,
        "confidence": confidence,
        "status": STATUS,
        "offer_id": offer_id,
        "listing_id": _listing_id(ordered, evidence_index),
        "ozon_product_id": product_id,
        "membership_status": _membership_status(ordered),
        "query_context": contexts,
        "previous_snapshot": _snapshot_ref(analysis["previous_snapshot"]),
        "current_snapshot": _snapshot_ref(analysis["current_snapshot"]),
        "metric": metric,
        "previous_value": previous_value,
        "current_value": current_value,
        "delta": delta,
        "delta_pct": delta_pct,
        "summary": summary,
        "evidence_refs": _evidence_refs(ordered, evidence_index),
        "observation_refs": _observation_refs(contexts),
        "dedup_key": f"{finding_type}|{offer_id}|{product_id}",
        "created_from_analysis_contract": SOURCE_CONTRACT_VERSION,
    }


def _visibility_value(rows: Sequence[Mapping[str, Any]], side: str) -> dict[str, Any]:
    status_field = f"{side}_status"
    found_queries = sorted(
        row["query_text_exact"] for row in rows if row[status_field] == "FOUND"
    )
    return {"any_found": bool(found_queries), "found_queries": found_queries}


def _visibility_findings(
    rows: Sequence[Mapping[str, Any]],
    evidence_index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    membership = _membership_status(rows)
    previous = _visibility_value(rows, "previous")
    current = _visibility_value(rows, "current")
    lost = [row for row in rows if row["visibility_transition"] == "DROPPED_OUT"]
    restored = [row for row in rows if row["visibility_transition"] == "REAPPEARED"]
    non_continuing = [row for row in rows if row["slot_classification"] != "CONTINUING_SLOT"]
    if non_continuing:
        if lost or restored:
            suppressed.append(
                {
                    "offer_id": rows[0]["offer_id"],
                    "ozon_product_id": rows[0]["ozon_product_id"],
                    "membership_status": membership,
                    "reason": "NON_CONTINUING_SLOT",
                    "query_contexts": sorted(row["query_text_exact"] for row in non_continuing),
                }
            )
        return findings, suppressed

    if membership == "CONTROL":
        if previous["any_found"] and not current["any_found"]:
            findings.append(
                _base_finding(
                    finding_type="OWN_SEARCH_VISIBILITY_LOST",
                    severity="IMPORTANT",
                    confidence="HIGH",
                    rows=rows,
                    evidence_index=evidence_index,
                    analysis=analysis,
                    metric="search_visibility",
                    previous_value=previous,
                    current_value=current,
                    delta=None,
                    delta_pct=None,
                    summary=(
                        "Own listing search visibility was not found within the monitored OEM "
                        "queries and scan limit in the current snapshot."
                    ),
                )
            )
        elif lost and current["any_found"]:
            findings.append(
                _base_finding(
                    finding_type="OWN_SEARCH_VISIBILITY_LOST",
                    severity="WATCH",
                    confidence="MEDIUM",
                    rows=rows,
                    evidence_index=evidence_index,
                    analysis=analysis,
                    metric="search_visibility",
                    previous_value=previous,
                    current_value=current,
                    delta=None,
                    delta_pct=None,
                    summary=(
                        "Own listing lost search visibility in some monitored OEM query contexts "
                        "within the scan limit and remains visible in other monitored queries."
                    ),
                )
            )
        if restored:
            full_restore = not previous["any_found"] and current["any_found"]
            findings.append(
                _base_finding(
                    finding_type="OWN_SEARCH_VISIBILITY_RESTORED",
                    severity="INFO",
                    confidence="HIGH" if full_restore else "MEDIUM",
                    rows=rows,
                    evidence_index=evidence_index,
                    analysis=analysis,
                    metric="search_visibility",
                    previous_value=previous,
                    current_value=current,
                    delta=None,
                    delta_pct=None,
                    summary=(
                        "Own listing search visibility was observed again in monitored OEM query "
                        "contexts in the current snapshot."
                    ),
                )
            )
        return findings, suppressed

    if previous["any_found"] and not current["any_found"]:
        findings.append(
            _base_finding(
                finding_type="COMPETITOR_VISIBILITY_LOST",
                severity="INFO",
                confidence="MEDIUM",
                rows=rows,
                evidence_index=evidence_index,
                analysis=analysis,
                metric="search_visibility",
                previous_value=previous,
                current_value=current,
                delta=None,
                delta_pct=None,
                summary=(
                    "Competitor listing was not found within any monitored OEM query context and "
                    "scan limit in the current snapshot."
                ),
            )
        )
    elif not previous["any_found"] and current["any_found"]:
        findings.append(
            _base_finding(
                finding_type="COMPETITOR_VISIBILITY_RESTORED",
                severity="INFO",
                confidence="MEDIUM",
                rows=rows,
                evidence_index=evidence_index,
                analysis=analysis,
                metric="search_visibility",
                previous_value=previous,
                current_value=current,
                delta=None,
                delta_pct=None,
                summary=(
                    "Competitor listing search visibility was observed again within monitored OEM "
                    "query contexts in the current snapshot."
                ),
            )
        )
    elif lost or restored:
        reason = "COMPETITOR_QUERY_SWAP_WITHOUT_LISTING_TRANSITION"
        if lost and not restored:
            reason = "COMPETITOR_LISTING_STILL_VISIBLE_IN_OTHER_QUERY"
        elif restored and not lost:
            reason = "COMPETITOR_ALREADY_VISIBLE_IN_PREVIOUS_QUERY"
        suppressed.append(
            {
                "offer_id": rows[0]["offer_id"],
                "ozon_product_id": rows[0]["ozon_product_id"],
                "membership_status": membership,
                "reason": reason,
                "query_contexts": sorted(
                    row["query_text_exact"] for row in rows if row in lost or row in restored
                ),
            }
        )
    return findings, suppressed


def _price_finding(
    rows: Sequence[Mapping[str, Any]],
    evidence_index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    membership = _membership_status(rows)
    comparable = [
        row
        for row in rows
        if row["comparison_quality"] == "VALID"
        and row.get("previous_bank_price") is not None
        and row.get("current_bank_price") is not None
    ]
    changed = [
        row
        for row in comparable
        if row.get("bank_price_direction") in {"INCREASED", "DECREASED"}
    ]
    if not changed:
        return None, None
    if membership == "CONTROL":
        return None, {
            "offer_id": rows[0]["offer_id"],
            "ozon_product_id": rows[0]["ozon_product_id"],
            "membership_status": membership,
            "reason": "CONTROL_PRICE_CHANGE_OUT_OF_SCOPE",
            "query_contexts": sorted(row["query_text_exact"] for row in changed),
        }
    if any(row.get("previous_bank_price") is None or row.get("current_bank_price") is None for row in comparable):
        raise FindingContractError("Comparable price context unexpectedly lacks bank price")
    bank_pairs = {
        (str(row["previous_bank_price"]), str(row["current_bank_price"])) for row in comparable
    }
    if len(bank_pairs) != 1:
        return None, {
            "offer_id": rows[0]["offer_id"],
            "ozon_product_id": rows[0]["ozon_product_id"],
            "membership_status": membership,
            "reason": "CONFLICTING_QUERY_BANK_PRICE_MOVEMENT",
            "query_contexts": sorted(row["query_text_exact"] for row in comparable),
        }
    previous_text, current_text = next(iter(bank_pairs))
    previous = Decimal(previous_text)
    current = Decimal(current_text)
    if previous <= 0 or previous == current:
        return None, None
    other_pairs = {
        (str(row["previous_other_payment_price"]), str(row["current_other_payment_price"]))
        for row in comparable
        if row.get("previous_other_payment_price") is not None
        and row.get("current_other_payment_price") is not None
    }
    if len(other_pairs) > 1:
        return None, {
            "offer_id": rows[0]["offer_id"],
            "ozon_product_id": rows[0]["ozon_product_id"],
            "membership_status": membership,
            "reason": "CONFLICTING_QUERY_OTHER_PAYMENT_MOVEMENT",
            "query_contexts": sorted(row["query_text_exact"] for row in comparable),
        }
    currencies = {
        record.get("currency")
        for row in comparable
        for record in evidence_index[_slot_key(row)].values()
        if record is not None and record.get("currency") is not None
    }
    if len(currencies) != 1:
        return None, {
            "offer_id": rows[0]["offer_id"],
            "ozon_product_id": rows[0]["ozon_product_id"],
            "membership_status": membership,
            "reason": "CONFLICTING_OR_MISSING_PRICE_CURRENCY",
            "query_contexts": sorted(row["query_text_exact"] for row in comparable),
        }
    finding_type = (
        "COMPETITOR_PRICE_INCREASED" if current > previous else "COMPETITOR_PRICE_DECREASED"
    )
    delta = current - previous
    delta_pct = delta / previous * Decimal("100")
    currency = next(iter(currencies))
    finding = _base_finding(
        finding_type=finding_type,
        severity="INFO",
        confidence="HIGH",
        rows=rows,
        evidence_index=evidence_index,
        analysis=analysis,
        metric="bank_price",
        previous_value={"amount": _number(previous), "currency": currency},
        current_value={"amount": _number(current), "currency": currency},
        delta=_number(delta),
        delta_pct=_number(delta_pct),
        summary=(
            f"Observed competitor bank price {'increased' if delta > 0 else 'decreased'} "
            f"from {_number(previous)} to {_number(current)} {currency} across consistent "
            "comparable query evidence."
        ),
    )
    return finding, None


def _summary(findings: Sequence[Mapping[str, Any]], suppressed: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_type = Counter(finding["finding_type"] for finding in findings)
    by_severity = Counter(finding["severity"] for finding in findings)
    by_membership = Counter(finding["membership_status"] for finding in findings)
    reasons = Counter(item["reason"] for item in suppressed)
    return {
        "findings_total": len(findings),
        "by_type": {name: by_type[name] for name in FINDING_TYPES},
        "by_severity": {name: by_severity[name] for name in SEVERITIES},
        "by_membership": {name: by_membership[name] for name in MEMBERSHIPS},
        "suppressed": {
            "count": len(suppressed),
            "reasons": dict(sorted(reasons.items())),
        },
    }


def generate_finding_set(
    analysis: Mapping[str, Any],
    source_sha256: str,
    evidence_index: Mapping[tuple[str, str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    _validate_source_analysis(analysis)
    original_digest = hashlib.sha256(_json_bytes(analysis)).hexdigest()
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for comparison in analysis["comparisons"]:
        key = _slot_key(comparison)
        if key not in evidence_index:
            raise EvidenceResolutionError("Evidence index does not cover source analysis")
        groups[_listing_key(comparison)].append(comparison)

    findings: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda row: row["query_text_exact"])
        visibility, visibility_suppressed = _visibility_findings(rows, evidence_index, analysis)
        findings.extend(visibility)
        suppressed.extend(visibility_suppressed)
        price, price_suppressed = _price_finding(rows, evidence_index, analysis)
        if price is not None:
            findings.append(price)
        if price_suppressed is not None:
            suppressed.append(price_suppressed)

    findings.sort(key=lambda item: (item["finding_type"], item["offer_id"], item["ozon_product_id"]))
    suppressed.sort(key=lambda item: (item["reason"], item["offer_id"], item["ozon_product_id"]))
    report = {
        "contract_version": CONTRACT_VERSION,
        "source_analysis_contract": SOURCE_CONTRACT_VERSION,
        "source_analysis_sha256": source_sha256,
        "previous_snapshot": dict(analysis["previous_snapshot"]),
        "current_snapshot": dict(analysis["current_snapshot"]),
        "summary": _summary(findings, suppressed),
        "findings": findings,
        "suppressed_events": suppressed,
    }
    validate_finding_set(report)
    if hashlib.sha256(_json_bytes(analysis)).hexdigest() != original_digest:
        raise FindingContractError("Source analysis changed during finding generation")
    return report


def validate_finding_set(report: Mapping[str, Any]) -> None:
    if report.get("contract_version") != CONTRACT_VERSION:
        raise FindingContractError("Finding set contract mismatch")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise FindingContractError("Findings must be an array")
    dedup_keys = [finding["dedup_key"] for finding in findings]
    if len(dedup_keys) != len(set(dedup_keys)):
        raise FindingContractError("Finding dedup keys are not unique")
    unsafe_language = ("listing removed", "product delisted", "product unavailable", "seller stopped selling")
    for finding in findings:
        finding_type = finding["finding_type"]
        expected_key = f"{finding_type}|{finding['offer_id']}|{finding['ozon_product_id']}"
        if finding_type not in FINDING_TYPES or finding["finding_kind"] != FINDING_KINDS[finding_type]:
            raise FindingContractError("Finding taxonomy mapping mismatch")
        if finding["dedup_key"] != expected_key:
            raise FindingContractError("Finding dedup key includes unsupported identity")
        if finding["severity"] not in SEVERITIES or finding["confidence"] not in CONFIDENCES:
            raise FindingContractError("Finding severity or confidence is invalid")
        if finding["status"] != STATUS:
            raise FindingContractError("Finding status is not PROPOSED")
        contexts = finding["query_context"]
        if not contexts or len(contexts) != len(finding["observation_refs"]):
            raise FindingContractError("Finding query evidence is incomplete")
        for context in contexts:
            if not context.get("previous_observation_id") or not context.get("current_observation_id"):
                raise FindingContractError("Finding lacks traceable observation UUIDs")
        if any(phrase in finding["summary"].lower() for phrase in unsafe_language):
            raise FindingContractError("Visibility finding uses unsafe language")
        if finding["metric"] in {"rank", "reviews", "product_fact"}:
            raise FindingContractError("Deferred metric emitted a v1 finding")
    summary = report["summary"]
    if summary["findings_total"] != len(findings):
        raise FindingContractError("Finding summary total mismatch")
    if sum(summary["by_type"].values()) != len(findings):
        raise FindingContractError("Finding type summary mismatch")
    if sum(summary["by_severity"].values()) != len(findings):
        raise FindingContractError("Finding severity summary mismatch")
    if sum(summary["by_membership"].values()) != len(findings):
        raise FindingContractError("Finding membership summary mismatch")
    if summary["suppressed"]["count"] != len(report.get("suppressed_events", ())):
        raise FindingContractError("Suppressed event summary mismatch")


def _fetch_dicts(cursor: Any, query: str) -> list[dict[str, Any]]:
    cursor.execute(query)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def read_counts(connection: Any) -> dict[str, int]:
    try:
        with connection.cursor() as cursor:
            row = _fetch_dicts(cursor, COUNTS_QUERY)[0]
    except Exception as error:
        raise EvidenceResolutionError(
            "Approved mcp_read operational counts query failed"
        ) from error
    return {name: int(value) for name, value in row.items()}


def read_resolution_rows(connection: Any) -> list[dict[str, Any]]:
    try:
        with connection.cursor() as cursor:
            return _fetch_dicts(cursor, RESOLUTION_QUERY)
    except Exception as error:
        raise EvidenceResolutionError(
            "Approved mcp_read evidence resolution query failed"
        ) from error


def run_engine(
    connection: Any, analysis: Mapping[str, Any], source_sha256: str
) -> dict[str, Any]:
    before = read_counts(connection)
    rows = read_resolution_rows(connection)
    evidence_index = resolve_production_evidence(analysis, rows)
    report = generate_finding_set(analysis, source_sha256, evidence_index)
    after = read_counts(connection)
    if before != after:
        raise FindingContractError("Source table counts changed during read-only finding generation")
    connection.rollback()
    report["production_read_only_check"] = {"before": before, "after": after}
    return report


def write_report(report: Mapping[str, Any], output: Path | None) -> None:
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        output.write_text(rendered, encoding="utf-8", newline="\n")


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Competitor Monitor Finding Engine v1")
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--require-analysis-sha256")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    analysis, source_sha256 = load_source_analysis(args.analysis, args.require_analysis_sha256)
    config = snapshot_analyzer.load_database_config(os.environ)
    connection = snapshot_analyzer.connect_database(config)
    try:
        report = run_engine(connection, analysis, source_sha256)
        write_report(report, args.output)
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FindingEngineError, snapshot_analyzer.AnalyzerError) as error:
        print(f"ERROR={error}")
        raise SystemExit(1)
