"""Read-only function-tool contract for Recommendation Engine v0.2."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from anomalies import build_profit_cost_anomaly
from config import AnomalyConfig, DatabaseConfig, PromotionMonitoringConfig, RecommendationConfig
from database import fetch_anomaly_economics, fetch_product_economics, fetch_promotion_states
from models import ProductEconomics, Recommendation
from promotions import build_promotion_state
from rules import build_recommendation

TOOL_NAME = "get_price_profit_recommendations"
_ACTIONS = ("KEEP", "CONSIDER_RAISE", "CONSIDER_LOWER", "REVIEW_DATA")
GET_PRICE_PROFIT_RECOMMENDATIONS_TOOL = {"type": "function", "name": TOOL_NAME, "description": "Return verified read-only price/profit recommendations from confirmed observed economics. Never changes Ozon prices.", "strict": True, "parameters": {"type": "object", "properties": {"offer_id": {"type": ["string", "null"]}, "action": {"type": ["string", "null"], "enum": [*_ACTIONS, None]}}, "required": ["offer_id", "action"], "additionalProperties": False}}
ANOMALY_TOOL_NAME = "get_profit_cost_anomalies"
_ANOMALIES = ("PROFIT_DROPPED", "MARGIN_DROPPED", "LOGISTICS_INCREASED", "COMMISSION_INCREASED", "OTHER_EXPENSES_APPEARED", "DATA_QUALITY_ISSUE")
_SEVERITIES = ("low", "medium", "high")
GET_PROFIT_COST_ANOMALIES_TOOL = {"type": "function", "name": ANOMALY_TOOL_NAME, "description": "Return compact verified read-only profit and cost anomaly signals from two equal confirmed delivery periods. Never changes Ozon data or prices.", "strict": True, "parameters": {"type": "object", "properties": {"offer_id": {"type": ["string", "null"]}, "severity": {"type": ["string", "null"], "enum": [*_SEVERITIES, None]}, "anomaly_type": {"type": ["string", "null"], "enum": [*_ANOMALIES, None]}}, "required": ["offer_id", "severity", "anomaly_type"], "additionalProperties": False}}
PROMOTION_TOOL_NAME = "get_promotion_monitoring"
_PROMOTION_STATES = ("PARTICIPATING", "CANDIDATE")
_PROMOTION_SIGNALS = ("ACTIVE_PARTICIPATION", "AVAILABLE_CANDIDATE", "PROMOTION_ENDING_SOON", "ACTION_PRICE_BELOW_CURRENT_PRICE", "DATA_QUALITY_ISSUE")
GET_PROMOTION_MONITORING_TOOL = {"type": "function", "name": PROMOTION_TOOL_NAME, "description": "Return compact verified read-only state of the latest successful Ozon promotion collection. Use for participation, candidates, action prices and promotion conditions. Never joins/leaves promotions, changes Ozon prices, or recommends promotion actions.", "strict": True, "parameters": {"type": "object", "properties": {"offer_id": {"type": ["string", "null"]}, "state": {"type": ["string", "null"], "enum": [*_PROMOTION_STATES, None]}, "signal": {"type": ["string", "null"], "enum": [*_PROMOTION_SIGNALS, None]}}, "required": ["offer_id", "state", "signal"], "additionalProperties": False}}


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


def get_profit_cost_anomalies(arguments: Mapping[str, object], database_config: DatabaseConfig, anomaly_config: AnomalyConfig, fetch_economics: Callable[[DatabaseConfig], Mapping[str, object]] = fetch_anomaly_economics) -> dict[str, object]:
    if set(arguments) != {"offer_id", "severity", "anomaly_type"}:
        raise ToolInputError("arguments must contain exactly: offer_id, severity, anomaly_type")
    offer_id, severity, anomaly_type = arguments["offer_id"], arguments["severity"], arguments["anomaly_type"]
    if offer_id is not None and (not isinstance(offer_id, str) or not offer_id.strip()):
        raise ToolInputError("offer_id must be a non-empty string or null")
    if severity is not None and severity not in _SEVERITIES:
        raise ToolInputError("severity must be low, medium, high, or null")
    if anomaly_type is not None and anomaly_type not in _ANOMALIES:
        raise ToolInputError("anomaly_type is not supported")
    items = [build_profit_cost_anomaly(key, value, anomaly_config) for key, value in fetch_economics(database_config).items()]
    items = [item for item in items if (offer_id is None or item.offer_id == offer_id.strip()) and (severity is None or item.severity == severity) and (anomaly_type is None or anomaly_type in item.anomalies)]
    return {"tool": ANOMALY_TOOL_NAME, "read_only": True, "count": len(items), "anomalies": [_serialize_anomaly(item) for item in items]}


def get_promotion_monitoring(arguments: Mapping[str, object], database_config: DatabaseConfig, monitoring_config: PromotionMonitoringConfig, fetch_states: Callable[[DatabaseConfig], Sequence[object]] = fetch_promotion_states) -> dict[str, object]:
    if set(arguments) != {"offer_id", "state", "signal"}:
        raise ToolInputError("arguments must contain exactly: offer_id, state, signal")
    offer_id, state, signal = arguments["offer_id"], arguments["state"], arguments["signal"]
    if offer_id is not None and (not isinstance(offer_id, str) or not offer_id.strip()):
        raise ToolInputError("offer_id must be a non-empty string or null")
    if state is not None and state not in _PROMOTION_STATES:
        raise ToolInputError("state must be PARTICIPATING, CANDIDATE, or null")
    if signal is not None and signal not in _PROMOTION_SIGNALS:
        raise ToolInputError("signal is not supported")
    states = [build_promotion_state(item, monitoring_config) for item in fetch_states(database_config)]
    items = [item for item in states if (offer_id is None or item.offer_id == offer_id.strip()) and (state is None or item.source_list_type == state) and (signal is None or signal in item.signals)]
    return {"tool": PROMOTION_TOOL_NAME, "read_only": True, "count": len(items), "promotions": [_serialize_promotion(item) for item in items]}


def _serialize_recommendation(item: Recommendation) -> dict[str, object]:
    return {key: _serialize(value) for key, value in item.__dict__.items()} | {"reasons": list(item.reasons)}


def _serialize_anomaly(item: object) -> dict[str, object]:
    data = item.__dict__.copy()
    for key in ("anomalies", "reasons"):
        data[key] = list(data[key])
    for section in ("current", "baseline", "changes"):
        data[section] = {key: _serialize(value) for key, value in data[section].items()}
    return {key: _serialize(value) for key, value in data.items()}


def _serialize_promotion(item: object) -> dict[str, object]:
    data = item.__dict__.copy()
    data["signals"] = list(data["signals"])
    return {key: _serialize(value) for key, value in data.items()}


def _serialize(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    return value
