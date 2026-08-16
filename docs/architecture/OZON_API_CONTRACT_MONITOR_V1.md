# Ozon API Contract Monitor v0.1

This is the API-specific adapter inside the common Information Intelligence
architecture documented in `OZON_INFORMATION_INTELLIGENCE_V1.md`.

## Boundary

The first Information Intelligence component monitors only the official Ozon
Seller and Performance OpenAPI documents. It makes public unauthenticated GET
requests, never calls business APIs, and cannot change Ozon, n8n or PostgreSQL.

Canonical sources:

- `SELLER_API_OPENAPI`: `https://docs.ozon.ru/api/seller/swagger.json`
- `PERFORMANCE_API_OPENAPI`: `https://docs.ozon.ru/api/performance/swagger.json`

Retrieval is one-shot with no retry loop. Anti-bot or redirect failure is
`SOURCE_UNAVAILABLE`; browser/session emulation is prohibited. An approved
manual bootstrap may place a compressed raw snapshot outside Git and pass its
reference to the future persistence layer.

The operator can validate such an official file without persistence:

```text
python -m services.information_intelligence.bootstrap --source-id SELLER_API_OPENAPI --file <outside-git-file>
```

## Contract normalization and changes

Raw SHA-256 proves exact bytes. Canonical SHA-256 is calculated from parsed
JSON with sorted object keys, insignificant whitespace removed and arrays left
in source order. The structural representation retains paths, methods,
operation IDs, parameters, request bodies, responses, schemas and security.

The first valid observation is `BASELINE_CREATED`. It is not a change event.
An equivalent later observation is `SUCCESS_ZERO` / `NO_CHANGE`. Structural
changes are classified as `NON_BREAKING`, `BREAKING` or `REVIEW`; text-only
metadata is `INFO_ONLY`. A changed element is routed only to EFA-OS components
whose versioned usage map contains that endpoint or field.

## Storage and evidence

Migration `008_information_intelligence_v1.sql` is prepared but not applied.
It separates source registry, immutable distinct contract snapshots, poll
checks/freshness and immutable change events. PostgreSQL stores normalized
structure and hashes, not repeated raw OpenAPI documents. Raw evidence is kept
as compressed local files outside Git with an evidence reference and hash.

Failure statuses are `SOURCE_UNAVAILABLE`, `HTTP_FAILED`, `PARSE_FAILED`,
`DIFF_FAILED`; a failed check never replaces the last good baseline.

## Future orchestration

Recommended cadence is once daily at 06:30 Europe/Moscow, before collectors and
the Daily Brief. API contracts change slowly and this avoids needless traffic.
n8n will orchestrate the private Python monitor only after migration review,
backup and controlled deployment. A future prepared brief payload may contain:

```json
{"seller_api":"NO_CHANGE","performance_api":"ACTION_REQUIRED","affected":["CPCDAILYV1"],"reason":"response schema changed"}
```

No LLM evaluates hashes, compatibility or severity.
