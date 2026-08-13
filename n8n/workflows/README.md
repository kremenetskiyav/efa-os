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
