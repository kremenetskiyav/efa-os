# efa-os
AI Operating System for EFA automotive cabin air filter brand.

## OZON automation — Phase A baseline

Current architectural baseline for the OZON automation project:

- n8n workflow: `n8n/workflows/OZON_workflow_Phase_A.json`
- PostgreSQL is the persistence layer.
- OZON API authentication is performed through the n8n `Header Auth account` credential (`httpHeaderAuth`); API keys must not be stored directly in workflow JSON.
- Phase A includes product, stock, finance, postings, price history, returns, stock history, posting logistics, product alerts/Decision Engine, OZON Analytics and OZON Problem Analysis, plus the OZON AI Analyst interface.
- Region/logistics analytics is part of the Phase A analytical layer and must be preserved when extending the workflow.

### Baseline rules

1. Treat the working n8n workflow as the source of truth for runtime behavior.
2. Do not create duplicate workflows when an existing node/branch can be extended.
3. Preserve existing credential architecture and PostgreSQL schema compatibility.
4. Do not expose or commit real OZON API keys.
5. Any architectural change must be documented here before moving to the next phase.

### Current project state

Phase A is the established working baseline. The next development work should extend the existing architecture rather than rebuild it.

### Analytical fixes completed

- Multi-unit posting cost calculation fixed.
- `vw_orders_finance_final` now derives posting-level cost as `cost_price × total quantity` from `postings`.
- `vw_orders_finance_summary` and downstream profit views use the corrected posting-level cost.
- Verified on four delivered multi-unit postings.
- Audit confirmed no delivered posting currently contains multiple SKUs.

### Regional analytics — OZON AI Analyst

- Added `OZON Regional Analytics` as a dedicated Postgres AI Tool connected to `OZON AI Analyst`.
- Regional destination is derived from `posting_logistics.cluster_to`; `region` and `city` are not reliable populated fields in the current dataset.
- The tool aggregates delivered sales by destination cluster/city and `offer_id` and returns units, postings count, revenue, commission, logistics, payout, profit, logistics per unit and profit per unit.
- Cost is calculated from `products.cost_price` multiplied by posting quantity, preserving the multi-unit correction.
- Financial rows without positive `accruals_for_sale` are excluded from regional sales analysis.
- Verified end-to-end through `OZON AI Analyst`: the agent correctly called `OZON Regional Analytics` and returned the top five regions for `УФ 005Б` by logistics per unit together with profit per unit.
- Current regional analytics implementation is considered `v1` and should be extended without duplicating the existing analytics tool architecture.

### Price history — OZON AI Analyst

- Added `OZON Price History` as a dedicated Postgres AI Tool connected to `OZON AI Analyst`.
- Uses the existing `ozon_price_history` table and does not introduce a new storage layer or duplicate the existing price-history workflow.
- Supports `offer_id` filtering and a configurable analysis period through the `days` parameter; `ALL` is supported for cross-product analysis.
- Returns observations, number of price changes, minimum, maximum and average price, first and current price, absolute and percentage price change, and the latest observation timestamp.
- The tool calculates the first/current price from the ordered history and aggregates the result before returning it to the AI Analyst.
- Verified directly for `УФ 005Б` over 30 days: 15 observations, 1 price change, minimum 667 ₽, maximum 901 ₽, average 791.80 ₽, current 667 ₽, first 901 ₽, total change −234 ₽ / −25.97%.
- Verified end-to-end through `OZON AI Analyst`: the agent correctly called `OZON Price History` and returned the same price-history metrics.
- Current price-history analytics implementation is considered `v1` and should be extended without duplicating the existing tool architecture.

### Returns analytics — OZON AI Analyst

- Added `OZON Returns Analytics` as a dedicated Postgres AI Tool connected to `OZON AI Analyst`.
- Uses the existing `returns` table; no new return-storage layer was introduced.
- Supports `offer_id` filtering and a configurable analysis period through the `days` parameter; `ALL` is supported for cross-product analysis.
- Returns return-row count, returned units, returned amount, number of distinct reasons/statuses, first/last return dates and detailed reason/status pairs.
- Parameters are normalized through a single `params` CTE so `$fromAI()` is called only once per parameter.
- Verified end-to-end for `УФ 005Б` over 30 days: 1 return row, 1 returned unit, returned amount 811 ₽, reason `Покупатель отказался при вручении: товар не подошел`, status `На складе Ozon`.
- Current returns analytics implementation is considered `v1` and should be extended without duplicating the existing tool architecture.
