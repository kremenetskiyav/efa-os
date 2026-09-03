# EFA OS — AI Assistants Interaction Architecture v1

| Field | Value |
| --- | --- |
| Status | DRAFT — READY FOR IMPLEMENTATION PLANNING |
| Approval status | `AI_ASSISTANTS_ARCHITECTURE_V1_APPROVED_FOR_CANONICAL_DRAFT` |
| Date | 2026-09-02 |
| Mode | READ-ONLY ARCHITECTURE / PROPOSE |
| Repository baseline | 676cf2ac88153ced08d301fb43fe951f64aefe78 |
| Production evidence baseline | 2026-09-02 production provenance snapshot |
| Capability inventory baseline | 2026-09-01 static Control Center snapshot |
| External or production changes | NOT AUTHORIZED / NOT PERFORMED |

This document defines the target responsibility and interaction model. It does
not create agents, change code, modify PostgreSQL, n8n, Calculator, Price
Decision, AI Analyst, Control Center, production, Ozon, prices, promotions,
advertising or inventory.

The document uses “assistant” for an AI role with a stable job-to-be-done and
“engine” for deterministic calculation, validation, detection or policy logic.
A role does not imply a separate service or process.

## Evidence baseline and authority

The design is based on the following sources:

- [AGENTS.md](../../AGENTS.md);
- [README.md](../../README.md);
- [Project Status](../PROJECT_STATUS.md);
- [Ozon Unit Economics Official Reference V1](../reference/OZON_UNIT_ECONOMICS_OFFICIAL_REFERENCE_V1.md);
- [Ozon Discount & Points Settlement Contract v1.1](../contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1_1.md);
- [Production Recovery & Provenance Manifest v1](../operations/EFA_PRODUCTION_RECOVERY_PROVENANCE_MANIFEST_V1.md);
- [Control Center Current Capabilities & Ready Agents Inventory](../../services/control-center/static/capabilities.json);
- [Calculator architecture](OZON_PRICE_CALCULATOR_V1.md);
- [Competitor Monitor runbook](../operations/COMPETITOR_MONITOR_RUNBOOK_V1.md);
- [Competitor Daily Cycle](COMPETITOR_DAILY_CYCLE_V1.md);
- [Competitor Finding Engine](COMPETITOR_FINDING_ENGINE_V1.md);
- [Competitor Monitor Summary](COMPETITOR_MONITOR_SUMMARY_V1.md);
- [Competitor Daily Report](COMPETITOR_DAILY_REPORT_V1.md);
- [EFA Read MCP](../../services/efa-read-mcp/README.md);
- current AI Analyst, Recommendation Engine, Control Center and delivery code;
- the observed production service, workflow, database and schedule manifest.

Source selection follows the project policy: Git describes tracked definitions;
the production manifest describes the observed runtime at its timestamp;
PostgreSQL is authoritative for stored operational history; supported Ozon APIs
are authoritative for current observable marketplace facts; final settlement
evidence outranks operational finance for settlement conclusions.

Two scope distinctions are mandatory:

1. Calculator v1.1 is a controlled legacy forecast model validated against the
   frozen EcomUnit checkpoint. It is not a settled-order model.
2. Settlement Contract v1.1 is the current canonical draft, but empirical cases
   1–7, 9 and 10 remain open. Therefore the production gates
   NO PRODUCTION CALCULATOR PATCH, NO PRICE DECISION UPDATE,
   NO AI ANALYST SETTLEMENT-AWARE CLAIM and NO AUTOMATED OZON WRITE remain closed.

The Control Center capabilities snapshot still cites the historical v1 contract
and cases 1–3 in its safety text. That is presentation metadata lag, not authority
to weaken the v1.1 gates. Target components must use v1.1.

## A. Goals

1. Establish the minimum sufficient set of AI roles.
2. Give every role one clear responsibility and one owner for each decision type.
3. Separate evidence, deterministic calculations, recommendations, approval and
   execution.
4. Preserve current working components and remove competing recommendation paths.
5. Make data freshness, provenance, confidence and blockers machine-propagated.
6. Keep all current business and Ozon actions human-controlled.
7. Provide one owner interface without forcing the owner to select a specialist
   for ordinary questions.

Non-goals:

- no implementation design below the level needed to define responsibilities;
- no new runtime agents;
- no event-bus or microservice proliferation;
- no autonomous Ozon execution;
- no reinterpretation of legacy financial fields by rename;
- no settlement-aware claim before the empirical gates pass.

## B. Design principles

1. ONE CLEAR RESPONSIBILITY = ONE ASSISTANT / ENGINE.
2. One logical role does not require one deployment unit.
3. Deterministic facts and formulas precede AI interpretation.
4. AI never becomes the source of truth for arithmetic, tariffs, hard floors,
   thresholds, identity reconciliation or settlement finality.
5. There is one canonical recommendation owner per decision type and exactly one
   current recommendation record for a request, SKU and decision type.
6. Coordinator routes and presents; it does not recalculate or override a
   specialist blocker.
7. Evidence providers do not silently become decision authorities.
8. Read, decision, approval and execution planes remain separate.
9. Required stale or missing data fails closed.
10. Facts, detected events, inference and recommendations remain explicitly
    separate in every handoff.
11. Internal persistence is not equivalent to an external marketplace write.
12. Direct specialist access is supported, but it uses the same contracts and
    authority rules as Coordinator-routed access.
13. Scheduled work is used only for stable recurring jobs; ad-hoc analysis is
    manual or delegated.
14. Existing working components are kept unless their responsibility conflicts
    with the canonical path.

## C. Current landscape

### C.1 Evidence freshness

| Evidence | Observation date | What it establishes | Limitation |
| --- | --- | --- | --- |
| Production provenance manifest | 2026-09-02 | Running services, schedules, images, schema, workflows and runtime overlays | Point-in-time observation; runtime is a multi-commit mosaic |
| Control Center capability catalog | 2026-09-01 | READY / CONTROLLED / PARTIAL / NOT READY inventory shown at /capabilities | Static snapshot, not live health; settlement banner still references v1 |
| Repository HEAD | 2026-09-02 | Current tracked code and canonical v1.1 settlement draft | Git is not the production runtime |
| Project Status | Through 2026-08-24 plus historical sections | Component rollout and validation checkpoints | Some sections are superseded by later evidence |
| Official Ozon reference | Reviewed 2026-09-02 | Current documented semantics at review time | Volatile; not order settlement |

### C.2 Current-state component map

| Component | Current role | Status | Inputs | Outputs | Trigger | Read/write | Production | Overlaps with |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AI Analyst v1.3 | Deterministic daily portfolio report covering demand, prices, stock, period economics, CPC, promotions, logistics and competitor summary | READY | Curated mcp_read views/function; competitor summary | Markdown report, diagnostics, price and promotion proposals | Daily 16:00 MSK | DB READ; atomic local report artifact WRITE; no Ozon write | Active host cron | Price Decision, sidecar price recommendations, sidecar anomaly tool, Daily Brief |
| Price Decision v1 | Price and promotion advisory embedded inside AI Analyst; emits LEAVE / RAISE / LOWER / CHECK-style outcomes and test prices | READY, LEGACY ADVISORY | Analyst period economics, price, demand, stock, promotions, logistics | Price/promotion action and reason per SKU | Inside daily Analyst | READ + PROPOSE | Active as Analyst code path | AI Analyst recommendation logic, sidecar price recommendations, Calculator integration plan |
| Ozon Price Calculator core v1.1 | Pure Decimal legacy forecast: profit, margin, P10/P12/P15 and margin classification | CONTROLLED | Versioned config, tariff snapshot inputs, seller_price, cost, tax/config assumptions | Forecast economics and reverse-price thresholds | Manual shadow CLI | READ-only in-memory calculation | Deployed in Recommendation Tool; no public ingress | AI Analyst simplified projection; legacy Price Decision formulas |
| Recommendation Sidecar | Private HTTP wrapper for price/profit recommendations, profit/cost anomalies and promotion monitoring | CONTROLLED | PostgreSQL read models, recommendation config, Calculator/config binds for shadow tools | Deterministic JSON tool responses | Manual/private tool call | DB READ + PROPOSE; no DB/Ozon write | Running private container | AI Analyst diagnosis, Price Decision, promotion analysis |
| Competitor Monitor collection/daily cycle | Controlled Work-browser evidence collection, deterministic validation, snapshot analysis and approved persistence path | CONTROLLED | Manual Work evidence, reference views, previous persisted batches | Immutable snapshot artifacts, analysis, proposed finding set; optionally approved DB inserts | Manual operator runbook | External READ; dry-run by default; DB INSERT only after exact approval | No scheduler; controlled persistence exists | Snapshot Layer, Finding Engine, future autonomous collector |
| Finding Engine v1 | Deterministic detection of six price/search-visibility finding types | CONTROLLED | Approved competitor snapshot analysis plus read-only provenance lookup | Proposed immutable factual findings and suppressed events | After validated competitor snapshot | READ + local dry-run artifact; persistence is separate controlled step | Used in controlled cycle | Competitor Intelligence interpretation; no threat/opportunity logic |
| Competitor Summary | Stable read model for latest complete persisted finding set, severity and portfolio coverage | READY | Three bounded mcp_read competitor views | competitor_monitor_summary.v1 DTO | Analyst run and Control Center page load | DB READ only | Active in Analyst and Control Center | Competitor report presentation only |
| EFA Read MCP v1 | Bounded read gateway over curated mcp_read sources | READY | PostgreSQL mcp_read schema/function | Nine read tools / bounded SELECT results | Agent or operator request | SELECT-only with AST validation and time/row limits | Active localhost/container; public route behind auth | Direct Analyst SQL reads; no dedicated deployed competitor tools |
| Period Economics function | Deterministic period cohort economics for up to 93 inclusive days | READY | postings, returns, finance operations, products/COGS through SQL | Revenue, costs, PBT, profit/unit and legacy margin before tax | Analyst or read query | Stable SQL READ function | Active in production schema | AI Analyst period aggregation; sidecar price-window economics uses a different model |
| CPC collector/lifecycle | Durable create/poll/download flow for Performance CPC reports | READY | Ozon Performance API | Run freshness and product/account CPC rows | 07:30 create; poll every 10 minutes | External READ to PostgreSQL WRITE; no campaign write | Active n8n workflows | Commercial diagnostics, CPC overlay |
| CPC analytics and advertising shadow | CPC diagnostics in Analyst plus manual Calculator-based scenario/ceilings | CONTROLLED | CPC rows, product GMV, legacy Calculator output | DRR/CTR/anomaly facts and read-only scenario | Daily Analyst or manual shadow | READ + in-memory calculation | Analyst active; overlay manual | Commercial Analyst, Pricing/Economics; no need for separate agent |
| Promotion collector | Captures participating/candidate actions and promotion state | READY | Ozon Seller API actions/products/candidates | Immutable promotion runs/snapshots | Every six hours | External READ to PostgreSQL WRITE; no join/leave | Active | Promotion monitoring/recommendation |
| Promotion monitoring/recommendation | Sidecar facts plus conservative REVIEW-only recommendation engine where attribution is missing | CONTROLLED | Latest promotion snapshot and confirmed economics | Participation/candidate signals; current recommendations remain REVIEW | Manual private call | READ + PROPOSE; no Ozon write | Monitoring tool active; recommendation is not canonical Analyst path | AI Analyst currently also proposes JOIN/LEAVE actions |
| Control Center | Read-only operator UI for health, freshness, reports, commercial data, competitors and capability inventory | READY | Health checks, DB facts, last Analyst artifact, competitor summary, static capabilities catalog | Web views and status | On request | READ-only UI; no business write path | Active behind Caddy/auth | Owner Brief presentation |
| Email/Telegram Reporter | Formats one Analyst artifact and transports the same compact payload to both channels | READY | Latest Analyst report | Email and Telegram messages | Daily 16:30 MSK | Informational external WRITE only; no Ozon write | Active cron + n8n webhook workflow | Old Daily Brief delivery, Coordinator presentation |
| Core commercial collectors | Demand, price, stock and operational-finance ingestion | READY | Supported Ozon APIs | PostgreSQL operational/history rows and freshness runs | 05:40, 06:00, 07:10 and six-hour schedules by source | External READ to internal DB WRITE | Active | Read Plane only; not assistants |
| Tax Engine | Deterministic statutory/tax ledger and preview | PARTIAL | Approved realization workbooks and taxpayer config | Tax state with explicit quality | Manual import/reconciliation; Daily Brief read | Controlled DB import; read-only calculation | Partial data; not integrated in current Analyst | Calculator tax input and commercial profitability |
| Daily Brief v1.1 | Deterministic commercial brief and renderers | PARTIAL / SUPERSEDED | Read-only operational and financial sources | Compact/extended brief, email/PDF/Telegram variants | Production workflow inactive | READ; delivery inactive | Runtime bridge exists, old schedule inactive | AI Analyst report and Owner Brief |

Status meaning in this table follows the capability catalog:

- READY: usable in its documented current scope;
- CONTROLLED: usable only in a manual, shadow, private or approval-gated scope;
- PARTIAL: implemented but materially incomplete or not in the active path;
- NOT READY: no approved production capability.

### C.3 Functional duplication and conflict map

| Function | Current implementations | Problem | Target resolution |
| --- | --- | --- | --- |
| Price recommendation | AI Analyst commercial recommendation; embedded Price Decision v1; sidecar price/profit recommendation | Several actions and vocabularies can disagree; no single authority | Deterministic Pricing Policy / Constraint Engine emits calculations, policy result and allowed/blocked actions only; Pricing & Economics alone emits the canonical recommendation and `decision_id` |
| Price projection | AI Analyst local estimate; Calculator core; sidecar observed-window economics | Formula, denominator and evidence scope differ | Calculator/Period Economics remain named engines; AI receives outputs and never recomputes |
| Promotion action | AI Analyst can say ENTER/EXIT/LEAVE; promotion engine returns conservative REVIEW | Competing authority and different evidence gates | Commercial supplies demand/context; Pricing owns promotion economics; canonical decision remains blocked until evidence passes |
| Profit/cost anomaly | AI Analyst diagnostics and sidecar anomaly tool | Duplicate thresholds and presentation | Sidecar deterministic anomaly detector becomes evidence provider; Commercial interprets |
| Executive brief | AI Analyst report, old Daily Brief, Control Center and channel formatter | Multiple presentation paths and retirement ambiguity | Coordinator owns owner-facing synthesis; one payload fans out to UI/email/Telegram |
| Competitor interpretation | Finding Engine facts, Summary prioritization, Analyst prose, Control Center rendering | Acceptable layering can become duplicate scoring if each adds severity | Finding Engine alone assigns factual finding/severity; Competitor Intelligence interprets; presentation layers do not rescore |
| Freshness/health | Collector run tables, Control Center checks, individual analyst checks | Blockers can be applied inconsistently | Deterministic Data Health Gate owns normalized readiness status and DO_NOT_DECIDE propagation; Coordinator explains it to the owner |

The highest-risk current overlap is not merely three names. Price Decision is
implemented inside AI Analyst while the sidecar exposes another independent
recommendation path, and AI Analyst also contains a simplified price projection
despite the separate Calculator core. These paths must not remain peer
authorities.

## D. Target agent model

### D.1 Recommended roles

| Target role | Type | Single responsibility | Separate runtime required now? |
| --- | --- | --- | --- |
| EFA Coordinator | CORE AI ROLE | Route owner requests and produce one non-conflicting answer from specialist envelopes | No. Implement first as the routing/presentation role of the existing main AI interface |
| Commercial Analyst | CORE AI ROLE | Diagnose business performance and identify what needs attention | No new service; evolve current AI Analyst |
| Pricing & Economics | CORE AI ROLE | Own price/promotion economic recommendations using deterministic engines and settlement gates | No new service; use the existing Recommendation Tool boundary |
| Competitor Intelligence | CORE AI ROLE | Interpret competitor findings and market context without inventing source facts | No new collector; wrap current Monitor/Finding/Summary stack |
| Data Health Gate | DETERMINISTIC SUPPORT GATE | Determine from explicit rules whether data and dependencies are healthy enough to decide | No AI wrapper and no new service; normalize existing health/freshness checks |

### D.2 Roles deliberately not created

| Candidate | Decision | Reason |
| --- | --- | --- |
| Advertising / Promotion Agent | Do not create | CPC diagnosis belongs to Commercial; economic guardrails belong to Pricing. It has no independent decision lifecycle today |
| Executive Assistant / Owner Brief | Do not create | This is Coordinator presentation, not a separate JTBD or source of truth |
| Calculator Agent | Do not create | Financial arithmetic is deterministic engine work |
| Finding Agent | Do not create | Finding Engine is deterministic detection, not an autonomous role |
| Reporter Agent | Do not create | Email/Telegram are transport adapters |
| Collector Agents | Do not create | Collectors are scheduled data-plane services |
| Ozon Execution Agent | FUTURE / NOT READY | There is no approved execution plane; creating it now would blur the human gate |

### D.3 Coordinator decision

A distinct Coordinator responsibility is needed because owner requests span
commercial, pricing, competitor and health domains. A distinct Coordinator
runtime is not needed now. The existing main AI interface should assume the role
through a routing policy and common message contract. Extraction into a
standalone orchestrator is justified only if multiple channels, concurrent jobs,
durable task state or independent scaling become proven requirements.

## E. Agent passports

### E.1 EFA Coordinator

#### NAME

EFA Coordinator.

#### ROLE

Single owner-facing router and synthesizer that delegates analysis and returns
one traceable answer without performing domain calculations.

#### PRIMARY JTBD

Turn an owner question or system event into the smallest correct dependency
plan, collect specialist results and present one coherent outcome.

#### RESPONSIBILITIES

- classify intent and decision type;
- select required specialists and dependency order;
- request health validation before high-impact decisions;
- correlate replies by request ID;
- preserve evidence, status, confidence and blockers;
- resolve presentation conflicts by authority, never by averaging opinions;
- perform bounded factual reads through EFA Read MCP when no domain analysis is
  required;
- produce the owner brief and channel-neutral presentation payload;
- keep direct specialist calls compatible with the same contract.

#### NOT RESPONSIBLE FOR

- financial formulas, margin or price calculation;
- competitor fact detection or severity scoring;
- freshness determination from raw rows;
- changing specialist status or recommendation;
- Ozon, database, n8n, campaign, price, promotion or inventory writes;
- approving a business action on behalf of the owner.

#### INPUTS

- owner request or approved scheduled review trigger;
- specialist message envelopes;
- deterministic Data Health Gate metadata;
- bounded factual EFA Read MCP results for current stock, current price,
  freshness, simple status or a last known factual metric;
- explicit owner approval response in a future execution flow.

#### OUTPUTS

- routing plan;
- consolidated evidence map;
- canonical owner answer;
- owner brief payload;
- explicit blocker or human-approval request.

#### DETERMINISTIC ENGINES USED

No domain calculation engine. It may use deterministic routing, schema
validation, status aggregation and bounded EFA Read MCP queries. The factual
fast path may return a current stock, current price, freshness, simple status or
last known factual metric; it may not calculate unit economics or safe price,
interpret competitor threat, issue a pricing recommendation or bypass the
registered domain authority.

#### SOURCE OF TRUTH

Specialist envelope for domain conclusions; authority registry for conflict
resolution; deterministic Data Health Gate for readiness; EFA Read MCP for
bounded facts; owner for approval.

#### TRIGGERS

- manual owner question;
- scheduled daily review;
- delegated alert from a specialist;
- future event notification.

#### READ/WRITE

READ of result envelopes and bounded factual reads through EFA Read MCP.
Optional future INTERNAL WRITE only for task/audit metadata. No business DB
write and no external business write.

#### HUMAN APPROVAL

Required before any action entering the Execution Plane. Coordinator may ask
for approval but cannot infer or manufacture it.

#### FAILURE MODE

- stale required data: return DATA_STALE and DO_NOT_DECIDE;
- unknown task: return INSUFFICIENT_DATA and request the minimum missing scope;
- settlement gap: preserve INSUFFICIENT_SETTLEMENT_DATA;
- conflict: preserve CONTRACT_CONFLICT and both observations;
- dependency failure: return DEPENDENCY_FAILED with the failed dependency;
- partial non-critical evidence: return PARTIAL and state the excluded conclusion.

#### CURRENT IMPLEMENTATION

No active dedicated Coordinator. Owner-facing behavior is split among AI
Analyst, Control Center and delivery formatting. Project Status lists
EFA Coordinator as planned.

#### MIGRATION

Add the logical routing and authority policy to the existing main interface;
make AI Analyst a specialist input rather than the final all-purpose brain;
reuse the existing report formatter as presentation infrastructure. Do not
create a new service in Phase 1.

### E.2 Commercial Analyst

#### NAME

EFA Commercial Analyst.

#### ROLE

Diagnoses sales, demand, stock, logistics, CPC and promotion performance and
identifies commercial attention items.

#### PRIMARY JTBD

Explain what changed in the business, why it may have changed, how material it
is and which specialist decision is needed next.

#### RESPONSIBILITIES

- period and daily sales/demand comparison;
- stock and coverage risk;
- logistics diagnostics;
- CPC performance, DRR, CPO/attribution caveats and promotion-state analysis;
- profit/cost anomaly interpretation;
- SKU-level and portfolio diagnosis;
- causal-hypothesis labeling, without converting correlation to fact;
- request Pricing when a price, promotion or ad-spend profitability decision is
  required;
- produce commercial evidence, not a competing price action.

#### NOT RESPONSIBLE FOR

- final price, hard-floor or promotion-economics recommendation;
- settlement decomposition;
- tariff or financial formula calculation;
- competitor collection or finding generation;
- data-health override;
- CPC bid/campaign, promotion, price, stock or Ozon writes.

#### INPUTS

- EFA Read MCP and approved mcp_read sources;
- Period Economics output;
- demand, price, stock, logistics, CPC and promotion facts;
- deterministic anomaly signals;
- deterministic Data Health Gate status;
- Competitor Intelligence context when relevant;
- owner question and period.

#### OUTPUTS

- commercial diagnosis;
- ranked attention items;
- factual comparisons and bounded hypotheses;
- evidence package for Pricing;
- non-price operational recommendation;
- PARTIAL / DATA_STALE / INSUFFICIENT_DATA blockers.

#### DETERMINISTIC ENGINES USED

- Period Economics;
- profit/cost anomaly detector;
- CPC metric calculations;
- promotion monitoring signals;
- stock/freshness thresholds.

#### SOURCE OF TRUTH

PostgreSQL operational history via curated mcp_read; collector run records for
freshness; Ozon source semantics for each metric; approved product master for
COGS/identity.

#### TRIGGERS

- daily scheduled review;
- manual question;
- Coordinator delegation;
- material demand, stock, CPC, logistics or promotion event.

#### READ/WRITE

READ + PROPOSE. Optional local report/result artifact only. No operational DB
write and no external business write.

#### HUMAN APPROVAL

Required for every recommended CPC/CPO change, promotion change, inventory
action or other external action. Informational diagnosis itself needs no
approval.

#### FAILURE MODE

- stale source: mark affected dimension DATA_STALE and exclude its conclusion;
- missing period coverage: INSUFFICIENT_DATA;
- advertising attribution unresolved: OZON_UNCLEAR;
- required engine failure: DEPENDENCY_FAILED;
- pricing implication: delegate, do not improvise.

#### CURRENT IMPLEMENTATION

AI Analyst v1.3 plus parts of the Recommendation Sidecar anomaly and promotion
monitoring tools.

#### MIGRATION

Retain the Analyst’s proven read model and reporting coverage; remove local
price/promotion authority and simplified financial projection; consume
deterministic anomaly outputs; emit the common message contract.

### E.3 Pricing & Economics

#### NAME

EFA Pricing & Economics.

#### ROLE

Owns canonical price and promotion-economic recommendations while delegating
all arithmetic, thresholds and settlement validation to deterministic engines.

#### PRIMARY JTBD

Answer whether a price or promotion should be left, tested or reviewed without
crossing financial, evidence or settlement gates.

#### RESPONSIBILITIES

- select forecast, observed-period or settlement mode explicitly;
- invoke the correct Calculator, Period Economics or Pricing Policy /
  Constraint Engine;
- combine economic guardrails with Commercial and Competitor evidence;
- own and emit the one canonical price or promotion-economic recommendation;
- create its `decision_id` and any valid `supersedes` reference;
- own promotion and advertising profitability guardrails;
- preserve margin-policy, lifecycle, provenance and formula version;
- run or interpret settlement empirical-case validation;
- return a blocker when settlement-critical evidence is absent.

#### NOT RESPONSIBLE FOR

- manually reproducing financial formulas in language output;
- treating buyer display price as seller revenue;
- converting legacy forecast into final settlement;
- inventing CPC allocation, promotion uplift, Green split or points eligibility;
- competitor fact collection;
- approving or executing price, promotion, Elastic, CPC/CPO or Ozon changes.

#### INPUTS

- Calculator resolved inputs and result;
- Period Economics and observed price-window economics;
- settlement evidence and Contract v1.1 validation state;
- Commercial evidence package;
- Competitor Intelligence market context;
- Tax Engine output with quality;
- owner target/constraint.

#### OUTPUTS

- one canonical recommendation per SKU and decision type, with `decision_id`;
- deterministic calculation references and versions;
- recommended action, bounded test and guardrails when permitted;
- risk, confidence and validity window;
- INSUFFICIENT_SETTLEMENT_DATA, OZON_UNCLEAR or CONTRACT_CONFLICT when required;
- HUMAN_APPROVAL_REQUIRED for every proposed external action.

#### DETERMINISTIC ENGINES USED

- Ozon Price Calculator core v1.1, explicitly legacy forecast;
- Input Resolver and tariff/config validation;
- Period Economics;
- observed price-window Recommendation Engine;
- target deterministic Pricing Policy / Constraint Engine;
- Advertising/CPC shadow overlay;
- Promotion Economics validator;
- Tax Engine;
- settlement empirical-case validator.

#### SOURCE OF TRUTH

For formulas and thresholds: versioned deterministic engine/config. For period
facts: PostgreSQL/mcp_read. For current Ozon state: supported Ozon API evidence.
For settlement: final settlement, then order finance detail, then lower-priority
sources exactly as Contract v1.1 defines.

#### TRIGGERS

- manual price/economics question;
- Coordinator delegation;
- Commercial escalation;
- WATCH/IMPORTANT competitor event with price relevance;
- scheduled daily review only for SKUs meeting a deterministic trigger;
- settlement validation request.

#### READ/WRITE

READ + PROPOSE + optional INTERNAL decision/audit record after future approval.
No external write.

#### HUMAN APPROVAL

Always required for price, promotion, Elastic, Green, CPC/CPO or any Ozon
change. Settlement-contract approval is separate from implementation approval,
which is separate from an exact production action approval.

#### FAILURE MODE

- stale tariff/price/economics: DATA_STALE;
- missing non-settlement evidence: INSUFFICIENT_DATA;
- missing settlement-critical evidence: INSUFFICIENT_SETTLEMENT_DATA;
- official ambiguity: OZON_UNCLEAR;
- source/contract contradiction: CONTRACT_CONFLICT;
- deterministic engine failure: DEPENDENCY_FAILED;
- attempted direct write: ACTION_NOT_ALLOWED.

#### CURRENT IMPLEMENTATION

Functionality is split across embedded Price Decision v1, Calculator core,
Recommendation Sidecar price recommendations, advertising shadow and
promotion recommendation code.

#### MIGRATION

Make the Recommendation Tool the single engine boundary; extract embedded Price
Decision rules from AI Analyst into one versioned deterministic Pricing Policy /
Constraint Engine; label legacy forecast separately. The engine emits only
calculations, policy result, hard-floor result, allowed action set, blocked
actions and reasons/gates. Pricing & Economics alone turns those outputs into
the canonical recommendation and `decision_id`; preserve every settlement gate.

### E.4 Competitor Intelligence

#### NAME

EFA Competitor Intelligence.

#### ROLE

Interprets validated competitor findings into bounded threats, opportunities
and market context while retaining source wording and uncertainty.

#### PRIMARY JTBD

Explain what changed among EFA and monitored competitor listings and whether
Commercial or Pricing attention is justified.

#### RESPONSIBILITIES

- consume only complete persisted finding sets or explicitly labeled dry-run
  evidence;
- interpret price and search-visibility findings;
- distinguish EFA CONTROL, PRIMARY and RESERVE roles;
- preserve OEM-query, region, scan-limit and snapshot provenance;
- route commercially relevant findings to Commercial or Pricing;
- provide market-corridor context only when source coverage supports it;
- keep INFO activity visible without unnecessary alerts.

#### NOT RESPONSIBLE FOR

- collecting browser evidence itself;
- mutating snapshots or findings;
- changing Finding Engine taxonomy/severity during presentation;
- claiming deletion, delisting or stopped sales from a bounded not-found result;
- calculating margin or issuing the final price action;
- Ozon or competitor-system writes.

#### INPUTS

- competitor_monitor_summary.v1;
- complete finding set and referenced evidence;
- portfolio/watchlist/OEM reference state;
- owner/direct specialist query;
- deterministic Data Health Gate freshness state.

#### OUTPUTS

- competitor situation summary;
- threat/opportunity interpretation with explicit confidence;
- market-context evidence for Commercial/Pricing;
- escalation with original severity;
- coverage and freshness caveats.

#### DETERMINISTIC ENGINES USED

- Competitor Snapshot Analyzer;
- Finding Engine v1;
- Finding Set reconciliation/persistence validator;
- Competitor Summary builder.

#### SOURCE OF TRUTH

Latest complete persisted Finding Set and approved mcp_read competitor views;
immutable Work-browser evidence for controlled dry-runs; approved SKU/OEM and
watchlist references.

#### TRIGGERS

- manual direct query;
- Coordinator delegation;
- newly persisted finding set;
- daily owner review;
- future event trigger after stabilization approval.

#### READ/WRITE

READ + INTERPRET + PROPOSE. No collector execution and no persistence. Current
Competitor Monitor persistence remains a separate operator-approved process.

#### HUMAN APPROVAL

Required before any production persistence under the current runbook, any new
external alert policy, any watchlist/master-data change, or any commercial
reaction.

#### FAILURE MODE

- incomplete/invalid finding set: DEPENDENCY_FAILED or INSUFFICIENT_DATA;
- stale set under an explicit freshness SLA: DATA_STALE;
- unknown freshness because no SLA exists: PARTIAL, never FRESH;
- ambiguous listing identity/query evidence: OZON_UNCLEAR;
- attempted severity rewrite or external action: ACTION_NOT_ALLOWED.

#### CURRENT IMPLEMENTATION

Competitor Monitor controlled cycle, Finding Engine, Summary builder,
competitor report module and Control Center competitor view.

#### MIGRATION

Add one AI interpretation layer above the unchanged deterministic stack; keep
collection/persistence separate; do not add a second severity algorithm;
introduce direct specialist routing without creating a new collector service.

### E.5 Deterministic Data Health Gate

#### NAME

EFA Data Health Gate.

#### ROLE

Deterministic support gate that normalizes collector, dependency, freshness,
schema and data-readiness state and decides whether downstream analysis is
allowed to proceed. It is not an AI role and must not receive an AI wrapper.

#### PRIMARY JTBD

Prevent commercial conclusions from being made on stale, incomplete, failed or
provenance-ambiguous data.

#### RESPONSIBILITIES

- aggregate collector run state and expected cadence by explicit rules;
- evaluate approved freshness SLAs;
- execute dependency-health, schema and readiness checks;
- identify missing coverage, failed dependencies and known runtime drift;
- emit `DATA_STALE`, `DEPENDENCY_FAILED` and `DO_NOT_DECIDE` by affected
  domain and period;
- distinguish service health from data freshness;
- provide recovery provenance references without performing recovery.

#### NOT RESPONSIBLE FOR

- commercial, pricing or competitor recommendations;
- natural-language diagnosis or owner-facing narrative;
- DevOps repair, deployment, restart, migration or credential changes;
- changing source data to make a check pass;
- overriding domain-specific settlement blockers;
- external business writes.

#### INPUTS

- collector run/freshness records;
- bounded service health endpoints;
- MCP/query status;
- capability inventory and production provenance metadata;
- engine validation status;
- expected schedule and source SLA configuration.

#### OUTPUTS

- normalized deterministic health envelope by domain;
- allow-analysis / do-not-decide gate;
- affected sources, last success and expected next run;
- dependency failure and escalation payload.

#### DETERMINISTIC CHECKS USED

- schedule/freshness evaluator;
- schema/contract validators;
- service health checks;
- capability-state registry.

#### SOURCE OF TRUTH

Run tables for data freshness; service endpoints/process evidence for
availability; schema/contract validation results; production manifest for
observed provenance; approved schedules for cadence.

#### TRIGGERS

- before every high-impact delegated decision;
- scheduled health review;
- collector/service failure event;
- manual owner request.

#### READ/WRITE

READ + deterministic STATUS. Optional future INTERNAL health/audit record only.
No repair and no external write.

#### HUMAN APPROVAL

Required before repair, restart, deployment, migration, credential action,
production write or recovery step.

#### FAILURE MODE

- health source unavailable: DEPENDENCY_FAILED;
- source past SLA: DATA_STALE;
- no approved SLA: PARTIAL / freshness unknown;
- conflicting run/provenance evidence: CONTRACT_CONFLICT;
- requested repair in read-only context: ACTION_NOT_ALLOWED.

#### CURRENT IMPLEMENTATION

Health/freshness logic is distributed across collector run tables, AI Analyst
checks, Control Center and production provenance documentation. No dedicated AI
role exists or is required.

#### MIGRATION

Merge distributed checks into one normalized deterministic health contract and
status authority; reuse current checks; do not create an AI wrapper. Coordinator
alone turns the gate result into a natural-language explanation for the owner.

## F. Interaction routes

### F.1 Routing rules

1. Coordinator requests only the specialists required by the decision type.
   `NO DEFAULT ALL-AGENTS FAN-OUT`.
2. The deterministic Data Health Gate is a mandatory dependency for
   high-impact, scheduled and externally actionable recommendations.
3. Independent evidence branches may run in parallel; deterministic
   dependencies run before the specialist conclusion.
4. Pricing is not called for every descriptive commercial question.
5. Commercial is not called for a pure formula/threshold question.
6. Competitor Intelligence is not called when competitor context cannot affect
   the requested conclusion.
7. Coordinator never converts a blocker into a positive action.
8. Scheduled routing produces the same contracts as manual routing.

### F.2 Route catalogue

This matrix is normative. “Required roles” may name the deterministic Data
Health Gate where the route cannot proceed without its status; that does not
make the gate an AI role.

| Route | Initiator | Required roles | Optional roles | Deterministic dependencies | Blocking statuses | Output authority | Human approval |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Daily Review | Approved schedule → Coordinator | Coordinator; Commercial; Data Health Gate | Competitor Intelligence when a complete persisted summary exists; Pricing only for a deterministic price/promotion trigger | Collectors, PostgreSQL, Period Economics, freshness/readiness checks, summary validation | DATA_STALE, INSUFFICIENT_DATA, DEPENDENCY_FAILED, CONTRACT_CONFLICT | Commercial owns diagnosis; Pricing owns any price/promotion recommendation; Coordinator owns the Owner Brief | Not for read-only brief; required for any later action |
| Price Question | Owner → Coordinator | Coordinator; Pricing & Economics; Data Health Gate | Commercial and/or Competitor Intelligence only when their evidence is required | EFA Read MCP, Calculator/Period Economics, Pricing Policy / Constraint Engine | DATA_STALE, INSUFFICIENT_DATA, INSUFFICIENT_SETTLEMENT_DATA, OZON_UNCLEAR, CONTRACT_CONFLICT, DEPENDENCY_FAILED | Pricing & Economics | Required for any external price/promotion action |
| Competitor Alert | Controlled collector cycle or Owner → Coordinator | Competitor Intelligence; Coordinator | Commercial and/or Pricing only when business or price relevance exists | Analyzer/Finding Engine, controlled persistence writer, PostgreSQL read, finding-set/summary validation | DATA_STALE, INSUFFICIENT_DATA, OZON_UNCLEAR, DEPENDENCY_FAILED, ACTION_NOT_ALLOWED | Finding Engine owns factual finding/severity; Competitor Intelligence owns interpretation | Required for current persistence and any external alert/reaction |
| CPC Problem | Owner or approved daily trigger → Coordinator | Coordinator; Commercial; Data Health Gate; Pricing when spend/action recommendation is requested | Competitor Intelligence only when market evidence is relevant | CPC lifecycle metrics, attribution/lag checks, Pricing profitability guardrail | DATA_STALE, INSUFFICIENT_DATA, INSUFFICIENT_SETTLEMENT_DATA, OZON_UNCLEAR, DEPENDENCY_FAILED | Commercial owns diagnosis and campaign recommendation; Pricing owns non-overridable economics | Required for campaign/spend change |
| Settlement Validation | Owner/reviewer → Coordinator | Coordinator; Pricing & Economics | None by default | Contract v1.1 deterministic validator, finance/closing evidence, validation registry | INSUFFICIENT_SETTLEMENT_DATA, OZON_UNCLEAR, CONTRACT_CONFLICT, DEPENDENCY_FAILED | Pricing & Economics owns the validation result | Separate review and implementation approval; no production authorization |
| System Failure | Health event or Owner → Coordinator | Coordinator; Data Health Gate | Affected domain authority only for impact scope | Dependency-health, schema, readiness and freshness checks | DATA_STALE, DEPENDENCY_FAILED, CONTRACT_CONFLICT, ACTION_NOT_ALLOWED | Data Health Gate owns readiness status; Coordinator explains it | Required for repair/restart/deployment/migration/recovery |
| Future Write | Owner request after canonical recommendation | Coordinator; originating domain authority; Human Approval Gate; future Execution Agent | None by default | Deterministic preflight, exact approval binding, write adapter, verifier, audit | Every unresolved blocker; HUMAN_APPROVAL_REQUIRED; ACTION_NOT_ALLOWED | Originating domain authority owns recommendation; human owns approval; verifier owns observed result | Exact one-use approval mandatory; route is FUTURE / NOT READY |

### F.3 Route-specific notes

#### Route 1 — Daily Business Review

The real order is data-health first, then analysis. Commercial and Competitor
may run in parallel because both consume already persisted facts. Pricing runs
only when a deterministic trigger indicates a price/promotion/economic decision
or the owner explicitly requests a portfolio price review. This prevents the
daily report from producing unnecessary price actions for every SKU.

The daily route must not start Competitor Collector on demand. It reads only the
latest complete persisted summary and reports unknown/stale freshness honestly.

#### Route 2 — Price Question

For “What is P15?” only Pricing and its deterministic Calculator are needed.
For “Should we change the price of УФ 004Б?” the route also needs current
demand/stock/logistics and competitor context. Coordinator supplies both
evidence branches to Pricing; it does not ask Commercial to calculate price.

Bounded factual requests do not use this analytical route. “Покажи остатки” may
go directly from Coordinator through EFA Read MCP to the owner, subject to the
factual fast-path rules below.

#### Route 3 — Competitor Alert

Current collection and persistence remain the five-step operator process:
COLLECT → VALIDATE → APPROVE → PERSIST → REVIEW. After persistence:

- INFO: Control Center and scheduled summary only;
- WATCH: Coordinator owner brief; delegate only when business relevance exists;
- IMPORTANT: immediate human review before external delivery or reaction under
  the current runbook.

No target assistant may reinterpret not-found-within-scan-limit as delisting.

#### Route 4 — CPC Problem

Commercial evaluates traffic, conversion, attribution, lag and demand.
Pricing calculates whether the proposed spend/bid scenario stays within the
applicable deterministic margin guardrail. A campaign recommendation is blocked
when advertising allocation is OZON_UNCLEAR for the required conclusion.

#### Route 5 — Settlement Validation

The validator records one of PASS, FAIL, INSUFFICIENT_SETTLEMENT_DATA or
OZON_UNCLEAR for each empirical case. Cases 1–7, 9 and 10 are settlement
critical. Case 8 independently gates advertising allocation. Contract review,
financial-logic implementation and production rollout are separate approvals.

#### Route 6 — System Failure

DO_NOT_DECIDE is scoped. A stale CPC source blocks CPC conclusions but need not
block an unrelated stock fact. A failed required Period Economics dependency
blocks a price profitability recommendation. The Coordinator must show affected
scope rather than labeling the whole platform down without evidence.

#### Route 7 — Future Write Action

Execution is outside the current architecture capability. The route is included
only to define the permanent approval boundary and prevent analysis roles from
acquiring write authority by accident.

### F.4 Selective fast paths

| Owner request | Minimal route |
| --- | --- |
| `Покажи остатки` | Coordinator → bounded EFA Read MCP → Owner |
| `Что изменилось у RAF?` | Coordinator → Competitor Intelligence → Owner |
| `Покажи P15` | Coordinator → Pricing & Economics → Calculator → Pricing & Economics → Coordinator → Owner |
| `Можно ли снизить цену?` | Coordinator → Data Health Gate → Pricing & Economics → only required Commercial and/or Competitor evidence → Coordinator → Owner |
| `Проверь систему` | Coordinator → Data Health Gate → Coordinator → Owner |

The factual fast path is read-only and may return current stock, current price,
freshness, a simple status or a last known factual metric. It may not calculate
unit economics or safe price, interpret competitor threat, issue a price
recommendation or bypass domain authority. Selective routing is mandatory:
`NO DEFAULT ALL-AGENTS FAN-OUT`.

## G. Data contract between assistants

### G.1 Minimal envelope

Contract name: efa_assistant_message.v1.

| Field | Required | Purpose |
| --- | --- | --- |
| schema_version | Yes | Exact envelope version |
| request_id | Yes | Correlates the owner request and all delegated work |
| timestamp | Yes | UTC timestamp of this immutable result |
| source_agent | Yes | Registered AI role or deterministic gate/engine that produced the envelope |
| target_agent | Yes | Intended consumer |
| task_type | Yes | Registered intent/decision type |
| sku | Yes | One SKU or an explicit bounded list; null only when the task is not SKU-scoped |
| period | Yes | Exact observation/analysis period; null only when not applicable |
| inputs | Yes | Compact owner constraints and immutable/query input references; no secrets or uncontrolled raw payload |
| evidence_refs | Yes | Stable references to facts, calculations, findings and gate results |
| data_freshness | Yes | Aggregate readiness/freshness for the exact SKU/period/task scope |
| financial_mode | Yes | `LEGACY_FORECAST`, `OBSERVED_PERIOD` or `SETTLEMENT` for financial work; null for non-financial work |
| status | Yes | One status from section H |
| result | Yes | Structured facts/analysis; may be null when blocked |
| recommendation | No | Present only when source_agent is the registered domain authority for this decision type |
| decision_id | Conditional | Required for every canonical recommendation; created by its domain authority. A deterministic gate may create one only for its own authoritative gate result |
| supersedes | No | Existing `decision_id` replaced by this result; same authority and scope only |
| risk | Yes | Empty array or explicit risk codes |
| blocked_by | Yes | Empty array or blocking dependency/evidence/gate codes |
| requires_human_approval | Yes | Boolean; true for every externally actionable proposal |

The envelope carries references and compact evidence, not arbitrary database
rows. It does not require a message broker. The first implementation may pass
the same JSON object through direct calls or one in-process coordinator.

`data_freshness` is the aggregate gate result for the envelope scope and uses
`FRESH`, `STALE`, `UNKNOWN` or `NOT_APPLICABLE`; item-level freshness remains on
the referenced evidence. A financial conclusion uses
exactly one `financial_mode`. If evidence from several modes is needed, each
mode is calculated separately and the result contains an explicit decomposition;
the values must not be blended into one financial conclusion.

`decision_id` is created by the registered domain authority, never by
Coordinator. The Data Health Gate is the status authority only for its readiness
domain. `supersedes` may reference only an existing `decision_id` from the same
authority, decision type and scope; it may never contain a request ID, message
ID or free-form label.

### G.2 Evidence item

Each material evidence item contains:

| Field | Meaning |
| --- | --- |
| evidence_type | Metric, finding, calculation, health state or owner constraint |
| source | Exact API/report/view/function/artifact/engine |
| source_ref | Stable identifier or bounded query reference |
| observed_at | When the fact was observed |
| freshness | FRESH, STALE, UNKNOWN or NOT_APPLICABLE |
| confidence | HIGH, MEDIUM, LOW or UNKNOWN |
| source_status | Official/empirical/internal status where applicable |
| lifecycle_status | LIVE_ESTIMATE, PROVISIONAL, FINAL_SETTLEMENT or CORRECTED_FINAL_SETTLEMENT when financial |
| value | Compact structured value |

### G.3 Recommendation object

Only the registered authority may populate recommendation:

| Field | Meaning |
| --- | --- |
| decision_type | PRICE, PROMOTION_ACTION, ELASTIC_ACTION, CPC, STOCK, COMPETITOR_RESPONSE or other registered type |
| action | Controlled vocabulary for that decision type |
| subject | SKU/campaign/promotion/source being considered |
| rationale | References to evidence and deterministic results |
| constraints | Floors, ceilings, expiry and other non-overridable limits |
| confidence | Confidence in the recommendation, distinct from source confidence |
| engine_versions | Exact deterministic formula/policy versions |

The envelope, not the nested recommendation object, carries `decision_id` and
`supersedes` so every consumer uses one canonical identity.

### G.4 Compact example

~~~json
{
  "schema_version": "efa_assistant_message.v1",
  "request_id": "req-20260902-uf004b-price-001",
  "timestamp": "2026-09-02T12:00:00Z",
  "source_agent": "pricing_economics",
  "target_agent": "coordinator",
  "task_type": "PRICE_DECISION",
  "sku": "УФ 004Б",
  "period": {"from": "2026-08-19", "to": "2026-09-01"},
  "inputs": {
    "owner_constraint_ref": "constraint:req-...:price-review"
  },
  "evidence_refs": [
    "commercial:req-...:result",
    "competitor:finding-set:...",
    "health:gate-...",
    "pricing-policy:calc-..."
  ],
  "data_freshness": "FRESH",
  "financial_mode": "OBSERVED_PERIOD",
  "status": "HUMAN_APPROVAL_REQUIRED",
  "result": {
    "policy_result": "WITHIN_ALLOWED_ACTION_SET"
  },
  "recommendation": {
    "decision_type": "PRICE",
    "action": "REVIEW_PRICE_CHANGE",
    "subject": "УФ 004Б",
    "rationale": ["pricing-policy:calc-..."],
    "constraints": ["HARD_FLOOR_NON_OVERRIDABLE"],
    "confidence": "MEDIUM",
    "engine_versions": ["pricing_policy.v1"]
  },
  "decision_id": "dec-20260902-uf004b-price-001",
  "supersedes": null,
  "risk": [],
  "blocked_by": [],
  "requires_human_approval": true
}
~~~

## H. Status and error protocol

### H.1 Status definitions

`STATUS MESSAGES ARE IMMUTABLE`. A stored or transmitted status is never edited,
cleared or downgraded. A newer authoritative result may only `SUPERSEDE` it under
the matrix below. If later supersession is possible, the status-bearing authority
assigns a `decision_id`; the new envelope references it through `supersedes`.

| Status | Blocking? | Meaning | Allowed emitter | Allowed superseding authority after new evidence | Coordinator behavior |
| --- | --- | --- | --- | --- | --- |
| OK | Non-blocking | Required evidence and dependencies passed for the stated scope | Registered domain authority or deterministic gate, only for its scope | Same original authority/gate | Present within scope; never use it to erase another branch blocker |
| PARTIAL | Non-blocking only for proven subset | Useful result exists, but a non-critical dimension is absent or excluded | Registered domain authority or deterministic gate/engine | Same original authority/gate | Show omissions; do not broaden the conclusion |
| DATA_STALE | Blocking for affected decisions | A required source exceeded its approved freshness limit | Data Health Gate only | Data Health Gate only, after a newer successful freshness check | Preserve `DO_NOT_DECIDE`; show source, scope and last valid observation |
| INSUFFICIENT_DATA | Blocking for affected conclusion | Required non-settlement evidence is missing | Registered domain authority for the conclusion | Same original authority after the missing evidence arrives | Name missing evidence; stop the affected conclusion |
| INSUFFICIENT_SETTLEMENT_DATA | Blocking for settlement-aware conclusion | Required settlement-critical evidence is missing/incomplete | Pricing & Economics from deterministic Contract v1.1 validator result | Pricing & Economics only after required evidence and validator rerun | Preserve exact status; no settlement-aware action or claim |
| OZON_UNCLEAR | Blocking for ambiguity-dependent conclusion | Official/current evidence does not resolve the semantic question | Registered domain authority using source/contract evidence | Same original authority only after new official or empirical evidence resolves the point | Preserve ambiguity; do not infer a mapping/formula |
| CONTRACT_CONFLICT | Blocking and terminal for affected publication/write | Authoritative sources or approved contract conflict | Domain authority or deterministic contract validator that detects the conflict | Reviewed reconciliation/new contract authority only | Preserve both observations and stop; never choose a preferred value |
| DEPENDENCY_FAILED | Blocking for dependent result | Required service, engine, schema or query failed | Data Health Gate or the deterministic dependency adapter for its own failure | Same original gate/adapter after a successful retry with new evidence | Name failed dependency, propagate `DO_NOT_DECIDE` to dependants |
| HUMAN_APPROVAL_REQUIRED | Blocking for execution; recommendation may be valid | External action requires exact approval | Originating domain authority for its canonical recommendation | Human Approval Gate only after exact approval of the unchanged payload | Ask for exact approval; freeze payload; never infer approval |
| ACTION_NOT_ALLOWED | Blocking | Requested action exceeds role, mode or approval scope | Authority/gate that owns the violated boundary | Same boundary authority only after valid scope/approval evidence changes | Explain boundary; do not retry through another role |

DO_NOT_DECIDE is a gate flag carried in blocked_by/risk, not a replacement for
the more specific primary status.

### H.2 Propagation rules

1. Status messages are immutable; no component rewrites history.
2. Only the original registered authority/gate may issue a superseding result
   after new evidence, except the explicit human/contract cases in H.1.
3. Coordinator copies a domain blocker unchanged into the owner result and may
   never downgrade or clear it.
4. A specialist may not clear a Data Health Gate blocker.
5. INSUFFICIENT_SETTLEMENT_DATA can never become LEAVE, SELL, RAISE, LOWER,
   JOIN, EXIT or any other financial action.
6. CONTRACT_CONFLICT is terminal for publication, implementation and external
   write in the affected scope.
   It is superseded only by a reviewed reconciliation or new contract result.
7. OZON_UNCLEAR remains explicit; inference may not fill the gap.
8. DATA_STALE applies to the affected source and dependent decisions. Unrelated
   facts may remain available.
9. PARTIAL is allowed only when the omitted dimension is not required for the
   stated result; omissions must be listed.
10. DEPENDENCY_FAILED is for a failed dependency, not for a valid negative
   business outcome or an evidence gap.
11. HUMAN_APPROVAL_REQUIRED means analysis completed; it does not mean approval
    exists and is superseded only by exact approval of the unchanged payload.
12. ACTION_NOT_ALLOWED must identify the violated role/mode/gate without
    attempting the action.
13. When parallel branches differ, Coordinator retains every branch status and
    sets the final task status from the status that blocks the requested
    conclusion, not from a numeric “majority”.
14. A later result may supersede an earlier one only with the same decision type,
    scope, original authority, newer evidence and an explicit `supersedes`
    reference to the existing `decision_id`.

### H.3 Required downstream behavior

| Upstream status | Coordinator | Domain specialist | Execution Plane |
| --- | --- | --- | --- |
| OK | Present result | May continue | Still requires approval if actionable |
| PARTIAL | Show omissions | Continue only within proven scope | Block if omitted input is execution-critical |
| DATA_STALE | Show stale source and DO_NOT_DECIDE | Exclude dependent conclusion | Block |
| INSUFFICIENT_DATA | Show missing evidence | Stop affected conclusion | Block |
| INSUFFICIENT_SETTLEMENT_DATA | Preserve exact status | Stop settlement-aware conclusion | Block |
| OZON_UNCLEAR | Preserve ambiguity | Do not invent mapping/formula | Block affected action |
| CONTRACT_CONFLICT | Preserve both sources and stop | Stop | Block |
| DEPENDENCY_FAILED | Name failed dependency | Stop dependent work | Block |
| HUMAN_APPROVAL_REQUIRED | Ask for exact approval | Freeze proposed payload | Wait |
| ACTION_NOT_ALLOWED | Explain boundary | Do not retry through another role | Block |

## I. Human approval gates

### I.1 Permanent separation

~~~text
AI interpretation + deterministic analysis
                    |
                    v
            recommendation artifact
================================================
              HUMAN APPROVAL GATE
================================================
                    |
                    v
       external execution + verification
~~~

Current state:

- analysis and proposals are allowed in their documented scopes;
- scheduled Email/Telegram report delivery is an already established
  informational route;
- no component has an approved Ozon business-write path;
- owner action is manual and outside the assistant execution plane.

Autonomous actions prohibited now:

- price change;
- promotion join/leave or parameter change;
- Elastic/Green/Points configuration change;
- CPC/CPO bid, budget, campaign or status change;
- inventory or replenishment write;
- any other Ozon write.

### I.2 Exact approval record for a future action

A future approval must bind:

- recommendation ID and deterministic engine versions;
- exact target account, environment and object;
- exact operation and before/after values;
- evidence timestamps and validity window;
- risk classification;
- rollback/recovery procedure;
- approver identity and approval timestamp;
- one-use execution key and expiry.

Changing target, value, operation, evidence, engine version or expected effect
invalidates approval. Contract approval, implementation approval, deployment
approval and one business-action approval are separate records.

### I.3 Current Competitor Monitor approval

Competitor snapshot/finding persistence is an internal PostgreSQL write, not an
Ozon write, but it still uses the exact operator approval defined by the
runbook. That approval does not authorize external delivery or commercial
reaction.

## J. Read, Decision, Approval and Execution planes

| Plane | Components | Allowed | Prohibited |
| --- | --- | --- | --- |
| READ PLANE | Ozon/Performance read APIs, commercial collectors, competitor evidence collection, PostgreSQL operational/history storage, mcp_read, EFA Read MCP | External reads; controlled internal ingestion/persistence; bounded queries | Marketplace state changes; business recommendations by collectors |
| DECISION PLANE | Period Economics, Calculator, anomaly/CPC/promotion engines, Finding Engine, Commercial, Pricing, Competitor Intelligence, Coordinator | Detection, calculation, analysis, recommendation and presentation | External business write; hidden formula duplication; blocker override |
| APPROVAL PLANE | Андрей / explicitly delegated human approver | Approve or reject an exact scoped action | Broad standing approval inferred from conversation or contract acceptance |
| EXECUTION PLANE | Future Execution Agent, deterministic preflight, Ozon write adapter, verifier, audit log | Only an exact one-use approved operation | Any execution now; scope expansion; unverified write |

Control Center and Email/Telegram are presentation/transport surfaces across
the Read and Decision outputs. They are not separate decision authorities.

Execution Plane status: NOT READY.

## K. AI versus deterministic responsibility

| Function | Classification | Owner |
| --- | --- | --- |
| Financial formulas and Decimal rounding | DETERMINISTIC ENGINE REQUIRED | Calculator / Period Economics |
| Tariff/config selection and validity | DETERMINISTIC ENGINE REQUIRED | Input Resolver/config validator |
| P10/P12/P15 and hard-floor checks | DETERMINISTIC ENGINE REQUIRED | Calculator/policy engine |
| Settlement identity and case reconciliation | DETERMINISTIC ENGINE REQUIRED | Contract v1.1 validator |
| Settlement evidence interpretation/explanation | HYBRID | Validator + Pricing |
| Price recommendation | HYBRID | Pricing & Economics, using Pricing Policy / Constraint Engine output |
| Promotion/CPC profitability guardrail | HYBRID | Deterministic economics + Pricing |
| CPC/DRR/CTR arithmetic | DETERMINISTIC ENGINE REQUIRED | CPC analytics |
| CPC problem diagnosis | HYBRID | Metric engine + Commercial |
| Demand/stock/logistics thresholds | DETERMINISTIC ENGINE REQUIRED | Monitoring/analytics rules |
| Commercial narrative and bounded hypotheses | AI SUITABLE | Commercial |
| Competitor snapshot comparison and finding thresholds | DETERMINISTIC ENGINE REQUIRED | Analyzer/Finding Engine |
| Competitor narrative, threat and opportunity context | AI SUITABLE | Competitor Intelligence |
| Data freshness and dependency gating | DETERMINISTIC SUPPORT GATE | Data Health Gate |
| Task routing and dependency planning | AI SUITABLE | Coordinator with deterministic registry validation |
| Executive summary | AI SUITABLE | Coordinator |
| External execution preflight | DETERMINISTIC ENGINE REQUIRED | Future Execution Plane |
| External write authorization | HUMAN ONLY | Approval Plane |

An AI role may explain a deterministic result but must cite the result and
engine version. It must not reconstruct the arithmetic from prose.

## L. Block diagram

~~~mermaid
flowchart TB
    Owner[Owner — Андрей]
    Coord[EFA Coordinator<br/>routing + final presentation]
    Commercial[Commercial Analyst]
    Pricing[Pricing & Economics]
    Competitor[Competitor Intelligence]

    subgraph ReadPlane[READ PLANE]
        Ozon[Ozon Seller / Performance / buyer evidence]
        Collectors[Collectors<br/>commercial + controlled competitor]
        DB[(PostgreSQL)]
        MCP[EFA Read MCP / mcp_read]
    end

    subgraph Engines[DETERMINISTIC ENGINES]
        Health[Data Health Gate]
        Period[Period Economics]
        Calc[Calculator + Input Resolver]
        Decision[Pricing Policy / Constraint Engine]
        Finding[Snapshot Analyzer + Finding Engine + Summary]
        Metrics[CPC / Promotion / Anomaly / Tax validators]
    end

    subgraph ApprovalPlane[APPROVAL PLANE]
        Gate{Human Approval Gate}
    end

    subgraph ExecutionPlane[EXECUTION PLANE — NOT READY]
        Exec[Future Execution Agent]
        Verify[Read-back verification + audit]
    end

    Owner -->|REQUEST| Coord
    Coord -->|SELECTIVE REQUEST| Commercial
    Coord -->|SELECTIVE REQUEST| Pricing
    Coord -->|SELECTIVE REQUEST| Competitor
    Coord -->|READINESS REQUEST| Health

    Ozon -->|READ| Collectors
    Collectors -->|INTERNAL WRITE| DB
    DB -->|READ| MCP
    DB -->|READ| Period
    DB -->|READ| Finding
    MCP -->|BOUNDED FACTUAL READ| Coord
    MCP -->|EVIDENCE| Commercial
    MCP -->|EVIDENCE| Pricing
    MCP -->|EVIDENCE| Health
    Period -->|EVIDENCE| Commercial
    Period -->|EVIDENCE| Pricing
    Calc -->|EVIDENCE| Pricing
    Finding -->|EVIDENCE| Competitor
    Metrics -->|EVIDENCE| Commercial
    Metrics -->|EVIDENCE| Pricing
    Pricing -->|CALCULATE / EVALUATE| Decision
    Decision -->|CALCULATIONS + POLICY + ALLOWED/BLOCKED ACTIONS| Pricing
    Commercial -->|EVIDENCE| Pricing
    Competitor -->|EVIDENCE| Pricing
    Pricing -->|RECOMMENDATION| Coord
    Commercial -->|EVIDENCE / RECOMMENDATION| Coord
    Competitor -->|EVIDENCE| Coord
    Health -->|STATUS / GATE| Coord
    Coord -->|RECOMMENDATION| Owner

    Owner -->|APPROVAL| Gate
    Gate -.->|APPROVED PAYLOAD — FUTURE| Exec
    Exec -.->|WRITE — FUTURE| Ozon
    Verify -.->|READ / VERIFY STATE| Ozon
    Ozon -.->|OBSERVED STATE| Verify
    Verify -.->|EVIDENCE| Coord
~~~

The dotted path is deliberately unavailable in v1.

## M. Sequence diagrams

### M.1 Daily analysis

~~~mermaid
sequenceDiagram
    participant C as Scheduled Collectors
    participant DB as PostgreSQL
    participant H as Data Health Gate
    participant CA as Commercial Analyst
    participant CI as Competitor Intelligence
    participant PE as Pricing & Economics
    participant CO as Coordinator
    participant O as Owner/Channels

    C->>DB: INTERNAL WRITE — observed facts and run freshness
    CO->>H: REQUEST daily readiness
    H->>DB: READ run state and freshness
    H-->>CO: STATUS / domain gates
    alt Required commercial data is healthy
        par Commercial branch
            CO->>CA: REQUEST daily business review
            CA->>DB: READ curated facts + Period Economics
            CA-->>CO: EVIDENCE + attention items
        and Competitor branch
            CO->>CI: REQUEST latest persisted competitor context
            CI->>DB: READ complete Summary
            CI-->>CO: EVIDENCE + severity
        end
        opt Deterministic price/promotion trigger exists
            CO->>PE: REQUEST decision with Commercial/Competitor refs
            PE-->>CO: RECOMMENDATION or blocker
        end
        CO-->>O: One Owner Brief
    else Required source stale/failed
        H-->>CO: DATA_STALE or DEPENDENCY_FAILED / DO_NOT_DECIDE
        CO-->>O: Blocked brief with available unaffected facts
    end
~~~

### M.2 Price decision

~~~mermaid
sequenceDiagram
    participant O as Owner
    participant CO as Coordinator
    participant H as Data Health Gate
    participant CA as Commercial Analyst
    participant CI as Competitor Intelligence
    participant PE as Pricing & Economics
    participant E as Deterministic Pricing Engines

    O->>CO: Нужно ли менять цену УФ 004Б?
    CO->>H: REQUEST freshness/readiness
    H-->>CO: STATUS
    alt Required data passes
        opt Business evidence required
            CO->>CA: REQUEST demand/stock/logistics/CPC context
            CA-->>CO: EVIDENCE
        end
        opt Market evidence required
            CO->>CI: REQUEST relevant competitor context
            CI-->>CO: EVIDENCE
        end
        CO->>PE: REQUEST canonical PRICE_DECISION with evidence refs
        PE->>E: READ/CALCULATE selected mode
        E-->>PE: Versioned economics + policy result
        PE-->>CO: One canonical recommendation
        CO-->>O: Recommendation + evidence + HUMAN_APPROVAL_REQUIRED
    else Data stale or dependency failed
        CO-->>O: DO_NOT_DECIDE with exact blocker
    end
~~~

### M.3 Competitor alert

~~~mermaid
sequenceDiagram
    participant OP as Operator
    participant OZ as Ozon Buyer Evidence
    participant CY as Controlled Daily Cycle
    participant FE as Finding Engine
    participant G as Human Persistence Gate
    participant W as Controlled Persistence Writer
    participant DB as PostgreSQL
    participant CI as Competitor Intelligence
    participant CO as Coordinator
    participant O as Owner

    OP->>OZ: READ manual controlled collection
    OZ-->>CY: Immutable evidence
    CY->>FE: Validated snapshot analysis
    FE-->>CY: Proposed factual Finding Set
    CY-->>G: Hashes, identities, expected inserts
    G-->>W: APPROVED exact persistence payload
    W->>DB: INTERNAL WRITE — approved Finding Set
    CI->>DB: READ latest complete Finding Set
    DB-->>CI: Persisted evidence
    CI->>CI: Interpret without rescoring
    alt INFO only
        CI-->>CO: EVIDENCE for Control Center/daily brief
    else WATCH or IMPORTANT
        CI-->>CO: EVIDENCE + original severity
        CO-->>O: Alert / review request
    end
~~~

### M.4 Settlement validation

~~~mermaid
sequenceDiagram
    participant O as Owner/Reviewer
    participant F as Finance and Closing Evidence
    participant PE as Pricing & Economics
    participant V as Contract v1.1 Validator
    participant R as Validation Registry
    participant G as Implementation Approval Gate

    O->>PE: REQUEST settlement validation
    PE->>F: READ linked order/period evidence
    F-->>PE: Evidence with provenance and lifecycle
    PE->>V: Validate empirical cases
    V-->>R: PASS / FAIL / INSUFFICIENT_SETTLEMENT_DATA / OZON_UNCLEAR per case
    R-->>PE: Aggregate gate state
    alt Any critical case is not PASS
        PE-->>O: Blocker; no settlement-aware conclusion
    else All required cases PASS
        PE-->>O: Validation package ready for separate review
        O->>G: Separate explicit implementation review
        Note over G: Contract approval alone does not authorize implementation
    end
~~~

### M.5 Future approved Ozon write

~~~mermaid
sequenceDiagram
    participant O as Owner
    participant CO as Coordinator
    participant PE as Decision Authority
    participant P as Deterministic Preflight
    participant G as Human Approval Gate
    participant X as Future Execution Agent
    participant OZ as Ozon
    participant A as Audit/Verifier

    O->>CO: REQUEST business decision
    CO->>PE: REQUEST canonical recommendation
    PE-->>CO: Recommendation artifact
    CO->>P: Validate target, limits, versions, freshness and rollback
    P-->>CO: Exact executable proposal
    CO-->>O: HUMAN_APPROVAL_REQUIRED
    alt Owner approves exact one-use payload
        O->>G: APPROVAL
        G->>X: Approved payload + expiry
        X->>OZ: WRITE exact operation
        A->>OZ: READ / verify state
        OZ-->>A: Observed state
        A-->>CO: Verification + audit evidence
        CO-->>O: Confirmed result or failed verification
    else Rejected, expired or changed
        G-->>CO: ACTION_NOT_ALLOWED
        CO-->>O: No write performed
    end
~~~

## N. Current to target migration

Every component has exactly one primary disposition from `KEEP`, `REFACTOR`,
`MERGE`, `DEPRECATE` or `RENAME_ROLE_ONLY`. Secondary actions do not alter that
primary classification.

| Current component | Primary disposition | Secondary actions | Target role/boundary | Reason |
| --- | --- | --- | --- | --- |
| AI Analyst v1.3 | REFACTOR | Remove embedded final price/promotion authority; emit the common envelope | Commercial Analyst + Coordinator presentation input | Preserve curated reads, daily coverage and report discipline without an all-purpose brain |
| Legacy Price Decision v1 | MERGE | DEPRECATE independent output after shadow comparison and approved cutover | Pricing Policy / Constraint Engine under Pricing & Economics | Preserve valid policy rules without a competing final decision |
| Calculator core v1.1 | KEEP | Label `LEGACY_FORECAST`; keep settlement extension gated | Deterministic Pricing engine | Preserve the pure Decimal formula source and validated legacy semantics |
| Recommendation Sidecar | REFACTOR | KEEP engine boundary; remove peer “second opinion” semantics | Shared deterministic engine boundary used by Pricing & Economics | Existing deployment boundary is suitable, but its contract and authority must change |
| Sidecar price recommendation | MERGE | Deprecate independent action vocabulary after transition | Pricing Policy / Constraint Engine | Keep confirmed price-window logic without a second price brain |
| Sidecar anomaly tool | KEEP | Return evidence envelope only | Commercial evidence engine | Equal-period detection is deterministic; diagnosis belongs to Commercial |
| Promotion monitoring/recommendation | REFACTOR | Split facts to Commercial and economics to Pricing | Commercial evidence + Pricing policy | One action schema; no Advertising/Promotion agent |
| Advertising shadow | KEEP | Add explicit financial-mode labels in future approved scope | Pricing deterministic guardrail | Preserve scenario arithmetic without campaign authority |
| Period Economics | KEEP | Preserve distinct formula semantics | Shared deterministic evidence engine | Proven production source; not a substitute for settlement |
| Competitor Monitor | KEEP | Add a common event envelope only after stabilization approval | Controlled Read Plane source | Preserve its runbook, immutable evidence and persistence boundary |
| Finding Engine | KEEP | No AI severity duplication | Deterministic competitor engine | Detection, taxonomy and severity remain deterministic |
| Competitor Summary | KEEP | Emit common evidence references and freshness status | Competitor evidence + Coordinator presentation | Preserve stable DTO and complete-set checks |
| EFA Read MCP | KEEP | Add only separately approved curated reads | Shared Read Plane adapter | Existing bounded tools and access controls form the correct security boundary |
| Distributed health checks | MERGE | Normalize SLA/status envelope; no AI wrapper | Deterministic Data Health Gate | One readiness authority per source/domain |
| Control Center | KEEP | Future read-only display of tasks, decisions and blockers | Presentation/observability surface | It observes; it does not decide |
| Email/Telegram | KEEP | Use one Owner Brief payload; add IDs only after approved implementation | Coordinator delivery adapters | Transport must not recalculate or decide |
| Daily Brief schedule | DEPRECATE | KEEP reusable renderers/source-quality patterns; leave old workflow inactive | Coordinator presentation where useful | Avoid two scheduled owner briefs |
| Collectors | KEEP | Report common freshness state to Data Health Gate | Read Plane ingestion | Ingestion is not reasoning |
| Tax Engine | KEEP | Integrate only after approved data-quality contract | Deterministic supporting engine | Preserve statutory separation and explicit PARTIAL quality |

Migration must be incremental. No current output is removed until its target
replacement produces equivalent or safer evidence in shadow comparison and an
explicit cutover is approved.

## O. Canonical recommendation authority

### O.1 Canonical path

~~~text
Evidence providers
    → deterministic calculation/detection
    → one registered domain authority
    → Coordinator presentation
    → Owner decision
~~~

For price and promotion economics specifically:

~~~text
Commercial evidence + Competitor evidence + Data Health Gate
    → deterministic calculations / Pricing Policy / Constraint Engine
    → calculations + policy result + hard-floor result
      + allowed action set + blocked actions + reasons/gates
    → Pricing & Economics canonical recommendation + decision_id
    → Coordinator presentation
    → Owner approval
~~~

AI Analyst, legacy Price Decision and Sidecar must not each publish peer
recommendations. In the target state:

- AI Analyst successor provides commercial evidence;
- Sidecar hosts deterministic engines;
- legacy Price Decision is absorbed into one versioned Pricing Policy /
  Constraint Engine that cannot publish a recommendation or `decision_id`;
- Pricing & Economics is the only price recommendation authority;
- Coordinator is the only owner-facing final packet publisher, but cannot alter
  the domain recommendation or blocker.

### O.2 Authority registry

| Decision type | Evidence providers | Decision authority | Presentation authority |
| --- | --- | --- | --- |
| PRICE | Commercial, Competitor, Data Health Gate, deterministic economics | Pricing & Economics | Coordinator |
| PROMOTION_ACTION | Commercial diagnostic, Data Health Gate, deterministic economics | Pricing & Economics | Coordinator |
| ELASTIC_ACTION | Commercial diagnostic, Data Health Gate, deterministic economics | Pricing & Economics | Coordinator |
| CPC/CPO CAMPAIGN RECOMMENDATION | CPC metrics, Data Health Gate, mandatory Pricing guardrail for spend/action | Commercial Analyst | Coordinator |
| SALES / DEMAND / STOCK ATTENTION | Collectors, Period Economics, Data Health Gate | Commercial Analyst | Coordinator |
| COMPETITOR THREAT / OPPORTUNITY | Finding Engine/Summary, Data Health Gate | Competitor Intelligence | Coordinator |
| DATA READINESS / DO_NOT_DECIDE | Run/health evidence | Deterministic Data Health Gate | Coordinator |
| ROUTING / OWNER BRIEF | Specialist envelopes | Coordinator | Coordinator |
| EXTERNAL ACTION APPROVAL | Canonical recommendation and preflight | Human only | Coordinator records/presents |

The registry allows several recommendation types without allowing several
authorities for the same type.

### O.3 Conflict resolution

If two components return different actions for the same decision type:

1. reject output from the non-authoritative component as non-canonical;
2. retain it as diagnostic evidence only if provenance is useful;
3. do not average or ask Coordinator to choose by opinion;
4. rerun the registered authority with the current evidence/version;
5. if authoritative inputs conflict, return CONTRACT_CONFLICT.

## P. Owner experience

### P.1 Default interaction

Андрей uses one main interface and natural language:

- “Почему сегодня упали продажи?”
- “Что требует моего внимания?”
- “Нужно ли менять цену УФ 004Б?”
- “Какой риск у текущей акции?”

Coordinator identifies intent, requests only required specialists and returns:

1. what happened;
2. why the evidence supports or does not support a conclusion;
3. financial impact where deterministically available;
4. risk and confidence;
5. recommended next step;
6. blocker or exact approval request.

The owner does not choose an agent for normal work.

### P.2 Direct specialist access

Optional shortcuts remain available for expert use:

- /price УФ 004Б
- /economics УФ 004Б 14d
- /competitor RAF 005Б
- /health collectors

`/commercial` and `/settlement` may remain advanced/internal aliases, but they
are not required owner entrypoints. Phase 1 must not introduce a large public
command namespace; natural-language routing through Coordinator remains the
primary UX.

A direct call bypasses Coordinator routing, not governance. The specialist
still returns the common envelope, uses the same deterministic engines and
cannot write externally.

### P.3 Scheduled and alert experience

- one daily owner brief, not parallel Analyst and Daily Brief messages;
- INFO competitor changes stay in Control Center/daily brief;
- WATCH enters the owner brief;
- IMPORTANT or system-wide DO_NOT_DECIDE may create a targeted alert only
  after an alert policy is explicitly approved;
- no unchanged “all normal” alert stream beyond the daily brief;
- every proposed action shows source freshness, decision version and approval
  requirement.

## Q. Recommended agent count

### Q.1 Core agents

Recommended: 4 logical core AI roles.

1. EFA Coordinator.
2. Commercial Analyst.
3. Pricing & Economics.
4. Competitor Intelligence.

### Q.2 Support agents

Recommended: 0 support AI roles.

Operations & Data Health is reclassified as the deterministic Data Health Gate.
Freshness checks, dependency health, schema/readiness gates, `DATA_STALE`,
`DEPENDENCY_FAILED` and `DO_NOT_DECIDE` are deterministic. Coordinator provides
the natural-language explanation; no AI wrapper is created.

Total target AI roles: 4.

New runtime agents required in Phase 1: 0.

### Q.3 Deterministic engines — not counted as AI agents

1. Calculator core + Input Resolver.
2. Period Economics.
3. Pricing Policy / Constraint Engine + observed price-window calculation.
4. Competitor Snapshot Analyzer + Finding Engine + Summary validation.
5. CPC/Advertising and Promotion metric/economic validators.
6. Profit & Cost Anomaly detector.
7. Tax Engine.
8. Data Health Gate: freshness, dependency health, schema/readiness and
   message-contract validators.

These may remain co-located in existing services; the list is a responsibility
map, not a microservice plan.

### Q.4 Future agents

One possible future role: External Execution Agent.

Do not create it now. Preconditions include completed settlement gates where
relevant, approved write contracts, least privilege, idempotency, exact
approval binding, rollback, read-back verification, audit and a separately
approved production deployment.

### Q.5 Why four roles is optimal

- Fewer than four would mix business diagnosis, financial authority,
  competitor interpretation or owner-facing coordination.
- More than four would turn deterministic readiness, CPC, promotions,
  reporting, Calculator or findings into AI roles without an independent stable
  JTBD.
- The model keeps specialist expertise while preserving one owner interface.
- It reuses existing components and requires no new runtime process initially.

## R. Implementation roadmap — proposal only

No phase below is authorized by this document.

| Phase | Goal | Proposed scope | Exit criterion |
| --- | --- | --- | --- |
| 0 — Architecture fixes | Close review findings without runtime change | Apply and review the role, authority, route, message, status and diagram corrections in this document | Final architecture review accepts the corrected draft |
| 1 — Minimal shared contract | Establish the facade required before any authority cutover | Role registry, authority registry, `efa_assistant_message.v1`, status rules, `financial_mode` and `decision_id` | Contract/schema and blocker tests pass in isolation |
| 2 — Selective Coordinator routing in shadow | Validate minimal routing without changing current owner authority | Natural-language intent routing, bounded factual fast path, optional aliases and shadow specialist calls | No default fan-out; current production behavior remains unchanged |
| 3 — Canonical pricing path | Remove peer price brains only after the shared contract exists | Sidecar engine boundary, deterministic policy outputs, Pricing-owned recommendation/`decision_id`, legacy comparison | One canonical price result per request/SKU; discrepancies reviewed before approved cutover |
| 4 — Control Center visualization | Make orchestration observable | Read-only agent/task/dependency/decision/gate screens | UI matches source envelopes and never recalculates |
| 5 — Settlement-aware evolution | Close evidence gates before logic changes | Empirical cases, contract review, shadow-only calculation design | All required cases PASS plus separate implementation approval |
| 6 — Future Execution Plane | Consider guarded external actions | Exact approval, least privilege, idempotency, verification and audit | Separate architecture, security and production approvals |

`SHARED CONTRACT / STATUS FACADE MUST PRECEDE CANONICAL DECISION CUTOVER`.

Recommended sequencing detail:

1. Keep current production behavior unchanged while roles and schemas are
   reviewed.
2. Introduce the minimal shared contract and status facade before routing or
   canonical decision cutover.
3. Validate selective Coordinator routing in shadow with no default fan-out.
4. Run legacy Analyst/Price Decision and target canonical output in comparison
   mode with no external effect.
5. Cut owner-facing authority only after discrepancies are reviewed.
6. Retire duplicate paths after an explicit rollback-capable cutover.
7. Treat settlement-aware logic as a separate gated programme, not a hidden
   part of agent consolidation.

### R.1 Control Center future view

The future /capabilities area should remain read-only and add:

| View | Minimum fields |
| --- | --- |
| Agent status | role, READY/CONTROLLED/PARTIAL/NOT READY, health, contract version |
| Last run | started_at, finished_at, trigger, result status, evidence freshness |
| Current task | request_id, task_type, sku, period, source_agent, target_agent, elapsed state |
| Dependencies | required component, latest status, freshness, blocker |
| Decisions | decision_id, task_type, sku, authority, action, confidence, recommendation constraints, supersedes |
| Approval gates | required gate, state, approver, expiry; no secret or write control |
| Failures | status code, affected scope, blocked_by, safe next step |
| Provenance | source refs, engine/formula versions, production evidence timestamp |

Recommended layout:

- portfolio strip for the four AI roles plus the deterministic Data Health Gate;
- dependency graph for the selected task;
- latest canonical decisions table;
- prominent blocked-gates panel;
- drill-down from decision to evidence;
- no Execute button while Execution Plane is NOT READY.

Control Center must read persisted or supplied contract envelopes. It must not
derive a new recommendation from displayed numbers.

## S. Open questions

| Question | Recommended default for review |
| --- | --- |
| Should Coordinator be a separate service? | No for Phase 1; use the existing main interface until durable orchestration needs are proven |
| Where should canonical decision records live? | Design a small versioned internal registry only in Phase 2/3; do not add a database table in this task |
| What freshness SLA applies to each source? | Approve source-specific SLAs before the Data Health Gate can emit FRESH instead of UNKNOWN |
| When should Pricing run in the daily review? | Only on deterministic price/promotion/economic triggers, not automatically for every SKU |
| Which current Price Decision behaviors survive consolidation? | Preserve as shadow comparison; adopt only rules consistent with Calculator policy, evidence boundaries and v1.1 gates |
| When is legacy Price Decision retired? | After canonical shadow equivalence/discrepancy review and explicit cutover approval |
| Should direct commands use slash syntax? | Yes as optional aliases; natural language remains default |
| When may competitor alerts become automatic? | Only after stabilization acceptance, freshness policy and separately approved delivery policy |
| How are settlement case results stored? | Define an immutable validation registry with source/document provenance in a separate read-only design |
| Does Tax Engine participate in price decisions now? | No automatic integration while data is PARTIAL; pass explicit quality and block unsupported conclusions |
| Who may approve future actions? | Андрей by default; any delegated approver must be explicit per action class and environment |
| What is the canonical action vocabulary? | Approve per decision type in Phase 2; do not reuse legacy mixed labels unchanged |

## T. Final recommendation

Adopt four logical core AI roles and zero support AI roles. Implement no new
runtime agent at the first stage. Use the deterministic Data Health Gate for
freshness, dependency health, schema/readiness and DO_NOT_DECIDE decisions; do
not create an AI wrapper around it.

The target authority model is:

1. Coordinator owns routing and the single owner-facing packet.
2. Commercial owns business diagnosis and non-price commercial recommendations.
3. Pricing & Economics owns the sole canonical price and promotion-economic
   recommendation.
4. Competitor Intelligence owns competitor interpretation while Finding Engine
   retains factual detection/severity.
5. The deterministic Data Health Gate owns readiness and DO_NOT_DECIDE status.
6. Deterministic engines own arithmetic, thresholds, reconciliation and
   detection.
7. Андрей alone owns approval of external business actions.

Consolidate the current recommendation overlap by evolving AI Analyst into the
Commercial role, making Recommendation Sidecar the deterministic engine
boundary, absorbing legacy Price Decision into one versioned Pricing Policy /
Constraint Engine that emits no final recommendation, and retaining Coordinator
only as routing/presentation. Do not create
separate Advertising, Executive Brief, Calculator, Finding, Reporter or
Collector agents.

Settlement-aware Pricing remains blocked until the empirical and approval gates
in Contract v1.1 are satisfied. Execution Plane remains NOT READY.

AI_ASSISTANTS_ARCHITECTURE_V1_APPROVED_FOR_CANONICAL_DRAFT
