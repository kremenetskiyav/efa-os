#!/usr/bin/env python3
"""Shared Competitor Monitor presentation for Analyst, Email and Telegram."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

if __package__:
    from .build_competitor_monitor_summary_v1 import (
        CONTRACT_VERSION,
        COVERAGE_SQL,
        FINDINGS_SQL,
        LATEST_FINDING_SET_SQL,
        SourceData,
        build_summary,
    )
else:
    from build_competitor_monitor_summary_v1 import (
        CONTRACT_VERSION,
        COVERAGE_SQL,
        FINDINGS_SQL,
        LATEST_FINDING_SET_SQL,
        SourceData,
        build_summary,
    )


SECTION_HEADING = "## КОНКУРЕНТЫ"
SECTION_MARKER = "<!-- competitor-report.v1 -->"
UNAVAILABLE_TEXT = "Данные мониторинга текущего цикла недоступны."
ZERO_FINDINGS_TEXT = (
    "Изменений, соответствующих правилам Finding Engine v1, не обнаружено."
)
MOSCOW = timezone(timedelta(hours=3), name="Europe/Moscow")
FORBIDDEN_VISIBILITY_WORDING = (
    "карточка пропала",
    "товар исчез",
    "товар удалён",
    "конкурент ушёл с ozon",
    "продажи остановлены",
)
SUMMARY_SELECT_COUNT = 3


@dataclass(frozen=True)
class CompetitorPresentation:
    available: bool
    status: str | None = None
    snapshot_label: str | None = None
    freshness_status: str | None = None
    portfolio_sku_count: int = 0
    active_monitored_sku_count: int = 0
    important_count: int = 0
    watch_count: int = 0
    info_count: int = 0
    total_findings: int = 0
    priority_items: tuple[tuple[str, str], ...] = ()
    own_restoration: str | None = None
    competitor_lost_count: int = 0
    competitor_restored_count: int = 0
    price_event: str | None = None

    @property
    def zero_findings(self) -> bool:
        return self.available and self.status == "NORMAL" and self.total_findings == 0


def unavailable_presentation() -> CompetitorPresentation:
    return CompetitorPresentation(available=False)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_text(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if any(phrase in text.casefold() for phrase in FORBIDDEN_VISIBILITY_WORDING):
        return "Событие видимости требует проверки в пределах лимита текущего снимка."
    return text


def _snapshot_label(value: Any) -> str | None:
    if not value:
        return None
    try:
        observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return observed.astimezone(MOSCOW).strftime("%d.%m.%Y %H:%M МСК")


def _number(value: Any, *, signed: bool = False, digits: int | None = None) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return "н/д"
    if digits is None:
        rendered = format(number.normalize(), "f")
    else:
        rendered = f"{number:.{digits}f}"
    if signed and number > 0:
        return "+" + rendered
    return rendered


def _price_event(item: Mapping[str, Any] | None) -> str | None:
    if not item:
        return None
    offer_id = _safe_text(item.get("offer_id")) or "SKU"
    role = _safe_text(item.get("role_label")) or "Конкурент"
    previous = _number(item.get("previous_price"))
    current = _number(item.get("current_price"))
    delta = _number(item.get("delta"), signed=True)
    delta_pct = _number(item.get("delta_pct"), signed=True, digits=1)
    return (
        f"{offer_id} · {role.lower()}: {previous} → {current} ₽ "
        f"({delta} ₽; {delta_pct}%)."
    )


def build_presentation(summary: Mapping[str, Any] | None) -> CompetitorPresentation:
    if (
        not isinstance(summary, Mapping)
        or summary.get("contract_version") != CONTRACT_VERSION
        or summary.get("available") is not True
    ):
        return unavailable_presentation()

    counts = summary.get("counts") if isinstance(summary.get("counts"), Mapping) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), Mapping) else {}
    competitors = (
        summary.get("competitors") if isinstance(summary.get("competitors"), Mapping) else {}
    )
    own = summary.get("own") if isinstance(summary.get("own"), Mapping) else {}
    prices = summary.get("prices") if isinstance(summary.get("prices"), Mapping) else {}
    snapshot = summary.get("snapshot") if isinstance(summary.get("snapshot"), Mapping) else {}

    priority: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in summary.get("top_findings") or []:
        if not isinstance(item, Mapping) or item.get("severity") not in {"IMPORTANT", "WATCH"}:
            continue
        key = str(item.get("finding_key") or "")
        message = _safe_text(item.get("message"))
        if not key or not message or key in seen:
            continue
        seen.add(key)
        priority.append((str(item["severity"]), message))

    own_restoration = None
    for item in own.get("own_findings") or []:
        if (
            isinstance(item, Mapping)
            and item.get("finding_type") == "OWN_SEARCH_VISIBILITY_RESTORED"
            and item.get("severity") == "INFO"
        ):
            own_restoration = _safe_text(item.get("message")) or None
            if own_restoration:
                break

    price_changes = [item for item in prices.get("price_changes") or [] if isinstance(item, Mapping)]
    return CompetitorPresentation(
        available=True,
        status=_safe_text(summary.get("status")) or None,
        snapshot_label=_snapshot_label(snapshot.get("reference_at")),
        freshness_status=_safe_text(snapshot.get("freshness_status")) or None,
        portfolio_sku_count=_safe_int(coverage.get("portfolio_sku_count")),
        active_monitored_sku_count=_safe_int(coverage.get("active_monitored_sku_count")),
        important_count=_safe_int(counts.get("important_count")),
        watch_count=_safe_int(counts.get("watch_count")),
        info_count=_safe_int(counts.get("info_count")),
        total_findings=_safe_int(counts.get("total_findings")),
        priority_items=tuple(priority),
        own_restoration=own_restoration,
        competitor_lost_count=_safe_int(competitors.get("visibility_lost_count")),
        competitor_restored_count=_safe_int(competitors.get("visibility_restored_count")),
        price_event=_price_event(price_changes[0] if price_changes else None),
    )


def render_source_section(presentation: CompetitorPresentation) -> str:
    lines = [SECTION_HEADING, "", SECTION_MARKER]
    if not presentation.available:
        lines.extend(["- Доступность: **НЕТ**", f"- Итог: {UNAVAILABLE_TEXT}"])
        return "\n".join(lines)

    lines.extend(
        [
            "- Доступность: **ДА**",
            f"- Статус: **{presentation.status or 'UNKNOWN'}**",
            f"- Снимок: **{presentation.snapshot_label or 'н/д'}**",
            f"- Свежесть: **{presentation.freshness_status or 'UNKNOWN'}**",
            f"- Мониторинг: **{presentation.active_monitored_sku_count} из {presentation.portfolio_sku_count} SKU**",
            "- События: **IMPORTANT "
            f"{presentation.important_count} · WATCH {presentation.watch_count} · "
            f"INFO {presentation.info_count} · TOTAL {presentation.total_findings}**",
        ]
    )
    if presentation.zero_findings:
        lines.append(f"- Итог: {ZERO_FINDINGS_TEXT}")
        return "\n".join(lines)
    for severity, message in presentation.priority_items:
        lines.append(f"- Приоритет {severity}: {message}")
    if presentation.own_restoration:
        lines.append(f"- Наша карточка INFO: {presentation.own_restoration}")
    lines.append(
        f"- Конкуренты: **−{presentation.competitor_lost_count} / +{presentation.competitor_restored_count}**"
    )
    if presentation.price_event:
        lines.append(f"- Цена INFO: {presentation.price_event}")
    return "\n".join(lines)


def parse_source_section(report: str) -> CompetitorPresentation:
    match = re.search(r"^## КОНКУРЕНТЫ\n(.*?)(?=^## |\Z)", report, re.M | re.S)
    if not match or SECTION_MARKER not in match.group(0):
        return unavailable_presentation()
    body = match.group(1)
    if "- Доступность: **ДА**" not in body:
        return unavailable_presentation()

    def field(pattern: str) -> str | None:
        found = re.search(pattern, body, re.M)
        return found.group(1).strip() if found else None

    status = field(r"^- Статус: \*\*(.+?)\*\*$")
    snapshot = field(r"^- Снимок: \*\*(.+?)\*\*$")
    freshness = field(r"^- Свежесть: \*\*(.+?)\*\*$")
    coverage = re.search(r"^- Мониторинг: \*\*(\d+) из (\d+) SKU\*\*$", body, re.M)
    counts = re.search(
        r"^- События: \*\*IMPORTANT (\d+) · WATCH (\d+) · INFO (\d+) · TOTAL (\d+)\*\*$",
        body,
        re.M,
    )
    competitors = re.search(r"^- Конкуренты: \*\*−(\d+) / \+(\d+)\*\*$", body, re.M)
    if not status or not coverage or not counts:
        return unavailable_presentation()
    priority = tuple(
        (severity, _safe_text(message))
        for severity, message in re.findall(
            r"^- Приоритет (IMPORTANT|WATCH): (.+)$", body, re.M
        )
    )
    own_restoration = field(r"^- Наша карточка INFO: (.+)$")
    price_event = field(r"^- Цена INFO: (.+)$")
    return CompetitorPresentation(
        available=True,
        status=status,
        snapshot_label=None if snapshot == "н/д" else snapshot,
        freshness_status=freshness,
        portfolio_sku_count=int(coverage.group(2)),
        active_monitored_sku_count=int(coverage.group(1)),
        important_count=int(counts.group(1)),
        watch_count=int(counts.group(2)),
        info_count=int(counts.group(3)),
        total_findings=int(counts.group(4)),
        priority_items=priority,
        own_restoration=own_restoration,
        competitor_lost_count=int(competitors.group(1)) if competitors else 0,
        competitor_restored_count=int(competitors.group(2)) if competitors else 0,
        price_event=price_event,
    )


def _freshness_text(presentation: CompetitorPresentation) -> str:
    if presentation.freshness_status == "UNKNOWN":
        return "Свежесть: не определена."
    if presentation.freshness_status == "STALE":
        return "Свежесть: снимок устарел."
    return f"Свежесть: {presentation.freshness_status or 'н/д'}."


def _short_snapshot(label: str | None) -> str:
    if not label:
        return "н/д"
    match = re.match(r"(\d{2}\.\d{2})\.\d{4} (\d{2}:\d{2} МСК)", label)
    return f"{match.group(1)} {match.group(2)}" if match else label


def render_email_html(presentation: CompetitorPresentation) -> str:
    if not presentation.available:
        return f"<h2>КОНКУРЕНТЫ</h2><p>{html.escape(UNAVAILABLE_TEXT)}</p>"
    heading = f"КОНКУРЕНТЫ · снимок {_short_snapshot(presentation.snapshot_label)}"
    if presentation.zero_findings:
        return f"<h2>{html.escape(heading)}</h2><p>{html.escape(ZERO_FINDINGS_TEXT)}</p>"
    rows = [f"<p>{html.escape(_freshness_text(presentation))}</p>"]
    labels = {"IMPORTANT": "Важно", "WATCH": "Наблюдать"}
    rows.extend(
        f"<p><b>{labels.get(severity, severity)}</b> — {html.escape(message)}</p>"
        for severity, message in presentation.priority_items
    )
    if presentation.own_restoration:
        rows.append(
            f"<p><b>Наша карточка:</b> {html.escape(presentation.own_restoration)}</p>"
        )
    rows.append(
        "<p><b>Мониторинг:</b> "
        f"{presentation.active_monitored_sku_count} из {presentation.portfolio_sku_count} SKU · "
        f"<b>Конкуренты:</b> −{presentation.competitor_lost_count} / +{presentation.competitor_restored_count}</p>"
    )
    if presentation.price_event:
        rows.append(f"<p><b>Цена:</b> {html.escape(presentation.price_event)}</p>")
    rows.append(
        "<p>IMPORTANT "
        f"{presentation.important_count} · WATCH {presentation.watch_count} · "
        f"INFO {presentation.info_count}</p>"
    )
    return f"<h2>{html.escape(heading)}</h2>" + "".join(rows)


def render_telegram_text(presentation: CompetitorPresentation) -> str:
    if not presentation.available:
        return f"КОНКУРЕНТЫ\n{UNAVAILABLE_TEXT}"
    heading = f"КОНКУРЕНТЫ · снимок {_short_snapshot(presentation.snapshot_label)}"
    if presentation.zero_findings:
        return f"{heading}\n{ZERO_FINDINGS_TEXT}"
    labels = {"IMPORTANT": "Важно", "WATCH": "Наблюдать"}
    lines = [heading, _freshness_text(presentation)]
    lines.extend(
        f"{labels.get(severity, severity)}: {message}"
        for severity, message in presentation.priority_items
    )
    lines.append(
        f"Конкуренты: −{presentation.competitor_lost_count} / +{presentation.competitor_restored_count}."
    )
    if presentation.price_event:
        lines.append(f"Цена: {presentation.price_event}")
    return "\n".join(lines)


def _asyncpg_sql(sql: str) -> str:
    return sql.replace("%s::uuid", "$1::uuid")


def _decode_record(record: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(record)
    for field in ("evidence", "details"):
        value = result.get(field)
        if isinstance(value, str):
            result[field] = json.loads(value)
    return result


async def read_summary(connection: Any) -> Mapping[str, Any]:
    """Read the persisted Summary once; isolate failures behind a savepoint."""
    try:
        async with connection.transaction():
            manifest_row = await connection.fetchrow(LATEST_FINDING_SET_SQL)
            manifest = _decode_record(manifest_row) if manifest_row is not None else None
            findings = (
                tuple(
                    _decode_record(row)
                    for row in await connection.fetch(
                        _asyncpg_sql(FINDINGS_SQL), manifest["finding_set_id"]
                    )
                )
                if manifest is not None
                else ()
            )
            coverage = tuple(
                _decode_record(row) for row in await connection.fetch(COVERAGE_SQL)
            )
        return build_summary(
            SourceData(manifest, findings, coverage),
            max_findings=max(1, len(findings)),
        )
    except Exception:
        return {"contract_version": CONTRACT_VERSION, "available": False}
