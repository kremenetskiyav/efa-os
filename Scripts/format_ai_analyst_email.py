#!/usr/bin/env python3
"""Render the verbose AI Analyst report as a compact email payload."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


MISSING = "НЕДОСТАТОЧНО ДАННЫХ"


@dataclass
class Sku:
    name: str
    signal: str
    sales: int
    revenue: int
    price: int
    stock: int
    price_action: str = "ОСТАВИТЬ"
    promo_action: str = "НЕДОСТАТОЧНО ДАННЫХ"
    reason: str = "Недостаточно данных для изменения."


def _number(value: str) -> int:
    return int(re.sub(r"\D", "", value))


def _blocks(report: str, heading: str) -> list[tuple[str, str]]:
    pattern = re.compile(rf"^### (.+?)\n(.*?)(?=^### |^## |\Z)", re.M | re.S)
    section = report.split(heading, 1)[1] if heading in report else ""
    return [(title.strip(), body) for title, body in pattern.findall(section)]


def _short_reason(raw: str) -> str:
    raw = raw.replace("`", "").strip()
    for prefix in ("Цена: ", "Акции: "):
        raw = raw.replace(prefix, "")
    first = re.split(r"(?<=[.!?])\s+", raw)[0].strip()
    return first[:160].rstrip(".; ") + "."


def _price_action(raw: str) -> str:
    upper = raw.upper()
    if "ПОДНЯ" in upper:
        return "ПОДНЯТЬ"
    if "СНИЗ" in upper:
        return "СНИЗИТЬ"
    if "ПРОВЕР" in upper:
        return "ПРОВЕРИТЬ"
    return "ОСТАВИТЬ"


def _promo_action(raw: str) -> str:
    upper = raw.upper()
    if "НЕ ТРОГАТЬ" in upper or "ОСТАВ" in upper:
        return "ОСТАВИТЬ"
    if "НЕ ВХОД" in upper:
        return "НЕ ВХОДИТЬ"
    if "ВЫЙ" in upper:
        return "ВЫЙТИ"
    return "НЕДОСТАТОЧНО ДАННЫХ"


def parse_report(report: str) -> tuple[str, list[Sku], str]:
    date_match = re.search(r"^## Сегодня: (\d{4}-\d{2}-\d{2})", report, re.M)
    report_date = date_match.group(1) if date_match else "н/д"

    daily: list[Sku] = []
    daily_pattern = re.compile(
        r"^### (?P<signal>[^·\n]+) · (?P<name>.+?)\n"
        r".*?Продажи: вчера \*\*(?P<sales>[\d ]+) шт\. / (?P<revenue>[\d ]+) ₽\*\*"
        r".*?Цена: \*\*(?P<price>[\d ]+) ₽\*\*"
        r".*?Остаток: \*\*(?P<stock>[\d ]+) шт\.\*\*"
        r".*?Почему: (?P<reason>.+?)$",
        re.M | re.S,
    )
    intro = report.split("Данные продаж:", 1)[0]
    for match in daily_pattern.finditer(intro):
        daily.append(
            Sku(
                name=match.group("name").strip(),
                signal=match.group("signal").strip(),
                sales=_number(match.group("sales")),
                revenue=_number(match.group("revenue")),
                price=_number(match.group("price")),
                stock=_number(match.group("stock")),
                reason=_short_reason(match.group("reason")),
            )
        )

    details = {title.split(" · ", 1)[0]: body for title, body in _blocks(report, "## SKU:")}
    for sku in daily:
        body = details.get(sku.name, "")
        price = re.search(r"Рекомендация по цене: \*\*(.+?)\*\*", body)
        promo = re.search(r"Рекомендация по акции: \*\*(.+?)\*\*", body)
        reason = re.search(r"- Причина: (.+)", body)
        if price:
            sku.price_action = _price_action(price.group(1))
        if promo:
            sku.promo_action = _promo_action(promo.group(1))
        if reason:
            sku.reason = _short_reason(reason.group(1))

    freshness_match = re.search(
        r"Данные продаж: \*\*(.+?)\*\*; сравнение: \*\*(.+?)\*\*", report
    )
    freshness = f"Спрос: {freshness_match.group(1)}" if freshness_match else "Спрос: свежесть н/д"
    snapshot_dates = re.findall(r"Цена: \*\*[\d ]+ ₽\*\* \((\d{4}-\d{2}-\d{2})\)", intro)
    if snapshot_dates:
        freshness += f" · цены и остатки: {max(snapshot_dates)}"
    return report_date, daily, freshness


def render(report: str) -> dict[str, str]:
    report_date, skus, freshness = parse_report(report)
    total_sales = sum(s.sales for s in skus)
    total_revenue = sum(s.revenue for s in skus)
    attention = sum("ПРОВЕРИТЬ СЕЙЧАС" in s.signal for s in skus)
    watch = sum("НАБЛЮДАТЬ" in s.signal for s in skus)
    leave = sum("НЕ ТРОГАТЬ" in s.signal for s in skus)

    actions = [
        s for s in skus
        if "ПРОВЕРИТЬ СЕЙЧАС" in s.signal
        or s.price_action != "ОСТАВИТЬ"
        or s.promo_action != MISSING
    ]
    action_html = "".join(
        f"<div class='action'><b>{html.escape(s.name)} — {html.escape(s.signal)}</b>"
        f"<div>{s.price} ₽ → {s.price_action.lower()} · акция: {s.promo_action.lower()}</div>"
        f"<small>{html.escape(s.reason)}</small></div>"
        for s in actions
    ) or "<p>Сегодня подтверждённых действий нет.</p>"
    rows = "".join(
        f"<tr><td><b>{html.escape(s.name)}</b></td><td>{s.sales}</td><td>{s.price} ₽</td>"
        f"<td>{s.stock}</td><td>{html.escape(s.signal)} / {s.promo_action}</td></tr>"
        for s in skus
    )
    css = """
body{margin:0;background:#f4f6f8;color:#17212b;font-family:Arial,sans-serif} .wrap{max-width:680px;margin:auto;background:#fff;padding:20px}
h1{font-size:22px;margin:0 0 16px} h2{font-size:15px;margin:20px 0 8px;color:#52606d;letter-spacing:.04em}
.metrics{display:flex;gap:8px;flex-wrap:wrap}.metric{background:#f3f7fa;border-radius:8px;padding:10px 12px;min-width:110px}.metric b{font-size:18px;display:block}
.action{border-left:4px solid #f0a202;padding:8px 12px;margin:8px 0;background:#fff9eb}.action div{margin:4px 0}.action small{color:#52606d}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid #e5e9ed}th{color:#52606d;font-size:11px}
.fresh{font-size:12px;color:#52606d;margin-top:14px}@media(max-width:520px){.wrap{padding:14px}.metric{min-width:90px}th,td{padding:7px 3px;font-size:11px}}
"""
    html_body = f"""<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body><div class='wrap'>
<h1>EFA — отчёт на {report_date}</h1><h2>ИТОГ ДНЯ</h2><div class='metrics'>
<div class='metric'><b>{total_sales} шт.</b>{total_revenue:,} ₽</div><div class='metric'><b>{attention}</b>требуют внимания</div>
<div class='metric'><b>{watch}</b>наблюдать</div><div class='metric'><b>{leave}</b>не трогать</div></div>
<div class='fresh'>{html.escape(freshness)}</div><h2>ЧТО ДЕЛАТЬ СЕГОДНЯ</h2>{action_html}
<h2>ВСЕ SKU</h2><table><thead><tr><th>SKU</th><th>Продажи</th><th>Цена</th><th>Остаток</th><th>Цена / акция</th></tr></thead><tbody>{rows}</tbody></table>
</div></body></html>""".replace(f"{total_revenue:,}", f"{total_revenue:,}".replace(",", " "))

    text_lines = [
        f"EFA — отчёт на {report_date}", "", "ИТОГ ДНЯ",
        f"Продажи вчера: {total_sales} шт. / {total_revenue:,} ₽".replace(",", " "),
        f"Требуют внимания: {attention} · Наблюдать: {watch} · Не трогать: {leave}", freshness,
        "", "ЧТО ДЕЛАТЬ СЕГОДНЯ",
    ]
    for sku in actions:
        text_lines += [f"{sku.name} — {sku.signal}", f"Цена: {sku.price} ₽ → {sku.price_action.lower()}; акция: {sku.promo_action.lower()}", f"Причина: {sku.reason}"]
    text_lines += ["", "ВСЕ SKU", "SKU | продажи | цена | остаток | цена/акция"]
    text_lines += [f"{s.name} | {s.sales} | {s.price} ₽ | {s.stock} | {s.signal}/{s.promo_action}" for s in skus]
    return {"date": report_date, "subject": f"EFA — что делать сегодня · {report_date}", "html": html_body, "text": "\n".join(text_lines)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(render(args.report.read_text(encoding="utf-8")), ensure_ascii=False))


if __name__ == "__main__":
    main()
