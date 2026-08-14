"""Read-only function-tool contract for the recommendation engine."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from config import DatabaseConfig, RecommendationConfig
from database import fetch_product_economics
from models import ProductEconomics, Recommendation
from rules import build_recommendation


TOOL_NAME = "get_price_profit_recommendations"
_ACTIONS = ("KEEP", "CONSIDER_RAISE", "REVIEW_DATA")

GET_PRICE_PROFIT_RECOMMENDATIONS_TOOL = {
    "type": "function",
    "name": TOOL_NAME,
    "description": (
        "Return verified, read-only price and profit recommendations from the "
        "deterministic EFA recommendation engine. This tool never changes Ozon "
        "prices and proposed_price remains null until a marginal-cost model is confirmed."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "offer_id": {
                "type": ["string", "null"],
                "description": "Canonical product offer_id, or null to return all products.",
            },
            "action": {
                "type": ["string", "null"],
                "enum": [*_ACTIONS, None],
                "description": "Recommendation action to include, or null to return all actions.",
            },
        },
        "required": ["offer_id", "action"],
        "additionalProperties": False,
    },
}


class ToolInputError(ValueError):
    """Raised when direct local tool invocation violates its JSON contract."""


def get_price_profit_recommendations(
    arguments: Mapping[str, object],
    database_config: DatabaseConfig,
    recommendation_config: RecommendationConfig,
    fetch_economics: Callable[[DatabaseConfig], Sequence[ProductEconomics]] = fetch_product_economics,
) -> dict[str, object]:
    """Execute the function tool using only the existing read-only engine sources."""

    offer_id, action = _parse_arguments(arguments)
    recommendations = [
        build_recommendation(product, recommendation_config)
        for product in fetch_economics(database_config)
    ]
    filtered = [
        item
        for item in recommendations
        if (offer_id is None or item.offer_id == offer_id)
        and (action is None or item.action == action)
    ]
    return {
        "tool": TOOL_NAME,
        "read_only": True,
        "count": len(filtered),
        "recommendations": [_serialize_recommendation(item) for item in filtered],
    }


def _parse_arguments(arguments: Mapping[str, object]) -> tuple[str | None, str | None]:
    expected = {"offer_id", "action"}
    if set(arguments) != expected:
        raise ToolInputError("arguments must contain exactly: offer_id, action")
    offer_id = arguments["offer_id"]
    action = arguments["action"]
    if offer_id is not None and (not isinstance(offer_id, str) or not offer_id.strip()):
        raise ToolInputError("offer_id must be a non-empty string or null")
    if action is not None and action not in _ACTIONS:
        raise ToolInputError("action must be KEEP, CONSIDER_RAISE, REVIEW_DATA, or null")
    return offer_id.strip() if isinstance(offer_id, str) else None, action if isinstance(action, str) else None


def _serialize_recommendation(item: Recommendation) -> dict[str, object]:
    return {
        "offer_id": item.offer_id,
        "current_price": _serialize(item.current_price),
        "cost_price": _serialize(item.cost_price),
        "revenue": _serialize(item.revenue),
        "profit": _serialize(item.profit),
        "profit_per_unit": _serialize(item.profit_per_unit),
        "profit_margin_percent": _serialize(item.profit_margin_percent),
        "commission": _serialize(item.commission),
        "logistics": _serialize(item.logistics),
        "period_start": _serialize(item.period_start),
        "period_end": _serialize(item.period_end),
        "data_quality_status": item.data_quality_status,
        "action": item.action,
        "priority": item.priority,
        "reasons": list(item.reasons),
        "proposed_price": _serialize(item.proposed_price),
        "proposed_price_range": item.proposed_price_range,
        "proposal_reason": item.proposal_reason,
    }


def _serialize(value: Decimal | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return value.isoformat()
