"""Read-only factual comparison of two consecutive Competitor Monitor snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


CONTRACT_VERSION = "competitor_snapshot_analysis.v1"
DERIVED_BATCH_CONTRACT = "competitor_snapshot_derived_batch.v1"
EXPECTED_RUNS_PER_BATCH = 9
BATCH_GAP = timedelta(minutes=5)
ACTIVE_OFFERS = ("УФ 001Б", "УФ 002Б", "УФ 004Б", "УФ 005Б")
ALL_OFFERS = ("УФ 001Б", "УФ 002Б", "УФ 003Б", "УФ 004Б", "УФ 005Б")

HISTORY_QUERY = """
SELECT
    r.search_run_id::text,
    r.offer_id,
    r.query_text_exact,
    r.region_key,
    r.location_label,
    r.captured_at AS run_captured_at,
    r.status AS run_status,
    r.collection_ref,
    o.observation_id::text,
    l.ozon_product_id::text,
    m.membership_status,
    o.captured_at,
    o.enrichment_captured_at,
    o.page_number,
    o.position_on_page,
    o.rank,
    o.ad_flag,
    o.bank_price,
    o.other_payment_price,
    o.old_price,
    o.currency,
    o.rating,
    o.reviews_count_observed,
    o.reviews_scope,
    o.purchase_count_observed,
    o.purchase_indicator_raw,
    o.availability_status,
    o.availability_raw,
    o.observed_oem_raw,
    o.observed_dimensions_raw,
    o.observed_length_mm,
    o.observed_width_mm,
    o.observed_height_mm,
    o.carbon_claim_raw,
    o.origin_raw,
    o.quality_status,
    o.quality_flags
FROM public.competitor_search_runs AS r
JOIN public.competitor_observations AS o
  ON o.search_run_id = r.search_run_id
JOIN public.competitor_listings AS l
  ON l.listing_id = o.listing_id
LEFT JOIN public.competitor_watchlist_memberships AS m
  ON m.membership_id = o.membership_id
WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%'
   OR r.collection_ref LIKE 'cm-snapshot-v1:run:%'
ORDER BY r.captured_at, r.collection_ref, r.offer_id,
         r.query_text_exact, l.ozon_product_id
"""

COUNTS_QUERY = """
SELECT
  (SELECT count(*) FROM public.competitor_search_runs) AS search_runs,
  (SELECT count(*) FROM public.competitor_observations) AS observations,
  (SELECT count(*) FROM public.competitor_reviews) AS reviews,
  (SELECT count(*) FROM public.competitor_findings) AS findings
"""


class AnalyzerError(RuntimeError):
    pass


class ConfigurationError(AnalyzerError):
    pass


class BatchResolutionError(AnalyzerError):
    pass


class DataContractError(AnalyzerError):
    pass


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class SnapshotBatch:
    source_kind: str
    derived_batch_id: str
    reference_at: datetime
    captured_through: datetime
    region_key: str
    run_ids: tuple[str, ...]
    collection_refs: tuple[str, ...]
    rows: tuple[Mapping[str, Any], ...]

    def metadata(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "derived_batch_id": self.derived_batch_id,
            "reference_at": _timestamp_text(self.reference_at),
            "captured_through": _timestamp_text(self.captured_through),
            "region_key": self.region_key,
            "search_runs": len(self.run_ids),
            "observations": len(self.rows),
            "selection_contract": "captured_at_gap_and_exact_run_structure",
        }


def _timestamp_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise DataContractError("Snapshot timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _number(value: object) -> int | float | None:
    if value is None:
        return None
    decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    if decimal == decimal.to_integral_value():
        return int(decimal)
    return float(decimal)


def _decimal(value: object) -> Decimal | None:
    return None if value is None else (value if isinstance(value, Decimal) else Decimal(str(value)))


def _collection_kind(collection_ref: str) -> str:
    if collection_ref.startswith("cm-baseline-v1:run:"):
        return "BASELINE_V1"
    if collection_ref.startswith("cm-snapshot-v1:run:"):
        return "SNAPSHOT_V1"
    raise BatchResolutionError("Unsupported collection_ref family")


def _derived_batch_id(collection_refs: Sequence[str]) -> str:
    identity = {
        "contract": DERIVED_BATCH_CONTRACT,
        "collection_refs": sorted(collection_refs),
    }
    return "cm-analysis-derived-batch:v1:" + hashlib.sha256(_json_bytes(identity)).hexdigest()


def _run_identity(row: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        row["search_run_id"],
        row["offer_id"],
        row["query_text_exact"],
        row["region_key"],
        row.get("location_label"),
        row["run_captured_at"],
        row["run_status"],
        row["collection_ref"],
    )


def _unique_runs(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    observation_ids: set[str] = set()
    for row in rows:
        observation_id = str(row["observation_id"])
        if observation_id in observation_ids:
            raise DataContractError("Duplicate source observation row")
        observation_ids.add(observation_id)
        search_run_id = str(row["search_run_id"])
        candidate = {
            "search_run_id": search_run_id,
            "offer_id": row["offer_id"],
            "query_text_exact": row["query_text_exact"],
            "region_key": row["region_key"],
            "location_label": row.get("location_label"),
            "run_captured_at": row["run_captured_at"],
            "run_status": row["run_status"],
            "collection_ref": row["collection_ref"],
        }
        existing = runs.get(search_run_id)
        if existing is not None and _run_identity(existing) != _run_identity(candidate):
            raise DataContractError("Search run facts differ across joined rows")
        runs[search_run_id] = candidate
    return sorted(runs.values(), key=lambda row: (row["run_captured_at"], row["collection_ref"]))


def resolve_snapshot_batches(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_runs: int = EXPECTED_RUNS_PER_BATCH,
    batch_gap: timedelta = BATCH_GAP,
) -> tuple[SnapshotBatch, ...]:
    if not rows:
        raise BatchResolutionError("No snapshot history is available")
    runs = _unique_runs(rows)
    clusters: list[list[dict[str, Any]]] = []
    for run in runs:
        captured_at = run["run_captured_at"]
        if not isinstance(captured_at, datetime) or captured_at.tzinfo is None:
            raise DataContractError("Run captured_at must be timezone-aware")
        if not clusters or captured_at - clusters[-1][-1]["run_captured_at"] > batch_gap:
            clusters.append([run])
        else:
            clusters[-1].append(run)

    batches: list[SnapshotBatch] = []
    for cluster in clusters:
        if len(cluster) != expected_runs:
            raise BatchResolutionError(
                f"Incomplete batch structure: expected={expected_runs} actual={len(cluster)}"
            )
        query_keys = {(row["offer_id"], row["query_text_exact"]) for row in cluster}
        if len(query_keys) != expected_runs:
            raise BatchResolutionError("Batch query identities are not unique")
        regions = {row["region_key"] for row in cluster}
        if len(regions) != 1:
            raise BatchResolutionError("Batch contains multiple regions")
        kinds = {_collection_kind(str(row["collection_ref"])) for row in cluster}
        if len(kinds) != 1:
            raise BatchResolutionError("Batch mixes collection_ref families")
        if any(row["run_status"] != "SUCCESS" for row in cluster):
            raise BatchResolutionError("Batch contains a non-success search run")
        run_ids = tuple(str(row["search_run_id"]) for row in cluster)
        cluster_rows = tuple(row for row in rows if str(row["search_run_id"]) in run_ids)
        refs = tuple(str(row["collection_ref"]) for row in cluster)
        batches.append(
            SnapshotBatch(
                source_kind=next(iter(kinds)),
                derived_batch_id=_derived_batch_id(refs),
                reference_at=min(row["run_captured_at"] for row in cluster),
                captured_through=max(row["run_captured_at"] for row in cluster),
                region_key=next(iter(regions)),
                run_ids=run_ids,
                collection_refs=refs,
                rows=cluster_rows,
            )
        )
    return tuple(batches)


def resolve_snapshot_pair(rows: Sequence[Mapping[str, Any]]) -> tuple[SnapshotBatch, SnapshotBatch]:
    batches = resolve_snapshot_batches(rows)
    if len(batches) < 2:
        raise BatchResolutionError("At least two complete batches are required")
    previous, current = batches[-2], batches[-1]
    if current.reference_at <= previous.reference_at:
        raise BatchResolutionError("Current snapshot is not newer than previous")
    return previous, current


def _slot_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    product_id = str(row["ozon_product_id"])
    if not product_id.isdecimal():
        raise DataContractError("ozon_product_id must be a decimal string")
    return str(row["offer_id"]), str(row["query_text_exact"]), product_id


def _slot_index(batch: SnapshotBatch) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in batch.rows:
        key = _slot_key(row)
        if key in result:
            raise DataContractError("Duplicate logical observation slot")
        if row["captured_at"] != row["run_captured_at"]:
            raise DataContractError("Observation timestamp differs from its search run")
        result[key] = row
    return result


def _observation_status(row: Mapping[str, Any] | None) -> str:
    if row is None:
        return "MISSING"
    if row.get("quality_status") == "VALID":
        return "FOUND"
    flags = tuple(row.get("quality_flags") or ())
    if row.get("quality_status") == "NOT_FOUND" and "NOT_FOUND_WITHIN_SCAN_LIMIT" in flags:
        return "NOT_FOUND_WITHIN_SCAN_LIMIT"
    return "NOT_COMPARABLE"


def _visibility_transition(previous: str, current: str, slot_classification: str) -> str:
    if slot_classification != "CONTINUING_SLOT":
        return slot_classification
    pair = (previous, current)
    return {
        ("FOUND", "FOUND"): "STILL_VISIBLE",
        ("FOUND", "NOT_FOUND_WITHIN_SCAN_LIMIT"): "DROPPED_OUT",
        ("NOT_FOUND_WITHIN_SCAN_LIMIT", "FOUND"): "REAPPEARED",
        ("NOT_FOUND_WITHIN_SCAN_LIMIT", "NOT_FOUND_WITHIN_SCAN_LIMIT"): "STILL_NOT_FOUND",
    }.get(pair, "NOT_COMPARABLE")


def _direction(delta: Decimal | None, comparable: bool) -> str:
    if not comparable or delta is None:
        return "NOT_COMPARABLE"
    if delta < 0:
        return "DECREASED"
    if delta > 0:
        return "INCREASED"
    return "UNCHANGED"


def _numeric_change(previous: object, current: object, comparable: bool) -> dict[str, Any]:
    previous_decimal = _decimal(previous)
    current_decimal = _decimal(current)
    valid = comparable and previous_decimal is not None and current_decimal is not None
    delta = current_decimal - previous_decimal if valid else None
    percent = None
    if valid and previous_decimal is not None and previous_decimal > 0:
        percent = (delta / previous_decimal * Decimal("100")).quantize(Decimal("0.000001"))
    return {
        "previous": _number(previous_decimal),
        "current": _number(current_decimal),
        "delta": _number(delta),
        "delta_pct": _number(percent),
        "direction": _direction(delta, valid),
    }


def _rank_change(previous: object, current: object, comparable: bool) -> dict[str, Any]:
    valid = comparable and isinstance(previous, int) and isinstance(current, int)
    delta = current - previous if valid else None
    if delta is None:
        direction = "NOT_COMPARABLE"
    elif delta < 0:
        direction = "IMPROVED"
    elif delta > 0:
        direction = "WORSENED"
    else:
        direction = "UNCHANGED"
    return {"previous": previous, "current": current, "delta": delta, "direction": direction}


def _simple_change(previous: object, current: object, comparable: bool) -> dict[str, Any]:
    previous_decimal = _decimal(previous)
    current_decimal = _decimal(current)
    valid = comparable and previous_decimal is not None and current_decimal is not None
    delta = current_decimal - previous_decimal if valid else None
    return {
        "previous": _number(previous_decimal),
        "current": _number(current_decimal),
        "delta": _number(delta),
        "direction": _direction(delta, valid),
    }


def _purchase_change(previous: Mapping[str, Any] | None, current: Mapping[str, Any] | None, comparable: bool) -> dict[str, Any]:
    previous_count = None if previous is None else previous.get("purchase_count_observed")
    current_count = None if current is None else current.get("purchase_count_observed")
    numeric = _simple_change(previous_count, current_count, comparable)
    previous_raw = None if previous is None else previous.get("purchase_indicator_raw")
    current_raw = None if current is None else current.get("purchase_indicator_raw")
    if numeric["direction"] != "NOT_COMPARABLE":
        classification = numeric["direction"]
    elif comparable and previous_raw != current_raw:
        classification = "RAW_CHANGED"
    else:
        classification = "NOT_COMPARABLE"
    return {
        "previous_count": numeric["previous"],
        "current_count": numeric["current"],
        "delta": numeric["delta"],
        "previous_raw": previous_raw,
        "current_raw": current_raw,
        "classification": classification,
    }


def _availability_transition(previous: object, current: object, comparable: bool) -> str:
    if not comparable or not previous or not current or "UNKNOWN" in {previous, current}:
        return "UNKNOWN"
    if previous == current:
        return "UNCHANGED"
    available = {"AVAILABLE", "IN_STOCK"}
    unavailable = {"UNAVAILABLE", "OUT_OF_STOCK"}
    if previous in unavailable and current in available:
        return "BECAME_AVAILABLE"
    if previous in available and current in unavailable:
        return "BECAME_UNAVAILABLE"
    return "CHANGED"


PRODUCT_FACT_FIELDS = (
    "observed_oem_raw",
    "observed_dimensions_raw",
    "observed_length_mm",
    "observed_width_mm",
    "observed_height_mm",
    "carbon_claim_raw",
    "origin_raw",
)


def _product_fact_changes(previous: Mapping[str, Any] | None, current: Mapping[str, Any] | None, comparable: bool) -> list[dict[str, Any]]:
    if not comparable or previous is None or current is None:
        return []
    changes = []
    for field in PRODUCT_FACT_FIELDS:
        before = previous.get(field)
        after = current.get(field)
        if before != after:
            changes.append({"field": field, "previous": _number(before) if isinstance(before, Decimal) else before, "current": _number(after) if isinstance(after, Decimal) else after})
    return changes


def compare_slot(
    key: tuple[str, str, str],
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if previous is not None and current is not None:
        slot_classification = "CONTINUING_SLOT"
    elif current is not None:
        slot_classification = "NEW_SLOT"
    else:
        slot_classification = "RETIRED_SLOT"
    previous_status = _observation_status(previous)
    current_status = _observation_status(current)
    visibility = _visibility_transition(previous_status, current_status, slot_classification)
    factual_comparable = visibility == "STILL_VISIBLE"
    if factual_comparable:
        comparison_quality = "VALID"
    elif slot_classification == "CONTINUING_SLOT" and visibility in {"DROPPED_OUT", "REAPPEARED", "STILL_NOT_FOUND"}:
        comparison_quality = "VISIBILITY_ONLY"
    else:
        comparison_quality = "NOT_COMPARABLE"

    rank = _rank_change(
        None if previous is None else previous.get("rank"),
        None if current is None else current.get("rank"),
        factual_comparable,
    )
    bank = _numeric_change(
        None if previous is None else previous.get("bank_price"),
        None if current is None else current.get("bank_price"),
        factual_comparable,
    )
    other = _numeric_change(
        None if previous is None else previous.get("other_payment_price"),
        None if current is None else current.get("other_payment_price"),
        factual_comparable,
    )
    old = _numeric_change(
        None if previous is None else previous.get("old_price"),
        None if current is None else current.get("old_price"),
        factual_comparable,
    )
    rating = _simple_change(
        None if previous is None else previous.get("rating"),
        None if current is None else current.get("rating"),
        factual_comparable,
    )
    reviews = _simple_change(
        None if previous is None else previous.get("reviews_count_observed"),
        None if current is None else current.get("reviews_count_observed"),
        factual_comparable,
    )
    fact_changes = _product_fact_changes(previous, current, factual_comparable)
    membership_status = (current or previous or {}).get("membership_status")
    return {
        "offer_id": key[0],
        "query_text_exact": key[1],
        "ozon_product_id": key[2],
        "slot_classification": slot_classification,
        "membership_status": membership_status,
        "previous_membership_status": None if previous is None else previous.get("membership_status"),
        "current_membership_status": None if current is None else current.get("membership_status"),
        "previous_status": previous_status,
        "current_status": current_status,
        "visibility_transition": visibility,
        "previous_rank": rank["previous"],
        "current_rank": rank["current"],
        "rank_delta": rank["delta"],
        "rank_direction": rank["direction"],
        "previous_bank_price": bank["previous"],
        "current_bank_price": bank["current"],
        "bank_price_delta": bank["delta"],
        "bank_price_delta_pct": bank["delta_pct"],
        "bank_price_direction": bank["direction"],
        "previous_other_payment_price": other["previous"],
        "current_other_payment_price": other["current"],
        "other_payment_price_delta": other["delta"],
        "other_payment_price_delta_pct": other["delta_pct"],
        "other_payment_price_direction": other["direction"],
        "previous_old_price": old["previous"],
        "current_old_price": old["current"],
        "old_price_delta": old["delta"],
        "old_price_delta_pct": old["delta_pct"],
        "old_price_direction": old["direction"],
        "previous_rating": rating["previous"],
        "current_rating": rating["current"],
        "rating_delta": rating["delta"],
        "rating_direction": rating["direction"],
        "previous_reviews_count_observed": reviews["previous"],
        "current_reviews_count_observed": reviews["current"],
        "reviews_delta": reviews["delta"],
        "reviews_direction": reviews["direction"],
        "reviews_change_semantics": "OBSERVED_REVIEW_COUNT_CHANGE",
        "purchase_indicator": _purchase_change(previous, current, factual_comparable),
        "previous_availability_status": None if previous is None else previous.get("availability_status"),
        "current_availability_status": None if current is None else current.get("availability_status"),
        "availability_transition": _availability_transition(
            None if previous is None else previous.get("availability_status"),
            None if current is None else current.get("availability_status"),
            factual_comparable,
        ),
        "product_fact_drift": bool(fact_changes),
        "product_fact_changes": fact_changes,
        "previous_quality_status": None if previous is None else previous.get("quality_status"),
        "current_quality_status": None if current is None else current.get("quality_status"),
        "previous_quality_flags": [] if previous is None else list(previous.get("quality_flags") or ()),
        "current_quality_flags": [] if current is None else list(current.get("quality_flags") or ()),
        "comparison_quality": comparison_quality,
    }


def _counter(comparisons: Sequence[Mapping[str, Any]], field: str, values: Sequence[str]) -> dict[str, int]:
    return {value.lower(): sum(row[field] == value for row in comparisons) for value in values}


def _per_sku_summary(comparisons: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for offer_id in ALL_OFFERS:
        rows = [row for row in comparisons if row["offer_id"] == offer_id]
        if not rows:
            result[offer_id] = {"status": "NO_ACTIVE_MONITORING", "slots": 0}
            continue
        result[offer_id] = {
            "status": "ACTIVE",
            "slots": len(rows),
            "visible_previous": sum(row["previous_status"] == "FOUND" for row in rows),
            "visible_current": sum(row["current_status"] == "FOUND" for row in rows),
            "dropped_out": sum(row["visibility_transition"] == "DROPPED_OUT" for row in rows),
            "reappeared": sum(row["visibility_transition"] == "REAPPEARED" for row in rows),
            "rank_improved": sum(row["rank_direction"] == "IMPROVED" for row in rows),
            "rank_worsened": sum(row["rank_direction"] == "WORSENED" for row in rows),
            "bank_price_increased": sum(row["bank_price_direction"] == "INCREASED" for row in rows),
            "bank_price_decreased": sum(row["bank_price_direction"] == "DECREASED" for row in rows),
        }
    return result


def _control_summary(comparisons: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [row for row in comparisons if row["membership_status"] == "CONTROL"]
    return {
        "slots": len(rows),
        "still_visible": sum(row["visibility_transition"] == "STILL_VISIBLE" for row in rows),
        "dropped_out": sum(row["visibility_transition"] == "DROPPED_OUT" for row in rows),
        "reappeared": sum(row["visibility_transition"] == "REAPPEARED" for row in rows),
        "still_not_found": sum(row["visibility_transition"] == "STILL_NOT_FOUND" for row in rows),
        "rank_improved": sum(row["rank_direction"] == "IMPROVED" for row in rows),
        "rank_worsened": sum(row["rank_direction"] == "WORSENED" for row in rows),
        "bank_price_increased": sum(row["bank_price_direction"] == "INCREASED" for row in rows),
        "bank_price_decreased": sum(row["bank_price_direction"] == "DECREASED" for row in rows),
    }


def build_analysis(previous: SnapshotBatch, current: SnapshotBatch, source_counts: Mapping[str, int]) -> dict[str, Any]:
    previous_slots = _slot_index(previous)
    current_slots = _slot_index(current)
    keys = sorted(set(previous_slots) | set(current_slots))
    comparisons = [compare_slot(key, previous_slots.get(key), current_slots.get(key)) for key in keys]
    summary = {
        "slots_total": len(comparisons),
        "continuing_slots": sum(row["slot_classification"] == "CONTINUING_SLOT" for row in comparisons),
        "new_slots": sum(row["slot_classification"] == "NEW_SLOT" for row in comparisons),
        "retired_slots": sum(row["slot_classification"] == "RETIRED_SLOT" for row in comparisons),
        "visibility": _counter(comparisons, "visibility_transition", ("STILL_VISIBLE", "DROPPED_OUT", "REAPPEARED", "STILL_NOT_FOUND", "NOT_COMPARABLE", "NEW_SLOT", "RETIRED_SLOT")),
        "rank": _counter(comparisons, "rank_direction", ("IMPROVED", "WORSENED", "UNCHANGED", "NOT_COMPARABLE")),
        "bank_price": _counter(comparisons, "bank_price_direction", ("INCREASED", "DECREASED", "UNCHANGED", "NOT_COMPARABLE")),
        "other_payment_price": _counter(comparisons, "other_payment_price_direction", ("INCREASED", "DECREASED", "UNCHANGED", "NOT_COMPARABLE")),
        "old_price": _counter(comparisons, "old_price_direction", ("INCREASED", "DECREASED", "UNCHANGED", "NOT_COMPARABLE")),
        "rating": _counter(comparisons, "rating_direction", ("INCREASED", "DECREASED", "UNCHANGED", "NOT_COMPARABLE")),
        "reviews": _counter(comparisons, "reviews_direction", ("INCREASED", "DECREASED", "UNCHANGED", "NOT_COMPARABLE")),
        "availability": _counter(comparisons, "availability_transition", ("UNCHANGED", "BECAME_AVAILABLE", "BECAME_UNAVAILABLE", "CHANGED", "UNKNOWN")),
        "product_fact_drift": sum(row["product_fact_drift"] for row in comparisons),
    }
    report = {
        "contract_version": CONTRACT_VERSION,
        "current_snapshot": current.metadata(),
        "previous_snapshot": previous.metadata(),
        "source_table_counts": dict(source_counts),
        "summary": summary,
        "per_sku_summary": _per_sku_summary(comparisons),
        "control_listings_summary": _control_summary(comparisons),
        "comparisons": comparisons,
    }
    validate_analysis(report)
    return report


def validate_analysis(report: Mapping[str, Any]) -> None:
    comparisons = report["comparisons"]
    keys = [(row["offer_id"], row["query_text_exact"], row["ozon_product_id"]) for row in comparisons]
    if len(keys) != len(set(keys)):
        raise DataContractError("Analysis contains duplicate logical slots")
    summary = report["summary"]
    total = len(comparisons)
    if summary["slots_total"] != total:
        raise DataContractError("slots_total mismatch")
    if summary["continuing_slots"] + summary["new_slots"] + summary["retired_slots"] != total:
        raise DataContractError("Slot reconciliation totals mismatch")
    for name in ("visibility", "rank", "bank_price", "other_payment_price", "old_price", "rating", "reviews", "availability"):
        if sum(summary[name].values()) != total:
            raise DataContractError(f"{name} summary total mismatch")
    if sum(row["slots"] for row in report["per_sku_summary"].values()) != total:
        raise DataContractError("Per-SKU totals mismatch")
    if any("comparison_price" in row for row in comparisons):
        raise DataContractError("comparison_price is forbidden")


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
    return DatabaseConfig(environment["EFA_DB_HOST"].strip(), port, environment["EFA_DB_NAME"].strip(), environment["EFA_DB_USER"].strip(), environment["EFA_DB_PASSWORD"])


def connect_database(config: DatabaseConfig) -> Any:
    try:
        import psycopg2
        return psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.name,
            user=config.user,
            password=config.password,
            connect_timeout=10,
            options="-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=3000",
        )
    except Exception as error:
        raise AnalyzerError("Read-only PostgreSQL connection failed") from error


def _fetch_dicts(cursor: Any, query: str) -> list[dict[str, Any]]:
    cursor.execute(query)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def read_counts(connection: Any) -> dict[str, int]:
    with connection.cursor() as cursor:
        rows = _fetch_dicts(cursor, COUNTS_QUERY)
    return {key: int(value) for key, value in rows[0].items()}


def read_history(connection: Any) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        return _fetch_dicts(cursor, HISTORY_QUERY)


def run_analysis(connection: Any) -> dict[str, Any]:
    before = read_counts(connection)
    rows = read_history(connection)
    previous, current = resolve_snapshot_pair(rows)
    report = build_analysis(previous, current, before)
    after = read_counts(connection)
    if before != after:
        raise DataContractError("Source table counts changed during read-only analysis")
    connection.rollback()
    return report


def write_report(report: Mapping[str, Any], output: Path | None) -> None:
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if output is None:
        print(rendered, end="")
        return
    output.write_text(rendered, encoding="utf-8", newline="\n")


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Competitor Monitor snapshot Analyzer v1")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    connection_factory: Callable[[DatabaseConfig], Any] | None = None,
) -> int:
    args = parse_arguments(argv)
    config = load_database_config(os.environ if environment is None else environment)
    connection = connect_database(config) if connection_factory is None else connection_factory(config)
    try:
        report = run_analysis(connection)
        write_report(report, args.output)
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AnalyzerError as error:
        print(f"ERROR={error}")
        raise SystemExit(1)
