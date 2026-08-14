# Project Status

## Baseline

Date: 2026-08-14

The project is based on a local Dockerized n8n + PostgreSQL stack. The canonical workflow is `OZON workflow - Phase A`.

Workflow ID: `q0yXnbt8BqFnukQj`
Canonical workflow JSON: `n8n/workflows/OZON_workflow_Phase_A.json`.

The repository copy is sanitized for source control. Secrets remain in local n8n credentials and are not committed.

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

## Next phase — Autonomous Monitoring Core

The next stage is **not** to add more ad-hoc SQL tools. The priority is to build the monitoring foundation that can detect changes automatically.

Target architecture:

`OZON -> PostgreSQL -> current state snapshot -> previous state snapshot -> change detection -> Decision Engine -> AI interpretation -> alert/report`

### Phase 1 — State and change monitoring

1. Verify the current PostgreSQL schema and existing historical tables before adding new structures.
2. Define the canonical state model for monitored entities/products.
3. Define snapshot cadence and retention.
4. Implement deterministic change detection for sales, prices, stock, returns and other existing metrics.
5. Store detected changes/events in PostgreSQL.
6. Keep facts separate from interpretations and recommendations.

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
