"""Pure normalisation, redaction and comparison for entitlement evidence."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import CRITICAL_CHECKS, CheckSpec, assert_read_only_contracts

RESULTS = {
    "AVAILABLE", "AVAILABLE_DEGRADED", "ENTITLEMENT_DENIED", "AUTH_FAILED", "RATE_LIMITED",
    "CONTRACT_CHANGED", "TRANSIENT_HTTP_FAILURE", "PARSE_FAILED", "UNKNOWN_FAILURE",
}
PHASES = {"BEFORE", "AFTER"}
SECRET_PATTERN = re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+|access[_-]?token[=:]\s*|client[_-]?secret[=:]\s*|api[_-]?key[=:]\s*)[^\s,;\"']+")


def _hash(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _schema(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_schema(value[0])] if value else []
    return type(value).__name__


def _get(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _row_count(response: Any) -> int | None:
    if isinstance(response, list):
        return len(response)
    if not isinstance(response, dict):
        return None
    for path in ("result.data", "result.actions", "result.products", "items", "result.operations", "result.postings", "list"):
        value = _get(response, path)
        if isinstance(value, list):
            return len(value)
    return None


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): redact(item) for key, item in value.items() if str(key).lower() not in {"authorization", "access_token", "client_secret", "api_key", "password"}}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SECRET_PATTERN.sub("[REDACTED]", value)
    return value


def classify(http_status: int | None, response: Any, spec: CheckSpec, error_code: Any = None, error_message: Any = None) -> tuple[str, bool]:
    message = str(error_message or "").lower()
    if http_status in (401, 403):
        return ("ENTITLEMENT_DENIED" if any(word in message for word in ("premium", "subscription", "entitlement", "permission", "access denied")) else "AUTH_FAILED", False)
    if http_status == 429:
        return "RATE_LIMITED", False
    if http_status is not None and http_status >= 500:
        return "TRANSIENT_HTTP_FAILURE", False
    if http_status is None:
        return "UNKNOWN_FAILURE", False
    if not 200 <= http_status < 300:
        return "UNKNOWN_FAILURE", False
    if not isinstance(response, (dict, list)):
        return "PARSE_FAILED", False
    required = all(_get(response, path) is not None for path in spec.required_fields)
    if not required:
        return "AVAILABLE_DEGRADED", False
    return "AVAILABLE", True


def _normalise_one(spec: CheckSpec, raw: dict[str, Any], phase: str, checked_at: str) -> dict[str, Any]:
    response = raw.get("response")
    status, required = classify(raw.get("http_status"), response, spec, raw.get("ozon_error_code"), raw.get("ozon_error_message"))
    return {
        "check_id": spec.check_id,
        "checked_at": checked_at,
        "subscription_phase": phase,
        "api_family": spec.api_family,
        "method": spec.method,
        "endpoint": spec.endpoint,
        "request_contract_hash": _hash({"method": spec.method, "endpoint": spec.endpoint, "shape": spec.request_shape}),
        "http_status": raw.get("http_status"),
        "ozon_error_code": redact(raw.get("ozon_error_code")),
        "ozon_error_message": redact(raw.get("ozon_error_message")),
        "response_schema_hash": _hash(_schema(response)) if isinstance(response, (dict, list)) else None,
        "row_count": _row_count(response),
        "required_fields_present": required,
        "result": status,
    }


def build_snapshot(phase: str, raw_checks: list[dict[str, Any]], checked_at: str | None = None) -> dict[str, Any]:
    if phase not in PHASES:
        raise ValueError("phase must be BEFORE or AFTER")
    assert_read_only_contracts()
    supplied = {str(item.get("check_id")): item for item in raw_checks}
    unknown = set(supplied) - {spec.check_id for spec in CRITICAL_CHECKS}
    if unknown:
        raise ValueError(f"unknown checks: {sorted(unknown)}")
    timestamp = checked_at or datetime.now(timezone.utc).isoformat()
    checks = [_normalise_one(spec, supplied.get(spec.check_id, {}), phase, timestamp) for spec in CRITICAL_CHECKS]
    return {"schema_version": "premium-exit-baseline/v0.1", "subscription_phase": phase, "checked_at": timestamp, "checks": checks}


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    if before.get("subscription_phase") != "BEFORE" or after.get("subscription_phase") != "AFTER":
        raise ValueError("comparison requires BEFORE then AFTER snapshots")
    before_by_id = {item["check_id"]: item for item in before.get("checks", [])}
    rows = []
    for current in after.get("checks", []):
        prior = before_by_id.get(current["check_id"])
        if prior is None:
            verdict = "INCONCLUSIVE"
        elif prior["result"] in {"AVAILABLE", "AVAILABLE_DEGRADED"} and current["result"] in {"AVAILABLE", "AVAILABLE_DEGRADED"}:
            verdict = "UNCHANGED" if prior["result"] == current["result"] and prior["response_schema_hash"] == current["response_schema_hash"] else "DEGRADED"
        elif current["result"] == "ENTITLEMENT_DENIED":
            verdict = "LOST"
        elif prior["result"] not in {"AVAILABLE", "AVAILABLE_DEGRADED"} and current["result"] in {"AVAILABLE", "AVAILABLE_DEGRADED"}:
            verdict = "IMPROVED"
        else:
            verdict = "INCONCLUSIVE"
        rows.append({"check_id": current["check_id"], "before_result": prior["result"] if prior else None, "after_result": current["result"], "comparison": verdict})
    critical_lost = any(row["comparison"] == "LOST" for row in rows)
    all_unchanged = bool(rows) and all(row["comparison"] == "UNCHANGED" for row in rows)
    decision = "SUBSCRIPTION_REVIEW_REQUIRED" if critical_lost else "KEEP_FREE" if all_unchanged else "KEEP_FREE_WITH_GAP"
    return {"schema_version": "premium-exit-baseline/v0.1", "before_checked_at": before.get("checked_at"), "after_checked_at": after.get("checked_at"), "checks": rows, "decision": decision}


def write_snapshot(snapshot: dict[str, Any], evidence_dir: str | Path) -> Path:
    phase = snapshot.get("subscription_phase")
    if phase not in PHASES:
        raise ValueError("snapshot phase is required")
    target = Path(evidence_dir) / ("before.json" if phase == "BEFORE" else "after.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(redact(snapshot), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return target
