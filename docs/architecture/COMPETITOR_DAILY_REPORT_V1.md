# Competitor Monitor Daily Report v1

## Boundary

The 16:00 AI Analyst process reads the persisted
`competitor_monitor_summary.v1` once through the approved `mcp_read` views. It
does not run the Collector, Snapshot Analyzer or Finding Engine and does not
read a JSON artifact or raw `public.competitor_*` relation.

The Summary read uses the Analyst's existing `efa_mcp_readonly` connection and
read-only transaction. Its three small SELECTs are isolated behind a nested
transaction/savepoint. A failure produces an unavailable competitor module and
does not fail the core Analyst report.

## Channel handoff

The Analyst appends a human-readable, version-marked `КОНКУРЕНТЫ` section to
the existing Markdown report. The 16:30 formatter parses that section once into
one presentation model and renders both channel variants:

- Email: snapshot/freshness, every IMPORTANT/WATCH item, at most one own
  restoration, aggregate competitor visibility, at most one price event,
  dynamic coverage and severity counts;
- Telegram: snapshot/freshness, every IMPORTANT/WATCH item, aggregate
  competitor visibility and at most one price event.

n8n remains transport-only and receives the existing single payload containing
`html` and `text`.

## Stable state rules

- Valid `NORMAL` with zero findings is always shown as: `Изменений,
  соответствующих правилам Finding Engine v1, не обнаружено.`
- Unavailable data is always shown as: `Данные мониторинга текущего цикла
  недоступны.` It is never represented as zero findings.
- `UNKNOWN` freshness is stated as `Свежесть: не определена.` Snapshot time is
  factual and remains visible; no current-day freshness is implied.
- Visibility wording retains the bounded observation semantics: `не найдена в
  пределах лимита текущего снимка`. It never claims that a listing disappeared,
  was deleted, left Ozon or stopped selling.
- Coverage and severity are read from the Summary DTO. The report introduces no
  second scoring algorithm.
