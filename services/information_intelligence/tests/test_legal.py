import unittest

from services.information_intelligence.legal import (
    LegalDocumentError,
    canonicalize_legal,
    detect_watch_concepts,
    diff_legal,
)


def doc(body: str):
    return canonicalize_legal(body.encode("utf-8"), content_type="text/html")


class LegalCanonicalizationTests(unittest.TestCase):
    def test_preserves_headings_clauses_tables_and_semantic_numbers(self):
        parsed = doc("""<html><body><h1>Условия</h1><h2>Тарифы FBS</h2>
        <p>1.1. Комиссия продавца составляет 42%.</p>
        <table><tr><td>Логистика</td><td>130 RUB</td></tr></table></body></html>""")
        self.assertIn("Условия", parsed.canonical_text)
        self.assertIn("42%", parsed.canonical_text)
        self.assertIn("130 RUB", parsed.canonical_text)
        clause = next(unit for unit in parsed.units if unit.clause_number == "1.1")
        self.assertEqual(clause.heading_path, ("Условия", "Тарифы FBS"))

    def test_cosmetic_html_and_tracking_links_do_not_change_hash(self):
        first = doc('<html><nav>Меню</nav><h1>Тарифы</h1><p><a href="/a?utm_source=x">Комиссия 42%</a></p></html>')
        second = doc('<html><header>Другое меню</header><h1> Тарифы </h1><p><a href="/a?utm_source=y">Комиссия   42%</a></p></html>')
        self.assertEqual(first.canonical_sha256, second.canonical_sha256)

    def test_antibot_empty_and_unsupported_are_rejected(self):
        with self.assertRaises(LegalDocumentError):
            doc("<html><body>Подтвердите, что вы не робот</body></html>")
        with self.assertRaises(LegalDocumentError):
            canonicalize_legal(b"")
        with self.assertRaises(LegalDocumentError):
            canonicalize_legal(b"%PDF-fake", content_type="application/pdf", filename="terms.pdf")


class LegalDiffTests(unittest.TestCase):
    def assert_numeric(self, old: str, new: str, expected_type: str, concept: str):
        result = diff_legal(doc(f"<h1>Правила</h1><p>1.1. {old}</p>"), doc(f"<h1>Правила</h1><p>1.1. {new}</p>"))
        self.assertEqual(result.status, "DOCUMENT_CHANGED")
        self.assertIn(expected_type, [item.numeric_type for item in result.numeric_changes])
        self.assertIn(concept, result.watch_concepts)
        self.assertEqual(result.severity, "ACTION_REQUIRED")

    def test_commission_percentage_change(self):
        self.assert_numeric("Комиссия продавца 42%", "Комиссия продавца 43%", "PERCENTAGE", "SELLER_COMMISSION")

    def test_fbs_logistics_rub_change(self):
        self.assert_numeric("FBS логистика 130 RUB", "FBS логистика 145 RUB", "RUB_AMOUNT", "FBS_LOGISTICS")

    def test_return_formula_change(self):
        self.assert_numeric("Обратная логистика возврата 100 RUB", "Обратная логистика возврата 150 RUB", "RUB_AMOUNT", "RETURN_LOGISTICS")

    def test_promotion_boost_change(self):
        self.assert_numeric("Акция promotion boost 15%", "Акция promotion boost 10%", "PERCENTAGE", "PROMOTION_ECONOMICS")

    def test_payment_deadline_change(self):
        self.assert_numeric("Срок выплаты 15 дней", "Срок выплаты 20 дней", "DEADLINE_OR_LIMIT", "PAYMENT_TIMING")

    def test_buyout_coefficient_change(self):
        self.assert_numeric("Коэффициент выкупа: 0.95", "Коэффициент выкупа: 0.92", "COEFFICIENT", "LEGAL_ENTITY_BUYOUT")

    def test_ozon_points_compensation_wording_is_watched(self):
        result = diff_legal(doc("<h1>Скидки</h1><p>1.1. Баллы компенсируются продавцу.</p>"), doc("<h1>Скидки</h1><p>1.1. Баллы не компенсируются продавцу.</p>"))
        self.assertIn("OZON_FUNDED_POINTS", result.watch_concepts)
        self.assertEqual(result.severity, "WATCH")

    def test_penalty_wording_is_economic_watch(self):
        result = diff_legal(doc("<p>1.1. Штраф не применяется.</p>"), doc("<p>1.1. Штраф применяется.</p>"))
        self.assertIn("PENALTY_AND_FINE", result.watch_concepts)
        self.assertIn("Operational risk review", result.affected_components)

    def test_whitespace_wrapper_change_is_success_zero(self):
        result = diff_legal(doc("<main><h1>Правила</h1><p>Текст договора</p></main>"), doc("<div><h1> Правила </h1><p>Текст   договора</p></div>"))
        self.assertEqual(result.status, "SUCCESS_ZERO")

    def test_unrelated_cosmetic_content_does_not_raise_economic_alert(self):
        result = diff_legal(doc("<h1>Правила</h1><p>Описание сервиса</p>"), doc("<h1>Правила</h1><p>Уточнённое описание сервиса</p>"))
        self.assertEqual(result.severity, "INFO")
        self.assertFalse(result.requires_action)

    def test_renumbered_identical_clause_is_detected_as_move(self):
        old = doc("<h1>Правила</h1><p>1.1. Логистика FBS</p>")
        new = doc("<h1>Правила</h1><p>2.1. Логистика FBS</p>")
        result = diff_legal(old, new)
        self.assertIn("MOVED_OR_RENUMBERED", [change.change_type for change in result.changes])

    def test_effective_now_numeric_economic_change_is_critical_candidate(self):
        result = diff_legal(doc("<p>1.1. Комиссия 42%</p>"), doc("<p>1.1. Комиссия 43%</p>"), effective_now=True)
        self.assertEqual(result.severity, "CRITICAL")


class WatchRoutingTests(unittest.TestCase):
    def test_known_watch_concepts(self):
        found = detect_watch_concepts("Баллы, комиссия, FBS логистика, возврат, реклама, выкуп, УПД")
        self.assertIn("OZON_FUNDED_POINTS", found)
        self.assertIn("SELLER_COMMISSION", found)
        self.assertIn("DOCUMENT_FLOW", found)


if __name__ == "__main__":
    unittest.main()
