"""Conservative read-only recommendations for persisted promotion states."""
from __future__ import annotations

from config import RecommendationConfig
from models import ProductEconomics, PromotionRecommendation, PromotionState
from rules import build_recommendation


def build_promotion_recommendation(
    state: PromotionState,
    economics: ProductEconomics | None,
    config: RecommendationConfig,
    *,
    historical_promotion_match: bool = False,
) -> PromotionRecommendation:
    """Combine existing v0.2 economics with a promotion fact without projection.

    `historical_promotion_match` is deliberately false in v0.1 production:
    persisted snapshots do not yet prove an action state at a delivery date.
    It exists as an explicit future evidence gate rather than inferring a
    match from an action price alone.
    """
    reasons: list[str] = []
    if state.offer_id is None or state.data_quality_status != "valid":
        reasons.append("promotion_data_quality_not_valid")
    if economics is None:
        reasons.append("missing_product_economics")
        return _result(state, None, "low", "REVIEW", reasons)

    price_recommendation = build_recommendation(economics, config)
    if price_recommendation.current_price_economics_status != "CONFIRMED":
        reasons.append("current_price_economics_not_confirmed")
    if price_recommendation.data_quality_status != "valid":
        reasons.append("unit_economics_data_quality_not_valid")
    if price_recommendation.confidence == "low":
        reasons.append("insufficient_confirmed_unit_sample")
    if not historical_promotion_match:
        reasons.append("no_confirmed_promotion_delivery_economics_match")

    # action_price is an Ozon action condition, not a predicted selling price.
    # Therefore v0.1 never projects commission, logistics, profit or margin.
    if reasons:
        return _result(state, price_recommendation, price_recommendation.confidence, "REVIEW", reasons)

    # This branch is reserved for a later historical action-to-delivery match.
    # The evidence gate represents a comparable action/effective-price delivery
    # observation, not a numerical equality between action_price and revenue.
    margin = price_recommendation.last_confirmed_margin
    safe_margin = margin is not None and margin >= config.low_margin_percent
    if state.source_list_type == "PARTICIPATING":
        if safe_margin:
            return _result(state, price_recommendation, price_recommendation.confidence, "KEEP", ("confirmed_promotion_delivery_economics_match",))
        return _result(state, price_recommendation, price_recommendation.confidence, "CONSIDER_LEAVE", ("confirmed_promotion_economics_below_margin_gate",))
    if safe_margin:
        return _result(state, price_recommendation, price_recommendation.confidence, "CONSIDER_JOIN", ("confirmed_comparable_promotion_economics_passes_margin_gate",))
    return _result(state, price_recommendation, price_recommendation.confidence, "REVIEW", ("candidate_historical_economics_does_not_pass_margin_gate",))


def _result(
    state: PromotionState,
    economics: object | None,
    confidence: str,
    recommendation: str,
    reasons: list[str] | tuple[str, ...],
) -> PromotionRecommendation:
    return PromotionRecommendation(
        offer_id=state.offer_id,
        action_id=state.action_id,
        action_title=state.action_title,
        action_type=state.action_type,
        source_list_type=state.source_list_type,
        current_price=getattr(economics, "current_price", None),
        action_price=state.action_price,
        max_action_price=state.max_action_price,
        confirmed_effective_price=getattr(economics, "last_confirmed_effective_price", None),
        confirmed_profit_per_unit=getattr(economics, "last_confirmed_profit_per_unit", None),
        confirmed_margin_percent=getattr(economics, "last_confirmed_margin", None),
        economics_confidence=confidence,
        current_price_economics_status=getattr(economics, "current_price_economics_status", "REVIEW_DATA"),
        data_quality_status="valid" if state.data_quality_status == "valid" and state.offer_id is not None else "review",
        recommendation=recommendation,
        reasons=tuple(sorted(set(reasons))),
        numeric_projection_allowed=False,
    )


def build_promotion_recommendations(
    states: list[PromotionState],
    economics: list[ProductEconomics],
    config: RecommendationConfig,
) -> list[PromotionRecommendation]:
    by_offer = {item.offer_id: item for item in economics}
    return [build_promotion_recommendation(state, by_offer.get(state.offer_id), config) for state in states]
