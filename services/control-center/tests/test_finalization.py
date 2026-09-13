import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import read_model as rm
import finance_model as fm
import w06_snapshot as w06

NOW = datetime(2026, 9, 13, 18, tzinfo=timezone.utc)
META = {f"W0{i}": {"name": str(i), "mode": "READ"} for i in range(9)}

class FinalizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "agents"
        self.root.mkdir()

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def test_latest_strategy_recommended_role_supersedes_old_role(self):
        self.write("REPORTS/W08/STRATEGY/2026-09-12/W08_EFA_PORTFOLIO_PROMOTION_STRATEGY_V1.md", "| SKU | Primary role | Why |\n|---|---|---|\n| UF003 | HOLD | older |")
        self.write("REPORTS/W08/STRATEGY/2026-09-13/W08_PORTFOLIO_STRATEGY_REFRESH_SEP13_V1.md", "NO TEST NOW\n| SKU | Current role | Recommended role | Main problem |\n|---|---|---|---|\n| UF003 | HOLD | FIX_FIRST | ECONOMICS |")
        model = rm.build(self.root, META, NOW)
        self.assertEqual("FIX_FIRST", model["portfolio"][2]["commercial_role"]["value"])
        self.assertTrue(model["strategy"]["no_paid_tests"])
        self.assertEqual("UNKNOWN", model["portfolio"][2]["cpc"]["value"])

    def test_applied_no_update_marker_is_not_pending_moderation(self):
        self.write("REPORTS/W04/CONTENT/2026-09-10/UF004_PUBLICATION_READBACK.md", "SKU: UF004\nModeration status: APPLIED; no Обновляется marker")
        model = rm.build(self.root, META, NOW)
        self.assertFalse(any(w["category"] == "MODERATION" for w in model["watchlist"]))
        self.assertEqual("UNKNOWN", model["portfolio"][3]["content_rating"]["value"])

    def test_rollback_supersedes_pending_without_old_primary_watch(self):
        self.write("REPORTS/W04/CONTENT/2026-09-10/UF002_PUBLISH.md", "SKU: UF002\nModeration status: IN PROGRESS")
        self.write("REPORTS/W04/CONTENT/2026-09-12/UF002_PUBLISH_ROLLBACK.md", "SKU: UF002\nFinal status: ABORTED / ROLLED BACK")
        model = rm.build(self.root, META, NOW)
        self.assertEqual("ABORTED / ROLLED BACK", model["portfolio"][1]["current_action"]["value"])
        self.assertFalse(any(w["category"] == "MODERATION" for w in model["watchlist"]))

    def test_newer_exact_dated_snapshot_beats_older_primary(self):
        period = next(p for p in fm.period_options(NOW) if p["id"] == "last7")
        old = w06.empty(period, NOW-timedelta(hours=2), "INSUFFICIENT_DATA")
        new = w06.empty(period, NOW-timedelta(hours=1), "INSUFFICIENT_DATA")
        self.write("REPORTS/W06/SNAPSHOTS/CURRENT_FINANCE_SNAPSHOT_V1.json", json.dumps(old))
        self.write("REPORTS/W06/SNAPSHOTS/2026-09-13/W06_FINANCE_SNAPSHOT_LATEST.json", json.dumps(new))
        actual, state = w06.read(self.root, period, NOW)
        self.assertEqual(new["generated_at"], actual["generated_at"])
        self.assertTrue(state["path"].endswith("LATEST.json"))
        self.assertNotIn(chr(92), state["path"])
        mismatch = dict(period, to="2026-09-11")
        self.assertIsNone(w06.read(self.root, mismatch, NOW)[0]["portfolio"]["seller_realization"])

    def test_russian_null_negative_and_quality_formatters(self):
        script = Path(__file__).resolve().parents[1] / "static/app.js"
        code = "const assert=require('assert');const ui=require(process.argv[1]);assert.strictEqual(ui.formatted('settlement_profit',{value:null}),'Нет данных');assert.strictEqual(ui.formatted('advertising',{value:null,missing_reason:'ACCOUNT_ADVERTISING_HAS_NO_CANONICAL_SKU_ALLOCATION'}),'Не распределена по SKU');assert(ui.formatted('proxy_result',{value:-12}).startsWith('-'));assert.strictEqual(ui.formatted('buyer_returned_units',{value:0}),'0');assert.strictEqual(ui.formatted('logistic_return_units',{value:3}),'3');assert.strictEqual(ui.translated('DEFEND'),'Защищать');assert.strictEqual(ui.translated('RECOVER'),'Восстановление');assert.strictEqual(ui.quality({value:1,mode:'SELLER_SIDE_PROXY'}),'Расчётные');assert.strictEqual(ui.quality({value:1,freshness:'STALE'}),'Устаревшие');"
        subprocess.run(["node", "-e", code, str(script)], check=True, capture_output=True)

    def test_primary_section_order_and_no_write_controls(self):
        page = (Path(__file__).resolve().parents[1] / "static/index.html").read_text(encoding="utf-8")
        ids = ["finance-title", "attention-title", "portfolio-title", "commercial-title", "agents-title", "governance-title", "system-title"]
        self.assertEqual(sorted(page.index('aria-labelledby="'+i+'"') for i in ids), [page.index('aria-labelledby="'+i+'"') for i in ids])
        script = (Path(__file__).resolve().parents[1] / "static/app.js").read_text(encoding="utf-8")
        self.assertNotIn("method:'POST'", script)
        self.assertNotIn("n8n", page[:page.index("<footer")].lower())

    def test_search_audit_uses_reported_grade_and_query_provenance(self):
        self.write("../REPORTS/W01/SEARCH_AUDIT/2026-09-11/W01_CURRENT_SEARCH_POSITION_AUDIT_V1.md", "| SKU | SEARCH_VISIBILITY | Best query |\n|---|---|---|\n| UF002 | CRITICAL | OEM-TEST, Москва rank 87; 2 unresolved |")
        model = rm.build(self.root, META, NOW)
        value = model["portfolio"][1]["search_visibility"]
        self.assertEqual("CRITICAL", value["value"])
        self.assertEqual("2026-09-11", value["observed_at"])
        self.assertIn("OEM-TEST", value["query"])
        self.assertTrue(value["regional_coverage_incomplete"])
        self.assertTrue(value["source"].startswith("repository-reports/"))

    def test_return_causes_keep_distinct_events_and_source_window(self):
        self.write("REPORTS/W02/ANALYSIS/2026-09-13/W02_UF005_RETURN_ROOT_CAUSE_ANALYSIS_V1.md", "SKU: UF005\nSignal window: 2026-09-06 through 2026-09-12\n| Exact Ozon reason | Confirmed customer return |\n|---|---|\n| Покупатель отменил заказ | NO |")
        context = rm.build(self.root, META, NOW)["returns_context"]
        self.assertEqual("UF005", context["sku"])
        self.assertIn("2026-09-06", context["window"])
        self.assertEqual("NO", context["events"][0]["Confirmed customer return"])

    def test_publication_reconciliation_supersedes_old_score_and_moderation(self):
        self.write("REPORTS/W04/CONTENT/2026-09-12/UF003_PUBLISH.md", "SKU: UF003\nModeration status: IN PROGRESS")
        self.write("REPORTS/W04/CONTENT/2026-09-13/UF003_PUBLICATION_STATUS_RECONCILIATION_V1.md", "SKU: UF003\nLatest read-only evidence: 2026-09-13T18:53:27+03:00\nCanonical publication status: PUBLISHED\nModeration status: MODERATION_COMPLETE\nContent rating: 68.5 / Базовый")
        model = rm.build(self.root, META, NOW)
        sku = model["portfolio"][2]
        self.assertEqual("PUBLISHED / MODERATION_COMPLETE", sku["current_action"]["value"])
        self.assertEqual(68.5, sku["content_rating"]["value"])
        self.assertEqual("2026-09-13T18:53:27+03:00", sku["content_rating"]["observed_at"])
        self.assertFalse(any(w["sku"] == "UF003" and w["category"] == "MODERATION" for w in model["watchlist"]))
