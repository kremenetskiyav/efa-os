"""Authoritative public sources monitored by the first intelligence block."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OpenAPISource:
    source_id: str
    canonical_url: str
    api_family: str
    authority: str = "OFFICIAL_OZON"


SOURCES = (
    OpenAPISource(
        "SELLER_API_OPENAPI",
        "https://docs.ozon.ru/api/seller/swagger.json",
        "SELLER",
    ),
    OpenAPISource(
        "PERFORMANCE_API_OPENAPI",
        "https://docs.ozon.ru/api/performance/swagger.json",
        "PERFORMANCE",
    ),
)
