import unittest

from services.information_intelligence.manual_evidence import (
    MANUAL_AUTHORITY,
    MANUAL_SOURCE_ID,
    SELLER_MAIN_NOTICES,
    daily_brief_preview,
)


class ManualEvidenceTests(unittest.TestCase):
    def test_two_known_notices_have_stable_identity_and_manual_quality(self):
        self.assertEqual(MANUAL_SOURCE_ID, "OZON_SELLER_MAIN_MANUAL")
        self.assertEqual(MANUAL_AUTHORITY, "SELLER_AUTHENTICATED_UI_MANUAL_EVIDENCE")
        self.assertEqual(len(SELLER_MAIN_NOTICES), 2)
        self.assertEqual(len({notice.content_sha256 for notice in SELLER_MAIN_NOTICES}), 2)
        self.assertTrue(all(notice.data_quality == "MANUAL_SELLER_UI_SUMMARY" for notice in SELLER_MAIN_NOTICES))

    def test_fbs_notice_routes_operational_risk_without_new_domain(self):
        notice = SELLER_MAIN_NOTICES[0]
        self.assertEqual(notice.effective_date, "2026-08-14")
        self.assertEqual(notice.severity, "ACTION_REQUIRED")
        self.assertEqual(notice.domains, ("FBS", "LOGISTICS", "FINANCE"))
        self.assertIn("FBS operations", notice.affected_components)

    def test_buyout_notice_is_review_only_for_tax(self):
        notice = SELLER_MAIN_NOTICES[1]
        self.assertIsNone(notice.effective_date)
        self.assertEqual(notice.severity, "WATCH")
        self.assertIn("TAX_REVIEW_ONLY", notice.domains)
        self.assertIn("TAX_REVIEW_ONLY", notice.affected_components)

    def test_preview_is_deterministic_and_contains_no_raw_json(self):
        preview = daily_brief_preview()
        self.assertEqual(preview, daily_brief_preview())
        self.assertIn("OZON CHANGES", preview)
        self.assertIn("FBS: как избежать ошибок при отгрузке", preview)
        self.assertIn("Открыли продажи юрлицам через выкупы", preview)
        self.assertNotIn("{", preview)


if __name__ == "__main__":
    unittest.main()
