"""Read-only contracts used before and after the Ozon Premium trial exit."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    api_family: str
    method: str
    endpoint: str
    request_shape: tuple[str, ...]
    required_fields: tuple[str, ...]


# Request shapes deliberately describe only contract keys. Dynamic values and all
# credentials stay in the approved n8n execution boundary, never in evidence.
CRITICAL_CHECKS: tuple[CheckSpec, ...] = (
    CheckSpec("seller_analytics", "SELLER", "POST", "/v1/analytics/data",
              ("date_from", "date_to", "metrics", "dimension", "filters", "limit", "offset"),
              ("result.data",)),
    CheckSpec("promotions_actions", "SELLER", "GET", "/v1/actions", (), ("result.actions",)),
    CheckSpec("promotions_products", "SELLER", "POST", "/v1/actions/products",
              ("action_id", "limit", "offset"), ("result.products",)),
    CheckSpec("promotions_candidates", "SELLER", "POST", "/v1/actions/candidates",
              ("action_id", "limit", "offset"), ("result.products",)),
    CheckSpec("prices", "SELLER", "POST", "/v5/product/info/prices",
              ("filter.product_id", "filter.visibility", "limit"), ("items",)),
    CheckSpec("finance", "SELLER", "POST", "/v3/finance/transaction/list",
              ("filter.date.from", "filter.date.to", "filter.operation_type", "filter.transaction_type", "page", "page_size"),
              ("result.operations",)),
    CheckSpec("postings", "SELLER", "POST", "/v3/posting/fbs/list",
              ("filter.since", "filter.to", "limit", "offset", "with"), ("result.postings",)),
    CheckSpec("performance_campaigns", "PERFORMANCE", "GET", "/api/client/campaign", (), ("list",)),
)

ALLOWED_METHODS = {"GET", "POST"}
WRITE_METHODS = {"PUT", "PATCH", "DELETE"}


def assert_read_only_contracts(checks: tuple[CheckSpec, ...] = CRITICAL_CHECKS) -> None:
    for check in checks:
        if check.method in WRITE_METHODS or check.method not in ALLOWED_METHODS:
            raise ValueError(f"non-read-only contract: {check.check_id}")
        if not check.endpoint.startswith("/"):
            raise ValueError(f"invalid endpoint: {check.check_id}")
