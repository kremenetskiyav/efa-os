# AGENTS.md

## Project purpose

`efa-os` is the source-controlled project for the EFA automotive cabin air filter brand and its OZON AI automation system. The canonical runtime is local: Docker Desktop + n8n + PostgreSQL, with OZON Seller API as the external source and an AI analyst/decision-support layer on top of PostgreSQL.

## Source of truth and architecture

- The canonical n8n workflow is `n8n/workflows/OZON_workflow_Phase_A.json`.
- GitHub is the source-control and documentation layer; it is not the production runtime.
- `products.offer_id` is the canonical product identifier for analytical and monitoring work.
- Extend existing workflow branches and PostgreSQL tables/views when they already provide the required capability; do not duplicate them.
- Keep persistent business calculations and SQL aggregation in PostgreSQL queries/views rather than duplicating them in n8n JavaScript nodes.

## Product-data integrity

- Facts take priority over assumptions. Do not invent technical specifications, OEM numbers, dimensions, compatibility, or service life.
- State vehicle compatibility only when it is supported by verified data; otherwise state that confirmation is unavailable.
- Do not claim that a product is OEM or superior to OEM without verified evidence.
- Treat SKU material in `EFA Products/` as a primary source until it is transferred into an approved product passport.
- Ozon documents and materials must follow the applicable product and marketplace standards.

## Security and configuration

- Never commit real OZON API keys, passwords, access tokens, cookies, session data, connection strings, or n8n credentials.
- Keep credentials in local n8n credential storage or local environment configuration.
- Configuration for scripts must use environment variables. Maintain permitted variable names in `.env.example` without real values; keep `.env` local and ignored.
- Do not commit local exports, database dumps, backups, financial workbooks, logs, Docker volumes, or temporary files.
- Repository copies of workflows must contain placeholders instead of secrets.

## Change discipline

Before changing a workflow, analytical query, migration, or monitoring logic:

1. Read `docs/PROJECT_STATUS.md` and `docs/ARCHITECTURE.md`.
2. Inspect the existing workflow branch, table, view, or tool before creating anything new.
3. Preserve table/view compatibility unless a migration is explicitly planned and reviewed.
4. Keep changes small, testable, and documented when architecture or behaviour changes.
5. Before a commit, review `git status` and the exact diff.
6. Do not delete or overwrite source product data without explicit approval.

## PostgreSQL and migrations

- Inspect the actual PostgreSQL schema before rewriting views, migrations, or analytical SQL; do not infer it from documentation alone.
- Do not modify existing Phase A tables or views unless the change is explicitly planned.
- Version new schema changes as reviewed migrations when the repository migration mechanism is present. Never apply a migration to a working database without explicit approval.

## Snapshot Layer and autonomous monitoring

- Snapshot Layer v1 is a monitoring foundation, not an automated control system.
- Its initial scope is immutable product snapshots and the deterministic `PRICE_CHANGED` event.
- Use UTC timestamps for technical event time and Europe/Moscow business dates for operations.
- Repeated runs must be idempotent; corrections are represented by new runs and snapshots, not updates to historical facts.
- Do not automatically change products, prices, promotions, inventory, or OZON settings.

## AI-agent rules

- AI agents may analyse verified facts and generate explanations or recommendations; they must not present inference as fact.
- Keep facts, detected events, interpretations, and recommended actions separate.
- Read existing tools and documentation before proposing a new tool or workflow branch.
- Do not bypass security controls, reveal credentials, execute production-changing actions, or claim the system is production-safe without evidence.
- Prefer improving the existing Phase A architecture over rebuilding it; preserve verified regional logistics, price history, returns, stock, and financial analytics.
