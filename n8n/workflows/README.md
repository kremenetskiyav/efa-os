# Canonical n8n workflows

## OZON workflow - Phase A

Canonical local workflow ID: `q0yXnbt8BqFnukQj`

Latest supplied export version: `2b069584-6423-4fd6-a849-6f9b4769c94d`

The workflow contains 51 nodes and is currently inactive in the supplied export.

The production n8n instance remains local. GitHub stores the sanitized source-control representation and documentation.

### Credential policy

The OZON API key must never be stored in this repository. The sanitized local export replaces the API key with `__OZON_API_KEY__`. The real credential remains in local n8n credential storage.

The current workflow uses seven OZON HTTP Request nodes that require the API credential:

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
