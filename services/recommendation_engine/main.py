"""Read-only CLI report for Price & Profit Recommendation Engine v0.1."""

from __future__ import annotations

from config import ConfigurationError, load_database_config, load_recommendation_config
from database import DatabaseError, fetch_product_economics
from rules import build_recommendation


def _display(value: object) -> str:
    return "NULL" if value is None else str(value)


def main() -> int:
    try:
        database_config = load_database_config()
        recommendation_config = load_recommendation_config()
        economics = fetch_product_economics(database_config)
    except (ConfigurationError, DatabaseError) as error:
        print(f"ERROR: {error}")
        return 2
    recommendations = [build_recommendation(product, recommendation_config) for product in economics]
    print("offer_id | current_price | profit | profit_per_unit | margin_percent | action | priority | proposed_price | reason")
    for item in recommendations:
        print(" | ".join((item.offer_id, _display(item.current_price), _display(item.profit), _display(item.profit_per_unit), _display(item.profit_margin_percent), item.action, item.priority, _display(item.proposed_price or item.proposed_price_range), "; ".join(item.reasons))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
