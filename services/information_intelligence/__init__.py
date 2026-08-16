"""Deterministic, read-only Ozon information intelligence primitives."""

from .openapi import canonicalize_openapi, diff_openapi, structural_contract
from .legal import canonicalize_legal, diff_legal

__all__ = ["canonicalize_openapi", "diff_openapi", "structural_contract", "canonicalize_legal", "diff_legal"]
