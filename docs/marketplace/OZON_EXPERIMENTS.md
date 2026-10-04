# Ozon Experiment Spec

## Purpose

This file is the canonical lightweight layer for controlled Ozon marketplace experiments in EFA.

Use it when a deliberate change is intended to measure business impact, for example:
- price;
- CPO / advertising;
- promotions or boosting;
- listing content;
- FBO / FBS;
- other controlled marketplace changes.

Do not create an experiment for routine read-only checks or mandatory corrections unless their business effect is intentionally being tested.

This file does not authorise any Ozon write. External writes still require separate explicit Owner approval under `AGENTS.md`.

## Core rules

1. One experiment has one principal controlled change.
2. Define the baseline, frozen variables, evidence sources, metrics, stop conditions, and acceptance criteria before execution whenever possible.
3. Do not retrofit success criteria after seeing results.
4. If a frozen variable changes materially during the observation window, mark the experiment `CONFOUNDED` unless the effect can be isolated with verified evidence.
5. `UNKNOWN` is not a success or failure.
6. Keep total store orders separate from campaign-attributed orders.
7. Declare a canonical source per metric. Do not treat any single source as universally authoritative.
8. Preserve provenance: source, period, observation/verification time when available, and confirmation level.
9. A completed experiment ends with explicit `RESULT`, `EVIDENCE`, and `DECISION`.

## Status values

- `DRAFT` — not ready to execute.
- `READY` — specification is sufficient; waiting for execution approval/start.
- `RUNNING` — experiment is active.
- `CONFOUNDED` — causal interpretation is compromised.
- `STOPPED` — ended early.
- `COMPLETE` — observation window ended and evidence is sufficient for evaluation.

## Decision values

Use only when evidence supports the decision:

- `CONTINUE`
- `SCALE`
- `STOP`
- `EXTEND`
- `RETEST`
- `INCONCLUSIVE`

## Experiment template

```text
## EXP-[ID]

GOAL:
Business question to answer.

HYPOTHESIS:
Expected effect and rationale.

SCOPE:
SKU / campaign / marketplace area.

BASELINE:
Verified comparison state or period.

CHANGE:
The principal controlled change.

FROZEN_VARIABLES:
Variables that should not change during the test.

CANONICAL_SOURCES:
Metric -> authoritative evidence source for this experiment.

METRICS:
Primary and supporting measurements.

STOP_CONDITIONS:
Conditions for early termination.

ACCEPTANCE_CRITERIA:
Predefined SUCCESS / FAIL / INCONCLUSIVE criteria.

STATUS:
DRAFT / READY / RUNNING / CONFOUNDED / STOPPED / COMPLETE

RESULT:
Filled after evaluation.

EVIDENCE:
Verified observations, source and period.

DECISION:
CONTINUE / SCALE / STOP / EXTEND / RETEST / INCONCLUSIVE
```

---

## EXP-CPO-7

GOAL:
Determine the commercial effect of CPO All Products at 7% for the current UF001-UF005 portfolio.

HYPOTHESIS:
Not pre-registered before start. Do not reconstruct retroactively.

SCOPE:
UF001-UF005.

BASELINE:
Not yet canonically resolved in this file. Use only a verified comparable pre-7% period when evaluating the final result.

CHANGE:
CPO All Products = 7%.

FROZEN_VARIABLES:
Not formally pre-registered before start. Any material price, content, promotion, stock-mode, or other growth-mechanic change during the observation window must be recorded and assessed for confounding.

CANONICAL_SOURCES:
- Gross / cancelled / net FBS orders: Owner-uploaded FBS `postings.csv`.
- CPO rate, spend and campaign attribution: direct Ozon Seller campaign data or verified export from that campaign.
- Other metrics: source must be declared before using the metric in a decision.

METRICS:
- gross orders;
- cancelled orders;
- net non-cancelled orders;
- net orders by SKU;
- CPO-attributed orders;
- CPO spend;
- contribution after advertising only when settlement-critical inputs are verified.

STOP_CONDITIONS:
Not pre-registered before start. Existing safety, economics, and Owner stop decisions still apply.

ACCEPTANCE_CRITERIA:
Not defined before start. Do not retrofit thresholds to observed results. Final interpretation must therefore use increased caution and may be `INCONCLUSIVE`.

STATUS:
RUNNING.

RESULT:
Pending.

EVIDENCE:
Verified Owner-side data for completed period 2026-10-02 through 2026-10-03:
- source: Owner-uploaded FBS `postings.csv`;
- rows = 5;
- quantity = 1 per row;
- gross orders = 5;
- cancelled = 1;
- net non-cancelled = 4;
- UF001 = 0 gross / 0 net;
- UF002 = 0 gross / 0 net;
- UF003 = 1 gross / 1 net;
- UF004 = 1 gross / 1 net;
- UF005 = 3 gross / 2 net.

DECISION:
Pending.
