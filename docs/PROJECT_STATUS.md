# Project Status

## Baseline

Date: 2026-08-13

The project is currently based on a local n8n + PostgreSQL stack. The canonical supplied workflow is `OZON workflow - Phase A`.

Workflow ID: `q0yXnbt8BqFnukQj`
Latest exported version ID: `2b069584-6423-4fd6-a849-6f9b4769c94d`

The canonical workflow JSON is sanitized for repository storage: the OZON API key is represented by a placeholder rather than a secret.

## Implemented areas

- OZON product collection and product master data
- stock collection and stock snapshots/history
- finance operations collection
- postings/orders collection
- current price collection and price history
- returns collection
- posting logistics with `cluster_from` / `cluster_to`
- product-level profitability and alert views
- regional logistics analysis
- AI analyst connected to PostgreSQL through read-oriented tools
- Decision Engine for product alerts

## Regional logistics analysis

The regional analysis compares a product's logistics cost in a destination cluster against a leave-one-region-out baseline. The current model distinguishes confidence levels by regional order count and separates confirmed problems from weak signals.

Important current conclusion: high percentage logistics deltas in regions with only 1–2 orders are not sufficient evidence of a product-level logistics problem. The system therefore uses confidence-aware classification rather than treating every maximum delta as a critical alert.

## Canonical workflow audit — 2026-08-13

The supplied GitHub version was inspected as a complete n8n export: 51 nodes and 29 connection groups.

The workflow is structurally useful as a Phase A baseline, but it is **not yet production-safe as an autonomous daily analytical pipeline**. The following blockers were identified and must be resolved before treating the workflow as stable:

1. **Pagination is incomplete.** Product list, product info, stocks, finance operations, FBS postings, current prices, and returns use fixed limits/first pages. This can silently truncate data as the catalogue and transaction volume grow.
2. **Finance window is hard-coded.** `Get Financial Operations` starts at `2026-08-01` and requests only page 1. The ingestion must move to a persistent incremental window/cursor strategy.
3. **Postings are limited to 30 days and one page.** `Get Postings` uses `limit: 1000` and `offset: 0`, so older or high-volume orders can disappear from the analytical dataset.
4. **Returns are limited to 100 records with `last_id: 0`.** The current node does not implement a complete pagination loop.
5. **Current prices are limited to 1000 products.** This is a latent catalogue-size failure.
6. **The `OZON Analytics` AI tool is currently incorrect.** Its SQL query returns the first 10 rows from `posting_logistics` and does not use the `$fromAI('offer_id', ...)` replacement in the SQL. Its description promises product metrics such as profit, orders, stock and Phase A derivatives that the actual query does not return. This is a critical correctness defect.
7. **The `Decision Engine` branch is disconnected from the operational ingestion path.** `Get Product Alerts` -> `Decision Engine` -> `Get Product Alerts Report` exists as a separate diagnostic branch and does not feed the AI analyst. It should not be treated as the authoritative decision layer until its role is explicitly defined.
8. **Schema creation is incomplete inside the workflow.** Only `products`, `stock_history`, and `posting_logistics` have visible CREATE statements in the export. Other tables/views used by the workflow (`stocks`, `postings`, `finance_operations`, `returns`, `ozon_price_history`, `sales`, `vw_product_metrics`, `vw_product_alerts`, `vw_orders_profit`, `vw_orders_profit_final`, `vw_orders_finance_summary`, and regional analytical objects) are assumed to exist in PostgreSQL but are not versioned in this repository yet.
9. **The database analytical layer cannot currently be verified from this environment.** No WoWSQL project is connected to the account, so the actual live PostgreSQL schema/view definitions have not been inspected. Therefore no database migration or view rewrite should be performed yet.
10. **The workflow is manual/inactive.** The export has `active: false` and starts from a manual trigger. A reliable scheduled daily execution path has not yet been established.

## Current state of AI analyst

The analyst is intended to answer product-specific and general Ozon questions from PostgreSQL. Its prompt contains detailed rules for stock history, sales, returns/refusals, profitability, and regional logistics.

However, prompt quality cannot compensate for an incorrect tool implementation. The AI tool contract and the SQL behind each tool must be audited together against the actual PostgreSQL schema before further prompt tuning.

## Security status

The repository copy is sanitized and does not contain the OZON API key. Credentials must remain in local n8n credential storage and must never be committed to GitHub.

## Next step

1. Obtain/inspect the live PostgreSQL schema and view definitions.
2. Reconcile the actual database schema with every table/view referenced by the canonical workflow.
3. Fix the `OZON Analytics` tool so its SQL and tool contract return the promised product analytics and actually honor `offer_id`.
4. Implement reliable pagination/incremental ingestion for all volume-sensitive OZON endpoints.
5. Decide whether the Decision Engine remains a diagnostic branch or becomes the authoritative alert layer; avoid maintaining two competing alert implementations.
6. Establish a scheduled daily execution path only after ingestion completeness and analytical correctness are verified.
7. Version the verified database analytical layer in Git without duplicating existing SQL.
