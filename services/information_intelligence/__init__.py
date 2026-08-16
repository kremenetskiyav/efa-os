"""Deterministic, read-only Ozon information intelligence primitives."""

from .openapi import canonicalize_openapi, diff_openapi, structural_contract

__all__ = ["canonicalize_openapi", "diff_openapi", "structural_contract"]
