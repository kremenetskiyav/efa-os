"""Read-only Control Center projection. No decisions, financial math or writes.

JSON sidecars are preferred. Legacy adapters consume named tables/metadata in
known report families, never infer execution/approval from narrative prose.
"""
from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

UNKNOWN = "UNKNOWN"
SKUS = tuple(f"UF00{i}" for i in range(1, 6))
FRESHNESS = {"FRESH", "STALE", "UNKNOWN", "NOT_APPLICABLE"}
OPEN_STATES = {"RECOMMENDATION", "AWAITING_OWNER_APPROVAL", "EXECUTION_ELIGIBLE",
               "BLOCKED", "OBSERVATION", "MODERATION_PENDING"}
CLOSED_STATES = {"EXECUTED", "REJECTED", "CLOSED", "CANCELLED", "SUPERSEDED"}
PORTFOLIO_FIELDS = ("commercial_role", "search_visibility", "best_search_rank",
    "current_search_rank", "content_rating", "seller_price", "buyer_price",
    "promotion", "cpc", "cpo", "elastic", "contribution", "fbs_stock", "fbo_stock",
    "current_action", "priority")
DAILY_NAMES = {"W00": "W00_OWNER_BRIEF", "W01": "W01_MARKET_REPORT",
    "W02": "W02_CUSTOMER_REPORT", "W03": "W03_PROMOTION_REPORT",
    "W04": "W04_CONTENT_REPORT", "W05": "W05_VISUAL_REPORT",
    "W06": "W06_FINANCE_STATUS", "W07": "W07_CONTROL_REPORT",
    "W08": "W08_COMMERCIAL_REPORT"}


def clean(value):
    return str(value).strip().replace("`", "").replace("**", "").strip()


def sku_id(value):
    text = clean(value).upper().replace(" ", "").removeprefix("ЭФА")
    for sku in SKUS:
        if text in {sku, sku.replace("UF", "УФ") + "Б"}:
            return sku
    return None


def split_cells(line):
    """Escaped pipes and pipes inside code spans are not column separators."""
    cells, cell, escaped, code = [], "", False, False
    for char in line.strip().strip("|"):
        if escaped:
            cell += char
            escaped = False
        elif char == "\\":
            escaped = True
            cell += char
        elif char == "`":
            code = not code
            cell += char
        elif char == "|" and not code:
            cells.append(clean(cell))
            cell = ""
        else:
            cell += char
    return cells + [clean(cell)]


class Document:
    """Strict, line-based adapter for Markdown pipe tables and key:value headers."""
    def __init__(self, path, root):
        self.path, self.root = path, root
        self.meta, self.tables = {}, []
        self.section = ""
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            lines = []
        fenced, i = False, 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith(("```", "~~~")):
                fenced = not fenced
            if fenced:
                i += 1
                continue
            if line.startswith("#"):
                self.section = clean(line.lstrip("#"))
            if line.startswith("|") and i + 1 < len(lines):
                header = split_cells(line)
                sep = split_cells(lines[i + 1])
                if len(header) == len(sep) and all(c and set(c) <= set("-: ") for c in sep):
                    rows = []
                    i += 2
                    while i < len(lines) and lines[i].strip().startswith("|"):
                        cells = split_cells(lines[i])
                        if i + 1 < len(lines):
                            next_cells = split_cells(lines[i + 1])
                            if len(cells) == len(next_cells) and all(c and set(c) <= set("-: ") for c in next_cells):
                                break
                        if len(cells) == len(header):
                            row = dict(zip(header, cells))
                            rows.append(row)
                            if header[0] == "Field" and len(header) == 2:
                                self.meta.setdefault(cells[0], cells[1])
                        i += 1
                    self.tables.append((self.section, header, rows))
                    continue
            text = clean(line.removeprefix("- "))
            key, colon, value = text.partition(":")
            if colon and key and len(key) < 65 and not key.startswith(("http", "|")):
                self.meta.setdefault(key, clean(value))
            i += 1

    def rows(self, *required):
        for _, header, rows in self.tables:
            if set(required) <= set(header):
                yield from rows

    def get(self, *keys, default=UNKNOWN):
        return next((self.meta[k] for k in keys if self.meta.get(k)), default)

    @property
    def date(self):
        # Event/report dates outrank filesystem mtimes (copying files is not a run).
        for key in ("Execution time", "Latest read-only evidence", "Date and final read-back", "Reconciliation timestamp", "Completed", "Generated at", "Observed", "Compiled", "Date", "date"):
            value = self.meta.get(key, "")
            if value[:4].isdigit() and len(value) >= 10:
                if value[10:11] == "T":
                    return value.split(" ")[0]
                suffix = value[10:].strip(" ,")
                token = suffix.split(" ")[0].split("–")[-1]
                if len(token) in {5, 8} and token[2:3] == ":" and "MSK" in suffix:
                    return value[:10] + "T" + token + "+03:00"
                return value[:10]
        return next((p for p in reversed(self.path.parts) if len(p) == 10 and p[4:5] == "-" and p[:4].isdigit()), UNKNOWN)

    @property
    def source(self):
        if self.path.is_relative_to(self.root):
            return self.path.relative_to(self.root).as_posix()
        return "repository-reports/" + self.path.relative_to(self.root.parent / "REPORTS").as_posix()


def datum(value=None, doc=None, **extra):
    return {"value": value if value not in (None, "") else UNKNOWN,
            "source": doc.source if doc else None,
            "observed_at": doc.date if doc else None,
            "confirmation": "REPORTED" if doc else "UNAVAILABLE",
            "freshness": UNKNOWN, **extra}


def source_url(source):
    return "/agent-source?path=" + quote(source, safe="") if source else None


def safe_source(source):
    return isinstance(source, str) and source.startswith(("REPORTS/", "repository-reports/")) and ".." not in Path(source).parts and "\\" not in source and ":" not in source and source.endswith(".md")


def timestamp(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timezone required")
    return stamp


def validate_datum(value, now):
    if not isinstance(value, dict) or not all(value.get(k) for k in ("source", "observed_at", "confirmation")):
        raise ValueError("provenance required")
    if not safe_source(value["source"]) or timestamp(value["observed_at"]) > now:
        raise ValueError("invalid source/timestamp")
    scalar = value.get("value")
    if not isinstance(scalar, (str, int, float)) or isinstance(scalar, bool) or (isinstance(scalar, float) and not math.isfinite(scalar)):
        raise ValueError("scalar value required")
    if value.get("freshness", UNKNOWN) not in FRESHNESS:
        raise ValueError("freshness enum")
    return {"freshness": UNKNOWN, **value}


def documents(root, pattern):
    return [Document(p, root) for p in root.glob(pattern)
            if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root.resolve())]


def latest(docs):
    return max(docs, key=lambda d: (observation_key(d.date), d.source), default=None)


def observation_key(value):
    """Compare instants across offsets; date-only reports retain day precision."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def freshness(value):
    token = clean(value).split(" — ")[0]
    return "FRESH" if token == "CURRENT" else token if token in FRESHNESS else UNKNOWN


def reconcile_actions(events, now):
    """Latest exact reference wins. Explicit terminal states stay out of primary.

    No fuzzy reference matching, no approve=>execute promotion, no expired action
    in primary. Equal-time contradictory states are a gap, never a guessed winner.
    """
    grouped, gaps = {}, []
    for event in events:
        if not isinstance(event, dict):
            gaps.append("Invalid action record")
            continue
        if not all(event.get(k) for k in ("reference", "work", "status", "observed_at", "source")):
            gaps.append("Action missing exact reference, Work, state or provenance")
            continue
        if not isinstance(event["status"], str) or event["status"] not in OPEN_STATES | CLOSED_STATES:
            gaps.append("Unmapped action state: " + str(event["status"]))
            continue
        try:
            stamp = timestamp(event["observed_at"])
            if stamp > now or event["work"] not in DAILY_NAMES or not isinstance(event["reference"], str) or not safe_source(event["source"]):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            gaps.append("Action observation requires a non-future timezone timestamp")
            continue
        key = (event["work"], event["reference"])
        grouped.setdefault(key, []).append((stamp, event))
    current, history = [], []
    for entries in grouped.values():
        entries.sort(key=lambda pair: pair[0])
        stamp, event = entries[-1]
        if len({json.dumps(e, sort_keys=True) for t, e in entries if t == stamp}) > 1:
            gaps.append("Conflicting action snapshots: " + event["reference"])
            continue
        if event["status"] in CLOSED_STATES:
            history.append(event)
            continue
        expiry = event.get("valid_until")
        try:
            expires = timestamp(expiry) if expiry else None
            if not expires or expires.tzinfo is None or expires <= now:
                gaps.append("Action needs current validity confirmation: " + event["reference"])
                continue
        except (ValueError, TypeError, AttributeError):
            gaps.append("Invalid action validity: " + event["reference"])
            continue
        current.append(event)
    current.sort(key=lambda e: ({"P1": 0, "P2": 1, "P3": 2}.get(e.get("priority"), 3), e["reference"]))
    return current, history, gaps


def build(root, metadata, now=None):
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    gaps, sources = [], set()
    portfolio = {sku: {"sku": sku, **{field: datum() for field in PORTFOLIO_FIELDS}}
                 for sku in SKUS}
    works, report_docs = [], {}
    mapping = Document(root / "OZON_AI_AGENTS_WORK_CONTRACT_CROSSWALK_V1.md", root)
    roles = {row["Work"]: row for row in mapping.rows("Work", "Producer type", "Canonical role")}
    project = Document(root / "PROJECT_MAP.md", root)
    lifecycle = {}
    for section, _, rows in project.tables:
        work = section.split(" ")[0]
        lifecycle[work] = next((r.get("Value") for r in rows if r.get("Field") == "Current status"), UNKNOWN)
    for wid, info in metadata.items():
        docs = documents(root, f"REPORTS/{wid}/DAILY/*/{DAILY_NAMES[wid]}.md")
        if not docs:
            docs = documents(root, f"REPORTS/{wid}/*/{DAILY_NAMES[wid]}.md")
        doc = latest(docs)
        report_docs[wid] = doc
        if doc:
            sources.add(doc.source)
        role = roles.get(wid, {})
        works.append({"id": wid, "name": info["name"], "mode": info["mode"],
            "canonical_role": role.get("Canonical role", UNKNOWN),
            "producer_type": role.get("Producer type", UNKNOWN),
            "canonical_status": doc.get("Canonical status", default="NOT_EMITTED") if doc and role.get("Producer type") == "CANONICAL_ROLE_INTERFACE" else "NOT_EMITTED",
            "status": doc.get(f"{wid} status", "Overall status", "Run status", "Run outcome", "Cycle status", "Status", "Gate status", "Final run status") if doc else UNKNOWN,
            "lifecycle_status": lifecycle.get(wid, UNKNOWN),
            "last_run": (None if doc.get("W06 validation run performed") == "NO" else doc.get("Completed", "Generated at", "Date", default=doc.date)) if doc else None,
            "freshness": freshness(doc.get("Freshness")) if doc else UNKNOWN,
            "blocker": doc.get("Blocker", "Active blocker") if doc else UNKNOWN,
            "open_action_count": None, "source": doc.source if doc else None,
            "audit_outcome": doc.get("Audit outcome") if doc and wid == "W07" else None,
            "latest_result": None})
        if not doc:
            gaps.append(f"{wid}: daily report unavailable; run due/failed is not inferred")

    def put(sku, field, value, doc, **extra):
        if sku in portfolio:
            existing = portfolio[sku][field]
            if existing["source"] and observation_key(existing["observed_at"]) > observation_key(doc.date):
                return
            portfolio[sku][field] = datum(value, doc, **extra)
            sources.add(doc.source)

    # W08 strategy is a recommendation source, never a current CPC/CPO switch.
    strategy = latest(documents(root, "REPORTS/W08/STRATEGY/*/*PORTFOLIO*STRATEGY*.md"))
    if strategy:
        for row in strategy.rows("SKU", "Recommended role", "Main problem"):
            put(sku_id(row["SKU"]), "commercial_role", row["Recommended role"], strategy, scope=row["Main problem"], recommendation=row)
        for row in strategy.rows("SKU", "Primary role", "Why"):
            put(sku_id(row["SKU"]), "commercial_role", row["Primary role"], strategy, scope=row["Why"])
        for row in strategy.rows("SKU", "Class", "Budget decision"):
            put(sku_id(row["SKU"]), "priority", row["Class"], strategy, scope=row["Budget decision"])
        works[-1]["latest_result"] = {"source": strategy.source, "observed_at": strategy.date,
                                      "status": strategy.get("Status")}

    # Exact observed table columns; never predicted content scores or future policy values.
    for doc in sorted(documents(root, "REPORTS/W04/AUDIT/*/*CONTENT_RATING*.md"), key=lambda d: (d.date, d.source)):
        for row in doc.rows("SKU", "Current score"):
            put(sku_id(row["SKU"]), "content_rating", row["Current score"], doc, scope="Observed score / 100; forecast excluded")

    watch, executions = [], []
    contribution_proxy = datum()
    finance_dir = root.parent / "REPORTS"
    finance_docs = [Document(p, root) for p in finance_dir.glob("W06/AUDIT/*/W06_EFA_ALL_SKU_AUGUST_UNIT_ECONOMICS_AUDIT_*.md") if p.is_file() and p.resolve().is_relative_to(finance_dir.resolve())]
    finance = latest(finance_docs)
    if finance:
        scope = finance.get("Period") + "; SELLER-SIDE PROXY. Current COGS; before tax, unallocated ads, Premium and later corrections. Not current margin."
        for row in finance.rows("SKU", "Proxy margin after matched CPC", "Was SKU profitable in August"):
            put(sku_id(row["SKU"]), "contribution", row["Proxy margin after matched CPC"], finance,
                scope=scope, confirmation="PROXY")
        value = finance.get("Confirmed portfolio result after CPC+CPO")
        if value != UNKNOWN:
            contribution_proxy = datum(value, finance, confirmation="PROXY", scope=finance.get("Period") + "; after portfolio CPC+CPO, before tax and Premium; not current/final contribution")
            sources.add(finance.source)
    for doc in sorted(documents(root, "REPORTS/W03/EXECUTION/*/*.md"), key=lambda d: (d.date, d.source)):
        for row in doc.rows("SKU", "CPC post-state", "CPO post-state", "Verification"):
            if "PASS" not in row["Verification"]:
                continue
            sku = sku_id(row["SKU"])
            cpc = row["CPC post-state"]
            state = "OFF" if "НЕАКТИВНА" in cpc or "INACTIVE" in cpc else "ON" if "ACTIVE" in cpc else UNKNOWN
            put(sku, "cpc", state, doc, scope=cpc + "; " + row["Verification"])
            put(sku, "cpo", row["CPO post-state"].split(",")[0], doc, scope=row["CPO post-state"])
        for row in doc.rows("SKU", "Seller-side price post", "Site price post", "Elastic configured state"):
            sku = sku_id(row["SKU"])
            put(sku, "seller_price", row["Seller-side price post"], doc, scope="Seller-side displayed price; NOT seller realization")
            put(sku, "buyer_price", row["Site price post"], doc, scope="Site price display; payment/region scope as reported; NOT seller realization")
            put(sku, "elastic", row["Elastic configured state"], doc)
        for row in doc.rows("Target", "Write", "Immediate read-back"):
            # Closed operation mapping for this known execution table; raw result retained.
            parts = row["Target"].split("/")
            sku = sku_id(parts[-1])
            mechanism = parts[0].split(" ")[0]
            op = {("CPC", "switch ON -> OFF"): "CPC_PAUSE", ("CPO", "switch ON -> OFF"): "CPO_DISABLE"}.get((mechanism, row["Write"]), UNKNOWN)
            executions.append({"timestamp": doc.date, "sku": sku or UNKNOWN, "operation": op,
                "reference": doc.get("Proposal reference", "Proposal"), "executor": doc.get("Executor"),
                "result": row["Write"], "read_back": row["Immediate read-back"], "source": doc.source})
            sources.add(doc.source)
        if not doc.get("Unexpected linked changes", default="NONE").upper().startswith(("NONE", "NO ")):
            watch.append({"category": "WATCH", "work": "W03", "sku": "Portfolio",
                "reason": doc.get("Unexpected linked changes"), "source": doc.source,
                "observed_at": doc.date, "status": "OZON_UNCLEAR"})

    content_docs = documents(root, "REPORTS/W04/CONTENT/*/*PUBLISH*.md") + documents(root, "REPORTS/W04/CONTENT/*/*PUBLICATION_READBACK*.md") + documents(root, "REPORTS/W04/CONTENT/*/*PUBLICATION_STATUS_RECONCILIATION*.md")
    for doc in sorted(content_docs, key=lambda d: (d.date, d.source)):
        state = doc.get("Moderation status")
        sku = sku_id(doc.get("SKU"))
        if sku and state != UNKNOWN:
            publication = doc.get("Canonical publication status")
            combined = publication + " / " + state if publication != UNKNOWN else state
            put(sku, "current_action", combined, doc)
            if publication == "PUBLISHED" and state == "MODERATION_COMPLETE":
                score = doc.get("Content rating").split(" / ")[0]
                try:
                    score = float(score)
                    if math.isfinite(score) and 0 <= score <= 100:
                        put(sku, "content_rating", score, doc, scope="Observed post-publication content rating; " + doc.get("Content rating"))
                except ValueError:
                    pass
            watch.append({"category": "MODERATION", "work": "W04", "sku": sku,
                "reason": state, "status": "MODERATION_PENDING", "source": doc.source, "observed_at": doc.date})
            # A previously observed numeric score must not masquerade as post-update.
            if not state.upper().startswith("APPLIED") and any(token in state.upper() for token in ("PENDING", "ОБНОВЛЯЕТСЯ", "IN PROGRESS")):
                # A dated submission with no exact time cannot certify a numeric
                # post-submit rating. Conservatively invalidate same-day scores.
                if str(portfolio[sku]["content_rating"]["observed_at"] or "")[:10] <= doc.date[:10]:
                    portfolio[sku]["content_rating"] = datum("RECALCULATION PENDING", doc)
        elif sku and doc.get("Final status") != UNKNOWN:
            put(sku, "current_action", doc.get("Final status"), doc)

    # Query-to-SKU mapping comes from evidence rows, never hardcoded OEM identities.
    market = report_docs.get("W01")
    if market:
        evidence_sku = {}
        for _, _, rows in market.tables:
            for row in rows:
                values = list(row.values())
                for value in values:
                    sku = sku_id(value)
                    if sku and values[0].startswith("EV-W01-"):
                        evidence_sku[values[0].split("-")[-1]] = sku
        ranked = {}
        for row in market.rows("Exact query", "EFA observation", "Scan limit", "Evidence"):
            sku = evidence_sku.get(row["Evidence"].split("-")[-1])
            if sku:
                ranked.setdefault(sku, []).append(row)
        for sku, rows in ranked.items():
            ranks = [int(r["EFA observation"].removeprefix("Rank ")) for r in rows
                     if r["EFA observation"].startswith("Rank ") and r["EFA observation"].removeprefix("Rank ").isdigit()]
            scope = "; ".join(r["Exact query"] + ": " + r["EFA observation"] + " / scan " + r["Scan limit"] for r in rows)
            put(sku, "current_search_rank", " / ".join(str(r["EFA observation"]).replace("Not found within monitored query and scan limit", ">" + r["Scan limit"]).replace("Rank ", "") for r in rows), market, scope=scope)
            put(sku, "best_search_rank", min(ranks) if ranks else UNKNOWN, market, scope="Best across current observed queries, not all-time; " + scope)
            put(sku, "search_visibility", f"{len(ranks)} / {len(rows)} queries", market, scope=scope)

    # The bounded search audit supersedes the daily query-count adapter.
    search_docs = [Document(p, root) for p in (root.parent / "REPORTS").glob("W01/SEARCH_AUDIT/*/*CURRENT_SEARCH_POSITION_AUDIT*.md") if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to((root.parent / "REPORTS").resolve())]
    search = latest(search_docs)
    if search:
        for row in search.rows("SKU", "SEARCH_VISIBILITY", "Best query"):
            if sku_id(row["SKU"]) not in portfolio:
                continue
            portfolio[sku_id(row["SKU"])]["search_visibility"] = datum(row["SEARCH_VISIBILITY"], search,
                scope="; ".join(f"{key}: {value}" for key, value in row.items()),
                regional_coverage_incomplete=any(re.search(r"\b[1-9]\d* unresolved\b|UNKNOWN|STALE", value) for value in row.values()),
                query=row["Best query"], evidence_tables=search.tables)
        sources.add(search.source)
    # Only the most recent publication observation can remain in active moderation.
    watch = [item for item in watch if item["category"] != "MODERATION" or (
        portfolio[item["sku"]]["current_action"]["source"] == item["source"] and not str(item["reason"]).upper().startswith("APPLIED") and
        any(token in str(item["reason"]).upper() for token in ("PENDING", "IN PROGRESS", "ОБНОВЛЯЕТСЯ")))]

    return_analysis = latest(documents(root, "REPORTS/W02/ANALYSIS/*/*RETURN_ROOT_CAUSE_ANALYSIS*.md"))
    returns_context = None
    if return_analysis:
        returns_context = {"source": return_analysis.source, "observed_at": return_analysis.date,
            "sku": sku_id(return_analysis.get("SKU")), "window": return_analysis.get("Signal window"),
            "events": list(return_analysis.rows("Exact Ozon reason", "Confirmed customer return"))}
        sources.add(return_analysis.source)

    # Preserve blockers with their source authority. No omission implies closure.
    blockers = []
    for wid in ("W00", "W08"):
        doc = report_docs.get(wid)
        if not doc:
            continue
        for row in doc.rows("Blocker reference", "W06 status", "Effect on W08 conclusion"):
            blockers.append({"reference": row["Blocker reference"], "status": row["W06 status"],
                "reason": row["Effect on W08 conclusion"], "owner": "W06 / Pricing & Economics",
                "source": doc.source, "observed_at": doc.date})
        for row in doc.rows("Blocker", "Owner / emitter", "Effect", "Unblock condition"):
            # Financial records are already preserved above with exact references.
            if "W06" in row["Owner / emitter"] or "Pricing" in row["Owner / emitter"]:
                continue
            watch.append({"category": "DATA GAP", "work": wid, "sku": row["Affected scope"],
                "reason": row["Effect"], "status": row["Blocker"], "source": doc.source, "observed_at": doc.date})
    if blockers:
        works[6]["blocker"] = "; ".join(b["reference"] for b in blockers)
    for work in works:
        matching = [w["status"] for w in watch if w["status"].startswith(work["id"] + " ")]
        if matching:
            work["blocker"] = "; ".join(matching)
    # Latest specialist result supplements, and never overwrites, a daily run.
    for wid, docs in (("W01", search_docs), ("W02", documents(root, "REPORTS/W02/ANALYSIS/*/*RETURN_ROOT_CAUSE_ANALYSIS*.md")), ("W08", [strategy] if strategy else []), ("W03", documents(root, "REPORTS/W03/EXECUTION/*/*.md")),
                      ("W04", content_docs), ("W06", finance_docs)):
        doc = latest(docs)
        if doc:
            works[int(wid[1:])]["latest_result"] = {"source": doc.source, "observed_at": doc.date,
                "status": doc.get("Execution status", "Final status", "Publication status", "Status", default="REPORT AVAILABLE")}
            sources.add(doc.source)

    policy = Document(root / "W03_BOUNDED_AD_EXECUTION_POLICY_V2.md", root)
    sources.update(d.source for d in (policy, mapping, project) if d.path.is_file())
    governance = {"global_execution_plane": policy.get("Global Execution Plane"),
        "capability": policy.get("Capability ID"), "capability_status": policy.get("Capability status"),
        "policy": policy.get("Policy ID"), "policy_status": policy.get("Status"),
        "read_back": policy.get("Read-back"), "source": policy.source, "classes": []}
    for row in policy.rows("Class", "Operations", "Owner command gate"):
        governance["classes"].append({"class": row["Class"], "operations": row["Operations"], "gate": row["Owner command gate"]})

    # Optional curated snapshot: no automatic markdown proposal=>action conversion.
    # Default is explicitly incomplete, never 'zero owner actions'.
    events, queue_complete = [], False
    original_portfolio = deepcopy(portfolio)
    original_works = deepcopy(works)
    browser_access = datum()
    structured_watch = []
    snapshot_path = root / "CONTROL_CENTER_READ_MODEL_V2.json"
    if snapshot_path.is_file():
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
            if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "efa.control_center.v2":
                raise ValueError("schema_version")
            if timestamp(snapshot["observed_at"]) > now or timestamp(snapshot["valid_until"]) <= now:
                raise ValueError("snapshot validity")
            events = snapshot.get("actions", [])
            if not isinstance(events, list):
                raise ValueError("actions")
            queue_complete = snapshot.get("queue_complete") is True
            for item in snapshot.get("portfolio", []):
                sku = item.get("sku")
                if sku not in portfolio:
                    raise ValueError("sku")
                for field in PORTFOLIO_FIELDS:
                    value = item.get(field)
                    if value is None:
                        continue
                    value = validate_datum(value, now)
                    existing = portfolio[sku][field]
                    if not existing["source"] or observation_key(value["observed_at"]) > observation_key(existing["observed_at"]):
                        portfolio[sku][field] = {"freshness": UNKNOWN, **value}
                    elif observation_key(value["observed_at"]) == observation_key(existing["observed_at"]) and value["value"] != existing["value"]:
                        portfolio[sku][field] = datum("CONFLICT", scope="Equal-time source conflict; observations preserved", observations=[existing, value])
                        gaps.append(f"{sku}/{field}: equal-time source conflict")
            for update in snapshot.get("works", []):
                if update.get("id") not in metadata or not safe_source(update.get("source")):
                    raise ValueError("work identity/source")
                observed = timestamp(update["observed_at"])
                if observed > now or update.get("freshness", UNKNOWN) not in FRESHNESS:
                    raise ValueError("work timestamp/freshness")
                work = works[int(update["id"][1:])]
                if work["source"] and update["observed_at"][:10] < (report_docs[update["id"]].date[:10]):
                    continue
                if work["producer_type"] != "CANONICAL_ROLE_INTERFACE" and update.get("canonical_status", "NOT_EMITTED") != "NOT_EMITTED":
                    raise ValueError("support Work cannot emit canonical status")
                for field in ("status", "canonical_status", "freshness", "blocker", "source", "last_run", "audit_outcome"):
                    if field in update:
                        if update[field] is not None and not isinstance(update[field], str):
                            raise ValueError("work field type")
                        work[field] = update[field]
            if "browser_access" in snapshot:
                browser_access = validate_datum(snapshot["browser_access"], now)
            for item in snapshot.get("watchlist", []):
                if not safe_source(item.get("source")) or item.get("category") not in {"CRITICAL", "OWNER ACTION", "WATCH", "MODERATION", "DATA GAP"}:
                    raise ValueError("watchlist source/category")
                if timestamp(item["observed_at"]) > now:
                    raise ValueError("future watch observation")
                structured_watch.append(item)
            sources.add(snapshot_path.name)
        except (ValueError, OSError, TypeError, AttributeError, KeyError):
            events, queue_complete = [], False
            portfolio = original_portfolio
            works = original_works
            browser_access, structured_watch = datum(), []
            gaps.append("Invalid CONTROL_CENTER_READ_MODEL_V2.json; action queue unavailable")
    else:
        gaps.append("Structured current action lifecycle feed unavailable; Markdown proposals are not current approval records")
    queue, history, action_gaps = reconcile_actions(events, now)
    gaps.extend(action_gaps)
    sources.update(a["source"] for a in queue + history)
    sources.update(w["source"] for w in works if w["source"])
    sources.update(w["source"] for w in structured_watch)
    if browser_access["source"]:
        sources.add(browser_access["source"])
    watch.extend(structured_watch)
    for item in portfolio.values():
        sources.update(item[field]["source"] for field in PORTFOLIO_FIELDS if item[field]["source"])
    queue_complete = queue_complete and not action_gaps
    for work in works:
        work["open_action_count"] = sum(a["work"] == work["id"] for a in queue) if queue_complete else None
    counts = {}
    for key in ("cpc", "cpo", "promotion"):
        vals = [p[key]["value"] for p in portfolio.values()]
        counts[key] = {"active": sum(v == "ON" for v in vals), "known": sum(v in {"ON", "OFF"} for v in vals), "total": len(SKUS)}
    priorities = {letter: sum(p["priority"]["value"] == "PRIORITY " + letter for p in portfolio.values()) for letter in "ABC"}
    if any(p[field]["value"] == UNKNOWN for p in portfolio.values() for field in ("fbs_stock", "fbo_stock")):
        gaps.append("FBS/FBO stock coverage is incomplete; connect a structured operational snapshot")
    if any(p["promotion"]["value"] == UNKNOWN for p in portfolio.values()):
        gaps.append("Promotion participation requires an explicit observation; no visible marker is not OFF")
    if not browser_access["source"]:
        gaps.append("Browser access has no live health probe; historical successful read-back is not current access")
    if not contribution_proxy["source"]:
        gaps.append("Portfolio contribution proxy unavailable; no PBT substitution")
    from w06_snapshot import build as build_w06_finance
    finance = build_w06_finance(root, now)
    sources.update(finance["sources"])
    emitted = [snap for snap in finance["snapshots"].values() if snap["metadata"].get("snapshot_path")]
    if emitted:
        newest = max(emitted, key=lambda snap: observation_key(snap["metadata"]["generated_at"]))
        works[6]["latest_result"] = {"source": newest["metadata"]["snapshot_path"], "observed_at": newest["metadata"]["generated_at"], "status": "REPORT_AVAILABLE"}
    return {"schema_version": "efa.control_center.v2", "works": works, "portfolio": list(portfolio.values()),
        "finance": finance, "returns_context": returns_context,
        "strategy": {"source": strategy.source if strategy else None, "observed_at": strategy.date if strategy else None,
            "no_paid_tests": bool(strategy and "NO TEST NOW" in strategy.path.read_text(encoding="utf-8-sig"))},
        "owner_queue": queue, "queue_complete": queue_complete, "action_history": history,
        "commercial": {"contribution_proxy": contribution_proxy, "hard_floor": "12%", "target": "15–20%",
            "threshold_source": "Owner dashboard brief; display only", "counts": counts, "priorities": priorities,
            "priority_known": sum(priorities.values()), "financial_blockers": blockers,
            "settlement_status": "INSUFFICIENT_SETTLEMENT_DATA"},
        "governance": governance, "executions": sorted(executions, key=lambda e: e["timestamp"], reverse=True)[:20],
        "watchlist": watch, "data_gaps": list(dict.fromkeys(gaps)), "sources": sorted(sources),
        "browser_access": browser_access, "last_agent_cycle": works[0]["last_run"]}
