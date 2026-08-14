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
    print("offer_id | current_price | current_price_since | last_effective_price | last_delivery | last_profit_per_unit | last_margin | current_status | action | proposed_price | reasons")
    for item in items:
        print(" | ".join(str(x) if x is not None else "NULL" for x in (item.offer_id, item.current_price, item.current_price_since, item.last_confirmed_effective_price, item.last_confirmed_delivery_date, item.last_confirmed_profit_per_unit, item.last_confirmed_margin, item.current_price_economics_status, item.action, item.proposed_price, "; ".join(item.reasons))))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
