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
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.format_ai_analyst_email import parse_report  # noqa: E402


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


COLLECTOR_QUERY = """
SELECT
  (SELECT max(business_date) FROM mcp_read.product_daily_performance) AS demand_date,
  (SELECT array_remove(array_agg(DISTINCT demand_quality_status), NULL)
     FROM mcp_read.product_daily_performance
    WHERE business_date = (SELECT max(business_date) FROM mcp_read.product_daily_performance)) AS demand_statuses,
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
    import asyncpg

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


def collector_snapshot(row: dict[str, Any], now: datetime) -> tuple[list[dict[str, Any]], datetime | date | None]:
    definitions = [
        ("Спрос", row.get("demand_date"), row.get("demand_statuses")),
        ("Цены", row.get("price_at"), ["OK"] if row.get("price_at") else []),
        ("Остатки", row.get("stock_at"), row.get("stock_statuses")),
        ("Акции", row.get("promotion_at"), row.get("promotion_statuses")),
        ("CPC", row.get("cpc_at") or row.get("cpc_date"), row.get("cpc_statuses")),
        ("Operational finance", row.get("operations_date"), row.get("operations_statuses")),
    ]
    result = []
    observed_values = []
    for name, observed, statuses in definitions:
        ok = _age_ok(observed, now) and _statuses_ok(list(statuses or []))
        result.append({
            "name": name,
            "ok": ok,
            "status": "OK" if ok else "Проблема",
            "updated": _fmt_dt(observed),
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


def build_status() -> dict[str, Any]:
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


def render_detail(kind: str, report: str) -> str:
    titles = {
        "prices": "Цены и акции",
        "stocks": "Остатки",
        "cpc": "CPC",
        "collectors": "Статус collectors",
        "report": "Последний отчёт Analyst",
    }
    title = titles.get(kind, "Control Center")
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


class Handler(BaseHTTPRequestHandler):
    server_version = "EFA-Control-Center/1.0"

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/":
            self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/api/status":
            self._json(build_status())
        elif path == "/healthz":
            self._json({"status": "ok", "service": "efa-control-center"})
        elif path.startswith("/static/") and path.removeprefix("/static/") in {"styles.css", "app.js"}:
            name = path.removeprefix("/static/")
            content_type = "text/css; charset=utf-8" if name.endswith(".css") else "text/javascript; charset=utf-8"
            self._file(STATIC_DIR / name, content_type)
        elif path in {"/report", "/prices", "/stocks", "/cpc", "/collectors"}:
            _, report = report_snapshot(REPORT_PATH)
            body = render_detail(path.lstrip("/"), report).encode("utf-8")
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
