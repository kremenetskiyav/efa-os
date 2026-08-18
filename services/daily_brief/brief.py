"""Pure deterministic assembly for Daily Commercial Brief v1.1."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

MOSCOW = timezone(timedelta(hours=3))
ATTENTION_CLASSES = (
    "ANOMALY", "DATA_QUALITY", "WATCH", "ACTION_REQUIRED",
    "INFORMATION_EVENT", "EXPERIMENT_ALERT",
)
_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


def last_completed_business_date(now: datetime | None = None) -> date:
    value = now.astimezone(MOSCOW) if now is not None else datetime.now(MOSCOW)
    return value.date() - timedelta(days=1)


def _decimal(value: Any) -> str | None:
    return None if value is None else format(value, "f") if isinstance(value, Decimal) else str(value)


def _date(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _index(rows: list[tuple[Any, ...]], key: int = 0) -> dict[Any, tuple[Any, ...]]:
    return {row[key]: row for row in rows}


def _group(rows: list[tuple[Any, ...]]) -> dict[str, list[tuple[Any, ...]]]:
    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(row)
    return grouped


def _cpc_state(run: tuple[Any, ...] | None) -> str:
    if run is None:
        return "MISSING"
    status = str(run[0] or "").upper()
    records = int(run[1] or 0)
    lifecycle = str(run[5] or "").upper()
    if lifecycle == "STUCK" or status == "STUCK":
        return "STUCK"
    if lifecycle == "FAILED" or status == "FAILED":
        return "FAILED"
    if lifecycle == "PENDING":
        return "PENDING"
    if lifecycle in {"COMPLETE", "COMPLETED", "SUCCESS"} or status == "SUCCESS":
        return "SUCCESS_ZERO" if records == 0 else "SUCCESS_NONZERO"
    return "MISSING"


def _map_run_state(run: tuple[Any, ...] | None, business_date: date) -> str:
    if run is None or run[1] is None:
        return "missing"
    run_date, status, records = run[1], str(run[2] or "").upper(), int(run[3] or 0)
    if status == "FAILED":
        return "failed"
    if run_date != business_date:
        return "stale"
    if status == "SUCCESS_ZERO" or (status == "SUCCESS" and records == 0):
        return "success_zero"
    return "fresh" if status == "SUCCESS" else "missing"


def _source_freshness(sources: dict[str, Any], business_date: date) -> dict[str, dict[str, Any]]:
    products = sources["products"]
    demand = sources["demand"]
    demand_valid = demand and len({row[0] for row in demand}) == len(products) and all(row[5] == "valid" for row in demand)
    seller_state = "fresh" if demand_valid else "failed" if demand else "missing"
    seller_ref = sorted({row[6] for row in demand if len(row) > 6 and row[6]})
    result: dict[str, dict[str, Any]] = {
        "seller_analytics": {
            "state": seller_state, "business_date": business_date.isoformat() if demand else None,
            "records_count": len(demand), "collection_ref": seller_ref[0] if len(seller_ref) == 1 else None,
        }
    }
    operational = {row[0]: row for row in sources.get("operational_runs", [])}
    for source in ("POSTINGS", "RETURNS", "FINANCE"):
        row = operational.get(source)
        result[source.lower()] = {
            "state": _map_run_state(row, business_date),
            "business_date": _date(row[1]) if row and row[1] else None,
            "records_count": row[3] if row else None, "pages_count": row[4] if row else None,
            "completed_at": _date(row[5]) if row and row[5] else None,
            "collection_ref": row[6] if row else None, "error": row[7] if row else None,
        }
    cpc_run = sources.get("cpc_collection")
    cpc_state = _cpc_state(cpc_run)
    result["cpc"] = {
        "state": cpc_state.lower(), "business_date": business_date.isoformat(),
        "records_count": cpc_run[1] if cpc_run else None,
        "lifecycle_state": cpc_run[5] if cpc_run else None,
        "external_state": cpc_run[6] if cpc_run else None,
        "error_code": cpc_run[7] if cpc_run else None,
        "error": cpc_run[8] if cpc_run else None,
        "attention_reason": cpc_run[9] if cpc_run else None,
        "collection_ref": cpc_run[11] if cpc_run else None,
    }
    info = sources.get("information_freshness")
    info_status = str(info[1]).upper() if info else ""
    if info_status == "SUCCESS_ZERO":
        info_state = "success_zero"
    elif info_status in {"SUCCESS", "BASELINE_CREATED"}:
        info_state = "fresh"
    elif info_status in {"SOURCE_UNAVAILABLE", "STALE"}:
        info_state = "stale"
    elif info:
        info_state = "failed"
    else:
        info_state = "missing"
    result["information_intelligence"] = {
        "state": info_state, "source_id": info[0] if info else None,
        "checked_at": _date(info[2]) if info else None,
        "run_status": info[1] if info else None, "error": info[3] if info else None,
    }
    tax = sources.get("tax_state") or {}
    tax_state = "missing"
    if tax.get("engine_state") == "ACTIVE":
        tax_state = "stale" if tax.get("income_periods_missing") else "fresh"
    result["tax_engine"] = {
        "state": tax_state, "engine_state": tax.get("engine_state"),
        "latest_source_period": tax.get("latest_source_period"),
        "expected_through_period": tax.get("expected_through_period"),
        "data_quality": tax.get("overall_tax_quality"),
    }
    return result


def _economics_block(business_date: date, revenue: Any = None, profit: Any = None,
                     units: Any = None, unallocated: Any = None,
                     confirmed_through: date | None = None) -> dict[str, Any]:
    confirmed = confirmed_through is not None and revenue is not None and profit is not None
    margin = profit / revenue * Decimal("100") if confirmed and revenue else None
    return {
        "business_date": business_date.isoformat(), "confirmed_through_date": _date(confirmed_through),
        "revenue": _decimal(revenue), "contribution_profit": _decimal(profit),
        "contribution_margin_pct": _decimal(margin), "confirmed_units": units,
        "confirmation_state": "CONFIRMED" if confirmed else "UNAVAILABLE",
        "data_quality": "REVIEW" if unallocated else "VALID" if confirmed else "UNAVAILABLE",
        "unallocated_other_expense_lines": unallocated if confirmed else None,
    }


def _current_economics(rows: list[tuple[Any, ...]], business_date: date) -> dict[str, Any]:
    if not rows:
        return _economics_block(business_date)
    return _economics_block(
        business_date,
        sum((row[1] for row in rows), Decimal("0")),
        sum((row[2] for row in rows), Decimal("0")),
        sum(row[3] for row in rows), sum(row[4] for row in rows), business_date,
    )


def _latest_summary(row: tuple[Any, ...] | None, business_date: date) -> dict[str, Any]:
    return _economics_block(business_date) if row is None else _economics_block(
        business_date, row[1], row[2], row[3], row[4], row[0],
    )


def _offer_latest(row: tuple[Any, ...] | None, business_date: date) -> dict[str, Any]:
    if row is None:
        block = _economics_block(business_date)
        block.update({"delivered_units": None, "return_events": None, "returned_units": None})
        return block
    block = _economics_block(business_date, row[2], row[3], row[4], row[7], row[1])
    block.update({"delivered_units": row[4], "return_events": row[5], "returned_units": row[6]})
    return block


def _promotion(row: tuple[Any, ...]) -> dict[str, Any]:
    return {"action_id": row[1], "action_title": row[2], "action_type": row[3], "source_list_type": row[4],
            "action_price": _decimal(row[5]), "current_boost": _decimal(row[6]), "min_boost": _decimal(row[7]),
            "max_boost": _decimal(row[8]), "data_quality_status": row[9], "collected_at": _date(row[10])}


def _cpc(row: tuple[Any, ...]) -> dict[str, Any]:
    return {"campaign_id": row[1], "campaign_state": row[2], "campaign_type": row[3],
            "spend": _decimal(row[4]), "views": row[5], "clicks": row[6], "orders": row[7],
            "orders_money": _decimal(row[8]), "data_quality_status": row[9]}


def _tax_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine_state": state.get("engine_state", "MISSING"), "tax_year": state.get("tax_year"),
        "taxable_revenue": _decimal(state.get("taxable_revenue_ytd")),
        "gross_usn": _decimal(state.get("usn_gross_ytd")),
        "estimated_payable": _decimal(state.get("usn_payable_estimate_ytd")),
        "additional_1pct": _decimal(state.get("additional_contribution_ytd")),
        "fixed_insurance_obligation": _decimal(state.get("fixed_contribution_annual")),
        "fixed_insurance_paid_ytd": _decimal(state.get("fixed_contribution_paid_ytd")),
        "data_quality": state.get("overall_tax_quality", "MISSING"),
        "tax_date_confidence": state.get("tax_date_confidence"),
        "latest_source_period": state.get("latest_source_period"),
        "expected_through_period": state.get("expected_through_period"),
        "income_periods_missing": state.get("income_periods_missing", []),
        "vat_status": state.get("vat_status"),
        "fixed_obligation_allocation": "BUSINESS_LEVEL_ONLY_NOT_ALLOCATED_TO_OFFERS",
    }


def _information(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    events = []
    for row in rows:
        metadata = row[9] or {}
        events.append({
            "event_id": row[0], "source_id": row[1], "source_title": row[2],
            "event_kind": row[3], "classification": row[4], "severity": row[5],
            "requires_action": row[6], "confidence": row[7], "review_status": row[8],
            "effective_date": metadata.get("effective_date"), "event_semantics": metadata.get("event_semantics"),
            "business_domains": row[10] or [], "affected_components": row[11] or [],
            "created_at": _date(row[12]),
        })
    return {"events": events, "counts": {severity: sum(event["severity"] == severity for event in events)
            for severity in ("CRITICAL", "ACTION_REQUIRED", "WATCH", "INFO")}}


def _experiments(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        started_at = row[4]
        result.append({
            "experiment_id": row[0], "offer_id": row[1], "type": row[2], "status": row[3],
            "started_at": _date(started_at), "ended_at": _date(row[5]), "target_config": row[6] or {},
            "unit_limit": row[7], "duration_limit_days": row[8], "loss_limit": _decimal(row[9]),
            "notes": row[10], "created_at": _date(row[11]), "updated_at": _date(row[12]),
            "attribution_state": "UNAVAILABLE_START_TIMESTAMP" if started_at is None else "NOT_CALCULATED",
            "performance_attribution": None,
            "guardrail_evaluation": "NOT_EVALUATED_ATTRIBUTION_UNAVAILABLE" if started_at is None else "NOT_CALCULATED",
            "deterministic_alerts": [],
        })
    return result


def _attention(source_freshness: dict[str, Any], information: dict[str, Any],
               experiments: list[dict[str, Any]], tax: dict[str, Any],
               current_economics: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source, value in source_freshness.items():
        state = value["state"]
        if state not in {"fresh", "success_zero", "success_nonzero"}:
            items.append({"class": "DATA_QUALITY", "severity": "HIGH" if state in {"failed", "stuck"} else "MEDIUM",
                          "scope": source, "code": f"SOURCE_{state.upper()}", "message": f"{source}: {state}"})
    for event in information["events"]:
        severity = event["severity"]
        event_class = "ACTION_REQUIRED" if severity in {"ACTION_REQUIRED", "CRITICAL"} else "WATCH" if severity == "WATCH" else "INFORMATION_EVENT"
        items.append({
            "class": event_class,
            "severity": "CRITICAL" if severity == "CRITICAL" else "HIGH" if severity == "ACTION_REQUIRED" else "MEDIUM" if severity == "WATCH" else "INFO",
            "scope": event["source_id"], "code": event["event_kind"],
            "message": f"{event['source_title']}: {event['event_kind']}", "event_id": event["event_id"],
        })
    for experiment in experiments:
        if experiment["started_at"] is None:
            items.append({"class": "DATA_QUALITY", "severity": "MEDIUM", "scope": experiment["experiment_id"],
                          "code": "EXPERIMENT_START_TIMESTAMP_UNKNOWN",
                          "message": "Experiment attribution is unavailable because started_at is unknown."})
        for alert in experiment["deterministic_alerts"]:
            items.append({"class": "EXPERIMENT_ALERT", "severity": "HIGH", "scope": experiment["experiment_id"],
                          "code": alert, "message": alert})
    if tax.get("data_quality") not in {"CONFIRMED", "VALID"}:
        items.append({"class": "DATA_QUALITY", "severity": "MEDIUM", "scope": "tax_engine",
                      "code": "TAX_DATA_PARTIAL", "message": "Tax Engine is active with partial data quality."})
    if current_economics["confirmation_state"] != "CONFIRMED":
        items.append({"class": "DATA_QUALITY", "severity": "INFO", "scope": "current_day_economics",
                      "code": "CURRENT_ECONOMICS_UNAVAILABLE", "message": "Current-day economics are not confirmed."})
    return sorted(items, key=lambda item: (_SEVERITY_ORDER[item["severity"]], ATTENTION_CLASSES.index(item["class"]), item["scope"], item["code"]))


def _serialize_trends(trends: dict[str, list[tuple[Any, ...]]]) -> dict[str, dict[str, Any]]:
    definitions = {
        "demand": (1, lambda row: {"offer_id": row[0], "business_date": _date(row[1]), "ordered_revenue": _decimal(row[2]), "ordered_units": row[3]}),
        "price": (1, lambda row: {"offer_id": row[0], "observed_at": _date(row[1]), "price": _decimal(row[2])}),
        "boost": (1, lambda row: {"offer_id": row[0], "observed_at": _date(row[1]), "current_boost": _decimal(row[2])}),
        "finance": (1, lambda row: {"offer_id": row[0], "business_date": _date(row[1]), "revenue": _decimal(row[2]),
                                    "contribution_profit": _decimal(row[3]),
                                    "contribution_margin_pct": _decimal(row[3] / row[2] * Decimal("100")) if row[2] else None}),
    }
    result: dict[str, dict[str, Any]] = {}
    for name, (date_index, serializer) in definitions.items():
        rows = trends.get(name, [])
        coverage: dict[str, set[str]] = {}
        for row in rows:
            coverage.setdefault(row[0], set()).add(_date(row[date_index])[:10])
        series = {offer: {"distinct_business_days": len(days),
                          "status": "READY" if len(days) >= 7 else "INSUFFICIENT_DATA"}
                  for offer, days in sorted(coverage.items())}
        result[name] = {"status": "READY" if series and all(item["status"] == "READY" for item in series.values()) else "INSUFFICIENT_DATA",
                        "minimum_distinct_business_days": 7, "series": series,
                        "points": [serializer(row) for row in rows]}
    return result


def build_brief(sources: dict[str, Any], business_date: date, generated_at: datetime | None = None) -> dict[str, Any]:
    generated = generated_at or datetime.now(timezone.utc)
    demand, deliveries, returns = _index(sources["demand"]), _index(sources["deliveries"]), _index(sources["returns"])
    current_finance, latest = _index(sources["finance"]), _index(sources.get("latest_economics", []))
    promotions, cpc_rows = _group(sources["promotions"]), _group(sources["cpc"])
    current_price_status = _index(sources["current_price_status"])
    cpc_state = _cpc_state(sources.get("cpc_collection"))
    source_freshness = _source_freshness(sources, business_date)
    current_summary = _current_economics(sources["finance"], business_date)
    latest_summary = _latest_summary(sources.get("latest_economics_summary"), business_date)
    information = _information(sources.get("information_events", []))
    experiments = _experiments(sources.get("experiments", []))
    tax = _tax_payload(sources.get("tax_state", {}))
    offers: list[dict[str, Any]] = []
    for offer_id, sku, product_id, price, cost_price, price_at in sources["products"]:
        demand_row, delivery_row, return_row = demand.get(offer_id), deliveries.get(offer_id), returns.get(offer_id)
        finance_row, latest_row = current_finance.get(offer_id), latest.get(offer_id)
        demand_block = {"ordered_revenue": _decimal(demand_row[2]) if demand_row else None,
                        "ordered_units": demand_row[3] if demand_row else None,
                        "status": demand_row[5] if demand_row else "NOT_AVAILABLE"}
        fulfilment = {"delivered_units": delivery_row[1] if delivery_row else None,
                       "return_events": return_row[1] if return_row else None,
                       "returned_units": return_row[2] if return_row else None}
        current_offer_economics = _economics_block(
            business_date, finance_row[1] if finance_row else None, finance_row[2] if finance_row else None,
            finance_row[3] if finance_row else None, finance_row[4] if finance_row else None,
            business_date if finance_row else None,
        )
        promo, cpc = promotions.get(offer_id, []), cpc_rows.get(offer_id, [])
        reasons = []
        if not demand_row or demand_row[5] != "valid": reasons.append("seller_daily_data_quality")
        if any(row[9] != "valid" for row in promo): reasons.append("promotion_data_quality")
        if any(row[9] != "valid" for row in cpc): reasons.append("cpc_data_quality")
        offers.append({
            "offer_id": offer_id, "sku": sku, "product_id": product_id, "cost_price": _decimal(cost_price),
            "price": {"current_price": _decimal(price), "observed_at": _date(price_at)},
            "current_day": {"business_date": business_date.isoformat(), "demand": demand_block,
                            "fulfilment": fulfilment, "economics": current_offer_economics},
            "demand": demand_block, "fulfilment": fulfilment, "economics": current_offer_economics,
            "latest_confirmed_economics": _offer_latest(latest_row, business_date),
            "current_price_economics_status": current_price_status.get(offer_id, (None, "REVIEW_DATA"))[1],
            "promotions": {"participating": [_promotion(row) for row in promo if row[4] == "PARTICIPATING"],
                           "candidates": [_promotion(row) for row in promo if row[4] == "CANDIDATE"],
                           "status": "MISSING" if not promo else "VALID" if all(row[9] == "valid" for row in promo) else "REVIEW"},
            "advertising": {"state": cpc_state, "cpc": [_cpc(row) for row in cpc],
                            "spend": _decimal(sum((row[4] for row in cpc), Decimal("0"))) if cpc else "0" if cpc_state == "SUCCESS_ZERO" else None,
                            "orders": sum(row[7] for row in cpc) if cpc else 0 if cpc_state == "SUCCESS_ZERO" else None},
            "attention": {"level": "DATA_QUALITY" if reasons else "NO_ACTION", "reasons": reasons},
        })
    ordered_values = [Decimal(item["demand"]["ordered_revenue"]) for item in offers if item["demand"]["ordered_revenue"] is not None]
    cpc_entries = [entry for item in offers for entry in item["advertising"]["cpc"]]
    summary = {
        "ordered_revenue": _decimal(sum(ordered_values, Decimal("0"))) if ordered_values else None,
        "ordered_units": sum(item["demand"]["ordered_units"] or 0 for item in offers) if any(item["demand"]["ordered_units"] is not None for item in offers) else None,
        "delivered_units": sum(item["fulfilment"]["delivered_units"] or 0 for item in offers) if any(item["fulfilment"]["delivered_units"] is not None for item in offers) else None,
        "returned_units": sum(item["fulfilment"]["returned_units"] or 0 for item in offers) if any(item["fulfilment"]["returned_units"] is not None for item in offers) else None,
        "cpc_spend": _decimal(sum((Decimal(entry["spend"]) for entry in cpc_entries), Decimal("0"))) if cpc_entries else "0" if cpc_state == "SUCCESS_ZERO" else None,
        "cpc_orders": sum(entry["orders"] for entry in cpc_entries) if cpc_entries else 0 if cpc_state == "SUCCESS_ZERO" else None,
    }
    attention = _attention(source_freshness, information, experiments, tax, current_summary)
    trends = _serialize_trends(sources.get("trends", {}))
    brief = {
        "report_version": "v1.1", "business_date": business_date.isoformat(),
        "generated_at": generated.isoformat(), "timezone": "Europe/Moscow", "read_only": True,
        "summary": summary, "current_day_economics": current_summary,
        "latest_confirmed_economics": latest_summary, "source_freshness": source_freshness,
        "advertising": {"cpc": {"business_date": business_date.isoformat(), "state": cpc_state,
                                  "spend": summary["cpc_spend"], "orders": summary["cpc_orders"],
                                  "external_state": source_freshness["cpc"]["external_state"],
                                  "error": source_freshness["cpc"]["error"]}},
        "tax": tax, "tax_status": tax["engine_state"], "information_intelligence": information,
        "experiments": experiments, "attention_taxonomy": list(ATTENTION_CLASSES),
        "attention_items": attention,
        "data_quality": {"status": "review" if attention else "valid", "sources": source_freshness,
                         "warnings": [item["code"] for item in attention if item["class"] == "DATA_QUALITY"]},
        "offers": offers,
    }
    brief["extended_report_payload"] = {key: brief[key] for key in (
        "report_version", "business_date", "generated_at", "summary", "current_day_economics",
        "latest_confirmed_economics", "source_freshness", "advertising", "tax",
        "information_intelligence", "experiments", "attention_items", "offers",
    )}
    brief["extended_report_payload"]["trends"] = trends
    brief["compact_report_payload"] = {
        "business_date": brief["business_date"], "summary": summary,
        "current_day_economics": current_summary, "latest_confirmed_economics": latest_summary,
        "cpc": brief["advertising"]["cpc"], "tax": tax,
        "information_counts": information["counts"],
        "experiments": [{"experiment_id": item["experiment_id"], "offer_id": item["offer_id"],
                         "status": item["status"], "started_at": item["started_at"],
                         "attribution_state": item["attribution_state"]} for item in experiments],
        "attention_counts": {kind: sum(item["class"] == kind for item in attention) for kind in ATTENTION_CLASSES},
    }
    return brief
