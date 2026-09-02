# AGENTS.md

## Repository identity

- Work only in the Git worktree that contains this file.
- Before any write, verify the Git root. On the primary workstation, expect `D:\efa-os-github`.
- Do not use sibling backup, export, or older directories as the working repository.

## Sources of truth

- Use Git/GitHub for tracked code, documentation, migrations, configuration templates, and sanitised workflow definitions.
- Use `EFA Products/` for local primary product materials; it is intentionally excluded from Git.
- Use an approved SKU passport as the authoritative structured product record when an explicit approval state exists.
- Use PostgreSQL for operational and historical data architecturally stored in the database.
- Use the Ozon API for the current observable Ozon state returned by supported endpoints at request time.
- Do not treat any source as universally authoritative. Match the source to the data type.
- Preserve material provenance: source, observation or verification time, and confirmation level.
- If authoritative sources conflict, preserve both observations, report the conflict, and stop before publication or external write.

## Product-data integrity

- Put facts before assumptions. Never invent specifications, OEM numbers, dimensions, fitment, or service life.
- State vehicle compatibility only when verified; otherwise state that confirmation is unavailable.
- Never claim OEM status or superiority over OEM without verified evidence.
- Keep facts, detected events, inference, and recommendations explicitly separate.
- Follow `docs/products/product-standard.md` and `docs/marketplace/ozon-standard.md` for product and listing work.

## Operating modes and scope

- `READ`: inspect, analyse, and validate without changing state.
- `PROPOSE`: produce a plan, recommendation, diff, or change design without applying it.
- `WRITE`: change only the scope explicitly authorised by the user.
- READ permission does not imply WRITE permission.
- An explicit request to create, change, or fix file X authorises local WRITE only for that stated scope.
- Local code WRITE does not authorise production or external writes.
- Never expand scope or move to a higher-impact mode implicitly.

## Production and external writes

- Require separate explicit approval before changing prices, product listings, advertising or CPC, promotions, inventory, production PostgreSQL, applying production migrations, production n8n workflows or schedules, Ozon, or any other external system.
- Confirm the exact target, environment, operation, and rollback or recovery path before an approved production write.

## Security and sensitive data

- Never commit API keys, passwords, tokens, cookies, connection strings, credentials, session data, or encryption keys.
- Use approved local credential storage or environment configuration; keep `.env` local and ignored.
- Do not read or display secret values from `.env`, credentials, dumps, runtime databases, or encryption keys without necessity and permission.
- You may safely check file existence, variable presence, variable names, and other metadata without revealing values.
- When a potential secret is found, report only its path and category, never its value.
- Never place secrets in workflow exports, source code, logs, diffs, reports, or chat output.
- Keep repository workflow definitions sanitised and configuration examples secret-free.
- Do not commit local exports, database dumps, backups, financial workbooks, logs, Docker volumes, runtime data, or temporary files.

## Change and Git discipline

- Inspect the existing implementation before changing it; do not create parallel implementations without need.
- Preserve unrelated and unfinished user changes in the worktree.
- Keep changes small, reviewable, testable, and traceable.
- Before a commit, review `git status`, the exact diff, and relevant test results.
- Commit or push only when it is explicitly included in the task.
- Do not run destructive Git commands without separate explicit approval.
- Do not delete, overwrite, or move source product data without explicit approval.
- Do not modify generated, runtime, or backup artifacts unless the task explicitly targets them.

## PostgreSQL and migrations

- Inspect the actual PostgreSQL schema when the task depends on it; do not infer it from documentation alone.
- Make schema changes only through reviewed, versioned migrations.
- Apply a production migration only with explicit approval.
- Never rewrite an applied migration; correct it with a new migration.
- Follow `database/README.md` for migration procedure and safety rules.

## Documentation routing

- Read `docs/ARCHITECTURE.md` for system boundaries and data flow.
- Read `docs/PROJECT_STATUS.md` only when the task depends on current production state.
- Read `n8n/workflows/README.md` for canonical workflow and credential rules.
- Read `docs/TRANSFER_RECOVERY.md` for backup, transfer, and recovery work.
- Prefer the relevant profile document over duplicating subsystem rules here.

### Ozon Unit Economics and Settlement prerequisites

For any task affecting Ozon Unit Economics, «Экономику магазина», revenue, profit, margin, Ozon commission, logistics, discounts, points, Green Price, or advertising, you MUST first read `docs/reference/OZON_UNIT_ECONOMICS_OFFICIAL_REFERENCE_V1.md`.

For settlement-specific tasks, and any task affecting Ozon Calculator, Price Decision, AI Analyst financial logic, pricing, promotions, Elastic Boost, minimum/safe price, or contribution margin, additionally read `docs/contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md`. This contract remains the canonical financial baseline for settlement-specific decisions.

Before changing financial logic, revalidate the current official Ozon documentation. If official Ozon semantics conflict with the EFA internal contract, `STOP / CONTRACT_CONFLICT`. If settlement-critical evidence is missing, return `INSUFFICIENT_SETTLEMENT_DATA`.

Do not modify production financial logic until the contract passes empirical validation and a later approved version explicitly permits implementation.

## Stop conditions

- Stop and report when authoritative sources conflict, production scope is ambiguous, required evidence is unavailable, an action may cause irreversible data loss, or the requested action exceeds the authorised scope.
- Data preservation, traceability, and reversibility take priority over speed or automation.
