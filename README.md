# efa-os

EFA OS is the operational system for the EFA automotive cabin air filter brand: OZON marketplace data, PostgreSQL analytics, n8n orchestration, and AI decision support.

## Business context

EFA develops automotive cabin air filters and technical requirements; manufacturing is performed by a partner factory to EFA specifications. The primary sales channel is Ozon Marketplace.

The long-term goal is to build a scalable filtration brand supported by AI, automation, and standardised business processes while keeping product facts and human responsibility central to decision-making.

## Technical architecture

The production runtime is the Timeweb VPS:

- Docker hosts PostgreSQL 16, n8n, the existing collectors and EFA Read MCP.
- EFA Read MCP exposes exactly nine read-only tools over curated `mcp_read`
  sources.
- The host cron generates AI Analyst at 16:00 Europe/Moscow and delivers one
  compact payload through Email and Telegram at 16:30.
- Control Center runs as one local-only systemd service behind Caddy and Basic
  Auth at [panel.efa-os.ru](https://panel.efa-os.ru).
- OZON Seller API is the external data source.
- PostgreSQL is the persistence and analytical layer; period financial
  economics are read through `mcp_read.product_period_economics(from_date,
  to_date)`.
- `n8n/workflows/OZON_workflow_Phase_A.json` is the canonical Phase A workflow.
- AI Analyst and Price Decision provide read-oriented analysis and proposals;
  they perform no automatic Ozon write actions.

Data flow:

`OZON API -> existing collectors/n8n -> PostgreSQL -> mcp_read -> AI Analyst -> Price Decision / Compact Report / Control Center`

GitHub stores version-controlled code, migrations, sanitised workflow exports
and documentation; it is not the production runtime. The current stable
production checkpoint is recorded in
[docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

## OZON automation — Phase A baseline

Phase A is the established working baseline. It covers products, stocks, finance operations, postings, price history, returns, stock history, posting logistics, product alerts, regional analytics, and AI-assisted analysis.

Key rules:

1. Extend the existing workflow instead of creating a duplicate one.
2. Preserve PostgreSQL schema compatibility and keep persistent calculations in SQL.
3. Keep OZON credentials in local n8n credential storage; never store API keys in workflow JSON.
4. Preserve verified regional logistics, price history, returns, stock, and financial analytics when extending the system.

The verified Phase A status, metrics, and roadmap are maintained in [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/ROADMAP.md](docs/ROADMAP.md).

## Snapshot Layer v1

The next architectural direction is autonomous monitoring based on immutable product state snapshots and deterministic change detection.

The initial scope is deliberately narrow:

- create immutable snapshots after successful data ingestion;
- compare consecutive valid price states for the same canonical `offer_id`;
- detect `PRICE_CHANGED` events only;
- keep AI in an analysis and recommendation role;
- do not automatically change products, prices, promotions, stock, or OZON settings.

Snapshot Layer implementation must reuse existing Phase A data sources and preserve the current workflow and analytical tools.

## Repository structure

```text
.env.example              Secret-free environment-variable template
AGENTS.md                 Project rules for contributors and AI agents
README.md                 Project overview
requirements.txt          Python dependencies for local scripts
Scripts/                  Local utility scripts, including cost-price import
database/                 Versioned PostgreSQL migrations and their instructions
docs/                     Architecture, project status, roadmap, and product standards
n8n/workflows/            Sanitised canonical n8n workflow exports
```

New directories are documented only after they are introduced and reviewed; this README does not list placeholder or non-existent folders.

## Security and data integrity

- Never commit secrets, `.env` files, n8n credentials, local database dumps, Docker volumes, logs, or temporary files.
- Use `.env.example` only as a secret-free configuration template when scripts require environment variables.
- Store reviewed PostgreSQL schema migrations in `database/migrations/`; apply them manually only after review and explicit approval.
- Keep n8n credentials in local n8n credential storage. Workflow exports in Git must remain sanitised and contain placeholders only.
- Do not invent product specifications, OEM references, or compatibility. Preserve traceability to verified product sources.
- AI supports people; it does not replace responsibility or approve autonomous business changes.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Ozon Discount & Points Settlement Contract v1.1](docs/contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1_1.md) — Current canonical draft for settlement semantics; not approved for production implementation.
- [Ozon Discount & Points Settlement Contract v1](docs/contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md) — Historical predecessor and deprecation reference.
- [Project status](docs/PROJECT_STATUS.md)
- [Roadmap](docs/ROADMAP.md)
- [Changelog](docs/CHANGELOG.md)
