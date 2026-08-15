"""Deterministic read-only promotion monitoring signals."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config import PromotionMonitoringConfig
from models import PromotionState


def build_promotion_state(row: PromotionState, config: PromotionMonitoringConfig, now: datetime | None = None) -> PromotionState:
    observed_at = now or datetime.now(timezone.utc)
    signals: list[str] = []
    if row.source_list_type == "PARTICIPATING":
        signals.append("ACTIVE_PARTICIPATION")
    elif row.source_list_type == "CANDIDATE":
        signals.append("AVAILABLE_CANDIDATE")
    if row.action_end_at is not None and observed_at <= row.action_end_at <= observed_at + timedelta(days=config.ending_soon_days):
        signals.append("PROMOTION_ENDING_SOON")
    if row.price is not None and row.action_price is not None and row.action_price > 0 and row.action_price < row.price:
        signals.append("ACTION_PRICE_BELOW_CURRENT_PRICE")
    if row.data_quality_status != "valid" or row.offer_id is None:
        signals.append("DATA_QUALITY_ISSUE")
    return PromotionState(**{**row.__dict__, "signals": tuple(signals)})
