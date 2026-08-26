# Competitor Finding Engine v1

## Boundary

`Scripts/generate_competitor_findings_v1.py` converts an approved `competitor_snapshot_analysis.v1` report into a compact factual `competitor_finding_set.v1` dry-run. It has no database write path. PostgreSQL is used only to re-resolve source observation provenance through a connection configured with `default_transaction_read_only=on`.

Finding Engine v1 does not persist findings, reviews, signals, workflow state, or source facts. It does not collect Ozon pages and has no dependency on `services/competitor_collector`.

## Inputs and provenance resolution

The source analysis is validated for contract version, unique logical slots, snapshot identity, and optional required SHA-256. The archived analysis intentionally omits production observation UUIDs, so the engine reads factual history and reuses the approved Analyzer batch contract to select the same previous/current batches.

Production evidence is indexed by:

```text
offer_id + query_text_exact + ozon_product_id
```

Every expected side of every analysis slot must resolve to exactly one observation. Missing slots, duplicate logical slots, duplicate observation UUIDs, batch mismatch, or listing identity changes are contract errors. The engine does not guess or emit untraceable findings.

Each emitted finding retains:

- production listing UUID;
- old/new observation UUID and observation reference for every query context;
- source, raw, and run-level raw-source references where stored;
- snapshot batch identity and reference time;
- all OEM-specific status, rank, price, review, and quality context.

Reference fields are retained without loading archived browser content.

## Finding identity and query deduplication

One physical monitored entity is:

```text
offer_id + ozon_product_id
```

Finding identity is:

```text
finding_type + offer_id + ozon_product_id
```

`query_text_exact` is deliberately excluded from `dedup_key`. All monitored OEM-query facts are preserved in `query_context[]`, including mixed query visibility and rank behavior.

## Included taxonomy

Finding Engine v1 emits only:

| Finding type | Kind | Default severity | Confidence |
|---|---|---|---|
| `OWN_SEARCH_VISIBILITY_LOST` | `ISSUE` | `WATCH` partial / `IMPORTANT` full | `MEDIUM` partial / `HIGH` full |
| `OWN_SEARCH_VISIBILITY_RESTORED` | `SIGNAL` | `INFO` | `MEDIUM` partial / `HIGH` full |
| `COMPETITOR_VISIBILITY_LOST` | `SIGNAL` | `INFO` | `MEDIUM` |
| `COMPETITOR_VISIBILITY_RESTORED` | `SIGNAL` | `INFO` | `MEDIUM` |
| `COMPETITOR_PRICE_INCREASED` | `SIGNAL` | `INFO` | `HIGH` |
| `COMPETITOR_PRICE_DECREASED` | `SIGNAL` | `INFO` | `HIGH` |

All dry-run findings use `status=PROPOSED`.

## Visibility rules

Listing-level visibility uses `previous_any_found` and `current_any_found` across every query context.

- Competitor lost: previous any found and current none found.
- Competitor restored: previous none found and current any found.
- A competitor that remains found in another query does not emit a listing-level visibility finding; the query event is recorded as suppressed noise.
- A CONTROL listing may emit a partial `OWN_SEARCH_VISIBILITY_LOST` when some query contexts drop while another remains found.
- A CONTROL query reappearance emits `OWN_SEARCH_VISIBILITY_RESTORED`.
- New or retired watchlist slots do not become visibility findings.

All language states only that search visibility was or was not observed within monitored OEM queries and the scan limit. It never claims deletion, delisting, unavailability, or cessation of selling.

## Price rules

Price findings apply only to `PRIMARY` and `RESERVE` listings with valid found-to-found comparison evidence, positive previous bank price, consistent previous/current bank values across comparable query contexts, one currency, and non-conflicting other-payment evidence.

The finding is listing-level even when the same change appears in several queries. Any proven increase or decrease is emitted as `INFO`; v1 has no materiality threshold. `old_price` is contextual only. CONTROL price changes are out of scope. Conflicting query prices are suppressed rather than collapsed into a scalar.

## Explicit non-goals

V1 does not emit findings for:

- rank movement;
- observed review-count movement;
- product-fact drift;
- availability interpretation from not-found observations;
- threat, opportunity, or weighted scoring;
- pricing recommendations;
- hysteresis or open/closed lifecycle state.

These source facts remain in query context where applicable. `reviews_scope` remains unchanged, including `UNKNOWN`.

## Output and validation

The deterministic `competitor_finding_set.v1` report contains source analysis identity, snapshot metadata, findings, suppressed events, and summaries by type, severity, membership, and suppression reason.

Validation requires unique dedup keys, exact taxonomy mapping, traceable old/new observation UUIDs for every query context, safe wording, complete summaries, and absence of deferred metric findings. Production table counts are checked before and after generation and must be identical.

The optional `--output` flag writes only a local JSON dry-run artifact. It does not authorize or perform database persistence.
