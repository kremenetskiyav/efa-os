# EFA OS — Production Recovery & Provenance Manifest v1

| Field | Value |
| --- | --- |
| Observed at | `2026-09-02` |
| Observation snapshot | `2026-09-02T05:43:44+00:00` |
| Canonical runtime recovery source | `6ee1711a2b61f86e8315721cf395fde197208f6c` |
| Repository HEAD at review time | `f1c1576ef0895fda03b30f1e769bc27deccddc5a` |
| Production runtime base | `87b442e9a1ae16d256101b0bf48f0c142c5d447d` |
| Status | `DRAFT — READY FOR REVIEW` |
| Runtime classification | `MULTI-COMMIT RUNTIME MOSAIC` |
| Source recoverability | `ALL 13 HOST RUNTIME OVERLAYS PRESENT IN CANONICAL MAIN` |
| Runtime-only host overlays | `RUNTIME_ONLY_OVERLAY = 0` |
| Overall recovery classification | `PARTIALLY REPRODUCIBLE` |

## 1. Purpose and authority

This manifest records the observed EFA OS production recovery state. It is an
inventory and recovery contract, not an authorization to perform recovery,
cleanup, deployment, restart, migration, workflow import, credential change,
or any external write.

The manifest has two distinct source references:

- `87b442e9a1ae16d256101b0bf48f0c142c5d447d` is the Git base of the
  observed `/opt/efa-os` production checkout.
- `6ee1711a2b61f86e8315721cf395fde197208f6c` is the canonical source commit
  that contains every one of the 13 observed host runtime overlays.

Runtime evidence is authoritative for what was running at the observation
time. Git is authoritative for tracked source provenance. PostgreSQL schema
evidence establishes observed capability, but not an exact migration sequence.

## 2. Safety boundaries

- Production recovery has not been executed.
- Production has not been switched to the canonical source commit.
- No production file, service, container, image, workflow, database object,
  schedule, Caddy configuration, or Ozon state was changed while preparing
  this manifest.
- Secret values are excluded. Only protected storage locations and recovery
  requirements are recorded.
- Calculator and settlement provenance does not authorize financial logic
  changes. The Ozon Discount & Points Settlement Contract v1 remains
  `NOT APPROVED FOR PRODUCTION`; the gate remains `NO PRODUCTION CALCULATOR PATCH`.

## 3. Source baseline

### 3.1 Local canonical checkout

| Item | Observed value |
| --- | --- |
| Local path | `D:\efa-os-github` |
| Branch | `main` |
| Local HEAD | `6ee1711a2b61f86e8315721cf395fde197208f6c` |
| Local `origin/main` | `6ee1711a2b61f86e8315721cf395fde197208f6c` |
| GitHub `main` | `6ee1711a2b61f86e8315721cf395fde197208f6c` |
| Ahead/behind | `0/0` |

### 3.2 Production checkout

| Item | Observed value |
| --- | --- |
| Runtime path | `/opt/efa-os` |
| Branch | `main` |
| HEAD | `87b442e9a1ae16d256101b0bf48f0c142c5d447d` |
| Production local `origin/main` | `87b442e9a1ae16d256101b0bf48f0c142c5d447d` |
| GitHub `main` | `6ee1711a2b61f86e8315721cf395fde197208f6c` |
| Ahead/behind against GitHub | `0/35` |
| Changed paths between base and canonical source | `80` |
| Modified tracked runtime files | `8` |
| Untracked runtime files | `5` |

The production-local remote-tracking ref is stale. It must not be treated as
the current GitHub state during recovery planning.

### 3.3 Post-observation repository advance

After the production snapshot and draft evidence collection were complete,
local/GitHub `main` advanced by one documentation commit to
`f1c1576ef0895fda03b30f1e769bc27deccddc5a` (`docs: add official Ozon unit
economics reference`). It is a direct child of `6ee1711a...` and is not the
audited production source target. The later repository commit is
documentation-only and does not supersede `6ee1711a` as the audited runtime
recovery source. This manifest remains deliberately pinned to the user-approved
canonical recovery source `6ee1711a...`; the later commit must not be silently
incorporated into an exact recovery.

## 4. Host runtime overlay manifest

Every runtime blob below exists in the canonical source tree. No file is a
mixed-hunk or unknown-content runtime file.

| Path | Runtime SHA-256 | Git blob | Source commit | Base status | Runtime consumer | Observed deployment time (UTC) | Backup/recovery source | Rollback confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Scripts/ai_analyst_v1.py` | `23b66b842b515eff6142078ac213d439da3dde4b3ff05e7646faa8ae1201fd1e` | `fe3b6a5c7e4f421359e6b7cdcee1a2b3fa6d0913` | `10e95e050b0ffc263c0a362926a6d394601ba804` | Modified tracked | AI Analyst cron | `2026-08-28T07:00` | `/var/backups/efa-os/competitor-daily-report-v1-20260828T065450Z/` and Git | HIGH |
| `Scripts/format_ai_analyst_email.py` | `f7843e83342d4a9e2312a25c20dbb0e0290135c2e3e68088cbfc1d02b01f2bb1` | `426f3140825c897c9aad7d767b342414b2b2fb55` | `10e95e050b0ffc263c0a362926a6d394601ba804` | Modified tracked | Email formatter and Control Center import | `2026-08-28T07:00` | `/var/backups/efa-os/competitor-daily-report-v1-20260828T065450Z/` and Git | HIGH |
| `config/ozon_price_calculator_v1.json` | `4b9db073d72936548206a78ac06e37b3247043d19f075e9acafc560d605b9017` | `de3ad7de51166e5264507cf2d85573a634b0e65c` | `d3adbebd2add9270b51b0b2efd945f317f414e34` | Modified tracked | Recommendation Tool read-only bind | `2026-08-29T06:08:31` | `/var/backups/efa-os/ozon-price-calculator-v1-pre-tariff-20260828-20260829-060811.json` and Git | HIGH |
| `services/commercial_baseline_collector/normalization.py` | `734cbc627f14e5eca541448685e76cbe9c0a737941080ba65b43c6bb26f5a5c4` | `1b97d4130205ac9c3d0b5bd1db30beca96ac3119` | `8c70d29a91d56d2abc95b7ab16b10617bcf0c882` | Modified tracked | Commercial Baseline Collector host and container writable layer | `2026-08-30T15:30:38` | `/var/backups/efa-os/cpc-normalizer-20260830T152644Z/` and Git | MEDIUM |
| `services/control-center/app.py` | `e6b29be7917a3f7298baf36c21d734f0f48ec58501abec54763bcc49a423451b` | `ec36ba2fb8528d65d96e6719602abc0f6cef9ba7` | `6ee1711a2b61f86e8315721cf395fde197208f6c` | Modified tracked | `efa-control-center.service` | `2026-09-01T19:10:45` | `/var/backups/efa-os/control-center-capabilities-pre-6ee1711/` and Git | HIGH |
| `services/control-center/static/app.js` | `a001f3b4aa188eebf075bb032bf06b8befef28e1355c56c293b0623c66aaca30` | `f7261ccd5613cf7483953d31462d8d036ef77f77` | `09f3353574e469fdbf3f24f9d2253fdb4c660e2d` | Modified tracked | Control Center browser UI | `2026-08-28T05:47:22` | `/var/backups/efa-os/control-center-20260828-054722/` and Git | HIGH |
| `services/control-center/static/index.html` | `3bd14d6584f20de81f7105ec740e4ebd8c96a8ac52e1e54a38e90ea0a3783d6c` | `8a45876c9412c91ad4e05820e627be677a70180b` | `6ee1711a2b61f86e8315721cf395fde197208f6c` | Modified tracked | Control Center browser UI | `2026-09-01T19:10:45` | `/var/backups/efa-os/control-center-capabilities-pre-6ee1711/` and Git | HIGH |
| `services/control-center/static/styles.css` | `ba4cd123e2a8274df154a5d1fd0cf9e7a4b646119e6f8fa6612c2b1a8d57d052` | `ab49f62930085747c91ddb5050b23eb1a588dad8` | `6ee1711a2b61f86e8315721cf395fde197208f6c` | Modified tracked | Control Center browser UI | `2026-09-01T19:10:45` | `/var/backups/efa-os/control-center-capabilities-pre-6ee1711/` and Git | HIGH |
| `Scripts/build_competitor_monitor_summary_v1.py` | `a68276b0492ec03a616bfa3b53b400d295c2c27809da3c52ed82f0005f8b630f` | `a88b89577ed62c7a096576fc71e577f316375958` | `4d2000cd6b75a7135b7e5e9a3d89ee173866d701` | Untracked at base | Control Center and competitor report | `2026-08-30T15:56:31` | `/var/backups/efa-os/summary-oem-context-20260830T155529Z/` and Git | HIGH |
| `Scripts/competitor_report_v1.py` | `ff6b827ae9af37b5b804f55f754569158f48518303f48a3fe1b2971760071e83` | `172ac62d7d0e3684572e7077ca11210c04fbd943` | `10e95e050b0ffc263c0a362926a6d394601ba804` | Untracked at base | Analyst and formatter imports | `2026-08-28T07:00` | `/var/backups/efa-os/competitor-daily-report-v1-20260828T065450Z/` and Git | HIGH |
| `services/control-center/static/capabilities.html` | `9f7834d955f83ff6be0e8ff15139579cff32c4516fdeadacc6b6dce808d135fd` | `271b852faccdae9ed6fd36dbe9a92ef96d598d21` | `6ee1711a2b61f86e8315721cf395fde197208f6c` | Untracked at base | Control Center `/capabilities` | `2026-09-01T19:10:45` | Pre-state recorded as absent in `/var/backups/efa-os/control-center-capabilities-pre-6ee1711/` and Git | HIGH |
| `services/control-center/static/capabilities.js` | `bf252146406f4a3cd8c2e46ac6d0dfe5af107eb5b9b827431a63f43e88ef1b16` | `9b9217f0fda44c949ead7db80fccc8aba343502f` | `6ee1711a2b61f86e8315721cf395fde197208f6c` | Untracked at base | Capabilities browser UI | `2026-09-01T19:10:45` | Pre-state recorded as absent in `/var/backups/efa-os/control-center-capabilities-pre-6ee1711/` and Git | HIGH |
| `services/control-center/static/capabilities.json` | `6ddae0bbd3b3660a2bf951aff2cb460eafc562fba6be6c044a92b27496bcaf6a` | `03fa4379941aba7c82eb02ced9a2fb8b69336bdb` | `6ee1711a2b61f86e8315721cf395fde197208f6c` | Untracked at base | Capabilities static snapshot | `2026-09-01T19:10:45` | Pre-state recorded as absent in `/var/backups/efa-os/control-center-capabilities-pre-6ee1711/` and Git | HIGH |

## 5. Service manifest

| Logical component | Runtime type | Runtime identity / entrypoint | Working directory | Port / health evidence | Dependencies | Relevant runtime files | Provenance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Control Center | systemd | `efa-control-center.service` → `/opt/efa-control-center/.venv/bin/python /opt/efa-os/services/control-center/app.py` | `/opt/efa-os` | Loopback `8090`; `/` and `/capabilities` returned HTTP 200 | PostgreSQL, n8n TCP, EFA Read MCP TCP, report file, Caddy | Control Center overlays, formatter, competitor summary builder | Host files equal canonical Git blobs; active unit is not Git-backed |
| AI Analyst | cron + one-shot Docker | `docker run ... efa-read-mcp:41d5487 ... /repo/Scripts/ai_analyst_v1.py` | Host `/opt/efa-os` mounted as `/repo:ro` | No service port; output `/var/log/efa-os/ai-analyst-latest.txt` | PostgreSQL read credential, EFA Read Python image, competitor read views | Analyst, competitor report, summary builder | Host files from canonical main; Python runtime image from `41d5487` |
| Email formatter | cron | `/usr/bin/python3 /opt/efa-os/Scripts/format_ai_analyst_email.py` | `/opt/efa-os` | Posts to local n8n webhook on `127.0.0.1:5678` | Analyst report file, n8n, Gmail/Telegram credentials inside n8n | Formatter, competitor report, summary builder | Host files from canonical main |
| EFA Read MCP | Docker | Container `efa-read-mcp`, entrypoint `python -m efa_read_mcp` | `/app` | `127.0.0.1:8000`; no dedicated Docker healthcheck; externally routed through Caddy `/mcp` | PostgreSQL, protected env file, `efa-tools` network, Caddy | Code baked in image | Nine checked Python files equal commit `41d54877ee64a5c013c7d3d5ac7e9aceb8453441`; no writable drift |
| Recommendation Tool | Docker | Container `efa-os-efa-recommendation-tool-1`, command `python server.py` | `/app` | Internal `efa-tools:8080`; no dedicated Docker healthcheck | PostgreSQL, Calculator config, Tax Engine bind | Image code, Calculator config, Tax Engine | Image code equals `501ad53ba45cdf81ff0fe3517d42340886bf70a2`; newer config from `d3adbeb`; `IMAGE + NEWER_BIND_MOUNTED_CONFIG` |
| Commercial Baseline Collector | Docker | Container `efa-os-efa-commercial-baseline-collector-1`, command `python server.py` | `/app` | Internal `efa-tools:8080`; no published host port or Docker healthcheck | PostgreSQL, n8n workflows, protected collectors env | Baked collector code plus `/app/normalization.py` | Base image code equals `87b442e`; normalization equals `8c70d29`; `WRITABLE_CODE_LAYER_PRESENT` |
| Promotions Collector | Docker | Container `efa-os-efa-promotions-collector-1`, command `python server.py` | `/app` | Internal `efa-tools:8080`; no published host port or Docker healthcheck | PostgreSQL, n8n workflow, protected collectors env | Baked collector code | Checked files equal production base `87b442e` |
| n8n | Docker + persistent volume | Container `efa-n8n`, image entrypoint `/docker-entrypoint.sh` | `/home/node` | Published `5678`; `/healthz` returned HTTP 200 | `n8n_data`, `/var/lib/efa-os/n8n-files`, protected env, `efa-tools` | Custom Performance API image and SQLite workflow/credential state | Image version 2.32.7; exact persistent state required |
| PostgreSQL | Docker + persistent volume | Container `efa-postgres`, command `postgres` | Image default | `127.0.0.1:5432`; PostgreSQL 16.14 | `efa_pgdata`, protected runtime env | Database files and observed schema | Exact upstream image digest known; schema state fingerprinted; migration history incomplete |
| Caddy | systemd | `caddy.service` → `/usr/bin/caddy run --environ --config /etc/caddy/Caddyfile` | System default | Public HTTP/HTTPS; reverse proxies MCP and Control Center | EFA Read MCP, Control Center, protected authentication material | `/etc/caddy/Caddyfile` | Active production config is not Git-backed |

## 6. Docker image manifest

All listed containers were `running` at the observation snapshot. None had a
Docker-native healthcheck configured.

Persistent-state classifications:

- n8n: `PERSISTENT_STATE_REQUIRED`.
- PostgreSQL: `PERSISTENT_STATE_REQUIRED`.

| Container | Image/tag | Image ID and immutable digest | Image created / container created | Code provenance | Mounts/state | Writable code drift | Recreation confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `efa-os-efa-recommendation-tool-1` | `efa-recommendation-tool:501ad53`; local latest alias | `sha256:c4b9034f3ed52d2da2ca19bf261b34f7b6cb46b5d0e5a58880aa94932b5e9afb` | Image `2026-08-29T08:57:29.919502924Z`; container `2026-08-29T08:59:56.384246347Z` | Checked image files equal `501ad53ba45cdf81ff0fe3517d42340886bf70a2` | Read-only binds: Calculator config, `taxpayer.2026.json`, Tax Engine directory | None in baked code; configuration is newer bind-mounted content | MEDIUM |
| `efa-read-mcp` | `efa-read-mcp:41d5487` | `sha256:93d36cb7f4b47c42d93356ccb949f0a9808f2e68edb414bfa6610ee3b43a2ce1` | Image `2026-08-21T08:37:07.791475584Z`; container `2026-08-23T20:57:52.865278127Z` | Exact checked code at `41d54877ee64a5c013c7d3d5ac7e9aceb8453441` | No mounts | None; `docker diff` empty | HIGH if image digest remains available; MEDIUM for rebuild |
| `efa-os-efa-commercial-baseline-collector-1` | `efa-os-efa-commercial-baseline-collector:latest` | `sha256:45df13a816ef2a09830d787681130725deab524da030a2e1d3da173c3623bb9b` | Image `2026-08-23T17:16:55.890441003Z`; container `2026-08-23T17:16:56.303996754Z` | Baked files at `87b442e`; one file at `8c70d29` | No host source mount | `WRITABLE_CODE_LAYER_PRESENT`: `/app/normalization.py` | LOW for exact layer recreation; HIGH for source recovery |
| `efa-n8n` | `efa-n8n-performance:0.1.0` | `sha256:00b2288cfaa14e18b0ec35d132644417691349b564f248faaca7f8eb805c4e9a` | Image `2026-08-19T04:27:34.786037918Z`; container `2026-08-21T11:54:56.680147775Z` | n8n 2.32.7 plus repository custom extension; no application revision label | `n8n_data` and `/var/lib/efa-os/n8n-files` | Runtime state in persistent volume | MEDIUM for image; LOW for exact current full state |
| `efa-os-efa-promotions-collector-1` | `efa-os-efa-promotions-collector:latest` | `sha256:8fec3ca988db3e577d2f055e2248963c48d4adc2a916b814eb7521f02cc4b918` | Image `2026-08-21T11:49:02.801528254Z`; container `2026-08-21T11:49:04.326370520Z` | Checked files at `87b442e` | No mounts | None observed | MEDIUM |
| `efa-postgres` | `postgres:16@sha256:33f923b05f64ca54ac4401c01126a6b92afe839a0aa0a52bc5aeb5cc958e5f20` | `sha256:33f923b05f64ca54ac4401c01126a6b92afe839a0aa0a52bc5aeb5cc958e5f20` | Image `2026-07-16T22:06:30.006861271Z`; container `2026-08-21T08:25:06.651676330Z` | Upstream PostgreSQL image | `efa_pgdata` | Persistent database state | HIGH for image; MEDIUM for data recovery |

## 7. Storage and volume manifest

| Storage path / volume | Purpose | Recovery required | Observed backup status | Restore confidence |
| --- | --- | --- | --- | --- |
| Docker volume `efa_pgdata` → `/var/lib/docker/volumes/efa_pgdata/_data` | PostgreSQL cluster data | YES | No raw-volume copy observed; 19 custom-format PostgreSQL dumps exist, latest `2026-08-31T21:02:27Z` | MEDIUM |
| Docker volume `n8n_data` → `/var/lib/docker/volumes/n8n_data/_data` | n8n SQLite database, workflow state, encrypted credentials and settings | YES | No full volume or `database.sqlite` backup found under `/var/backups/efa-os` | LOW |
| `/var/lib/efa-os/n8n-files` → `/files` | n8n local file exchange | CONDITIONAL/YES for exact state | No dedicated backup found | LOW |
| `/opt/efa-os` | Production source checkout and host overlays | YES | All 13 overlay bytes exist in canonical Git; pre-change component backups also exist | HIGH for source; MEDIUM for exact dirty-layout reconstruction |
| `/opt/efa-os/config/ozon_price_calculator_v1.json` | Recommendation Tool Calculator config | YES | Git and pre-tariff file backup | HIGH |
| `/opt/efa-os/config/taxpayer.2026.json` | Tax Engine config | YES | Git-backed path; exact recovery still depends on source checkout and review | HIGH |
| `/opt/efa-os/services/tax_engine` | Recommendation Tool Tax Engine code | YES | Git-backed, bind-mounted read-only | HIGH |
| `/var/log/efa-os` | Latest Analyst report and delivery logs | NO for core restore; YES for exact operational continuity/evidence | Historical copies exist for some deployments; no complete directory backup observed | MEDIUM |
| `/var/backups/efa-os` | Production pre-change files, manifests and PostgreSQL dumps | YES | Primary observed recovery evidence directory | MEDIUM; no full end-to-end restore observed |
| `/etc/efa-os` | Protected runtime environment and authentication material | YES | No export or value-level backup inspected; must be recovered through approved encrypted secret handling | LOW unless separately protected |

### 7.1 Protected secret locations

The following names and locations are recovery dependencies. Their contents
are intentionally absent from this manifest:

- `/etc/efa-os/runtime.env`
- `/etc/efa-os/n8n.env`
- `/etc/efa-os/collectors.env`
- `/etc/efa-os/ai-analyst.env`
- `/etc/efa-os/efa-read-mcp.env`
- `/etc/efa-os/mcp-bearer.env`
- `/etc/efa-os/control-center/database.env`
- `/etc/efa-os/control-center/basic-auth.hash`
- `/etc/efa-os/control-center/basic-auth.secret`
- `/etc/efa-os/n8n-postgres-credential-backup.json`

All observed protected files were owned by root and had mode `0600`. Secret
values must be restored from separately approved encrypted storage or manually
recreated/re-authorized. They must never be placed in Git or this manifest.

## 8. systemd manifest

### 8.1 `efa-control-center.service`

Classification: `ACTIVE_PRODUCTION_CONFIG_NOT_GIT_BACKED`

| Property | Observed value |
| --- | --- |
| Unit path | `/etc/systemd/system/efa-control-center.service` |
| SHA-256 | `38c2cccbef11446c27e4fd81cdb3f3d7d041bffc8249d24bba31c216e827591f` |
| Git blob calculated from active bytes | `ba6afd5d5d938d72ae1d10c736594d940ab2d524` |
| Exact blob in Git history | Not found |
| User/group | `efa-control-center` / `efa-control-center` |
| WorkingDirectory | `/opt/efa-os` |
| ExecStart | `/opt/efa-control-center/.venv/bin/python /opt/efa-os/services/control-center/app.py` |
| Environment file | `/etc/efa-os/control-center/database.env` — contents excluded |
| Restart policy | `on-failure`, `RestartSec=3` |
| Dependencies | `network-online.target`, `docker.service` |
| Hardening | `NoNewPrivileges`, private tmp, strict filesystem protection, read-only runtime paths |
| Observed service state | active/running |

Git contains `deployment/control-center/efa-control-center.service.example`,
but its blob differs from the active production unit. The active bytes must be
captured through an approved, sanitized configuration reconciliation before a
high-confidence full recovery is possible.

### 8.2 Other relevant active units

| Unit | Role | Provenance |
| --- | --- | --- |
| `caddy.service` | Public reverse proxy and authentication boundary | Distribution unit plus production-local config/drop-in |
| `docker.service` | Container runtime | Distribution unit |

No active EFA systemd timers were observed.

## 9. Caddy manifest

Classification: `ACTIVE_PRODUCTION_CONFIG_NOT_GIT_BACKED`

| Property | Observed value |
| --- | --- |
| Config path | `/etc/caddy/Caddyfile` |
| SHA-256 | `55e5b4a47d412706493f244856ffc8085df5f2d5697da29445e93abb3be635c1` |
| Service | `caddy.service`, active/running |
| MCP route | `mcp.efa-os.ru` → `127.0.0.1:8000` |
| Control Center route | `panel.efa-os.ru` → `127.0.0.1:8090` |
| Authentication role | Caddy is the public authentication boundary for MCP bearer access and Control Center Basic Auth |
| Protected authentication storage | `/etc/efa-os/mcp-bearer.env` and protected Control Center Basic Auth material; values excluded |
| Git provenance | Exact active config blob not established in Git; repository example exists but is not the active file |

## 10. Cron manifest

| Property | Value |
| --- | --- |
| Active file | `/etc/cron.d/efa-os-analytics` |
| SHA-256 | `94ad509ac5ed098c71831d0384312aa99a5d900f09bd9bf987333c0558d87494` |
| Git blob | `192df42ef3e6b4a4b97786154749e1e083e0edf4` |
| Source commit | `79a8f73178175c74cf221c4be745592dd2d503c1` |
| Source status | Exact Git match |
| Server timezone | UTC; comments map schedules to Europe/Moscow |

| Schedule Europe/Moscow | Job | Dependencies and recovery note |
| --- | --- | --- |
| `06:00` daily | Execute n8n workflow `B2DiIq630Yb2fXR8` for Phase A baseline refresh | Temporarily stops/restarts n8n around CLI execution; restore only after single-production ownership is confirmed |
| `16:00` daily | Generate AI Analyst report | Requires image `efa-read-mcp:41d5487`, host overlays, PostgreSQL read credential, `efa-tools`, log directory |
| `16:30` daily | Format and deliver Analyst payload through local n8n webhook | Requires report file, formatter overlays, active `EFAANALYSTEMAIL`, Gmail/Telegram runtime credentials |

No additional active EFA cron job or systemd timer was observed. The file
`/etc/cron.d/efa-os-analytics.pre-v13` is historical evidence and is not an
active `/etc/cron.d` schedule because its name contains a dot.

## 11. n8n workflow manifest

The n8n runtime contained 7 active and 18 inactive workflows. Nine workflows
have canonical tracked JSON files. The remaining inactive records are legacy
or test runtime records and are not recovery sources.

Structural match comparison excludes secret values while preserving workflow
logic, connections, schedules and non-secret settings.

| Workflow ID / name | Runtime state | Runtime version ID | Tracked source / blob | Source commit | Match and runtime-only state |
| --- | --- | --- | --- | --- | --- |
| `CPCDAILYV1` — CPC Daily Collection v1 | Active | `33f7dace-c840-4cca-83df-46fbc3c80ead` | `n8n/workflows/CPC_Daily_Collection.json`; blob `cb044d7e3ee56606640751477bf8c7186c875716` | `a2bf1f4b996c61ad2a0d039da8107ef60b32239c` | Exact structural match |
| `CPCREPORTPOLLERV1` — CPC Report Poller v1 | Active | `8edbfea5-9080-4ccb-9f5b-4ff7762de4c9` | `n8n/workflows/CPC_Report_Poller_v1.json`; blob `a8496351f857ab42a5c3034cec45eeabadeddeb6` | `b4688e879f63200bf7cb6ad57256348687f1191c` | Exact structural match; tracked/runtime `active=true`; stale test expects `false`; `CPC_LIFECYCLE_CONTRACT_REVIEW_REQUIRED` |
| `EFAANALYSTEMAIL` — EFA AI Analyst Email | Active | `b6963782-e346-4e11-a15b-453b8674538d` | `n8n/workflows/EFA_AI_Analyst_Delivery_v1.json`; blob `fbf8e16d2838f7a61cd341a72ab758e7b319e474` | `79a8f73178175c74cf221c4be745592dd2d503c1` | Expected production credential bindings and destination payload differ from sanitized Git; no secret values recorded |
| `OPFINDAILYV1` — Operational Finance Daily | Active | `bfa95acf-24cb-4769-b7a5-1dd1ec350d6c` | `n8n/workflows/Ozon_Operational_Finance_Daily_Collection_v1.json`; blob `4adf66608fee4175799194f877578ccbf0cc7ab3` | `fc3a229475682f1c7034c75834e8737e5d739c5a` | Exact structural match |
| `nw3DytLJdwTieOgJ` — Price Snapshot | Active | `b8df6c1e-a840-424d-a387-c4be73a0dbb9` | `n8n/workflows/Ozon_Price_Snapshot_Automation.json`; blob `8492614e60e403796c0a0f61616df16f2d9c9ca3` | `6bee0782896c18e66af368529fb10bf14cd06184` | Exact structural match |
| `PROMOAUTOV1` — Promotions Snapshot | Active | `7ebed766-aec4-4f5a-8669-75414d73115d` | `n8n/workflows/Promotion_Snapshot_Automation.json`; blob `4d3805d74383808448734ad01608a2b59a5d54e2` | `20e0404bd783350b041e3225a93da5d018bc533b` | Exact structural match |
| `SELLERDAILYV1` — Seller Analytics Daily | Active | `83590742-8a74-413e-8d3f-c462ffd39709` | `n8n/workflows/Seller_Analytics_Daily_Collection.json`; blob `7b001a0aa8bdc2363f4d2ea60852a157829fd404` | `20e0404bd783350b041e3225a93da5d018bc533b` | Runtime adds `retryOnFail` and `waitBetweenTries`; source reconciliation required |
| `B2DiIq630Yb2fXR8` — Phase A GitHub baseline | Inactive | `312bb217-6c9c-486f-a16a-cceee579ba99` | `n8n/workflows/OZON_workflow_Phase_A.json`; blob `f50899bbd84673c8ecddb100d09001c269f012eb` | `b2e360c5b38ad7c3b98c87d39c3f882d377d5fb2` | Exact structural match; executed by host cron through CLI while inactive |
| `Kf241Y5kzETghygL` — old Daily Commercial Brief Delivery | Inactive | `ffb86eee-a4a0-49ba-96ca-5e1075da3596` | `n8n/workflows/Ozon_Daily_Commercial_Brief_Delivery_v1.json`; blob `8bc5b62afd0c132f18f5cf596caa587f6ddc5257` | `96ccaf948c18367c4d0acfa3fe014bb47a5c8be9` | Significant historical structural drift; must remain inactive pending separate review |

### 11.1 n8n recovery boundary

Tracked JSON restores sanitized workflow logic, not production credential
bindings, version history, execution history, owners/projects, encryption keys,
or current active runtime state. Exact recovery requires the protected
`n8n_data` volume and the matching n8n encryption context. No complete current
volume backup was observed.

## 12. Database manifest

Classification: `OBSERVED_SCHEMA_STATE_WITHOUT_COMPLETE_MIGRATION_LEDGER`

| Property | Observed value |
| --- | --- |
| Container | `efa-postgres` |
| PostgreSQL version | `16.14 (Debian 16.14-1.pgdg13+1)` |
| Application database | `efa` |
| Application schemas fingerprinted | `public`, `mcp_read` |
| Application tables | `44` |
| Application views | `32` — 18 `public`, 14 `mcp_read` |
| Application functions | `1` — `mcp_read.product_period_economics(date,date)` |
| Fingerprinted schemas | `2` |
| Total fingerprint objects | `79` |
| Migration ledger | Not found |
| Read evidence | Audit query executed inside an explicit read-only transaction; no business rows were read |

Key observed roles:

- `efa_mcp_readonly`: login role, non-superuser.
- `efa_mcp_reader`: non-login read capability role, non-superuser.
- `efa_competitor_writer`: login role, non-superuser, no role/database creation capability.

Observed structures demonstrate capabilities associated with migrations
001–018 and 021–026. Seed effects from migrations 019 and 020 are not proven
by this schema-only fingerprint. The observed presence of later objects does
not prove the exact execution order or exclude manual DDL.

### 12.1 Schema fingerprint method

Fingerprint version: `EFA_SCHEMA_FINGERPRINT_V1`.

For tables, the canonical definition includes owner, ACL, ordered columns,
types, nullability, defaults, constraints and indexes. For views and functions,
it includes owner, ACL and PostgreSQL canonical definition. Extension-owned
functions are excluded. No table rows or business values are included.

Aggregate fingerprint:

`1e010b170999ff9875d52aa23f33415c921eb81c3c1688c2e6c78aca4f9319a1`

Canonical ordered object fingerprints:

```text
mcp_read|FUNCTION|product_period_economics(p_from_date date, p_to_date date)|fdc02f3fbdf5d18af95f2f472234570d8a720e4b296b706d828deed27eaec08f
mcp_read|SCHEMA|mcp_read|7d7b3c158f18d81662a6e28ab101c323f916025bc2538d1d159911e5741afa97
mcp_read|VIEW|competitor_finding_sets_reconciliation|d2ace0da43d3b29db0244c6b1c8a6313d0e2064e0c6cfb7848ead747c7709491
mcp_read|VIEW|competitor_findings|b3da1274e06d5aa8eb7d4b4687d0bfd8721d47c77971252ac5a915cf17c2a6d2
mcp_read|VIEW|competitor_latest_finding_set|7df290c234e6dab1778c06ad9c845b704ca860debe5b66307316546bba943288
mcp_read|VIEW|competitor_monitoring_coverage|480f75571c787b75657af17c55cf3e5878b2b87231072477b2f1c2bb20068382
mcp_read|VIEW|competitor_reference_plan_source|774d63ece0c515fc74b6c5bcab862bfaec7b615cd97191acc044da15fc645111
mcp_read|VIEW|competitor_snapshot_observations|09ebe423ac52c6e97215949038accaed4400e31eb303cf83806766d60ce0dbac
mcp_read|VIEW|competitor_snapshot_runs|8e68e4134e4a5f84f3eb60329ec50b58e342dffed40c71a6c77b735993340972
mcp_read|VIEW|product_cpc_daily|f09e0b892d9a9cb2ce9f2dbc22011b6a6478a6cbdd9feb48cbbda2db09747a4c
mcp_read|VIEW|product_daily_performance|dd6008a8a0336e982a4d9e17106e592f4a219ddd5b64ee8c32f09d8964f66569
mcp_read|VIEW|product_overview|233564039b5574f7dd1faf74d38b763a93a9ad2a16c44a859dbccc28de205494
mcp_read|VIEW|product_price_history|711fe45b5d972f6eda16d721669d65a4b159d856126af85d518cb884c8edc3f7
mcp_read|VIEW|product_promotion_state|c43b9d7357a01f9418479ba0535aab283062961caf8a7b61eb35e988632f42f5
mcp_read|VIEW|product_region_logistics|fef77756ff4d73a41f5e84b654cf994d1bc98f1e58ecf914ad9fd9b360d2dcd2
mcp_read|VIEW|product_stock_history|57fecf92d093b52cb4548b40f5441a295913612615647dc5eff1808198ac2fc2
public|SCHEMA|public|63fb77a4f87e6f76a3960ac0aa8af36bce117f31fc0f960a4c5720732445ec87
public|TABLE|cash_flow|8f76e435347854c240c4132908edd573b50f1f678b479b2ed19e08e0db789ddc
public|TABLE|change_events|2298c4da3332174719ddcb00e24ca07be9beeb203f061bbab5ffe871f993742d
public|TABLE|commercial_experiments|7896dc3aeae8dc45b03b0ac62d0a772ab42832c0c5a679832b2f6a8b2f9e2d89
public|TABLE|commissions|d9ee6dd9d23e9f50c7ab876af2ee071797bcfd371eabc4c1de6c1f1e889e773e
public|TABLE|competitor_finding_sets|f5378499e1a6138abf81f64b7825117dbde1035694a4d84e03e629e979112d5e
public|TABLE|competitor_findings|e65d2f21cd74cd72b9cd7708a291b883158c621e6703567837018a1d5539cc13
public|TABLE|competitor_listings|3062ffcf46e4b1d10ad0ec3cf76d7dfde3c124731a154e46480bfd8c3930e564
public|TABLE|competitor_observations|51df46374eef33dfa984651847f38096cdd4c34eceb08403f6c7478afbc52f57
public|TABLE|competitor_product_families|1ffc5fc5c4d8ca96a9c0a73157fae79ffb0bbfc2a6ad0039ccdc0af26b716232
public|TABLE|competitor_reviews|3d1463cb78a5cdf129c25fd34ca077591eebd0071b129f7e8134362ecaf838e9
public|TABLE|competitor_search_runs|d5a55d1adbf674499ac03ec5ed104651a590e40f25d43660f9f05cd881965d0c
public|TABLE|competitor_sku_oems|3e934c354c3ec006a9296223136fe6920ac9b379497b655b6facb94e35efc3c8
public|TABLE|competitor_sku_profiles|c708f6d11f52dd502c7163a1dbedc6361f3b9f0702c87b6b9db9037b5d479a9e
public|TABLE|competitor_watchlist_memberships|a3c1781a3731dc629e975c20adf9201d601ee12a3072dc23bccdec32e7d418a6
public|TABLE|cpc_advertising_daily|af456c8eae61979187e215c59e11f03df480faef6d08a37a4d817a12e5461831
public|TABLE|cpc_collection_runs|53dd756a55a445f42aeb675849b10d43737d624ea07cb83780d603100d312b2a
public|TABLE|fbs_expenses|030b1bd28bdda0c6cd10f24f97ffa32f586dc73fe0e7033c4bb8cf04e52dfab4
public|TABLE|finance_operations|8295be24f536a73c413e9c08c096449833a5e66862270816a734298e5a9f73b4
public|TABLE|information_change_events|2304157334a2aa33dce52e8587f0c2791a15c204d5b0d682d0c2ab60d1673b23
public|TABLE|information_source_checks|f97a22d30dcb1cd1db937bc9620d6a7746efe75105d1e44a6d8887eb6e5fcb67
public|TABLE|information_source_snapshots|f6ef12b66ff102430b6b5a8833928444ffc48bb80894374a4c735ab7a2c631d2
public|TABLE|information_sources|f4b417b2908aec6ee75ed395502b67a80bcb9fbbe6821d7ad28ddf668ab8768b
public|TABLE|operational_collection_runs|d4f3ef059a34dbfa56e631d15e4b612fd4a1266be3f09aff2c04e2f839c9cd8f
public|TABLE|order_finance|1ff8794bf741275512137b57b13e78a3d3af5f6d85855dc02200974932590063
public|TABLE|ozon_fbs_tariff_snapshots|9f4699676a4ecfeb8fd05c916a436d670c6a3119bedccafbecf5f3489b3bc851
public|TABLE|ozon_price_history|b67ddde3f1565c8012f8a1a627b51fc9ef32fd3f87b50cbaa9e6c978d7212ceb
public|TABLE|ozon_prices|32f71c498a22c642bbd36e9e516c031a29a4670a328a66ee90393f02bb1ea0e8
public|TABLE|posting_logistics|fb14214e619273cc48ae10304eb2ff1aeb9c6c497d75241cf0b572557a03a70e
public|TABLE|postings|70fdb8111ed37104f4b755a2056363800304eae92c1b742e9de701563473c7f6
public|TABLE|price_collection_runs|d05c4d96dbe49d5e95b9928a873132c5b2327ec26a57f85e9f61c6dc77ea8473
public|TABLE|prices|e87f42c65609b6d754be32173cc297d3eff0ec9ff67b8f3b92ff4b9e97bfbb4d
public|TABLE|product_snapshots|3d27051e2ffb92562b49f3f674d385b4a1e8400fe0966a687628010facb2b46f
public|TABLE|products|eca46dada526ecc716c5f0795c51b82b89066f130eccfe334d6fbc82bac5f0a3
public|TABLE|promotion_runs|0a23fdcf9db5349743ee4a0161bd77a00d4fe78bd2da5963883a64073ddd0b43
public|TABLE|promotion_snapshots|2bd3f4e2dae161345e48ee14d9083591ee5067f8c2b3276962189d9e18b0fab2
public|TABLE|returns|a10cce8672070b1883d07f14903144b0557be798177001e9f7462203b2022b14
public|TABLE|sales|2b0b85a60b2becbe989d37c3aa2206977c15a9aeed60966f75bfe89cf2848a5c
public|TABLE|seller_product_demand_daily|e8e76dd5700aee16ce4a08d8173c4bf61e0c10b2055469499c920a3bde029239
public|TABLE|snapshot_runs|efcd6ba33d4f66f7dcd9b358587b129ca9997f77d98629fc698cc21058bc7638
public|TABLE|stock_history|46d9d8f694cc24d33f82f1868fd3592ad2b6e42ae2c933cc660ebce2afd69e10
public|TABLE|stocks|5fbbae7c7a515e46362ff5808aa08d93bfcfe4cd0e44ff3cb6e034c3722637ed
public|TABLE|tax_revenue_events|68ede7a9fd18fe3eb252cf5f92856127b2f680218be802ece6561e245b8f59bd
public|TABLE|tax_revenue_import_runs|e0b96d359bd7ed37935f4af6b5d9c37e9f0c02b0ec479baabc08f84b8c0fb82d
public|VIEW|sales_analytics|01cf38feb156849bd787c4c9024d60c2a8506101f4466f1ae64466a019332eb0
public|VIEW|vw_orders_finance_final|ec430c667af7e9c893e63f06a585a198a71f565d1668bc17fa7aa29f7b306b44
public|VIEW|vw_orders_finance_normalized|11d574331cd02752c14112e1c01737f6384228ecbc87c43cc694fad18da18493
public|VIEW|vw_orders_finance_raw|a78db4ed9839182412c73dd169d4c7c90ecf33d9d3b920edfad9b502ad440000
public|VIEW|vw_orders_finance_summary|fa29c914069748d905c28436012e7d01ba468234ca3840c44edda7fa377b83e6
public|VIEW|vw_orders_finance|d44f510cf2c8c694a0d9d6624dafa2a27559bd29ce0b98bb07559aac137c9b36
public|VIEW|vw_orders_profit_final|1a28f9b8bf3605204f9a25c7e0bcb1908bf1e6e429165639262e4af217358569
public|VIEW|vw_orders_profit|4ca375eb80414254a5d23be214cd90f993977ffc8e4f87d53f5e6f9eb45f049a
public|VIEW|vw_product_alerts|742c85c1922d54b9298a557414835e0087ae1e8cf772869cc9319ce976d4df2e
public|VIEW|vw_product_analytics|5db6318ad0e3cbc0e3a05af8847fcf82c969b4c4b003d24b69f2e139285ec79f
public|VIEW|vw_product_metrics|413bccf53a9700fc90ec9a15665b8a51cfcba5eada8e3241eb32ff8e0e8d47c7
public|VIEW|vw_product_region_analysis|284afd1d0542b929313749b9227f87cf13dc5c6aabeb008b719c3dbbccfcb4b6
public|VIEW|vw_product_region_logistics|08a18899f05dc5a920fa46582b0d39ed8a8953d37799da58477584a0f31c7bb5
public|VIEW|vw_product_region_summary|01afc594e5d5ab439cabce3896c954ae661816e946688474c4ddea9b27d7ae6d
public|VIEW|vw_product_stock_status|5baefe22b0872bc29cead35efb839b06260c5d4a59125fa04f26065fcd0db66b
public|VIEW|vw_sales_base|6560f1f5638891f155716bec7d3107658a28269760143ef9be48243253712b3e
public|VIEW|vw_sales|f571fcbc3c1b0ea16cef08426e6097446d59d364f1c340be3d593ddf3eea6c4d
public|VIEW|vw_stock_history_changes|35e27d1a327fbfab853b23e8557a113216f7f57fd2ad62cc793f2a840f623a95
public|VIEW|vw_stock_history_summary|faee7c7514bdc03d75dba1df8fe78b75c03997cd97e476671f302ef620d071b7
```

## 13. Backup manifest

The production backup directory contained 81 files totalling approximately
13.77 MB. Backup existence or archive/list validation is not equivalent to a
successful full restore test.

| Location / group | Component | Date / latest evidence | Purpose | Restore tested | Confidence |
| --- | --- | --- | --- | --- | --- |
| `/var/backups/efa-os/control-center-capabilities-pre-6ee1711/` | Control Center capabilities deployment | `2026-09-01T19:09:39Z` | Predeploy app/index/styles, absence record for new capability files, source commit and service state | No full restore observed | HIGH for file rollback |
| `/var/backups/efa-os/control-center-20260828-054722/` | Control Center competitor integration | `2026-08-28` | Deployment manifest and pre-change files | No full restore observed | HIGH for file rollback |
| `/var/backups/efa-os/competitor-daily-report-v1-20260828T065450Z/` | Analyst, formatter, competitor report | `2026-08-28` | Pre-change and exact deployed Git blobs | No full restore observed | HIGH for file recovery |
| `/var/backups/efa-os/summary-oem-context-20260830T155529Z/` | Competitor summary builder | `2026-08-30` | Pre-change summary implementation | No full restore observed | HIGH with Git source |
| `/var/backups/efa-os/cpc-normalizer-20260830T152644Z/` | Commercial Collector normalization | `2026-08-30` | Pre-writable-layer normalization file | No container rollback test observed | MEDIUM |
| `/var/backups/efa-os/cpc-recovery-2026-08-29-20260830T154408Z/` | CPC lifecycle/data recovery | `2026-08-30` | CPC relation dump, source execution evidence and checksums | Archive/checksum evidence exists; no full stack restore observed | MEDIUM |
| `/var/backups/efa-os/ozon-price-calculator-v1-pre-tariff-20260828-20260829-060811.json` | Calculator config | `2026-08-29` | Pre-tariff configuration | No runtime rollback test observed | HIGH for bytes |
| `/var/backups/efa-os/recommendation-price-source-20260829-20260829-080626/` | Recommendation Tool | `2026-08-29` | Pre-change source files | No image rebuild/restore test observed | MEDIUM |
| `/var/backups/efa-os/report-delivery-20260822-061301/` | n8n delivery workflows and cron | `2026-08-22` | Workflow exports and historical cron | Workflow export only; not full n8n state | MEDIUM for logic, LOW for full state |
| `/var/backups/efa-os/timeweb-n8n-OPFINDAILYV1-pre-step3-20260822-004933.json` | Operational Finance workflow | `2026-08-21` | Pre-change workflow export | No full n8n restore observed | MEDIUM |
| `/var/backups/efa-os/pre-migration-021...026*.dump` | PostgreSQL schema changes | `2026-08-25` to `2026-08-30` | Pre-migration custom-format dumps | Actual restore not observed in this audit | MEDIUM |
| `/var/backups/efa-os/pre-competitor-T3-write-20260831T210226Z.dump` | Latest observed PostgreSQL backup | `2026-08-31T21:02:27Z` | Pre-T3 production state | Actual restore not observed | MEDIUM |

Nineteen PostgreSQL custom-format dumps were observed. No full backup of the
current n8n volume or its SQLite database was found in the production backup
directory.

## 14. Recovery targets

Two targets must not be confused:

### 14.1 Exact forensic runtime target

Reconstruct `/opt/efa-os` at base `87b442e9...`, then materialize the 13 exact
overlay blobs listed in section 4. Restore the exact image IDs, writable
Commercial Collector layer, persistent data, runtime bindings and local
infrastructure configs. This best represents the observed runtime, but has the
lowest operational reproducibility.

### 14.2 Canonical clean source target

Use a clean checkout of `6ee1711a...`. This contains all 13 overlay bytes but
also includes the complete 80-path source delta from the production base. It
is the preferred source reconciliation target for a future controlled clean
rollout, but it is not the observed production checkout and requires separate
review and approval before use.

## 15. Full-loss recovery order — no execution

1. **Declare recovery target and ownership.** Confirm the old production host
   is unavailable or fully stopped. Choose exact forensic recovery or a
   separately approved clean-source recovery. Keep schedules and outbound
   delivery disabled.
2. **Provision the base host.** Recreate the supported Linux host, filesystem
   ownership, firewall/network policy, time synchronization, Docker Engine,
   Compose, Caddy, Python runtime/venv requirements and operator access.
3. **Recover protected secrets.** Restore or manually recreate the protected
   `/etc/efa-os` files using approved encrypted handling. Do not place secrets
   in source control or recovery logs.
4. **Create Docker foundations.** Recreate the external `efa-tools` network and
   named volumes `efa_pgdata` and `n8n_data`; recreate `/var/lib/efa-os/n8n-files`.
5. **Recover PostgreSQL.** Load the exact PostgreSQL image and restore the
   selected verified custom-format dump or approved volume backup. Validate
   database roles, schemas, ACLs and the schema fingerprint before consumers
   start.
6. **Recover the source tree.** For exact forensic recovery, checkout
   `87b442e9...` and materialize the exact 13 blobs without inventing a deployed
   commit. For a separately approved clean recovery, checkout `6ee1711a...` in
   a clean tree.
7. **Recover immutable images.** Load/pull the exact image digests where
   available. Do not rebuild from `latest`. If rebuilding becomes unavoidable,
   record the source commit, Dockerfile, dependency lock state and new digest,
   and classify it as a changed recovery target.
8. **Recover component configs and binds.** Recreate Compose configuration,
   bind-mounted Calculator/Tax files, protected environment references and
   required host directories. Recreate the Commercial Collector normalization
   state explicitly; do not rely on an undocumented `docker cp` step.
9. **Recover n8n state.** Prefer an exact protected `n8n_data` backup with the
   matching encryption context. If unavailable, treat restoration from
   sanitized JSON as partial: import canonical workflows inactive, bind
   credentials manually, preserve production-only destinations separately,
   and review known drift before activation.
10. **Start containers in dependency order.** PostgreSQL first; then n8n,
    collectors, EFA Read MCP and Recommendation Tool. Validate network and
    read-only dependencies before downstream activation.
11. **Restore systemd.** Recreate the service account, Python environment and
    exact reviewed Control Center unit. Start and validate the local-only
    service before exposing it through Caddy.
12. **Restore Caddy.** Recreate the reviewed Caddy config and protected
    authentication boundary. Validate loopback upstreams before public DNS or
    traffic cutover.
13. **Restore cron last.** Install the exact tracked cron only after all manual
    health checks pass and single-production ownership is confirmed.
14. **Perform provenance verification.** Compare source commit/base, all host
    file SHA-256 values, image digests, mounts, workflow versions/structure,
    schema fingerprint, unit/Caddy hashes, ports and health evidence.
15. **Enable controlled production.** Activate n8n schedules and outbound
    delivery only under a separate approval after duplicate execution risk has
    been excluded.

## 16. Recovery gaps

| Severity | Gap | Recovery consequence | Recommended fix — separate future scope |
| --- | --- | --- | --- |
| HIGH | Commercial Collector has `WRITABLE_CODE_LAYER_PRESENT` | Recreating the image alone restores the old normalizer, not the running behavior | Build a reviewed immutable image containing the Git-tracked normalizer; add revision label and digest manifest |
| HIGH | No complete current n8n state backup was found | Sanitized workflow JSON cannot restore credentials, versions, ownership, encryption context or exact runtime state | Create an approved encrypted `n8n_data` backup and perform a restore test in standby |
| HIGH | No migration ledger | Exact applied sequence and manual DDL history cannot be proven | Establish a reviewed baseline ledger from observed schema; never fabricate historical application records |
| HIGH | Protected `/etc/efa-os` recovery source was not verified | Full stack may start without credentials/authentication or may require manual reauthorization | Maintain an approved encrypted secret recovery bundle and rotation/recreation runbook |
| MEDIUM | Application images lack consistent OCI revision/build labels | Exact source-to-image reconstruction depends on tags and sampled file hashes | Add `org.opencontainers.image.revision`, source, build timestamp and dependency/build manifest |
| MEDIUM | Active Control Center unit is not Git-backed | Exact service hardening and runtime launch cannot be reconstructed from repository example alone | Sanitize and version the active unit template; preserve local secret paths only |
| MEDIUM | Active Caddy config is not Git-backed | Public routing/authentication boundary requires manual reconstruction | Store a sanitized canonical template and separately protected auth material |
| MEDIUM | PostgreSQL backups were not restore-tested in this audit | Backup files may be valid archives but full recovery remains unproven | Perform a documented standby restore and compare schema/data integrity under separate approval |
| MEDIUM | Recommendation Tool is image code plus newer bind-mounted config | Image tag alone does not represent effective runtime | Add an effective-runtime manifest covering image digest and bind hashes |
| MEDIUM | Seller Analytics n8n runtime has retry drift | Git import alone changes retry behavior | Review and reconcile `retryOnFail` and `waitBetweenTries` before canonical import |
| MEDIUM | `CPCREPORTPOLLERV1` contract assertion conflicts with runtime/tracked active state | Automated recovery could apply an unresolved policy assumption | Complete `CPC_LIFECYCLE_CONTRACT_REVIEW_REQUIRED`; do not change activation during recovery drafting |
| LOW | Old Daily Brief workflow has substantial inactive drift | Importing or activating the wrong historical record could duplicate delivery | Keep inactive and exclude it from automatic activation |

## 17. Recovery confidence

| Recovery domain | Confidence | Reason |
| --- | --- | --- |
| Source code | HIGH | All 13 host overlays have exact SHA-256, blob and commit provenance in canonical main |
| PostgreSQL image | HIGH | Exact upstream digest known |
| PostgreSQL data/schema | MEDIUM | Multiple dumps and a 79-object schema fingerprint exist; no ledger or observed full restore test |
| n8n workflow logic | MEDIUM | All canonical workflow JSON files exist; known structural/binding drift is documented |
| n8n full state | LOW | No current full volume/SQLite backup observed; credential/encryption context required |
| Container images | MEDIUM | Exact image IDs/digests known; build provenance labels are incomplete |
| Commercial Collector exact runtime | LOW | Effective code depends on writable container layer |
| systemd/Caddy infrastructure config | MEDIUM | Exact active hashes and launch/routing metadata known, but active files are not Git-backed |
| Protected secrets | LOW | Locations and permissions are known; approved recovery copies were not verified |
| Full stack | MEDIUM-LOW | Source is strong, but n8n state, secret recovery, writable image drift and migration history prevent high confidence |

## 18. Recovery validation checklist

- [ ] Recovery target and single-production ownership explicitly approved.
- [ ] Exact source base/canonical commit verified.
- [ ] All 13 host runtime SHA-256 values verified or a reviewed clean-source
      target explicitly selected.
- [ ] Exact Docker image IDs/digests available.
- [ ] Commercial Collector effective normalizer verified.
- [ ] `efa_pgdata` restored and PostgreSQL 16.14-compatible.
- [ ] Schema fingerprint equals the approved target or every difference is
      reviewed and documented.
- [ ] Key roles and ACLs verified.
- [ ] `n8n_data` and encryption context restored, or recovery classified partial.
- [ ] Canonical workflows structurally reconciled and initially inactive.
- [ ] Production-only n8n bindings restored without disclosure.
- [ ] Seller retry drift reviewed.
- [ ] CPC poller activation contract reviewed.
- [ ] Active systemd unit hash verified.
- [ ] Caddy routing and authentication boundary verified without exposing secrets.
- [ ] Cron hash and blob verified; cron installed only at the final stage.
- [ ] Control Center and capabilities endpoints return HTTP 200.
- [ ] n8n `/healthz` returns HTTP 200.
- [ ] MCP route and Recommendation Tool read-only calls pass.
- [ ] No duplicate collectors, schedules or outbound deliveries are active.
- [ ] Calculator remains behind the Settlement Contract implementation gate.

## 19. Final decision

`PRODUCTION_RECOVERY_MANIFEST_READY_FOR_REVIEW`

The source-level production mosaic is fully attributed. Full-stack recovery
remains partially reproducible until the documented n8n, migration-ledger,
container-build, writable-layer and infrastructure-configuration gaps are
closed under separately approved work.
