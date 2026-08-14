"""Read-only function-tool contract for Recommendation Engine v0.2."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from config import DatabaseConfig, RecommendationConfig
from database import fetch_product_economics
from models import ProductEconomics, Recommendation
from rules import build_recommendation

TOOL_NAME = "get_price_profit_recommendations"
_ACTIONS = ("KEEP", "CONSIDER_RAISE", "CONSIDER_LOWER", "REVIEW_DATA")
GET_PRICE_PROFIT_RECOMMENDATIONS_TOOL = {"type": "function", "name": TOOL_NAME, "description": "Return verified read-only price/profit recommendations from confirmed observed economics. Never changes Ozon prices.", "strict": True, "parameters": {"type": "object", "properties": {"offer_id": {"type": ["string", "null"]}, "action": {"type": ["string", "null"], "enum": [*_ACTIONS, None]}}, "required": ["offer_id", "action"], "additionalProperties": False}}


class ToolInputError(ValueError):
    pass


def get_price_profit_recommendations(arguments: Mapping[str, object], database_config: DatabaseConfig, recommendation_config: RecommendationConfig, fetch_economics: Callable[[DatabaseConfig], Sequence[ProductEconomics]] = fetch_product_economics) -> dict[str, object]:
    offer_id, action = _parse_arguments(arguments)
    all_items = [build_recommendation(product, recommendation_config) for product in fetch_economics(database_config)]
    items = [item for item in all_items if (offer_id is None or item.offer_id == offer_id) and (action is None or item.action == action)]
    return {"tool": TOOL_NAME, "read_only": True, "count": len(items), "recommendations": [_serialize_recommendation(item) for item in items]}


def _parse_arguments(arguments: Mapping[str, object]) -> tuple[str | None, str | None]:
    if set(arguments) != {"offer_id", "action"}:
        raise ToolInputError("arguments must contain exactly: offer_id, action")
    offer_id, action = arguments["offer_id"], arguments["action"]
    if offer_id is not None and (not isinstance(offer_id, str) or not offer_id.strip()):
        raise ToolInputError("offer_id must be a non-empty string or null")
    if action is not None and action not in _ACTIONS:
        raise ToolInputError("action must be KEEP, CONSIDER_RAISE, CONSIDER_LOWER, REVIEW_DATA, or null")
    return offer_id.strip() if isinstance(offer_id, str) else None, action if isinstance(action, str) else None


def _serialize_recommendation(item: Recommendation) -> dict[str, object]:
    return {key: _serialize(value) for key, value in item.__dict__.items()} | {"reasons": list(item.reasons)}


def _serialize(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    return value
