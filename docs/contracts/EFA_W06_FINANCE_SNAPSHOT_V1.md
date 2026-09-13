# efa_w06_finance_snapshot.v1

Owner-authorized local integration, 2026-09-13. Financial authority/provider: W06.
Consumers: W00, W07, read-only Control Center. No n8n/collector dependency.
Machine schema: [efa_w06_finance_snapshot.v1.schema.json](efa_w06_finance_snapshot.v1.schema.json).
Runtime validator and presentation adapter: `services/control-center/w06_snapshot.py`.

## Storage and publication

- Primary: `OZON_AI_AGENTS/REPORTS/W06/SNAPSHOTS/CURRENT_FINANCE_SNAPSHOT_V1.json`.
- Immutable dated: `OZON_AI_AGENTS/REPORTS/W06/SNAPSHOTS/YYYY-MM-DD/W06_FINANCE_SNAPSHOT_<timestamp>_<preset>.json`.
- Current-period evidence uses the stable dated alias
  `W06_FINANCE_SNAPSHOT_<PRESET>_V1.json`; the first required artifact is
  `W06_FINANCE_SNAPSHOT_YESTERDAY_V1.json`.
- `build_current_period_finance_snapshot.py` accepts captured EFA Read MCP
  daily evidence, a read-only Ozon Unit Economics XLSX and an Accruals XLSX.
  It keeps demand, order-cohort economics, account accruals, current-cost proxy
  and settlement as separate layers. A semantic source difference is disclosed
  and is not a global conflict. The builder applies one contract path for
  YESTERDAY, LAST_7_DAYS and CURRENT_MONTH, audits before publication, and
  never allocates account advertising to SKU.
- W06 publishes with `OZON_AI_AGENTS/W06_FINANCE_UNIT_ECONOMICS/publish_finance_snapshot.py --input <prepared-result.json>`.
- `--dated-only` adds another exact period. `--import-august` explicitly converts
  the retained August W06 report without any network read or external write.
- `--audit-only` validates without publishing. Output always identifies whether
  a file was created and its actual path. Dated files are immutable/idempotent;
  CURRENT replacement is atomic after validation. Keep prior dated versions.
- Readers perform no writes. No schedule/backend/collector was added.

## Required top-level fields

| Field | Meaning |
| --- | --- |
| schema | Literal `efa_w06_finance_snapshot.v1` |
| generated_at | Timezone-aware publication timestamp; never evidence freshness |
| period | preset, from/to ISO dates inclusive, timezone=Europe/Moscow |
| source_status | Top level: AVAILABLE, PARTIAL, INSUFFICIENT_DATA. Layer level additionally permits INCOMPLETE when exact coverage gaps are disclosed and affected canonical totals remain null; supplied by W06 |
| financial_mode | OBSERVED, SETTLEMENT_AWARE, SELLER_SIDE_PROXY, MIXED_OBSERVED_PROXY, INSUFFICIENT_DATA |
| settlement_status | INSUFFICIENT_SETTLEMENT_DATA, FINAL_SETTLEMENT, CORRECTED_FINAL_SETTLEMENT |
| freshness | status, observed_at, valid_until; validity belongs to W06 |
| layers | demand, operational_economics, account_finance, cost and settlement, each with independent source status, mode, freshness, confidence and basis |
| source_comparisons | Explicit cross-source observations and their semantic/conflict classification |
| portfolio | Explicit portfolio values; never calculated by summing displayed SKU |
| skus | Exactly five unique EFA/Ozon mappings, financial fields, commercial_role, financial_gate |
| reconciliation | W06 status, field rows (portfolio, sku_sum, gap, status), optional gap reasons/bridge |
| warnings | Explicit limits/blockers; no fake zero or inferred completion |
| evidence | Source references with observation, confirmation and limitations where available |

Portfolio and SKU require all these nullable fields:

`ordered_units`, `delivered_units`, deprecated `returned_units`,
`buyer_returned_units`, `logistic_return_units`, `ordered_revenue`,
`seller_realization`, `cogs`, `ozon_commission`, `logistics`, `last_mile`,
`processing`, `acquiring`, `advertising_cpc`, `advertising_cpo`,
`advertising_total`, `compensations`, `other_costs`, `contribution_rub`,
`contribution_pct`, `profit_rub`, `profit_pct`.

Amounts are finite JSON numbers or decimal strings, or null. Numeric strings
avoid rounding on serialization. Unit counts must be nonnegative integers.
Percentages are W06-reported values; consumers do not derive ratios.
Every field, including null, requires `field_metadata[field]` with `semantic`,
`source`, `source_timestamp`, `confidence` and `financial_mode`. Null values use
`INSUFFICIENT_DATA`; absent provenance remains explicit null rather than an
invented source. Every non-null field requires a source reference present in
evidence. Realization additionally requires `basis=SELLER_REALIZATION`. Buyer
observations and attributed advertising sales cannot satisfy that assertion.
Proxy contribution requires a non-empty `missing_components` list.

## Semantics and safe failure

- Buyer price is not seller realization. Ordered revenue stays separate.
- `returned_units` is a deprecated compatibility field and must remain null in
  new snapshots. Ozon Unit Economics buyer returns belong in
  `buyer_returned_units`; MCP logistics-return events belong in
  `logistic_return_units`.
- Contribution is not profit. No profit may be inferred from contribution.
- Non-final settlement requires both profit fields null and
  `settlement_status=INSUFFICIENT_SETTLEMENT_DATA`.
- A supplied profit additionally requires SETTLEMENT_AWARE and explicit
  `complete_costs=true` and `cost_completeness` flags for tax, historical_cogs,
  returns, settlement_adjustments, internal_costs, finance_costs, advertising. This validator does not grant settlement implementation
  approval; all v1.1 empirical/production gates remain in force.
- Portfolio CPC/CPO from Ozon Accruals may remain non-null while all SKU
  advertising fields are null. This is an allowed account-level allocation gap.
- Numerical reconciliation is valid only when metric definition, date basis,
  cohort basis and lifecycle state are the same. Differences between semantic
  layers are recorded in `source_comparisons`, not forced into equality.
- No automatic allocation, unit-economics formula or financial
  reconciliation is run in the UI reader. It copies the W06 reconciliation.
- Optional historical `presentation_metrics` preserve already reported
  named totals/COGS limitations; they cannot override canonical fields or profit.
- Schema-invalid, unsafe provenance, duplicate/mismatched SKU and nonfinite
  numbers fail closed. An invalid current artifact does not revive old numbers.

W07 audit outcomes are `PASS`, `PARTIAL_VALID`,
`SEMANTIC_SOURCE_DIFFERENCE`, `TRUE_DATA_CONFLICT` and `STRUCTURAL_FAIL`.
Strict `audit()` preserves validation exceptions for publication safety;
`audit_outcome()` converts such an exception to the explicit `STRUCTURAL_FAIL`
result for reporting without making the document publishable.
An `INCOMPLETE` demand layer does not block independently sourced exact-period
operational-economics or account-finance facts. Demand totals remain `null`,
missing dates and coverage are disclosed, and contribution/profit remain `null`.

For a current-period seller-side proxy, W06 may report SKU contribution before
advertising from seller realization less operational Ozon costs and current
COGS proxy when all three use the same Unit Economics order cohort. Account
advertising remains `null` by SKU. At portfolio level only, W06 may subtract the
exact-period account advertising total once and report contribution and margin
as `SELLER_SIDE_PROXY`. Profit remains `null`; historical effective COGS,
settlement, tax and internal-cost gaps must stay disclosed.
Publication is allowed for `PARTIAL_VALID` and semantic differences, but blocked
for `TRUE_DATA_CONFLICT` or structural/provenance/financial-safety failure.

## Period and freshness rules

TODAY, YESTERDAY, LAST_7_DAYS, LAST_30_DAYS, CURRENT_MONTH, PREVIOUS_MONTH,
and separately AUGUST_2026 are supported. Reader matches **both preset and exact
date bounds**. August never fills PREVIOUS_MONTH, even when dates coincide.
CURRENT is primary for its period; other exact periods can use dated snapshots.
Expired rolling-period values are not relabelled with new dates.

FRESH requires W06 `observed_at` and `valid_until`. Consumer checks the supplied
expiry against now; it does not invent a collector cadence or freshness SLA.
An expired exact-period result remains visible with STALE and its provenance.
Refreshing generated_at alone does not refresh evidence. Without evidence
validity use UNKNOWN for observed evidence whose validity SLA is not approved,
or NO_DATA for absent evidence. HISTORICAL_REFERENCE is August-only.

Missing: “Финансовый отчёт W06 ещё не сформирован”.
Stale: “Финансовый отчёт требует обновления”.
Invalid: “Финансовый отчёт W06 не прошёл проверку”.
Missing/invalid period values remain null and retain all five SKU identities.

## API compatibility

GET `/api/finance?period=CURRENT_MONTH` retains
`schema_version=efa_finance_snapshot_v1`, portfolio/skus/metadata/warnings/
reconciliation and adds the canonical schema/period/source fields.
GET `/api/status` uses the same provider for the existing V3 views/period selector.
`metadata.provider=W06`, `transport=W06_STRUCTURED_SNAPSHOT`, `load_status`,
`snapshot_path` and `provider_check` expose intake readiness independently of
Work execution state. No POST or external-write endpoint is added.
