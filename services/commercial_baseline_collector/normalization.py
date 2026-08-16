"""Pure validation and normalization for confirmed Seller/CPC contracts."""
from __future__ import annotations

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


def _omitted_zero_int(source: dict[str, Any], name: str) -> int:
    """Performance statistics omit some counters when their value is zero."""
    return _positive_int(source.get(name, 0), name)


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
                "orders": _positive_int(source.get("orders"), "orders"),
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
        rows.append({
            "product_id": product_id,
            "offer_id": str(source.get("offer_id") or "").strip(),
            "price": _decimal(price.get("price"), "price"),
            "old_price": _decimal(price.get("old_price"), "old_price"),
            "min_price": _decimal(price.get("min_price"), "min_price"),
            # v5 account response confirms this field may be absent.
            "marketing_price": _optional_decimal(price, "marketing_price"),
            "marketing_seller_price": _decimal(price.get("marketing_seller_price"), "marketing_seller_price"),
        })
    return {"kind": "prices", "persist": bool(data.get("persist", False)), "rows": rows,
            "collection_ref": str(data["collection_ref"]), "collected_at": str(data["collected_at"])}
