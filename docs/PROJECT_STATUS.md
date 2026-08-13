# Project Status

## Baseline

Date: 2026-08-13

The project is currently based on a local n8n + PostgreSQL stack. The latest supplied workflow export is `OZON workflow - Phase A`.

Workflow ID: `q0yXnbt8BqFnukQj`
Latest exported version ID: `2b069584-6423-4fd6-a849-6f9b4769c94d`

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

## Current state of AI analyst

The analyst is intended to answer product-specific and general Ozon questions from PostgreSQL. It has explicit interpretation rules for stock history, sales, returns/refusals, profitability, and regional logistics data.

## Security blocker before workflow commit

The latest exported workflow contains OZON API credentials directly inside HTTP request headers. The GitHub repository is currently public. Therefore the production workflow JSON must not be committed until the exposed OZON API key is revoked/rotated and the workflow is converted to use n8n credentials rather than embedded secrets.

## Next step

1. Rotate/revoke the exposed OZON API key.
2. Confirm the local n8n credential is updated and the workflow still executes.
3. Commit a sanitized canonical workflow JSON to `n8n/workflows/`.
4. Add database schema/views to `database/` without duplicating existing SQL.
5. Continue development from the Git history rather than from manually exchanged JSON files.
