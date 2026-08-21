"""Deterministic daily analyst report over the seven curated mcp_read views."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

import asyncpg


EXPECTED_DATABASE = "efa"
EXPECTED_ROLE = "efa_mcp_readonly"
MOSCOW = timezone(timedelta(hours=3), name="Europe/Moscow")

# Transparent, intentionally conservative v1 thresholds.
SALES_DROP_PERCENT = Decimal("-30")
MIN_BASELINE_UNITS = Decimal("3")
FRESHNESS_DAYS = 2
LOW_STOCK_COVER_DAYS = Decimal("7")
MIN_CPC_DAYS = 3
MIN_CPC_SPEND = Decimal("100")
HIGH_CPC_DRR_PERCENT = Decimal("25")
MIN_LOGISTICS_ORDERS = 5
HIGH_LOGISTICS_DELTA_PP = Decimal("3")
DAILY_DROP_UNITS = Decimal("2")
DAILY_DROP_PERCENT = Decimal("-50")

VIEW_QUERIES = {
    "overview": """
        SELECT offer_id, sku, product_name, is_archived, current_price,
               price_observed_at, price_checked_at, stock_snapshot_at, total_present,
               stock_data_quality_status, regional_data_quality
        FROM mcp_read.product_overview
        ORDER BY offer_id
    """,
    "price": """
        SELECT offer_id, observed_at, price, previous_price, change_percent
        FROM mcp_read.product_price_history
        ORDER BY offer_id, observed_at DESC
    """,
    "stock": """
        SELECT offer_id, snapshot_at, total_present, total_present_change,
               data_quality_status
        FROM mcp_read.product_stock_history
        ORDER BY offer_id, snapshot_at DESC
    """,
    "performance": """
        SELECT offer_id, business_date, ordered_units, ordered_revenue,
               demand_quality_status
        FROM mcp_read.product_daily_performance
        WHERE business_date BETWEEN $1 AND $2
        ORDER BY offer_id, business_date
    """,
    "logistics": """
        SELECT offer_id, cluster_from, cluster_to, orders_count,
               logistics_rate_percent, logistics_rate_delta_pp, confidence,
               data_through
        FROM mcp_read.product_region_logistics
        ORDER BY offer_id, cluster_from, cluster_to
    """,
    "promotions": """
        SELECT offer_id, promotion_title, participation_state, starts_at,
               ends_at, observed_at, data_quality_status
        FROM mcp_read.product_promotion_state
        ORDER BY offer_id, promotion_title
    """,
    "cpc": """
        SELECT offer_id, business_date, active_campaigns_count, views, clicks,
               spend, attributed_orders, attributed_revenue,
               data_quality_status, collection_status, observed_at
        FROM mcp_read.product_cpc_daily
        WHERE data_scope = 'PRODUCT'
          AND business_date BETWEEN $1 AND $2
        ORDER BY offer_id, business_date
    """,
}

ACTION_TEXT = {
    "DEMAND_INCOMPLETE": "Проверить штатный сбор спроса для {skus} и дождаться двух полных 7-дневных окон.",
    "STOCK_UNTRUSTED": "Обновить и проверить штатный снимок остатков для {skus}; до подтверждения не менять остатки, цены или рекламу.",
    "PRICE_STALE": "Обновить проверку цены для {skus} до принятия коммерческих решений.",
    "OUT_OF_STOCK": "Подтвердить нулевой остаток и подготовить пополнение для {skus}.",
    "LOW_STOCK": "Проверить план пополнения для {skus}: расчётное покрытие меньше 7 дней.",
    "SALES_DROP": "Разобрать падение {skus}: последовательно проверить цену, CPC, акции и наличие, не меняя их автоматически.",
    "NO_SALES": "Проверить видимость карточки и доступность предложения для {skus}: спрос за 7 дней равен нулю.",
    "CPC_NO_ORDERS": "Проверить поисковые запросы и ставки CPC для {skus}: есть расход без атрибутированных заказов.",
    "CPC_HIGH_DRR": "Пересмотреть ставки и кампании CPC для {skus}: агрегированный ДРР выше 25%.",
    "LOGISTICS_HIGH": "Проверить размещение запасов по кластерам для {skus}: логистическая ставка выше базовой.",
}


class SafeReportError(RuntimeError):
    """A report error whose message contains no credentials or database payload."""


def _database_url() -> str:
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise SafeReportError("DATABASE_URL is required")
    parsed = urlsplit(value)
    scheme = "postgresql" if parsed.scheme == "postgresql+asyncpg" else parsed.scheme
    if scheme not in {"postgresql", "postgres"}:
        raise SafeReportError("DATABASE_URL must use PostgreSQL")
    if parsed.username != EXPECTED_ROLE or unquote(parsed.path.lstrip("/")) != EXPECTED_DATABASE:
        raise SafeReportError("DATABASE_URL must target efa as efa_mcp_readonly")
    if not parsed.hostname:
        raise SafeReportError("DATABASE_URL must include a host")
    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def _num(value: Any) -> Decimal:
    return Decimal("0") if value is None else Decimal(str(value))


def _percent(numerator: Any, denominator: Any) -> Decimal | None:
    n, d = _num(numerator), _num(denominator)
    return None if d == 0 else (n / d * 100).quantize(Decimal("0.1"))


def _observed_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(MOSCOW).date() if value.tzinfo else value.date()
    return value


def _age_days(value: Any, as_of: date) -> int | None:
    observed = _observed_date(value)
    return None if observed is None else max(0, (as_of - observed).days)


def _fmt_number(value: Any, digits: int = 0) -> str:
    if value is None:
        return "н/д"
    number = float(value)
    return f"{number:,.{digits}f}".replace(",", " ")


def _fmt_money(value: Any) -> str:
    return "н/д" if value is None else f"{_fmt_number(value)} ₽"


def _fmt_percent(value: Any, signed: bool = False) -> str:
    if value is None:
        return "н/д"
    prefix = "+" if signed and _num(value) > 0 else ""
    return f"{prefix}{_fmt_number(value, 1)}%"


def _clean(value: Any) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ").strip()


def _empty_period() -> dict[str, Any]:
    return {"days": set(), "units": Decimal("0"), "revenue": Decimal("0"), "statuses": set()}


def _latest_two(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if len(result[row["offer_id"]]) < 2:
            result[row["offer_id"]].append(row)
    return result


def _daily_signal(yesterday: dict[str, Any] | None, day_before: dict[str, Any] | None) -> tuple[str, str]:
    if yesterday is None or day_before is None:
        missing = []
        if yesterday is None:
            missing.append("вчера")
        if day_before is None:
            missing.append("позавчера")
        return "НАБЛЮДАТЬ", f"продажи за {' и '.join(missing)}: н/д; изменение не рассчитано"

    units_change = _num(yesterday["ordered_units"]) - _num(day_before["ordered_units"])
    units_percent = _percent(units_change, day_before["ordered_units"])
    if units_change <= -DAILY_DROP_UNITS and units_percent is not None and units_percent <= DAILY_DROP_PERCENT:
        return (
            "ПРОВЕРИТЬ СЕЙЧАС",
            f"заказанные единицы снизились с {_fmt_number(day_before['ordered_units'])} до {_fmt_number(yesterday['ordered_units'])} ({_fmt_percent(units_percent, True)})",
        )
    if units_change < 0:
        return "НАБЛЮДАТЬ", f"заказанные единицы снизились с {_fmt_number(day_before['ordered_units'])} до {_fmt_number(yesterday['ordered_units'])}"
    if units_change > 0:
        return "НЕ ТРОГАТЬ", f"заказанные единицы выросли с {_fmt_number(day_before['ordered_units'])} до {_fmt_number(yesterday['ordered_units'])}"
    return "НЕ ТРОГАТЬ", f"заказанные единицы без изменения: {_fmt_number(yesterday['ordered_units'])}"


def _daily_comparison(product: dict[str, Any], yesterday: date, day_before: date) -> dict[str, Any]:
    rows = product["performance_rows"]
    by_date = {
        row["business_date"]: row
        for row in rows
        if row["ordered_units"] is not None and row["ordered_revenue"] is not None
    }
    y_row, d_row = by_date.get(yesterday), by_date.get(day_before)
    signal, reason = _daily_signal(y_row, d_row)
    stock = product.get("stock_snapshots") or []
    if stock and stock[0].get("data_quality_status") == "VALID" and _num(stock[0].get("total_present")) == 0:
        signal, reason = "ПРОВЕРИТЬ СЕЙЧАС", "последний подтверждённый остаток равен 0"
    return {"yesterday": y_row, "day_before": d_row, "signal": signal, "reason": reason}


def _aggregate_performance(
    rows: list[dict[str, Any]], current_start: date, previous_start: date, previous_end: date
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"current": _empty_period(), "previous": _empty_period()}
    )
    for row in rows:
        period = "current" if row["business_date"] >= current_start else "previous"
        if period == "previous" and not previous_start <= row["business_date"] <= previous_end:
            continue
        target = result[row["offer_id"]][period]
        if row["ordered_units"] is not None:
            target["days"].add(row["business_date"])
            target["units"] += _num(row["ordered_units"])
        if row["ordered_revenue"] is not None:
            target["revenue"] += _num(row["ordered_revenue"])
        if row["demand_quality_status"]:
            target["statuses"].add(row["demand_quality_status"])
    return result


def _aggregate_cpc(rows: list[dict[str, Any]], current_start: date) -> dict[str, dict[str, Any]]:
    def empty() -> dict[str, Any]:
        return {
            "days": set(), "active": 0, "views": 0, "clicks": 0,
            "spend": Decimal("0"), "orders": 0, "revenue": Decimal("0"),
            "statuses": set(), "observed_at": None, "ctr": None, "drr": None,
        }

    result: dict[str, dict[str, Any]] = defaultdict(lambda: {"current": empty(), "previous": empty()})
    for row in rows:
        period = "current" if row["business_date"] >= current_start else "previous"
        target = result[row["offer_id"]][period]
        target["days"].add(row["business_date"])
        target["active"] = max(target["active"], int(row["active_campaigns_count"] or 0))
        target["views"] += int(row["views"] or 0)
        target["clicks"] += int(row["clicks"] or 0)
        target["spend"] += _num(row["spend"])
        target["orders"] += int(row["attributed_orders"] or 0)
        target["revenue"] += _num(row["attributed_revenue"])
        target["statuses"].update(filter(None, (row["data_quality_status"], row["collection_status"])))
        if row["observed_at"] and (target["observed_at"] is None or row["observed_at"] > target["observed_at"]):
            target["observed_at"] = row["observed_at"]
    for periods in result.values():
        for target in periods.values():
            target["ctr"] = _percent(target["clicks"], target["views"])
            target["drr"] = _percent(target["spend"], target["revenue"])
    return result


def _aggregate_promotions(rows: list[dict[str, Any]], as_of: date) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"active": [], "candidates": 0, "observed_at": None}
    )
    for row in rows:
        target = result[row["offer_id"]]
        starts, ends = _observed_date(row["starts_at"]), _observed_date(row["ends_at"])
        in_window = (starts is None or starts <= as_of) and (ends is None or ends >= as_of)
        if row["participation_state"] == "PARTICIPATING" and in_window:
            target["active"].append(_clean(row["promotion_title"]) or "без названия")
        elif row["participation_state"] == "CANDIDATE" and in_window:
            target["candidates"] += 1
        if row["observed_at"] and (target["observed_at"] is None or row["observed_at"] > target["observed_at"]):
            target["observed_at"] = row["observed_at"]
    return result


def _aggregate_logistics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["offer_id"]].append(row)
    result: dict[str, dict[str, Any]] = {}
    for offer_id, items in grouped.items():
        weighted = [row for row in items if row["orders_count"] and row["logistics_rate_percent"] is not None]
        orders = sum(int(row["orders_count"] or 0) for row in weighted)
        rate = None if not orders else sum(_num(row["logistics_rate_percent"]) * int(row["orders_count"]) for row in weighted) / orders
        risk_rows = [
            row for row in items
            if row["logistics_rate_delta_pp"] is not None
            and str(row.get("confidence") or "").upper() in {"MEDIUM", "HIGH", "VERY_HIGH"}
        ]
        risk = max(risk_rows, key=lambda row: (_num(row["logistics_rate_delta_pp"]), int(row["orders_count"] or 0)), default=None)
        result[offer_id] = {
            "routes": len(items), "orders": orders, "rate": rate, "risk": risk,
            "data_through": max((row["data_through"] for row in items if row["data_through"]), default=None),
        }
    return result


def _add_issue(product: dict[str, Any], code: str, priority: int, signal: str, cause: str, hold: bool = False) -> None:
    product["issues"].append({"code": code, "priority": priority, "signal": signal, "cause": cause, "hold": hold})


def _diagnose(product: dict[str, Any], current_end: date) -> None:
    product["issues"] = []
    perf, cpc = product["performance"], product["cpc"]
    current, previous = perf["current"], perf["previous"]
    current_days, previous_days = len(current["days"]), len(previous["days"])
    product["sales_change"] = (
        _percent(current["units"] - previous["units"], previous["units"])
        if current_days == previous_days == 7 else None
    )

    if current_days < 7 or previous_days < 7:
        _add_issue(
            product, "DEMAND_INCOMPLETE", 100,
            f"спрос покрывает {current_days}/7 и {previous_days}/7 дней",
            "неполные окна могут искажать сравнение продаж", True,
        )

    stock_age = _age_days(product.get("stock_snapshot_at"), current_end)
    product["stock_age"] = stock_age
    stock_valid = product.get("stock_data_quality_status") == "VALID"
    stock_fresh = stock_valid and stock_age is not None and stock_age <= FRESHNESS_DAYS
    if not stock_fresh:
        detail = "снимок отсутствует" if stock_age is None else f"снимку {stock_age} дн.; status={product.get('stock_data_quality_status') or 'н/д'}"
        _add_issue(product, "STOCK_UNTRUSTED", 96, detail, "текущее наличие нельзя надёжно подтвердить", True)
    else:
        stock = _num(product.get("total_present"))
        if stock == 0:
            _add_issue(product, "OUT_OF_STOCK", 95, "подтверждённый остаток равен 0", "отсутствие товара ограничивает продажи")
        elif current_days == 7 and current["units"] > 0:
            cover = (stock / (current["units"] / Decimal("7"))).quantize(Decimal("0.1"))
            product["stock_cover_days"] = cover
            if cover < LOW_STOCK_COVER_DAYS:
                _add_issue(product, "LOW_STOCK", 90, f"покрытие около {cover} дн.", "остатка недостаточно при текущем темпе спроса")

    price_age = _age_days(product.get("price_checked_at"), current_end)
    product["price_age"] = price_age
    if price_age is None or price_age > FRESHNESS_DAYS:
        detail = "цена отсутствует" if price_age is None else f"наблюдению цены {price_age} дн."
        _add_issue(product, "PRICE_STALE", 94, detail, "актуальная цена не подтверждена", True)

    complete = current_days == previous_days == 7
    change = product["sales_change"]
    if complete and previous["units"] >= MIN_BASELINE_UNITS and change is not None and change <= SALES_DROP_PERCENT:
        signals = []
        latest_price = product.get("price_history") or {}
        if _num(latest_price.get("change_percent")) > 0:
            signals.append(f"последняя цена выросла на {_fmt_percent(latest_price['change_percent'], True)}")
        previous_cpc, current_cpc = cpc["previous"], cpc["current"]
        if previous_cpc["views"] >= 20 and current_cpc["views"] < previous_cpc["views"] * 0.7:
            signals.append("CPC-показы снизились более чем на 30%")
        if not stock_fresh:
            signals.append("актуальный остаток не подтверждён")
        cause = "; ".join(signals) if signals else "причина не подтверждена доступными агрегатами; нужны проверки цены, CPC, акции и наличия"
        _add_issue(product, "SALES_DROP", 85, f"продажи {_fmt_number(current['units'])} против {_fmt_number(previous['units'])} ({_fmt_percent(change, True)})", cause)
    elif complete and current["units"] == 0 and stock_fresh and _num(product.get("total_present")) > 0:
        _add_issue(product, "NO_SALES", 80, "0 заказанных единиц при подтверждённом наличии", "проблема вероятнее связана с видимостью, ценой или спросом, а не с остатком")

    current_cpc = cpc["current"]
    if len(current_cpc["days"]) >= MIN_CPC_DAYS and current_cpc["spend"] >= MIN_CPC_SPEND:
        if current_cpc["orders"] == 0:
            _add_issue(product, "CPC_NO_ORDERS", 75, f"расход {_fmt_money(current_cpc['spend'])}, атрибутированных заказов 0", "CPC-трафик не конвертировался в доступном окне")
        elif current_cpc["drr"] is not None and current_cpc["drr"] > HIGH_CPC_DRR_PERCENT:
            _add_issue(product, "CPC_HIGH_DRR", 70, f"агрегированный ДРР {_fmt_percent(current_cpc['drr'])}", "рекламный расход высок относительно атрибутированной выручки")

    worst = (product.get("logistics") or {}).get("risk")
    if (
        worst and int(worst["orders_count"] or 0) >= MIN_LOGISTICS_ORDERS
        and _num(worst["logistics_rate_delta_pp"]) >= HIGH_LOGISTICS_DELTA_PP
    ):
        route = f"{_clean(worst['cluster_from'])}→{_clean(worst['cluster_to'])}"
        _add_issue(product, "LOGISTICS_HIGH", 60, f"{route}: +{_fmt_number(worst['logistics_rate_delta_pp'], 1)} п.п., {worst['orders_count']} заказов", "региональный маршрут дороже базового при достаточной выборке")


def _render(products: list[dict[str, Any]], current_start: date, current_end: date, previous_start: date, previous_end: date, limit: int) -> str:
    current_units = sum((p["performance"]["current"]["units"] for p in products), Decimal("0"))
    previous_units = sum((p["performance"]["previous"]["units"] for p in products), Decimal("0"))
    current_revenue = sum((p["performance"]["current"]["revenue"] for p in products), Decimal("0"))
    previous_revenue = sum((p["performance"]["previous"]["revenue"] for p in products), Decimal("0"))
    current_coverage = sum(len(p["performance"]["current"]["days"]) for p in products)
    previous_coverage = sum(len(p["performance"]["previous"]["days"]) for p in products)
    expected = len(products) * 7
    comparable = current_coverage == previous_coverage == expected
    units_change = _percent(current_units - previous_units, previous_units) if comparable else None
    revenue_change = _percent(current_revenue - previous_revenue, previous_revenue) if comparable else None
    current_units_display = current_units if current_coverage else None
    previous_units_display = previous_units if previous_coverage else None
    current_revenue_display = current_revenue if current_coverage else None
    previous_revenue_display = previous_revenue if previous_coverage else None

    ranked = sorted(
        products,
        key=lambda p: (-max((i["priority"] for i in p["issues"]), default=0), -p["performance"]["current"]["units"], p["offer_id"]),
    )[:limit]
    daily_priority = {"ПРОВЕРИТЬ СЕЙЧАС": 3, "НАБЛЮДАТЬ": 2, "НЕ ТРОГАТЬ": 1}
    daily_ranked = sorted(
        products,
        key=lambda p: (-daily_priority[p["daily"]["signal"]], p["offer_id"]),
    )[:limit]
    lines = [
        "# AI Analyst v1.1 — ежедневный отчёт EFA",
        "",
        f"## Сегодня: {current_end.isoformat()} против {(current_end - timedelta(days=1)).isoformat()}",
        "",
        "Первым показан SKU, который требует больше внимания. `н/д` означает отсутствие факта; оно не считается нулём.",
    ]

    for product in daily_ranked:
        daily = product["daily"]
        y_row, d_row = daily["yesterday"], daily["day_before"]
        prices = product.get("price_snapshots") or []
        stocks = product.get("stock_snapshots") or []
        latest_price = prices[0] if prices else None
        previous_price = prices[1] if len(prices) > 1 else None
        latest_stock = stocks[0] if stocks else None
        previous_stock = stocks[1] if len(stocks) > 1 else None
        price_delta = None if latest_price is None or previous_price is None else _num(latest_price["price"]) - _num(previous_price["price"])
        stock_delta = None if latest_stock is None or previous_stock is None else _num(latest_stock["total_present"]) - _num(previous_stock["total_present"])
        cpc_rows = product.get("cpc_rows") or []
        latest_cpc = max(cpc_rows, key=lambda row: row["business_date"], default=None)
        promo, logistics = product["promotions"], product["logistics"]
        y_units = y_row["ordered_units"] if y_row else None
        d_units = d_row["ordered_units"] if d_row else None
        y_revenue = y_row["ordered_revenue"] if y_row else None
        d_revenue = d_row["ordered_revenue"] if d_row else None
        units_delta = None if y_row is None or d_row is None else _num(y_units) - _num(d_units)
        revenue_delta = None if y_row is None or d_row is None else _num(y_revenue) - _num(d_revenue)
        cpc_text = (
            "н/д"
            if latest_cpc is None
            else f"по {latest_cpc['business_date']}: кампаний {int(latest_cpc['active_campaigns_count'] or 0)}, расход {_fmt_money(latest_cpc['spend'])}, атриб. заказов {int(latest_cpc['attributed_orders'] or 0)}"
        )
        lines.extend([
            "",
            f"### {daily['signal']} · {_clean(product['offer_id'])}",
            "",
            f"- Продажи: вчера **{_fmt_number(y_units)} шт. / {_fmt_money(y_revenue)}**, позавчера **{_fmt_number(d_units)} шт. / {_fmt_money(d_revenue)}**; изменение **{_fmt_number(units_delta)} шт. / {_fmt_money(revenue_delta)}**.",
            f"- Цена: **{_fmt_money(latest_price['price'] if latest_price else None)}** ({_observed_date(latest_price['observed_at']) if latest_price else 'н/д'}); предыдущий снимок **{_fmt_money(previous_price['price'] if previous_price else None)}** ({_observed_date(previous_price['observed_at']) if previous_price else 'н/д'}); изменение **{_fmt_money(price_delta)}**.",
            f"- Остаток: **{_fmt_number(latest_stock['total_present'] if latest_stock else None)} шт.** ({_observed_date(latest_stock['snapshot_at']) if latest_stock else 'н/д'}); предыдущий снимок **{_fmt_number(previous_stock['total_present'] if previous_stock else None)} шт.** ({_observed_date(previous_stock['snapshot_at']) if previous_stock else 'н/д'}); изменение **{_fmt_number(stock_delta)} шт.**.",
            f"- Логистика: ставка **{_fmt_percent(logistics.get('rate'))}** по {_observed_date(logistics.get('data_through')) or 'н/д'}; изменение: **н/д**, представление содержит только последнее агрегированное окно.",
            f"- Акции/CPC: активных акций {len(promo['active'])}, кандидатов {promo['candidates']} (наблюдение {_observed_date(promo['observed_at']) or 'н/д'}); CPC {cpc_text}.",
            f"- Почему: {daily['reason']}.",
        ])

    lines.extend([
        "",
        f"Данные продаж: **{current_start.isoformat()} — {current_end.isoformat()}**; сравнение: **{previous_start.isoformat()} — {previous_end.isoformat()}**. "
        "Окна привязаны к последней доступной `business_date` (Europe/Moscow). Продажи = ordered demand, выручка = ordered revenue.",
        "",
        "## Продажи: последние 7 дней против предыдущих 7",
        "",
        f"- Продажи: **{_fmt_number(current_units_display)} шт.** против **{_fmt_number(previous_units_display)} шт.** ({_fmt_percent(units_change, True)}).",
        f"- Выручка: **{_fmt_money(current_revenue_display)}** против **{_fmt_money(previous_revenue_display)}** ({_fmt_percent(revenue_change, True)}).",
        f"- Покрытие спроса: текущее окно **{current_coverage}/{expected}**, предыдущее **{previous_coverage}/{expected} SKU-дней**; сравнение рассчитывается только для двух полных окон.",
        "",
        f"## SKU: {len(ranked)}",
    ])

    for product in ranked:
        perf, cpc = product["performance"]["current"], product["cpc"]["current"]
        promo, logistics = product["promotions"], product["logistics"]
        price_change = (product.get("price_history") or {}).get("change_percent")
        stock_change = (product.get("stock_history") or {}).get("total_present_change")
        offer = _clean(product["offer_id"])
        ozon_sku = _clean(product.get("sku")) or "н/д"
        cpc_text = (
            "н/д: продуктовых CPC-строк в окне нет"
            if not cpc["days"]
            else f"расход **{_fmt_money(cpc['spend'])}**, кампаний {cpc['active']}, показы/клики {cpc['views']}/{cpc['clicks']}, CTR {_fmt_percent(cpc['ctr'])}, атриб. заказы {cpc['orders']}, ДРР {_fmt_percent(cpc['drr'])}; доступно {len(cpc['days'])}/7 дней"
        )
        lines.extend([
            "",
            f"### {offer} · Ozon SKU {ozon_sku}",
            "",
            f"- Продажи/выручка: **{_fmt_number(perf['units'] if perf['days'] else None)} шт. / {_fmt_money(perf['revenue'] if perf['days'] else None)}**; предыдущее окно: **{_fmt_number(product['performance']['previous']['units'] if product['performance']['previous']['days'] else None)} шт.**; изменение: **{_fmt_percent(product['sales_change'], True)}**; покрытие {len(perf['days'])}/7 дней.",
            f"- Цена: **{_fmt_money(product.get('current_price'))}**; последнее изменение: {_fmt_percent(price_change, True)}; наблюдение/проверка: {_observed_date(product.get('price_observed_at')) or 'н/д'} / {_observed_date(product.get('price_checked_at')) or 'н/д'}.",
            f"- Остаток: **{_fmt_number(product.get('total_present'))} шт.**; изменение снимка: {_fmt_number(stock_change, 0)}; снимок: {_observed_date(product.get('stock_snapshot_at')) or 'н/д'} ({product.get('stock_data_quality_status') or 'н/д'}).",
            f"- CPC: {cpc_text}.",
            f"- Продвижение: активных акций {len(promo['active'])}, кандидатов {promo['candidates']}; наблюдение: {_observed_date(promo['observed_at']) or 'н/д'}.",
            f"- Региональная логистика: маршрутов {logistics.get('routes', 0)}, заказов {logistics.get('orders', 0)}, взвешенная ставка {_fmt_percent(logistics.get('rate'))}; данные по {_observed_date(logistics.get('data_through')) or 'н/д'}.",
        ])

    problems = [p for p in ranked if p["issues"]]
    lines.extend(["", "## Проблемные SKU", ""])
    if not problems:
        lines.append("Пороговые правила не сработали.")
    for product in problems:
        lines.append(f"- **{_clean(product['offer_id'])}**")
        for issue in sorted(product["issues"], key=lambda item: -item["priority"]):
            lines.append(f"  - {issue['signal']}. Вероятная причина/ограничение: {issue['cause']}.")

    grouped: dict[str, list[str]] = defaultdict(list)
    priorities: dict[str, int] = {}
    for product in products:
        for issue in product["issues"]:
            grouped[issue["code"]].append(_clean(product["offer_id"]))
            priorities[issue["code"]] = max(priorities.get(issue["code"], 0), issue["priority"])
    action_codes = sorted(grouped, key=lambda code: (-priorities[code], code))[:5]
    lines.extend(["", "## Действия на сегодня", ""])
    if action_codes:
        for number, code in enumerate(action_codes, 1):
            skus = ", ".join(sorted(set(grouped[code])))
            lines.append(f"{number}. {ACTION_TEXT[code].format(skus=skus)}")
    else:
        lines.append("1. Не менять текущие настройки; повторить отчёт после следующего полного дня данных.")

    untouched: list[tuple[str, str]] = []
    for product in products:
        blockers = [i for i in product["issues"] if i["hold"]]
        if blockers:
            untouched.append((_clean(product["offer_id"]), "; ".join(i["signal"] for i in blockers)))
        elif not product["issues"]:
            untouched.append((_clean(product["offer_id"]), "нет подтверждённого проблемного сигнала"))
    lines.extend(["", "## Сейчас лучше не трогать", ""])
    if untouched:
        lines.extend(f"- **{sku}** — {reason}." for sku, reason in untouched)
    else:
        lines.append("Нет SKU, попавших в консервативную hold-категорию.")

    lines.extend([
        "",
        "## Правила v1.1",
        "",
        "Падение: ≥30% при базе ≥3 шт.; свежесть цены/остатка: ≤2 дней; низкий запас: <7 дней покрытия; "
        "CPC: минимум 3 дня и 100 ₽ расхода, ДРР >25%; логистика: +3 п.п. при ≥5 заказах и confidence не ниже MEDIUM. "
        "Дневной сигнал: ПРОВЕРИТЬ СЕЙЧАС при падении минимум на 2 шт. и 50% либо подтверждённом нулевом остатке; "
        "НАБЛЮДАТЬ при меньшем снижении или неполных данных; иначе НЕ ТРОГАТЬ. "
        "Сигналы являются диагностикой, а не доказательством причинности; скрипт ничего не изменяет.",
    ])
    return "\n".join(lines)


async def _run(limit: int) -> str:
    connection = await asyncpg.connect(
        dsn=_database_url(),
        command_timeout=11,
        server_settings={
            "application_name": "efa_ai_analyst_v1",
            "default_transaction_read_only": "on",
            "statement_timeout": "10000ms",
            "lock_timeout": "3000ms",
            "search_path": "mcp_read,pg_catalog",
        },
    )
    try:
        async with connection.transaction(readonly=True):
            identity = await connection.fetchrow(
                "SELECT current_user AS role, current_database() AS db, current_setting('transaction_read_only') AS read_only"
            )
            if identity["role"] != EXPECTED_ROLE or identity["db"] != EXPECTED_DATABASE or identity["read_only"] != "on":
                raise SafeReportError("Database read-only identity check failed")
            current_end = await connection.fetchval(
                "SELECT max(business_date) FROM mcp_read.product_daily_performance"
            )
            if current_end is None:
                raise SafeReportError("No performance dates are available")
            current_start = current_end - timedelta(days=6)
            previous_end = current_start - timedelta(days=1)
            previous_start = previous_end - timedelta(days=6)

            overview = [dict(row) for row in await connection.fetch(VIEW_QUERIES["overview"])]
            price = [dict(row) for row in await connection.fetch(VIEW_QUERIES["price"])]
            stock = [dict(row) for row in await connection.fetch(VIEW_QUERIES["stock"])]
            performance = [dict(row) for row in await connection.fetch(VIEW_QUERIES["performance"], previous_start, current_end)]
            logistics_rows = [dict(row) for row in await connection.fetch(VIEW_QUERIES["logistics"])]
            promotion_rows = [dict(row) for row in await connection.fetch(VIEW_QUERIES["promotions"])]
            cpc_rows = [dict(row) for row in await connection.fetch(VIEW_QUERIES["cpc"], previous_start, current_end)]

            performance_by_offer = _aggregate_performance(performance, current_start, previous_start, previous_end)
            cpc_by_offer = _aggregate_cpc(cpc_rows, current_start)
            promotions_by_offer = _aggregate_promotions(promotion_rows, datetime.now(MOSCOW).date())
            logistics_by_offer = _aggregate_logistics(logistics_rows)
            price_snapshots = _latest_two(price)
            stock_snapshots = _latest_two(stock)
            performance_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
            cpc_product_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for item in performance:
                performance_rows[item["offer_id"]].append(item)
            for item in cpc_rows:
                cpc_product_rows[item["offer_id"]].append(item)

            products = []
            for row in overview:
                if row["is_archived"]:
                    continue
                product = row
                product["performance"] = performance_by_offer[row["offer_id"]]
                product["cpc"] = cpc_by_offer[row["offer_id"]]
                product["promotions"] = promotions_by_offer[row["offer_id"]]
                product["logistics"] = logistics_by_offer.get(row["offer_id"], {})
                product["price_snapshots"] = price_snapshots.get(row["offer_id"], [])
                product["stock_snapshots"] = stock_snapshots.get(row["offer_id"], [])
                product["performance_rows"] = performance_rows[row["offer_id"]]
                product["cpc_rows"] = cpc_product_rows[row["offer_id"]]
                product["price_history"] = product["price_snapshots"][0] if product["price_snapshots"] else None
                product["stock_history"] = product["stock_snapshots"][0] if product["stock_snapshots"] else None
                product["daily"] = _daily_comparison(product, current_end, current_end - timedelta(days=1))
                _diagnose(product, current_end)
                products.append(product)
            if not products:
                raise SafeReportError("No active products are available")
            return _render(products, current_start, current_end, previous_start, previous_end, limit)
    finally:
        await connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="EFA deterministic AI Analyst v1.1")
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 51), metavar="1..50")
    args = parser.parse_args()
    try:
        print(asyncio.run(_run(args.limit)))
        return 0
    except SafeReportError as exc:
        print(f"AI Analyst v1.1: {exc}", file=sys.stderr)
    except Exception:
        print("AI Analyst v1.1: read-only report failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
