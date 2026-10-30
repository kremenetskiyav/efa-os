# AGENTS.md

## Current EFA Ozon Cloud — shared rules (Owner 2026-10-30)

**Scope boundary:** This repository contains the legacy EFA OS implementation. Do not assume its VPS, PostgreSQL, n8n, agents, or dashboards are part of the current **EFA Ozon Cloud** workflow. Do not reactivate or expand that architecture for cloud tasks.

**Single canonical instruction set for Work and Codex:** [EFA_CORE_INSTRUCTIONS (Google Drive)](https://docs.google.com/document/d/1K2PLgq_VDQnIWfw-So0YO81Uz3DIBV9gcjpWsuSsZTE/edit). For EFA Ozon Cloud tasks, read and follow its current version; this GitHub file is the Codex entry point and does not establish an independent competing policy. GitHub remains authoritative for versioned code; Google Drive holds the current cloud workflow rules and verified business records. If the canonical document is unavailable, report `NEEDS_VERIFICATION` rather than assuming old instructions remain current. For legacy repository maintenance, keep the applicable repository-specific safeguards below.

**Canonical direct COGS:** [EFA_Себестоимость_закупка_UF001-UF005 (Google Sheets)](https://docs.google.com/spreadsheets/d/16sREkDri9NGY4PeVbXAwr9nHZqOh24ntIDs7xK1EDbA/edit), sheet `Себестоимость`, cells `K7:K11`, with cost breakdown and assumptions on `Расходы`. Only the **actually purchased Series B** for UF001–UF005 is included. Never use virtual Series A, competitor RAF references, historic V6/V7 figures, Seller/customer prices, market prices, or ReStat estimates as a substitute for verified purchase costs. Do not copy the cost workbook or confidential procurement values into this public repository.

**COGS FREEZE:** Do not change purchase prices of filters or consumables, their direct-cost inputs, or the derived COGS in the Google Sheet until a new actual purchase of consumables or filter inventory, supported by its purchase evidence **and explicit Owner approval**. Error corrections likewise need separate Owner approval. Store/maintain historical purchase facts; never silently revalue past inventory or modify the Sheet as a side effect of financial analysis or code changes. This lock does not freeze Ozon *selling* prices, which have their own Owner-approval rule.

**Cost boundaries:** Direct COGS includes paid filters, inbound delivery of the batch, per-item packaging, two thermal labels, and marking cartridge with a **10% ink-loss allowance**. Do not include home rent, electricity, or incidental/walking delivery to the drop-off point, and do not assume VAT refunds or tax deductions for privately paid materials. Ozon marketplace commission, fulfillment/logistics, promotion, tax and Premium overhead are assessed **separately** without double counting. Calculations use the sheet's live formulas, not hard-coded prices.

**Execution boundary:** Default `READ-ONLY`; no Ozon price, ad, listing, stock, promotion, or other changes without explicit Owner approval. For any website access in EFA Ozon Cloud Work/Codex, use only the task's own ChatGPT Cloud Browser; do not substitute a local, connected, or user's browser. Connector access to the verified Google Docs/Sheets is allowed without browsing websites. If Cloud Browser is unavailable, mark the website step `BLOCKED`.

**Keep both stores consistent:** Business and workflow rules are edited in the canonical Google Doc; the GitHub `AGENTS.md` entry point must be reconciled in the same change when its stated boundaries or links change. Do not create a second independent rulebook, or a duplicate cost database.

---

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

### Ozon experiment prerequisite

For any deliberate Ozon test intended to measure business impact — including price, CPO/advertising, promotions or boosting, listing content, FBO/FBS, or another controlled marketplace change — first read `docs/marketplace/OZON_EXPERIMENTS.md`.

Use or create one experiment block before execution when practical. Keep one principal controlled change, declare evidence sources and acceptance criteria in advance, and mark material uncontrolled changes as potential confounders.

The experiment spec is not Ozon WRITE approval. All production/external-write rules above still apply.

### AI Assistants Architecture prerequisite

For any task affecting AI assistants, Coordinator, routing, agent authority,
recommendation ownership, Price Decision, inter-agent messages, status
propagation, future execution, or human approval flow, first read
`docs/architecture/EFA_AI_ASSISTANTS_INTERACTION_ARCHITECTURE_V1.md`.

This architecture does not override the Ozon Unit Economics and Settlement
prerequisites or any settlement implementation gate below.

### Ozon Unit Economics and Settlement prerequisites

For any task affecting Ozon Unit Economics, «Экономику магазина», settlement, pricing economics, revenue, profit, margin, Ozon commission, acquiring, logistics, discounts, points, Green Price, advertising, promotions, Elastic Boost, Ozon Calculator, minimum/safe price, contribution margin, Price Decision, or AI Analyst financial logic, you MUST first read, in this order:

1. `docs/reference/OZON_UNIT_ECONOMICS_OFFICIAL_REFERENCE_V1.md`;
2. `docs/contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1_1.md`.

V1.1 is the current canonical draft for settlement semantics. `docs/contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md` is a historical predecessor and deprecation source only. Canonical-draft approval is not production implementation authorization.

Before changing financial logic, revalidate the current official Ozon documentation. If official Ozon semantics conflict with the EFA internal contract, `STOP / CONTRACT_CONFLICT`. If settlement-critical evidence is missing, return `INSUFFICIENT_SETTLEMENT_DATA`.

Until every required settlement-critical case has empirical `PASS` and a separate explicit implementation approval is recorded, preserve all gates:

- `NO PRODUCTION CALCULATOR PATCH`;
- `NO PRICE DECISION UPDATE`;
- `NO AI ANALYST SETTLEMENT-AWARE CLAIM`;
- `NO AUTOMATED OZON WRITE`.

Do not modify production financial logic until those requirements are satisfied.

## Stop conditions

- Stop and report when authoritative sources conflict, production scope is ambiguous, required evidence is unavailable, an action may cause irreversible data loss, or the requested action exceeds the authorised scope.
- Data preservation, traceability, and reversibility take priority over speed or automation.
