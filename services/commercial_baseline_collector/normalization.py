"""Pure validation and normalization for confirmed Seller/CPC contracts."""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class PayloadError(ValueError):
    """Raised for a payload that cannot preserve deterministic attribution."""


def _required(payload: object, fields: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not fields.issubset(payload):
        raise PayloadError(f"required fields: {','.join(sorted(fields))}")
    if payload.get("persist", False) not in (True, False):
        raise PayloadError("persist must be boolean")
    return payload


def _positive_int(value: Any, name: str, allow_zero: bool = True) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise PayloadError(f"{name} must be integer") from error
    if parsed < (0 if allow_zero else 1):
        raise PayloadError(f"{name} is out of range")
    return parsed


def _decimal(value: Any, name: str) -> Decimal:
    try:
        parsed = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise PayloadError(f"{name} must be numeric") from error
    if parsed < 0:
        raise PayloadError(f"{name} is out of range")
    return parsed


def _optional_decimal(source: dict[str, Any], name: str) -> Decimal | None:
    """An omitted or JSON-null optional Seller field remains unknown, never zero."""
    value = source.get(name)
    return None if value is None else _decimal(value, name)


def _tariff_decimal(value: Any, name: str) -> Decimal:
    """Preserve a raw finite Ozon JSON number without binary-float arithmetic."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise PayloadError(f"{name} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise PayloadError(f"{name} must be numeric") from error
    if not parsed.is_finite():
        raise PayloadError(f"{name} must be finite")
    if parsed < 0:
        raise PayloadError(f"{name} is out of range")
    return parsed


def _optional_tariff_decimal(source: dict[str, Any], name: str) -> Decimal | None:
    value = source.get(name)
    return None if value is None else _tariff_decimal(value, name)


def _omitted_zero_int(source: dict[str, Any], name: str) -> int:
    """Performance statistics omit some counters when their value is zero."""
    return _positive_int(source.get(name, 0), name)


def _omitted_zero_cpc_orders(source: dict[str, Any]) -> int:
    """Ozon omits zero orders; explicit null and malformed values remain invalid."""
    if "orders" not in source:
        return 0
    value = source["orders"]
    if isinstance(value, bool):
        raise PayloadError("orders must be integer")
    if isinstance(value, float):
        raise PayloadError("orders must be integer")
    if isinstance(value, Decimal) and value != value.to_integral_value():
        raise PayloadError("orders must be integer")
    return _positive_int(value, "orders")


def normalize_seller_demand(payload: object) -> dict[str, Any]:
    data = _required(payload, {"collection_ref", "collected_at", "business_date", "rows"})
    if not isinstance(data["rows"], list):
        raise PayloadError("rows must be an array")
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for source in data["rows"]:
        if not isinstance(source, dict):
            raise PayloadError("seller row must be an object")
        sku = _positive_int(source.get("sku"), "sku", allow_zero=False)
        if sku in seen:
            raise PayloadError(f"duplicate seller SKU:{sku}")
        seen.add(sku)
        rows.append({
            "sku": sku,
            "business_date": str(data["business_date"]),
            "ordered_revenue": _decimal(source.get("ordered_revenue"), "ordered_revenue"),
            "ordered_units": _positive_int(source.get("ordered_units"), "ordered_units"),
            "collected_at": str(data["collected_at"]),
            "collection_ref": str(data["collection_ref"]),
            "source": "ozon_seller_analytics_v1",
        })
    return {"kind": "seller_demand", "persist": bool(data.get("persist", False)), "rows": rows, "collection_ref": str(data["collection_ref"])}


def _date(value: Any) -> str:
    raw = str(value)
    try:
        return datetime.strptime(raw, "%d.%m.%Y").date().isoformat()
    except ValueError:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
        except ValueError as error:
            raise PayloadError("CPC date must be DD.MM.YYYY or YYYY-MM-DD") from error


def normalize_cpc(payload: object) -> dict[str, Any]:
    data = _required(payload, {"collection_ref", "collected_at", "business_date", "report_uuid", "campaigns", "report"})
    if not isinstance(data["campaigns"], list) or not isinstance(data["report"], dict):
        raise PayloadError("campaigns/report type is invalid")
    campaigns = {
        _positive_int(item.get("id"), "campaign_id", allow_zero=False): item
        for item in data["campaigns"] if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for campaign_key, report_item in data["report"].items():
        campaign_id = _positive_int(campaign_key, "campaign_id", allow_zero=False)
        if campaign_id not in campaigns:
            raise PayloadError(f"report campaign is not in campaign list:{campaign_id}")
        report_rows = report_item.get("report", {}).get("rows") if isinstance(report_item, dict) else None
        if not isinstance(report_rows, list):
            raise PayloadError(f"campaign report has no rows:{campaign_id}")
        campaign = campaigns[campaign_id]
        for source in report_rows:
            sku = _positive_int(source.get("sku"), "sku", allow_zero=False)
            business_date = _date(source.get("date"))
            key = (business_date, campaign_id, sku)
            if key in seen:
                raise PayloadError(f"duplicate CPC detail:{business_date}:{campaign_id}:{sku}")
            seen.add(key)
            rows.append({
                "business_date": business_date,
                "campaign_id": campaign_id,
                "campaign_state": campaign.get("state"),
                "campaign_type": campaign.get("advObjectType"),
                "sku": sku,
                "views": _omitted_zero_int(source, "views"),
                "clicks": _omitted_zero_int(source, "clicks"),
                "ctr": _decimal(source.get("ctr"), "ctr"),
                "avg_bid": _decimal(source.get("avgBid"), "avgBid"),
                "money_spent": _decimal(source.get("moneySpent"), "moneySpent"),
                "orders": _omitted_zero_cpc_orders(source),
                "orders_money": _decimal(source.get("ordersMoney"), "ordersMoney"),
                "drr": _decimal(source.get("drr"), "drr"),
                "general_drr": _decimal(source.get("general_drr"), "general_drr"),
                "product_gmv": _decimal(source.get("product_gmv"), "product_gmv"),
                "price": _decimal(source.get("price"), "price"),
                "report_uuid": str(data["report_uuid"]),
                "source": "ozon_performance_statistics_v1",
            })
    return {
        "kind": "cpc", "persist": bool(data.get("persist", False)), "rows": rows,
        "collection_ref": str(data["collection_ref"]), "collected_at": str(data["collected_at"]),
        "business_date": str(data["business_date"]), "report_uuid": str(data["report_uuid"]),
        "campaigns_count": len(campaigns),
    }


def normalize_cpc_prepare(payload: object) -> dict[str, Any]:
    data = _required(payload, {"business_date"})
    business_date = _date(data["business_date"])
    return {
        "business_date": business_date,
        "collection_ref": f"cpc-day-{business_date}",
        "requested_at": str(data.get("requested_at") or datetime.utcnow().isoformat() + "Z"),
    }


def _campaign_snapshot(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise PayloadError("campaigns must be a non-empty array")
    campaigns: list[dict[str, Any]] = []
    seen: set[int] = set()
    for source in value:
        if not isinstance(source, dict):
            raise PayloadError("campaign must be an object")
        campaign_id = _positive_int(source.get("id"), "campaign_id", allow_zero=False)
        if campaign_id in seen:
            raise PayloadError(f"duplicate campaign_id:{campaign_id}")
        if source.get("advObjectType") != "SKU":
            raise PayloadError(f"non-SKU campaign:{campaign_id}")
        seen.add(campaign_id)
        campaigns.append({
            "id": str(campaign_id),
            "title": str(source.get("title") or ""),
            "state": source.get("state"),
            "advObjectType": "SKU",
        })
    return campaigns


def normalize_cpc_registration(payload: object) -> dict[str, Any]:
    data = _required(payload, {"business_date", "report_uuid", "campaigns"})
    report_uuid = str(data["report_uuid"]).strip()
    try:
        from uuid import UUID
        UUID(report_uuid)
    except (ValueError, TypeError) as error:
        raise PayloadError("report_uuid must be UUID") from error
    campaigns = _campaign_snapshot(data["campaigns"])
    return {
        "business_date": _date(data["business_date"]),
        "report_uuid": report_uuid,
        "campaigns": campaigns,
        "campaigns_json": json.dumps(campaigns, ensure_ascii=False, separators=(",", ":")),
    }


def normalize_cpc_status(payload: object) -> dict[str, Any]:
    data = _required(payload, {"run_id", "lease_token", "report_uuid", "report_state"})
    normalized = {
        "run_id": str(data["run_id"]),
        "lease_token": str(data["lease_token"]),
        "report_uuid": str(data["report_uuid"]),
        "report_state": str(data["report_state"] or "").strip().upper(),
        "error_code": str(data["error_code"]) if data.get("error_code") else None,
        "error_message": str(data["error_message"]) if data.get("error_message") else None,
    }
    if not normalized["report_state"]:
        raise PayloadError("report_state is required")
    return normalized


def normalize_prices(payload: object) -> dict[str, Any]:
    data = _required(payload, {"collection_ref", "collected_at", "items"})
    if not isinstance(data["items"], list) or not data["items"]:
        raise PayloadError("items must be a non-empty array")
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for source in data["items"]:
        if not isinstance(source, dict):
            raise PayloadError("price item must be an object")
        product_id = _positive_int(source.get("product_id"), "product_id", allow_zero=False)
        if product_id in seen:
            raise PayloadError(f"duplicate product_id:{product_id}")
        seen.add(product_id)
        price = source.get("price")
        if not isinstance(price, dict):
            raise PayloadError(f"price object is required:{product_id}")
        commissions = source.get("commissions")
        if not isinstance(commissions, dict):
            raise PayloadError(f"commissions object is required:{product_id}")
        sales_percent_fbs = _tariff_decimal(
            commissions.get("sales_percent_fbs"), "sales_percent_fbs"
        )
        if sales_percent_fbs > Decimal("100"):
            raise PayloadError("sales_percent_fbs is out of range")
        direct_min = _optional_tariff_decimal(
            commissions, "fbs_direct_flow_trans_min_amount"
        )
        direct_max = _optional_tariff_decimal(
            commissions, "fbs_direct_flow_trans_max_amount"
        )
        if direct_min is not None and direct_max is not None and direct_min > direct_max:
            raise PayloadError("fbs direct flow minimum exceeds maximum")
        rows.append({
            "product_id": product_id,
            "offer_id": str(source.get("offer_id") or "").strip(),
            "price": _decimal(price.get("price"), "price"),
            "old_price": _decimal(price.get("old_price"), "old_price"),
            "min_price": _decimal(price.get("min_price"), "min_price"),
            # v5 account response confirms this field may be absent.
            "marketing_price": _optional_decimal(price, "marketing_price"),
            "marketing_seller_price": _decimal(price.get("marketing_seller_price"), "marketing_seller_price"),
            "sales_percent_fbs": sales_percent_fbs,
            "fbs_deliv_to_customer_amount": _tariff_decimal(
                commissions.get("fbs_deliv_to_customer_amount"),
                "fbs_deliv_to_customer_amount",
            ),
            "acquiring": _optional_tariff_decimal(source, "acquiring"),
            "fbs_direct_flow_trans_min_amount": direct_min,
            "fbs_direct_flow_trans_max_amount": direct_max,
            "fbs_return_flow_amount": _optional_tariff_decimal(
                commissions, "fbs_return_flow_amount"
            ),
        })
    return {"kind": "prices", "persist": bool(data.get("persist", False)), "rows": rows,
            "collection_ref": str(data["collection_ref"]), "collected_at": str(data["collected_at"])}
