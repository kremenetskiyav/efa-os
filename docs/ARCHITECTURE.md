# Architecture

## Runtime

The production runtime is local:

- n8n running in Docker Desktop
- PostgreSQL running in Docker Desktop
- OZON Seller API as the external source
- OpenAI model used by the AI analyst

GitHub is the source-control and documentation layer, not the production runtime.

## Data flow

OZON API -> n8n ingestion nodes -> PostgreSQL raw/operational tables -> SQL views / analytical layer -> AI analyst / decision support.

## Current analytical layers

The database contains product metrics and regional logistics analysis. Regional logistics is built from posting logistics joined to postings and finance operations. The analysis uses destination cluster, order count, average logistics, baseline logistics, logistics delta, logistics delta percentage, logistics rate, baseline logistics rate, and rate delta in percentage points.

Confidence is based on regional order count:

- LOW: <= 2 orders
- MEDIUM: 3–4 orders
- HIGH: 5–9 orders
- VERY_HIGH: >= 10 orders

The summary layer classifies confirmed problems, weak signals, and low-confidence signals separately.

## Workflow boundaries

The canonical n8n workflow should remain the orchestration layer. Business calculations that need persistence or SQL aggregation belong in PostgreSQL views/queries rather than being duplicated across JavaScript nodes.

Credentials must remain in local n8n credential storage. They must not be committed to GitHub.

## Repository principle

One canonical production workflow JSON. SQL and documentation are versioned separately. Changes are made incrementally and recorded in Git history.
