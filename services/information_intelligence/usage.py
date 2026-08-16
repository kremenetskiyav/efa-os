"""Versioned inventory of active EFA-OS API dependencies."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

from .openapi import ContractDiff


@dataclass(frozen=True)
class APIUsage:
    subsystem: str
    artifact: str
    api_family: str
    method: str
    path: str
    request_fields: tuple[str, ...]
    response_fields: tuple[str, ...]
    criticality: str
    downstream: tuple[str, ...] = ("Daily Brief Delivery v1",)

    def as_dict(self) -> dict:
        return asdict(self)


USAGE_MAP = (
    APIUsage("PROMOAUTOV1", "Promotion_Snapshot_Automation.json + promotion_collector", "SELLER", "GET", "/v1/actions", (), ("result", "id", "title", "action_type", "date_start", "date_end"), "CRITICAL"),
    APIUsage("PROMOAUTOV1", "Promotion_Snapshot_Automation.json + promotion_collector", "SELLER", "POST", "/v1/actions/products", ("action_id", "limit", "offset"), ("result.products", "id", "price", "action_price", "max_action_price", "add_mode", "current_boost", "min_boost", "max_boost"), "CRITICAL"),
    APIUsage("PROMOAUTOV1", "Promotion_Snapshot_Automation.json + promotion_collector", "SELLER", "POST", "/v1/actions/candidates", ("action_id", "limit", "offset"), ("result.products", "id", "price", "action_price", "max_action_price", "add_mode", "current_boost", "min_boost", "max_boost"), "CRITICAL"),
    APIUsage("SELLERDAILYV1", "Seller_Analytics_Daily_Collection.json + commercial_baseline_collector", "SELLER", "POST", "/v1/analytics/data", ("date_from", "date_to", "metrics", "dimension", "filters", "limit", "offset"), ("result.data", "dimensions.id", "metrics"), "CRITICAL"),
    APIUsage("Price Snapshot Automation", "Ozon_Price_Snapshot_Automation.json + commercial_baseline_collector", "SELLER", "POST", "/v5/product/info/prices", ("filter.product_id", "filter.visibility", "limit"), ("items", "product_id", "offer_id", "price.price", "price.old_price", "price.min_price", "price.marketing_price", "price.marketing_seller_price"), "CRITICAL"),
    APIUsage("CPCDAILYV1", "CPC_Daily_Collection.json + OzonPerformance.node.js", "PERFORMANCE", "GET", "/api/client/campaign", (), ("id", "state", "advObjectType"), "CRITICAL"),
    APIUsage("CPCDAILYV1", "CPC_Daily_Collection.json + OzonPerformance.node.js", "PERFORMANCE", "POST", "/api/client/statistics/json", ("campaigns", "dateFrom", "dateTo", "groupBy"), ("UUID",), "CRITICAL"),
    APIUsage("CPCDAILYV1", "CPC_Daily_Collection.json + OzonPerformance.node.js", "PERFORMANCE", "GET", "/api/client/statistics/{reportUuid}", ("reportUuid",), ("state", "link"), "CRITICAL"),
    APIUsage("CPCDAILYV1", "CPC_Daily_Collection.json + OzonPerformance.node.js + commercial_baseline_collector", "PERFORMANCE", "GET", "/api/client/statistics/report", ("UUID",), ("report.rows", "date", "sku", "views", "clicks", "ctr", "avgBid", "moneySpent", "orders", "ordersMoney", "drr", "general_drr", "product_gmv", "price"), "CRITICAL"),
)


def _encoded_path(path: str) -> str:
    return path.replace("~", "~0").replace("/", "~1")


def route_impact(diff: ContractDiff, api_family: str, usages: Iterable[APIUsage] = USAGE_MAP) -> list[dict]:
    routed: list[dict] = []
    for usage in usages:
        if usage.api_family != api_family:
            continue
        prefix = f"/paths/{_encoded_path(usage.path)}/{usage.method.lower()}"
        endpoint_prefix = f"/paths/{_encoded_path(usage.path)}"
        matching = [path for path in diff.changed_paths if path.startswith(prefix) or path == endpoint_prefix]
        if matching:
            field_names = set(usage.request_fields + usage.response_fields)
            exact_field = any(any(field.split(".")[-1] in path for field in field_names) for path in matching)
            impact = "AFFECTED" if exact_field or any(path == prefix for path in matching) else "POTENTIALLY_AFFECTED"
        elif any(path.startswith("/components/schemas") or "/security" in path for path in diff.changed_paths):
            impact = "POTENTIALLY_AFFECTED"
        else:
            impact = "NOT_USED"
        severity = "INFO"
        if diff.classification == "BREAKING" and impact == "AFFECTED":
            severity = "CRITICAL"
        elif diff.classification in {"BREAKING", "REVIEW"} and impact in {"AFFECTED", "POTENTIALLY_AFFECTED"}:
            severity = "ACTION_REQUIRED"
        elif diff.classification == "REVIEW":
            severity = "WATCH"
        routed.append({"subsystem": usage.subsystem, "impact": impact, "severity": severity, "changed_paths": matching})
    return routed
