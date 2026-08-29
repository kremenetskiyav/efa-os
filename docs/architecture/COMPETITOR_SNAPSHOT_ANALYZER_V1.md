# Competitor Snapshot Analyzer v1

## Purpose and boundary

`Scripts/analyze_competitor_snapshots_v1.py` produces a factual, derived comparison of the latest two complete Competitor Monitor snapshot batches. It reads `competitor_search_runs`, `competitor_observations`, listings, and watchlist membership identity. It does not create findings, reviews, signals, or any database state.

The analyzer has no database write mode. PostgreSQL connections set `default_transaction_read_only=on`. Live read-surface counts are checked before and after analysis only as an in-memory operational consistency guard; they are not serialized into the canonical artifact. The only optional output is a local JSON report selected with `--output`.

## Snapshot pair resolution

The current schema does not persist the external batch reference on a search-run row. Analyzer v1 therefore derives batch identity deterministically from stored run facts:

1. Select only approved baseline and snapshot run families by exact `collection_ref` prefixes.
2. Order unique search runs by `captured_at`, then `collection_ref`.
3. Start a new group when the gap from the preceding run is greater than five minutes.
4. Require every group to contain exactly nine successful runs, nine unique `(offer_id, query_text_exact)` query identities, one region, and one collection-reference family.
5. Select the latest complete group as `CURRENT` and the immediately preceding complete group as `PREVIOUS`.
6. Hash the sorted stored collection references to produce a reproducible `derived_batch_id`.

The derived identifier is not presented as the original external batch reference. An incomplete, duplicated, mixed-region, mixed-family, failed, or otherwise ambiguous group is a contract error; the analyzer stops instead of guessing. Selection is based on captured run history, not calendar dates.

## Comparison identity and reconciliation

The canonical logical observation slot is:

```text
offer_id + query_text_exact + ozon_product_id
```

Observation UUIDs are not comparison identity. A duplicate logical slot inside either snapshot is rejected. The union of previous and current slot keys is classified as:

- `CONTINUING_SLOT`: present in both snapshots;
- `NEW_SLOT`: present only in current;
- `RETIRED_SLOT`: present only in previous.

A retired historical slot is not converted to an ordinary not-found observation. Membership status, including `CONTROL`, is retained as a factual dimension.

## Factual comparison dimensions

Stored observation status is mapped only to `FOUND` or `NOT_FOUND_WITHIN_SCAN_LIMIT`. The latter does not mean unavailable or delisted. Continuing-slot visibility transitions are:

- `STILL_VISIBLE`;
- `DROPPED_OUT`;
- `REAPPEARED`;
- `STILL_NOT_FOUND`.

Rank, price, rating, reviews, purchase indicator, availability, and product facts are compared only under their explicit field contracts:

- Rank delta is `current - previous`; negative is `IMPROVED`, positive is `WORSENED`. No synthetic rank is assigned.
- `bank_price`, `other_payment_price`, and `old_price` are independent dimensions. There is no combined price field. Percent delta exists only when the previous value is greater than zero.
- `old_price` remains a marketing/reference observation; null is not zero.
- Rating and observed review count require non-null values on both sides. Review count remains scope `UNKNOWN` and is not represented as a seller-specific fact.
- Purchase count is an observed indicator, not confirmed orders or sales. A changed raw indicator without two parsed counts is `RAW_CHANGED`, without a numeric delta.
- Availability is independent from visibility. A not-found observation is never interpreted as unavailable.
- Changes in observed OEM, dimensions, carbon, or origin fields are `PRODUCT_FACT_DRIFT`, not ordinary market movement and not a causal conclusion.

Comparisons retain previous/current quality statuses and flags. Two valid found observations yield `VALID`; visibility transitions involving not-found facts yield `VISIBILITY_ONLY`; unsupported or partial states are `NOT_COMPARABLE`.

## Output contract

The report contract is `competitor_snapshot_analysis.v1` and contains:

- metadata for the previous and current derived snapshot batches;
- deterministic Analyzer input coverage through the selected current snapshot: distinct eligible search runs and observations, with canonical `reviews=0` and `findings=0` because neither mutable downstream table is an Analyzer input;
- slot reconciliation and dimension summaries;
- per-SKU summaries for monitored SKUs, with `УФ 003Б` explicitly marked `NO_ACTIVE_MONITORING`;
- a separate `CONTROL` membership summary;
- one factual comparison object per reconciled logical slot.

All summary dimensions must total `slots_total`. Per-SKU slot totals must also equal `slots_total`. Analyzer validation rejects duplicates and summary mismatches. Standalone Analyzer and Daily Cycle use the same deterministic source-count helper, so later review or finding persistence cannot change Analysis v1 bytes.

## Safety and non-goals

Analyzer v1 contains only read queries and has no dependency on `services/competitor_collector`. It does not:

- modify snapshots, observations, watchlist, listings, or other source facts;
- create findings, reviews, signals, scores, recommendations, or causal interpretations;
- perform Ozon collection;
- perform repair, upsert, or schema changes;
- commit or publish its local runtime artifact.

Finding rules and business scoring are deliberately deferred to a separate reviewed stage.
