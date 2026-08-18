from datetime import datetime, timezone
import tempfile
from pathlib import Path
import unittest

from services.daily_brief.brief import build_brief
from services.daily_brief.renderers import finance_lag_text, render_email_html, render_pdf, render_telegram_text
from services.daily_brief.tests.test_brief import DAY, sources


class RendererV11Tests(unittest.TestCase):
    def setUp(self):
        self.payload = build_brief(sources(cpc_state="STUCK"), DAY, datetime(2026,8,18,tzinfo=timezone.utc))

    def test_finance_lag_and_historical_values_are_explicit(self):
        self.assertEqual(finance_lag_text(self.payload), "Экономика за 17.08.2026 не подтверждена; последняя подтверждённая дата — 14.08.2026.")
        text = render_telegram_text(self.payload)
        self.assertIn("Сегодня: не подтверждена", text)
        self.assertIn("Последняя подтверждённая (14.08.2026)", text)
        self.assertNotIn("Сегодня: вклад 92,11", text)

    def test_telegram_is_concise_and_represents_all_contract_sections(self):
        text = render_telegram_text(self.payload)
        for required in ("ПРОДАЖИ", "ЭКОНОМИКА", "РЕКЛАМА", "ОПЕРАЦИИ", "ЭКСПЕРИМЕНТЫ", "ИНФОРМАЦИЯ", "НАЛОГ", "ВНИМАНИЕ"):
            self.assertIn(required, text)
        self.assertIn("CPC 2026-08-17: STUCK", text)
        self.assertIn("ACTION_REQUIRED: Seller Main", text)
        self.assertIn("Tax ACTIVE", text)
        self.assertIn("start UNKNOWN · атрибуция недоступна", text)
        self.assertNotIn("существенных подтверждённых аномалий нет", text.lower())
        self.assertLess(len(text), 3500)

    def test_success_zero_is_zero_but_stuck_is_not(self):
        stuck = render_telegram_text(self.payload)
        zero = render_telegram_text(build_brief(sources(cpc_state="SUCCESS_ZERO"), DAY))
        self.assertIn("нулём не считается", stuck)
        self.assertIn("SUCCESS_ZERO · spend 0 ₽", zero)

    def test_email_uses_tax_engine_and_separate_economics(self):
        html = render_email_html(self.payload)
        self.assertIn("Экономика сегодня:</strong> UNAVAILABLE", html)
        self.assertIn("Tax ACTIVE", html)
        self.assertNotIn("NOT_IMPLEMENTED", html)

    def test_pdf_generation_contains_v11_sections(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as directory:
            path = render_pdf(self.payload, Path(directory) / "brief.pdf")
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            self.assertEqual(len(reader.pages), 5)
            for required in ("Daily Commercial Brief v1.1", "Source freshness", "Experiments", "Information Intelligence", "Tax Engine", "Trend coverage"):
                self.assertIn(required, text)
            self.assertGreater(path.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
