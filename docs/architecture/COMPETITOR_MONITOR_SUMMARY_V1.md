# Competitor Monitor Summary Read Model v1

## Purpose

`competitor_monitor_summary.v1` is the stable, read-only presentation contract
for Control Center and daily-report consumers. It is built from the latest
persisted Competitor Finding Set and does not run the Snapshot Analyzer or
Finding Engine on demand.

The implementation is `Scripts/build_competitor_monitor_summary_v1.py`.
Control Center consumes the same DTO through the approved `mcp_read` source
surface; report integration remains outside v1 scope.

## Runtime sources

Primary facts:

- `mcp_read.competitor_latest_finding_set`;
- `mcp_read.competitor_findings`.

Dynamic portfolio coverage:

- `mcp_read.competitor_monitoring_coverage`.

The views preserve source equivalence while keeping the runtime role away from
raw `public.competitor_*` relations. There is no fallback to raw tables.

Archived JSON is evidence and recovery material, not the normal runtime source.

## Read-only boundary

The PostgreSQL connection sets `default_transaction_read_only=on` and the
source reader also calls `set_session(readonly=True, autocommit=False)` before
its first query. It performs three bounded `SELECT` statements and finishes the
read transaction with `rollback()`. The implementation has no database write
mode.

## Latest-set resolution

The latest supported set is selected deterministically:

```sql
WHERE finding_set_contract_version = 'competitor_finding_set.v1'
ORDER BY current_reference_at DESC, applied_at DESC, finding_set_id DESC
LIMIT 1
```

`created_at` is not a snapshot timestamp and does not participate in this
selection.

## Source validation

The builder returns `available=true` only when all of the following hold:

- the manifest exists and uses `competitor_finding_set.v1`;
- contract, hash, source-kind, batch-id, and snapshot timestamp fields are
  present and valid;
- actual child count equals `expected_findings_count`;
- every child points to the selected manifest;
- finding keys are unique;
- every `details` value is an object and every `evidence` value is an array;
- presentation fields needed by v1 have supported severity and membership
  values;
- severity counts sum to the child count.

The reader never returns a partial finding set as available.

A manifest with `expected_findings_count=0` and no children is valid. It yields
zero counts and `status=NORMAL`; it is not a degraded state.

## DTO contract

The top-level response is:

```json
{
  "contract_version": "competitor_monitor_summary.v1",
  "generated_at": "...",
  "available": true,
  "degraded_reason": null,
  "coverage": {},
  "snapshot": {},
  "status": "WATCH",
  "counts": {},
  "headline": {},
  "own": {},
  "competitors": {},
  "prices": {},
  "top_findings": []
}
```

Raw database rows are not exposed.

### Coverage

`portfolio_sku_count` is the current number of SKU profiles.
`active_monitored_sku_count` counts profiles in `ACTIVE` state with at least
one active approved watchlist membership. Every remaining SKU is returned in
`unmonitored_skus` with `offer_id`, `watchlist_state`, and a source-backed
reason when one exists. A reason remains `null` when the reference layer only
supports the state.

No portfolio or monitored count is hardcoded.

### Snapshot and freshness

The snapshot contains finding-set identity, previous/current source and batch
provenance, factual `reference_at`, `captured_through`, `age_seconds`, and the
finding-set contract version. `age_seconds` is calculated from
`generated_at - current_reference_at`.

Freshness is policy-driven:

- no threshold: `UNKNOWN`;
- age not greater than threshold plus optional grace: `FRESH`;
- age greater than threshold plus grace: `STALE`;
- missing or invalid source: `UNAVAILABLE`.

No daily schedule is inferred. An explicitly stale set returns
`available=false` with `FINDING_SET_STALE`.

### Counts and overall status

Counts contain `important_count`, `watch_count`, `info_count`, and
`total_findings`.

Overall status is `IMPORTANT` when at least one IMPORTANT finding exists,
otherwise `WATCH` when at least one WATCH finding exists, otherwise `NORMAL`.
INFO does not elevate the status.

### Roles

Presentation labels are fixed:

- `CONTROL` — `Наша карточка`;
- `PRIMARY` — `Основной конкурент`;
- `RESERVE` — `Дополнительный конкурент`.

The technical membership state may accompany the label.

### Own, competitor, and price summaries

CONTROL findings are placed in `own`. PRIMARY and RESERVE visibility findings
are aggregated in `competitors`, including lost/restored role breakdown.
Competitor price changes are placed in `prices` with factual previous/current
amounts, delta, currency, query context, and stable `details_ref`.

Affected OEM queries are transitions that changed in the direction represented
by the finding. Remaining queries are current `FOUND` contexts not in that
affected set.

### Headline and top findings

Headline attention priority is:

1. IMPORTANT own;
2. IMPORTANT competitor;
3. WATCH own;
4. WATCH competitor.

Equal-priority rows use `finding_type`, `offer_id`, and `finding_key`.
When no WATCH or IMPORTANT row exists, a neutral no-attention headline is
returned.

`top_findings` defaults to five rows. Its ordering is IMPORTANT before WATCH
before INFO, then own before competitor, followed by the same deterministic
fields. `details_ref` is always `finding:<finding_key>`.

Visibility messages preserve scan semantics: a row may be described as not
found for an OEM query within the current snapshot scan limit. The summary must
not infer listing deletion, product unavailability, or stopped sales.

## Degraded states

- `FINDING_SET_MISSING`: no supported manifest exists;
- `FINDING_SET_INVALID`: manifest/child reconciliation or finding validation
  failed;
- `FINDING_SET_STALE`: an explicit caller policy marked an otherwise valid set
  stale;
- `SNAPSHOT_UNAVAILABLE`: required snapshot provenance is invalid or missing.

Missing or invalid source responses use `UNAVAILABLE` status and null counts;
they are not presented as a healthy zero-finding result.

## CLI

The builder reads database connection settings from the existing
`EFA_DB_HOST`, `EFA_DB_PORT`, `EFA_DB_NAME`, `EFA_DB_USER`, and
`EFA_DB_PASSWORD` environment contract. Optional arguments are:

- `--output PATH` for a local verification artifact;
- `--max-findings N`;
- `--freshness-threshold-seconds N`;
- `--freshness-grace-seconds N`.

The output artifact is runtime verification data and must remain untracked.
