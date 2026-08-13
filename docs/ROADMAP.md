# Roadmap

## Phase A — data foundation

Status: baseline established and core analytical toolset verified.

- [x] Products
- [x] Stocks
- [x] Finance operations
- [x] Postings
- [x] Prices
- [x] Returns
- [x] Posting logistics
- [x] Product metrics
- [x] Product alerts
- [x] Regional logistics analysis
- [x] AI analyst foundation
- [x] Joint verification of five analytical tools

## Current stabilization phase

The five core AI analytical tools are now working together:

1. `OZON Analytics`
2. `OZON Regional Analytics`
3. `OZON Price History`
4. `OZON Returns Analytics`
5. `OZON Stock History`

The immediate priority is not to add more tools. It is to eliminate inconsistency between the verified financial source of truth and the legacy `Tool — Анализ проблем товаров`.

### Immediate next steps

1. Fix `Tool — Анализ проблем товаров` only.
2. Make `profit`, `profit_per_unit`, `revenue`, `commission`, `logistics`, `payout`, and `cost` consistent with `OZON Analytics`.
3. Keep `orders_count` separate from `delivered_units`.
4. Remove or replace the legacy `avg_profit` calculation if it does not match the authoritative methodology.
5. Recalculate `commission_rate` from the same verified financial values.
6. Retest on `УФ 005Б` for 30 days.
7. Audit the AI answer for factual grounding, arithmetic, and unsupported recommendations.

## Next analytical layer

Only after the stabilization step above is complete:

- link price changes to sales and profit by time interval
- add a formal Days of Stock metric
- improve return analysis without inventing thresholds
- improve confidence-aware regional diagnostics

## Later phases

- reliable pagination and incremental ingestion for all volume-sensitive OZON endpoints
- automated anomaly detection
- price and promotion decision support
- inventory/replenishment recommendations
- regional logistics optimization
- automated daily management briefings
- scheduled daily execution
- controlled autonomous actions with explicit safety gates

## Architectural rule

Do not modify a verified analytical tool merely to accelerate the roadmap. New functionality must preserve the existing source-of-truth model and remain compatible with the current architecture.
