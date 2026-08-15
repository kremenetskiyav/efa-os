from datetime import date, datetime, timezone
import tempfile
from pathlib import Path
import unittest

from services.daily_brief.brief import build_brief
from services.daily_brief.renderers import finance_lag_text, render_email_html, render_pdf, render_telegram_text
from services.daily_brief.tests.test_brief import sources


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.payload = build_brief(sources(), date(2026, 8, 14), datetime(2026, 8, 15, tzinfo=timezone.utc))

    def test_finance_lag_is_explicit_and_null_is_not_zero(self):
        self.assertEqual(finance_lag_text(self.payload), "Финансовая экономика подтверждена по состоянию на 10.08.2026.")
        missing = sources(finance=False); missing["latest_economics"] = []
        text = render_telegram_text(build_brief(missing, date(2026, 8, 14)))
        self.assertIn("Прибыль до налога: НЕТ ДАННЫХ", text)
        self.assertNotIn("Прибыль до налога: 0", text)

    def test_telegram_is_deterministic_has_no_buyout_and_uses_same_values(self):
        payload = build_brief(sources(), date(2026, 8, 14), datetime(2026, 8, 15, tzinfo=timezone.utc))
        payload["data_quality"]["warnings"].append("confirmed_finance_not_available_for_business_date")
        for item in payload["offers"]:
            item["attention"] = {"level": "WATCH", "reasons": ["confirmed_finance_not_available_for_business_date"]}
        first = render_telegram_text(payload)
        self.assertEqual(first, render_telegram_text(payload))
        self.assertNotIn("выкуп", first.lower())
        self.assertIn("ИТОГО", first)
        self.assertIn("ТОВАРЫ", first)
        self.assertIn("ВНИМАНИЕ", first)
        self.assertIn("АКТУАЛЬНОСТЬ ДАННЫХ", first)
        self.assertIn("Заказано: 2 шт. · 250 ₽", first)
        self.assertIn("Прибыль до налога: 50 ₽", first)
        self.assertIn("Состояние цены требует обновления.", first)
        self.assertNotIn("price_state_stale", first)
        self.assertEqual(first.count("confirmed_finance_not_available_for_business_date"), 0)
        self.assertEqual(first.count("Финансовая экономика подтверждена по 10.08.2026, операционный отчёт — за 14.08.2026."), 1)
        self.assertIn("* Подтверждённая финансовая экономика относится к данным по 10.08.2026.", first)
        self.assertNotIn("доставлено НЕТ ДАННЫХ", first)
        self.assertNotIn("profit НЕТ ДАННЫХ", first)
        html = render_email_html(self.payload)
        self.assertIn("Сумма заказов: 250 ₽", html)
        self.assertIn("Confirmed profit before tax: 50 ₽", html)

    def test_telegram_shows_real_offer_specific_anomaly_once(self):
        payload = self.payload
        payload["offers"][0]["attention"] = {"level": "WATCH", "reasons": ["promotion_data_quality_review"]}
        text = render_telegram_text(payload)
        self.assertIn("ВНИМАНИЕ\nA — данные акции требуют проверки.", text)
        self.assertNotIn("Существенных подтверждённых аномалий нет.", text)

    def test_pdf_generated_and_cyrillic_extracts(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as directory:
            path = render_pdf(self.payload, Path(directory) / "brief.pdf")
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            self.assertEqual(len(reader.pages), 5)
            self.assertIn("Операционный день", text)
            self.assertIn("Финансовая экономика подтверждена", text)
            self.assertGreater(path.stat().st_size, 10_000)
