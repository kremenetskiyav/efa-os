"""Pure deterministic assembly for Daily Commercial Brief v0.1."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

MOSCOW = timezone(timedelta(hours=3))


def last_completed_business_date(now: datetime | None = None) -> date:
    value = now.astimezone(MOSCOW) if now is not None else datetime.now(MOSCOW)
    return value.date() - timedelta(days=1)


def _decimal(value: Any) -> str | None:
    return None if value is None else format(value, "f") if isinstance(value, Decimal) else str(value)


def _date(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _index(rows: list[tuple[Any, ...]], key: int = 0) -> dict[Any, tuple[Any, ...]]:
    return {row[key]: row for row in rows}


def _group(rows: list[tuple[Any, ...]]) -> dict[str, list[tuple[Any, ...]]]:
    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(row)
    return grouped


def _quality(freshness: tuple[Any, ...], business_date: date, generated_at: datetime) -> tuple[dict[str, Any], list[str]]:
    demand_date, promotion_at, cpc_date, finance_delivery_at, price_at = freshness
    warnings: list[str] = []
    if demand_date != business_date:
        warnings.append("seller_daily_missing_or_stale_for_business_date")
    if cpc_date != business_date:
        warnings.append("cpc_daily_missing_or_stale_for_business_date")
    if promotion_at is None:
        warnings.append("promotion_state_missing")
    elif _utc(promotion_at) < _utc(generated_at) - timedelta(hours=12):
        warnings.append("promotion_state_stale")
    if finance_delivery_at is None or finance_delivery_at.date() < business_date:
        warnings.append("confirmed_finance_not_available_for_business_date")
    if price_at is None:
        warnings.append("price_state_missing")
    elif _utc(price_at) < _utc(generated_at) - timedelta(hours=48):
        warnings.append("price_state_stale")
    status = "review" if warnings else "valid"
    return {
        "status": status,
        "sources": {
            "seller_daily": _date(demand_date), "promotions": _date(promotion_at),
            "cpc": _date(cpc_date), "confirmed_finance_delivery": _date(finance_delivery_at),
            "price": _date(price_at),
        },
        "missing_sources": sorted(warnings), "warnings": sorted(warnings),
    }, warnings


def build_brief(sources: dict[str, Any], business_date: date, generated_at: datetime | None = None) -> dict[str, Any]:
    generated = generated_at or datetime.now(timezone.utc)
    demand = _index(sources["demand"])
    deliveries = _index(sources["deliveries"])
    returns = _index(sources["returns"])
    finance = _index(sources["finance"])
    promotion_rows = _group(sources["promotions"])
    cpc_rows = _group(sources["cpc"])
    current_price_status = _index(sources["current_price_status"])
    latest_economics = _index(sources.get("latest_economics", []))
    quality, global_warnings = _quality(sources["freshness"], business_date, generated)
    offers: list[dict[str, Any]] = []
    for offer_id, sku, product_id, price, cost_price, price_at in sources["products"]:
        demand_row, delivery_row = demand.get(offer_id), deliveries.get(offer_id)
        return_row, finance_row = returns.get(offer_id), finance.get(offer_id)
        promo = promotion_rows.get(offer_id, [])
        participating = [row for row in promo if row[4] == "PARTICIPATING"]
        candidates = [row for row in promo if row[4] == "CANDIDATE"]
        cpc = cpc_rows.get(offer_id, [])
        ordered_revenue = demand_row[2] if demand_row else None
        ordered_units = demand_row[3] if demand_row else None
        confirmed_revenue = finance_row[1] if finance_row else None
        profit = finance_row[2] if finance_row else None
        confirmed_units = finance_row[3] if finance_row else None
        margin = (profit / confirmed_revenue * Decimal("100")) if profit is not None and confirmed_revenue else None
        profit_per_unit = (profit / confirmed_units) if profit is not None and confirmed_units else None
        latest_row = latest_economics.get(offer_id)
        latest_revenue = latest_row[2] if latest_row else None
        latest_profit = latest_row[3] if latest_row else None
        latest_units = latest_row[4] if latest_row else None
        reasons: list[str] = []
        if not demand_row:
            reasons.append("seller_daily_missing_or_stale_for_business_date")
        if not finance_row:
            reasons.append("confirmed_finance_not_available_for_business_date")
        if any(row[9] != "valid" for row in promo):
            reasons.append("promotion_data_quality_review")
        if any(row[9] != "valid" for row in cpc):
            reasons.append("cpc_data_quality_review")
        level = "WATCH" if reasons else "NO_ACTION"
        offers.append({
            "offer_id": offer_id, "sku": sku, "product_id": product_id, "cost_price": _decimal(cost_price),
            "price": {"current_price": _decimal(price), "observed_at": _date(price_at)},
            "demand": {"ordered_revenue": _decimal(ordered_revenue), "ordered_units": ordered_units,
                       "status": demand_row[5] if demand_row else "NOT_AVAILABLE"},
            "fulfilment": {"delivered_units": delivery_row[1] if delivery_row else None,
                            "cancelled_units": None, "return_events": return_row[1] if return_row else None,
                            "returned_units": return_row[2] if return_row else None,
                            "buyout_units": None, "buyout_status": "NOT_IMPLEMENTED"},
            "economics": {"confirmed_revenue": _decimal(confirmed_revenue),
                          "profit_before_tax": _decimal(profit), "confirmed_margin_percent": _decimal(margin),
                          "profit_per_unit": _decimal(profit_per_unit),
                          "current_price_economics_status": current_price_status.get(offer_id, (None, "REVIEW_DATA"))[1],
                          "temporal_semantics": "delivery_date_confirmed_finance"},
            "latest_confirmed_economics": {
                "confirmed_through_date": _date(latest_row[1]) if latest_row else None,
                "confirmed_revenue": _decimal(latest_revenue),
                "profit_before_tax": _decimal(latest_profit),
                "confirmed_margin_percent": _decimal(latest_profit / latest_revenue * Decimal("100")) if latest_profit is not None and latest_revenue else None,
                "profit_per_unit": _decimal(latest_profit / latest_units) if latest_profit is not None and latest_units else None,
                "delivered_units": latest_units,
                "return_events": latest_row[5] if latest_row else None,
                "returned_units": latest_row[6] if latest_row else None,
                "data_quality_status": "review" if latest_row and latest_row[7] else "valid" if latest_row else "NOT_AVAILABLE",
            },
            "promotions": {"participating": [_promotion(row) for row in participating],
                           "candidates": [_promotion(row) for row in candidates],
                           "status": "NOT_AVAILABLE" if not promo else "valid" if all(row[9] == "valid" for row in promo) else "review"},
            "advertising": {"cpc": [_cpc(row) for row in cpc],
                            "status": "NOT_AVAILABLE" if not cpc else "valid" if all(row[9] == "valid" for row in cpc) else "review",
                            "inactive_attribution_note": "orders_are_attributed_history_not_current_activity" if any(row[2] == "CAMPAIGN_STATE_INACTIVE" and row[7] > 0 for row in cpc) else None},
            "attention": {"level": level, "reasons": sorted(set(reasons))},
        })
    summary = _summary(offers)
    latest_summary = _latest_summary(offers)
    trends = _serialize_trends(sources.get("trends", {}))
    brief = {"business_date": business_date.isoformat(), "generated_at": generated.isoformat(),
             "timezone": "Europe/Moscow", "read_only": True, "tax_status": "NOT_IMPLEMENTED",
             "data_quality": quality, "summary": summary,
             "latest_confirmed_economics": latest_summary, "offers": offers}
    brief["extended_report_payload"] = {"business_date": brief["business_date"], "generated_at": brief["generated_at"],
                                        "timezone": brief["timezone"], "summary": summary,
                                        "latest_confirmed_economics": latest_summary,
                                        "offers": offers, "warnings": global_warnings, "trends": trends,
                                        "tax_status": brief["tax_status"]}
    brief["compact_report_payload"] = _compact(brief)
    return brief


def _promotion(row: tuple[Any, ...]) -> dict[str, Any]:
    return {"action_id": row[1], "action_title": row[2], "action_type": row[3], "source_list_type": row[4],
            "action_price": _decimal(row[5]), "current_boost": _decimal(row[6]), "min_boost": _decimal(row[7]),
            "max_boost": _decimal(row[8]), "data_quality_status": row[9], "collected_at": _date(row[10])}


def _cpc(row: tuple[Any, ...]) -> dict[str, Any]:
    return {"campaign_id": row[1], "campaign_state": row[2], "campaign_type": row[3],
            "spend": _decimal(row[4]), "views": row[5], "clicks": row[6], "orders": row[7],
            "orders_money": _decimal(row[8]), "data_quality_status": row[9]}


def _sum_decimal(values: list[str | None]) -> Decimal | None:
    present = [Decimal(value) for value in values if value is not None]
    return sum(present, Decimal("0")) if present else None


def _summary(offers: list[dict[str, Any]]) -> dict[str, Any]:
    ordered_revenue = _sum_decimal([item["demand"]["ordered_revenue"] for item in offers])
    profit = _sum_decimal([item["economics"]["profit_before_tax"] for item in offers])
    revenue = _sum_decimal([item["economics"]["confirmed_revenue"] for item in offers])
    cpc_spend = _sum_decimal([entry["spend"] for item in offers for entry in item["advertising"]["cpc"]])
    return {"ordered_revenue": _decimal(ordered_revenue),
            "ordered_units": sum(item["demand"]["ordered_units"] or 0 for item in offers) if any(item["demand"]["ordered_units"] is not None for item in offers) else None,
            "delivered_units": sum(item["fulfilment"]["delivered_units"] or 0 for item in offers) if any(item["fulfilment"]["delivered_units"] is not None for item in offers) else None,
            "returned_units": sum(item["fulfilment"]["returned_units"] or 0 for item in offers) if any(item["fulfilment"]["returned_units"] is not None for item in offers) else None,
            "confirmed_revenue": _decimal(revenue), "profit_before_tax": _decimal(profit),
            "margin_percent": _decimal(profit / revenue * Decimal("100")) if profit is not None and revenue else None,
            "cpc_spend": _decimal(cpc_spend),
            "offers_action": sum(item["attention"]["level"] in ("ACTION", "CRITICAL") for item in offers),
            "offers_watch": sum(item["attention"]["level"] == "WATCH" for item in offers)}


def _latest_summary(offers: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [item["latest_confirmed_economics"] for item in offers]
    dates = sorted({row["confirmed_through_date"] for row in rows if row["confirmed_through_date"]})
    revenue = _sum_decimal([row["confirmed_revenue"] for row in rows])
    profit = _sum_decimal([row["profit_before_tax"] for row in rows])
    units = sum(row["delivered_units"] or 0 for row in rows) if any(row["delivered_units"] is not None for row in rows) else None
    return {"confirmed_through_date": dates[-1] if dates else None,
            "confirmed_revenue": _decimal(revenue), "profit_before_tax": _decimal(profit),
            "margin_percent": _decimal(profit / revenue * Decimal("100")) if profit is not None and revenue else None,
            "profit_per_unit": _decimal(profit / units) if profit is not None and units else None,
            "delivered_units": units,
            "return_events": sum(row["return_events"] or 0 for row in rows) if any(row["return_events"] is not None for row in rows) else None,
            "returned_units": sum(row["returned_units"] or 0 for row in rows) if any(row["returned_units"] is not None for row in rows) else None}


def _serialize_trends(trends: dict[str, list[tuple[Any, ...]]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "demand": [{"offer_id": row[0], "business_date": _date(row[1]), "ordered_revenue": _decimal(row[2]), "ordered_units": row[3]} for row in trends.get("demand", [])],
        "price": [{"offer_id": row[0], "observed_at": _date(row[1]), "price": _decimal(row[2])} for row in trends.get("price", [])],
        "boost": [{"offer_id": row[0], "observed_at": _date(row[1]), "current_boost": _decimal(row[2])} for row in trends.get("boost", [])],
        "finance": [{"offer_id": row[0], "business_date": _date(row[1]), "confirmed_revenue": _decimal(row[2]),
                     "profit_before_tax": _decimal(row[3]),
                     "margin_percent": _decimal(row[3] / row[2] * Decimal("100")) if row[2] else None}
                    for row in trends.get("finance", [])],
    }


def _compact(brief: dict[str, Any]) -> dict[str, Any]:
    offers = []
    for item in brief["offers"]:
        if item["attention"]["level"] == "NO_ACTION":
            continue
        latest = item["latest_confirmed_economics"]
        offers.append({"offer_id": item["offer_id"], "ordered_units": item["demand"]["ordered_units"],
                       "delivered_units": item["fulfilment"]["delivered_units"],
                       "returned_units": item["fulfilment"]["returned_units"], "ordered_revenue": item["demand"]["ordered_revenue"],
                       "confirmed_through_date": latest["confirmed_through_date"],
                       "profit_before_tax": latest["profit_before_tax"],
                       "margin_percent": latest["confirmed_margin_percent"], "attention": item["attention"]})
    return {"business_date": brief["business_date"], "summary": brief["summary"],
            "latest_confirmed_economics": brief["latest_confirmed_economics"], "offers": offers,
            "warnings": brief["data_quality"]["warnings"]}
