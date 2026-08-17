"""Deterministic, credential-free Premium exit entitlement evidence tools."""

from .checker import build_snapshot, compare_snapshots, write_snapshot
from .contracts import CRITICAL_CHECKS

__all__ = ["CRITICAL_CHECKS", "build_snapshot", "compare_snapshots", "write_snapshot"]
