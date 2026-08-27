"""Build the Competitor Monitor Summary v1 from persisted finding tables."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


CONTRACT_VERSION = "competitor_monitor_summary.v1"
FINDING_SET_CONTRACT = "competitor_finding_set.v1"
DETAILS_REF_PREFIX = "finding:"
ROLE_LABELS = {
    "CONTROL": "Наша карточка",
    "PRIMARY": "Основной конкурент",
    "RESERVE": "Дополнительный конкурент",
}
SEVERITY_PRIORITY = {"IMPORTANT": 0, "WATCH": 1, "INFO": 2}
VISIBILITY_LOST = {
    "OWN_SEARCH_VISIBILITY_LOST",
    "COMPETITOR_VISIBILITY_LOST",
}
VISIBILITY_RESTORED = {
    "OWN_SEARCH_VISIBILITY_RESTORED",
    "COMPETITOR_VISIBILITY_RESTORED",
}
PRICE_INCREASED = "COMPETITOR_PRICE_INCREASED"
PRICE_DECREASED = "COMPETITOR_PRICE_DECREASED"


LATEST_FINDING_SET_SQL = """
SELECT finding_set_id::text,set_key,persistence_contract_version,
       finding_set_contract_version,source_analysis_contract_version,
       source_findings_sha256,source_findings_semantic_sha256,
       source_analysis_sha256,previous_source_kind,
       previous_derived_batch_id,previous_reference_at,
       previous_captured_through,current_source_kind,
       current_derived_batch_id,current_reference_at,
       current_captured_through,expected_findings_count,applied_at
  FROM public.competitor_finding_sets
 WHERE finding_set_contract_version = 'competitor_finding_set.v1'
 ORDER BY current_reference_at DESC, applied_at DESC, finding_set_id DESC
 LIMIT 1
"""

FINDINGS_SQL = """
SELECT finding_id::text,finding_set_id::text,finding_kind,offer_id,
       product_family_id::text,listing_id::text,
       old_observation_id::text,new_observation_id::text,topic,metric,
       severity,confidence,status,evidence,details,finding_key,
       first_detected_at,last_detected_at
  FROM public.competitor_findings
 WHERE finding_set_id = %s::uuid
 ORDER BY finding_key
"""

COVERAGE_SQL = """
SELECT p.offer_id,p.watchlist_state,NULLIF(btrim(p.notes),'') AS source_reason,
       (
         p.watchlist_state = 'ACTIVE'
         AND EXISTS (
           SELECT 1
             FROM public.competitor_watchlist_memberships m
            WHERE m.offer_id = p.offer_id
              AND m.valid_to IS NULL
              AND m.membership_status IN ('CONTROL','PRIMARY','RESERVE')
         )
       ) AS active_monitored
  FROM public.competitor_sku_profiles p
 ORDER BY p.offer_id
"""


class SummaryError(RuntimeError):
    """Base class for safe summary failures."""


class ConfigurationError(SummaryError):
    """Raised when local runtime configuration is incomplete."""


class DatabaseError(SummaryError):
    """Raised when the read-only source cannot be queried."""


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class SourceData:
    manifest: Mapping[str, Any] | None
    findings: tuple[Mapping[str, Any], ...]
    coverage_rows: tuple[Mapping[str, Any], ...]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _hash_is_present(value: Any) -> bool:
    return _non_empty(value) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _coverage(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: str(row.get("offer_id", "")))
    active = [row for row in ordered if bool(row.get("active_monitored"))]
    unmonitored = [
        {
            "offer_id": row.get("offer_id"),
            "watchlist_state": row.get("watchlist_state"),
            "reason": row.get("source_reason") or None,
        }
        for row in ordered
        if not bool(row.get("active_monitored"))
    ]
    return {
        "portfolio_sku_count": len(ordered),
        "active_monitored_sku_count": len(active),
        "unmonitored_skus": unmonitored,
    }


def _empty_snapshot() -> dict[str, Any]:
    return {
        "finding_set_id": None,
        "set_key": None,
        "previous_source_kind": None,
        "previous_derived_batch_id": None,
        "previous_reference_at": None,
        "current_source_kind": None,
        "current_derived_batch_id": None,
        "reference_at": None,
        "captured_through": None,
        "age_seconds": None,
        "freshness_status": "UNAVAILABLE",
        "finding_set_contract_version": None,
    }


def _unavailable(
    *,
    generated_at: datetime,
    coverage: Mapping[str, Any],
    reason: str,
    snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": _iso(generated_at),
        "available": False,
        "degraded_reason": reason,
        "coverage": dict(coverage),
        "snapshot": dict(snapshot or _empty_snapshot()),
        "status": "UNAVAILABLE",
        "counts": {
            "important_count": None,
            "watch_count": None,
            "info_count": None,
            "total_findings": None,
        },
        "headline": None,
        "own": None,
        "competitors": None,
        "prices": None,
        "top_findings": [],
    }


def _snapshot_validation_error(manifest: Mapping[str, Any]) -> bool:
    required_text = (
        "finding_set_id",
        "set_key",
        "persistence_contract_version",
        "finding_set_contract_version",
        "source_analysis_contract_version",
        "previous_source_kind",
        "previous_derived_batch_id",
        "current_source_kind",
        "current_derived_batch_id",
    )
    if any(not _non_empty(manifest.get(name)) for name in required_text):
        return True
    if manifest.get("finding_set_contract_version") != FINDING_SET_CONTRACT:
        return True
    if any(
        not _hash_is_present(manifest.get(name))
        for name in (
            "source_findings_sha256",
            "source_findings_semantic_sha256",
            "source_analysis_sha256",
        )
    ):
        return True
    timestamps = (
        manifest.get("previous_reference_at"),
        manifest.get("previous_captured_through"),
        manifest.get("current_reference_at"),
        manifest.get("current_captured_through"),
    )
    if any(not isinstance(value, datetime) for value in timestamps):
        return True
    previous_reference, previous_captured, current_reference, current_captured = timestamps
    return not (
        _utc(previous_captured) >= _utc(previous_reference)
        and _utc(current_captured) >= _utc(current_reference)
        and _utc(current_reference) > _utc(previous_reference)
    )


def _snapshot(
    manifest: Mapping[str, Any],
    generated_at: datetime,
    threshold_seconds: int | None,
    grace_seconds: int,
) -> dict[str, Any]:
    reference_at = _utc(manifest["current_reference_at"])
    age_seconds = int((_utc(generated_at) - reference_at).total_seconds())
    if threshold_seconds is None:
        freshness = "UNKNOWN"
    else:
        freshness = "STALE" if age_seconds > threshold_seconds + grace_seconds else "FRESH"
    return {
        "finding_set_id": manifest["finding_set_id"],
        "set_key": manifest["set_key"],
        "previous_source_kind": manifest["previous_source_kind"],
        "previous_derived_batch_id": manifest["previous_derived_batch_id"],
        "previous_reference_at": _iso(manifest["previous_reference_at"]),
        "current_source_kind": manifest["current_source_kind"],
        "current_derived_batch_id": manifest["current_derived_batch_id"],
        "reference_at": _iso(reference_at),
        "captured_through": _iso(manifest["current_captured_through"]),
        "age_seconds": age_seconds,
        "freshness_status": freshness,
        "finding_set_contract_version": manifest["finding_set_contract_version"],
    }


def _finding_validation_error(
    manifest: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]
) -> bool:
    expected = manifest.get("expected_findings_count")
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
        return True
    if expected != len(findings):
        return True
    set_id = str(manifest["finding_set_id"])
    keys: list[str] = []
    for finding in findings:
        key = finding.get("finding_key")
        details = finding.get("details")
        evidence = finding.get("evidence")
        if not _non_empty(key) or str(finding.get("finding_set_id")) != set_id:
            return True
        if not isinstance(details, Mapping) or not isinstance(evidence, list):
            return True
        if not _non_empty(details.get("finding_type")) or details.get("finding_type") != finding.get("topic"):
            return True
        if details.get("membership_status") not in ROLE_LABELS:
            return True
        if not isinstance(details.get("query_context"), list):
            return True
        if finding.get("severity") not in SEVERITY_PRIORITY:
            return True
        keys.append(key)
    return len(keys) != len(set(keys))


def _queries(finding: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    details = finding["details"]
    return sorted(
        details.get("query_context", []), key=lambda row: str(row.get("query_text_exact", ""))
    )


def _query_names(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row["query_text_exact"])
            for row in rows
            if _non_empty(row.get("query_text_exact"))
        }
    )


def _affected_and_remaining(finding: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    contexts = _queries(finding)
    topic = finding["topic"]
    transition = "DROPPED_OUT" if topic in VISIBILITY_LOST else "APPEARED"
    affected_rows = [row for row in contexts if row.get("visibility_transition") == transition]
    affected = _query_names(affected_rows)
    remaining = _query_names(
        [
            row
            for row in contexts
            if row.get("current_status") == "FOUND"
            and row.get("query_text_exact") not in affected
        ]
    )
    return affected, remaining


def _role_label(finding: Mapping[str, Any]) -> str:
    return ROLE_LABELS[finding["details"]["membership_status"]]


def _message(finding: Mapping[str, Any]) -> str:
    topic = finding["topic"]
    offer_id = str(finding["offer_id"])
    role = finding["details"]["membership_status"]
    label = _role_label(finding)
    affected, remaining = _affected_and_remaining(finding)
    query_text = ", ".join(affected or _query_names(_queries(finding)))
    if topic in VISIBILITY_LOST:
        if role == "CONTROL":
            message = (
                f"{offer_id}: наша карточка не найдена по OEM {query_text} "
                "в пределах лимита текущего снимка"
            )
        else:
            message = (
                f"{offer_id}: {label.lower()} не найден по OEM {query_text} "
                "в пределах лимита текущего снимка"
            )
        if remaining:
            message += f"; найдена по OEM {', '.join(remaining)}"
        return message + "."
    if topic in VISIBILITY_RESTORED:
        if role == "CONTROL":
            return (
                f"{offer_id}: наша карточка снова найдена по OEM {query_text} "
                "в пределах лимита текущего снимка."
            )
        return (
            f"{offer_id}: {label.lower()} снова найден по OEM {query_text} "
            "в пределах лимита текущего снимка."
        )
    if topic in {PRICE_INCREASED, PRICE_DECREASED}:
        details = finding["details"]
        previous = details.get("previous_value") or {}
        current = details.get("current_value") or {}
        direction = "выросла" if topic == PRICE_INCREASED else "снизилась"
        currency = current.get("currency") or previous.get("currency") or ""
        return (
            f"{offer_id}: цена ({label.lower()}) {direction} "
            f"с {previous.get('amount')} до {current.get('amount')} {currency}."
        ).replace("  ", " ")
    return f"{offer_id}: зафиксирован сигнал {topic}."


def _sort_key(finding: Mapping[str, Any]) -> tuple[Any, ...]:
    membership = finding["details"]["membership_status"]
    return (
        SEVERITY_PRIORITY[finding["severity"]],
        0 if membership == "CONTROL" else 1,
        str(finding["topic"]),
        str(finding["offer_id"]),
        str(finding["finding_key"]),
    )


def _compact(finding: Mapping[str, Any]) -> dict[str, Any]:
    affected, remaining = _affected_and_remaining(finding)
    return {
        "finding_key": finding["finding_key"],
        "finding_type": finding["topic"],
        "severity": finding["severity"],
        "confidence": finding["confidence"],
        "offer_id": finding["offer_id"],
        "role_label": _role_label(finding),
        "membership_status": finding["details"]["membership_status"],
        "message": _message(finding),
        "affected_queries": affected,
        "remaining_queries": remaining,
        "details_ref": DETAILS_REF_PREFIX + finding["finding_key"],
    }


def _price_item(finding: Mapping[str, Any]) -> dict[str, Any]:
    details = finding["details"]
    previous = details.get("previous_value") or {}
    current = details.get("current_value") or {}
    return {
        "finding_key": finding["finding_key"],
        "offer_id": finding["offer_id"],
        "ozon_product_id": details.get("ozon_product_id"),
        "role_label": _role_label(finding),
        "previous_price": previous.get("amount"),
        "current_price": current.get("amount"),
        "delta": details.get("delta"),
        "delta_pct": details.get("delta_pct"),
        "currency": current.get("currency") or previous.get("currency"),
        "query_context": _query_names(_queries(finding)),
        "details_ref": DETAILS_REF_PREFIX + finding["finding_key"],
    }


def build_summary(
    source: SourceData,
    *,
    generated_at: datetime | None = None,
    freshness_threshold_seconds: int | None = None,
    freshness_grace_seconds: int = 0,
    max_findings: int = 5,
) -> dict[str, Any]:
    """Build the stable presentation DTO without consulting Analyzer artifacts."""
    now = _utc(generated_at or datetime.now(timezone.utc))
    if freshness_threshold_seconds is not None and freshness_threshold_seconds < 0:
        raise ConfigurationError("Freshness threshold must be non-negative")
    if freshness_grace_seconds < 0:
        raise ConfigurationError("Freshness grace must be non-negative")
    if max_findings < 1:
        raise ConfigurationError("max_findings must be positive")
    coverage = _coverage(source.coverage_rows)
    manifest = source.manifest
    if manifest is None:
        return _unavailable(
            generated_at=now, coverage=coverage, reason="FINDING_SET_MISSING"
        )
    if _snapshot_validation_error(manifest):
        return _unavailable(
            generated_at=now, coverage=coverage, reason="SNAPSHOT_UNAVAILABLE"
        )
    snapshot = _snapshot(
        manifest, now, freshness_threshold_seconds, freshness_grace_seconds
    )
    if _finding_validation_error(manifest, source.findings):
        return _unavailable(
            generated_at=now,
            coverage=coverage,
            reason="FINDING_SET_INVALID",
            snapshot=snapshot,
        )

    findings = list(source.findings)
    counts = {
        "important_count": sum(row["severity"] == "IMPORTANT" for row in findings),
        "watch_count": sum(row["severity"] == "WATCH" for row in findings),
        "info_count": sum(row["severity"] == "INFO" for row in findings),
        "total_findings": len(findings),
    }
    if sum(counts[name] for name in ("important_count", "watch_count", "info_count")) != len(findings):
        return _unavailable(
            generated_at=now,
            coverage=coverage,
            reason="FINDING_SET_INVALID",
            snapshot=snapshot,
        )
    status = (
        "IMPORTANT"
        if counts["important_count"]
        else "WATCH" if counts["watch_count"] else "NORMAL"
    )
    own = [row for row in findings if row["details"]["membership_status"] == "CONTROL"]
    competitors = [
        row
        for row in findings
        if row["details"]["membership_status"] in {"PRIMARY", "RESERVE"}
    ]
    competitor_lost = [row for row in competitors if row["topic"] == "COMPETITOR_VISIBILITY_LOST"]
    competitor_restored = [
        row for row in competitors if row["topic"] == "COMPETITOR_VISIBILITY_RESTORED"
    ]
    price_changes = [
        row for row in competitors if row["topic"] in {PRICE_INCREASED, PRICE_DECREASED}
    ]
    attention = [row for row in findings if row["severity"] in {"IMPORTANT", "WATCH"}]
    headline_row = min(attention, key=_sort_key) if attention else None
    headline = (
        {
            "finding_key": headline_row["finding_key"],
            "severity": headline_row["severity"],
            "message": _message(headline_row),
            "details_ref": DETAILS_REF_PREFIX + headline_row["finding_key"],
        }
        if headline_row
        else {
            "finding_key": None,
            "severity": None,
            "message": "Нет findings уровня WATCH или IMPORTANT.",
            "details_ref": None,
        }
    )
    summary = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": _iso(now),
        "available": True,
        "degraded_reason": None,
        "coverage": coverage,
        "snapshot": snapshot,
        "status": status,
        "counts": counts,
        "headline": headline,
        "own": {
            "own_watch_count": sum(row["severity"] == "WATCH" for row in own),
            "own_restored_count": sum(row["topic"] == "OWN_SEARCH_VISIBILITY_RESTORED" for row in own),
            "own_findings": [_compact(row) for row in sorted(own, key=_sort_key)],
        },
        "competitors": {
            "visibility_lost_count": len(competitor_lost),
            "visibility_restored_count": len(competitor_restored),
            "primary_lost_count": sum(row["details"]["membership_status"] == "PRIMARY" for row in competitor_lost),
            "reserve_lost_count": sum(row["details"]["membership_status"] == "RESERVE" for row in competitor_lost),
            "primary_restored_count": sum(row["details"]["membership_status"] == "PRIMARY" for row in competitor_restored),
            "reserve_restored_count": sum(row["details"]["membership_status"] == "RESERVE" for row in competitor_restored),
            "findings": [_compact(row) for row in sorted(competitor_lost + competitor_restored, key=_sort_key)],
        },
        "prices": {
            "price_changes_count": len(price_changes),
            "price_increased_count": sum(row["topic"] == PRICE_INCREASED for row in price_changes),
            "price_decreased_count": sum(row["topic"] == PRICE_DECREASED for row in price_changes),
            "price_changes": [_price_item(row) for row in sorted(price_changes, key=_sort_key)],
        },
        "top_findings": [_compact(row) for row in sorted(findings, key=_sort_key)[:max_findings]],
    }
    if snapshot["freshness_status"] == "STALE":
        summary["available"] = False
        summary["degraded_reason"] = "FINDING_SET_STALE"
    return summary


def _dict_rows(cursor: Any) -> tuple[dict[str, Any], ...]:
    columns = [item.name if hasattr(item, "name") else item[0] for item in cursor.description]
    return tuple(dict(zip(columns, row)) for row in cursor.fetchall())


def read_source(connection: Any) -> SourceData:
    """Read one consistent source snapshot and always end it with rollback."""
    try:
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor() as cursor:
            cursor.execute(LATEST_FINDING_SET_SQL)
            row = cursor.fetchone()
            if row is None:
                manifest = None
            else:
                columns = [item.name if hasattr(item, "name") else item[0] for item in cursor.description]
                manifest = dict(zip(columns, row))
            if manifest is None:
                findings: tuple[dict[str, Any], ...] = ()
            else:
                cursor.execute(FINDINGS_SQL, (manifest["finding_set_id"],))
                findings = _dict_rows(cursor)
            cursor.execute(COVERAGE_SQL)
            coverage_rows = _dict_rows(cursor)
        connection.rollback()
        return SourceData(manifest, findings, coverage_rows)
    except Exception as error:
        try:
            connection.rollback()
        except Exception:
            pass
        raise DatabaseError("Competitor Monitor summary read failed") from error


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
        environment["EFA_DB_HOST"].strip(),
        port,
        environment["EFA_DB_NAME"].strip(),
        environment["EFA_DB_USER"].strip(),
        environment["EFA_DB_PASSWORD"],
    )


def connect_database(config: DatabaseConfig) -> Any:
    connection = None
    try:
        import psycopg2

        connection = psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.name,
            user=config.user,
            password=config.password,
            connect_timeout=10,
            options="-c default_transaction_read_only=on -c statement_timeout=30000",
        )
        connection.set_session(readonly=True, autocommit=False)
        return connection
    except Exception as error:
        if connection is not None:
            connection.close()
        raise DatabaseError("PostgreSQL read-only connection failed") from error


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Competitor Monitor Summary Read Model v1")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-findings", type=int, default=5)
    parser.add_argument("--freshness-threshold-seconds", type=int)
    parser.add_argument("--freshness-grace-seconds", type=int, default=0)
    return parser.parse_args(argv)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    connection_factory: Callable[[DatabaseConfig], Any] | None = None,
) -> int:
    args = parse_arguments(argv)
    env = os.environ if environment is None else environment
    config = load_database_config(env)
    factory = connect_database if connection_factory is None else connection_factory
    connection = factory(config)
    try:
        source = read_source(connection)
    finally:
        connection.close()
    result = build_summary(
        source,
        freshness_threshold_seconds=args.freshness_threshold_seconds,
        freshness_grace_seconds=args.freshness_grace_seconds,
        max_findings=args.max_findings,
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2, default=_json_default) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SummaryError as error:
        print(f"ERROR={error}", file=sys.stderr)
        raise SystemExit(1) from None
