# Competitor Findings Persistence v1

## Purpose and scope

`Scripts/persist_competitor_findings_v1.py` persists an already approved Finding Engine v1 result. It does not rerun the Analyzer or Finding Engine, change severity, emit recommendations, close findings, or notify users. The writer is standalone and has no dependency on `services/competitor_collector/`.

The source artifact for the first controlled set is `COMPETITOR_T1_VS_T0_FINDINGS_V1.json`. It remains a runtime artifact outside Git.

## Safety mode

The default is `DRY_RUN`. A write requires all of the following:

1. `--write`;
2. `COMPETITOR_FINDINGS_WRITE_ENABLED=true`;
3. `--findings-sha256` equal to the approved raw artifact SHA-256;
4. `--analysis-sha256` equal to the canonical source-analysis SHA-256.

Environment configuration uses `EFA_DB_HOST`, `EFA_DB_PORT`, `EFA_DB_NAME`, `EFA_DB_USER`, and `EFA_DB_PASSWORD`. Credentials and DSNs are never printed.

Immediately after opening the psycopg2 connection, the writer calls
`psycopg2.extras.register_uuid(conn_or_curs=connection)`. PostgreSQL UUID
typecasters are scoped to that connection. Psycopg2 registers the Python
`uuid.UUID` input adapter process-wide by library design; this is acceptable
because the writer runs as a dedicated short-lived process and does not host
other application workloads. UUIDv5 identities remain UUID values through
parameter binding and are not converted or re-derived.

## Immutable hash gates

The approved first set has:

- raw findings SHA-256: `3202131a109e04c1a05dcb735f33190b75a76ab596bd6921fbafd7b7e0c8fbcd`;
- semantic SHA-256: `7fbf7c23a285749733d6beaaba7602701c3d47af04d793f0978a600fd5919e47`;
- analysis SHA-256: `99483c51928b7073f00cfc2f93c2fcafd52e25a94676774091b21740f24e03dd`.

The semantic projection contains, in canonical key-sorted JSON form with compact separators and one trailing LF:

- `contract_version`;
- `source_analysis_contract`;
- `source_analysis_sha256`;
- `previous_snapshot`;
- `current_snapshot`;
- `summary`;
- `findings`;
- `suppressed_events`.

The operational `production_read_only_check` field is deliberately excluded. Any semantic change fails the gate.

## Finding-set identity

The canonical identity document is:

```json
{
  "contract": "competitor-finding-set-persistence.v1",
  "finding_contract": "competitor_finding_set.v1",
  "previous_snapshot": {
    "source_kind": "BASELINE_V1",
    "derived_batch_id": "<previous derived batch id>"
  },
  "current_snapshot": {
    "source_kind": "SNAPSHOT_V1",
    "derived_batch_id": "<current derived batch id>"
  },
  "source_analysis_sha256": "<analysis sha256>",
  "finding_set_semantic_sha256": "<semantic sha256>"
}
```

Canonical serialization uses UTF-8, sorted keys, compact separators, JSON non-ASCII characters unchanged, non-finite numbers rejected, and one trailing LF. The key is:

```text
cm-finding-set-v1:<sha256(canonical identity bytes)>
```

For the approved T1 versus T0 set this independently produces:

```text
cm-finding-set-v1:097963f537b2a32a919d325698ca099889aa8ab08b4dbc8367e1e0684f520f7b
```

`finding_set_id` is `UUIDv5(NAMESPACE_URL, set_key)`.

## Finding identity

Each persisted finding identity contains:

- contract `competitor-finding-persistence.v1`;
- finding contract;
- previous source kind and derived batch ID;
- current source kind and derived batch ID;
- the Finding Engine `dedup_key`.

`query_text_exact` is not part of identity. One listing event represented by multiple OEM query contexts remains one row. The key and ID are:

```text
finding_key = cm-finding-v1:<sha256(canonical identity bytes)>
finding_id  = UUIDv5(NAMESPACE_URL, finding_key)
```

## Manifest mapping

One `competitor_finding_sets` row stores deterministic ID/key, all three contract versions, raw/semantic/analysis hashes, previous/current snapshot provenance, and expected finding count. `applied_at` and `created_at` use database defaults. Writer execution time is never substituted for factual snapshot timestamps.

The schema permits `expected_findings_count=0`. A zero-result successful cycle therefore persists one manifest and no child findings.

## Finding mapping

Each Engine finding becomes one immutable `competitor_findings` row. `topic` is the exact `finding_type`; kind, offer, metric, severity, confidence, and `PROPOSED` status are preserved. `product_family_id`, `listing_id`, observations, and offer are reconciled against PostgreSQL instead of being invented.

`first_detected_at` and `last_detected_at` both equal the current snapshot `reference_at` for this immutable event row. Database defaults supply `created_at` and `updated_at`.

### Scalar observation rule

- Exactly one query context: `old_observation_id` and `new_observation_id` contain the resolved UUIDs.
- More than one query context: both scalar IDs are NULL.

No primary query is selected for a multi-query finding.

## Evidence and details

`evidence` is an array with one item per exact query context. Every item stores query text and previous/current observation IDs, observation refs, source refs, raw refs, and run-level raw source refs.

`details` uses `competitor_finding_details.v1` and stores set key, finding type, engine dedup key, Ozon product ID, membership status, previous/current snapshots, metric values and deltas, the full query-context array, summary, and all source contract/hash provenance. Browser HTML, cookies, profiles, and session data are prohibited.

## Reconciliation

Before planning any insert, the writer verifies Migration 022 columns, constraints, and indexes. For every evidence side it re-resolves the observation UUID and checks:

- observation and listing existence;
- offer, exact query, and Ozon product ID;
- previous/current batch side;
- observation ref;
- source, raw, and raw-source refs.

It also verifies offer, listing, product-family, and membership resolution for each finding. Any mismatch aborts.

## History state machine

- `NEW_FINDING_SET`: no matching set key, snapshot-pair manifest, or planned finding key exists.
- `EXACT_ALREADY_APPLIED`: manifest and all child rows exactly equal the plan. No insert occurs.
- `PARTIAL_FINDING_SET_CONFLICT`: any partial, duplicate, pair, hash, key, count, set-link, or row-value mismatch. Processing aborts.
- Unrelated older finding sets are allowed.

The same rules cover zero-finding sets: an exact zero manifest is already applied; a missing one is new.

## Transaction contract

A future approved write uses one transaction:

1. acquire transaction-scoped advisory lock `efa-os:competitor-findings-persist:v1`;
2. repeat file and semantic gates;
3. validate schema and reconcile references;
4. determine history state;
5. insert one manifest;
6. insert exact child rows;
7. re-read and require exact equality;
8. commit.

Every error rolls back. There is no upsert, repair, merge, mutation of historical rows, or partial commit.

## Read model

Consumers select the latest successful set using the active finding contract and deterministic ordering such as `current_reference_at DESC, applied_at DESC, finding_set_id DESC`, then read children by `finding_set_id`. A manifest with count zero and no children means successful zero, not missing or failed.
