# Project Status

## Baseline

Date: 2026-08-14

The project is based on a local Dockerized n8n + PostgreSQL stack. The canonical workflow is `OZON workflow - Phase A`.

Live workflow ID: `B2DiIq630Yb2fXR8`
Canonical workflow JSON: `n8n/workflows/OZON_workflow_Phase_A.json`.

The repository copy is sanitized for source control. Secrets remain in local n8n credentials and are not committed.

## Taxable Revenue investigation — accounting contract confirmed, tax recognition partial

Official Ozon input documents used read-only and kept outside Git are the June
and July Monthly Realization Reports plus the July Order-Level Realization
Report. The July order-level document has 433 rows and 433 unique
`posting_number`; its five-offer totals reconcile exactly to the monthly
report.

For July 2026, the official accounting contour is: gross realised amount
138,224.71 RUB, returns 356.77 RUB, net realised amount 137,867.94 RUB,
partner-loyalty payments 1,803.32 RUB and reversals 3.57 RUB. The resulting
combined accounting candidate is 139,667.69 RUB. Ozon support confirms that
partner-loyalty payments are separately reported in the Realization Report,
enter total accruals, have no separate closing document, and are accounted for
with sales; return-side payments are recorded separately. This does not by
itself establish a USN recognition date.

The read-only July Finance API extraction (`/v3/finance/transaction/list`)
returned 1,185 operations in two pages with no duplicate operation ID. Exact
report-to-finance coverage is 433/433 by posting and SKU where present. Its
critical result is that `accruals_for_sale` is neither `realised_amount` nor
`realised_amount + partner_loyalty_payment`, including both one-ruble cases;
it is therefore a management-economics/reconciliation field, not an automatic
taxable-revenue source. No separate same-posting finance operation equal to a
partner-loyalty payment was found.

Architectural roles are: Order-Level Realization Report — primary candidate
source for accounting/tax events; Monthly Realization Report — official period
reconciliation; `finance_operations` — management economics/reconciliation;
`postings` and `returns` — operational attribution. A future Tax Revenue Layer
must keep `REALIZATION`, `PARTNER_LOYALTY_PAYMENT`, `RETURN`,
`PARTNER_LOYALTY_REVERSAL` and `CORRECTION` distinct from commission,
logistics, advertising, COGS and payout. It may later derive gross revenue,
adjustments, net revenue, USN tax, a separate additional-1% insurance
contribution, conditional VAT, and after-tax economic profit.

Tax Engine status: **NOT_IMPLEMENTED / WAITING_FOR_TAX_DATE_CONTRACT**. Before
implementation, validate official FNS rules for marketplace/agent USN income
date, loyalty-payment date, return timing, 2026 USN rules, the 2026 additional
1% insurance limits, and VAT applicability/threshold/rate for this taxpayer.
Next tax step: **official FNS tax-date / USN / 1% / VAT validation**.

## Commercial Baseline Collection v0.1 — active

Separate read-only daily automations now accumulate commercial flows without
mixing their time semantics. `Seller Analytics Daily Collection v0.1`
(`SELLERDAILYV1`, 07:10 Europe/Moscow) stores only confirmed ordered revenue
and ordered units at `offer_id × business_date`. `CPC Daily Collection v0.1`
(`CPCDAILYV1`, 07:30 Europe/Moscow) dynamically selects CPC/SKU campaigns and
stores their confirmed daily Performance metrics with exact SKU attribution.
Both persist only through the private commercial-baseline collector.

Migration 004 extends new promotion snapshots with the confirmed nullable
`current_boost`, `min_boost`, and `max_boost` fields; the existing active
`PROMOAUTOV1` schedule remains every six hours. State, daily demand and
advertising flows, delivery outcomes, and finance recognition remain separate.
The first checkpoint is intentionally **PARTIAL**: history has only started
accumulating. CPC rows for an inactive campaign can still contain attributed
orders; until the Performance attribution-window semantics are confirmed, they
must not be interpreted as current campaign activity. The project remains at
**Control Level 0 (read-only)**.
The next stage is **Safe Commercial Experiment v0.1**; recommendations and all
commercial control actions remain disabled.

## Daily Commercial Brief v0.1 — read-only deterministic source of truth

`python -m services.daily_brief.main [--date YYYY-MM-DD]` builds a compact and
an extended JSON-safe report from canonical `products`, Seller daily demand,
delivery/return outcomes, delivery-date confirmed finance via
`vw_orders_profit_final`, the latest successful promotion state, and CPC daily
history. It reads all PostgreSQL sources in a read-only transaction and makes
no Ozon, database, collector, schedule, or tax-layer change.

The brief makes time semantics explicit: `ordered_revenue` is ordered flow,
not confirmed revenue; finance is delivery-date confirmed and is not mixed
into ordered flow; returns are shown as events/units without inventing cohort
buyout; `profit_before_tax` is the only profit term because the Tax Engine is
not implemented. Missing or stale sources remain `NULL`/`NOT_AVAILABLE` and
produce warnings. Participating promotions and candidates remain separate;
inactive CPC attributed orders are historical attribution, not current
campaign activity. Future PDF/email/Telegram delivery must consume these
deterministic payloads rather than recompute metrics or use an LLM.

## Daily Brief Delivery v0.1 — prepared, not active

Deterministic renderers now produce a five-page Cyrillic-safe A4 PDF, a short
HTML email body and a compact Telegram message from the same Daily Brief
payload. Delivery never recalculates business metrics. The presentation
separates the operational `business_date` from `confirmed_through_date`; stale
finance is labelled explicitly, `NULL` is never displayed as zero, cohort
buyout and after-tax profit remain unavailable.

The channel-independent orchestration contract uses idempotency key
`channel + business_date + report version`, isolates email/PDF failures from
Telegram failures, and scopes manual tests separately from production. Target
schedule is 08:15 Europe/Moscow after morning freshness checks, but no delivery
workflow is active. Activation requires visual PDF approval plus manually
created n8n Gmail OAuth2 and Telegram Bot credentials and one manual test per
channel. Generated previews and all credential material remain outside Git.

## Ozon Performance API — working read-only baseline

The private `Ozon Performance OAuth2` n8n credential type is deployed with
runtime-only Client ID and Client Secret storage. Its client-credentials token
exchange and Bearer-token handling were confirmed by the isolated manual,
disabled workflow `TEST - Ozon Performance API Contract`
(`a2qlNkgKiIpsPEmF`). No credential material or access token is serialized in
the workflow, execution output, logs, or repository.

The real read-only `GET /api/client/campaign` call returned six campaigns: five
CPC `SKU` campaigns are inactive, and CPO `SEARCH_PROMO` campaign `29676456`
is running. CPC product attribution and daily statistics are confirmed and now
feed the read-only baseline history. CPO attribution remains blocked.

## CPC campaign-to-product attribution — confirmed

Read-only `GET /api/client/campaign/29798564/v2/products` returned
`sku=4601821825`. An exact read-only match through `products.sku` maps it to
canonical offer `УФ 001Б`; title-based and fuzzy attribution are prohibited.
The CPC product operation and safe HTTP error formatter are part of the private
custom node. The formatter exposes only HTTP status plus redacted Ozon error
body/code/message.

CPO `SEARCH_PROMO` product attribution remains blocked until Ozon publishes a
confirmed read-only CPO product/state contract. The CPC product endpoint was
rejected by the real CPO campaign and must not be reused for it.

## Promotions Persistence v0.1 — deployed and verified

The private Promotions Collector now has an explicit, transactional persistence
mode for `promotion_runs` and immutable `promotion_snapshots`. The existing
`POST /v1/promotions/collect` endpoint remains non-persistent by default;
PostgreSQL writes require `persist: true`. A successful repeated
`collection_ref` is returned as an idempotent replay, while duplicate logical
details are rejected before persistence.

Migration `database/migrations/002_promotion_snapshots_v1.sql` is applied after
a verified PostgreSQL backup. One controlled TEST collection created one
successful run and 10 immutable details (5 `PARTICIPATING`, 5 `CANDIDATE`) for
5 mapped offers. Replaying the same `collection_ref` created no additional
rows. The manual TEST workflow was returned to its default non-persistent mode.

## Promotion Snapshot Automation v0.1 — live, read-only Ozon collection

Separate workflow `Ozon Promotions Snapshot Automation v0.1`
(`PROMOAUTOV1`) is published on a six-hour schedule and is not connected to
Phase A. Each run starts from the current Actions list, makes exactly one
read-only Products request and one read-only Candidates request per returned
action, preserves their action association, and sends the completed payload
with `persist: true` only to the private Promotions Collector.

The controlled run covered 4 actions and persisted 5 `PARTICIPATING` plus 14
`CANDIDATE` records for 5 mapped offers with `mapping_status=valid` and no
errors. Counts changed from 1/10 to 2/29; the new run has no duplicate logical
snapshots. The TEST workflow remains manual, disabled and non-persistent.

## Promotions checkpoint — 2026-08-15

Promotions Data Collector v0.1 and Promotion Monitoring Tool v0.1 are
complete. Promotion Recommendation Engine v0.1 is implemented read-only and
is deliberately not connected to the AI Analyst: every current state is
`REVIEW`, and numeric projection remains prohibited without confirmed
promotion economics.

Last controlled collection:
`ozon-actions-6h-2026-08-15T06:00:00.000Z` — 4 actions, 5 participating, 14
candidates, 5 mapped offers, 0 unmapped, valid data quality and 0 errors.
PostgreSQL is at 2 `promotion_runs` / 29 `promotion_snapshots`; duplicate
logical snapshots in that collection are 0.

Target commercial state is: Price + Ozon Actions + Promotion/Advertising
instruments + Sales velocity + Deliveries + Confirmed Finance + Unit
Economics. A future Commercial Decision Engine must assess their combination,
not an instrument in isolation. Before any promotion is considered it must
separate deterministic cost impact, break-even volume, required uplift,
historically observed uplift, compatibility, profit/unit, margin,
profit/day/total profit and confidence. Expected sales uplift is `null` unless
historically evidenced.

The current evidence gap is promotion state → delivery → confirmed unit
economics → sales velocity. Six-hour automation now accumulates the necessary
state history. Next: **Ozon Performance API Authentication & Contract
Validation v0.1** — first confirm official auth and real read-only Analytics,
CPC and CPO response contracts; do not begin Advertising Collector before
that confirmation.

## Promotion Recommendation Engine v0.1 — implemented, read-only

The conservative engine combines the latest promotion state with the existing
confirmed v0.2 unit-economics output. All current Elastic Boosting
participation and Maximum Boosting candidate records are confirmed as facts,
but every one of the 10 states remains `REVIEW` with
`numeric_projection_allowed=false`: there is no proven promotion-state to
delivery/effective-price economics link. The engine does not calculate future
profit or margin and does not recommend JOIN/LEAVE without that evidence.

Next: accumulate promotion snapshots and then establish a confirmed
promotion-state → delivery → unit-economics attribution layer. It must
reconstruct the full commercial state without assuming sales uplift.

## Repository and source-control status

## Promotion Monitoring Tool v0.1 — live and read-only

`get_promotion_monitoring` is available to the live OZON AI Analyst through
the existing private recommendation sidecar. It reads only the latest
successful `promotion_runs` / `promotion_snapshots` collection and returns
compact product-level participation and candidate states, confirmed action
prices, dates and data-quality status. Its deterministic signals are
`ACTIVE_PARTICIPATION`, `AVAILABLE_CANDIDATE`, `PROMOTION_ENDING_SOON`,
`ACTION_PRICE_BELOW_CURRENT_PRICE` and `DATA_QUALITY_ISSUE`; the ending-soon
window is configured by `EFA_PROMOTION_ENDING_SOON_DAYS` (default 7).

The live E2E call confirmed the tool invocation: all five offers currently
have one participating Elastic Boosting record and one Maximum Boosting
candidate record. The AI presents facts only: it neither joins/leaves actions
nor makes profitability or price-change recommendations.

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
