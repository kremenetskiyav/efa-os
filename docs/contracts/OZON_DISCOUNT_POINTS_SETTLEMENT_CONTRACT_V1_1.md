# EFA OS — Ozon Discount & Points Settlement Contract v1.1

| Field | Value |
| --- | --- |
| Version | `1.1-draft` |
| Date | `2026-09-02` |
| Status | `DRAFT — OFFICIAL SEMANTICS RECONCILED — EMPIRICAL VALIDATION PENDING` |
| Approval status | `V1_1_APPROVED_FOR_CANONICAL_DRAFT` |
| Canonical role | `CURRENT CANONICAL DRAFT FOR SETTLEMENT SEMANTICS` |
| Approval review baseline SHA-256 | `65f74603ddc88611ba0cffa995bb634bc4f5ad42208c4b0e986513c3883ae22e` |
| Official reference | [`docs/reference/OZON_UNIT_ECONOMICS_OFFICIAL_REFERENCE_V1.md`](../reference/OZON_UNIT_ECONOMICS_OFFICIAL_REFERENCE_V1.md) |
| Historical predecessor | [`OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md`](OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md) |
| Supersedes | V1 as the canonical settlement-semantics draft; V1 remains a historical/deprecation source |
| Implementation status | `NOT APPROVED FOR PRODUCTION` |
| Validation status | `EMPIRICAL VALIDATION CASES PENDING` |

## 1. Versioning, purpose and authority

This draft reconciles the historical v1 contract with the dated official-reference
snapshot and the completed review `Settlement Contract v1 — Official Semantics
Reconciliation`.

It defines financial semantics, evidence boundaries and validation gates. It is
not an authorization to change Calculator, Price Decision, AI Analyst, PostgreSQL,
n8n, production, Ozon, runtime configuration, prices, promotions or advertising.

V1.1 is the current canonical draft for settlement semantics. The historical v1
contract remains available only as its predecessor and deprecation baseline.

`V1.1 != production implementation authorization`

Canonical-draft approval does not authorize production implementation or an
automated Ozon write. The empirical-validation and implementation gates in
sections 17 and 18 remain in force until their own completion and explicit
approval requirements are satisfied.

## 2. Source precedence and provenance

For definitions and official semantics:

```text
CURRENT OZON OFFICIAL DOCUMENTATION
>
EFA OFFICIAL REFERENCE SNAPSHOT
>
INTERNAL ASSUMPTIONS
```

For the factual financial result of a particular order or period:

```text
FINAL OZON SETTLEMENT
>
ORDER FINANCE DETAIL
>
SELLER UNIT ECONOMICS
>
OFFICIAL DOCUMENTATION
>
EFA FORECAST
```

Buyer UI and price/promotion configuration are supplemental evidence only. They
can establish what was displayed or configured, but cannot independently establish
what the seller earned or how a difference was funded.

The precedence chains are EFA OS policy with source status `INTERPRETATION`; they
are not claims that Ozon publishes those chains.

### 2.1 Sources

- Repository snapshot: [`OZON_UNIT_ECONOMICS_OFFICIAL_REFERENCE_V1.md`](../reference/OZON_UNIT_ECONOMICS_OFFICIAL_REFERENCE_V1.md), reviewed `2026-09-02`.
- Historical predecessor/deprecation source: [`OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md`](OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md).
- Reconciliation review: `Settlement Contract v1 — Official Semantics Reconciliation`, result `PASS`, reviewed `2026-09-02`.
- Ozon Seller Education: [Unit Economics](https://seller-edu.ozon.ru/libra/finances-documents/additional-information/unit-ekonomika).
- Ozon Seller Education: [Discount points](https://seller-edu.ozon.ru/libra/finances-documents/additional-information/bally-za-skidki).
- Ozon Seller Education: [Commission](https://seller-edu.ozon.ru/libra/commissions-tariffs/commissions-tariffs-ozon/komissii-tovary-uslugi).
- Ozon Seller Education: [Green Price](https://seller-edu.ozon.ru/libra/how-to-sell-effectively/loyalty/zelenaya-cena).

Official pages are volatile and do not expose a stable page version. Before any
financial-logic change:

`REVALIDATE_OFFICIAL_SOURCE_BEFORE_FINANCIAL_LOGIC_CHANGE`

## 3. Canonical price and compensation layers

| Canonical field | Semantic role | Strongest expected evidence | Boundary |
| --- | --- | --- | --- |
| `CATALOG_SELLER_PRICE` | Seller-controlled catalog or pre-promotion price | Order-time price configuration | Internal provenance layer; not the official settled seller price |
| `SELLER_FUNDED_PROMO_DISCOUNT` | Confirmed reduction funded through seller-defined discounts or promotions | Order-time promotion configuration and finance evidence | Reduces the seller action layer |
| `SELLER_ACTION_PRICE` | Price after seller-defined discounts and promotions, before an additional discount compensated by points | Order-time promotion state plus order finance verification | Official semantic commission base; operational field mapping is not yet confirmed |
| `BUYER_STANDARD_DISPLAY_PRICE` | Buyer-facing price without Green payment conditions | Timestamped buyer UI observation | Market display only; not seller revenue |
| `BUYER_GREEN_PRICE` | Buyer-facing Green price for an eligible payment method | Timestamped buyer UI or order evidence | Market display/payment candidate; funding split requires order evidence |
| `BUYER_CASH_REVENUE` | Amount actually paid by the buyer for the sale | Order finance detail or final settlement | Official acquiring base and one component of official seller price |
| `LOYALTY_PROGRAM_COMPENSATION` | Ruble compensation under partner loyalty mechanisms | Order finance detail or final settlement | Separate from points compensation |
| `GREEN_PRICE_BANK_COMPENSATION` | Green-related ruble bank/partner component | Loyalty report or order finance detail | A subtype or allocation of loyalty-program compensation, not an extra fourth seller-price component |
| `POINTS_COMPENSATION` | Compensation represented by discount points | Points detail and final settlement documents | One component of official seller price; subject to lifecycle and reversal |
| `OFFICIAL_SELLER_PRICE` | Official seller price in the accruals decomposition | Final or sufficiently complete order decomposition | Sum of buyer cash, loyalty compensation and points compensation |
| `ADDITIONAL_DISCOUNT_COMPENSATED_BY_POINTS` | Explanatory contra-price amount for the additional discount | Official discount/points detail | Audit/decomposition field; never an additional positive revenue component |
| `COMMISSION_PRICE_BASE` | Semantic price base for Ozon commission | Official rule plus validated order mapping | Semantically equals the seller action layer; field mapping remains unconfirmed |
| `ACQUIRING_BASE` | Amount on which acquiring is calculated | Actual buyer payment | Equals buyer cash revenue |

One physical or logical field must not be reused for multiple semantic roles. In
particular, catalog price, seller action price, buyer display price, buyer cash,
official seller price, commission base and acquiring base require distinct names,
provenance and lifecycle status even when two observed values happen to be equal.

### 3.1 Field-level source status and lifecycle applicability

`OBSERVED_BUYER_UI` is an evidence classification, not a source status and not a
financial lifecycle status. The source-status column below uses only section 9
values.

| Field | Source status | Lifecycle applicability | Primary source | Notes |
| --- | --- | --- | --- | --- |
| `CATALOG_SELLER_PRICE` | `INTERPRETATION` | `LIVE_ESTIMATE` when modeled; `PROVISIONAL` when attached to order-time configuration | Order-time price configuration | Configuration alone cannot make the value final settlement |
| `SELLER_FUNDED_PROMO_DISCOUNT` | `INTERPRETATION` | `LIVE_ESTIMATE` when modeled; `PROVISIONAL` when observed before close | Promotion configuration plus finance evidence | Seller funding must be evidenced, not inferred from a UI difference |
| `SELLER_ACTION_PRICE` | `INTERPRETATION` | `LIVE_ESTIMATE` when modeled; `PROVISIONAL` until order mapping and close | Order-time promotion state plus order finance detail | EFA normalization aligned with the official commission-base semantics |
| `BUYER_STANDARD_DISPLAY_PRICE` | `INTERPRETATION` | Not applicable to financial lifecycle | Timestamped buyer UI | Evidence classification: `OBSERVED_BUYER_UI`; display only |
| `BUYER_GREEN_PRICE` | `OFFICIAL_EXPLICIT` | Not applicable to financial lifecycle when observed only in UI; `PROVISIONAL` when linked to an order payment | Timestamped buyer UI or order finance detail | UI-only evidence classification: `OBSERVED_BUYER_UI` |
| `BUYER_CASH_REVENUE` | `OFFICIAL_EXPLICIT` | `PROVISIONAL`, `FINAL_SETTLEMENT`, `CORRECTED_FINAL_SETTLEMENT` | Order finance detail or final settlement | Actual buyer payment and acquiring base |
| `LOYALTY_PROGRAM_COMPENSATION` | `OFFICIAL_EXPLICIT` | `PROVISIONAL`, `FINAL_SETTLEMENT`, `CORRECTED_FINAL_SETTLEMENT` | Order finance detail or final settlement | Parent component; do not add a Green subtype twice |
| `GREEN_PRICE_BANK_COMPENSATION` | `OFFICIAL_EXPLICIT` | `PROVISIONAL`, `FINAL_SETTLEMENT`, `CORRECTED_FINAL_SETTLEMENT` | Partner-loyalty report or order finance detail | Allocation inside loyalty-program compensation |
| `POINTS_COMPENSATION` | `OFFICIAL_EXPLICIT` | `PROVISIONAL`, `FINAL_SETTLEMENT`, `CORRECTED_FINAL_SETTLEMENT` | Points detail and final settlement | Subject to accrual, reversal and close |
| `OFFICIAL_SELLER_PRICE` | `OFFICIAL_EXPLICIT` | `PROVISIONAL` only for an incomplete reconciliation; otherwise `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` | Complete order decomposition or final settlement | Must satisfy the identity in section 4.2 |
| `ADDITIONAL_DISCOUNT_COMPENSATED_BY_POINTS` | `OFFICIAL_EXPLICIT` | `PROVISIONAL`, `FINAL_SETTLEMENT`, `CORRECTED_FINAL_SETTLEMENT` | Discount/points detail | Explanatory contra-price amount, never extra revenue |
| `COMMISSION_PRICE_BASE` | `OFFICIAL_EXPLICIT` | `LIVE_ESTIMATE` when modeled; `PROVISIONAL`, `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` when evidenced | Official rule plus validated order mapping | Operational source-field mapping remains empirical |
| `ACQUIRING_BASE` | `OFFICIAL_EXPLICIT` | `LIVE_ESTIMATE` when modeled; `PROVISIONAL`, `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` when evidenced | Actual buyer payment and settlement | Equals buyer cash revenue |

## 4. Core formulas and rule status

### 4.1 Seller action layer

```text
SELLER_ACTION_PRICE
= CATALOG_SELLER_PRICE
- SELLER_FUNDED_PROMO_DISCOUNT
```

This is the canonical EFA normalization of the seller-controlled price chain.
Source status: `INTERPRETATION`, aligned with official price-layer semantics.

### 4.2 Official seller-price identity

```text
OFFICIAL_SELLER_PRICE
= BUYER_CASH_REVENUE
+ LOYALTY_PROGRAM_COMPENSATION
+ POINTS_COMPENSATION
```

Source status: `OFFICIAL_EXPLICIT`.

The additional discount amount explains the difference that may produce points;
it is not added again to this identity. Green-related ruble compensation is
included through `LOYALTY_PROGRAM_COMPENSATION`, and any Green-related points are
included through `POINTS_COMPENSATION`.

### 4.3 Acquiring base

```text
ACQUIRING_BASE = BUYER_CASH_REVENUE
```

Source status: `OFFICIAL_EXPLICIT`.

### 4.4 Commission base

```text
COMMISSION_PRICE_BASE = SELLER_ACTION_PRICE
```

| Layer | Status |
| --- | --- |
| Semantic rule: seller-defined price after seller discounts/promotions and before the additional points-compensated discount | `OFFICIAL_EXPLICIT` |
| Mapping to a concrete API, report or database field | `EMPIRICALLY_UNCONFIRMED` |
| Order-time rate, amount, VAT semantics, rounding, reversal and correction | Must be verified from the applicable order and settlement |

The formula does not authorize assigning an existing field to
`COMMISSION_PRICE_BASE` without order-level evidence.

## 5. Migration and deprecation

The terms below may appear in historical artifacts and migration logic only. They
must not be used as canonical v1.1 fields.

| Deprecated v1 term | v1.1 replacement | Migration action | Reason |
| --- | --- | --- | --- |
| `OZON_FUNDED_DISCOUNT` | `ADDITIONAL_DISCOUNT_COMPENSATED_BY_POINTS` | Rename only after provenance review; do not imply platform funding | The official legal/economic description does not support the old funding label |
| `BASE_SELLER_PRICE` | `CATALOG_SELLER_PRICE` | Map only when the source is a catalog or pre-promotion configuration | Prevent confusion with the official settled seller-price term |
| `SELLER_ECONOMIC_PRICE` | Split into `SELLER_ACTION_PRICE` and `OFFICIAL_SELLER_PRICE` | No one-to-one migration; classify each use by semantic role | The old field mixed action price, revenue and commission semantics |
| `BUYER_OTHER_PRICE` | `BUYER_STANDARD_DISPLAY_PRICE` or `BUYER_CASH_REVENUE` | Select by evidence source; UI and actual payment cannot share a field | Displayed price and paid amount are different roles |
| generic `economic_revenue` | `OFFICIAL_SELLER_PRICE` for final evidence, or an explicitly named forecast value | Require lifecycle and provenance before migration | A generic value hides whether compensation is included and whether the amount is final |
| generic `points_net` | Full points lifecycle in section 7 | Decompose; never copy one aggregate into every lifecycle stage | Accrual, availability, application, reversal and settlement are distinct events |
| old `settlement_status` | `financial_lifecycle_status` using section 8 vocabulary | Translate only when documentary finality is known | The old binary model did not distinguish provisional and corrected final states |

No database or code migration is authorized by this table.

## 6. Green Price, loyalty and compensation

The official Green mechanism may contain:

- ruble bank/partner compensation;
- points compensation;
- a combination of both.

The mechanism itself is not wholly unknown. The unresolved element before
order-level finance evidence is the allocation of a particular order:

`GREEN_PRICE_COMPENSATION_SPLIT_UNCONFIRMED`

Rules:

1. A buyer-visible difference must not be classified as bank compensation,
   points compensation or seller funding from UI evidence alone.
2. A Green ruble amount is represented by `GREEN_PRICE_BANK_COMPENSATION` and
   reconciled inside `LOYALTY_PROGRAM_COMPENSATION`.
3. Green-related points are an attributed part of `POINTS_COMPENSATION`, not an
   additional seller-price component.
4. The official seller-price identity in section 4 remains the only canonical
   positive-component identity.
5. No compensation is recognized twice through both a subtype and its parent.

## 7. Points lifecycle and eligibility

### 7.1 Canonical fields

| Field | Meaning | Minimum evidence |
| --- | --- | --- |
| `points_accrued` | Points recorded for qualifying sales in the observed period | Points detail with period/order linkage where available |
| `points_available` | Points available for application after applicable reversals and timing rules | Period points statement |
| `points_applied` | Points actually applied as a discount to eligible Ozon services | Closed-period service/points detail |
| `points_reversed` | Previously accrued points reversed, including return effects | Reversal or return-linked points detail |
| `points_excess_premium` | Excess compensation paid in rubles after eligible services are covered | Closing documents and premium line |
| `points_settled` | Points amount accepted in the closed-period settlement result | Final settlement package |
| `points_adjustment` | Other documented correction not represented by accrual/application/reversal | Correction document with provenance |
| `points_balance_after_settlement` | Residual balance after the documented settlement sequence | Closed-period reconciliation |

A single aggregate points field is not a sufficient lifecycle model.

### 7.2 Field-level source status and lifecycle applicability

| Field | Source status | Lifecycle applicability | Primary source | Notes |
| --- | --- | --- | --- | --- |
| `points_accrued` | `OFFICIAL_EXPLICIT` | `PROVISIONAL`; later `CORRECTED_FINAL_SETTLEMENT` if reversed or corrected | Real-time points detail with order/period linkage | Accrual is not final settlement |
| `points_available` | `INTERPRETATION` | `PROVISIONAL`, then closed-period evidence only | Period points statement | EFA lifecycle field; must preserve timing and reversal provenance |
| `points_applied` | `OFFICIAL_EXPLICIT` | `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` | Closed-period service/points detail | Application changes cash settlement, not service economic cost |
| `points_reversed` | `OFFICIAL_EXPLICIT` | `PROVISIONAL`, `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` according to evidence | Return-linked points detail or correction document | Preserve original accrual and reversal separately |
| `points_excess_premium` | `OFFICIAL_EXPLICIT` | `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` | Closing documents and premium line | Cash realization, not new economic revenue |
| `points_settled` | `INTERPRETATION` | `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` | Final settlement package | EFA normalization of the accepted closed-period result |
| `points_adjustment` | `INTERPRETATION` | `PROVISIONAL`, `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` according to document finality | Correction document | Must not duplicate accrual, application or reversal |
| `points_balance_after_settlement` | `INTERPRETATION` | `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` | Closed-period reconciliation | EFA reconciliation field; calculate only when every required lifecycle component is evidenced |

### 7.3 Official value and timing boundaries

The following relations are limited to their officially documented context:

```text
1 ₽ additional qualifying discount -> 1 point accrued
1 point applied -> 1 ₽ discount on an applicable service
```

Source status: `OFFICIAL_EXPLICIT`.

Accrued points are visible in real time but are not final settlement. Applied and
final amounts are determined after the period closes, and later returns can create
reversals or corrections. An excess premium is cash realization of already
recognized compensation, not new revenue a second time.

### 7.4 Eligibility

Eligibility is evidence-driven for each service line. The documented sequence
starts with commission and then applies proportionally to delivery, returns and
applicable parts of other own Ozon services. Partner-executor services are not
automatically eligible; official examples include acquiring, delivery to the
pickup point and return processing.

Allowed classification per service line:

- `POINTS_ELIGIBLE_CONFIRMED`
- `POINTS_NOT_ELIGIBLE_CONFIRMED`
- `POINTS_ELIGIBILITY_UNCONFIRMED`

Eligibility and source status are separate dimensions. For example, an unresolved
line is stored as:

```text
Eligibility: POINTS_ELIGIBILITY_UNCONFIRMED
Source status: OZON_UNCLEAR
```

An unconfirmed line must never be promoted to eligible by assumption.

## 8. Financial lifecycle

| Lifecycle status | Meaning | Prohibited promotion |
| --- | --- | --- |
| `LIVE_ESTIMATE` | Internal Calculator forecast, internal modeled scenario or another explicitly named EFA forecast | Must not be used for Seller Unit Economics or buyer UI evidence and must not be called settled |
| `PROVISIONAL` | Seller Unit Economics or observed order/finance/points data still subject to period close, reversal or correction | Must not be assigned merely because a price is visible in buyer UI and must not be called final |
| `FINAL_SETTLEMENT` | Final Ozon documents for a defined order/period and document version | Must retain document and period provenance |
| `CORRECTED_FINAL_SETTLEMENT` | Later documented correction to a previously final result | Must retain both original and correcting provenance |

Mandatory invariant:

`SELLER_UNIT_ECONOMICS != FINAL_SETTLEMENT`

Source status and financial lifecycle status are separate dimensions. A rule may
be `OFFICIAL_EXPLICIT` while an observed amount remains `PROVISIONAL`.

Buyer UI is outside the financial lifecycle. A buyer-display observation receives
the separate evidence classification `OBSERVED_BUYER_UI`; observation in the UI
does not assign `LIVE_ESTIMATE` or `PROVISIONAL`.

## 9. Source-status vocabulary

| Source status | Meaning |
| --- | --- |
| `OFFICIAL_EXPLICIT` | Directly stated in current official Ozon documentation captured by the reference |
| `OFFICIAL_EXAMPLE` | Demonstrated by an official example but not necessarily published as a universal formula |
| `DERIVED_FROM_OFFICIAL_FORMULA` | Necessary derivation from an official formula without adding a new factual premise |
| `INTERPRETATION` | EFA policy, normalization or internal modeling choice |
| `OZON_UNCLEAR` | Official material does not resolve the semantic or operational question |

Source status must not be stored in or inferred from the financial lifecycle
status. `EMPIRICALLY_UNCONFIRMED` may additionally describe a proposed operational
mapping; it does not replace either vocabulary.

## 10. Advertising boundary

- CPC accrues at click. Source status: `OFFICIAL_EXPLICIT`.
- CPO accrues when the buyer pays. Source status: `OFFICIAL_EXPLICIT`.
- Advertising DRR is not the Unit Economics margin.
- Paid orders later cancelled or returned may remain in CPC/CPO advertising
  statistics.
- Exact SKU/order allocation for CPC and brand advertising is `OZON_UNCLEAR`.
- Lag before an advertising expense appears in Seller Unit Economics is
  `OZON_UNCLEAR`.
- No Calculator, Price Decision, AI Analyst or reporting component may invent an
  allocation rule or treat advertising attribution as settlement evidence.

Elastic or another seller-funded price reduction belongs to the seller action
price chain; it is not automatically a CPC/CPO expense.

## 11. Returns, reversals and corrections

Return and correction processing must preserve separate components:

| Component | Required treatment |
| --- | --- |
| Sale reversal | Record the sale-side reversal with order, event and period provenance |
| Commission correction | Record the actual returned or adjusted commission independently |
| Points reversal | Record the documented points reversal and affected period |
| Loyalty/bank compensation correction | Record only the amount supported by partner/finance evidence |
| Logistics correction | Record actual forward, reverse or other logistics corrections separately |
| Processing/return expense | Preserve the exact service line and executor classification |
| Acquiring correction | Record only the actual correction; acquiring may remain charged in some scenarios |

No return event implies an automatic full reversal of every original field. The
relationship between excluding returned units from Seller Unit Economics and the
separate return-expense line remains `OZON_UNCLEAR`.

## 12. Tax boundary

`TAX = OUTSIDE OZON UNIT ECONOMICS OFFICIAL CONTRACT`

Tax may remain a versioned EFA internal input only with source status
`INTERPRETATION`, separate provenance and a clearly named internal model field.
Absence of an official Unit Economics tax row does not mean zero tax. Tax must not
be presented as an official Ozon Unit Economics component.

## 13. EFA contribution margin

The internal metric is named:

`EFA_CONTRIBUTION_MARGIN`

It must not be described as an official Ozon margin. Every stored or reported
value must carry a formula version and denominator version.

The versioned numerator is an internal EFA metric:

```text
EFA_CONTRIBUTION_PROFIT_V1_1
= SELLER_REALIZATION_INPUT_V1_1
- COMMISSION_AMOUNT
- OZON_LOGISTICS_COST
- FULFILMENT_PROCESSING_COST
- LAST_MILE_COST
- ACQUIRING_COST
- OTHER_VARIABLE_OZON_CHARGES
- ADVERTISING_COST
- COGS
- EFA_TAX_INPUT
- OTHER_EXPLICITLY_CONFIGURED_VARIABLE_COSTS
```

`SELLER_REALIZATION_INPUT_V1_1` is `OFFICIAL_SELLER_PRICE` for
`FINAL_SETTLEMENT` and `CORRECTED_FINAL_SETTLEMENT`. In `LIVE_ESTIMATE` it may be
an explicitly named estimated seller realization only when its decomposition,
assumptions and forecast provenance are retained; a buyer display price must not
be substituted.

Included deductions are only the order/SKU-attributable variable components
listed in the formula: commission; Ozon logistics; fulfilment processing; last
mile; acquiring; other explicitly identified variable Ozon charges; advertising;
COGS; the EFA tax input; and other explicitly configured variable costs. Returns,
reversals and corrections affect only their evidenced component and lifecycle.

Excluded components are buyer display prices, catalog price, seller action price
unless explicitly used as a forecast realization assumption, points application
as a second expense reduction, excess-points cash premium as second revenue,
fixed overhead, capital expenditure, inventory financing and any unconfigured or
unattributed cost. Points change the payment form of an eligible service but do
not remove its included economic cost.

The entire numerator definition, including `EFA_TAX_INPUT`, has source status
`INTERPRETATION` and must not be called official Ozon profit. If any required
component for the selected formula version is `UNKNOWN`, the numerator and margin
result status is `INCOMPLETE`; no missing component is silently set to zero.

For final and corrected-final settlement in this draft:

```text
EFA_CONTRIBUTION_MARGIN_V1_1
= EFA_CONTRIBUTION_PROFIT_V1_1
/ EFA_CONTRIBUTION_MARGIN_DENOMINATOR_V1_1

EFA_CONTRIBUTION_MARGIN_DENOMINATOR_V1_1
= OFFICIAL_SELLER_PRICE
```

Source status: `INTERPRETATION`. A zero or unavailable denominator returns
`INSUFFICIENT_SETTLEMENT_DATA`; it is never silently replaced by a buyer display
price.

For the Ozon UI metric, the general denominator when points or partner
compensation are present remains unresolved:

`OZON_UI_MARGIN_DENOMINATOR = OZON_UNCLEAR`

An estimated EFA margin must be explicitly named as an estimate and cannot be
promoted to the final formula without final seller-price evidence.

## 14. Final invariants

### `INV-1`
`SELLER_ACTION_PRICE = CATALOG_SELLER_PRICE - SELLER_FUNDED_PROMO_DISCOUNT`.

### `INV-2`
`OFFICIAL_SELLER_PRICE = BUYER_CASH_REVENUE + LOYALTY_PROGRAM_COMPENSATION + POINTS_COMPENSATION`.

### `INV-3`
Buyer display prices do not establish seller revenue or compensation funding.

### `INV-4`
`SELLER_ACTION_PRICE != OFFICIAL_SELLER_PRICE` unless equality is supported by
order evidence or is explicitly marked as a forecast assumption.

### `INV-5`
An additional discount amount is explanatory contra-price data; only its actual
compensation component participates in the official seller-price identity.

### `INV-6`
`ACQUIRING_BASE = BUYER_CASH_REVENUE`.

### `INV-7`
`COMMISSION_PRICE_BASE = SELLER_ACTION_PRICE` is the semantic rule, while the
operational source-field mapping remains `EMPIRICALLY_UNCONFIRMED` until validated.

### `INV-8`
Applying points to a service does not eliminate that service's economic expense;
economic P&L and cash settlement remain separate models.

### `INV-9`
Green compensation may be rubles, points or both; the particular order-level
split remains `GREEN_PRICE_COMPENSATION_SPLIT_UNCONFIRMED` until evidence resolves it.

### `INV-10`
No discount, compensation, points application, reversal or excess premium may be
counted twice through an amount and its subtype, settlement form or later cash
realization.

### `INV-11`
`SELLER_UNIT_ECONOMICS != FINAL_SETTLEMENT`.

## 15. Hard rules for EFA OS

1. `BUYER_DISPLAY_PRICE != SELLER_REVENUE` without a complete decomposition.
2. Always preserve the official seller-price identity from section 4.
3. Do not equate `SELLER_ACTION_PRICE` and `OFFICIAL_SELLER_PRICE` without evidence
   or an explicit forecast assumption.
4. A confirmed seller-funded promotion reduces `SELLER_ACTION_PRICE`.
5. Do not add the explanatory additional-discount amount as positive revenue.
6. Do not add points or loyalty compensation on top of a value that already
   represents the complete `OFFICIAL_SELLER_PRICE`.
7. Use `ACQUIRING_BASE = BUYER_CASH_REVENUE`; never substitute a display or catalog
   price.
8. Preserve the official semantic commission base, but do not select an API/DB
   field until order-level empirical mapping confirms it.
9. Points used to discount a service change cash settlement, not the economic
   amount of that service.
10. Keep economic P&L and cash settlement as separate, reconcilable models.
11. Preserve the full points lifecycle; never treat one aggregate balance as a
    substitute for accrual, application, reversal and settlement events.
12. Treat Green ruble compensation and Green-related points as allocations inside
    their parent official seller-price components; do not count both levels.
13. Keep source status separate from lifecycle/finality status.
14. Preserve `OZON_UNCLEAR`; do not convert an official ambiguity into a formula,
    allocation rule or factual claim.
15. When settlement-critical evidence is missing, return
    `INSUFFICIENT_SETTLEMENT_DATA` and stop the financial conclusion.
16. When authoritative sources or an approved contract conflict, return
    `CONTRACT_CONFLICT`, preserve both observations and stop before implementation.
17. Do not present Seller Unit Economics, advertising DRR or buyer UI as final
    settlement.
18. No Calculator patch, Price Decision update, settlement-aware AI Analyst claim
    or automated Ozon write is permitted until empirical validation, separate
    review and explicit approval are complete.

## 16. Current EFA example — УФ 001Б

The example records observed price/configuration layers, not a settlement
decomposition.

| Observation | Value | Evidence role | Financial lifecycle / evidence classification |
| --- | ---: | --- | --- |
| `CATALOG_SELLER_PRICE` | 1,290 ₽ | Seller catalog/base configuration | `PROVISIONAL` |
| `SELLER_FUNDED_PROMO_DISCOUNT` | 630 ₽ | Derived configuration difference | `PROVISIONAL` |
| `SELLER_ACTION_PRICE` | 660 ₽ | Elastic action price | `PROVISIONAL` |
| `BUYER_STANDARD_DISPLAY_PRICE` | 436 ₽ | Buyer UI observation | `OBSERVED_BUYER_UI`; financial lifecycle not applicable |
| `BUYER_GREEN_PRICE` | 393 ₽ | Buyer UI observation | `OBSERVED_BUYER_UI`; financial lifecycle not applicable |

Configuration arithmetic:

```text
1,290 ₽ - 630 ₽ = 660 ₽
```

Observed differences:

```text
660 ₽ - 436 ₽ = 224 ₽ = UNRESOLVED_OBSERVED_DIFFERENCE
436 ₽ - 393 ₽ =  43 ₽ = UNRESOLVED_OBSERVED_DIFFERENCE
```

The 224 ₽ and 43 ₽ differences do not establish points, bank compensation,
seller funding or any combination. Until an order finance decomposition and final
settlement exist, `OFFICIAL_SELLER_PRICE`, `BUYER_CASH_REVENUE`, compensation and
the Green split remain unconfirmed.

## 17. Empirical validation cases

All cases must preserve source, observation time, order/posting linkage, period,
document version, original operation names, sign, currency and lifecycle status.

### Case #1 — Official seller-price identity

For delivered orders, reconcile buyer cash, loyalty compensation and points
compensation to the official seller price. PASS requires line-level evidence and
zero unexplained difference after documented rounding and corrections.

### Case #2 — Commission operational field mapping

Compare the actual commission amount with every plausible order-time field and
the applicable rate. PASS requires a repeated mapping across representative
orders, documented rounding/VAT semantics and return behavior. A semantic formula
alone does not pass this case.

### Case #3 — Acquiring base

Verify the actual acquiring amount against buyer cash and the bank tariff for the
order. PASS requires the buyer-paid base, rate, rounding and any correction to be
visible.

### Case #4 — Green compensation split

For an order using Green price, identify the ruble bank/partner component and the
points component from finance and loyalty evidence. Buyer UI differences alone do
not pass this case.

### Case #5 — Points lifecycle

Trace accrual, availability, application, reversal, settlement, adjustments,
excess premium and closing balance across the applicable period. PASS requires a
closed-period reconciliation and later-correction check.

### Case #6 — Points eligibility

Classify each service line as eligible, not eligible or unclear. PASS requires
documented application order and proof that partner-executor lines were not
silently treated as eligible.

### Case #7 — Settlement timing and finality

Verify real-time accrual, period close, document issue date and any subsequent
correction. PASS requires a provable transition from provisional data to final or
corrected-final evidence.

### Case #8 — Advertising allocation

Compare CPC/CPO source reports with Seller Unit Economics and order/SKU detail.
PASS requires an official or empirically proven allocation and lag rule. If it
cannot be established, the result remains `OZON_UNCLEAR`; no allocation is invented.

### Case #9 — Return corrections

On a returned order, verify sale, commission, points, loyalty/bank compensation,
logistics, processing/return and acquiring corrections independently. PASS does
not require every component to reverse, only a complete factual reconciliation.

### Case #10 — `accruals_for_sale` mapping

Determine whether and under what lifecycle/document context the operational field
maps to buyer cash, seller action price, official seller price or another amount.
Official documentation does not define this field, so PASS requires repeated
order-level empirical evidence and must not be generalized beyond its source scope.

### 17.1 Empirical validation case-to-gate matrix

A `SETTLEMENT_CRITICAL_CASE` is an empirical case whose unresolved or adverse
outcome can change seller realization, an included variable charge, settlement
finality or the interpretation of an operational financial field used by EFA OS.
The settlement-critical cases are **Cases #1–#7, #9 and #10**. Case #8 is not
settlement-critical for the core seller-price reconciliation, but it is mandatory
for any advertising-allocation implementation or claim.

Every case has exactly one of these allowed outcomes:

- `PASS`: all required evidence exists and satisfies the stated PASS criteria;
- `FAIL`: available authoritative or empirical evidence contradicts the tested
  identity, mapping, classification or reconciliation;
- `INSUFFICIENT_SETTLEMENT_DATA`: required evidence is missing or incomplete, so
  PASS/FAIL cannot be determined;
- `OZON_UNCLEAR`: official material and completed empirical review do not resolve
  the semantic or allocation question without invention.

For a settlement-critical case, only `PASS` closes its linked gates. `FAIL`,
`INSUFFICIENT_SETTLEMENT_DATA` and `OZON_UNCLEAR` keep every linked gate blocked.
Case #8 may remain `OZON_UNCLEAR` without blocking the core seller-price
reconciliation; that outcome still blocks every advertising-allocation-specific
formula, update and settlement-aware claim.

Gate codes in the matrix map to section 18: `G-CALC`, `G-PRICE`, `G-AI` and
`G-OZON`. “All four” means that no settlement-aware update to Calculator, Price
Decision or AI Analyst and no automated Ozon write may use the unresolved subject.

| Case | Required evidence | PASS criteria | FAIL criteria | Allowed outcomes | Blocked production gates | Components that cannot be updated while unclosed |
| --- | --- | --- | --- | --- | --- | --- |
| #1 Seller-price identity | Delivered-order buyer cash, loyalty, points and official seller-price lines; rounding/correction provenance | Components reconcile to `OFFICIAL_SELLER_PRICE` with zero unexplained difference | Non-zero unexplained difference or evidenced component counted twice | All four outcomes | All four | Calculator, Price Decision and AI Analyst seller-realization logic/claims; automated Ozon writes depending on it |
| #2 Commission mapping | Order-time candidate fields, actual commission, applicable rate, VAT/rounding and return behavior across representative orders | One repeatable operational mapping explains amount and corrections | Mapping is contradicted, non-repeatable or requires an unevidenced base | All four outcomes | All four | Calculator commission logic, Price Decision margin, AI Analyst commission claims; dependent Ozon writes |
| #3 Acquiring mapping | Buyer-paid amount, bank tariff, acquiring line, rounding and corrections | Actual acquiring is reproducibly explained by buyer cash, rate and rounding | Another base is evidenced or buyer-cash mapping does not reconcile | All four outcomes | All four | Calculator acquiring logic, Price Decision margin, AI Analyst acquiring claims; dependent Ozon writes |
| #4 Green split | Green order finance, partner-loyalty report, points detail and final settlement | Ruble and points allocations reconcile without UI inference or double count | Proven split contradicts the decomposition or leaves an unexplained funded amount | All four outcomes | All four | Calculator Green realization, Price Decision Green economics, AI Analyst funding claims; dependent Ozon writes |
| #5 Points lifecycle | Linked accrual, availability, application, reversal, adjustment, premium, close and later-correction evidence | Closed-period lifecycle reconciles and later corrections retain provenance | Lifecycle totals conflict, stages are collapsed or compensation is double counted | All four outcomes | All four | Calculator points economics, Price Decision margin, AI Analyst final-points claims; dependent Ozon writes |
| #6 Points eligibility | Service-line owner/executor, official rule, application order and actual points application | Every line has separate eligibility and source status; partner lines are not silently eligible | An ineligible/unconfirmed line is treated as eligible or application order conflicts with evidence | All four outcomes | All four | Calculator service cash/economic split, Price Decision margin, AI Analyst eligibility claims; dependent Ozon writes |
| #7 Finality transition | Timestamped real-time data, period close, closing documents, version and subsequent corrections | Evidence proves `PROVISIONAL` to `FINAL_SETTLEMENT` or `CORRECTED_FINAL_SETTLEMENT` transition | A final claim lacks closing provenance or ignores a documented correction | All four outcomes | All four | Calculator settled mode, Price Decision final recommendations, AI Analyst settlement-aware claims; dependent Ozon writes |
| #8 Advertising allocation | CPC/CPO source reports, Seller Unit Economics, order/SKU detail, attribution window and lag | Official or repeated empirical evidence establishes allocation and lag within a stated scope | Proposed allocation is contradicted or produces unreconciled attribution | All four outcomes | No core gate for `FAIL`, `INSUFFICIENT_SETTLEMENT_DATA` or `OZON_UNCLEAR`; advertising-specific scope remains blocked unless `PASS` | Advertising allocation in Calculator/Price Decision and AI Analyst advertising-settlement claims |
| #9 Return corrections | Returned-order sale, commission, points, loyalty/bank, logistics, processing and acquiring correction lines | Each component is independently reconciled; non-reversal is supported where applicable | Automatic blanket reversal, missing component provenance or unexplained difference remains | All four outcomes | All four | Calculator return economics, Price Decision margin, AI Analyst corrected-final claims; dependent Ozon writes |
| #10 `accruals_for_sale` mapping | Repeated order-level operational values, source scope, finance detail and lifecycle/document context | Mapping is repeatable and explicitly bounded to its proven source/context | Field is renamed into a canonical role, maps inconsistently or is generalized beyond evidence | All four outcomes | All four | Calculator/Price Decision use of period revenue, AI Analyst revenue and margin claims; dependent Ozon writes |

## 18. Implementation gates

The production gates are:

- `G-CALC`: `NO PRODUCTION CALCULATOR PATCH`;
- `G-PRICE`: `NO PRICE DECISION UPDATE`;
- `G-AI`: `NO AI ANALYST SETTLEMENT-AWARE CLAIM`;
- `G-OZON`: `NO AUTOMATED OZON WRITE`.

Until every settlement-critical case has outcome `PASS`, this contract
passes strict review, and a separate explicit `APPROVE` is recorded:

`NO PRODUCTION CALCULATOR PATCH`

`NO PRICE DECISION UPDATE`

`NO AI ANALYST SETTLEMENT-AWARE CLAIM`

`NO AUTOMATED OZON WRITE`

Allowed work is limited to read-only evidence collection, specification,
reconciliation, shadow calculations and tests of already supported rules. A later
approval of a contract version does not by itself authorize production or external
writes; those require their own exact target, operation and rollback approval.

## 19. Backward compatibility impact — no implementation

| Component | Current boundary | v1.1 impact after future approval | Current action |
| --- | --- | --- | --- |
| Calculator v1.1 | Frozen forecast model with one legacy seller-price input | Separate catalog, action, buyer cash, compensation, commission and acquiring semantics; preserve forecast provenance | None; existing validated checkpoint remains unchanged |
| Price Decision v1 | Forecast-oriented price recommendation | Use seller action economics separately from buyer competitiveness and block on unresolved settlement inputs | None |
| AI Analyst v1.3 | May observe prices and operational finance without full settlement lifecycle | Use canonical names, lifecycle/source status and avoid final claims from provisional data | None |
| Recommendation sidecar | Reads current Calculator configuration | Version contract/schema inputs and keep old behavior until an approved migration exists | None |
| Control Center | Displays capability and financial-gate state | Surface contract version, validation state and explicit blockers without claiming live settlement readiness | None |
| DB | Existing operational schema is authoritative for stored data, not for new semantics | Future versioned migration may add distinct fields, provenance and lifecycle events | None; no migration created or applied |
| Reports | Existing labels may reflect historical terminology | Future report version must label canonical layers and separate forecast, provisional and final values | None |
| n8n | Existing workflows use current payload contracts | Future sanitized workflow revisions must carry versioned fields and preserve credential separation | None |

The EFA Ozon Price Calculator V1 validated checkpoint remains historical forecast
evidence. Its field semantics are preserved rather than silently reinterpreted.
The official-reference conflict is recorded here and must be resolved only by a
separately reviewed implementation design.

### 19.1 Exact legacy runtime-field preservation

| Legacy field or output | Frozen/current semantics | v1.1 compatibility rule |
| --- | --- | --- |
| `seller_price` | Legacy Calculator forecast base input; commission, acquiring, tax, profit and `margin = profit / seller_price` use this input in the frozen model | Do not rename automatically and do not treat as `SELLER_ACTION_PRICE` without a reviewed migration mapping |
| `gross_sales` | Current `mcp_read.product_period_economics` aggregate built from `SUM(accruals_for_sale)` | Do not treat as `OFFICIAL_SELLER_PRICE` without repeated empirical mapping and lifecycle scope |
| `accruals_for_sale` | Operational Ozon-derived finance field used by the current period aggregate | Exact official semantic mapping remains empirical; no direct official equivalent is established |
| Legacy Calculator margin | Frozen `profit / seller_price` forecast formula and its validated rounding/threshold semantics | Preserve unchanged; it is not automatically equivalent to `EFA_CONTRIBUTION_MARGIN_V1_1` |
| Period economics margin | Separate legacy `margin_before_tax = TRUNC(profit_before_tax / gross_sales * 100, 2)` when existing validity conditions pass | Preserve as a distinct period formula; do not relabel it as the v1.1 margin |
| `P10` / `P12` / `P15` | Frozen legacy reverse-price outputs from the validated Calculator checkpoint | Preserve inputs, formula behavior and meaning; do not reinterpret through v1.1 terminology |

Mandatory compatibility invariant:

`NO LEGACY FIELD MAY BE REINTERPRETED BY RENAME ALONE`

## 20. Validation requirements for this draft

Before review completion, verify:

- all 21 document sections and required metadata are present;
- repository and official source links resolve to the intended sources;
- every formula is either required by this contract, official, derived from an
  official formula or explicitly marked `INTERPRETATION`;
- deprecated terminology occurs only in section 5;
- source status and financial lifecycle status are never conflated;
- all 13 canonical price/compensation fields, eight points lifecycle fields,
  four lifecycle statuses, five source statuses, 11 invariants, 18 hard rules,
  ten validation cases, four implementation gates and eight compatibility targets
  are present;
- no password, token, API key, bearer credential, Basic Auth value, database
  password, Telegram secret or Ozon secret is present;
- only the approved canonical-draft file and its prerequisite/index references
  are changed for canonical publication;
- `git diff --check` passes.

## 21. File scope and approval boundary

Canonical-draft publication adds:

`docs/contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1_1.md`

The accompanying changes to `AGENTS.md` and the documentation index may only
route settlement tasks to this canonical draft and preserve v1 as historical.
This approval does not authorize changes to the v1 contract, official reference,
code, configuration, database, workflows, production or Ozon.

Canonical-draft approval marker:

`V1_1_APPROVED_FOR_CANONICAL_DRAFT`
