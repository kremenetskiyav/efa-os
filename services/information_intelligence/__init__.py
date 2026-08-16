"""Deterministic, read-only Ozon information intelligence primitives."""

from .openapi import canonicalize_openapi, diff_openapi, structural_contract
from .legal import canonicalize_legal, canonicalize_legal_pdf, diff_legal
from .manual_evidence import SELLER_MAIN_NOTICES, daily_brief_preview

__all__ = ["canonicalize_openapi", "diff_openapi", "structural_contract", "canonicalize_legal", "canonicalize_legal_pdf", "diff_legal", "SELLER_MAIN_NOTICES", "daily_brief_preview"]
