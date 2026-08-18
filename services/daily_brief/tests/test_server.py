from __future__ import annotations

from datetime import date, datetime, timezone
import inspect
import json
from pathlib import Path
import tempfile
import unittest

from services.daily_brief.brief import build_brief
from services.daily_brief.server import DailyBriefApplication
from services.daily_brief.tests.test_brief import DAY, sources


class DailyBriefServerTests(unittest.TestCase):
    def setUp(self):
        self.requested_dates: list[date] = []
        self.payload = build_brief(
            sources(cpc_state="STUCK"), DAY, datetime(2026, 8, 18, tzinfo=timezone.utc)
        )

        def loader(value: date):
            self.requested_dates.append(value)
            return self.payload

        self.pdf_paths: list[Path] = []

        def pdf_renderer(payload, path):
            target = Path(path)
            self.pdf_paths.append(target)
            target.write_bytes(b"%PDF-1.4\nmock")
            return target

        self.app = DailyBriefApplication(
            loader,
            default_date=lambda: DAY,
            pdf_renderer=pdf_renderer,
        )

    def request(self, path):
        status, content_type, body = self.app.handle("GET", path)
        return status, content_type, body, json.loads(body) if "json" in content_type else None

    def test_health_requires_no_database(self):
        status, _, _, payload = self.request("/health")
        self.assertEqual((status, payload["read_only"], self.requested_dates), (200, True, []))

    def test_explicit_and_default_business_dates(self):
        self.request("/v1/daily-brief?date=2026-08-17")
        self.request("/v1/daily-brief")
        self.assertEqual(self.requested_dates, [DAY, DAY])

    def test_json_endpoint_returns_existing_payload_unchanged(self):
        _, _, _, payload = self.request("/v1/daily-brief?date=2026-08-17")
        self.assertEqual(payload, self.payload)

    def test_telegram_contains_full_contract_and_all_offers(self):
        payload = build_brief(sources(cpc_state="STUCK"), DAY, datetime(2026, 8, 18, tzinfo=timezone.utc))
        template = payload["offers"][0]
        payload["offers"] = []
        payload["compact_report_payload"]["offers"] = []
        for offer in ("УФ 001Б", "УФ 002Б", "УФ 003Б", "УФ 004Б", "УФ 005Б"):
            item = {**template, "offer_id": offer}
            item["attention"] = {"level": "NO_ACTION", "reasons": []}
            payload["offers"].append(item)
            compact = {**payload["compact_report_payload"].get("offers", [{}])[0]} if payload["compact_report_payload"].get("offers") else {
                "offer_id": offer, "ordered_units": 2, "delivered_units": None, "returned_units": None,
                "ordered_revenue": "250", "confirmed_through_date": "2026-08-14",
                "contribution_profit": None, "contribution_margin_pct": None, "attention": item["attention"],
            }
            compact["offer_id"] = offer
            payload["compact_report_payload"]["offers"].append(compact)
        app = DailyBriefApplication(lambda _: payload)
        _, _, _, response = self._json(app.handle("GET", "/v1/daily-brief/telegram?date=2026-08-17"))
        text = response["text"]
        for required in ("ПРОДАЖИ", "ЭКОНОМИКА", "РЕКЛАМА", "ВНИМАНИЕ", "УФ 001Б", "УФ 002Б", "УФ 003Б", "УФ 004Б", "УФ 005Б"):
            self.assertIn(required, text)
        self.assertNotIn("выкуп", text.lower())
        self.assertNotIn("null", text)

    def test_email_contract(self):
        _, _, _, payload = self.request("/v1/daily-brief/email?date=2026-08-17")
        self.assertEqual(payload["subject"], "OZON Daily Commercial Brief — 2026-08-17")
        self.assertIn("Экономика сегодня", payload["html"])
        self.assertIn("Tax ACTIVE", payload["html"])

    def test_pdf_binary_content_type_and_temp_cleanup(self):
        status, content_type, body = self.app.handle("GET", "/v1/daily-brief/pdf?date=2026-08-17")
        self.assertEqual((status, content_type, body[:4]), (200, "application/pdf", b"%PDF"))
        self.assertTrue(self.pdf_paths)
        self.assertFalse(self.pdf_paths[0].exists())

    def test_renderer_error_is_sanitized(self):
        app = DailyBriefApplication(lambda _: self.payload, telegram_renderer=lambda _: 1 / 0)
        status, _, body = app.handle("GET", "/v1/daily-brief/telegram?date=2026-08-17")
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body), {"error": "render_failed"})

    def test_repeated_render_is_deterministic(self):
        first = self.app.handle("GET", "/v1/daily-brief/telegram?date=2026-08-17")
        second = self.app.handle("GET", "/v1/daily-brief/telegram?date=2026-08-17")
        self.assertEqual(first, second)

    def test_invalid_date_and_method_are_rejected(self):
        self.assertEqual(self.app.handle("GET", "/v1/daily-brief?date=nope")[0], 400)
        self.assertEqual(self.app.handle("POST", "/v1/daily-brief")[0], 405)

    def test_no_write_or_external_api_contract(self):
        modules = [
            inspect.getsource(__import__("services.daily_brief.server", fromlist=["*"])),
            inspect.getsource(__import__("services.daily_brief.database", fromlist=["*"])),
        ]
        source = "\n".join(modules).upper()
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "API-SELLER.OZON.RU", "OZON_API_KEY", "GMAIL", "BOT_TOKEN"):
            self.assertNotIn(forbidden, source)
        self.assertIn("DEFAULT_TRANSACTION_READ_ONLY=ON", source)

    @staticmethod
    def _json(result):
        status, content_type, body = result
        return status, content_type, body, json.loads(body)


if __name__ == "__main__":
    unittest.main()
