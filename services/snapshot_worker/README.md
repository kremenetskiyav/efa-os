# Snapshot Worker v1 skeleton

This directory is a non-production skeleton for the future Snapshot Worker described in [SNAPSHOT_WORKER_V1_DESIGN.md](../../docs/architecture/SNAPSHOT_WORKER_V1_DESIGN.md).

## Scope

- Reads configuration only from environment variables.
- Supports `--dry-run`.
- In dry-run, validates PostgreSQL settings and opens/closes a connection without executing SQL queries.
- Does not create snapshots, events, migrations, tables, n8n integrations, or business-data changes.

## Required environment variables

- `EFA_DB_HOST`
- `EFA_DB_PORT`
- `EFA_DB_NAME`
- `EFA_DB_USER`
- `EFA_DB_PASSWORD`

Keep values local. Do not commit `.env`, passwords, connection strings, or n8n credentials.

## Local dry-run

```text
python main.py --dry-run
```

Expected successful output includes configuration status, PostgreSQL connection status, and:

```text
Snapshot Worker v1 skeleton ready
```

## Docker

The Dockerfile is a runtime foundation only. Build and run it with local environment injection after a separate operational review. Applying the Snapshot Layer migration and connecting this service to n8n are intentionally out of scope for this skeleton.
