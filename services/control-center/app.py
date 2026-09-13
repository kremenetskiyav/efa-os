#!/usr/bin/env python3
"""Small read-only web panel for the existing EFA OS runtime."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import re
import socket
import sys
from datetime import date, datetime, time, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

import read_model  # noqa: E402
import current_finance  # noqa: E402

# Archived detail routes load their old helpers only when explicitly visited.
# The W00-W08/W06 home page can start without the retired collector modules.
def parse_report(*args, **kwargs):
    from Scripts.format_ai_analyst_email import parse_report as legacy_parse
    return legacy_parse(*args, **kwargs)


def build_summary(*args, **kwargs):
    from Scripts.build_competitor_monitor_summary_v1 import build_summary as legacy_build
    return legacy_build(*args, **kwargs)


def SourceData(*args, **kwargs):
    from Scripts.build_competitor_monitor_summary_v1 import SourceData as legacy_source
    return legacy_source(*args, **kwargs)


MOSCOW = timezone(timedelta(hours=3), name="Europe/Moscow")
UTC = timezone.utc
STATIC_DIR = Path(__file__).with_name("static")
REPORT_PATH = Path(os.environ.get("EFA_ANALYST_REPORT", "/var/log/efa-os/ai-analyst-latest.txt"))
DELIVERY_LOG_PATH = Path(os.environ.get("EFA_ANALYST_EMAIL_LOG", "/var/log/efa-os/ai-analyst-email.log"))
CRON_PATH = Path(os.environ.get("EFA_ANALYTICS_CRON", "/etc/cron.d/efa-os-analytics"))
DELIVERY_WORKFLOW_PATH = Path(os.environ.get(
    "EFA_ANALYST_DELIVERY_WORKFLOW",
    REPO_ROOT / "n8n/workflows/EFA_AI_Analyst_Delivery_v1.json",
))
OLD_BRIEF_WORKFLOW_PATH = Path(os.environ.get(
    "EFA_OLD_BRIEF_WORKFLOW",
    REPO_ROOT / "n8n/workflows/Ozon_Daily_Commercial_Brief_Delivery_v1.json",
))
N8N_HOST = os.environ.get("EFA_N8N_HEALTH_HOST", "127.0.0.1")
N8N_PORT = int(os.environ.get("EFA_N8N_HEALTH_PORT", "5678"))
MCP_HOST = os.environ.get("EFA_MCP_HEALTH_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("EFA_MCP_HEALTH_PORT", "8000"))
N8N_URL = os.environ.get("EFA_N8N_URL", "http://127.0.0.1:5678")
OZON_AGENTS_ROOT = Path(os.environ.get("EFA_OZON_AGENTS_ROOT", REPO_ROOT / "OZON_AI_AGENTS"))
OZON_REPORTS_ROOT = OZON_AGENTS_ROOT / "REPORTS"

WORK_METADATA: dict[str, dict[str, str | None]] = {
    "W00": {"name": "EFA Coordinator", "canonical_role": "EFA Coordinator", "mode": "DAILY"},
    "W01": {"name": "Market & Competitor Intelligence", "canonical_role": "Competitor Intelligence", "mode": "DAILY"},
    "W02": {"name": "Customer Service & Compatibility", "canonical_role": None, "mode": "DAILY"},
    "W03": {"name": "Promotion & Advertising", "canonical_role": None, "mode": "DAILY"},
    "W04": {"name": "Content & SEO", "canonical_role": None, "mode": "ON DEMAND"},
    "W05": {"name": "Visual Content", "canonical_role": None, "mode": "ON DEMAND"},
    "W06": {"name": "Finance & Unit Economics", "canonical_role": "Pricing & Economics", "mode": "CONDITIONAL"},
    "W07": {"name": "Control & Audit", "canonical_role": None, "mode": "DAILY"},
    "W08": {"name": "Commercial Analyst", "canonical_role": "Commercial Analyst", "mode": "DAILY"},
}

REPORT_PATTERNS = {
    "W00": "W00/DAILY/*/W00_OWNER_BRIEF.md",
    "W01": "W01/DAILY/*/W01_MARKET_REPORT.md",
    "W02": "W02/DAILY/*/W02_CUSTOMER_REPORT.md",
    "W03": "W03/DAILY/*/W03_PROMOTION_REPORT.md",
    "W04": "W04/**/W04_CONTENT_REPORT*.md",
    "W05": "W05/**/W05_VISUAL_REPORT*.md",
    "W06": "W06/**/*.md",
    "W07": "W07/DAILY/*/W07_CONTROL_REPORT.md",
    "W08": "W08/DAILY/*/W08_COMMERCIAL_REPORT.md",
}


COLLECTOR_QUERY = """
WITH latest_demand_date AS (
  SELECT max(business_date) AS business_date
    FROM mcp_read.product_daily_performance
   WHERE demand_collected_at IS NOT NULL
), demand_snapshot AS (
  SELECT
    p.business_date,
    max(p.demand_collected_at) AS collected_at,
    array_remove(array_agg(DISTINCT p.demand_quality_status), NULL) AS statuses
  FROM mcp_read.product_daily_performance p
  JOIN latest_demand_date d ON d.business_date = p.business_date
  WHERE p.demand_collected_at IS NOT NULL
  GROUP BY p.business_date
)
SELECT
  (SELECT business_date FROM demand_snapshot) AS demand_date,
  (SELECT collected_at FROM demand_snapshot) AS demand_at,
  (SELECT statuses FROM demand_snapshot) AS demand_statuses,
  (SELECT max(price_checked_at) FROM mcp_read.product_overview) AS price_at,
  (SELECT max(stock_snapshot_at) FROM mcp_read.product_overview) AS stock_at,
  (SELECT array_remove(array_agg(DISTINCT stock_data_quality_status), NULL)
     FROM mcp_read.product_overview) AS stock_statuses,
  (SELECT max(observed_at) FROM mcp_read.product_promotion_state) AS promotion_at,
  (SELECT array_remove(array_agg(DISTINCT data_quality_status), NULL)
     FROM mcp_read.product_promotion_state
    WHERE observed_at = (SELECT max(observed_at) FROM mcp_read.product_promotion_state)) AS promotion_statuses,
  (SELECT max(observed_at) FROM mcp_read.product_cpc_daily) AS cpc_at,
  (SELECT max(business_date) FROM mcp_read.product_cpc_daily) AS cpc_date,
  (SELECT array_remove(array_agg(DISTINCT collection_status), NULL)
     FROM mcp_read.product_cpc_daily
    WHERE business_date = (SELECT max(business_date) FROM mcp_read.product_cpc_daily)) AS cpc_statuses,
  (SELECT max(business_date) FROM mcp_read.product_daily_performance
    WHERE delivered_units IS NOT NULL) AS operations_date,
  (SELECT array_remove(array_agg(DISTINCT economics_quality_status), NULL)
     FROM mcp_read.product_daily_performance
    WHERE business_date = (SELECT max(business_date) FROM mcp_read.product_daily_performance
                            WHERE delivered_units IS NOT NULL)) AS operations_statuses
"""


def _fmt_dt(value: datetime | date | None) -> str:
    if value is None:
        return "Нет данных"
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(MOSCOW).strftime("%d.%m.%Y %H:%M МСК")


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _age_ok(value: datetime | date | None, now: datetime, hours: int = 54) -> bool:
    if value is None:
        return False
    if isinstance(value, date) and not isinstance(value, datetime):
        observed = datetime.combine(value, time(23, 59), tzinfo=MOSCOW)
    else:
        observed = value if value.tzinfo else value.replace(tzinfo=UTC)
    return now.astimezone(UTC) - observed.astimezone(UTC) <= timedelta(hours=hours)


def _statuses_ok(values: list[str] | None) -> bool:
    if not values:
        return False
    bad = ("FAIL", "ERROR", "INVALID", "STALE", "MISSING", "STUCK")
    return not any(any(word in str(value).upper() for word in bad) for value in values)


def _demand_statuses_ok(values: list[str] | None) -> bool:
    """Demand is healthy only when every latest-source row is explicitly valid."""
    return bool(values) and all(value == "valid" for value in values)


def parse_cron_schedule(text: str, now: datetime, lock_name: str = "efa-ai-analyst.lock") -> tuple[datetime | None, str]:
    """Read an existing daily schedule from cron; do not duplicate its time in code."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or lock_name not in line:
            continue
        fields = line.split(None, 5)
        if len(fields) < 6 or not fields[0].isdigit() or not fields[1].isdigit():
            return None, "Расписание не распознано"
        minute, hour = int(fields[0]), int(fields[1])
        candidate_utc = now.astimezone(UTC).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate_utc <= now.astimezone(UTC):
            candidate_utc += timedelta(days=1)
        return candidate_utc, f"Ежедневно в {candidate_utc.astimezone(MOSCOW):%H:%M} МСК"
    return None, "Расписание не найдено"


def delivery_confirmation(path: Path) -> dict[str, Any]:
    """The current log confirms webhook acceptance, not completion of both channels."""
    source = "webhook_acknowledgement" if path.is_file() else "unavailable"
    return {"confirmed": False, "label": "Нет подтверждения", "at": None, "source": source}


def delivery_configuration(delivery_path: Path, old_brief_path: Path) -> dict[str, bool | None]:
    """Read channel switches from the existing deployed, sanitised workflow definitions."""
    try:
        delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        delivery = None
    try:
        old_brief = json.loads(old_brief_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        old_brief = None

    email_on: bool | None = None
    telegram_on: bool | None = None
    if isinstance(delivery, dict):
        active = delivery.get("active") is True
        nodes = delivery.get("nodes") if isinstance(delivery.get("nodes"), list) else []
        email_on = active and any(
            isinstance(node, dict)
            and node.get("disabled") is not True
            and node.get("type") == "n8n-nodes-base.gmail"
            for node in nodes
        )
        telegram_on = active and any(
            isinstance(node, dict)
            and node.get("disabled") is not True
            and "telegram" in str(node.get("name", "")).lower()
            for node in nodes
        )

    old_brief_on: bool | None = None
    if isinstance(old_brief, dict):
        old_brief_on = old_brief.get("active") is True

    return {
        "email_on": email_on,
        "telegram_on": telegram_on,
        "old_brief_on": old_brief_on,
    }


def _tcp_online(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


async def read_database() -> tuple[bool, dict[str, Any]]:
    try:
        import asyncpg
    except ImportError:
        return False, {}

    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        return False, {}
    connection = None
    try:
        connection = await asyncpg.connect(
            dsn=dsn,
            timeout=3,
            command_timeout=5,
            server_settings={
                "application_name": "efa_control_center_v1",
                "default_transaction_read_only": "on",
                "statement_timeout": "5000ms",
                "lock_timeout": "1500ms",
                "search_path": "mcp_read,pg_catalog",
            },
        )
        async with connection.transaction(readonly=True):
            identity = await connection.fetchrow(
                "SELECT current_user AS role, current_database() AS db, current_setting('transaction_read_only') AS ro"
            )
            if identity["role"] != "efa_mcp_readonly" or identity["db"] != "efa" or identity["ro"] != "on":
                return False, {}
            row = await connection.fetchrow(COLLECTOR_QUERY)
            return True, dict(row)
    except (asyncpg.PostgresError, OSError, TimeoutError):
        return False, {}
    finally:
        if connection is not None:
            await connection.close()


def _decode_competitor_record(record: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(record)
    for field in ("evidence", "details"):
        value = result.get(field)
        if isinstance(value, str):
            result[field] = json.loads(value)
    return result


async def read_competitor_summary() -> dict[str, Any]:
    from Scripts.build_competitor_monitor_summary_v1 import COVERAGE_SQL, FINDINGS_SQL, LATEST_FINDING_SET_SQL
    """Read the approved three-view source using the dedicated runtime role."""
    import asyncpg

    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("Competitor Monitor database configuration is unavailable")
    connection = None
    try:
        connection = await asyncpg.connect(
            dsn=dsn,
            timeout=3,
            command_timeout=5,
            server_settings={
                "application_name": "efa_control_center_competitor_v1",
                "default_transaction_read_only": "on",
                "statement_timeout": "5000ms",
                "lock_timeout": "1500ms",
                "search_path": "mcp_read,pg_catalog",
            },
        )
        async with connection.transaction(readonly=True):
            identity = await connection.fetchrow(
                "SELECT current_user AS role, current_database() AS db, "
                "current_setting('transaction_read_only') AS ro"
            )
            if identity["role"] != "efa_mcp_readonly" or identity["db"] != "efa" or identity["ro"] != "on":
                raise RuntimeError("Competitor Monitor runtime identity is invalid")
            manifest_row = await connection.fetchrow(LATEST_FINDING_SET_SQL)
            manifest = _decode_competitor_record(manifest_row) if manifest_row is not None else None
            if manifest is None:
                findings: tuple[dict[str, Any], ...] = ()
            else:
                findings_query = FINDINGS_SQL.replace("%s::uuid", "$1::uuid")
                finding_rows = await connection.fetch(findings_query, manifest["finding_set_id"])
                findings = tuple(_decode_competitor_record(row) for row in finding_rows)
            coverage_rows = await connection.fetch(COVERAGE_SQL)
            source = SourceData(
                manifest,
                findings,
                tuple(_decode_competitor_record(row) for row in coverage_rows),
            )
        return build_summary(source)
    finally:
        if connection is not None:
            await connection.close()


def _competitor_read_error() -> dict[str, Any]:
    result = build_summary(SourceData(None, (), ()))
    result["degraded_reason"] = "CONTROL_CENTER_COMPETITOR_READ_ERROR"
    return result


def load_competitor_summary() -> dict[str, Any]:
    try:
        return asyncio.run(read_competitor_summary())
    except Exception:
        return _competitor_read_error()


def collector_snapshot(row: dict[str, Any], now: datetime) -> tuple[list[dict[str, Any]], datetime | date | None]:
    definitions = [
        (
            "Спрос",
            row.get("demand_at") or row.get("demand_date"),
            row.get("demand_statuses"),
            _demand_statuses_ok,
        ),
        ("Цены", row.get("price_at"), ["OK"] if row.get("price_at") else [], _statuses_ok),
        ("Остатки", row.get("stock_at"), row.get("stock_statuses"), _statuses_ok),
        ("Акции", row.get("promotion_at"), row.get("promotion_statuses"), _statuses_ok),
        (
            "CPC",
            row.get("cpc_at") or row.get("cpc_date"),
            row.get("cpc_statuses"),
            _statuses_ok,
        ),
        (
            "Operational finance",
            row.get("operations_date"),
            row.get("operations_statuses"),
            _statuses_ok,
        ),
    ]
    result = []
    observed_values = []
    for name, observed, statuses, status_check in definitions:
        ok = _age_ok(observed, now) and status_check(list(statuses or []))
        result.append({
            "name": name,
            "ok": ok,
            "status": "OK" if ok else "Проблема",
            "updated": _fmt_dt(observed),
            "observed_at": _iso(observed),
            "details": ", ".join(str(value) for value in (statuses or [])) or "Нет данных",
        })
        if observed is not None:
            observed_values.append(observed)
    latest = max(observed_values, key=lambda value: str(value), default=None)
    return result, latest


def report_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        return {"available": False, "counts": {"attention": 0, "watch": 0, "leave": 0}, "signals": []}, ""
    try:
        report = path.read_text(encoding="utf-8")
        report_date, skus, freshness = parse_report(report)
    except (OSError, UnicodeError, ValueError):
        return {"available": False, "counts": {"attention": 0, "watch": 0, "leave": 0}, "signals": []}, ""
    counts = {
        "attention": sum("ПРОВЕРИТЬ СЕЙЧАС" in sku.signal for sku in skus),
        "watch": sum("НАБЛЮДАТЬ" in sku.signal for sku in skus),
        "leave": sum("НЕ ТРОГАТЬ" in sku.signal for sku in skus),
    }
    signals = [
        {"sku": sku.name, "signal": sku.signal, "reason": sku.reason}
        for sku in skus[:5]
    ]
    modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    return {
        "available": True,
        "date": report_date,
        "freshness": freshness,
        "modified": _fmt_dt(modified),
        "modified_iso": _iso(modified),
        "counts": counts,
        "signals": signals,
    }, report


def _read_text(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _latest_report_path(work_id: str) -> Path | None:
    pattern = REPORT_PATTERNS.get(work_id)
    if not pattern or not OZON_REPORTS_ROOT.is_dir():
        return None
    candidates = [path for path in OZON_REPORTS_ROOT.glob(pattern) if path.is_file()]
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)), default=None)


def _first_match(text: str, *patterns: str, default: str = "NOT AVAILABLE") -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            return match.group(1).strip().strip("`.* ")
    return default


def _int_match(text: str, *patterns: str) -> int | None:
    value = _first_match(text, *patterns, default="")
    if not value:
        return None
    match = re.search(r"\d+", value.replace(",", ""))
    return int(match.group()) if match else None


def _report_date(path: Path | None) -> str | None:
    if path is None:
        return None
    for part in reversed(path.parts):
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", part):
            return part
    return datetime.fromtimestamp(path.stat().st_mtime, MOSCOW).date().isoformat()


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s|\Z)",
        text,
        re.I | re.M | re.S,
    )
    return match.group("body") if match else ""


def _plain_markdown(value: str) -> str:
    value = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", value)
    value = re.sub(r"[`*]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _owner_attention(text: str) -> list[str]:
    body = _section(text, "Owner Attention")
    items = re.findall(r"^\d+\.\s+(.+)$", body, re.M)
    return [_plain_markdown(item) for item in items]


def _blockers(text: str) -> list[dict[str, str]]:
    body = _section(text, "Active Blockers")
    rows = []
    for line in body.splitlines():
        if not re.match(r"^\|\s*FB-\d+\s*\|", line):
            continue
        cells = [_plain_markdown(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 4:
            rows.append({
                "id": cells[0],
                "domain": "Finance / Advertising",
                "owner": cells[1],
                "status": cells[2],
                "reason": cells[3],
            })
    return rows


def _work_status(work_id: str, text: str) -> str:
    patterns = {
        "W00": (r"\|\s*Run status\s*\|\s*`?([^|`]+)",),
        "W01": (r"Final run status:\s*`?([^`\n]+)", r"\|\s*Run status\s*\|\s*([^|]+)"),
        "W02": (r"Run status:\s*`([^`]+)`",),
        "W03": (r"Run status:\s*`([^`]+)`",),
        "W06": (r"Re-validation status:\*{0,2}\s*`([^`]+)`",),
        "W07": (r"\|\s*Audit outcome\s*\|\s*`?([^|`]+)",),
        "W08": (r"Run status:\s*`([^`]+)`",),
    }
    return _first_match(text, *patterns.get(work_id, ()), default="NOT AVAILABLE")


def _work_freshness(work_id: str, text: str) -> str:
    if work_id in {"W04", "W05"}:
        return "NOT_APPLICABLE"
    patterns = {
        "W01": (r"Direct-observation freshness\s*\|\s*`?([^|`]+)",),
        "W02": (r"Freshness:\s*`([^`]+)`",),
        "W08": (r"Aggregate freshness:\s*`([^`]+)`",),
    }
    return _first_match(text, *patterns.get(work_id, ()), default="UNKNOWN")


def _count_unique(text: str, pattern: str) -> int | None:
    values = set(re.findall(pattern, text, re.I | re.M))
    return len(values) if values else None


def _work_metrics(work_id: str, text: str) -> dict[str, int | None]:
    findings: int | None = None
    proposals: int | None = None
    blockers: int | None = None
    handoffs: int | None = None
    if work_id == "W00":
        findings = _int_match(text, r"Owner attention items:\s*`?(\d+)")
        blockers = _int_match(text, r"Blockers preserved\s*\|\s*`?YES\s*[—-]\s*(\d+)/")
        handoffs = 0
    elif work_id == "W01":
        findings = _int_match(text, r"Significant findings:\s*(\d+)")
        handoffs = _count_unique(_section(text, "Recommendations / Handoffs"), r"^###\s+(W\d{2})")
    elif work_id == "W02":
        findings = _int_match(text, r"Product-data findings:\s*`?(\d+)")
        handoffs = len(re.findall(r"^\|\s*W\d{2}\s*\|\s*`YES`", _section(text, "Handoffs"), re.M)) or None
    elif work_id == "W03":
        findings = _count_unique(text, r"W03-D-A\d+")
        proposals = _count_unique(text, r"W03-D-P\d+")
        handoffs = _int_match(text, r"Handoffs required:\s*(\d+)")
    elif work_id == "W06":
        blockers = len(re.findall(r"^#{2,3}\s+FB-\d+", text, re.M)) or None
    elif work_id == "W07":
        findings = _int_match(text, r"Follow-up findings preserved\s*\|\s*`?YES\s*[—-]\s*(\d+)/")
        blockers = _int_match(text, r"Blockers checked:\s*`?(\d+)")
        handoffs = 0 if "W00 DAILY OWNER BRIEF" in _read_text(_latest_report_path("W00")) else 1
    elif work_id == "W08":
        findings = _int_match(text, r"SKU requiring commercial attention:\s*`?(\d+)")
        proposals = _int_match(text, r"Commercial test proposals:\s*`?(\d+)")
        blockers = _int_match(text, r"Active financial blockers:\s*`?(\d+)")
        handoffs = 0 if "W00 DAILY OWNER BRIEF" in _read_text(_latest_report_path("W00")) else 1
    return {"findings": findings, "proposals": proposals, "blockers": blockers, "pending_handoffs": handoffs}


def _on_demand_status(work_id: str, index_text: str) -> str:
    block = re.search(rf"###\s+{work_id}\b(?P<body>.*?)(?=^###\s+W\d{{2}}|\Z)", index_text, re.M | re.S)
    if not block:
        return "READY_FOR_TEST"
    status = _first_match(block.group("body"), r"Current status:\s*`?([^`\n]+)", default="READY_FOR_TEST")
    return status.removeprefix(f"{work_id}_")


def _sku_health(w00: str, w01: str, w02: str) -> list[dict[str, str]]:
    skus = [f"УФ 00{number}Б" for number in range(1, 6)]
    result = []
    for sku in skus:
        attention = "ATTENTION" if re.search(rf"\|\s*{re.escape(sku)}\s*\|\s*`?(HIGH|MEDIUM)", w00) else "WATCH"
        visibility = "UNKNOWN"
        found = re.search(rf"{re.escape(sku)}\s+found in\s+(\d+)/(\d+)", w01, re.I)
        if found:
            visibility = "OK" if int(found.group(1)) else "WEAK"
        seller = "WATCH" if re.search(rf"^\|[^\n]*{re.escape(sku)}[^\n]*\|\s*MULTIPLE_SELLERS\s*\|", w01, re.M) else "OK"
        customer = "UNKNOWN"
        if sku == "УФ 003Б" and "CONFLICTING_DATA" in w02:
            customer = "CONFLICT"
        elif sku == "УФ 001Б" and "CU 2358" in w02 and "CUK 2358" in w02:
            customer = "WATCH"
        advertising = "ATTENTION" if sku in {"УФ 002Б", "УФ 004Б"} and attention == "ATTENTION" else "UNKNOWN"
        finance = "ATTENTION" if sku == "УФ 002Б" and "financial validation" in w00.lower() else "UNKNOWN"
        result.append({
            "sku": sku,
            "market": "OK" if re.search(r"all five.*available|all five.*Продается", w00, re.I) else "UNKNOWN",
            "visibility": visibility,
            "seller_integrity": seller,
            "customer_compatibility": customer,
            "advertising": advertising,
            "finance": finance,
            "attention": attention,
        })
    return result


def build_operating_layer() -> dict[str, Any]:
    paths = {work_id: _latest_report_path(work_id) for work_id in WORK_METADATA}
    reports = {work_id: _read_text(path) for work_id, path in paths.items()}
    index_text = _read_text(OZON_AGENTS_ROOT / "INDEX.md")
    w00, w01, w02, w08, w06 = (reports[key] for key in ("W00", "W01", "W02", "W08", "W06"))
    report_date = _report_date(paths["W00"]) or max(
        (value for value in (_report_date(path) for path in paths.values()) if value),
        default=None,
    )
    works = []
    for work_id, metadata in WORK_METADATA.items():
        text = reports[work_id]
        if work_id in {"W04", "W05"} and not text:
            status = _on_demand_status(work_id, index_text)
        else:
            status = _work_status(work_id, text)
        works.append({
            "id": work_id,
            **metadata,
            "status": status,
            "last_run": _report_date(paths[work_id]) or "NOT AVAILABLE",
            "freshness": _work_freshness(work_id, text),
            **_work_metrics(work_id, text),
            "external_write": "NONE",
            "report_available": paths[work_id] is not None,
            "report_url": f"/work-report?work={work_id}" if paths[work_id] else None,
        })

    if _work_status("W00", w00) == "COMPLETED":
        for work in works:
            if work["mode"] != "ON DEMAND" and work["last_run"] != "NOT AVAILABLE":
                work["pending_handoffs"] = 0

    blockers = _blockers(w08)
    owner_attention = _owner_attention(w00)
    owner_decisions = _int_match(w00, r"Owner decisions required:\s*`?(\d+)")
    active_blockers = len(blockers) or _int_match(w08, r"Active financial blockers:\s*`?(\d+)") or 0
    advertising = {
        "active_cpc": _int_match(w00, r"Confirmed active CPC\s*\|\s*`?(\d+)") ,
        "archived_cpc": _int_match(w00, r"Archived CPC\s*\|\s*`?(\d+)") ,
        "spend": _first_match(w00, r"Completed-period spend\s*\|\s*`?([^|`]+)"),
        "campaign_sales": _first_match(w00, r"Campaign grain\s*\|\s*`?([^/|`]+)"),
        "campaign_drr": _first_match(w00, r"Campaign grain\s*\|\s*`?[^/|`]+/\s*DRR\s*([^|`]+)"),
        "product_sales": _first_match(w00, r"Product grain\s*\|\s*`?([^/|`]+)"),
        "product_drr": _first_match(w00, r"Product grain\s*\|\s*`?[^/|`]+/\s*DRR\s*([^|`]+)"),
        "attribution": _first_match(w00, r"Attribution\s*\|\s*`?([^|`]+)"),
        "cpo_state": _first_match(w00, r"CPO lifecycle\s*\|\s*`?([^|`]+)"),
    }
    financial = {
        "status": _work_status("W06", w06),
        "confirmed_numeric_bounds": _int_match(w06, r"Confirmed numeric (?:CPC/DRR/spend/bid )?bounds\s*\|\s*(\d+)", r"Confirmed numeric bounds:\s*`?(\d+)"),
        "unified_attributed_sales": _first_match(w06, r"Unified attributed sales confirmed\s*\|\s*`?([^|`]+)", r"Unified attributed sales:\s*`?([^`\n]+)"),
        "unified_drr": _first_match(w06, r"Unified DRR confirmed\s*\|\s*`?([^|`]+)", r"Unified DRR:\s*`?([^`\n]+)"),
        "revalidation": _first_match(w06, r"Input reconciliation status:\*{0,2}\s*`([^`]+)`"),
    }
    commercial = {
        "diagnosis": _first_match(w08, r"Commercial diagnosis status:\s*`([^`]+)`"),
        "sku_attention": _int_match(w08, r"SKU requiring commercial attention:\s*`?(\d+)"),
        "cpc_restart": _first_match(w08, r"\|\s*CPC restart supported now\s*\|\s*`?([^|`]+)"),
        "controlled_test": _first_match(w08, r"\|\s*Controlled commercial test warranted\s*\|\s*`?([^|`]+)"),
        "proposals": _int_match(w08, r"Commercial test proposals:\s*`?(\d+)"),
        "financial_validation_required": _first_match(w08, r"W06 re-validation required:\s*`?([^`—\n]+)"),
        "owner_decision": "YES" if (owner_decisions or 0) > 0 else "NO",
    }
    report_items = []
    for work_id in ("W00", "W07", "W08", "W06", "W03", "W02", "W01"):
        path = paths[work_id]
        if path:
            report_items.append({
                "work": work_id,
                "name": path.name,
                "date": _report_date(path),
                "url": f"/work-report?work={work_id}",
            })
    return {
        "available": bool(w00),
        "report_date": report_date or "NOT AVAILABLE",
        "global": {
            "daily_cycle": _work_status("W00", w00),
            "audit": _first_match(w00, r"Audit outcome\s*\|\s*`?([^|`]+)"),
            "owner_decisions_required": owner_decisions if owner_decisions is not None else 0,
            "owner_attention_count": len(owner_attention),
            "active_blockers_count": active_blockers,
            "execution_plane": "NOT READY",
            "external_write": "DISABLED",
        },
        "owner_attention": owner_attention,
        "blockers": blockers,
        "works": works,
        "commercial": commercial,
        "advertising": advertising,
        "financial": financial,
        "sku_health": _sku_health(w00, w01, w02),
        "daily_flow": {
            "primary": ["W01", "W02", "W03", "W08", "W06", "W07", "W00"],
            "on_demand": ["W04", "W05"],
            "pending_handoffs": [],
        },
        "reports": report_items,
        "sources": ["INDEX.md", "PROJECT_MAP.md", "latest W00–W08 reports"],
    }


def build_legacy_status() -> dict[str, Any]:
    """Retained legacy diagnostics, never part of the active W00–W08 status path."""
    now = datetime.now(UTC)
    report, _ = report_snapshot(REPORT_PATH)
    try:
        cron_text = CRON_PATH.read_text(encoding="utf-8")
    except OSError:
        cron_text = ""
    next_run, schedule_label = parse_cron_schedule(cron_text, now)
    next_delivery, delivery_schedule_label = parse_cron_schedule(cron_text, now, "efa-ai-analyst-email.lock")
    delivery_config = delivery_configuration(DELIVERY_WORKFLOW_PATH, OLD_BRIEF_WORKFLOW_PATH)
    postgres_online, db_row = asyncio.run(read_database())
    collectors, latest_data = collector_snapshot(db_row, now) if postgres_online else ([], None)
    return {
        "generated_at": _fmt_dt(now),
        "system": {
            "postgresql": postgres_online,
            "n8n": _tcp_online(N8N_HOST, N8N_PORT),
            "mcp": _tcp_online(MCP_HOST, MCP_PORT),
            "collectors_ok": bool(collectors) and all(item["ok"] for item in collectors),
        },
        "collectors": collectors,
        "last_data_update": _fmt_dt(latest_data),
        # Source-row timestamps do not prove completion of a collector run.
        "last_successful_collection": None,
        "analyst": {
            "last": report.get("modified", "Нет данных"),
            "next": _fmt_dt(next_run),
            "schedule": schedule_label,
        },
        "delivery": {
            "last": delivery_confirmation(DELIVERY_LOG_PATH),
            "next": _fmt_dt(next_delivery),
            "schedule": delivery_schedule_label,
            **delivery_config,
        },
        "attention": report,
        "competitor_monitor": load_competitor_summary(),
        "operating_layer": build_operating_layer(),
        "control_center": read_model.build(OZON_AGENTS_ROOT, WORK_METADATA, now),
    }


def build_status() -> dict[str, Any]:
    now = datetime.now(UTC)
    model = read_model.build(OZON_AGENTS_ROOT, WORK_METADATA, now)
    finance_check = model['finance']['snapshots']['CURRENT_MONTH']['provider_check']
    # Required local visibility sources only. No legacy DB query or n8n health probe.
    return {
        'generated_at': _fmt_dt(now),
        'system': {'w06_snapshot': finance_check['status'],
                   'reports': 'AVAILABLE' if any(w['last_run'] for w in model['works']) else 'NO_DATA'},
        'finance_provider': finance_check,
        'optional_sources': {
            'postgresql': {'classification': 'LEGACY_OPTIONAL', 'status': 'NOT_PROBED',
                           'required_for_control_center': False},
            'mcp': {'classification': 'LEGACY_OPTIONAL', 'status': 'NOT_PROBED',
                    'required_for_control_center': False},
        },
        'legacy_systems': {'classification': 'LEGACY_UNUSED',
                          'components': ['n8n', 'OPFINDAILYV1', 'old Daily Brief', 'collector statuses']},
        # Old API keys remain inert for compatibility; no legacy reads or alerts.
        'collectors': [], 'last_data_update': None, 'last_successful_collection': None,
        'analyst': {'last': None, 'next': None, 'schedule': 'LEGACY_UNUSED'},
        'delivery': {'last': {'label': 'LEGACY_UNUSED'}, 'next': None, 'schedule': 'LEGACY_UNUSED'},
        'attention': {},
        'control_center': model,
    }


def _daily_report_lines(report: str) -> list[dict[str, str]]:
    intro = report.split("Данные продаж:", 1)[0]
    pattern = re.compile(r"^### (?P<signal>[^·\n]+) · (?P<sku>.+?)\n(?P<body>.*?)(?=^### |\Z)", re.M | re.S)
    rows = []
    for match in pattern.finditer(intro):
        body = match.group("body")
        values = {}
        for label in ("Продажи", "Цена", "Остаток", "Логистика", "Акции/CPC", "Почему"):
            found = re.search(rf"^- {re.escape(label)}: (.+)$", body, re.M)
            values[label] = found.group(1).replace("**", "").replace("`", "") if found else "Нет данных"
        rows.append({"sku": match.group("sku").strip(), "signal": match.group("signal").strip(), **values})
    return rows


def _compact_money(value: int | None) -> str:
    return "н/д" if value is None else f"{value:,} ₽".replace(",", " ")


def _detail_items(items: Sequence[Mapping[str, Any]]) -> str:
    seen: set[str] = set()
    rows = []
    for item in items:
        key = str(item.get("finding_key", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        role = html.escape(str(item.get("role_label") or "Событие"))
        message = html.escape(str(item.get("message") or "Нет описания"))
        rows.append(f"<li><b>{role}</b><p>{message}</p></li>")
    return "".join(rows) or "<li class='muted'>Нет событий.</li>"


def _unique_findings(
    items: Sequence[Mapping[str, Any]], seen: set[str]
) -> list[Mapping[str, Any]]:
    result = []
    for item in items:
        key = str(item.get("finding_key", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _price_items(items: Sequence[Mapping[str, Any]]) -> str:
    rows = []
    seen: set[str] = set()
    for item in items:
        key = str(item.get("finding_key", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        offer_id = html.escape(str(item.get("offer_id") or "SKU"))
        role = html.escape(str(item.get("role_label") or "Конкурент"))
        previous = html.escape(str(item.get("previous_price") if item.get("previous_price") is not None else "н/д"))
        current = html.escape(str(item.get("current_price") if item.get("current_price") is not None else "н/д"))
        delta = html.escape(str(item.get("delta") if item.get("delta") is not None else "н/д"))
        delta_pct = item.get("delta_pct")
        pct = "н/д" if delta_pct is None else f"{float(delta_pct):+.1f}%"
        rows.append(
            f"<li><b>{offer_id} — {role}</b>"
            f"<p>{previous} → {current} ₽; изменение {delta} ₽ ({html.escape(pct)}).</p></li>"
        )
    return "".join(rows) or "<li class='muted'>Нет изменений цен.</li>"


def render_competitor_detail(summary: Mapping[str, Any]) -> str:
    if not summary.get("available"):
        content = "<p class='module-unavailable'>Данные мониторинга сейчас недоступны.</p>"
    elif (summary.get("counts") or {}).get("total_findings") == 0:
        content = "<p>Изменений, соответствующих правилам Finding Engine v1, не обнаружено.</p>"
    else:
        used: set[str] = set()
        own = _unique_findings((summary.get("own") or {}).get("own_findings") or [], used)
        competitors = _unique_findings(
            (summary.get("competitors") or {}).get("findings") or [], used
        )
        prices = _unique_findings((summary.get("prices") or {}).get("price_changes") or [], used)
        other = _unique_findings(summary.get("top_findings") or [], used)
        reference = html.escape(str((summary.get("snapshot") or {}).get("reference_at") or "Нет данных"))
        content = (
            f"<p class='detail-snapshot'>Последний снимок: {reference}</p>"
            "<section class='detail-section'><h2>Наша карточка</h2><ul>" + _detail_items(own) + "</ul></section>"
            "<section class='detail-section'><h2>Видимость конкурентов</h2><ul>" + _detail_items(competitors) + "</ul></section>"
            "<section class='detail-section'><h2>Изменения цен</h2><ul>" + _price_items(prices) + "</ul></section>"
            "<section class='detail-section'><h2>Прочие информационные события</h2><ul>" + _detail_items(other) + "</ul></section>"
        )
    return f"""<!doctype html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Конкуренты — EFA OS</title><link rel='stylesheet' href='/static/styles.css'></head><body>
<main class='detail-wrap'><a class='back' href='/'>← Control Center</a><h1>Конкуренты</h1>{content}</main></body></html>"""


def render_detail(kind: str, report: str) -> str:
    titles = {
        "prices": "Цены и акции",
        "stocks": "Остатки",
        "cpc": "CPC",
        "collectors": "Статус collectors",
        "report": "Последний отчёт Analyst",
        "competitors": "Конкуренты",
    }
    title = titles.get(kind, "Control Center")
    if kind == "competitors":
        content = render_competitor_detail(load_competitor_summary())
        return content
    if kind == "report":
        content = f"<pre class='report'>{html.escape(report or 'Отчёт недоступен')}</pre>"
    elif kind == "collectors":
        items = build_status()["collectors"]
        rows = "".join(
            f"<tr><td>{html.escape(item['name'])}</td><td><span class='state {'ok' if item['ok'] else 'bad'}'>{html.escape(item['status'])}</span></td>"
            f"<td>{html.escape(item['updated'])}</td><td>{html.escape(item['details'])}</td></tr>" for item in items
        )
        content = f"<table><thead><tr><th>Источник</th><th>Статус</th><th>Обновлён</th><th>Подтверждение</th></tr></thead><tbody>{rows}</tbody></table>"
    elif kind == "prices":
        try:
            _, skus, _ = parse_report(report)
        except (ValueError, TypeError):
            skus = []
        body = "".join(
            "<tr><td><b>" + html.escape(sku.name) + "</b><br><small>" + html.escape(sku.signal) + "</small></td>"
            f"<td><b>{_compact_money(sku.price)} → {_compact_money(sku.recommended_price)}</b>"
            f"<br><small>фактическая продажа: {_compact_money(sku.factual_price)}</small></td>"
            f"<td><b>{html.escape(sku.price_action)}</b></td>"
            f"<td><b>{html.escape(sku.pbt)}</b><br><small>{html.escape(sku.profit_per_unit)} / {html.escape(sku.margin)}</small></td>"
            f"<td>{html.escape(sku.confidence)}</td>"
            f"<td>{html.escape(sku.promo_action)}</td>"
            f"<td><small>{html.escape(sku.reason)}</small></td></tr>"
            for sku in skus
        )
        content = (
            "<table><thead><tr><th>SKU</th><th>Текущая → тестовая</th><th>Решение</th>"
            "<th>PBT / прибыль/шт. / маржа</th><th>Уверенность</th><th>Акция</th><th>Почему</th></tr></thead>"
            f"<tbody>{body}</tbody></table>"
        )
    else:
        rows = _daily_report_lines(report)
        if kind == "stocks":
            columns = (("Остаток", "Остаток"),)
        else:
            columns = (("Акции/CPC", "CPC"),)
        head = "".join(f"<th>{label}</th>" for _, label in columns)
        body = "".join(
            "<tr><td><b>" + html.escape(row["sku"]) + "</b><br><small>" + html.escape(row["signal"]) + "</small></td>" +
            "".join(f"<td>{html.escape(row[key])}</td>" for key, _ in columns) + "</tr>" for row in rows
        )
        content = f"<table><thead><tr><th>SKU</th>{head}</tr></thead><tbody>{body}</tbody></table>"
    return f"""<!doctype html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(title)} — EFA OS</title><link rel='stylesheet' href='/static/styles.css'></head><body>
<main class='detail-wrap'><a class='back' href='/'>← Control Center</a><h1>{html.escape(title)}</h1>{content}</main></body></html>"""


def render_work_report(work_id: str, filename: str, report: str) -> str:
    metadata = WORK_METADATA.get(work_id, {"name": "Source evidence"})
    title = f"{work_id} — {metadata['name']}"
    return f"""<!doctype html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(title)} — EFA OS</title><link rel='stylesheet' href='/static/styles.css'></head><body>
<main class='detail-wrap'><a class='back' href='/'>← Control Center</a><p class='detail-snapshot'>{html.escape(filename)}</p><h1>{html.escape(title)}</h1><pre class='report'>{html.escape(report)}</pre></main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "EFA-Control-Center/1.0"

    def do_GET(self) -> None:  # noqa: N802
        request = urlsplit(self.path)
        path = request.path
        if path == "/":
            self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/capabilities":
            self._file(STATIC_DIR / "capabilities.html", "text/html; charset=utf-8")
        elif path == "/api/status":
            self._json(build_status())
        elif path == "/api/finance":
            params = parse_qs(request.query, keep_blank_values=True)
            period = params.get('period', ['CURRENT_MONTH'])[0]
            period = current_finance.PRESETS.get(period, period)
            if set(params) - {'period'} or len(params.get('period', [])) > 1:
                self._json({'error': 'INVALID_FINANCE_PERIOD'}, HTTPStatus.BAD_REQUEST)
                return
            try:
                self._json(current_finance.get_snapshot(OZON_AGENTS_ROOT, period))
            except ValueError:
                self._json({'error': 'INVALID_FINANCE_PERIOD'}, HTTPStatus.BAD_REQUEST)
        elif path == "/healthz":
            self._json({"status": "ok", "service": "efa-control-center"})
        elif path.startswith("/static/") and path.removeprefix("/static/") in {
            "styles.css", "app.js", "capabilities.js", "capabilities.json",
        }:
            name = path.removeprefix("/static/")
            content_types = {
                ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".json": "application/json; charset=utf-8",
            }
            content_type = content_types[Path(name).suffix]
            self._file(STATIC_DIR / name, content_type)
        elif path in {"/report", "/prices", "/stocks", "/cpc", "/collectors", "/competitors"}:
            _, report = report_snapshot(REPORT_PATH)
            body = render_detail(path.lstrip("/"), report).encode("utf-8")
            self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
        elif path == "/work-report":
            work_id = parse_qs(request.query).get("work", [""])[0].upper()
            report_path = _latest_report_path(work_id) if work_id in WORK_METADATA else None
            report = _read_text(report_path)
            if not report_path or not report:
                self._json({"error": "report_unavailable"}, HTTPStatus.NOT_FOUND)
                return
            body = render_work_report(work_id, report_path.name, report).encode("utf-8")
            self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
        elif path == "/agent-source":
            source = parse_qs(request.query).get("path", [""])[0]
            root = OZON_AGENTS_ROOT.resolve()
            source_root = (root.parent / "REPORTS").resolve() if source.startswith("repository-reports/") else root
            relative = source.removeprefix("repository-reports/") if source.startswith("repository-reports/") else source
            candidate = (source_root / relative).resolve()
            # Only reports/governance exposed by the projection, never arbitrary files.
            allowed = set(read_model.build(root, WORK_METADATA)["sources"])
            snapshot_json = (candidate.suffix == '.json' and
                             candidate.is_relative_to((root / 'REPORTS/W06/SNAPSHOTS').resolve()))
            if source not in allowed or not candidate.is_relative_to(source_root) or (candidate.suffix != ".md" and not snapshot_json):
                self._json({"error": "source_unavailable"}, HTTPStatus.NOT_FOUND)
                return
            if snapshot_json:
                self._file(candidate, 'application/json; charset=utf-8')
                return
            body = render_work_report("SOURCE", candidate.name, _read_text(candidate)).encode("utf-8")
            self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
        elif path == "/n8n":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", N8N_URL)
            self.end_headers()
        else:
            self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def _file(self, path: Path, content_type: str) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._json({"error": "unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        self._send(HTTPStatus.OK, body, content_type)

    def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"control-center {self.address_string()} {fmt % args}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="EFA OS Control Center v1")
    parser.add_argument("--host", default=os.environ.get("EFA_CONTROL_CENTER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("EFA_CONTROL_CENTER_PORT", "8090")))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"EFA Control Center listening on {args.host}:{args.port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
