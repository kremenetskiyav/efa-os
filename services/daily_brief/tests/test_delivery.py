from datetime import date, datetime, timezone
import inspect
import unittest

from services.daily_brief.brief import build_brief
from services.daily_brief.delivery import InMemoryDeliveryLedger, deliver_channels
from services.daily_brief.renderers import render_email_html, render_telegram_text
from services.daily_brief.tests.test_brief import sources


class DeliveryContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = build_brief(sources(), date(2026, 8, 14), datetime(2026, 8, 15, tzinfo=timezone.utc))

    def test_channel_idempotency_and_test_scope(self):
        ledger = InMemoryDeliveryLedger(); sent = []
        args = (self.payload, ledger, lambda _: "brief.pdf",
                lambda *values: sent.append(("email", values)), lambda text: sent.append(("telegram", text)),
                render_email_html, render_telegram_text)
        first = deliver_channels(*args, recipient="runtime@example.test")
        second = deliver_channels(*args, recipient="runtime@example.test")
        self.assertEqual(first["channels"]["email"]["status"], "SUCCESS")
        self.assertEqual(second["channels"]["email"]["status"], "SKIPPED_DUPLICATE")
        self.assertEqual(second["channels"]["telegram"]["status"], "SKIPPED_DUPLICATE")
        test = deliver_channels(*args, recipient="runtime@example.test", test_mode=True)
        self.assertEqual(test["channels"]["email"]["status"], "SUCCESS")

    def test_partial_channel_failure_is_isolated(self):
        def fail(_): raise RuntimeError("transport failed")
        result = deliver_channels(self.payload, InMemoryDeliveryLedger(), lambda _: "brief.pdf", lambda *_: None,
                                  fail, render_email_html, render_telegram_text, recipient="runtime@example.test")
        self.assertEqual(result["channels"]["email"]["status"], "SUCCESS")
        self.assertEqual(result["channels"]["telegram"]["status"], "TELEGRAM_FAILED")

    def test_pdf_failure_does_not_block_telegram(self):
        def fail(_): raise RuntimeError("render failed")
        sent = []
        result = deliver_channels(self.payload, InMemoryDeliveryLedger(), fail, lambda *_: None,
                                  sent.append, render_email_html, render_telegram_text, recipient="runtime@example.test")
        self.assertEqual(result["channels"]["email"]["status"], "PDF_RENDER_FAILED")
        self.assertEqual(result["channels"]["telegram"]["status"], "SUCCESS")

    def test_no_database_ozon_or_secret_dependency(self):
        source = inspect.getsource(__import__("services.daily_brief.delivery", fromlist=["*"]))
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "API-SELLER.OZON.RU", "OZON_API_KEY", "BOT_TOKEN"):
            self.assertNotIn(forbidden, source.upper())
