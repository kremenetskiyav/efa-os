# efa-os
AI Operating System for EFA automotive cabin air filter brand.

## OZON automation — Phase A baseline

Current architectural baseline for the OZON automation project:

- n8n workflow: `n8n/workflows/OZON_workflow_Phase_A.json`
- PostgreSQL is the persistence layer.
- OZON API authentication is performed through the n8n `Header Auth account` credential (`httpHeaderAuth`); API keys must not be stored directly in workflow JSON.
- Phase A includes product, stock, finance, postings, price history, returns, stock history, posting logistics, product alerts/Decision Engine, OZON Analytics and OZON Problem Analysis, plus the OZON AI Analyst interface.
- Region/logistics analytics is part of the Phase A analytical layer and must be preserved when extending the workflow.

### Baseline rules

1. Treat the working n8n workflow as the source of truth for runtime behavior.
2. Do not create duplicate workflows when an existing node/branch can be extended.
3. Preserve existing credential architecture and PostgreSQL schema compatibility.
4. Do not expose or commit real OZON API keys.
5. Any architectural change must be documented here before moving to the next phase.

### Current project state

Phase A is the established working baseline. The next development work should extend the existing architecture rather than rebuild it.
