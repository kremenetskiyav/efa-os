# EFA Ozon Price Calculator V1

## Status and scope

This document records the validated architecture and current production
checkpoint for EFA Ozon Price Calculator V1 as of 2026-08-24, Europe/Moscow.

- Business logic and Golden SKU validation: **COMPLETED**.
- Formula status: **VALIDATED** against EcomUnit.
- Phase 1 calculator core: **COMPLETE**.
- Phase 2 development: **COMPLETE**.
- Phase 2 production rollout: **COMPLETE**.
- Phase 3: **NOT STARTED**.

Production runs the Git checkpoint
`87b442e9a1ae16d256101b0bf48f0c142c5d447d`. The calculator remains a
read-only decision-support component; it does not automatically change Ozon
prices.

## Phase 2 production rollout

- Migration `016_ozon_fbs_tariff_snapshots_v1.sql` is applied.
- Commercial Baseline Collector Phase 2B and Recommendation Engine Phase 2C
  are deployed and healthy.
- A normal Ozon price collection created tariff observations for all five
  configured SKUs; the latest validated snapshot has
  `observed_at = 2026-08-24T03:20:00.383+00:00`.
- Recommendation Engine has no host port exposure. Calculator and taxpayer
  configuration mounts are read-only, and the PostgreSQL connection uses
  `default_transaction_read_only=on`.
- Production shadow acceptance passed for all five SKUs. Counts remained
  unchanged at 25 `price_collection_runs` and 10
  `ozon_fbs_tariff_snapshots`, confirming that shadow execution did not write
  to these tables.

The detailed deployment provenance, backup and rollback references, and the
five-SKU acceptance results are recorded in
[`PROJECT_STATUS.md`](../PROJECT_STATUS.md).

## Business margin policy

Price Calculator V1 uses this approved policy:

| Margin | Classification |
| --- | --- |
| `< 10%` | `HARD_FLOOR_VIOLATION` |
| `>= 10%` and `< 12%` | `BELOW_WORKING_MINIMUM` |
| `>= 12%` and `< 15%` | `BELOW_TARGET` |
| `>= 15%` | `TARGET_OR_ABOVE` |

The thresholds are:

- hard floor: 10%;
- working minimum: 12%;
- target: 15%.

The former 15% mandatory minimum is superseded for Price Calculator V1. It
must not override the 10% / 12% / 15% policy above.

## Price semantics

The forecast input is `seller_price`: the base price set by the seller.

These values are observed or actual marketplace economics and must not be used
as the forecast `seller_price` input:

- `marketing_seller_price`;
- `buyer_price`;
- `card_price`;
- confirmed revenue.

## Golden SKU

| Parameter | Golden value |
| --- | ---: |
| `offer_id` | УФ 001Б |
| `product_id` | 4861934525 |
| Ozon `sku` | 4601821825 |
| `seller_price` | 910 ₽ |
| `cost_price` | 166 ₽ |
| `scheme` | FBS |
| `handover` | ПВЗ/ППЗ |
| `handover_status` | `recommended_slot` |
| `buyout_rate` | 0.92 |
| `tax_rate` | 0.06 |
| validation `acquiring_rate` | 0.015 |
| `other_expenses` | 0 ₽ |

Golden SKU data is validated checkpoint data. It is not a claim about the
current live marketplace state after the checkpoint date.

## Confirmed Ozon economics for the Golden validation

| Parameter | Golden value |
| --- | ---: |
| base FBS commission | 44% |
| recommended-slot adjustment | -2 percentage points |
| effective commission | 42% |
| `processing_amount` | 10 ₽ |
| `forward_logistics_amount` | 84 ₽ |
| `delivery_to_customer_amount` | 25 ₽ |
| `return_logistics_amount` | 84 ₽ |
| `return_processing_amount` | 15 ₽ |

The failed-order cost is:

`failed_order_cost = 10 + 84 + 25 + 84 + 15 = 218 ₽`

The expected non-buyout formula is:

`expected_nonbuyout_cost = failed_order_cost × (1 - buyout_rate) / buyout_rate`

For the Golden SKU:

`expected_nonbuyout_cost = 218 × 0.08 / 0.92 = 18.956521739...`

The rounded monetary result is `18.96 ₽`.

## Validated calculator formula

`commission_amount = seller_price × commission_rate`

`acquiring_amount = seller_price × acquiring_rate`

`tax_amount = seller_price × tax_rate`

`failed_order_cost = processing_amount + forward_logistics_amount + delivery_to_customer_amount + return_logistics_amount + return_processing_amount`

`expected_nonbuyout_cost = failed_order_cost × (1 - buyout_rate) / buyout_rate`

`profit = seller_price - cost_price - commission_amount - acquiring_amount - processing_amount - forward_logistics_amount - delivery_to_customer_amount - expected_nonbuyout_cost - tax_amount - other_expenses`

`margin = profit / seller_price`

Formula status: **VALIDATED against EcomUnit**.

## Golden result

For `seller_price = 910 ₽`:

| Result | Value |
| --- | ---: |
| commission | 382.20 ₽ |
| acquiring | 13.65 ₽ |
| processing | 10.00 ₽ |
| forward logistics | 84.00 ₽ |
| delivery | 25.00 ₽ |
| expected non-buyout cost | 18.96 ₽ |
| tax | 54.60 ₽ |
| cost | 166.00 ₽ |
| profit | 155.59 ₽ |
| margin | 17.10% |

Reverse price calculation:

| Margin threshold | Minimum seller price |
| --- | ---: |
| 10% | 751 ₽ |
| 12% | 790 ₽ |
| 15% | 857 ₽ |

EcomUnit comparison result:

- all individual expense lines: exact match;
- profit: exact match;
- margin: exact match;
- P10 / P12 / P15: exact match.

Validation status: **VALIDATED**.

## Architecture decision

The single calculator core belongs inside
`services/recommendation_engine`.

Do not create a separate calculator service. The pure calculator core must not
depend on:

- PostgreSQL;
- Ozon API;
- n8n;
- HTTP;
- MCP;
- AI Analyst;
- Control Center.

The formula must exist in one place only. Do not duplicate it in SQL, n8n, AI
Analyst or Control Center.

Future consumers are:

- Price Decision;
- AI Analyst;
- Control Center;
- promotion economics.

## Phase plan

### Phase 1 — calculator core

- pure calculator core;
- Decimal arithmetic;
- input validation;
- `find_price_for_margin`;
- margin classification;
- Golden and unit tests.

Status: **COMPLETE**.

### Phase 2 — live input resolution

- validate live `/v5` contract semantics;
- capture the minimum tariff inputs;
- tariff snapshots;
- versioned EFA calculator configuration;
- Input Resolver.

Status: **COMPLETE IN PRODUCTION**.

### Phase 3 — decision integration

- Recommendation Engine and Price Decision integration;
- replace the AI Analyst simplified forecast with the calculator result;
- keep n8n as transport only.

Status: **NOT STARTED**.

### Phase 4 — portfolio acceptance

- EcomUnit acceptance baselines for УФ 002Б–005Б;
- shadow mode;
- Control Center display;
- promotion economics readiness.

Status: **PARTIAL**. Read-only production shadow acceptance is complete for
all five SKUs; the remaining integration scope has not started.

## Phase 2 design record

Phase 2 addressed these design concerns through live `/v5` contract
validation, immutable tariff observations, versioned configuration, the Input
Resolver and five-SKU production shadow acceptance:

- semantics of the live `/v5` tariff fields;
- treatment of `sales_percent_fbs`;
- route selection when the API returns minimum and maximum values;
- acceptance baselines for УФ 002Б–005Б;
- dynamic versus fallback acquiring policy.

## Static product dimensions

Dimensions for all five EFA SKUs were previously confirmed. They are not
required in Calculator Core Phase 1 because the validated model receives
monetary logistics inputs.

Phase 1 therefore did not add a `/v4/product/info/attributes` collector.

## Resume point

Phase 2 production rollout is complete. Phase 3 has not started. The next
development decision concerns Phase 3 integration; it must preserve the
read-only boundary until a separate production-write capability is explicitly
designed, reviewed and approved.
