# Ozon Information Intelligence v0.1

## Source strategy and boundary

All sources produce the same durable `OzonInformationEvent` contract. There is
no parallel event architecture for API, legal, news or manual evidence.

Automated official-source priority is:

1. Ozon Legal / Contract documents;
2. Ozon Seller News;
3. Ozon for dev;
4. Seller and Performance API contract monitoring.

The seller-specific Ozon Seller `Главное` hub is a high-value
`MANUAL_EVIDENCE_SOURCE` for v0.1. A supported pull API was not found, Seller
push covers operational events and hub coverage is unproven. UI scraping,
browser/session emulation, undocumented endpoints and a public webhook are
prohibited. Gmail inbound is future research only.

The confirmed Seller News listing is
`https://seller.ozon.ru/media/news/`. Its first one-shot public retrieval
returned HTTP 307 and is `SOURCE_UNAVAILABLE`; no redirect or anti-bot bypass
is permitted. Article identity, pagination and live DOM/feed contracts are
therefore not claimed. The v0.1 adapter is `MANUAL_ONLY`: an operator may
provide a JSON manifest outside Git containing an official Ozon permalink,
title, publication date, optional update/category/official links and captured
article HTML/text. The fallback preview validates official HTTPS URLs,
canonicalizes semantic content, strips tracking parameters and persists
nothing. Automated Seller News polling is not active.

## Legal source registry

`OZON_SELLER_AGREEMENT` is the confirmed canonical Level-1 source at
`https://docs.ozon.ru/legal/partners/logistics/contract/`. It can cover seller
agreement, FBS/FBO, commission/remuneration, logistics, returns, settlement
and document-flow clauses. Its document exposes revision/effective markers and
may link a previous version. Applicability of a retrieved revision to the EFA
seller account must be validated from the document itself; the registry marks
this `NEEDS_ACCOUNT_APPLICABILITY_CONFIRMATION` rather than assuming it.

Separate canonical URLs for promotion/discount/seller-points terms,
Performance advertising terms and legal-entity buyout terms are deliberately
`NEEDS_SOURCE_CONFIRMATION`. The registry does not invent URLs or substitute
third-party copies.

Retrieval is one unauthenticated official HTTP request per source, without
retry, cookies, Seller credentials or anti-bot bypass. A valid response records
HTTP status, content type, raw byte size, retrieval time and raw SHA-256.
Redirect/anti-bot failure is `SOURCE_UNAVAILABLE` and never replaces the last
good baseline.

## Manual bootstrap and evidence

When public retrieval is blocked, an operator may save the official HTML or
plain-text document outside Git under a user-local EFA OS import directory and
run:

```text
python -m services.information_intelligence.legal_bootstrap --source-id OZON_SELLER_AGREEMENT --file <outside-git-official-file>
```

The preview rejects empty, corrupt, unsupported and recognisable anti-bot
pages. Official PDF input is supported only where it has a usable text layer;
OCR is deliberately not enabled. It validates and canonicalizes the document
but performs no PostgreSQL write. Raw evidence should later be retained, compressed where useful, under a
user-local EFA OS evidence directory. PostgreSQL stores source metadata,
hashes, normalized structure, events and the external evidence reference—not
unnecessary repeated blobs.

Manual seller-hub evidence uses the same snapshot/event records. Snapshot
metadata can carry channel, observed date, title, manual reference, linked
official URLs and domains; the raw/canonical hash proves captured text.
Independent hub and legal evidence may correlate by canonical URL, title,
effective date, domains and watch concepts but must not be deduplicated away.
Screenshot OCR is outside v0.1.

## Canonicalization and structural diff

Raw SHA-256 proves transport bytes. Canonical SHA-256 represents semantic HTML
or plain text after removing safe presentation noise: navigation/chrome,
scripts/styles, generated attributes and insignificant whitespace. Headings,
paragraphs, numbered clauses, lists, table rows/cells, amounts, percentages,
dates, deadlines, formulas and document markers remain intact.

Units are identified using clause number when present, otherwise heading path,
kind and normalized position. Content fingerprints detect modifications;
semantic fingerprints support movement/renumbering. Legal changes are
`ADDED`, `REMOVED`, `MODIFIED`, `MOVED_OR_RENUMBERED` or `UNKNOWN`. No LLM
determines equality.

The numeric detector emits structured old/new percentage, RUB amount,
coefficient, date, deadline and threshold changes with delta where meaningful.
Economic watch concepts are `OZON_FUNDED_POINTS`, `SELLER_COMMISSION`,
`FBS_LOGISTICS`, `RETURN_LOGISTICS`, `PROMOTION_ECONOMICS`,
`PERFORMANCE_ADVERTISING_TERMS`, `FINANCE_SETTLEMENT`,
`LEGAL_ENTITY_BUYOUT`, `DOCUMENT_FLOW` and `PAYMENT_TIMING`.

Impact routing is review-only. It can request Profit/Price/Commercial Revenue,
FBS, promotion, CPC, finance, documents or return-reserve review. Legal/tax
wording routes to `TAX_REVIEW_ONLY`. Nothing mutates Profit, Price or Tax
Engine.

Severity is common across Information Intelligence: `INFO`, `WATCH`,
`ACTION_REQUIRED`, `CRITICAL`. A watched semantic change is `WATCH`; a watched
numeric change is `ACTION_REQUIRED`; `CRITICAL` requires explicit evidence
that an effective-now change invalidates active economics.

## Persistence, failures and future orchestration

Migration 008 is applied. Its four normalized tables now
support API and legal snapshots, checks/freshness, numeric legal changes, news
events and manual evidence through the common event model.

States are `SUCCESS`, `SUCCESS_ZERO`, `BASELINE_CREATED`,
`SOURCE_UNAVAILABLE`, `HTTP_FAILED`, `PARSE_FAILED`, `CONTRACT_CHANGED`,
`DIFF_FAILED`, `STALE`. No change is `SUCCESS_ZERO`; failed checks preserve the
last good snapshot.

If deterministic Seller News retrieval later becomes available, its candidate
polling time is 06:20 Europe/Moscow between Legal Monitor at 06:15 and API
Monitor at 06:30, before the 08:15 Daily Brief. No workflow or schedule exists
yet. A future
deterministic brief fragment may be:

```json
{
  "section": "OZON RULE CHANGES",
  "severity": "ACTION_REQUIRED",
  "title": "FBS logistics tariff changed",
  "old_value": "130 RUB",
  "new_value": "145 RUB",
  "effective_date": "2026-08-20",
  "affected": ["Profit Engine", "Price Engine"],
  "action": "RECALCULATION_REQUIRED"
}
```

Daily Brief would consume prepared deterministic events; it would not crawl or
use an LLM to derive changes.
