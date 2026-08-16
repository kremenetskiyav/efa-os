# Changelog

## 2026-08-16

- Recorded the commercial recovery checkpoint: June remains a launch period;
  all historical June–July CPC campaigns are `DO_NOT_REACTIVATE` under the
  mandatory 15% contribution-margin-after-CPC policy. `УФ 004Б` is the sole
  current modelled non-CPC priority at 16.45% margin, but is
  `NOT_CONFIRMED` until five post-2026-08-11 delivered units validate its
  price interval and finance settlement. No commercial write experiment is
  approved.

- Recorded the mandatory Commercial Profit Policy: COGS recovery and all
  attributable Ozon, advertising/promotion and management-tax-reserve costs
  precede distributable profit; the hard floor for controlled commercial
  decisions is 15% contribution margin after applicable reserve. The annual
  57,390 RUB insurance obligation remains business-level.

- Added Tax Engine v0.1 and applied migration 007 after a validated PostgreSQL
  backup. Official June/July monthly Realization reports reconcile exactly with
  the order-level documents and persist idempotently as 2 import runs and 8
  period-only events. YTD accounting income through July is 156,074.83 RUB;
  tax-date and partner-loyalty semantics remain partial, and no Tax Engine
  output is connected to Daily Brief or commercial decisions.

- Activated Price Refresh Automation v0.1: a six-hour private read-only Seller
  price collection for canonical products. Successful collection runs provide
  price freshness independently of change-only price history; the confirmed
  optional `marketing_price` field is stored as `NULL` when absent.

- Added the local-only Daily Brief runtime-secret deployment contract: a
  tracked names-only template, masked interactive initializer with
  current-user ACL, and a fail-safe, `--env-file` Docker Compose wrapper that
  targets only `efa-daily-brief` and retains an image rollback reference.
- Redeployed `efa-daily-brief` using the protected local runtime env and
  confirmed the 2026-08-15 `SUCCESS_ZERO` CPC presentation through one
  read-only Telegram representation request. No channel message was sent.

- Fixed Daily Brief CPC freshness to use successful `cpc_collection_runs`, not
  the presence of CPC detail rows. A successful zero-row report is now
  explicitly `SUCCESS_ZERO`, preserves zero spend/orders without synthetic
  SKU rows, and no longer produces the false "CPC requires refresh" warning.
- Updated the shared n8n PostgreSQL credential host from
  `host.docker.internal` to private Docker DNS `efa-postgres:5432`, removing
  the unnecessary host-gateway dependency for n8n-to-PostgreSQL traffic.

- Activated `Ozon Daily Commercial Brief Delivery v1` (`Kf241Y5kzETghygL`) at
  08:15 Europe/Moscow. It uses the existing deterministic rendering bridge for
  Gmail HTML/PDF and compact Telegram delivery, keeps per-channel production
  idempotency in n8n static data, and does not recalculate commercial metrics
  or call Ozon. Manual test workflows remain inactive.

- Added the private read-only `efa-daily-brief` rendering service on the
  existing `efa-tools` network. It reuses the deterministic Daily Brief and
  existing Telegram, HTML and PDF renderers, exposes no host port and holds no
  channel or Ozon credentials. A controlled request from `efa-n8n` for
  2026-08-14 validated all five offers and the five-page Cyrillic PDF; the
  initially prepared schedule was subsequently activated as recorded above.

- Prepared Daily Brief Delivery v0.1 before its subsequent activation. Added a
  deterministic five-page A4 PDF renderer, HTML email and Telegram text
  renderers, latest-confirmed-economics separation, real-data trend charts,
  channel idempotency and independent failure states. No email or Telegram
  message was sent at that preparation point; later manual channel E2E and
  visual approval completed before the 08:15 Europe/Moscow activation.

## 2026-08-15

- Added Daily Commercial Brief v0.1: a deterministic, read-only CLI that
  assembles canonical product state, Seller ordered flow, delivery/return
  outcomes, delivery-date confirmed `profit_before_tax`, latest
  promotion/Elastic Boost state and CPC history into extended and compact
  JSON-safe payloads. It preserves source freshness and `NULL` versus zero,
  keeps candidates separate from participation, never calculates cohort
  buyout or after-tax profit, and performs no Ozon or PostgreSQL write.

- Recorded the taxable-revenue accounting-data checkpoint from official Ozon
  June/July Realization Reports and a two-page, read-only July Finance API
  extraction. July order-level and monthly totals reconcile exactly; the
  433 report rows map exactly to finance by posting/SKU where present.
  `accruals_for_sale` is confirmed unsuitable as an automatic taxable-revenue
  field because it differs from both realization-report candidates, including
  the one-ruble cases. Tax recognition remains partial: no tax engine, formula,
  database schema, production data or workflow was changed.

- Added Commercial Baseline Collection v0.1: immutable daily Seller Analytics
  demand (`ordered_revenue`, `ordered_units`), dynamic CPC/SKU Performance
  history with exact SKU-to-offer attribution, and nullable Elastic Boosting
  fields on new promotion snapshots. Controlled runs mapped all five Seller
  SKUs and the two CPC rows returned for 2026-08-14; daily workflows are active
  at 07:10 and 07:30 Europe/Moscow. All Seller/Performance calls remain
  read-only and no price, promotion, bid, budget, or campaign state is changed.

- Added a constrained read-only CPC campaign-products operation to the private
  Ozon Performance node. Real campaign `29798564` returned SKU `4601821825`,
  which exactly maps through `products.sku` to `УФ 001Б`; no title or fuzzy
  matching is used. CPO/`SEARCH_PROMO` attribution remains blocked: the CPC
  endpoint was rejected for campaign `29676456` and will not be reused.
  Added redacted HTTP-error formatting that exposes status and Ozon error
  body/code/message without credential material.

- Added the reproducible private n8n Ozon Performance API extension and
  confirmed its runtime-only OAuth2 client-credentials flow through the
  isolated manual/disabled `TEST - Ozon Performance API Contract` workflow.
  A real read-only campaign-list call returned six campaigns: five inactive
  CPC/SKU campaigns and one running CPO/SEARCH_PROMO campaign (`29676456`).
  Credentials and tokens were not serialized to the workflow, output, logs or
  repository. Product attribution and campaign statistics remain unvalidated;
  the next step is campaign → product contract validation.

- Recorded the Promotions checkpoint: the active six-hour Action snapshot
  history is the evidence foundation for future commercial-state analysis.
  Promotion recommendation remains conservative/read-only until promotion
  state can be matched to delivery economics and sales velocity. The next
  gated step is Performance API authentication and read-only contract
  validation for Analytics, CPC and CPO.

- Added and activated Promotion Snapshot Automation v0.1 as a separate
  six-hour n8n workflow (`PROMOAUTOV1`). It collects every action returned by
  the read-only Actions endpoint, preserves per-action Products/Candidates
  association, and persists only through the private collector. The controlled
  run stored 5 participating and 14 candidate snapshots across 4 actions with
  complete mapping and no duplicate logical details; Phase A and the manual
  non-persistent TEST workflow were not changed.

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
