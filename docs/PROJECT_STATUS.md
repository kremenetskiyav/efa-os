# Project Status

## Transfer/recovery checkpoint — 2026-08-17

- GitHub `main` is canonical for code, migrations, sanitised workflow
  definitions, configuration templates and recovery documentation.
- The home computer remains the only production runtime. A second computer must
  default to `DEV_ONLY`; duplicate schedules and deliveries are prohibited.
- A validated PostgreSQL recovery backup and metadata-only transfer bundle are
  stored outside Git under `C:\Users\Andrey\.efa-os\`.
- Full recovery requires manual restoration of protected runtime settings and
  manual recreation/re-authorisation of n8n credentials. Secret values and
  private Ozon evidence are intentionally excluded from Git and the default
  manifest.
- Detailed restore order and mode controls are documented in
  `docs/TRANSFER_RECOVERY.md`.

## Premium exit baseline v0.1 — ABORTED / NOT REQUIRED FOR DECISION

- The home computer remains the only `PRODUCTION` host; any second computer is
  `DEV_ONLY`.
- The Premium trial is approved to expire without purchase at 00:20
  Europe/Moscow on 2026-08-19. The decision is `FREE OBSERVATION`.
- The trial will expire naturally without a Premium, Plus or Pro purchase.
  Post-expiry production collectors remain the authoritative entitlement
  evidence. The unfinished manual probe was intentionally discarded; no
  production workflow was changed.

## Baseline

Date: 2026-08-14

The project is based on a local Dockerized n8n + PostgreSQL stack. The canonical workflow is `OZON workflow - Phase A`.

Live workflow ID: `B2DiIq630Yb2fXR8`
Canonical workflow JSON: `n8n/workflows/OZON_workflow_Phase_A.json`.

The repository copy is sanitized for source control. Secrets remain in local n8n credentials and are not committed.

## Ozon Information Intelligence — production storage initialized

The first read-only Information Intelligence component now provides
deterministic canonicalization, structural diffing, compatibility classes and
an exact EFA-OS usage map for the official Seller and Performance OpenAPI
contracts. Initial observations are `BASELINE_CREATED`, not change alerts;
equivalent later observations are `SUCCESS_ZERO` / `NO_CHANGE`.

Both official URLs returned HTTP 307 anti-bot redirects during the single
approved live preview, so no browser workaround was attempted. Migration 008
is now applied. The manually supplied official 100-page seller-agreement PDF
was validated outside Git and persisted as the first immutable
`OZON_SELLER_AGREEMENT` baseline. Its repeat import is `SUCCESS_ZERO`: one
source and one snapshot remain, with no legal change event. Automated legal
polling and Daily Brief integration remain **not active**.

The source strategy is now final: automated official candidates are Ozon
Legal/Contract, Seller News, Ozon for dev and API contracts. Seller News is
currently `SOURCE_UNAVAILABLE / MANUAL_ONLY`: its confirmed official listing
returned HTTP 307 during the single allowed public preview, so no source or
article baseline was persisted and no schedule was created. Seller-specific
`Главное` notices use the same `OzonInformationEvent` model as manual evidence;
UI scraping, browser/session extraction and a public Seller-push webhook are
excluded. A dedicated local `gmail.readonly` adapter now reads the technical
`info.efa.ozon@gmail.com` mailbox without n8n, mailbox mutation or polling.
`OZON_GMAIL_NOTIFICATIONS` is registered through the same source/check/event
model. The first controlled collection found two authenticated FBS order
notifications; both were correctly classified `ROUTINE_OPERATIONAL / NO_EVENT`.
Gmail polling is **active hourly** with a 48-hour overlap window through the
protected local Python adapter. Its scope remains `gmail.readonly`; Daily Brief
integration is **not yet active**.

The deterministic Legal/Contract Monitor now adds semantic HTML/text/PDF
canonicalization, heading/clause/table units, legal unit diffing, structured
percentage/RUB/coefficient/date/deadline detection, economic watch concepts
and review-only impact routing. The canonical seller agreement is registered;
separate promotion, Performance and legal-entity-buyout URLs remain
`NEEDS_SOURCE_CONFIRMATION`. The first legal baseline is persisted through the
manual official-file path because deterministic HTTP retrieval is unavailable.
Seller `Главное` manual-evidence ingestion is active through the same common
event model: the first two operator-verified notices are persisted as one
`ACTION_REQUIRED` FBS review and one `WATCH` legal-entity-buyout review. There
is no automated Seller Hub collector. API baselines are not yet bootstrapped,
and Daily Brief integration is not active. No workflow, schedule or engine
changed.

## Commercial recovery checkpoint — UF004B settlement gate

June is retained as a **LAUNCH_PERIOD**. The historical June–July CPC
configuration is not sustainable: all five CPC campaigns failed the mandatory
15% contribution-margin-after-CPC floor and are **DO_NOT_REACTIVATE** under
their historical configuration. Historical attributed orders do not establish
incremental profit or reactivation eligibility.

Current non-CPC recovery priority is `УФ 004Б` (`SKU 4642180551`, product
`4861934500`). Its latest modelled state is 16.45% contribution margin at
seller price 899 RUB / `marketing_seller_price` 805 RUB, with COGS 179 RUB
and Elastic Boost 15%. This is **NOT_CONFIRMED**: the current price interval
started on 2026-08-11 and has no delivered units yet. No commercial write
experiment is approved.

The read-only settlement gate opens only after at least five `УФ 004Б` units
are delivered in that post-2026-08-11 interval. Each sample must be exactly
linked by posting and SKU to price-interval evidence and finance
`accruals_for_sale`, commission, logistics/services, acquiring and other
attributable operations. The gate reports mean, median, min, max and weighted
contribution margin; it passes only at a weighted margin of at least 15%.
It also validates whether current `marketing_seller_price` 805 RUB exactly
matches or is consistently related to `accruals_for_sale`. Until then,
PROMOAUTOV1, SELLERDAILYV1, CPCDAILYV1, Price Snapshot Automation and Daily
Brief Delivery continue unchanged and the project remains Control Level 0.

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

Tax Engine status: **ACTIVE / PARTIAL_DATA**. Its deterministic statutory state
is available from the persisted June/July ledger and the existing 2026 taxpayer
configuration. Exact tax dates and partner-loyalty semantics remain partial;
the engine therefore exposes its quality explicitly and does not convert
partial accounting evidence into confirmed offer-level tax economics.

## Commercial Baseline Collection v0.1 — active

### CPC Async Report Lifecycle v1 — CREATE active / POLLER active

The asynchronous Performance report lifecycle is now durable in the existing
`cpc_collection_runs` table. `CPCDAILYV1` remains active at 07:30
Europe/Moscow but now ends after reserving a business date, creating at most
one report and registering its UUID. It contains no wait or status loop.

`CPC Report Poller v1` (`CPCREPORTPOLLERV1`) is active every ten minutes. It
leases at most one pending UUID, makes one status request,
persists ready data transactionally and maps pending, terminal and two-hour
stuck states deterministically. It has no report-creation path.

Migration 010 is applied. The existing 2026-08-17 UUID
`191827e5-2c73-429a-9ce1-34b48f560a46` is retained as
`STUCK / NOT_STARTED`; the active poller does not reopen it and no replacement
report was created.
Daily Brief code and delivery remain unchanged.

### Operational / Finance Daily Collection v1 — active and runtime validated

`Ozon Operational Finance Daily Collection v1` (`OPFINDAILYV1`) is active at
05:40 Europe/Moscow. It collects Postings, Returns and Finance sequentially,
uses bounded pagination, one-second inter-source spacing, and three total HTTP
attempts with five seconds between attempts. Migration 011 records independent
`SUCCESS`, `SUCCESS_ZERO` or `FAILED` freshness for each source and business
date without changing the existing business-table keys.

The controlled recovery execution `1107` on 2026-08-18 completed the Finance
branch: 39 unique operations for 2026-08-14 through 2026-08-17. Its inclusive
upper-bound overread was corrected to the approved end-of-day boundary.
Postings and Returns initially failed before an external request because their
n8n JSON-body expressions did not compile (`invalid syntax`). After correcting
those expressions, the single approved node-level execution `1111` ran only
Postings and Returns and stopped before Finance. Both external requests,
normalization and persistence completed successfully in one page: Postings
`SUCCESS` with 256 normalized rows and Returns `SUCCESS` with 16 normalized
rows. The business tables contain 377 postings and 27 returns with zero key
duplicates. No Daily Brief delivery was triggered.

Separate read-only daily automations now accumulate commercial flows without
mixing their time semantics. `Seller Analytics Daily Collection v0.1`
(`SELLERDAILYV1`, 07:10 Europe/Moscow) stores only confirmed ordered revenue
and ordered units at `offer_id × business_date`. `CPC Daily Collection v0.1`
(`CPCDAILYV1`, 07:30 Europe/Moscow) dynamically selects CPC/SKU campaigns and
stores their confirmed daily Performance metrics with exact SKU attribution.
Both persist only through the private commercial-baseline collector.

A successful CPC collection run is the freshness source of truth, while
`cpc_advertising_daily` rows describe activity only. Therefore a successful
run with zero detail rows is represented as `SUCCESS_ZERO`: CPC is fresh and
its confirmed spend/orders are zero, without synthetic product rows or a
false stale-source warning. Missing and failed collection remain distinct.
The private `efa-daily-brief` runtime was redeployed with this fix and a
read-only 2026-08-15 validation confirmed 3 ordered units / 1,847 RUB,
`SUCCESS_ZERO` CPC, zero CPC spend/orders, and no false CPC refresh warning.

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

## Daily Commercial Brief v1.1 — read-only deterministic source of truth

`python -m services.daily_brief.main [--date YYYY-MM-DD]` now builds the v1.1
compact and extended payload from the same private read-only service. Current
day demand/operations and `current_day_economics` are physically separate from
`latest_confirmed_economics`; historical contribution is never carried into a
current-day result. For 2026-08-17 current economics are `UNAVAILABLE`, while
the latest confirmed economics are dated 2026-08-14.

Run-level freshness covers Seller Analytics, Postings, Returns, Finance, CPC,
Information Intelligence and Tax Engine. Durable CPC lifecycle states remain
distinct: `SUCCESS_ZERO`, `SUCCESS_NONZERO`, `PENDING`, `STUCK`, `FAILED` and
`MISSING`; the 2026-08-17 report is represented as `STUCK`, not zero. Pending
Information Intelligence `ACTION_REQUIRED` and `WATCH` events are included
from persisted data. Tax Engine is `ACTIVE / PARTIAL_DATA` and supplies taxable
revenue, gross USN, estimated payable, additional 1% and fixed insurance as a
business-level obligation; no tax formula is copied into the brief and the
fixed obligation is not allocated to offers.

Migration 012 creates the minimal `commercial_experiments` registry. Existing
experiment `FBS-UF004B-4118344-V0.1` is registered as active for `УФ 004Б`
with its approved limits and configuration; `started_at` is intentionally
`NULL`, so performance attribution is unavailable and no result is invented.
Trend calculation requires at least seven distinct valid business days per
offer series; shorter coverage is `INSUFFICIENT_DATA`.

The unified deterministic attention classes are `ANOMALY`, `DATA_QUALITY`,
`WATCH`, `ACTION_REQUIRED`, `INFORMATION_EVENT` and `EXPERIMENT_ALERT`.
Telegram remains compact and the five-page PDF contains executive summary,
freshness, offer economics, advertising/operations, experiments, Information
Intelligence, Tax and data-quality notes.

## Production Daily Commercial Brief Delivery v1 — active

Deterministic renderers now produce a five-page Cyrillic-safe A4 PDF, a short
HTML email body and a compact Telegram message from the same Daily Brief
v1.1 payload. Delivery never recalculates business metrics. The presentation
separates the operational `business_date` from `confirmed_through_date`; stale
finance is labelled explicitly, `NULL` is never displayed as zero, cohort
buyout and after-tax profit remain unavailable.

The active n8n workflow `Ozon Daily Commercial Brief Delivery v1`
(`Kf241Y5kzETghygL`) runs daily at 08:15 Europe/Moscow. It obtains the
deterministic brief, sends the existing HTML/PDF representation through Gmail,
and sends the compact Telegram representation through the existing Telegram
credential. It does not calculate metrics or call Ozon. Per-channel
idempotency is persisted by n8n workflow static data with key
`daily-brief:v0.1:production:<channel>:<business_date>`; a successful channel
is not resent, while a failed channel remains eligible on the next run.
Manual test deliveries remain separate, inactive and non-production.

Following the 2026-08-18 transient Docker DNS failure resolving
`efa-daily-brief`, its `Get Daily Brief` node uses standard n8n retry semantics:
three total attempts with a five-second wait. No schedule, payload, rendering,
credential or channel behavior changed.

Both production channel paths have completed one controlled manual E2E: Gmail
OAuth2 delivered the verified HTML plus PDF after desktop/mobile review, and
Telegram delivered the approved compact summary to the confirmed private
numeric chat. The first autonomous production delivery is scheduled for
16.08.2026 at 08:15 Europe/Moscow and has not been manually triggered. The
next checkpoint is to verify receipt, attachment, business date, freshness,
workflow status and absence of duplicate channel delivery; only then may this
status advance to **PRODUCTION / AUTONOMOUS**.

The private `efa-daily-brief` rendering bridge is deployed on the existing
`efa-tools` network with no host port. It exposes read-only JSON, Telegram,
HTML-email and streamed PDF representations of the existing deterministic
brief; it does not recalculate metrics or send messages. PostgreSQL sessions
enforce `default_transaction_read_only=on`, and the service has no Ozon,
Gmail, Telegram or Docker-socket access. A real 2026-08-14 request from
`efa-n8n` confirmed all five canonical offers, explicit finance freshness and
a five-page Cyrillic-safe PDF. Delivery is now scheduled, while generated
previews and all credential material remain outside Git.

### Internal PostgreSQL connectivity

The shared n8n PostgreSQL credential now targets `efa-postgres:5432` on the
private `efa-tools` Docker network instead of `host.docker.internal`. This
removes an unnecessary host-gateway dependency while preserving the existing
database, SSL and credential-secret settings.

### Local Runtime Secrets

Private Docker services receive database runtime settings from a user-local
`runtime.env`, outside the repository. The tracked template contains names
only. `Scripts/Initialize-EfaRuntimeSecrets.ps1` creates the file through
masked interactive password input and restricts its Windows ACL to the current
user. Where the existing private `efa-postgres` runtime already holds the
password, `Scripts/Bootstrap-EfaRuntimeSecretsFromPostgres.ps1` can transfer
it directly into that protected local file without printing it.
`Scripts/Deploy-DailyBrief.ps1` validates required names and
`efa-postgres:5432` before it rebuilds/recreates only `efa-daily-brief`; it
keeps an image rollback reference and never displays values.

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

## Commercial Profit Policy — mandatory guardrail

- A commercial sale must first recover COGS for inventory replenishment and
  cover attributable Ozon, advertising/promotion and applicable management-tax
  reserve costs before it is treated as distributable or reinvestable profit.
- The hard floor for any commercial recommendation or controlled experiment is
  `contribution_margin_after_tax_reserve >= 15%`; the target operating range is
  15–20%, with more than 20% preferred where market conditions allow.
- `contribution_after_tax_reserve` is recognised/effective revenue less COGS,
  attributable Ozon variable expenses, advertising/promotion spend and the
  applicable management tax reserve. Positive profit, orders or revenue alone
  do not satisfy this policy.
- The fixed annual insurance obligation (57,390 RUB) remains business-level and
  is not arbitrarily allocated to an offer or order; aggregate contribution
  must nevertheless cover it.
- CPC, promotion, price and boosting evaluation must retain these guardrails.
  Expected uplift is never assumed without historical evidence.

## Price Refresh Automation v0.1 — ACTIVE

- `Ozon Price Snapshot Automation v0.1` (`nw3DytLJdwTieOgJ`) runs every six hours at minute 20 Europe/Moscow.
- It uses one batched, read-only Seller API request for canonical product IDs and exact `product_id → offer_id` validation.
- `ozon_price_history` remains change-only; `price_collection_runs` is the authoritative freshness signal for successful checked state, including unchanged prices.
- In the confirmed account contract `marketing_price` is optional/nullable; its absence is recorded as `NULL`, never zero or `marketing_seller_price`.

## Tax Engine v0.1 — ACTIVE / PARTIAL_DATA

- The deterministic 2026 tax layer keeps statutory tax accounting separate
  from confirmed `profit_before_tax` and all commercial recommendations.
- Official June and July Ozon Realization workbooks reconcile exactly with
  their order-level reports and are persisted as immutable monthly tax-ledger
  events. January–May are confirmed zero-business periods; August is not yet
  available.
- Persisted accounting-income candidates are 16,407.14 RUB for June and
  139,667.69 RUB for July, or 156,074.83 RUB YTD through July. Exact tax dates
  remain `PERIOD_ONLY`, and partner-loyalty tax semantics remain `PARTIAL`.
- Migration 007 provides idempotent import runs and events. Replaying both
  official sources leaves 2 runs and 8 events; a changed workbook for an
  imported period requires explicit review.
- Current statutory preview: USN gross 9,364.49 RUB, additional contribution
  0, estimated USN payable 0 after eligible no-employee insurance reduction,
  fixed annual obligation 57,390 RUB kept separate, VAT status
  `EXEMPT_UNDER_THRESHOLD` at 0.78% threshold usage.
- Tax Engine is connected read-only to Daily Brief v1.1 through its existing
  deterministic calculator and persisted ledger. It remains disconnected from
  Price/Profit recommendations, promotions and advertising decisions.
