# Control Center V3

Read-only owner dashboard for W00–W08. W06 owns financial results; W00
routes and presents them; W07 reports structural audit results. An audit PASS
is not proof of settlement or source truth. No production deployment is performed
by this repository release.

## Runtime and inputs

The active runtime uses Python 3.11+ and its standard library. Start locally:

```powershell
python -X utf8 services/control-center/app.py --host 127.0.0.1 --port 8091
```

Alternatively use `services/control-center/run-local.ps1`. The existing
`requirements.txt` supplies asyncpg for archived compatibility paths; it is not
required by the active V3 home page or finance API.

`EFA_OZON_AGENTS_ROOT` defaults to `<repository>/OZON_AI_AGENTS`. Reports also
come from its adjacent `../REPORTS` directory. The dashboard reads structured
W06 JSON snapshots and bounded report/policy Markdown files. Missing sources
remain unknown; runtime requests do not collect or publish data.

Active dependency chain:

```text
app.py -> read_model.py -> w06_snapshot.py -> finance_model.py
app.py -> current_finance.get_snapshot -> w06_snapshot.py
```

`finance_model.py` supplies period options and presentation metadata. Active
finance reads do not invoke the historical economics parser. The primary input
is `REPORTS/W06/SNAPSHOTS/CURRENT_FINANCE_SNAPSHOT_V1.json` under the data root.
Dated `YYYY-MM-DD/W06_FINANCE_SNAPSHOT_*.json` files are searched for the exact
requested preset and inclusive date bounds. Newer valid matching snapshots
supersede older matching candidates. Invalid primary data fails closed.

The [W06 contract](../../docs/contracts/EFA_W06_FINANCE_SNAPSHOT_V1.md) and
[JSON schema](../../docs/contracts/efa_w06_finance_snapshot.v1.schema.json)
define the provider boundary. Runtime validation is implemented in
`w06_snapshot.py`; those documentation files are not opened on each request.
The W06 XLSX producer/publisher is a separate upstream workflow and is not
shipped with the consumer release.

The UI keeps demand, order-cohort economics, account advertising, cost proxy
and settlement separate. Missing settlement profit stays null; account
advertising is not allocated to SKU. Freshness and exact period coverage come
from the provider evidence, not from the time the dashboard was loaded.

## HTTP interface

- `/`: owner dashboard.
- `/api/status`: W00–W08 read model and W06 provider status.
- `/api/finance?period=CURRENT_MONTH`: finance snapshot; supported presets also
  include TODAY, YESTERDAY, LAST_7_DAYS, LAST_30_DAYS, PREVIOUS_MONTH, AUGUST_2026.
- Existing source/report drill-down routes render bounded local evidence.
- POST is rejected; the dashboard exposes no execution or publication action.

Active routes do not query PostgreSQL, MCP, n8n, OPFINDailyV1 or collector health.
Archived detail routes and compatibility tests retain lazy imports of existing
`Scripts/format_ai_analyst_email.py` and
`Scripts/build_competitor_monitor_summary_v1.py`. `finance_source.py` remains
for tests of the retired adapter; it is not imported by active snapshot reads.
These helpers do not require deployment changes for V3.

## Verification

Run from the repository root:

```powershell
python -X utf8 -m unittest discover -s services/control-center/tests -v
python -X utf8 -m compileall -q services/control-center
node --check services/control-center/static/app.js
node --check services/control-center/static/capabilities.js
git diff --check
```

The release suite contains 137 tests, including compatibility regressions, and
uses temporary fixtures rather than private reports or XLSX exports. Three
upstream XLSX producer tests were moved intact to its local
`test_current_period_builder.py`; that producer and its tests are outside this
consumer release. No assertion was removed from those producer checks.

## Selective deployment

[deploy-manifest.json](deploy-manifest.json) is the exact versioned file
allowlist: eight runtime files and two contract files. Its remaining sections
identify data roots, input discovery patterns, optional archived dependencies,
preflight and rollback requirements. It contains no credentials or financial
records. README, tests, local launcher and retained test adapters belong to the
release source but need not be copied to the running service.

Only an independently authorized deployment may transfer the allowlisted files
from the release commit, after backing up the corresponding target files.
Preserve authentication and service configuration. Supply current W06 snapshots
and required owner reports through their established private data path; do not
copy the local worktree wholesale. Validate source availability, exact dates,
freshness and HTTP reads after deployment. Restore the backed-up files to roll
back; never remove or overwrite owner data as part of a code rollback.

This release does not verify or change production files, network bindings,
credentials, database schema, workflows or schedules. Code deployment alone
does not establish that production has current W06 inputs.
