import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
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
- Рекомендация по акции: **ОСТАВИТЬ**.
- Расчётная текущая маржа: **13.6%** до налога; подтверждено доставок: **3**.
- Уверенность: **ВЫСОКАЯ**.
- Причина: Фактическая цена 624 ₽ совпадает с активной акцией; маржа 13.6% при 3 подтверждённых доставках.
"""


class ControlCenterTests(unittest.TestCase):
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
        cron = "0 13 * * * root flock -n /run/lock/efa-ai-analyst.lock command"
        next_run, label = app.parse_cron_schedule(cron, datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(next_run.hour, 13)
        self.assertIn("16:00 МСК", label)

    def test_missing_email_log_is_not_confirmed(self):
        self.assertEqual(app.email_confirmation(Path("missing-email-log"))["label"], "Нет подтверждения")

    def test_detail_views_only_present_existing_report_data(self):
        prices = app.render_detail("prices", REPORT)
        cpc = app.render_detail("cpc", REPORT)
        self.assertIn("757 ₽ → 757 ₽", prices)
        self.assertIn("фактическая продажа: 624 ₽", prices)
        self.assertIn("ВЫСОКАЯ", prices)
        self.assertIn("13.6%", prices)
        self.assertIn("CPC расход", cpc)
        self.assertNotIn("Изменить цену", prices)


if __name__ == "__main__":
    unittest.main()
