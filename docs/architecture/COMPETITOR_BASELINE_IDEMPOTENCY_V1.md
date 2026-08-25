# Competitor Baseline Idempotency Contract v1

This specification defines deterministic identities for the first Competitor
Monitor baseline. It does not change the payload or evidence contracts and does
not make market-data artifacts part of Git.

## Canonical JSON

Identity documents use the logical equivalent of:

```python
json.dumps(
    value,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
).encode("utf-8")
```

The result has no BOM or trailing newline. Unicode is not additionally
normalised. Ozon product identifiers are decimal strings, not JSON numbers.

## Identities

The identity contract is `cm-baseline-idempotency.v1`.

The batch identity document contains `contract`, `evidence_sha256`, and
`payload_sha256`. Its reference is
`cm-baseline-v1:batch:<sha256(canonical-document)>`.

Each run identity contains `batch_ref`, `offer_id`, `query_kind`, and
`query_text_exact`. Its reference is
`cm-baseline-v1:run:<sha256(canonical-document)>`.

Each observation identity contains `collection_ref` and the decimal-string
`ozon_product_id`. Its reference is
`cm-baseline-v1:observation:<sha256(canonical-document)>`.

PostgreSQL primary keys are deterministic UUIDv5 values in
`uuid.NAMESPACE_URL`, derived from the corresponding run or observation ref.

## Replay states

- `EMPTY_HISTORY`: all four competitor history tables are empty; the first
  baseline is ready to apply.
- `EXACT_ALREADY_APPLIED`: all 9 run refs and 87 observation refs exist and all
  persisted factual values match the plan; no inserts are allowed.
- `PARTIAL_HISTORY_CONFLICT`: any partial set, unrelated history, or factual
  mismatch aborts the importer. Repair and upsert are forbidden.

A future write uses one PostgreSQL transaction and a transaction-scoped
advisory lock dedicated to this importer. Hash, history, static reference, and
post-insert checks are performed inside the transaction; every mismatch rolls
the transaction back.
