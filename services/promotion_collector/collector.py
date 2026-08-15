"""Pure promotion-response normalization; transport is the private bridge only."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PromotionRow:
    action_id: int | None; title: str | None; action_type: str | None
    date_start: str | None; date_end: str | None; source_kind: str
    product_id: int | None; price: str | None; action_price: str | None; max_action_price: str | None

def normalize(action: dict, item: dict | None, source_kind: str) -> PromotionRow:
    item = item or {}
    def value(name: str) -> str | None:
        return str(item[name]) if item.get(name) is not None else None
    return PromotionRow(action.get("id"), action.get("title"), action.get("action_type"), action.get("date_start"), action.get("date_end"), source_kind, item.get("id"), value("price"), value("action_price"), value("max_action_price"))
