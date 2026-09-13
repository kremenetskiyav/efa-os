"""Period-aware financial presentation. No new profit or allocation formulas.

Amounts are copied from bounded sources. Decimal arithmetic is limited to
totalling named expense lines and reconciling portfolio/SKU observations.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from read_model import Document, SKUS, sku_id, latest, safe_source, timestamp, FRESHNESS

MOSCOW = timezone(timedelta(hours=3))
MODES = {"OBSERVED", "SETTLEMENT_AWARE", "LEGACY_FORECAST", "SELLER_SIDE_PROXY",
         "MIXED_OBSERVED_PROXY", "INSUFFICIENT_DATA"}
METRICS = (
    "seller_realization", "ordered_revenue", "ordered_units", "delivered_units",
    "returned_units", "buyer_returned_units", "logistic_return_units",
    "net_sold_units", "cogs", "commission", "logistics",
    "acquiring", "processing", "last_mile", "return_logistics", "return_processing",
    "other_costs", "ozon_expenses", "advertising", "contribution_before_ads",
    "margin_before_ads", "contribution", "margin", "profit_before_tax",
    "settlement_profit", "proxy_result", "premium", "tax", "corrections",
)
EXPENSES = ("commission", "logistics", "acquiring", "processing", "last_mile",
            "return_logistics", "return_processing", "other_costs")
COST_COLUMNS = {"Commission": "commission", "Acquiring": "acquiring",
    "Forward logistics": "logistics", "Return logistics": "return_logistics",
    "Last mile": "last_mile", "Processing": "processing",
    "Return processing": "return_processing", "Other attributable": "other_costs",
    "COGS proxy": "cogs"}


def period_options(now):
    today = now.astimezone(MOSCOW).date()
    completed = today - timedelta(days=1)
    month_start = today.replace(day=1)
    previous_end = month_start - timedelta(days=1)
    ranges = [
        ("today", "Сегодня", today, today),
        ("yesterday", "Вчера", today-timedelta(days=1), today-timedelta(days=1)),
        ("last7", "7 дней", today-timedelta(days=7), completed),
        ("last30", "30 дней", today-timedelta(days=29), today),
        ("this_month", "Этот месяц", month_start, completed),
        ("previous_month", "Прошлый месяц", previous_end.replace(day=1), previous_end),
        ("august2026", "Август 2026", date(2026,8,1), date(2026,8,31)),
    ]
    return [{"id": key, "label": label, "from": start.isoformat(), "to": end.isoformat()}
            for key, label, start, end in ranges]


def amount(text):
    """Known English-format W06 numeric cells, not arbitrary report prose."""
    value = str(text).strip().replace("`", "").replace("**", "")
    value = value.split("₽")[0].split("%")[0].strip().replace(",", "").replace(" ", "")
    try:
        number = Decimal(value)
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def decimal_value(metric):
    value = metric.get("value")
    return Decimal(str(value)) if value is not None else None


def metric(value, period, *, source=None, mode="OBSERVED", observed_at=None,
           scope=None, cohort="accrual_date", settlement_status="INSUFFICIENT_SETTLEMENT_DATA"):
    return {"value": str(value) if value is not None else None,
        "period": {"from": period["from"], "to": period["to"]}, "mode": mode,
        "source": source, "observed_at": observed_at, "freshness": "UNKNOWN",
        "confidence": "SOURCE_REPORTED" if source else "UNKNOWN",
        "settlement_status": settlement_status, "cohort": cohort, "scope": scope}


def blank(period):
    return {"period": period, "available": False,
        "portfolio": {key: metric(None, period) for key in METRICS},
        "skus": [{"sku": sku, "metrics": {key: metric(None, period) for key in METRICS}} for sku in SKUS],
        "reconciliation": [], "sources": [],
        "data_gaps": ["Нет проверенного финансового источника за выбранный период. Данные другого периода не подставляются."]}


def add_known(metrics, keys):
    values = [decimal_value(metrics[key]) for key in keys]
    return sum(values, Decimal(0)) if all(v is not None for v in values) else None


def reconcile(view):
    """No allocation: expose same-metric totals, residuals and missing coverage."""
    result = []
    for key in ("seller_realization", "ordered_units", "ozon_expenses", "advertising", "contribution", "proxy_result"):
        total_metric = view["portfolio"][key]
        total = decimal_value(total_metric)
        metrics = [row["metrics"][key] for row in view["skus"]]
        values = [decimal_value(m) for m in metrics]
        comparable = all(m["period"] == total_metric["period"] and m["cohort"] == total_metric["cohort"] and m["mode"] == total_metric["mode"] for m in metrics)
        sku_sum = sum(values, Decimal(0)) if comparable and all(v is not None for v in values) else None
        delta = total - sku_sum if total is not None and sku_sum is not None else None
        result.append({"metric": key, "portfolio": str(total) if total is not None else None,
            "sku_sum": str(sku_sum) if sku_sum is not None else None,
            "difference": str(delta) if delta is not None else None,
            "status": "INSUFFICIENT_DATA" if delta is None else "PASS" if delta == 0 else "GAP",
            "coverage": sum(v is not None for v in values)})
    return result


def august_view(doc, period):
    view = blank(period)
    rows = {p["sku"]: p["metrics"] for p in view["skus"]}
    total = view["portfolio"]
    common = {"source": doc.source, "observed_at": doc.date,
              "scope": "Август 2026; операции Ozon по дате начисления. Финальный финансовый результат не подтверждён."}
    proxy_scope = "Август 2026; текущая себестоимость как допущение. До налогов, Premium и поздних корректировок; не чистая прибыль."

    def put(target, key, value, mode="SETTLEMENT_AWARE", scope=None):
        target[key] = metric(value, period, **{**common, "mode": mode, "scope": scope or common["scope"]},
                             cohort="order_date" if key in {"ordered_units", "ordered_revenue"} else "accrual_date")

    for row in doc.rows("SKU", "Ordered units / ordered revenue", "Proxy contribution after matched CPC", "Seller realization"):
        sku = sku_id(row["SKU"])
        target = rows.get(sku) if sku else total if row["SKU"] == "Portfolio" else None
        if target is None:
            continue
        ordered = row["Ordered units / ordered revenue"].split(" / ")
        delivered = row["Delivered / returned / net units"].split(" / ")
        if len(ordered) == 2:
            for key, val in zip(("ordered_units", "ordered_revenue"), ordered):
                put(target, key, amount(val), "OBSERVED", "Количество и сумма заказанных товаров по дате заказа; отдельная выборка от доставок и начислений.")
        if len(delivered) == 3:
            for key, val in zip(("delivered_units", "returned_units", "net_sold_units"), delivered):
                put(target, key, amount(val))
        put(target, "seller_realization", amount(row["Seller realization"]))
        before = row["Proxy contribution before advertising"].split(" / ")
        if len(before) == 2:
            put(target, "contribution_before_ads", amount(before[0]), "SELLER_SIDE_PROXY", proxy_scope)
            put(target, "margin_before_ads", amount(before[1]), "SELLER_SIDE_PROXY", proxy_scope)
        put(target, "advertising", amount(row["Settlement-matched SKU CPC"]), scope="Только сопоставленный со SKU CPC; нераспределённая реклама исключена.")
        if sku:
            for key, val in (("contribution", row["Proxy contribution after matched CPC"]),
                             ("margin", row["Proxy margin after matched CPC"]),
                             ("proxy_result", row["Proxy contribution after matched CPC"])):
                put(target, key, amount(val), "SELLER_SIDE_PROXY", proxy_scope + " Нераспределённая реклама и другие общие расходы исключены.")

    for row in doc.rows("SKU", "Commission", "COGS proxy", "Other attributable"):
        sku = sku_id(row["SKU"])
        target = rows.get(sku) if sku else total if row["SKU"] == "Total" else None
        if target is not None:
            for column, key in COST_COLUMNS.items():
                put(target, key, amount(row.get(column)), "SELLER_SIDE_PROXY" if key == "cogs" else "SETTLEMENT_AWARE",
                    proxy_scope if key == "cogs" else None)
            put(target, "ozon_expenses", add_known(target, EXPENSES), scope="Сумма названных расходов Ozon: комиссия, доставка, эквайринг, обработка, последняя миля, возвраты и другие расходы. Без рекламы и Premium.")

    components = {row["Component"]: amount(row["August observed amount"])
                  for row in doc.rows("Component", "August observed amount", "Allocation status")}
    cpc, cpo = components.get("CPC"), components.get("CPO")
    view["advertising_components"] = {
        "cpc": str(cpc) if cpc is not None else None,
        "cpo": str(cpo) if cpo is not None else None,
        "source": doc.source,
    }
    if cpc is not None and cpo is not None:
        put(total, "advertising", cpc+cpo, scope="Полная сумма CPC + CPO по августовским операциям, включая расходы без подтверждённого распределения по SKU.")
    put(total, "premium", components.get("Premium subscription"), scope="Расход аккаунта; не распределён по SKU и не вычтен из показанного маржинального дохода.")
    unallocated_other = components.get("Other account-level charge")
    if unallocated_other is not None and decimal_value(total["other_costs"]) is not None:
        put(total, "other_costs", decimal_value(total["other_costs"])+unallocated_other,
            scope="Известные прочие расходы по SKU плюс общая нераспределённая строка аккаунта.")
        put(total, "ozon_expenses", add_known(total, EXPENSES), scope="Известные расходы Ozon без рекламы и Premium; включает общую нераспределённую строку.")
    # Exact named metadata field already supported in V2. Not a recomputation.
    final = doc.get("Confirmed portfolio result after CPC+CPO", default="").split(" / ")
    if len(final) == 2:
        put(total, "contribution", amount(final[0]), "SELLER_SIDE_PROXY", proxy_scope + " После полной рекламы и нераспределённой прочей строки.")
        put(total, "proxy_result", amount(final[0]), "SELLER_SIDE_PROXY", proxy_scope + " Совпадает с маржинальным доходом, не является отдельной прибылью.")
        put(total, "margin", amount(final[1]), "SELLER_SIDE_PROXY", proxy_scope)
    view["available"] = any(m["value"] is not None for m in total.values())
    view["sources"] = [doc.source]
    view["data_gaps"] = [
        "Финансовые данные августа закрыты не полностью: прибыль после всех расходов и налогов не подтверждена.",
        "Использована текущая себестоимость; история себестоимости на даты августа отсутствует.",
        "Часть CPC, весь CPO и общая строка расходов не распределены по SKU. Разница показана в сверке.",
        "Заказы относятся к дате заказа, выручка и доставки — к августовским начислениям. Это разные выборки.",
        "Налоги, внутренние переменные расходы и последующие корректировки не подтверждены. Premium показан отдельно.",
    ]
    view["reconciliation"] = reconcile(view)
    gaps = {r["metric"]: r for r in view["reconciliation"]}
    ad_gap = gaps["advertising"]["difference"]
    contribution_gap = gaps["contribution"]["difference"]
    residual = (Decimal(contribution_gap) + Decimal(ad_gap) + unallocated_other
                if contribution_gap is not None and ad_gap is not None and unallocated_other is not None else None)
    view["bridge"] = {"unallocated_advertising": ad_gap,
        "unallocated_other": str(unallocated_other) if unallocated_other is not None else None,
        "unexplained_difference": str(residual) if residual is not None else None,
        "status": "PASS" if residual == 0 else "GAP" if residual is not None else "INSUFFICIENT_DATA"}
    return view


def validate_snapshot_metric(value, period, now):
    if not isinstance(value, dict) or value.get("period") != {"from": period["from"], "to": period["to"]}:
        raise ValueError("exact metric period required")
    if value.get("mode") not in MODES or value.get("freshness") not in FRESHNESS:
        raise ValueError("mode/freshness")
    if not safe_source(value.get("source")) or timestamp(value["observed_at"]) > now:
        raise ValueError("provenance")
    if not value.get("confidence") or not value.get("settlement_status") or value.get("cohort") not in {"order_date", "accrual_date", "order_cohort", "forecast"}:
        raise ValueError("financial semantics")
    raw = value.get("value")
    if isinstance(raw, bool):
        raise ValueError("numeric value")
    number = Decimal(str(raw)) if raw is not None else None
    if number is not None and not number.is_finite():
        raise ValueError("finite value")
    return {**value, "value": str(number) if number is not None else None}


def build_finance(root, now=None):
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    options = period_options(now)
    views = {p["id"]: blank(p) for p in options}
    finance_root = root.parent / "REPORTS"
    doc = latest([Document(p, root) for p in finance_root.glob("W06/AUDIT/*/W06_EFA_ALL_SKU_AUGUST_UNIT_ECONOMICS_AUDIT_*.md")
                  if p.is_file() and p.resolve().is_relative_to(finance_root.resolve())])
    for key, view in views.items():
        p = view["period"]
        if doc and key == "august2026" and p["from"] == "2026-08-01" and p["to"] == "2026-08-31":
            # Report scope is required, not inferred from filename alone.
            if doc.get("Period") == "2026-08-01 — 2026-08-31":
                views[key] = august_view(doc, p)
    issues = []
    path = root / "CONTROL_CENTER_FINANCE_V3.json"
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if payload["schema_version"] != "efa.control_center.finance.v3" or timestamp(payload["observed_at"]) > now or timestamp(payload["valid_until"]) <= now:
                raise ValueError("envelope")
            staged = {}
            if not isinstance(payload["periods"], list):
                raise ValueError("period list")
            for item in payload["periods"]:
                matches = [p for p in options if item["period"] == {"from": p["from"], "to": p["to"]}]
                if not matches:
                    raise ValueError("unsupported period")
                for period in matches:
                    view = blank(period)
                    if period["id"] in staged or set(item.get("portfolio", {})) - set(METRICS):
                        raise ValueError("duplicate period or unsupported financial metric")
                    for key, value in item.get("portfolio", {}).items():
                        view["portfolio"][key] = validate_snapshot_metric(value, period, now)
                    seen = set()
                    for row in item.get("skus", []):
                        if row["sku"] not in SKUS or row["sku"] in seen or set(row["metrics"]) - set(METRICS):
                            raise ValueError("SKU metrics")
                        seen.add(row["sku"])
                        target = next(p["metrics"] for p in view["skus"] if p["sku"] == row["sku"])
                        for key, value in row["metrics"].items():
                            target[key] = validate_snapshot_metric(value, period, now)
                    for metrics in [view["portfolio"], *(r["metrics"] for r in view["skus"])]:
                        profit = metrics["settlement_profit"]
                        if profit["value"] is not None and (profit["mode"] != "SETTLEMENT_AWARE" or profit["settlement_status"] not in {"FINAL_SETTLEMENT", "CORRECTED_FINAL_SETTLEMENT"}):
                            raise ValueError("final profit requires final source")
                    view["available"] = any(m["value"] is not None for m in view["portfolio"].values())
                    view["data_gaps"] = [] if view["available"] else view["data_gaps"]
                    view["sources"] = sorted({m["source"] for metrics in [view["portfolio"], *(r["metrics"] for r in view["skus"])] for m in metrics.values() if m["source"]})
                    view["reconciliation"] = reconcile(view)
                    staged[period["id"]] = view
            views.update(staged)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, InvalidOperation):
            issues.append("Финансовый снимок отклонён: неверный период, источник, срок актуальности или семантика показателя. Частичные изменения не применены.")
    if not views["this_month"]["available"]:
        issues.append("Текущий финансовый результат не подтверждён. Нужен проверенный периодный финансовый снимок; прежняя прибыль до налога не подставляется вместо текущей.")
    default = "this_month"
    return {"schema_version": "efa.control_center.finance.v3", "periods": options,
        "default_period": default, "views": views, "data_gaps": issues,
        "sources": sorted({s for v in views.values() for s in v["sources"]})}
