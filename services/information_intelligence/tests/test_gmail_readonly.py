from __future__ import annotations

import base64
import unittest

from services.information_intelligence.gmail_readonly import (
    ALLOWED_GMAIL_OPERATIONS, GMAIL_READONLY_SCOPE, is_confirmed_ozon,
    decode_rfc2047_header, normalize_message, require_exact_scope,
)
from services.information_intelligence.gmail_routing import EVENT_CANDIDATE, ROUTINE_OPERATIONAL, route_message
from services.information_intelligence.gmail_persistence import _collection_ref


def b64(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


class GmailReadOnlyTests(unittest.TestCase):
    def test_scope_must_be_exactly_readonly(self):
        require_exact_scope([GMAIL_READONLY_SCOPE])
        with self.assertRaises(ValueError):
            require_exact_scope([GMAIL_READONLY_SCOPE, "https://www.googleapis.com/auth/gmail.modify"])

    def test_only_message_reads_are_allowed(self):
        self.assertEqual(ALLOWED_GMAIL_OPERATIONS, {"messages.list", "messages.get"})
        self.assertFalse(any(word in " ".join(ALLOWED_GMAIL_OPERATIONS) for word in ("send", "modify", "trash", "delete", "labels", "drafts")))

    def test_normalization_and_identity_are_deterministic(self):
        message = {"id": "g-1", "threadId": "t-1", "internalDate": "1780000000000", "payload": {"headers": [
            {"name": "From", "value": "Ozon <notice@mail.ozon.ru>"}, {"name": "Subject", "value": "  Новости Ozon  "},
            {"name": "Message-ID", "value": "<rfc-1>"},
        ], "mimeType": "text/plain", "body": {"data": b64("Текст https://seller.ozon.ru/news")}, "parts": []}}
        first = normalize_message(message)
        second = normalize_message(message)
        self.assertTrue(first.confirmed_ozon)
        self.assertEqual(first.normalized_text, "Текст https://seller.ozon.ru/news")
        self.assertEqual(first.content_hash, second.content_hash)
        self.assertEqual(first.rfc_message_id, "<rfc-1>")
        replay = dict(message)
        replay["id"] = "g-2"
        self.assertEqual(first.content_hash, normalize_message(replay).content_hash)

    def test_sender_validation_does_not_assume_subject_alone(self):
        self.assertFalse(is_confirmed_ozon("example.com", "Ozon news", "", []))
        self.assertFalse(is_confirmed_ozon("mail.ozon.ru", "Receipt", "", []))

    def test_decodes_utf8_base64_and_quoted_printable_headers(self):
        self.assertEqual(decode_rfc2047_header("=?UTF-8?B?0J7RgdC+0L0=?=")[0], "Осон")
        self.assertEqual(decode_rfc2047_header("=?UTF-8?Q?Ozon_=D0=BD=D0=BE=D0=B2=D0=BE=D1=81=D1=82=D0=B8?=")[0], "Ozon новости")

    def test_decodes_mixed_and_preserves_unicode(self):
        self.assertEqual(decode_rfc2047_header("Ozon =?UTF-8?B?0L3QvtCy0L7RgdGC0Lg=?=")[0], "Ozon новости")
        self.assertEqual(decode_rfc2047_header("Уже Unicode")[0], "Уже Unicode")

    def test_malformed_header_falls_back_without_crashing(self):
        text, quality = decode_rfc2047_header("=?unknown-charset?B?dGVzdA==?=")
        self.assertEqual(text, "test")
        self.assertEqual(quality, "REVIEW_REQUIRED")

    def test_routing_filters_routine_order_but_keeps_regulation_candidate(self):
        order = normalize_message({"id": "order", "payload": {"headers": [{"name": "From", "value": "marketplace@seller.ozon.ru"}, {"name": "Subject", "value": "Есть новый заказ"}], "body": {"data": b64("FBS заказ")}}})
        rule = normalize_message({"id": "rule", "payload": {"headers": [{"name": "From", "value": "marketplace@seller.ozon.ru"}, {"name": "Subject", "value": "Изменение комиссии"}], "body": {"data": b64("Ozon меняет комиссию")}}})
        self.assertEqual(route_message(order)[0], ROUTINE_OPERATIONAL)
        self.assertEqual(route_message(rule)[0], EVENT_CANDIDATE)
        self.assertEqual(_collection_ref([order, rule]), _collection_ref([rule, order]))

    def test_real_routine_order_subject_wins_over_fbs_presentation_html(self):
        message = normalize_message({"id": "real-order", "payload": {"headers": [
            {"name": "From", "value": "marketplace@seller.ozon.ru"},
            {"name": "Subject", "value": "Есть новый заказ"},
        ], "mimeType": "text/html", "body": {"data": b64("<style>.fbs{content:'изменение'}</style><p>FBS: новый заказ</p>")}}})
        self.assertEqual(message.normalized_text, "FBS: новый заказ")
        self.assertEqual(route_message(message)[0], ROUTINE_OPERATIONAL)


if __name__ == "__main__":
    unittest.main()
