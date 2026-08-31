# Competitor Monitor Operator Runbook v1

Status: T3/T4/T5 stabilization procedure.

This runbook is the normal operator path for one genuine Competitor Monitor
snapshot. It does not authorize a run by itself. Every production write still
requires an explicit approval for the exact validated cycle.

## 1. Scope and fixed baseline

The normal cycle has five steps:

1. **COLLECT**
2. **VALIDATE**
3. **APPROVE**
4. **PERSIST**
5. **REVIEW**

Stabilization cadence is Monday / Wednesday / Friday for T3 / T4 / T5. The
operator starts every cycle manually. There is no scheduler, browser
automation, unattended tunnel, or automatic production write in this runbook.

Production checkpoint before T3:

| Item | Value |
| --- | --- |
| State | `T2_PRODUCTION_PERSISTENCE_COMPLETE` |
| Search runs | `27` |
| Observations | `261` |
| Finding sets | `2` |
| Findings | `45` |
| Latest T2 Finding Set | `c2834d33-9176-520f-a010-598b9f18a6c8` |
| Approved Git baseline | `92dfed7af7104984e69f5e6b648fc048e109be95` |
| Read role | `efa_mcp_readonly` |
| Writer role | `efa_competitor_writer` |

These values are the starting checkpoint only. Never reuse T2 query, slot, or
insert counts as T3+ requirements. Every T3+ count comes from its own fresh
Reference Plan and validated Import Plan.

## 2. Before starting

Use a cycle label `<TN>` equal to `T3`, `T4`, or `T5`. Create a dedicated local
artifact directory outside Git, for example:

```text
C:\Users\Andrey\.efa-os\artifacts\competitor-monitor\<TN>-<UTC>\
```

Use the following placeholders throughout the run:

| Placeholder | Meaning |
| --- | --- |
| `<TN>` | `T3`, `T4`, or `T5` |
| `<EVIDENCE_PATH>` | Accepted immutable Evidence file |
| `<EVIDENCE_SHA>` | SHA-256 of the exact Evidence bytes |
| `<OUTPUT_DIR>` | Local non-Git artifact directory |
| `<PAYLOAD_PATH>` | `<OUTPUT_DIR>\COMPETITOR_SNAPSHOT_PAYLOAD_V1.json` |
| `<PAYLOAD_SHA>` | SHA-256 emitted by the Daily Cycle |
| `<ANALYSIS_PATH>` | `<OUTPUT_DIR>\COMPETITOR_SNAPSHOT_ANALYSIS_V1.json` |
| `<ANALYSIS_SHA>` | SHA-256 emitted by the Daily Cycle |
| `<FINDINGS_PATH>` | `<OUTPUT_DIR>\COMPETITOR_FINDING_SET_V1.json` |
| `<FINDINGS_SHA>` | SHA-256 independently calculated from Findings |
| `<FINDING_SET_KEY>` | Deterministic key emitted by the Daily Cycle |

Do not store artifacts, operator logs, backups, credentials, or connection
information in Git.

## 3. STEP 1 — COLLECT

### Input

- fresh production Reference Plan summary;
- active Ozon buyer session in the official buyer interface;
- one operator-controlled Work browser session.

### Blocking prechecks

Before the first OEM query confirm:

- [ ] the official Ozon buyer interface is open;
- [ ] the buyer session is active;
- [ ] location label is exactly `Почта России • Венёвская ул., 3а`;
- [ ] region key is exactly
      `OZON_RU:DISPLAY:ПОЧТА_РОССИИ|ВЕНЁВСКАЯ_УЛ_3А`;
- [ ] there is no CAPTCHA;
- [ ] there is no antibot/login challenge;
- [ ] there is no incident or system-error page;
- [ ] the fresh plan identifies ACTIVE/HOLD SKU, queries, slots, memberships,
      and ordering.

**Region mismatch means STOP before the first OEM query.** Do not change the
region automatically and do not attempt to bypass a challenge.

### Collection contract

- Run every ACTIVE query exactly once.
- Cover every logical slot in the fresh plan.
- Do not add an unplanned query or slot.
- Enrich each unique found monitored listing exactly once.
- Do not emit duplicate logical slots or duplicate enrichment identities.
- Require every search to be `SUCCESS`.
- Require every required enrichment to be `COMPLETE`.
- Preserve exact search and enrichment timestamps.
- Use `source=OZON_BUYER_WORK`.
- Use `collection_method=MANUAL_CONTROLLED_WORK_BROWSER`.

### Reference Plan rule

The canonical reference time is derived, never typed manually:

```text
reference_at = min(search_evidence[].captured_at)
```

Do not hardcode nine queries or 87 slots. Record from the current plan:

- ACTIVE/HOLD SKU;
- query count;
- slot count;
- membership count;
- Reference Plan hash;
- additions/removals since the previous cycle.

A changed plan is not automatically invalid, but it requires human review
before write.

### Output and acceptance

Output must be one `competitor_snapshot_evidence.v1` artifact. Before accepting
it, record:

- Evidence path and byte size;
- Evidence SHA-256;
- derived `reference_at`;
- query and slot counts;
- FOUND and `NOT_FOUND_WITHIN_SCAN_LIMIT` counts;
- unique found listing count;
- enrichment count;
- collection start, finish, and duration.

Once accepted, Evidence is immutable. If an error is found before acceptance,
create a new artifact and a new SHA-256. Never edit an accepted Evidence file.

## 4. STEP 2 — VALIDATE

### Transport and read credential

Use only the approved ephemeral loopback SSH forward:

```text
127.0.0.1:5432 -> root@72.56.66.63:22 -> 127.0.0.1:5432
```

The tunnel is operator-managed, uses the already approved SSH key, binds only
to `127.0.0.1`, and is removed after the controlled work. No fallback to port
2222, `GatewayPorts`, persistent service, or background scheduler is allowed.

The local launcher reads the protected read credential and verifies
`efa_mcp_readonly`, database `efa`, read-only transaction state, schema ACLs,
and approved views before starting a business stage.

### Canonical dry-run command

Run from the repository root in PowerShell, substituting only the three path/hash
placeholders:

```powershell
python Scripts/run_competitor_daily_cycle_local_v1.py -- --evidence "<EVIDENCE_PATH>" --evidence-sha256 "<EVIDENCE_SHA>" --output-dir "<OUTPUT_DIR>"
```

This is read-only. It builds the Reference Plan, Payload, Analysis, Finding Set,
and both reconciliation plans. It must not receive a writer credential or a
write gate.

### PASS contract

For a genuine new cycle require:

```text
final_status=DRY_RUN_SUCCESS
import_state=NEW_BATCH
persistence_state=NEW_FINDING_SET
db_writes.insert=0
db_writes.update=0
db_writes.delete=0
```

`EXACT_ALREADY_APPLIED` is valid only for an intentional exact replay of an
already persisted cycle. If T3/T4/T5 was expected to be new, an unexpected
already-applied result is a STOP until the identity is explained.

### Required record

Record from `COMPETITOR_DAILY_CYCLE_RESULT_V1.json` and generated artifacts:

- Evidence SHA;
- Payload SHA and batch ref;
- Analysis SHA;
- Findings SHA;
- Finding Set key;
- Importer and Persistence states;
- expected queries and slots;
- FOUND, NOT_FOUND, and enrichment counts;
- finding counts by severity;
- start, finish, and calculated dry-run duration.

The Daily Cycle result does not currently expose Findings SHA directly.
Calculate it without changing the file:

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath "<FINDINGS_PATH>").Hash.ToLowerInvariant()
```

For `NEW_BATCH`, planned snapshot inserts are:

```text
search-run inserts = expected_queries
observation inserts = expected_slots
```

For `NEW_FINDING_SET`, planned finding inserts are:

```text
finding-set inserts = 1
finding child inserts = finding_count
```

Do not replace these formulas with T2 values.

### Focused validation checklist

- [ ] Evidence path exists and its SHA equals `<EVIDENCE_SHA>`.
- [ ] Evidence contract, source, method, region, and derived `reference_at` pass.
- [ ] Fresh Reference Plan has unique positive ordinals and exact query/slot
      reconciliation.
- [ ] Daily Cycle finished with `DRY_RUN_SUCCESS`.
- [ ] Importer state is `NEW_BATCH` for a new cycle.
- [ ] Persistence state is `NEW_FINDING_SET` for a new cycle.
- [ ] Expected queries equal planned search-run inserts.
- [ ] Expected slots equal planned observation inserts.
- [ ] FOUND + NOT_FOUND equals expected slots.
- [ ] Finding child inserts equal `finding_count`; manifest inserts equal one.
- [ ] Evidence, Payload, Analysis, and Findings SHA values are recorded.
- [ ] Batch ref and Finding Set key are recorded.
- [ ] Severity totals equal finding count.
- [ ] Database INSERT/UPDATE/DELETE counters are all zero.
- [ ] No secret, DSN, credential, cookie, or browser state appears in output.
- [ ] Generated artifacts remain outside Git and unchanged after hashing.

### VALIDATE stop conditions

STOP on any of the following:

- Evidence, region, timestamp, or hash validation failure;
- Reference Plan conflict or unexpected plan drift;
- partial batch or partial Finding Set conflict;
- unexpected already-persisted cycle;
- importer state outside the approved state machine;
- FK, constraint, schema, or unique conflict;
- Analysis or Finding Engine failure;
- persistence reconciliation conflict;
- raw-read, approved-view, role, ACL, or read-only failure;
- artifact bytes/hash changed during validation.

No repair, upsert, backfill, partial continuation, or destructive cleanup is
allowed.

## 5. STEP 3 — APPROVE

One explicit approval covers the complete validated cycle. The approval record
must contain:

```text
Cycle: <TN>
Evidence SHA: <EVIDENCE_SHA>
Payload SHA: <PAYLOAD_SHA>
Batch ref: <BATCH_REF>
Analysis SHA: <ANALYSIS_SHA>
Findings SHA: <FINDINGS_SHA>
Finding Set key: <FINDING_SET_KEY>
Importer state: NEW_BATCH
Persistence state: NEW_FINDING_SET
Expected search-run inserts: <EXPECTED_QUERIES>
Expected observation inserts: <EXPECTED_SLOTS>
Expected finding-set inserts: 1
Expected finding child inserts: <FINDING_COUNT>
```

Approval becomes invalid if any approved semantic identity or expected database
effect changes: Evidence SHA, Payload SHA, batch ref, Analysis SHA, Findings
SHA, Finding Set key, Importer or Persistence history state, planned Snapshot
insert counts, or planned Finding insert counts. A new approval is then
required. A change only to
non-semantic execution metadata -- such as `attempt_id`, `started_at`,
`finished_at`, other execution timestamps, local output directory,
verification-run identifier, or regenerated result JSON containing only those
permitted metadata changes -- does not invalidate approval. It must not alter
the approved artifact bytes, identities, states, or counts. Ordinary
deterministic INFO findings do not require separate approval per finding.

### Human-review triggers

Human review is mandatory before write when:

- Reference Plan composition changed;
- a SKU/OEM is new or ACTIVE/HOLD changed;
- collection is partial;
- a challenge, session, or region anomaly occurred;
- Analyzer reports material, structured, or unexplained product fact drift,
  such as a structured numeric dimension, country, manufacturer,
  compatibility, materially interpreted carbon/filter-type claim, conflicting
  structured facts across query contexts, or another unexplained change that
  may affect product identity or business interpretation;
- coverage changed by at least 20 percentage points;
- finding count is more than twice the previous count and increased by at
  least ten;
- an unexpected IMPORTANT finding exists;
- query contexts contain inconsistent price evidence;
- any runtime or security condition differs from the approved contract.

Raw text representation, title/layout/UI-block, parser-formatting changes, or
raw-field changes do not by themselves require human review when normalized
structured facts remain materially identical. Unresolved material ambiguity
remains fail-closed.

IMPORTANT does not invalidate factual persistence, but it requires review
before external delivery or business reaction.

## 6. STEP 4 — PERSIST

PERSIST is allowed only after exact approval. It consists of two independent
atomic transactions with an exact comparison between them.

### Common pre-write gate

- [ ] Git/runtime baseline is the approved version.
- [ ] Production health is PASS.
- [ ] `collectors_ok=true`.
- [ ] There is an exclusive job window.
- [ ] No competing Competitor Monitor write is active.
- [ ] Writer identity is exactly `efa_competitor_writer`.
- [ ] Writer is non-superuser, non-owner, and has the approved ACL fingerprint.
- [ ] Writer credential came from the separate protected writer secret.
- [ ] No credential or DSN appears in arguments, output, logs, or artifacts.
- [ ] Evidence/Payload/Analysis/Findings hashes remain approved.
- [ ] Production history still matches the approved pre-write state.
- [ ] A new verified backup exists.

There is no committed unified writer launcher. Use only the already approved
protected writer credential handoff established for T2. Never paste or echo a
password/DSN. Do not reuse the read credential for writes and do not use a
superuser.

### Backup for T3/T4/T5

Create a full PostgreSQL custom-format backup through the approved production
backup procedure. Use this path convention:

```text
/var/backups/efa-os/pre-competitor-<TN>-write-<UTC>.dump
```

Require and record:

- command return code `0`;
- non-empty file;
- SHA-256;
- `pg_restore --list` success;
- pre-write manifest with production counts and approved artifact identities.

Retain each stabilization backup for at least 30 days. Do not place it in Git.

### Stage 1 — Snapshot Importer

Allowed inserts only:

- `public.competitor_search_runs`;
- `public.competitor_observations`.

No UPDATE, DELETE, upsert, repair, or unrelated table write is permitted.

Run the existing importer under the protected writer child environment. The
write gate must exist only for that child process:

```powershell
cmd.exe /d /s /c 'set "COMPETITOR_SNAPSHOT_WRITE_ENABLED=true" && python Scripts/import_competitor_snapshot_v1.py --payload "<PAYLOAD_PATH>" --evidence "<EVIDENCE_PATH>" --payload-sha256 "<PAYLOAD_SHA>" --evidence-sha256 "<EVIDENCE_SHA>" --write'
```

The command template assumes the approved writer DB variables have already
been supplied to this child-only execution context without being printed or
made persistent.

Require:

- exact approved insert counts;
- `DB_UPDATES=0` and `DB_DELETES=0`;
- transaction commit success;
- post-write exact reconciliation;
- exactly one new current snapshot;
- exact replay returns `EXACT_ALREADY_APPLIED` with zero inserts.

If Stage 1 rolls back, no new snapshot exists. Correct the cause and retry the
same approved artifacts only if their identity remains unchanged.

### Between Stage 1 and Stage 2

Re-run the canonical read-only Daily Cycle using the same Evidence/SHA into a
new verification output directory. Require:

- Importer state `EXACT_ALREADY_APPLIED`;
- current snapshot is the newly persisted `<TN>`;
- previous snapshot is the latest complete earlier snapshot;
- Payload SHA unchanged;
- Analysis SHA unchanged;
- Findings SHA unchanged;
- Finding Set key unchanged;
- Persistence state remains `NEW_FINDING_SET`.

If Analysis SHA or Findings SHA changes, STOP. Keep the valid snapshot and do
not proceed to Stage 2.

### Stage 2 — Finding Persistence Writer

Allowed inserts only:

- `public.competitor_finding_sets`;
- `public.competitor_findings`.

No UPDATE, DELETE, upsert, repair, finding mutation, or external notification
is permitted.

Use the revalidated post-Stage-1 Findings artifact. The write gate must exist
only for the writer child process:

```powershell
cmd.exe /d /s /c 'set "COMPETITOR_FINDINGS_WRITE_ENABLED=true" && python Scripts/persist_competitor_findings_v1.py --findings "<FINDINGS_PATH>" --findings-sha256 "<FINDINGS_SHA>" --analysis-sha256 "<ANALYSIS_SHA>" --write'
```

Require:

- one exact manifest for the approved Finding Set key;
- exact approved child count, including valid zero-child sets;
- `DB_UPDATES=0` and `DB_DELETES=0`;
- post-write exact reconciliation;
- exact replay returns `EXACT_ALREADY_APPLIED` with zero inserts.

### Partial-stage failure rules

| Failure | Persistent state | Safe next action |
| --- | --- | --- |
| Stage 1 rolls back | No new snapshot | Correct cause; rerun exact Stage 1 |
| Stage 1 commits, Stage 2 blocks | Valid snapshot remains | Revalidate persisted Current/Previous and exact artifacts; retry Stage 2 |
| Stage 2 rolls back | Snapshot remains; no new Finding Set | Retry exact Finding Set write |
| Summary fails after Stage 2 | Snapshot and Finding Set remain | Repair only read/presentation path |

Never manually delete a valid snapshot or persisted Finding Set. There is no
destructive rollback by default.

## 7. STEP 5 — REVIEW

After successful persistence verify:

- [ ] latest complete snapshot is `<TN>`;
- [ ] latest Finding Set belongs to that snapshot pair;
- [ ] Finding Set UUID/key and child count match approval;
- [ ] production table-count deltas match the Import/Persistence plans;
- [ ] Summary selects the latest persisted Finding Set;
- [ ] Summary severity totals equal manifest children;
- [ ] coverage reflects the current production reference state;
- [ ] restoration OEM scopes use only `REAPPEARED` contexts;
- [ ] Control Center returns HTTP 200 and renders the same counts;
- [ ] `collectors_ok=true` and there is no service regression;
- [ ] exact replay is a zero-write no-op;
- [ ] tunnel is terminated and write gates are absent from the parent
      environment.

Record:

- post-write table counts;
- latest Finding Set UUID and children;
- Summary status, coverage, and severity counts;
- price and visibility aggregates;
- Control Center result;
- full pipeline duration;
- manual interventions;
- backup path/SHA;
- delivery state.

## 8. Delivery policy

During T3–T5:

- Control Center reflects every successfully persisted snapshot;
- leave the existing scheduled AI Analyst/report unchanged;
- do not perform an extra manual competitor send;
- do not add Telegram alerting;
- INFO-only activity is visible in Control Center and the existing aggregate
  report.

After T5, a separately reviewed target policy may send successful summaries
and WATCH/IMPORTANT by Email, and reserve Telegram for WATCH/IMPORTANT, failed
cycles, or stale-monitor alerts. This runbook does not implement that policy.

## 9. Security checklist

### Every run

- [ ] read identity is exactly `efa_mcp_readonly`;
- [ ] writer identity is exactly `efa_competitor_writer`;
- [ ] writer is non-superuser, is not the database owner, has the exact approved
      role/ACL fingerprint, and has unchanged zero memberships;
- [ ] read and writer secret files remain separate and protected;
- [ ] secret ACL inheritance is disabled and fingerprint matches the approved
      local contract;
- [ ] SSH uses port 22 and a loopback-only ephemeral forward;
- [ ] no `GatewayPorts`, public/LAN/VPN bind, or persistent tunnel;
- [ ] every write gate exists only in its child process and is removed after;
- [ ] no credential, DSN, token, cookie, or password was logged;
- [ ] artifacts and command-line arguments contain no secret;
- [ ] tunnel cleanup is complete.

Do not repeat the full Migration 026 audit on every cycle.

### Periodic or change-triggered

- full Migration 026 ACL validation;
- full role-membership and application-object ownership audit, including after
  database/ACL migrations or role changes;
- verified restore test;
- credential rotation;
- SSH host-key review;
- revalidation after a database migration, role change, or infrastructure
  change.

## 10. Operator log template

Store one completed copy outside Git for each cycle:

```text
Cycle:
Date:
Evidence path:
Evidence SHA:
Reference at:
Reference Plan SHA:
Reference Plan stable/changed:
Queries:
Slots:
FOUND:
NOT_FOUND:
Unique listings:
Enrichments:
Collection duration:
Dry-run duration:
Payload SHA:
Batch ref:
Analysis SHA:
Findings SHA:
Finding Set key:
IMPORTANT:
WATCH:
INFO:
Manual intervention:
Approval reference:
Stage 1:
Stage 2:
Exact replay:
Final counts:
Latest Finding Set UUID:
Finding children:
Summary status:
Coverage:
Control Center:
Delivery:
Backup path:
Backup SHA:
Notes:
```

Do not create a database schema for this log during stabilization.

## 11. T3–T5 stabilization scorecard

| Cycle | Collection PASS | Region stable | No challenge | Plan stable/changed | Dry-run PASS | Write PASS | Exact replay PASS | Control Center PASS | Manual interventions | Duration | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| T3 |  |  |  |  |  |  |  |  |  |  |  |
| T4 |  |  |  |  |  |  |  |  |  |  |  |
| T5 |  |  |  |  |  |  |  |  |  |  |  |

## 12. Automation and scheduler gates after T5

Browser automation may be considered only if T3/T4/T5 all succeeded, the
region and session remained stable, no challenge occurred, Evidence required
no manual repair, collection duration was predictable, and manual intervention
was low.

No scheduler is created now. After T5, consider scheduling only read-only
downstream validation, health/freshness monitoring, or delivery. Browser
collection and production writes remain operator-controlled unless separately
redesigned and approved.

## 13. Definition of Done

Competitor Monitor v1 stabilization is complete only when T3, T4, and T5 each
have:

- immutable accepted Evidence;
- complete deterministic dry-run;
- artifact and hash stability across persistence;
- least-privilege Stage 1 and Stage 2 writes;
- exact replay no-op;
- no manual database intervention;
- correct latest Summary and Control Center state;
- no credential leak;
- safe retry behavior for any failure encountered.

The runbook and delivery policy must be accepted, and technical debt must
remain separate from operational blockers.

## 14. Non-blocking technical debt

- No committed pre-collection Reference Plan export command.
- No unified writer persistence wrapper.
- Archive path and required Evidence SHA are enforced by runbook, not CLI.
- Control Center freshness threshold is unresolved.
- Cycle attempts and failures are not persisted operationally.
- Summary architecture documentation contains stale integration wording.
- The Collector prototype remains untracked and outside production runtime.
- `STALE_TEST_ASSERTION poller.active=false` remains a cleanup item.

**None of these items blocks T3–T5.** Do not expand a normal run into a
development audit to compensate for them.

## 15. Escalation rule

If the happy path requires more than Collect, Validate, Approve, Persist, and
Review, stop and classify the additional action. A repair, schema change,
credential change, new automation, manual database mutation, or external send
requires separate scope and approval.

## 16. Deep troubleshooting references

- [Competitor Daily Cycle v1](../architecture/COMPETITOR_DAILY_CYCLE_V1.md)
- [Snapshot Import v1](../architecture/COMPETITOR_SNAPSHOT_IMPORT_V1.md)
- [Snapshot Analyzer v1](../architecture/COMPETITOR_SNAPSHOT_ANALYZER_V1.md)
- [Finding Engine v1](../architecture/COMPETITOR_FINDING_ENGINE_V1.md)
- [Findings Persistence v1](../architecture/COMPETITOR_FINDINGS_PERSISTENCE_V1.md)
- [Monitor Summary v1](../architecture/COMPETITOR_MONITOR_SUMMARY_V1.md)
- [Daily Report v1](../architecture/COMPETITOR_DAILY_REPORT_V1.md)
- [Writer ACL validation](../../database/validation/026_competitor_writer_role_acl_v1_validation.sql)
