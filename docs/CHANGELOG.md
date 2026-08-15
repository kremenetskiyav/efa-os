# Changelog

## 2026-08-15

- Added the read-only Promotion Recommendation Engine v0.1. It reuses the
  persisted promotion state and confirmed v0.2 economics without projecting
  action-price profit or margin. Elastic participation and Maximum candidates
  are factual; JOIN/LEAVE remains blocked until promotion-to-delivery
  economics is observed. The next priority is accumulating promotion
  snapshots for that evidence.

- Added Promotion Monitoring Tool v0.1 to the private recommendation sidecar
  and live OZON AI Analyst. `get_promotion_monitoring` reads the latest
  successful persisted promotion collection only, exposes deterministic
  participation/candidate, price, ending-soon and data-quality signals, and
  performs no Ozon or PostgreSQL writes. The live E2E call confirmed routing
  to the tool (about 4,331 tokens); it reports the five current participating
  and candidate offer states without recommending JOIN/LEAVE actions.

- Deployed Promotions Persistence v0.1 after a verified PostgreSQL backup.
  Migration 002 created `promotion_runs` and `promotion_snapshots`; the first
  controlled collection stored 1 successful run and 10 details with complete
  mapping. Replaying the same `collection_ref` preserved counts at 1/10 and
  returned `idempotent_replay=true`. The TEST workflow was restored to its
  manual, non-persistent default.

- Completed the deploy-ready Promotions Persistence v0.1 layer. The private
  collector now supports explicit `persist: true`, one transaction for run,
  batch product mapping, immutable details and final status, rollback on any
  failure, and successful `collection_ref` replay without duplicate writes.
  Migration 002 remains unapplied and production promotion writes remain zero.

- Added `get_profit_cost_anomalies` v0.1 to the existing private
  recommendation sidecar and OZON AI Analyst. It compares equal confirmed
  delivery periods read-only and supports deterministic profit, margin,
  logistics, commission, other-expense and data-quality signals.
- Confirmed the live anomaly-tool call. Optimized its general-answer
  presentation: `DATA_QUALITY_ISSUE` now reports only insufficient confirmed
  units and is never presented as a profit/cost business anomaly; detailed
  period metrics are shown only on an explicit detailed or product request.

- Deployed Price Recommendation Engine v0.2 to the private recommendation-tool
  sidecar and synchronized its v0.2 context with the live OZON AI Analyst.
  End-to-end execution called `get_price_profit_recommendations`; all five
  current price intervals were correctly reported as `NOT_YET_CONFIRMED`, so
  the AI recommended observation rather than another price change. Numeric
  `proposed_price` remained `null` (about 3,336 tokens).
- Expanded the nullable `action` contract to include `CONSIDER_LOWER` while
  preserving real JSON `null` for unfiltered calls.

- Corrected v0.2 price-window timing: delivered-posting date now selects the
  active price-history interval, while finance-operation date is not used as
  a sale-date proxy. Added current-price confirmation fields and conservative
  `NOT_YET_CONFIRMED` handling when the changed price has no sufficient
  delivered sample.

- Added Price Recommendation Engine v0.2: read-only confirmed unit economics
  from delivered posting quantity, historical observed-effective-price windows,
  `CONSIDER_LOWER`, confidence gates and a configurable maximum price step.
  Numeric prices are limited to observed windows; no tariff, tax or unknown
  price extrapolation is used.
- Set `vw_orders_profit_final` as the profit source of truth. Product-level
  other expenses are included only when a posting key uniquely identifies one
  delivered product line; unallocated CPC, insurance and disposal costs remain
  excluded.

- Completed Token Optimization v0.1 for the live OZON AI Analyst workflow.
  End-to-end execution confirmed `get_price_profit_recommendations`, correct
  recommendations, and `proposed_price = null`; observed usage fell from about
  7,262 to 2,458 tokens (about 66%).
- Fixed the HTTP Request Tool JSON Body so separately supplied nullable
  `offer_id` and `action` parameters are serialized as JSON `null`, not
  `undefined` or the string `"null"`.
- Synchronized the successful live workflow to the canonical workflow JSON.
  Prompt caching is automatically applicable, while current n8n execution
  metrics do not report cache usage.

## 2026-08-14

- Connected the canonical OZON AI Analyst workflow to the new internal
  `get_price_profit_recommendations` AI tool through a private Docker-network
  HTTP adapter. No port, Docker socket, PostgreSQL schema, n8n business logic,
  or recommendation rules were added.

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
