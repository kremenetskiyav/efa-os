import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
