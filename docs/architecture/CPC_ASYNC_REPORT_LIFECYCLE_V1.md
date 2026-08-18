# CPC Async Report Lifecycle v1

## Purpose

Ozon Performance CPC reports are asynchronous. A single long-running n8n
execution must not create a report, wait, repeatedly poll it and fail merely
because the external state is still `NOT_STARTED` or `IN_PROGRESS`.

The production lifecycle is split into two workflows backed by the existing
`cpc_collection_runs` table.

## Create stage

`CPCDAILYV1` remains scheduled for 07:30 `Europe/Moscow`.

1. Build the target `business_date`.
2. Reserve that date transactionally in `cpc_collection_runs`.
3. Stop successfully when a `PENDING`, successful, failed or stuck lifecycle
   already exists.
4. Only a new reservation may read the current CPC/SKU campaign list and
   create one Performance report.
5. Register the returned UUID and campaign snapshot, then end successfully.

The unique `business_date` and non-null `report_uuid` indexes, plus a
transaction-scoped advisory lock, prevent duplicate creation. A crash between
reservation and UUID registration leaves a visible pending reservation; it
does not silently create a replacement.

## Poll stage

`CPCREPORTPOLLERV1` is the separate ten-minute poller. It claims at most one
pending lifecycle with `FOR UPDATE SKIP LOCKED` and a five-minute lease. One
poll cycle makes one status request for the existing UUID and never creates a
report.

- `NOT_STARTED`, `IN_PROGRESS` -> remain `PENDING`.
- `OK`, `COMPLETE`, `COMPLETED` -> download and persist through the existing
  normalized CPC path.
- Any terminal or unsupported external state -> `FAILED` with deterministic
  error metadata.
- Pending for two hours -> `STUCK`; no replacement is created automatically.

The ready lease is retained until transactional CPC persistence completes.
If download or persistence is interrupted, the lease expires and a later poll
may safely retry the same UUID.

## Durable state

`lifecycle_state` is authoritative:

- `PENDING`
- `SUCCESS_ZERO`
- `SUCCESS_NONZERO`
- `FAILED`
- `STUCK`

The existing lowercase `status` column remains a compatibility signal for the
current Daily Brief: only final successful lifecycles have `status='success'`.
This preserves existing freshness behaviour without changing the Daily Brief.

`cpc_advertising_daily` remains detail-only. A ready report with no details is
`SUCCESS_ZERO`; no synthetic zero rows are created.

## Operational attention

`FAILED` and `STUCK` store `error_code`, `error_message` and
`attention_reason`. No new email or Telegram alert subsystem is introduced.
Replacement of a stuck report requires an explicit owner-approved recovery
policy.
