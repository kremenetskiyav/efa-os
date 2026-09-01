import importlib.util
import json
import sys
import tempfile
import threading
import types
import unittest
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
STATIC_PATH = MODULE_PATH.parent / "static"
SPEC = importlib.util.spec_from_file_location("control_center_app", MODULE_PATH)
app = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = app
SPEC.loader.exec_module(app)


REPORT = """# AI Analyst v1.3 — Price Decision v1
## Сегодня: 2026-08-20 против 2026-08-19
### НАБЛЮДАТЬ · УФ 001Б
- Продажи: вчера **2 шт. / 1 248 ₽**, позавчера **1 шт. / 600 ₽**; изменение **1 шт. / 648 ₽**.
- Цена: **757 ₽** (2026-08-21); предыдущий снимок **757 ₽** (2026-08-16); изменение **0 ₽**.
- Остаток: **285 шт.** (2026-08-21); предыдущий снимок **285 шт.** (2026-08-13); изменение **0 шт.**.
- Логистика: ставка **10%** по 2026-08-20; изменение: **н/д**.
- Акции/CPC: активных акций 1, кандидатов 1; CPC расход **0 ₽**.
- Почему: продажи требуют наблюдения.
Данные продаж: **2026-08-14 — 2026-08-20**; сравнение: **2026-08-07 — 2026-08-13**.
## SKU: 1
### УФ 001Б · Ozon SKU 4601821825
#### PRICE DECISION V1
- Текущая цена: **757 ₽**.
- Фактическая цена продажи / цена активной акции: **624 ₽ / 624 ₽**.
- Рекомендация по цене: **ОСТАВИТЬ**.
- Рекомендуемая тестовая цена: **757 ₽**.
- Изменение: **0 ₽ / 0.0%**.
- Рекомендация по акции: **ВЫЙТИ**.
- Финансы периода: PBT **81.11 ₽**; прибыль/шт. **40.555 ₽**; маржа **6.49%**.
- Уверенность: **ВЫСОКАЯ**.
- Причина: Фактическая цена 624 ₽ совпадает с активной акцией; маржа 6.49% при 2 подтверждённых доставках.
"""


def competitor_summary(*, available=True, total=10, reason=None):
    own_lost = {
        "finding_key": "own-lost",
        "finding_type": "OWN_SEARCH_VISIBILITY_LOST",
        "severity": "WATCH",
        "offer_id": "УФ 005Б",
        "role_label": "Наша карточка",
        "message": "УФ 005Б: наша карточка не найдена по OEM 647941 в пределах лимита текущего снимка; найдена по OEM 647975.",
    }
    own_restored = {
        "finding_key": "own-restored",
        "finding_type": "OWN_SEARCH_VISIBILITY_RESTORED",
        "severity": "INFO",
        "offer_id": "УФ 004Б",
        "role_label": "Наша карточка",
        "message": "УФ 004Б: наша карточка снова найдена по OEM 5Q0819669 в пределах лимита текущего снимка.",
    }
    competitor = {
        "finding_key": "competitor-lost",
        "finding_type": "COMPETITOR_VISIBILITY_LOST",
        "severity": "INFO",
        "offer_id": "УФ 001Б",
        "role_label": "Основной конкурент",
        "message": "УФ 001Б: основной конкурент не найден по OEM 80292SLJ013 в пределах лимита текущего снимка.",
    }
    competitor_two = {
        "finding_key": "competitor-restored",
        "finding_type": "COMPETITOR_VISIBILITY_RESTORED",
        "severity": "INFO",
        "offer_id": "УФ 002Б",
        "role_label": "Основной конкурент",
        "message": "УФ 002Б: основной конкурент снова найден по OEM 6R0820367 в пределах лимита текущего снимка.",
    }
    price = {
        "finding_key": "price-change",
        "offer_id": "УФ 005Б",
        "role_label": "Дополнительный конкурент",
        "previous_price": 689,
        "current_price": 698,
        "delta": 9,
        "delta_pct": 1.3062,
        "currency": "RUB",
    }
    return {
        "contract_version": "competitor_monitor_summary.v1",
        "generated_at": "2026-08-28T05:00:00.000Z",
        "available": available,
        "degraded_reason": reason,
        "coverage": {
            "portfolio_sku_count": 5,
            "active_monitored_sku_count": 4,
            "unmonitored_skus": [{"offer_id": "УФ 003Б", "watchlist_state": "HOLD", "reason": None}],
        },
        "snapshot": {
            "reference_at": "2026-08-26T06:14:43.000Z",
            "captured_through": "2026-08-26T06:16:00.000Z",
            "freshness_status": "UNKNOWN",
        },
        "status": "WATCH" if total else "NORMAL",
        "counts": {
            "important_count": 0,
            "watch_count": 1 if total else 0,
            "info_count": 9 if total else 0,
            "total_findings": total,
        },
        "headline": own_lost if total else {"finding_key": None, "message": "Нет findings уровня WATCH или IMPORTANT."},
        "own": {
            "own_watch_count": 1 if total else 0,
            "own_restored_count": 1 if total else 0,
            "own_findings": [own_lost, own_restored] if total else [],
        },
        "competitors": {
            "visibility_lost_count": 4 if total else 0,
            "visibility_restored_count": 3 if total else 0,
            "findings": [competitor, competitor_two] if total else [],
        },
        "prices": {
            "price_changes_count": 1 if total else 0,
            "price_increased_count": 1 if total else 0,
            "price_decreased_count": 0,
            "price_changes": [price] if total else [],
        },
        "top_findings": [own_lost, own_restored, competitor, competitor_two, price] if total else [],
    }


class ControlCenterTests(unittest.TestCase):
    @staticmethod
    def collector_row(demand_at, demand_statuses):
        current = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        return {
            "demand_date": date(2026, 8, 24) if demand_at else None,
            "demand_at": demand_at,
            "demand_statuses": demand_statuses,
            "price_at": current,
            "stock_at": current,
            "stock_statuses": ["VALID"],
            "promotion_at": current,
            "promotion_statuses": ["valid"],
            "cpc_at": current,
            "cpc_date": current.date(),
            "cpc_statuses": ["SUCCESS_NONZERO"],
            "operations_date": current.date(),
            "operations_statuses": ["NO_DELIVERIES"],
        }

    @staticmethod
    def demand_health(row, now):
        collectors, _ = app.collector_snapshot(row, now)
        return next(item for item in collectors if item["name"] == "Спрос")

    def test_reuses_compact_report_parser(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.txt"
            path.write_text(REPORT, encoding="utf-8")
            snapshot, raw = app.report_snapshot(path)
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["counts"]["watch"], 1)
        self.assertEqual(snapshot["signals"][0]["sku"], "УФ 001Б")
        self.assertEqual(raw, REPORT)

    def test_reads_daily_schedule_from_cron(self):
        cron = """0 13 * * * root flock -n /run/lock/efa-ai-analyst.lock command
30 13 * * * root flock -n /run/lock/efa-ai-analyst-email.lock command"""
        now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
        next_analyst, analyst_label = app.parse_cron_schedule(cron, now)
        next_delivery, delivery_label = app.parse_cron_schedule(cron, now, "efa-ai-analyst-email.lock")
        self.assertEqual((next_analyst.hour, next_analyst.minute), (13, 0))
        self.assertEqual((next_delivery.hour, next_delivery.minute), (13, 30))
        self.assertIn("16:00 МСК", analyst_label)
        self.assertIn("16:30 МСК", delivery_label)

    def test_webhook_log_is_not_treated_as_delivery_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "delivery.log"
            path.write_text('{"message":"Workflow was started"}', encoding="utf-8")
            confirmation = app.delivery_confirmation(path)
        self.assertFalse(confirmation["confirmed"])
        self.assertEqual(confirmation["label"], "Нет подтверждения")

    def test_reads_delivery_switches_from_existing_workflow_files(self):
        with tempfile.TemporaryDirectory() as folder:
            delivery_path = Path(folder) / "delivery.json"
            old_brief_path = Path(folder) / "old.json"
            delivery_path.write_text(json.dumps({
                "active": True,
                "nodes": [
                    {"name": "Send Email", "type": "n8n-nodes-base.gmail"},
                    {"name": "Send Telegram", "type": "n8n-nodes-base.httpRequest"},
                ],
            }), encoding="utf-8")
            old_brief_path.write_text(json.dumps({"active": False}), encoding="utf-8")
            status = app.delivery_configuration(delivery_path, old_brief_path)
        self.assertEqual(status, {"email_on": True, "telegram_on": True, "old_brief_on": False})

    def test_system_timeline_contains_current_delivery_fields(self):
        page = (STATIC_PATH / "index.html").read_text(encoding="utf-8")
        for element_id in (
            "analyst-last", "analyst-next", "delivery-next", "delivery-last",
            "delivery-email", "delivery-telegram", "old-brief",
        ):
            self.assertIn(f'id="{element_id}"', page)
        self.assertNotIn("Последний email-report", page)

    def test_home_links_to_capabilities_catalog(self):
        page = (STATIC_PATH / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/capabilities"', page)
        self.assertIn("Возможности и команды", page)

    def test_capabilities_catalog_has_exact_audited_maturity_counts(self):
        catalog = json.loads((STATIC_PATH / "capabilities.json").read_text(encoding="utf-8"))
        actual = {}
        for item in catalog["capabilities"]:
            actual[item["status"]] = actual.get(item["status"], 0) + 1
        self.assertEqual(30, len(catalog["capabilities"]))
        self.assertEqual(
            {"READY": 16, "CONTROLLED": 7, "PARTIAL": 4, "NOT READY": 3},
            actual,
        )
        self.assertEqual(actual, catalog["summary"])

    def test_each_capability_has_required_operator_fields(self):
        catalog = json.loads((STATIC_PATH / "capabilities.json").read_text(encoding="utf-8"))
        required = {
            "id", "name", "status", "does", "example_command", "trigger",
            "read_write_scope", "limitations",
        }
        for item in catalog["capabilities"]:
            self.assertTrue(required.issubset(item), item.get("name"))
            self.assertTrue(all(str(item[field]).strip() for field in required), item["name"])

    def test_capabilities_catalog_keeps_settlement_and_write_gate_visible(self):
        catalog = json.loads((STATIC_PATH / "capabilities.json").read_text(encoding="utf-8"))
        page = (STATIC_PATH / "capabilities.html").read_text(encoding="utf-8")
        safety = catalog["safety"]
        self.assertEqual("INSUFFICIENT_SETTLEMENT_DATA", safety["fallback"])
        self.assertIn("Points / Green / Elastic", safety["title"])
        self.assertIn("Ozon write actions запрещены", safety["write_policy"])
        self.assertIn('id="safety-title"', page)
        self.assertIn('id="write-policy"', page)
        self.assertIn("INSUFFICIENT_SETTLEMENT_DATA", page)
        self.assertIn("Ozon write actions запрещены", page)
        self.assertIn('<details class="safety-details">', page)
        self.assertNotIn('<details class="safety-details" open>', page)

    def test_capabilities_catalog_is_explicitly_a_static_derived_snapshot(self):
        catalog = json.loads((STATIC_PATH / "capabilities.json").read_text(encoding="utf-8"))
        page = (STATIC_PATH / "capabilities.html").read_text(encoding="utf-8")
        self.assertEqual("2026-09-01", catalog["inventory_snapshot"])
        self.assertEqual("STATIC SNAPSHOT", catalog["snapshot_type"])
        self.assertEqual("Snapshot, not live runtime", catalog["runtime_note"])
        self.assertIn("not an independent source of truth", catalog["provenance"]["catalog_role"])
        self.assertEqual(
            [
                "EFA OS — Current Capabilities & Ready Agents Inventory",
                "Runtime evidence reconciled by the audit",
                "Repository contracts",
                "docs/contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md",
            ],
            catalog["provenance"]["canonical_sources"],
        )
        for marker in (
            "Inventory snapshot: 2026-09-01", "STATIC SNAPSHOT",
            "Snapshot, not live runtime", "capabilities.json",
            "docs/contracts/OZON_DISCOUNT_POINTS_SETTLEMENT_CONTRACT_V1.md",
        ):
            self.assertIn(marker, page)

    def test_owner_cheat_sheet_contains_fifteen_non_executing_commands(self):
        catalog = json.loads((STATIC_PATH / "capabilities.json").read_text(encoding="utf-8"))
        commands = catalog["daily_commands"]
        self.assertEqual(15, len(commands))
        self.assertTrue(all(item["command"].strip() for item in commands))
        self.assertTrue(any("ничего не изменяй" in item["command"].lower() for item in commands))

    def test_capabilities_route_and_static_catalog_are_served_read_only(self):
        server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/capabilities", timeout=3
            ) as response:
                page = response.read().decode("utf-8")
                self.assertEqual(200, response.status)
                self.assertIn("Возможности и команды", page)
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/static/capabilities.json", timeout=3
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(200, response.status)
                self.assertEqual("efa_capabilities_catalog.v1", payload["schema_version"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_detail_views_only_present_existing_report_data(self):
        prices = app.render_detail("prices", REPORT)
        cpc = app.render_detail("cpc", REPORT)
        self.assertIn("757 ₽ → 757 ₽", prices)
        self.assertIn("фактическая продажа: 624 ₽", prices)
        self.assertIn("ВЫСОКАЯ", prices)
        self.assertIn("81.11 ₽", prices)
        self.assertIn("40.555 ₽ / 6.49%", prices)
        self.assertIn("ВЫЙТИ", prices)
        self.assertIn("CPC расход", cpc)
        self.assertNotIn("Изменить цену", prices)

    def test_demand_is_healthy_when_latest_source_date_is_current_and_valid(self):
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        demand = self.demand_health(self.collector_row(now - timedelta(hours=1), ["valid"]), now)

        self.assertTrue(demand["ok"])
        self.assertEqual(demand["status"], "OK")

    def test_return_only_future_date_does_not_replace_latest_demand_snapshot(self):
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        row = self.collector_row(now - timedelta(hours=5), ["valid"])
        row["composite_date"] = date(2026, 8, 25)

        demand = self.demand_health(row, now)

        self.assertTrue(demand["ok"])
        self.assertEqual(row["demand_date"], date(2026, 8, 24))
        self.assertIn("WHERE demand_collected_at IS NOT NULL", app.COLLECTOR_QUERY)
        self.assertIn("AS demand_at", app.COLLECTOR_QUERY)

    def test_review_demand_status_is_unhealthy(self):
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        demand = self.demand_health(self.collector_row(now, ["review"]), now)

        self.assertFalse(demand["ok"])

    def test_missing_demand_is_unhealthy(self):
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        demand = self.demand_health(self.collector_row(None, []), now)

        self.assertFalse(demand["ok"])

    def test_stale_demand_is_unhealthy_after_54_hours(self):
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        demand = self.demand_health(
            self.collector_row(now - timedelta(hours=55), ["valid"]),
            now,
        )

        self.assertFalse(demand["ok"])

    def test_competitor_api_field_is_additive_and_core_fields_remain(self):
        with mock.patch.object(
            app, "read_database", new=mock.AsyncMock(return_value=(False, {}))
        ), mock.patch.object(app, "load_competitor_summary", return_value=competitor_summary()):
            payload = app.build_status()
        for key in (
            "generated_at", "system", "collectors", "last_data_update",
            "analyst", "delivery", "attention", "competitor_monitor",
        ):
            self.assertIn(key, payload)
        self.assertEqual("competitor_monitor_summary.v1", payload["competitor_monitor"]["contract_version"])

    def test_api_status_handler_returns_http_200_with_competitor_monitor(self):
        payload = {"system": {}, "competitor_monitor": competitor_summary()}
        with mock.patch.object(app, "build_status", return_value=payload):
            server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}/api/status", timeout=3
                ) as response:
                    actual = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(200, response.status)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
        self.assertIn("competitor_monitor", actual)

    def test_current_watch_mapping(self):
        value = competitor_summary()
        self.assertEqual((True, "WATCH"), (value["available"], value["status"]))

    def test_current_headline_mapping(self):
        headline = competitor_summary()["headline"]
        self.assertEqual("OWN_SEARCH_VISIBILITY_LOST", headline["finding_type"])
        self.assertIn("УФ 005Б", headline["message"])
        self.assertIn("647941", headline["message"])
        self.assertIn("647975", headline["message"])

    def test_current_dynamic_coverage_is_five_four_with_hold(self):
        coverage = competitor_summary()["coverage"]
        self.assertEqual((5, 4), (coverage["portfolio_sku_count"], coverage["active_monitored_sku_count"]))
        self.assertEqual("HOLD", coverage["unmonitored_skus"][0]["watchlist_state"])

    def test_current_severity_counts(self):
        counts = competitor_summary()["counts"]
        self.assertEqual((0, 1, 9, 10), tuple(counts.values()))

    def test_current_own_counts(self):
        own = competitor_summary()["own"]
        self.assertEqual((1, 1), (own["own_watch_count"], own["own_restored_count"]))

    def test_current_competitor_counts(self):
        value = competitor_summary()["competitors"]
        self.assertEqual((4, 3), (value["visibility_lost_count"], value["visibility_restored_count"]))

    def test_current_price_counts_and_direction(self):
        prices = competitor_summary()["prices"]
        self.assertEqual((1, 1, 0), (
            prices["price_changes_count"],
            prices["price_increased_count"],
            prices["price_decreased_count"],
        ))

    def test_zero_finding_state_is_healthy(self):
        value = competitor_summary(total=0)
        page = app.render_competitor_detail(value)
        self.assertTrue(value["available"])
        self.assertEqual("NORMAL", value["status"])
        self.assertIn("Изменений, соответствующих правилам Finding Engine v1, не обнаружено", page)

    def test_all_approved_degraded_reasons_render_module_only_state(self):
        reasons = (
            "FINDING_SET_MISSING", "FINDING_SET_INVALID", "FINDING_SET_STALE",
            "SNAPSHOT_UNAVAILABLE", "CONTROL_CENTER_COMPETITOR_READ_ERROR",
        )
        for reason in reasons:
            page = app.render_competitor_detail(
                competitor_summary(available=False, reason=reason)
            )
            self.assertIn("Данные мониторинга сейчас недоступны", page)
            self.assertNotIn("IMPORTANT 0", page)

    def test_summary_exception_is_isolated(self):
        with mock.patch.object(
            app, "read_competitor_summary", new=mock.AsyncMock(side_effect=RuntimeError("blocked"))
        ):
            value = app.load_competitor_summary()
        self.assertFalse(value["available"])
        self.assertEqual("CONTROL_CENTER_COMPETITOR_READ_ERROR", value["degraded_reason"])

    def test_competitor_failure_does_not_change_collectors_ok(self):
        healthy_collectors = [{"name": "Спрос", "ok": True}]
        with mock.patch.object(
            app, "read_database", new=mock.AsyncMock(return_value=(True, {}))
        ), mock.patch.object(
            app, "collector_snapshot", return_value=(healthy_collectors, None)
        ), mock.patch.object(
            app,
            "load_competitor_summary",
            return_value=competitor_summary(
                available=False, reason="CONTROL_CENTER_COMPETITOR_READ_ERROR"
            ),
        ):
            payload = app.build_status()
        self.assertTrue(payload["system"]["collectors_ok"])
        self.assertFalse(payload["competitor_monitor"]["available"])

    def test_safe_visibility_wording(self):
        page = app.render_competitor_detail(competitor_summary()).lower()
        self.assertIn("не найдена по oem 647941", page)
        self.assertIn("в пределах лимита текущего снимка", page)
        self.assertIn("видимость", page)

    def test_forbidden_visibility_claims_absent(self):
        content = (
            app.render_competitor_detail(competitor_summary())
            + (STATIC_PATH / "app.js").read_text(encoding="utf-8")
            + (STATIC_PATH / "index.html").read_text(encoding="utf-8")
        ).lower()
        for forbidden in (
            "карточка пропала", "товар исчез", "товар удалён", "продажи остановлены",
        ):
            self.assertNotIn(forbidden, content)

    def test_detail_role_labels(self):
        page = app.render_competitor_detail(competitor_summary())
        for label in ("Наша карточка", "Основной конкурент", "Дополнительный конкурент"):
            self.assertIn(label, page)

    def test_main_dashboard_does_not_render_all_findings(self):
        script = (STATIC_PATH / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("top_findings", script)
        self.assertEqual(5, len(competitor_summary()["top_findings"]))

    def test_details_use_four_required_groups(self):
        page = app.render_competitor_detail(competitor_summary())
        for title in (
            "Наша карточка", "Видимость конкурентов", "Изменения цен",
            "Прочие информационные события",
        ):
            self.assertIn(f"<h2>{title}</h2>", page)

    def test_detail_cards_are_deduplicated_by_finding_key(self):
        value = competitor_summary()
        duplicate = dict(value["own"]["own_findings"][0])
        value["competitors"]["findings"].append(duplicate)
        page = app.render_competitor_detail(value)
        self.assertEqual(1, page.count(duplicate["message"]))

    def test_price_formatting_is_neutral_and_factual(self):
        page = app.render_competitor_detail(competitor_summary())
        self.assertIn("689 → 698 ₽", page)
        self.assertIn("изменение 9 ₽ (+1.3%)", page)
        for forbidden in ("резко", "значительно", "агрессивно"):
            self.assertNotIn(forbidden, page.lower())

    def test_database_derived_html_is_escaped(self):
        value = competitor_summary()
        value["own"]["own_findings"][0]["role_label"] = "<script>alert(1)</script>"
        value["own"]["own_findings"][0]["message"] = "<img src=x onerror=alert(1)>"
        page = app.render_competitor_detail(value)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("&lt;img", page)

    def test_sensitive_provenance_fields_are_not_rendered(self):
        value = competitor_summary()
        value["own"]["own_findings"][0].update({
            "raw_ref": "secret-raw-ref",
            "raw_source_ref": "secret-source-ref",
            "observation_id": "00000000-0000-0000-0000-000000000000",
            "source_url": "https://example.invalid/private",
        })
        page = app.render_competitor_detail(value)
        for hidden in (
            "secret-raw-ref", "secret-source-ref", "00000000-0000-0000-0000-000000000000",
            "example.invalid",
        ):
            self.assertNotIn(hidden, page)

    def test_competitor_summary_is_json_serializable(self):
        payload = json.dumps(competitor_summary(), ensure_ascii=False)
        self.assertIn("competitor_monitor_summary.v1", payload)

    def test_source_path_is_exactly_three_mcp_read_queries(self):
        class Transaction:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False

        class Connection:
            def __init__(self):
                self.queries = []
                self.closed = False
            def transaction(self, *, readonly):
                self.readonly = readonly
                return Transaction()
            async def fetchrow(self, query, *args):
                self.queries.append(query)
                if "current_user AS role" in query:
                    return {"role": "efa_mcp_readonly", "db": "efa", "ro": "on"}
                return {"finding_set_id": "00000000-0000-0000-0000-000000000001"}
            async def fetch(self, query, *args):
                self.queries.append(query)
                return []
            async def close(self):
                self.closed = True

        connection = Connection()
        captured = {}

        async def connect(**kwargs):
            captured.update(kwargs)
            return connection

        fake_asyncpg = types.SimpleNamespace(connect=connect)
        with mock.patch.dict(sys.modules, {"asyncpg": fake_asyncpg}), mock.patch.dict(
            app.os.environ, {"DATABASE_URL": "postgresql://masked@db/efa"}
        ), mock.patch.object(app, "build_summary", return_value=competitor_summary()):
            value = app.asyncio.run(app.read_competitor_summary())
        source_queries = [query for query in connection.queries if "current_user AS role" not in query]
        self.assertEqual(3, len(source_queries))
        self.assertTrue(all("mcp_read.competitor_" in query for query in source_queries))
        self.assertTrue(connection.readonly)
        self.assertTrue(connection.closed)
        self.assertEqual("on", captured["server_settings"]["default_transaction_read_only"])
        self.assertTrue(value["available"])

    def test_jsonb_records_are_decoded_without_exposure(self):
        decoded = app._decode_competitor_record({
            "evidence": '[{"query":"647941"}]',
            "details": '{"membership_status":"CONTROL"}',
        })
        self.assertIsInstance(decoded["evidence"], list)
        self.assertEqual("CONTROL", decoded["details"]["membership_status"])

    def test_no_raw_table_fallback_or_database_write_path(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        runtime_sql = "\n".join((
            app.LATEST_FINDING_SET_SQL, app.FINDINGS_SQL, app.COVERAGE_SQL,
        ))
        self.assertNotIn("public.competitor_", runtime_sql)
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "ON CONFLICT"):
            self.assertNotIn(forbidden, runtime_sql.upper())
        self.assertNotIn("execute_write", source)

    def test_freshness_is_unknown_and_ui_makes_no_fresh_claim(self):
        value = competitor_summary()
        script = (STATIC_PATH / "app.js").read_text(encoding="utf-8").lower()
        self.assertEqual("UNKNOWN", value["snapshot"]["freshness_status"])
        self.assertNotIn("данные свежие", script)
        self.assertNotIn("freshness_status", script)

    def test_dashboard_has_competitor_block_and_detail_link(self):
        page = (STATIC_PATH / "index.html").read_text(encoding="utf-8")
        for element_id in (
            "competitor-panel", "competitor-status", "competitor-snapshot",
            "competitor-headline", "competitor-coverage", "competitor-own",
            "competitor-visibility", "competitor-prices", "competitor-important",
            "competitor-watch", "competitor-info",
        ):
            self.assertIn(f'id="{element_id}"', page)
        self.assertIn('href="/competitors"', page)

    def test_ui_uses_text_content_for_competitor_values(self):
        script = (STATIC_PATH / "app.js").read_text(encoding="utf-8")
        for element_id in (
            "competitor-headline", "competitor-coverage", "competitor-own",
            "competitor-visibility", "competitor-prices",
        ):
            self.assertIn(f"getElementById('{element_id}').textContent", script)

    def test_responsive_rules_cover_tablet_and_mobile(self):
        styles = (STATIC_PATH / "styles.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:850px)", styles)
        self.assertIn("@media(max-width:560px)", styles)
        self.assertIn(".competitor-metrics{grid-template-columns:1fr}", styles)


if __name__ == "__main__":
    unittest.main()
