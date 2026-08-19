from datetime import date, datetime, timezone
import inspect
import json
from pathlib import Path
import unittest

from services.daily_brief.brief import build_brief
from services.daily_brief.delivery import InMemoryDeliveryLedger, deliver_channels
from services.daily_brief.renderers import render_email_html, render_telegram_text
from services.daily_brief.tests.test_brief import DAY, sources


class DeliveryContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = build_brief(sources(), DAY, datetime(2026, 8, 18, tzinfo=timezone.utc))

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

    def test_production_workflow_locks_one_explicit_business_date(self):
        repository_root = Path(__file__).resolve().parents[3]
        workflow_path = repository_root / "n8n" / "workflows" / "Ozon_Daily_Commercial_Brief_Delivery_v1.json"
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        nodes = {node["name"]: node for node in workflow["nodes"]}
        locked_date = "$('Lock Delivery Business Date').first().json.business_date"

        date_code = nodes["Lock Delivery Business Date"]["parameters"]["jsCode"]
        self.assertIn("MANUAL_BUSINESS_DATE_REQUIRED", date_code)
        self.assertIn("SCHEDULED_TIMESTAMP_REQUIRED", date_code)
        self.assertIn("SCHEDULED_PREVIOUS_MSK_DAY", date_code)
        self.assertNotIn("input.timestamp ?", date_code)

        expected_paths = {
            "Get Daily Brief": "/v1/daily-brief?date=",
            "Get Production Telegram Text": "/v1/daily-brief/telegram?date=",
            "Get Production Email HTML": "/v1/daily-brief/email?date=",
            "Get Production PDF": "/v1/daily-brief/pdf?date=",
        }
        for node_name, path in expected_paths.items():
            url = nodes[node_name]["parameters"]["url"]
            self.assertIn(path, url)
            self.assertIn(locked_date, url)

        validation_code = nodes["Validate Production Brief"]["parameters"]["jsCode"]
        self.assertIn("DELIVERY_DATE_CONTEXT_MISMATCH", validation_code)
        self.assertEqual(
            workflow["connections"]["Daily 08:15 Moscow"]["main"][0][0]["node"],
            "Lock Delivery Business Date",
        )
