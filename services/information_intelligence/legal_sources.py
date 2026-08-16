"""Official Ozon legal sources and unresolved source requirements."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LegalSource:
    source_id: str
    title: str
    canonical_url: str | None
    source_type: str
    authority_level: str
    business_domains: tuple[str, ...]
    document_format: str
    version_marker: str | None
    effective_date: str | None
    last_update_marker: str | None
    retrieval_capability: str
    historical_version_capability: str
    monitoring_priority: str
    applicability_status: str
    accept: str = "text/html,application/xhtml+xml,text/plain;q=0.9"


LEGAL_SOURCES = (
    LegalSource(
        source_id="OZON_SELLER_AGREEMENT",
        title="Ozon seller agency agreement and standard terms",
        canonical_url="https://docs.ozon.ru/legal/partners/logistics/contract/",
        source_type="LEGAL_DOCUMENT",
        authority_level="LEVEL_1",
        business_domains=(
            "COMMERCIAL_REVENUE", "FBS", "FBO", "COMMISSION", "LOGISTICS",
            "RETURNS", "FINANCE", "DOCUMENTS",
        ),
        document_format="HTML",
        version_marker="EXPOSED_IN_DOCUMENT",
        effective_date="EXPOSED_IN_DOCUMENT",
        last_update_marker="EXPOSED_IN_DOCUMENT",
        retrieval_capability="PUBLIC_HTTP_OR_MANUAL_BOOTSTRAP",
        historical_version_capability="LINKED_PREVIOUS_VERSION_WHEN_EXPOSED",
        monitoring_priority="CRITICAL",
        applicability_status="NEEDS_ACCOUNT_APPLICABILITY_CONFIRMATION",
    ),
    LegalSource(
        source_id="OZON_PROMOTION_DISCOUNT_TERMS",
        title="Ozon promotion, discount and seller-points terms",
        canonical_url=None,
        source_type="LEGAL_DOCUMENT",
        authority_level="LEVEL_1",
        business_domains=("PROMOTION", "PRICING", "COMMERCIAL_REVENUE"),
        document_format="UNKNOWN",
        version_marker=None,
        effective_date=None,
        last_update_marker=None,
        retrieval_capability="NEEDS_SOURCE_CONFIRMATION",
        historical_version_capability="UNKNOWN",
        monitoring_priority="CRITICAL",
        applicability_status="NEEDS_SOURCE_CONFIRMATION",
    ),
    LegalSource(
        source_id="OZON_PERFORMANCE_ADVERTISING_TERMS",
        title="Ozon Performance advertising terms",
        canonical_url=None,
        source_type="LEGAL_DOCUMENT",
        authority_level="LEVEL_1",
        business_domains=("ADVERTISING", "FINANCE"),
        document_format="UNKNOWN",
        version_marker=None,
        effective_date=None,
        last_update_marker=None,
        retrieval_capability="NEEDS_SOURCE_CONFIRMATION",
        historical_version_capability="UNKNOWN",
        monitoring_priority="CRITICAL",
        applicability_status="NEEDS_SOURCE_CONFIRMATION",
    ),
    LegalSource(
        source_id="OZON_LEGAL_ENTITY_BUYOUT_TERMS",
        title="Ozon legal-entity marketplace buyout terms",
        canonical_url=None,
        source_type="LEGAL_DOCUMENT",
        authority_level="LEVEL_1",
        business_domains=("FINANCE", "DOCUMENTS", "PRICING", "FBS", "FBO", "TAX_REVIEW_ONLY"),
        document_format="UNKNOWN",
        version_marker=None,
        effective_date=None,
        last_update_marker=None,
        retrieval_capability="NEEDS_SOURCE_CONFIRMATION",
        historical_version_capability="UNKNOWN",
        monitoring_priority="HIGH",
        applicability_status="NEEDS_SOURCE_CONFIRMATION",
    ),
)
