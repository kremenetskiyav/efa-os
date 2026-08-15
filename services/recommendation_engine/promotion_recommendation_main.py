"""Read-only CLI report for Promotion Recommendation Engine v0.1."""
from __future__ import annotations

from config import ConfigurationError, load_database_config, load_recommendation_config
from database import DatabaseError, fetch_product_economics, fetch_promotion_states
from promotion_recommendations import build_promotion_recommendations


def main() -> int:
    try:
        items = build_promotion_recommendations(
            fetch_promotion_states(load_database_config()),
            fetch_product_economics(load_database_config()),
            load_recommendation_config(),
        )
    except (ConfigurationError, DatabaseError) as error:
        print(f"ERROR: {error}")
        return 2
    print("offer_id | action_id | promotion | state | current_price | action_price | confirmed_effective_price | confirmed_profit_per_unit | confirmed_margin | economics_confidence | recommendation | numeric_projection_allowed | reason")
    for item in items:
        print(" | ".join(str(value) if value is not None else "NULL" for value in (
            item.offer_id,
            item.action_id,
            item.action_title,
            item.source_list_type,
            item.current_price,
            item.action_price,
            item.confirmed_effective_price,
            item.confirmed_profit_per_unit,
            item.confirmed_margin_percent,
            item.economics_confidence,
            item.recommendation,
            item.numeric_projection_allowed,
            "; ".join(item.reasons),
        )))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
