# Project Status

## Baseline

Date: 2026-08-14

The project is based on a local Dockerized n8n + PostgreSQL stack. The canonical workflow is `OZON workflow - Phase A`.

Live workflow ID: `B2DiIq630Yb2fXR8`
Canonical workflow JSON: `n8n/workflows/OZON_workflow_Phase_A.json`.

The repository copy is sanitized for source control. Secrets remain in local n8n credentials and are not committed.

## Promotions Persistence v0.1 — ready for deployment

The private Promotions Collector now has an explicit, transactional persistence
mode for `promotion_runs` and immutable `promotion_snapshots`. The existing
`POST /v1/promotions/collect` endpoint remains non-persistent by default;
PostgreSQL writes require `persist: true`. A successful repeated
`collection_ref` is returned as an idempotent replay, while duplicate logical
details are rejected before persistence.

Migration `database/migrations/002_promotion_snapshots_v1.sql` is prepared but
has **not** been applied. Production promotion writes remain zero. The next step
is a PostgreSQL backup and validation, followed by applying migration 002 and
one controlled persisted TEST-workflow collection.

## Repository and source-control status

- Commit `7dcdc2e` (`feat: synchronize repository and add Snapshot Layer foundation`) was created and pushed to `origin/main`.
- The local `main` branch is synchronized with GitHub.
- The repository now contains the Snapshot Layer v1 architecture documents, its reviewed PostgreSQL DDL migration, the safe cost-price import script, and secret-free configuration/dependency files.
- The PostgreSQL migration has **not** been applied. No PostgreSQL schema or production data was changed as part of this repository synchronization.

## Completed analytical foundation

The following six AI-facing tools are now verified in the live workflow:

1. `Tool — Анализ проблем товаров` — verified and synchronized with the current financial methodology.
2. `OZON Analytics` — verified.
3. `OZON Regional Analytics` — verified.
4. `OZON Price History` — verified.
5. `OZON Returns Analytics` — verified.
6. `OZON Stock History` — verified.

All five specialized OZON analytical tools were also individually tested through `OZON AI Analyst` using `УФ 005Б` and a 30-day period. Routing tests confirmed that each request reaches the correct specialized tool without unnecessary calls.

## Verified financial baseline — УФ 005Б

Latest 30-day test window:

- `orders_count`: 14
- `delivered_units`: 15
- `revenue`: 11,444.00 ₽
- `commission`: -4,856.36 ₽
- `logistics`: -1,706.81 ₽
- `payout`: 4,880.83 ₽
- `cost`: 2,490.00 ₽
- `profit`: 2,390.83 ₽
- `profit_per_unit`: 159.39 ₽

Regional profitability reconciles with the overall product profit.

## Verified price / returns / stock baseline — УФ 005Б

Price history:

- first price: 901.00 ₽
- current price: 667.00 ₽
- total change: -234.00 ₽ / -25.97%
- one recorded price change

Returns:

- 1 returned unit out of 15 delivered units
- returned amount: 811.00 ₽
- reason: `Покупатель отказался при вручении: товар не подошел`
- status: `На складе Ozon`

Stock:

- FBO: current 0
- FBS: current 381
- rFBS: current 0

## Problem-analysis tool status

The legacy `Tool — Анализ проблем товаров` was corrected and re-tested.

The tool now uses the same financial methodology as `OZON Analytics` and returns, among other fields:

- `orders_count`
- `delivered_units`
- `profit`
- `profit_per_unit`
- `commission_per_order`
- `logistics_per_unit`
- `profit_alert`
- `logistics_alert`
- `commission_alert`
- `reasons`
- `recommended_action`

The AI presentation rules were also updated so that only alert fields corresponding to actual reasons are shown. Artificial three-field output limits were removed.

## Current architecture state

The project has moved from a reactive analytical chatbot toward an autonomous monitoring architecture.

Current architecture:

`OZON APIs / data sources -> PostgreSQL -> analytical views/tools -> OZON AI Analyst`

Dockerized infrastructure remains the execution environment for n8n and PostgreSQL.

## Price & Profit Recommendation Engine v0.1

A read-only deterministic recommendation service is available in
`services/recommendation_engine/`. It uses canonical `products.offer_id`, the
latest Ozon price point, `vw_orders_profit_final`, and `vw_product_analytics`.
It reports `KEEP`, `CONSIDER_RAISE`, or `REVIEW_DATA`; it does not change
prices or calculate a target price without a confirmed marginal commission and
logistics model.

The initial live report covered all five current products. It identified two
low-margin `CONSIDER_RAISE` cases, two `KEEP` cases, and one `REVIEW_DATA`
case because the existing profit views disagree for that product. No database,
n8n, Ozon, or Snapshot Layer data was modified.

### AI function-tool contract

The engine now exposes the minimal read-only function-tool contract
`get_price_profit_recommendations`. It returns JSON-safe deterministic results
for all products or an optional canonical `offer_id` / recommendation-action
filter. The contract does not connect to n8n or alter PostgreSQL; it is the
next integration point for OZON AI Analyst.

### OZON AI Analyst price-recommendation tool

The canonical n8n workflow now includes `get_price_profit_recommendations` as
an AI tool. It calls a private Docker-network HTTP adapter which invokes the
existing Python engine; no recommendation rules were copied into n8n or SQL,
and the adapter exposes no host port. The provided Compose fragment must be
included with the local runtime Compose file before the sanitized workflow is
imported into the production n8n instance.

### Token Optimization v0.1

The live `OZON AI Analyst` workflow was synchronized to the canonical JSON and
successfully tested end-to-end with `get_price_profit_recommendations`.

- The agent correctly called the tool and returned `CONSIDER_RAISE` for
  `УФ 001Б` and `УФ 002Б`, and `REVIEW_DATA` for `УФ 004Б`.
- `proposed_price` remained `null`; the AI did not invent a target price.
- Prompt and tool-context reduction lowered the observed run from about
  `7,262` to `2,458` tokens (about 66%).
- The HTTP Request Tool now serializes `offer_id` and `action` separately,
  preserving absent filters as JSON `null` rather than `undefined` or the
  string `"null"`.
- Prompt caching is automatically applicable to the stable prompt prefix, but
  the current n8n execution UI does not expose its cache metrics.

## Price Recommendation Engine v0.2

v0.2 now calculates read-only, confirmed unit economics from delivered
posting/product quantity and `products.cost_price`, rather than deriving cost
from an order-level view. It uses delivery finance data for revenue,
commission, logistics and payout, and includes return/package expenses only
when their normalized posting key has one delivered product line. CPC,
insurance, disposal, taxes and any unallocated charge remain excluded.

Historical windows are grouped by observed effective revenue per unit, not by
the display price. A numeric proposed price is allowed only for an observed
window with sufficient sample size, better confirmed unit economics and a
configurable maximum step. The engine never extrapolates an unknown price.
`vw_orders_profit_final` is the profit source of truth; its discrepancy with
`vw_product_analytics` no longer independently causes `REVIEW_DATA`.

Current-price confirmation is based on `postings.delivering_date`, not the
later financial-recognition timestamp. The current `price` receives
`CONFIRMED` economics only after sufficient delivered quantity inside its
price-history interval; otherwise it is `NOT_YET_CONFIRMED`, retains no
proposed price, and requests observation. Historical delivery economics is
never transferred to a later display price.

### Live v0.2 AI integration

The private `get_price_profit_recommendations` sidecar and live OZON AI
Analyst are synchronized with v0.2. The confirmed end-to-end request used the
tool and returned all five current intervals as `NOT_YET_CONFIRMED`: the
current price has no sufficient confirmed deliveries after its start date.
The AI recommends observation only, uses `last_confirmed_*` as historical
context, and returns no numeric price (`proposed_price = null`). The observed
run used about 3,336 tokens.

Next: **Profit & Cost Anomaly Tool v0.1** → connection to OZON AI Analyst.

### Profit & Cost Anomaly Tool v0.1

`get_profit_cost_anomalies` is a private, read-only AI tool in the existing
recommendation sidecar. It compares two equal confirmed delivery periods using
`vw_orders_profit_final` and reports deterministic profit, margin, commission,
logistics, other-expense and data-quality signals. The live AI integration is
confirmed. For general questions its presentation is compact: an insufficient
period is reported only as `НЕДОСТАТОЧНО ДАННЫХ` with confirmed units versus
the minimum sample; calculated changes are not presented as business anomalies.
Detailed current/baseline metrics require a product-specific or explicit
detail request.

## Snapshot Layer v1 — architecture complete

The project has completed the architecture and DDL design for the first Autonomous Monitoring Core layer. The relevant documents are:

- `docs/architecture/SNAPSHOT_LAYER_V1.md`
- `docs/architecture/SNAPSHOT_LAYER_DDL_DESIGN_V1.md`
- `database/migrations/001_snapshot_layer_v1.sql`

The migration is versioned and reviewed, but it remains unapplied. It creates the planned `snapshot_runs`, `product_snapshots`, and `change_events` tables only after explicit approval and manual execution.

The v1 MVP is intentionally narrow:

- the only event type is `PRICE_CHANGED`;
- price comparisons use immutable product snapshots and the canonical `products.offer_id`;
- repeated runs are designed to be idempotent;
- AI may analyse facts and provide recommendations, but it performs no automatic actions;
- no product, price, promotion, stock, or OZON setting is changed automatically.

## Next phase — Snapshot Layer implementation

The next stage is **not** to add more ad-hoc SQL tools. The priority is controlled implementation of the designed monitoring foundation.

Target architecture:

`OZON -> PostgreSQL -> current state snapshot -> previous state snapshot -> change detection -> Decision Engine -> AI interpretation -> alert/report`

### Completed design work

1. Audited the existing PostgreSQL schema and historical price/stock sources in read-only mode.
2. Defined the canonical v1 state model, immutable snapshot rules, UTC timestamps, and Europe/Moscow business dates.
3. Defined idempotency rules for runs, snapshots, and events.
4. Designed and versioned the v1 DDL migration without applying it.

### Implementation prerequisites

1. Review and explicitly approve manual application of the Snapshot Layer migration.
2. Implement the Snapshot Collector only after the migration is available.
3. Create deterministic `PRICE_CHANGED` detection from consecutive valid snapshots.
4. Validate the first scenario for `УФ 005Б`: `901 ₽ -> 667 ₽` (`-234 ₽`, `-25.97%`).
5. Keep detected facts separate from AI interpretation and recommendations.

### Phase 2 — Autonomous business monitoring

7. Automatic sales monitoring.
8. Automatic price monitoring.
9. Automatic promotion/campaign monitoring.
10. Automatic advertising/promotion monitoring.
11. Cross-factor analysis: price -> sales -> payout -> cost -> profit.
12. Regional and stock-risk monitoring.

### Phase 3 — Decision Engine and AI assistant

13. Prioritize detected events.
14. Generate grounded explanations.
15. Generate recommendations without taking actions automatically.
16. Add daily summaries and targeted alerts.

### Phase 4 — Controlled automation

17. Accumulate evidence and history.
18. Introduce guarded semi-automatic actions.
19. Only later evaluate fully automatic changes to prices, promotions or other OZON settings.

## Design constraints for the next phase

- Do not modify the five verified analytical tools unless a new test proves a concrete defect.
- Prefer extending existing PostgreSQL structures over creating duplicates.
- Do not create a second database or parallel Docker stack.
- Keep secrets in local credentials only.
- Do not make causal claims from simple correlation without supporting data.
- Do not automatically change prices, promotions, advertising or inventory parameters.
- Build deterministic monitoring before adding more autonomous AI behavior.
