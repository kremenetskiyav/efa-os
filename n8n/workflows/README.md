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

The sanitised workflow is [`Ozon_Daily_Commercial_Brief_Delivery_v1.json`](Ozon_Daily_Commercial_Brief_Delivery_v1.json). It has one daily Schedule Trigger at 08:15 in `Europe/Moscow`, obtains deterministic representations only from the private `efa-daily-brief` bridge, and has no Ozon nodes. Recipient and chat destination are runtime placeholders; Gmail and Telegram credentials are bound only in local n8n credential storage. Per-channel production idempotency is stored in workflow static data under `daily-brief:v0.1:production:<channel>:<business_date>`. The separate TEST workflow remains inactive.

## CPC Async Report Lifecycle v1

`CPCDAILYV1` is the active 07:30 `Europe/Moscow` CREATE stage in
[`CPC_Daily_Collection.json`](CPC_Daily_Collection.json). It reserves one
durable lifecycle per business date, skips dates that already have any state,
creates at most one Performance report and registers its UUID without waiting.

[`CPC_Report_Poller_v1.json`](CPC_Report_Poller_v1.json) contains the separate
ten-minute status/download poller (`CPCREPORTPOLLERV1`). It checks only leased
`PENDING` UUIDs and has no report-creation node. The production poller is kept
inactive until the owner approves the first controlled poll of the migrated
17.08 report.
