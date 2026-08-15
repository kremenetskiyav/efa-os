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
        self.assertIn("Profit before tax: НЕТ ДАННЫХ", text)
        self.assertNotIn("Profit before tax: 0", text)

    def test_telegram_is_deterministic_has_no_buyout_and_uses_same_values(self):
        first = render_telegram_text(self.payload)
        self.assertEqual(first, render_telegram_text(self.payload))
        self.assertNotIn("выкуп", first.lower())
        self.assertIn("Сумма заказов: 250 ₽", first)
        self.assertIn("Profit before tax: 50 ₽", first)
        self.assertIn("price_state_stale", first)
        html = render_email_html(self.payload)
        self.assertIn("Сумма заказов: 250 ₽", html)
        self.assertIn("Confirmed profit before tax: 50 ₽", html)

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

