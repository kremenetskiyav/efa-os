"""Read-only CLI report for Price Recommendation Engine v0.2."""
from __future__ import annotations
from config import ConfigurationError, load_database_config, load_recommendation_config
from database import DatabaseError, fetch_product_economics
from rules import build_recommendation

def main() -> int:
    try:
        items = [build_recommendation(x, load_recommendation_config()) for x in fetch_product_economics(load_database_config())]
    except (ConfigurationError, DatabaseError) as error:
        print(f"ERROR: {error}")
        return 2
    print("offer_id | current_price | effective_price | profit_per_unit | margin | action | proposed_price | expected_profit_per_unit | expected_margin | confidence | reasons")
    for item in items:
        print(" | ".join(str(x) if x is not None else "NULL" for x in (item.offer_id, item.current_price, item.current_effective_price, item.profit_per_unit, item.profit_margin_percent, item.action, item.proposed_price, item.expected_profit_per_unit, item.expected_margin_percent, item.confidence, "; ".join(item.reasons))))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
