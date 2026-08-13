# AGENTS.md

## Project purpose

`efa-os` is the source-controlled project for the EFA OZON AI automation system.
The canonical runtime is local: Docker Desktop + n8n + PostgreSQL, with OZON Seller API as the external data source and an AI analyst/decision-support layer on top of PostgreSQL.

## Source of truth

- The canonical n8n workflow is `n8n/workflows/OZON_workflow_Phase_A.json`.
- GitHub is the source-control and documentation layer; it is not the production runtime.
- Existing workflow branches should be extended rather than duplicated.
- Existing PostgreSQL tables/views must be reused when they already provide the required data.
- SQL/analytical logic should live in PostgreSQL queries/views rather than being duplicated in n8n JavaScript nodes.

## Security

- Never commit real OZON API keys, passwords, access tokens, cookies, session data, or n8n credentials.
- Keep credentials in local n8n credential storage or local environment configuration.
- Repository copies of workflows must contain placeholders instead of secrets.

## Change discipline

Before changing a workflow or analytical query:
1. Read `docs/PROJECT_STATUS.md`.
2. Read `docs/ARCHITECTURE.md`.
3. Inspect the existing workflow branch/tool before creating anything new.
4. Preserve existing table and view compatibility unless a migration is explicitly planned.
5. Update the relevant documentation when architecture or behavior changes.
6. Keep changes small and testable.

## Current known blockers

The Phase A audit identifies incomplete pagination/incremental ingestion, an incorrect `OZON Analytics` AI tool contract/SQL, an unresolved Decision Engine role, incomplete versioning of the database analytical layer, and the lack of a verified live PostgreSQL schema in the connected environment. Do not declare the system production-safe until these issues are resolved.

## PostgreSQL

A WoWSQL connector is installed, but the connected account currently has no WoWSQL project. Do not invent or assume a live database schema. Inspect the actual schema before rewriting views, migrations, or analytical SQL.

## Ongoing rule

Prefer improving the existing Phase A architecture over rebuilding it. Preserve regional logistics, price history, returns analytics, and other verified analytical tools when extending the system.
