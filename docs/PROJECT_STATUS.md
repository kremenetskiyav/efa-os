# Project Status

## Baseline

Date: 2026-08-14

The project is based on a local n8n + PostgreSQL stack. The canonical supplied workflow is `OZON workflow - Phase A`.

Workflow ID: `q0yXnbt8BqFnukQj`
Latest exported version recorded previously: `2b069584-6423-4fd6-a849-6f9b4769c94d`

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

## Verified AI analytical tools — 2026-08-14

The following five tools were successfully executed together through `OZON AI Analyst` using product `УФ 005Б` and a 30-day period:

1. `OZON Analytics` — verified
2. `OZON Regional Analytics` — verified
3. `OZON Price History` — verified
4. `OZON Returns Analytics` — verified
5. `OZON Stock History` — verified

Integration errors encountered during the audit were resolved, including duplicate `$fromAI('offer_id', ...)` definitions, SQL quoting/type issues around `offer_id`, and the `days` argument being passed with the wrong type to the returns tool.

## Verified financial baseline — УФ 005Б

For the latest 30-day test window the authoritative financial result is:

- `orders_count`: 14
- `delivered_units`: 15
- `revenue`: 11,444.00 ₽
- `commission`: -4,856.36 ₽
- `logistics`: -1,706.81 ₽
- `payout`: 4,880.83 ₽
- `cost`: 2,490.00 ₽
- `profit`: 2,390.83 ₽
- `profit_per_unit`: 159.39 ₽

The regional profitability results reconcile with the overall product profit. This confirms that the current regional tool is using compatible financial facts rather than an unrelated calculation.

## Verified price / returns / stock baseline — УФ 005Б

Price history for the same period:

- first price: 901.00 ₽
- current price: 667.00 ₽
- total change: -234.00 ₽ / -25.97%
- one recorded price change

Returns:

- 1 returned unit out of 15 delivered units
- returned amount: 811.00 ₽
- reason: `Покупатель отказался при вручении: товар не подошел`
- status: `На складе Ozon`

Stock snapshots:

- FBO: current 0
- FBS: current 381
- rFBS: current 0

A single return is a fact, not an automatic problem classification. Likewise, 381 FBS units must not be called excessive without a formal stock-coverage metric.

## Regional logistics analysis

The regional analysis compares product financial results by destination. Current verified examples for `УФ 005Б` include:

- weakest profit per unit: Ufa — 1.47 ₽
- strongest profit per unit among the tested regions: Samara — 198.01 ₽
- highest absolute regional profit among the tested regions: Samara — 396.02 ₽

High logistics cost in a low-volume region is not by itself proof of a product-level logistics problem. The system must continue to distinguish facts, weak signals, and confirmed problems.

## Current critical inconsistency

The legacy `Tool — Анализ проблем товаров` is **not yet synchronized with the verified financial source of truth**.

Observed inconsistencies for `УФ 005Б`:

- it reports `orders_count: 15`, while the verified `OZON Analytics` value is `14`; 15 is the delivered-unit count
- it reports `avg_profit: 175.46`, while the authoritative `profit_per_unit` is `159.39`
- it reports `commission_rate: 42.14`, while the rate calculated from the verified revenue and commission is approximately 42.43%

Therefore this tool must not be treated as an authoritative source for financial metrics until corrected.

### Source-of-truth rule

For financial product metrics, use `OZON Analytics` values:

- `profit` — total profit
- `profit_per_unit` — profit per delivered unit
- `revenue` — revenue
- `commission` — commission
- `logistics` — logistics
- `payout` — Ozon payout
- `cost` — actual cost of sold delivered units

`orders_count` and `delivered_units` must remain separate concepts.

## Previously identified Phase A blockers

The earlier workflow audit remains relevant:

1. Pagination is incomplete for several volume-sensitive OZON endpoints.
2. Finance ingestion uses a hard-coded time window and first-page limitation.
3. Postings are limited to 30 days and one page.
4. Returns pagination is incomplete.
5. Current prices are limited to 1000 products.
6. The legacy problem-analysis tool is inconsistent with the verified financial tool and must be corrected.
7. The Decision Engine branch remains a separate diagnostic branch and is not yet the authoritative autonomous decision layer.
8. Database analytical objects are not fully versioned in the repository.
9. The live PostgreSQL analytical schema still needs explicit verification before migrations or view rewrites.
10. The workflow is still manual/inactive; reliable scheduled daily execution is a later step.

## Next work session

1. Fix only `Tool — Анализ проблем товаров`.
2. Make its financial fields consume the same source-of-truth methodology as `OZON Analytics`.
3. Remove dependence on the inconsistent legacy `avg_profit` calculation.
4. Correct the distinction between `orders_count` and `delivered_units`.
5. Recalculate `commission_rate` only from the same verified `revenue` and `commission` values.
6. Retest `УФ 005Б` for 30 days.
7. Audit the resulting AI response for arithmetic correctness, factual grounding, and unsupported recommendations.
8. Only after that, proceed to time-linked price -> sales -> profit analysis and a formal Days of Stock metric.

Do not modify the five verified analytical tools unless a new test demonstrates a concrete defect.

## Security status

The repository copy is sanitized and does not contain the OZON API key. Credentials must remain in local n8n credential storage and must never be committed to GitHub.
