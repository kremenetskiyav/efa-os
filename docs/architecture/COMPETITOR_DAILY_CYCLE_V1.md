# Competitor Daily Cycle v1

Status: local implementation, dry-run only.

## Boundary

The cycle starts after a human-controlled Work browser session has finished. Its only collection input is one immutable UTF-8 JSON artifact with contract `competitor_snapshot_evidence.v1`. The cycle never opens a browser, connects to Work, repairs evidence, schedules work, or changes PostgreSQL.

The approved handoff records the Evidence path, SHA-256, byte size, contract version, region, source, collection method, and collection timestamps. The expected source is `OZON_BUYER_WORK`; the expected method is `MANUAL_CONTROLLED_WORK_BROWSER`.

## Pipeline

`Scripts/run_competitor_daily_cycle_v1.py` performs these stages:

1. validate the immutable Evidence and reject partial searches, region drift, challenge markers, timestamp errors, and unresolved enrichment evidence;
2. read versioned SKU/OEM/watchlist references with the approved read-only PostgreSQL role;
3. freeze `competitor_snapshot_reference_plan.v1` at the minimum search `captured_at`;
4. build deterministic `competitor_snapshot_payload.v1` with `Scripts/build_competitor_snapshot_artifacts_v1.py`;
5. execute Snapshot Importer reconciliation in dry-run and accept only `NEW_BATCH` or `EXACT_ALREADY_APPLIED`;
6. resolve the exact current batch from its collection refs and the latest complete persisted batch strictly before it;
7. run Analyzer v1 and the unchanged Finding Engine v1 taxonomy;
8. execute Finding Persistence reconciliation in dry-run and accept only `NEW_FINDING_SET` or `EXACT_ALREADY_APPLIED`;
9. emit `competitor_daily_cycle_result.v1`.

There is no write option in the orchestrator. It rejects PostgreSQL owner/superuser identities and verifies `transaction_read_only=on` on the live connection before reading reference data.

## Frozen reference plan

The plan is derived, not hardcoded. It uses profiles, OEM records created by `reference_at`, and monitored memberships (`PRIMARY`, `RESERVE`, `CONTROL`) whose validity interval contains `reference_at`. Each slot binds the offer, exact OEM query, Ozon product ID, listing, family, membership, membership status, seller ID, and product name.

Query and slot ordinals are frozen in the artifact. They preserve the source reference order for canonical replay. Plan validation requires unique query identities, unique logical slots, exact counts, and exact region/source/method metadata. The current production result of 9 queries and 87 slots is therefore an observation, not a permanent constant.

## Payload and identity

The builder maps search evidence, structured enrichment evidence, and every frozen slot into `FOUND` or `NOT_FOUND_WITHIN_SCAN_LIMIT`. Missing optional observed dimensions remain null and are not a validation failure. Search and enrichment timestamps and raw evidence refs are preserved.

Payload serialization is UTF-8 JSON, two-space indentation, original contract field order, and one terminal newline. Identity is:

- Evidence SHA-256: hash of the immutable input bytes;
- Payload SHA-256: hash of canonical payload bytes;
- batch ref: existing `cm-snapshot-idempotency.v1` derivation;
- cycle ID: deterministic hash of Evidence hash, Payload hash, and batch ref;
- attempt ID: UUID generated per invocation and excluded from semantic identity.

The archived T1 replay is a required regression: Evidence `77c8e862688fccbe61e283c73566a65d0920fc0b18931314c64e68e51ac85b08` must produce Payload `6449a24a3a68809642b69bf043056fc4b9845c48a973e6d72852be2fbe499852` and batch `cm-snapshot-v1:batch:961baa306c34ff7dc6c973e02b49d0c26226864709148fe6c128109e6a68138e`.

## Snapshot comparison

Current selection uses the exact collection-ref set produced by the import plan and validates its exact query set against the frozen reference data. Previous selection is the latest complete successful persisted batch with `reference_at` earlier than current; calendar dates are not used. The expected query set is resolved at each batch reference time, so a legitimate watchlist change can yield continuing, new, and retired slots without weakening batch completeness.

Analyzer source counts in this orchestrated replay are deterministic counts through the selected current batch. Downstream finding rows are excluded from analysis identity. This preserves replay identity after findings have subsequently been persisted.

## Finding persistence input

The writer validates the supplied Finding Set byte hash, embedded analysis hash, Finding Set contract, summary count, deterministic set identity, child dedup identities, observation provenance, schema, and history. It contains no T1-specific approved hashes or set key. Zero-finding manifests are valid. Snapshot-to-snapshot comparisons are supported; previous is not assumed to be a baseline.

## Result and failures

The machine-readable result contract is `competitor_daily_cycle_result.v1`. Success is only `DRY_RUN_SUCCESS`. Failures use exactly:

- `VALIDATION_FAILED`;
- `IMPORT_CONFLICT`;
- `ANALYSIS_FAILED`;
- `ENGINE_FAILED`;
- `PERSISTENCE_CONFLICT`;
- `INTERNAL_ERROR`.

Failures stop the next stage, return a non-zero process status, keep database write counters at zero, and emit a length-limited sanitized message. The result never contains credentials, connection strings, cookies, or browser state.

## Operational handoff

The semi-automated operator command accepts `--evidence`, optional `--evidence-sha256`, and optional `--output-dir`. Evidence collection remains a separate controlled manual step. Production snapshot or finding writes, scheduling, n8n integration, deployment, and browser automation require separate future approval and are outside v1.

## Local read-only credential handoff

`Scripts/run_competitor_daily_cycle_local_v1.py` is the only approved local v1 adapter between the protected credential file and the Daily Cycle process. It reads `C:\Users\Andrey\.efa-os\secrets\efa-read-mcp.env`, which must contain exactly one variable named `DATABASE_URL`. The file remains local and outside Git. The launcher checks that Windows ACL inheritance is disabled, the current local user is the sole access principal established by the current EFA file pattern, and no unexpected principal has an access rule. It never weakens or rewrites the ACL.

The parsed credential must target database `efa` as role `efa_mcp_readonly`. Before any business stage, the launcher opens a connection with `default_transaction_read_only=on` and verifies all of the following:

- current and session role are exactly `efa_mcp_readonly`;
- the role is neither superuser nor database owner and has no database `CREATE` privilege;
- `transaction_read_only=on`;
- `mcp_read` grants `USAGE` but not `CREATE`;
- `public` grants neither `USAGE` nor `CREATE`;
- the role can select the approved Daily Cycle views in `mcp_read`.

The launcher has no raw-table fallback and performs no business reads during preflight. Missing or unreadable files, unsafe ACL metadata, malformed or unexpected variables, a wrong database or role, authentication failure, or any role/ACL mismatch stops execution before the Daily Cycle process exists. There is no SSH, owner, write-credential, old-secret, or alternate-secret fallback.

For a full manual invocation, the launcher converts the URL in memory to `EFA_DB_HOST`, `EFA_DB_PORT`, `EFA_DB_NAME`, `EFA_DB_USER`, and `EFA_DB_PASSWORD`, removes any inherited conflicting database variables, and places the credential only in the spawned child's environment. It does not modify the parent shell, user or machine environment, Windows registry, or disk. The launcher waits for the child, propagates its exit code, closes the preflight connection, and exits. It creates no daemon, service, scheduler, or background process.

`--preflight-only` performs only the protected-file, connection, role, schema, and approved-view checks. It does not launch Analyzer, Finding Engine, import/persistence reconciliation, or any other Daily Cycle business stage. Sanitized output contains only status, role, database, host category, port presence, ACL/read-only booleans, child exit code when applicable, and zero database-write counters. URLs, passwords, DSNs, tokens, and database exception text are never logged or included in result JSON.

## Approved manual SSH transport

The approved local PostgreSQL transport is one operator-managed, ephemeral,
loopback-only SSH local forward with this canonical shape:

`127.0.0.1:5432 → SSH root@72.56.66.63:22 → 127.0.0.1:5432`

Its fixed transport metadata is:

- SSH host: `72.56.66.63`;
- SSH user: `root`;
- SSH port: `22`;
- SSH key identifier: `efa-mcp-ams1`;
- local bind: `127.0.0.1:5432`;
- remote PostgreSQL target: `127.0.0.1:5432`;
- transport type: manual ephemeral loopback-only SSH local forward.

The operator starts this tunnel manually before the local Daily Cycle and
terminates it after the run. The tunnel is not a persistent service. It is not
created by the local launcher, and Task Scheduler, cron, systemd, n8n, or any
background daemon is not used to create or retain it. The only approved SSH
port is `22`; there is no automatic fallback to port `2222`. `GatewayPorts` is
not used. Binding to `0.0.0.0`, a LAN interface, or a VPN interface is
prohibited.

The SSH key may already be loaded in the Windows `ssh-agent`. Its passphrase,
private-key material, and any SSH credential value remain outside the
repository. The launcher stores no SSH configuration and has no SSH credential
or tunnel-management responsibility.

The local Daily Cycle credential remains in the protected, non-Git file
`C:\Users\Andrey\.efa-os\secrets\efa-read-mcp.env`. It contains exactly one
variable, `DATABASE_URL`; the value is never documented or logged. Its expected
logical identity is database `efa`, user `efa_mcp_readonly`, endpoint
`127.0.0.1:5432`, and launcher scheme `postgresql+asyncpg`.

Responsibilities remain separated:

- the operator starts the approved ephemeral tunnel, initiates the controlled
  Work collection, and starts the local Daily Cycle;
- the local launcher validates the protected credential and read-only database
  role/ACL, creates the child-only environment, and starts the Daily Cycle; it
  does not create or retain the tunnel;
- the Daily Cycle knows no SSH credentials, does not manage the tunnel, contains
  no browser transport or unattended scheduler, and uses the already available
  `127.0.0.1:5432` endpoint.

If `127.0.0.1:5432` is unavailable, authentication fails, or database preflight
does not pass, execution stops with a non-zero exit before business stages. No
SSH or port fallback, remote credential retrieval, raw-database fallback,
business-stage continuation, or database write is allowed. Semi-automatic v1
therefore remains manual Work collection plus the manual ephemeral tunnel plus
the automated local downstream dry-run pipeline.

### Manual rotation and reprovisioning

When the local credential is stale, obtain the current `efa_mcp_readonly` URL through the approved credential-rotation channel without copying it into chat, command arguments, shell history, logs, or Git. Open the existing protected env file in a local non-syncing editor, replace only the `DATABASE_URL` value, and save the existing file rather than creating a differently protected replacement. Then recheck that inheritance remains disabled, the current user is the only intended principal, and unexpected principals remain zero. Run the launcher with `--preflight-only`; do not continue to the Daily Cycle unless the sanitized result is `PREFLIGHT_PASS`.
