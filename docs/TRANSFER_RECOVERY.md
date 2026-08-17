# EFA OS transfer and recovery contract

Checkpoint date: 2026-08-17. GitHub is canonical for source code, migrations,
sanitised n8n workflows, configuration templates and documentation. It is not
the production runtime and must not contain secrets, database backups, private
Ozon reports, downloaded legal documents or browser/session data.

## Operating modes

- `DEV_ONLY` — mandatory default on a second computer. No production database
  restore, active schedules, delivery credentials or production API calls.
- `STANDBY` — runtime may be reconstructed, but every n8n schedule remains
  inactive and outbound deliveries remain disabled.
- `PRODUCTION` — allowed only after the owner has stopped and verified the old
  production instance. Only one computer may be in this mode.

The home computer remains the production instance at this checkpoint. Starting
the same schedules on another computer would duplicate collectors and Daily
Brief deliveries.

## Second-computer development mode

1. Install Git and the required development tools.
2. Clone `https://github.com/kremenetskiyav/efa-os.git` and checkout `main`.
3. Verify the expected checkpoint commit documented in `PROJECT_STATUS.md`.
4. Work in `DEV_ONLY`; do not apply production migrations or import active n8n
   workflows.
5. Without Docker, limit work to source, documentation and tests whose declared
   dependencies are locally available.

## Full recovery prerequisites

- Docker Desktop with Compose;
- PostgreSQL 16 (the recovery Compose definition pins the observed image);
- n8n 2.32.7 and the repository custom Performance API extension;
- a protected local `runtime.env` created from the secret-free templates;
- the validated PostgreSQL custom-format backup referenced by the local
  recovery manifest;
- manual access to recreate or re-authorise n8n credentials.

The n8n image build uses the pinned local base tag
`efa-n8n-base:2.32.7-local`. On a replacement host, obtain the exact n8n 2.32.7
base image, verify its digest against the local recovery manifest, and assign
that tag before building `docker-compose.n8n-performance.yml`. Do not use an
unverified newer `latest` image.

## Full recovery order

1. Confirm the old production instance and all of its schedules are stopped.
2. Clone GitHub and checkout the recorded checkpoint.
3. Install Docker prerequisites; create external network `efa-tools` and volumes
   `efa_pgdata` and `n8n_data` explicitly.
4. Restore the protected local secret mechanism; never copy secrets into Git.
5. Start only PostgreSQL using `deployment/docker-compose.infrastructure.yml`.
6. Restore the validated database backup and verify schema/migration objects.
7. Build n8n 2.32.7 with the custom Performance API package.
8. Recreate/re-authorise n8n credentials manually, then import the sanitised
   canonical workflow definitions with every schedule inactive.
9. Start private EFA services and run health/read-only checks.
10. Compare canonical workflows, credential bindings and schedules.
11. Move from `STANDBY` to `PRODUCTION` only with explicit owner approval.

## Credentials

Credential values are not backed up in Git or in the default recovery bundle.
PostgreSQL runtime settings remain in the protected local secret file. Seller
API, Performance API, Gmail OAuth and Telegram credentials require manual
recreation or re-authorisation unless the owner separately approves an
encrypted n8n credential-store backup.

## Canonical production workflows

The sanitised definitions in `n8n/workflows/` cover Promotions Snapshot,
Seller Analytics Daily, CPC Daily, Price Snapshot and Daily Commercial Brief
Delivery. Recipient/chat destinations and credential bindings are intentionally
local and require manual reconstruction.

## Local recovery data

The current backup and metadata-only recovery bundle live under
`C:\Users\Andrey\.efa-os\`. Their names, checksums and local-only evidence
locations are recorded in the bundle manifest. The directory is outside Git and
must be transferred through owner-approved encrypted storage.
