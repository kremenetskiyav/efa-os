# Changelog

## 2026-08-14

- Added the strict, read-only function-tool contract
  `get_price_profit_recommendations` over the existing Price & Profit
  Recommendation Engine v0.1, with local unit tests and no changes to n8n,
  PostgreSQL, or Snapshot Layer.

- Added the read-only Price & Profit Recommendation Engine v0.1 for the five
  current products. It uses deterministic rules and reports `KEEP`,
  `CONSIDER_RAISE`, or `REVIEW_DATA` without changing prices.
- Added conservative configurable low-margin threshold
  `EFA_RECOMMENDATION_LOW_MARGIN_PERCENT` (default `15`).
- Confirmed the engine report against local PostgreSQL. It does not calculate
  a target price without a confirmed marginal commission and logistics model.

## 2026-08-14

- Verified the five core AI analytical tools together on `УФ 005Б` for a 30-day period: `OZON Analytics`, `OZON Regional Analytics`, `OZON Price History`, `OZON Returns Analytics`, and `OZON Stock History`.
- Confirmed that regional profit reconciles with the overall product profit returned by `OZON Analytics`.
- Resolved tool integration issues involving duplicate `offer_id` definitions, SQL quoting/type handling, and the `days` argument type.
- Identified a remaining correctness issue in the legacy `Tool — Анализ проблем товаров`: its `orders_count`, `avg_profit`, and `commission_rate` do not match the verified financial source of truth.
- Established `OZON Analytics` as the source of truth for product financial metrics: `profit`, `profit_per_unit`, `revenue`, `commission`, `logistics`, `payout`, and `cost`.
- Defined the next work session: fix only the legacy problem-analysis tool, retest, and audit the AI response before adding new analytical layers.

## 2026-08-13

- Established GitHub repository as the project source-control layer.
- Documented current local n8n + PostgreSQL architecture.
- Recorded the Phase A analytical baseline and regional logistics classification.
- Added security gate: production workflow exports containing embedded credentials must not be committed to the public repository.
- Added roadmap for the next development phase.
