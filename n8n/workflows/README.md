# Canonical n8n workflows

## OZON workflow - Phase A

Canonical local workflow ID: `B2DiIq630Yb2fXR8`.

The workflow contains 57 nodes and is inactive in both the canonical export and
the current production instance. Older local workflows with similar names are
not recovery sources.

The production n8n instance remains local. GitHub stores the sanitized source-control representation and documentation.

### Credential policy

The OZON API key must never be stored in this repository. The sanitized local export replaces the API key with `__OZON_API_KEY__`. The real credential remains in local n8n credential storage.

The workflow uses the local Seller API header credential. Credential IDs and
secret values are deliberately absent from the canonical export and must be
bound manually during an authorised recovery.

- Get Products
- Get Product Info
- Get Stocks
- Get Financial Operations
- Get Postings
- Get Returns
- Get Current Prices

### Baseline

The current baseline was exported from the local n8n instance after the OZON API credential rotation. The full sanitized JSON is kept locally and is the source artifact for the next repository synchronization step.

## Ozon Daily Commercial Brief Delivery v1

Canonical production workflow ID: `Kf241Y5kzETghygL`.

The sanitised workflow is [`Ozon_Daily_Commercial_Brief_Delivery_v1.json`](Ozon_Daily_Commercial_Brief_Delivery_v1.json). It is retained for history and recovery but is **inactive** in production. Its former 08:15 `Europe/Moscow` Email and Telegram delivery must not be reactivated while the AI Analyst delivery below is active. The separate TEST workflow also remains inactive.

## EFA AI Analyst Delivery

Canonical production workflow ID: `EFAANALYSTEMAIL`.

[`EFA_AI_Analyst_Delivery_v1.json`](EFA_AI_Analyst_Delivery_v1.json) is the active delivery workflow behind the existing `efa-ai-analyst-email` webhook. The existing cron generates AI Analyst at 16:00 `Europe/Moscow` and posts one compact formatter payload at 16:30. The workflow sends that same payload through the existing Gmail credential and through one Telegram branch using the existing Telegram credential and chat destination. Runtime destinations and credentials remain only in n8n; the repository export uses placeholders. The workflow has no schedule trigger and does not calculate analytics.

## CPC Async Report Lifecycle v1

`CPCDAILYV1` is the active 07:30 `Europe/Moscow` CREATE stage in
[`CPC_Daily_Collection.json`](CPC_Daily_Collection.json). It reserves one
durable lifecycle per business date, skips dates that already have any state,
creates at most one Performance report and registers its UUID without waiting.

[`CPC_Report_Poller_v1.json`](CPC_Report_Poller_v1.json) contains the separate
ten-minute status/download poller (`CPCREPORTPOLLERV1`). It checks only leased
`PENDING` UUIDs and has no report-creation node. The production poller is
active; the migrated 17.08 report is final `STUCK / NOT_STARTED` and is not
reopened.

## Ozon Operational Finance Daily Collection v1

[`Ozon_Operational_Finance_Daily_Collection_v1.json`](Ozon_Operational_Finance_Daily_Collection_v1.json)
is the active 05:40 `Europe/Moscow` sequential collector (`OPFINDAILYV1`) for
FBS Postings, Returns and Finance. It retains the existing source endpoints and
business-table keys, uses bounded pagination and HTTP retry, and persists
independent run freshness through migration 011. Runtime Seller API and
PostgreSQL credentials remain bound only in local n8n storage.
