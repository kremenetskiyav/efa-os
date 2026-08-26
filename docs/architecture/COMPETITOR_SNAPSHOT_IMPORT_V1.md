# Competitor Snapshot Import v1

Status: implementation contract for factual snapshots T1+.

This contract is separate from the one-shot baseline T0 contract. The snapshot
importer records facts only. Comparison, deltas, signals, reviews, findings,
issues, recommendations, and selection of the official daily run belong to
later stages.

## Scope and artifacts

Every snapshot is represented by two immutable JSON artifacts:

- Evidence: `competitor_snapshot_evidence.v1`;
- Payload: `competitor_snapshot_payload.v1`;
- mode: `SNAPSHOT` in both artifacts.

Recommended names are
`COMPETITOR_SNAPSHOT_EVIDENCE_<UTC_TIMESTAMP>.json` and
`COMPETITOR_SNAPSHOT_PAYLOAD_<UTC_TIMESTAMP>.json`. Identity never depends on
the filename.

Evidence contains source records: successful batch state, search evidence,
ordered cards, product-page enrichment evidence, exact per-record timestamps,
structured price evidence, source URLs, and raw evidence keys. Payload contains
only normalized factual rows in `batch`, `search_runs`, `observations`, and
`enrichments`. Top-level `signals` and `findings` must both be empty.
Comparison prices and delta fields are forbidden.

The payload batch embeds the exact SHA-256 of the Evidence artifact.
`reference_at` is derived-only and is not persisted in the artifact. The exact
rule is:

> `reference_at = min(parse_timestamp(run["captured_at"]) for run in
> payload["search_runs"])`.

This is the single time used to reconstruct the historical reference layer. DB
`created_at` and orchestration metadata `batch.search_phase_started_at` are
never the snapshot reference time. A stored `batch.reference_at` is rejected so
the derived rule cannot conflict with artifact metadata.

Canonical JSON bytes are:

```python
json.dumps(
    value,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
).encode("utf-8")
```

## Evidence and normalized fact validation

Evidence keys are globally unique. Search identities `(offer_id, exact query)`
and ordered-card product IDs within a search are unique. Every
`raw_source_ref` resolves to its exact search evidence record. Every FOUND
`raw_ref` resolves to one COMPLETE product enrichment record for the same Ozon
product. Normalized values must equal their source evidence values.

### Actual v1 artifact mapping

The first immutable T1 artifacts define the canonical v1 field shape. There is
no legacy `query` alias and no synthetic compatibility layer.

| Actual T1 field | Importer semantic / DB field |
| --- | --- |
| `evidence.search_evidence[].query_text_exact` | Exact OEM query |
| `payload.search_runs[].query_text_exact` | Run query and deterministic run identity |
| `payload.search_runs[].captured_at` | Run `captured_at`; minimum across runs is derived `reference_at` |
| `evidence.search_evidence[].ordered_cards[].ordinal` | FOUND `position_on_page`; reconciled with card `rank` |
| `evidence.search_evidence[].ordered_cards[].ad_marker_raw` | FOUND `ad_flag = ad_marker_raw is not null` |
| Card `rating_parsed`, `reviews_count_parsed` | Observation rating and review count |
| Card `price_text`, `availability_raw` | Evidence-only search facts; never product-price fallback |
| `payload.search_runs[].cards_scanned` | Exact ordered-card count validation |
| Missing `page_count_observed` | DB `page_count_observed=NULL`; no page count is invented |
| `payload.observations[].raw_ref` | Immutable product-enrichment resolution |
| `payload.enrichments[].currency` | FOUND DB `currency` |
| `payload.enrichments[].source_ref` | FOUND DB `source_ref` |
| `payload.enrichments[].availability_raw` | FOUND DB `availability_raw` |
| Referenced search evidence `source_url` | NOT_FOUND DB `source_ref` |
| NOT_FOUND without enrichment | DB `currency=NULL`, `availability_raw=NULL` |
| `price_evidence.visible_price_elements[].classification` | Canonical structured price classification |
| Visible classified `₽` elements | Deterministic proof for normalized `currency=RUB` |
| Top-level `signals`, `findings` | Both must be empty arrays |

Observation-level `currency`, `source_ref`, and `availability_raw` are
derived-only DB mapping fields and are forbidden in the v1 observation object.
They may only come from the exact normalized enrichment or search evidence
listed above, never from the static DB registry.

Supported old-price classifications are:

- `OLD_PRICE_PRESENT`: extraction is COMPLETE; `old_price` equals a structured
  visible OLD_PRICE element;
- `OLD_PRICE_EXPLICITLY_ABSENT`: extraction is COMPLETE, `old_price` is null,
  and no structured OLD_PRICE element exists;
- `AMBIGUOUS_PRICE_SECTION` and `PRICE_SECTION_FAILED`: recognized evidence
  states, but not valid proof for the required prices of a FOUND observation.

Search price is never a fallback for bank, other-payment, or old price.
Structured price elements use the canonical key `classification` with values
`BANK_PRICE`, `OTHER_PAYMENT_PRICE`, `OLD_PRICE`, and
`UNKNOWN_PRICE_ELEMENT`.

FOUND requires positive rank/page/position, `reviews_scope=UNKNOWN`, exact
search timestamp and card facts, exact enrichment timestamp and product facts,
resolved raw evidence, and `quality_status=VALID`. Page 1 is not hardcoded.

`NOT_FOUND_WITHIN_SCAN_LIMIT` is a real observation slot. Rank, page, position,
ad flag, rating, review count, enrichment timestamp, prices, currency, seller
facts, purchase facts, raw availability, OEM, dimensions, origin/carbon facts,
and `raw_ref` are null. `reviews_scope=UNKNOWN`,
`availability_status=UNKNOWN`, `quality_status=NOT_FOUND`, and `quality_flags`
contains `NOT_FOUND_WITHIN_SCAN_LIMIT`. Its DB `source_ref` is derived from the
exact search evidence source URL. Rank zero is invalid.

Search and enrichment timestamps remain separate. One product enrichment may
prove multiple OEM observation slots within the same snapshot.

## Idempotency and deterministic identifiers

Idempotency contract: `cm-snapshot-idempotency.v1`.

Batch identity is canonical JSON of:

```json
{
  "contract": "cm-snapshot-idempotency.v1",
  "evidence_sha256": "<exact evidence hash>",
  "payload_sha256": "<exact payload hash>"
}
```

`batch_ref` is `cm-snapshot-v1:batch:<sha256(identity)>`.

Run identity is canonical JSON of `batch_ref`, exact `offer_id`, `query_kind`,
and `query_text_exact`. `collection_ref` is
`cm-snapshot-v1:run:<sha256(identity)>`.

Observation identity is canonical JSON of `collection_ref` and decimal-string
`ozon_product_id`. `observation_ref` is
`cm-snapshot-v1:observation:<sha256(identity)>`.

Primary keys are UUIDv5 in `uuid.NAMESPACE_URL` over the corresponding canonical
reference. UUIDv4 is forbidden. Multiple same-day snapshots are allowed: a
different immutable artifact pair produces a different batch identity.

## Membership at time

Expected logical observation slots are derived at `reference_at` from joined
watchlist membership, listing/family relationship, `matched_oem_set`, and the
historically applicable SKU/OEM row. Membership validity is half-open:

```text
valid_from <= reference_at
AND (valid_to IS NULL OR reference_at < valid_to)
```

Monitored statuses are PRIMARY, RESERVE, and CONTROL; EXCLUDE is omitted. An OEM
row must belong to the same offer, match the exact normalized OEM, and have
`created_at <= reference_at`. Its current `active` flag is not used to rewrite
historical applicability. The historically valid membership's
`matched_oem_set` is the material applicability record because schema 021 has no
OEM validity-end column.

Current profile state is not a historical shortcut. A HOLD or inactive SKU is
absent only when the reference layer at the snapshot time supplies no monitored
membership slots. The importer hardcodes neither a SKU nor query/slot counts.
The production reference currently derives 9 OEM queries and 87 logical slots;
an approved future watchlist may derive different counts.

The payload must contain exactly one observation for every derived
`(offer_id, query_text_exact, ozon_product_id)` slot and no extras.

## History state machine

Only exact refs for the current artifact pair participate. T0 and previous
valid snapshot history are unrelated and allowed.

- `NEW_BATCH`: none of the planned current-batch refs exist; ready to apply.
- `EXACT_ALREADY_APPLIED`: every planned run and observation exists and every
  persisted factual field equals the plan; zero inserts.
- `PARTIAL_BATCH_CONFLICT`: a subset exists, a set is incomplete, or any factual
  field differs; abort without repair.
- `REFERENCE_CONFLICT`: artifact slots or facts do not reconcile with the
  historical reference/schema contract; abort.

Refs-only equality is insufficient. There is no repair, upsert, or partial
continuation.

## Database mapping

Schema 021 is sufficient; no migration is required.

The only target tables are:

- `public.competitor_search_runs` — one row per derived OEM query;
- `public.competitor_observations` — one factual row per derived logical slot.

`captured_at` values are artifact facts. `enrichment_captured_at` is separately
preserved. Table `created_at` remains technical insertion time. The importer
does not write reviews, findings, memberships, listings, families, profiles,
OEM registry, baseline rows, or orchestration state.

## Dry-run, write gates, transaction, and concurrency

Dry-run is the default and uses a read-only DB connection. A future write needs
all of:

- `--write`;
- `COMPETITOR_SNAPSHOT_WRITE_ENABLED=true`;
- `--payload-sha256 <exact>`;
- `--evidence-sha256 <exact>`.

The baseline write gate is not accepted. DB configuration uses only
`EFA_DB_HOST`, `EFA_DB_PORT`, `EFA_DB_NAME`, `EFA_DB_USER`, and
`EFA_DB_PASSWORD`; credentials and DSNs are never logged.

The write transaction is:

1. acquire transaction-scoped advisory lock
   `efa-os:competitor-snapshot-import:v1`;
2. re-read and hash both artifacts;
3. validate Evidence and Payload plus their linkage;
4. reconstruct and reconcile the reference layer at `reference_at`;
5. determine current-batch history state;
6. insert search runs;
7. insert observations;
8. reconstruct references and assert exact persisted factual equality;
9. commit.

Any mismatch rolls back. SQL contains no `ON CONFLICT`, UPDATE, DELETE, repair,
or upsert. Existing baseline and previous snapshots are never modified.

## Implementation boundary

Implementation: `Scripts/import_competitor_snapshot_v1.py`.

Focused synthetic tests:
`Scripts/tests/test_import_competitor_snapshot_v1.py`.

The implementation has no runtime dependency on the baseline importer or the
untracked Collector implementation. Its minimal fixture uses the exact field
names and nesting of the immutable T1 Evidence/Payload contracts without
embedding the real market dataset. Real artifacts remain outside Git and are
hash-gated before every dry-run or controlled write.
