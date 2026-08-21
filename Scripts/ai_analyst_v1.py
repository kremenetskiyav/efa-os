"""Deterministic daily analyst report over the seven curated mcp_read views."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

import asyncpg


EXPECTED_DATABASE = "efa"
EXPECTED_ROLE = "efa_mcp_readonly"
MOSCOW = timezone(timedelta(hours=3), name="Europe/Moscow")

# Price Decision v1 business parameters. Keep these simple and editable here.
MIN_MARGIN_PERCENT = Decimal("10")
COMFORTABLE_MARGIN_PERCENT = Decimal("15")
PRICE_TEST_STEP_PERCENT = Decimal("3")
MAX_PRICE_STEP_PERCENT = Decimal("5")
PRICE_ROUNDING_RUB = Decimal("5")

# Existing diagnostic thresholds.
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
               current_price_since, price_observed_at, price_checked_at, cost_price, cost_basis,
               confirmed_units_at_current_price, multi_line_units_excluded_at_current_price,
               unmatched_finance_units_at_current_price, current_price_economics_status,
               stock_snapshot_at, total_present,
               stock_data_quality_status, regional_data_quality
        FROM mcp_read.product_overview
        ORDER BY offer_id
    """,
    "price": """
        SELECT offer_id, observed_at, price, previous_price, absolute_change,
               change_percent, min_price, marketing_price, marketing_seller_price
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
               demand_quality_status, delivered_units,
               finance_matched_delivered_units, multi_line_excluded_units,
               unmatched_finance_units, confirmed_revenue, commission_expense,
               logistics_expense, other_expenses, cost_of_goods, payout,
               profit_before_tax, economics_quality_status
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
        SELECT offer_id, promotion_title, promotion_type, participation_state,
               add_mode, starts_at, ends_at, observed_price, promotion_price,
               max_promotion_price, current_boost, min_boost, max_boost,
               observed_at, data_quality_status
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
    "DEMAND_INCOMPLETE": "Проверить штатный сбор спроса для {skus}; недельное сравнение пока неполное, но доступные факты используются в ценовом решении.",
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


def _fmt_signed_money(value: Any) -> str:
    if value is None:
        return "н/д"
    prefix = "+" if _num(value) > 0 else ""
    return f"{prefix}{_fmt_number(value)} ₽"


def _fmt_percent(value: Any, signed: bool = False) -> str:
    if value is None:
        return "н/д"
    prefix = "+" if signed and _num(value) > 0 else ""
    return f"{prefix}{_fmt_number(value, 1)}%"


def _clean(value: Any) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ").strip()


def _empty_period() -> dict[str, Any]:
    return {
        "days": set(), "units": Decimal("0"), "revenue": Decimal("0"), "statuses": set(),
        "delivered": Decimal("0"), "matched": Decimal("0"), "excluded": Decimal("0"),
        "unmatched": Decimal("0"), "confirmed_revenue": Decimal("0"),
        "commission": Decimal("0"), "logistics": Decimal("0"),
        "other_expenses": Decimal("0"), "cost": Decimal("0"), "payout": Decimal("0"),
        "profit": Decimal("0"), "missing_profit_units": Decimal("0"),
        "bad_economics_units": Decimal("0"), "economics_statuses": set(),
    }


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
        target["delivered"] += _num(row.get("delivered_units"))
        matched_units = _num(row.get("finance_matched_delivered_units"))
        target["matched"] += matched_units
        target["excluded"] += _num(row.get("multi_line_excluded_units"))
        target["unmatched"] += _num(row.get("unmatched_finance_units"))
        target["confirmed_revenue"] += _num(row.get("confirmed_revenue"))
        target["commission"] += _num(row.get("commission_expense"))
        target["logistics"] += _num(row.get("logistics_expense"))
        target["other_expenses"] += _num(row.get("other_expenses"))
        target["cost"] += _num(row.get("cost_of_goods"))
        target["payout"] += _num(row.get("payout"))
        target["profit"] += _num(row.get("profit_before_tax"))
        if matched_units > 0 and (
            row.get("confirmed_revenue") is None
            or row.get("cost_of_goods") is None
            or row.get("profit_before_tax") is None
        ):
            target["missing_profit_units"] += matched_units
        if _num(row.get("delivered_units")) > 0 and row.get("economics_quality_status") != "CONFIRMED_CURRENT_COST":
            target["bad_economics_units"] += _num(row.get("delivered_units"))
        if row.get("economics_quality_status"):
            target["economics_statuses"].add(row["economics_quality_status"])
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
        lambda: {"active": [], "candidates": [], "observed_at": None}
    )
    for row in rows:
        target = result[row["offer_id"]]
        starts, ends = _observed_date(row["starts_at"]), _observed_date(row["ends_at"])
        in_window = (starts is None or starts <= as_of) and (ends is None or ends >= as_of)
        if row["participation_state"] == "PARTICIPATING" and in_window:
            target["active"].append(row)
        elif row["participation_state"] == "CANDIDATE" and in_window:
            target["candidates"].append(row)
        if row["observed_at"] and (target["observed_at"] is None or row["observed_at"] > target["observed_at"]):
            target["observed_at"] = row["observed_at"]
    return result


def _confidence(confirmed_units: Any) -> str:
    units = _num(confirmed_units)
    if units >= 3:
        return "ВЫСОКАЯ"
    if units == 2:
        return "СРЕДНЯЯ"
    if units == 1:
        return "НИЗКАЯ"
    return "Н/Д"


def _economics(period: dict[str, Any]) -> dict[str, Any]:
    confirmed_units = period["matched"]
    available = (
        confirmed_units >= 1
        and period["missing_profit_units"] == 0
        and period["confirmed_revenue"] > 0
    )
    revenue = period["confirmed_revenue"] if available else None
    profit = period["profit"] if available else None
    margin = _percent(profit, revenue) if available else None
    per_unit_revenue = None if not available else revenue / confirmed_units
    return {
        "available": available,
        "partial": available and (
            period["excluded"] > 0
            or period["unmatched"] > 0
            or confirmed_units < period["delivered"]
        ),
        "confirmed_units": confirmed_units if available else Decimal("0"),
        "confidence": _confidence(confirmed_units if available else 0),
        "revenue": revenue,
        "profit": profit,
        "margin": margin,
        "per_unit_revenue": per_unit_revenue,
    }


def _round_test_price(current_price: Any, direction: int, step_percent: Decimal) -> Decimal:
    current = _num(current_price)
    if current <= 0 or direction not in {-1, 1}:
        return current
    raw = current * (Decimal("1") + Decimal(direction) * step_percent / Decimal("100"))
    rounded = (raw / PRICE_ROUNDING_RUB).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * PRICE_ROUNDING_RUB
    upper = current * (Decimal("1") + MAX_PRICE_STEP_PERCENT / Decimal("100"))
    lower = current * (Decimal("1") - MAX_PRICE_STEP_PERCENT / Decimal("100"))
    if direction > 0 and rounded > upper:
        rounded = (upper / PRICE_ROUNDING_RUB).quantize(Decimal("1"), rounding=ROUND_FLOOR) * PRICE_ROUNDING_RUB
    if direction < 0 and rounded < lower:
        rounded = (lower / PRICE_ROUNDING_RUB).quantize(Decimal("1"), rounding=ROUND_CEILING) * PRICE_ROUNDING_RUB
    if direction > 0 and rounded <= current:
        rounded = (current / PRICE_ROUNDING_RUB).quantize(Decimal("1"), rounding=ROUND_FLOOR) * PRICE_ROUNDING_RUB + PRICE_ROUNDING_RUB
    if direction < 0 and rounded >= current:
        rounded = (current / PRICE_ROUNDING_RUB).quantize(Decimal("1"), rounding=ROUND_CEILING) * PRICE_ROUNDING_RUB - PRICE_ROUNDING_RUB
    return current if rounded < lower or rounded > upper else rounded


def _estimate_margin_at_price(period: dict[str, Any], economics: dict[str, Any], price: Any) -> dict[str, Any] | None:
    target = _num(price)
    if not economics["available"] or target <= 0:
        return None
    units = economics["confirmed_units"]
    commission_rate = period["commission"] / economics["revenue"]
    fixed_per_unit = (period["logistics"] + period["other_expenses"] + period["cost"]) / units
    estimated_profit = target - target * commission_rate - fixed_per_unit
    return {
        "price": target,
        "profit": estimated_profit,
        "margin": _percent(estimated_profit, target),
    }


def _active_promo_match(rows: list[dict[str, Any]], actual_price: Any) -> dict[str, Any] | None:
    if actual_price is None:
        return None
    priced = [
        row for row in rows
        if row.get("promotion_price") is not None and _num(row.get("promotion_price")) > 0
    ]
    return min(
        (row for row in priced if abs(_num(row["promotion_price"]) - _num(actual_price)) <= Decimal("2")),
        key=lambda row: abs(_num(row["promotion_price"]) - _num(actual_price)),
        default=None,
    )


def _active_promo_price(rows: list[dict[str, Any]], matched: dict[str, Any] | None) -> Decimal | None:
    if matched is not None:
        return _num(matched["promotion_price"])
    prices = [
        _num(row.get("promotion_price")) for row in rows
        if row.get("promotion_price") is not None and _num(row.get("promotion_price")) > 0
    ]
    return min(prices, default=None)


def _candidate_effective_price(row: dict[str, Any], current_price: Any) -> Decimal | None:
    action_price = _num(row.get("promotion_price"))
    if action_price > 0:
        return action_price
    current = _num(current_price)
    observed = _num(row.get("observed_price"))
    limit = _num(row.get("max_promotion_price"))
    starting = observed if observed > 0 else current
    if starting <= 0:
        return limit if limit > 0 else None
    return min(starting, limit) if limit > 0 else starting


def _active_promos_allow_price(rows: list[dict[str, Any]], test_price: Any) -> bool:
    target = _num(test_price)
    for row in rows:
        if str(row.get("add_mode") or "").upper() == "MANUAL":
            return False
        limit = _num(row.get("max_promotion_price"))
        if limit <= 0 or target > limit:
            return False
    return True


def _stock_sufficient(product: dict[str, Any], current_end: date) -> bool:
    age = _age_days(product.get("stock_snapshot_at"), current_end)
    if age is None or age > FRESHNESS_DAYS or product.get("stock_data_quality_status") != "VALID":
        return False
    stock = _num(product.get("total_present"))
    period = product["performance"]["current"]
    if stock <= 0:
        return False
    if not period["days"] or period["units"] <= 0:
        return True
    daily_rate = period["units"] / Decimal(len(period["days"]))
    return stock / daily_rate >= LOW_STOCK_COVER_DAYS


def _logistics_worse(product: dict[str, Any]) -> bool:
    risk = (product.get("logistics") or {}).get("risk")
    return bool(risk and _num(risk.get("logistics_rate_delta_pp")) >= HIGH_LOGISTICS_DELTA_PP)


def _promotion_text(rows: list[dict[str, Any]], candidate: bool = False) -> str:
    if not rows:
        return "нет"
    items = []
    for row in rows:
        candidate_price = row.get("promotion_price")
        if candidate and candidate_price is not None and _num(candidate_price) > 0:
            price, price_label = candidate_price, "цена"
        elif candidate:
            price, price_label = row.get("max_promotion_price"), "лимит цены"
        else:
            price, price_label = row.get("promotion_price"), "цена"
        price_text = _fmt_money(price) if price is not None and _num(price) > 0 else "н/д"
        mode = _clean(row.get("add_mode")) or "н/д"
        items.append(f"{_clean(row.get('promotion_title')) or 'без названия'} ({price_label} {price_text}, режим {mode})")
    return "; ".join(items)


def _commercial_recommendation(product: dict[str, Any], current_end: date) -> dict[str, Any]:
    period = product["performance"]["current"]
    economics = _economics(period)
    promo = product["promotions"]
    current_price = _num(product.get("current_price"))
    actual_price = economics["per_unit_revenue"]
    active_match = _active_promo_match(promo["active"], actual_price)
    actual_matches_base = actual_price is not None and abs(_num(actual_price) - current_price) <= Decimal("2")
    fixed_active = any(str(row.get("add_mode") or "").upper() == "MANUAL" for row in promo["active"])
    base_interval_supported = (
        "confirmed_units_at_current_price" not in product
        or _num(product.get("confirmed_units_at_current_price")) >= economics["confirmed_units"]
    )
    active_price = _active_promo_price(promo["active"], active_match)
    price_age = _age_days(product.get("price_checked_at"), current_end)
    price_fresh = price_age is not None and price_age <= FRESHNESS_DAYS and current_price > 0
    stock_sufficient = _stock_sufficient(product, current_end)
    logistics_worse = _logistics_worse(product)
    rank = int(product.get("sales_rank") or 0)
    product_count = int(product.get("sales_product_count") or 0)
    strong_demand = period["units"] > 0 and rank > 0 and rank <= (product_count + 1) // 2
    weekly_drop = product.get("sales_change") is not None and product["sales_change"] <= SALES_DROP_PERCENT
    daily = product.get("daily") or {}
    daily_drop = (
        daily.get("signal") == "ПРОВЕРИТЬ СЕЙЧАС"
        and daily.get("yesterday") is not None
        and daily.get("day_before") is not None
    )
    demand_falling = weekly_drop or daily_drop

    candidate_estimate = None
    for row in promo["candidates"]:
        candidate_price = _candidate_effective_price(row, current_price)
        estimate = _estimate_margin_at_price(period, economics, candidate_price)
        if estimate is not None and (
            candidate_estimate is None or estimate["margin"] > candidate_estimate["margin"]
        ):
            candidate_estimate = estimate

    if active_match is not None:
        if economics["margin"] < MIN_MARGIN_PERCENT:
            promo_action = "ВЫЙТИ"
            promo_reason = "фактическая акционная маржа ниже 10%"
        elif economics["margin"] >= COMFORTABLE_MARGIN_PERCENT:
            promo_action = "ОСТАВИТЬ"
            promo_reason = "фактическая акционная маржа в комфортной зоне от 15%"
        else:
            promo_action = "ОСТАВИТЬ"
            promo_reason = "фактическая акционная маржа не ниже 10%"
    elif promo["active"]:
        promo_action = "ОСТАВИТЬ"
        promo_reason = "активная цена акции не подтверждена фактической доставкой"
    elif candidate_estimate is not None:
        if candidate_estimate["margin"] >= MIN_MARGIN_PERCENT:
            promo_action = "ВОЙТИ"
            promo_reason = "оценочная маржа кандидатной цены не ниже 10%"
        else:
            promo_action = "НЕ ВХОДИТЬ"
            promo_reason = "оценочная маржа кандидатной цены ниже 10%"
    elif promo["candidates"]:
        promo_action = "НЕ ВХОДИТЬ"
        promo_reason = "экономика кандидатной цены не подтверждена"
    else:
        promo_action = "ОСТАВИТЬ"
        promo_reason = "активных и кандидатных акций нет"

    price_action = "ОСТАВИТЬ"
    test_price = current_price
    test_estimate = _estimate_margin_at_price(period, economics, test_price)
    if not price_fresh:
        price_reason = "текущая цена не подтверждена свежим снимком"
    elif not economics["available"]:
        price_reason = "нет подтверждённых доставок для фактической экономики"
    elif active_match is not None:
        mode = "ручной" if str(active_match.get("add_mode") or "").upper() == "MANUAL" else "активной"
        test_estimate = None
        price_reason = f"продажи фактически идут по {mode} акции {_fmt_money(active_price)}"
    elif fixed_active:
        test_estimate = None
        price_reason = "есть активная ручная акция, но её цена ещё не подтверждена фактической доставкой"
    elif actual_matches_base and not base_interval_supported:
        test_estimate = None
        price_reason = "экономика окна не полностью относится к текущему интервалу базовой цены"
    elif not actual_matches_base:
        test_estimate = None
        price_reason = "фактическая цена доставки не совпадает ни с базовой, ни с активной акционной ценой"
    elif economics["margin"] < MIN_MARGIN_PERCENT:
        candidate_price = _round_test_price(current_price, 1, MAX_PRICE_STEP_PERCENT)
        if _active_promos_allow_price(promo["active"], candidate_price):
            price_action = "ПОДНЯТЬ"
            test_price = candidate_price
            test_estimate = _estimate_margin_at_price(period, economics, test_price)
            price_reason = f"фактическая маржа {_fmt_percent(economics['margin'])} ниже минимума 10%; тест ограничен +5%"
        else:
            price_reason = "повышение не подтверждено условиями активной акции"
    elif demand_falling and stock_sufficient and not logistics_worse:
        candidate_price = _round_test_price(current_price, -1, PRICE_TEST_STEP_PERCENT)
        candidate_test = _estimate_margin_at_price(period, economics, candidate_price)
        if not _active_promos_allow_price(promo["active"], candidate_price):
            price_reason = "снижение не подтверждено условиями активной акции"
        elif candidate_test is not None and candidate_test["margin"] >= MIN_MARGIN_PERCENT:
            price_action = "СНИЗИТЬ"
            test_price = candidate_price
            test_estimate = candidate_test
            price_reason = "спрос подтверждённо снизился, запас достаточный, логистика не объясняет падение"
        else:
            price_reason = "снижение спроса есть, но тестовая цена уводит оценочную маржу ниже 10%"
    elif strong_demand and stock_sufficient and not logistics_worse:
        candidate_price = _round_test_price(current_price, 1, PRICE_TEST_STEP_PERCENT)
        if _active_promos_allow_price(promo["active"], candidate_price):
            price_action = "ПОДНЯТЬ"
            test_price = candidate_price
            test_estimate = _estimate_margin_at_price(period, economics, test_price)
            margin_zone = "комфортная" if economics["margin"] >= COMFORTABLE_MARGIN_PERCENT else "допустимая"
            promo_limit = min(
                (_num(row.get("max_promotion_price")) for row in promo["active"]),
                default=Decimal("0"),
            )
            promo_note = f", лимит активной акции {_fmt_money(promo_limit)} не нарушен" if promo["active"] else ""
            price_reason = f"{rank}-е место по продажам, запас достаточный и фактическая маржа {margin_zone}{promo_note}"
        else:
            price_reason = "повышение не подтверждено условиями активной акции"
    elif logistics_worse:
        price_reason = "изменение цены отложено из-за подтверждённого ухудшения логистики"
    elif not stock_sufficient:
        price_reason = "нет подтверждения достаточного запаса для ценового теста"
    else:
        price_reason = "фактическая экономика приемлема, подтверждённого ценового триггера нет"

    delta = test_price - current_price
    delta_percent = _percent(delta, current_price)
    if active_match is not None:
        confirmed = int(economics["confirmed_units"])
        deliveries = "1 подтверждённой доставке" if confirmed == 1 else f"{confirmed} подтверждённых доставках"
        partial = "; остальные доставки без полной экономики не включены" if economics["partial"] else ""
        reason = (
            f"Фактическая цена {_fmt_money(actual_price)} совпадает с активной акцией; "
            f"маржа {_fmt_percent(economics['margin'])} при {deliveries}{partial}."
        )
    elif price_action == "ПОДНЯТЬ":
        reason = f"{price_reason}; тестовая цена, экономика после изменения требует проверки."
    elif price_action == "СНИЗИТЬ":
        reason = f"{price_reason}; оценочная маржа теста {_fmt_percent(test_estimate['margin'])}."
    else:
        reason = f"{price_reason}; {promo_reason}."
    return {
        "price": price_action,
        "test_price": test_price,
        "delta": delta,
        "delta_percent": delta_percent,
        "actual_price": actual_price,
        "active_promo_price": active_price,
        "candidate_promo_price": None if candidate_estimate is None else candidate_estimate["price"],
        "candidate_promo_margin": None if candidate_estimate is None else candidate_estimate["margin"],
        "test_margin": None if test_estimate is None else test_estimate["margin"],
        "promotion": promo_action,
        "promotion_reason": promo_reason,
        "margin": economics["margin"],
        "confidence": economics["confidence"],
        "confirmed_units": economics["confirmed_units"],
        "partial_economics": economics["partial"],
        "reason": reason,
    }


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
            and int(row.get("orders_count") or 0) >= MIN_LOGISTICS_ORDERS
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
            "неполные окна могут искажать недельное сравнение продаж", False,
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
        "# AI Analyst v1.3 — Price Decision v1",
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
            f"- Акции/CPC: активных акций {len(promo['active'])}, кандидатов {len(promo['candidates'])} (наблюдение {_observed_date(promo['observed_at']) or 'н/д'}); CPC {cpc_text}.",
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
        economics = _economics(perf)
        commercial = product["commercial"]
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
            f"- Продвижение: активных акций {len(promo['active'])}, кандидатов {len(promo['candidates'])}; наблюдение: {_observed_date(promo['observed_at']) or 'н/д'}.",
            f"- Региональная логистика: маршрутов {logistics.get('routes', 0)}, заказов {logistics.get('orders', 0)}, взвешенная ставка {_fmt_percent(logistics.get('rate'))}; данные по {_observed_date(logistics.get('data_through')) or 'н/д'}.",
            "",
            "#### PRICE DECISION V1",
            "",
            f"- Текущая цена: **{_fmt_money(product.get('current_price'))}**.",
            f"- Фактическая цена продажи / цена активной акции: **{_fmt_money(commercial['actual_price'])} / {_fmt_money(commercial['active_promo_price'])}**.",
            f"- Рекомендация по цене: **{commercial['price']}**.",
            f"- Рекомендуемая тестовая цена: **{_fmt_money(commercial['test_price'])}**.",
            f"- Изменение: **{_fmt_signed_money(commercial['delta'])} / {_fmt_percent(commercial['delta_percent'], True)}**.",
            f"- Рекомендация по акции: **{commercial['promotion']}**.",
            f"- Расчётная текущая маржа: **{_fmt_percent(commercial['margin'])}** до налога; подтверждено доставок: **{int(commercial['confirmed_units'])}**.",
            f"- Уверенность: **{commercial['confidence']}**.",
            f"- Причина: {commercial['reason']}",
            "",
            "#### ФАКТЫ ЭКОНОМИКИ И АКЦИЙ",
            "",
            f"- Последнее изменение базовой цены: **{_fmt_percent(price_change, True)}** ({_fmt_money((product.get('price_history') or {}).get('absolute_change'))}).",
            f"- Интервал текущей базовой цены: с **{_observed_date(product.get('current_price_since')) or 'н/д'}**; подтверждено на интервале **{_fmt_number(product.get('confirmed_units_at_current_price'))} шт.**; status `{product.get('current_price_economics_status') or 'н/д'}`.",
            f"- Себестоимость единицы: **{_fmt_money(product.get('cost_price'))}** ({product.get('cost_basis') or 'н/д'}).",
            f"- Расходы Ozon за текущее 7-дневное окно: комиссия **{_fmt_money(perf['commission'] if perf['matched'] else None)}**, логистика **{_fmt_money(perf['logistics'] if perf['matched'] else None)}**, прочие **{_fmt_money(perf['other_expenses'] if perf['matched'] else None)}**; подтверждено {int(perf['matched'])}/{int(perf['delivered'])} доставленных единиц.",
            f"- Фактическая выплата Ozon: **{_fmt_money(perf['payout'] if perf['matched'] else None)}**; прибыль до налога берётся из существующего `profit_before_tax`, а не пересчитывается панелью.",
            f"- CPC: **{_fmt_money(cpc['spend'] if cpc['days'] else None)}** за {len(cpc['days'])}/7 дней; в подтверждённую прибыль доставки не включён, потому что view не распределяет CPC по единице.",
            f"- Подтверждённая прибыль до налога/маржа: **{_fmt_money(economics['profit'])} / {_fmt_percent(economics['margin'])}**; уверенность определяется по {int(economics['confirmed_units'])} подтверждённым доставкам.",
            f"- Оценка маржи тестовой цены: **{_fmt_percent(commercial['test_margin'])}** — при текущей фактической доле комиссии и фактических расходах на единицу; после изменения требует проверки.",
            f"- Активные: {_promotion_text(promo['active'])}.",
            f"- Кандидатные: {_promotion_text(promo['candidates'], candidate=True)}.",
            f"- Лучшая доступная оценка кандидатной цены/маржи: **{_fmt_money(commercial['candidate_promo_price'])} / {_fmt_percent(commercial['candidate_promo_margin'])}**; это оценка без предположения об uplift.",
            f"- Основание по акции: {commercial['promotion_reason']}.",
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
        "## Правила Price Decision v1",
        "",
        "Маржа до налога: минимум 10%, комфортная 15%; тестовый шаг 3%, максимум 5%, округление до 5 ₽. "
        "Уверенность: 1 доставка — НИЗКАЯ, 2 — СРЕДНЯЯ, 3 и более — ВЫСОКАЯ; при 0 экономика н/д. "
        "Поднять: сильная часть продаж, достаточный запас, без подтверждённого ухудшения логистики и маржа ≥10%; "
        "при марже <10% используется защитный тест не более +5%. Снизить: только при подтверждённом ухудшении спроса, "
        "достаточном запасе, отсутствии логистической причины и оценочной марже теста ≥10%. Неполное предыдущее окно "
        "не блокирует фактическую экономику и ценовое решение. Фактическая акционная доставка приоритетнее базовой цены; "
        "кандидат оценивается по текущей фактической доле комиссии и расходам на единицу без предположения об uplift. "
        "CPC включается только при фактической привязке к единице; здесь он не распределён. Скрипт работает только READ + PROPOSE и ничего не изменяет.",
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
            sales_ranked = sorted(
                products,
                key=lambda product: (-product["performance"]["current"]["units"], product["offer_id"]),
            )
            for rank, product in enumerate(sales_ranked, 1):
                product["sales_rank"] = rank
                product["sales_product_count"] = len(sales_ranked)
            for product in products:
                product["commercial"] = _commercial_recommendation(product, current_end)
            return _render(products, current_start, current_end, previous_start, previous_end, limit)
    finally:
        await connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="EFA deterministic AI Analyst v1.3 / Price Decision v1")
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 51), metavar="1..50")
    args = parser.parse_args()
    try:
        print(asyncio.run(_run(args.limit)))
        return 0
    except SafeReportError as exc:
        print(f"AI Analyst v1.3: {exc}", file=sys.stderr)
    except Exception:
        print("AI Analyst v1.3: read-only report failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
