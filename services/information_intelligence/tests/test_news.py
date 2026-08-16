import unittest

from services.information_intelligence.news import (
    NewsEvidence,
    NewsEvidenceError,
    canonicalize_news,
    diff_news,
    listing_fingerprint,
)


def evidence(body="<h1>Тарифы FBS</h1><p>С 20 августа 2026 года логистика 100 RUB.</p>", **updates):
    values = dict(
        canonical_url="https://seller.ozon.ru/media/news/fbs-tariffs/?utm_source=test",
        title="Тарифы FBS",
        published_at="2026-08-10",
        body=body,
        content_type="text/html",
    )
    values.update(updates)
    return NewsEvidence(**values)


class SellerNewsContractTests(unittest.TestCase):
    def test_identity_falls_back_to_canonical_permalink(self):
        item = canonicalize_news(evidence())
        self.assertEqual(item.identity, "https://seller.ozon.ru/media/news/fbs-tariffs/")
        self.assertEqual(item.effective_date, "20 августа 2026")

    def test_new_same_and_updated_article(self):
        first = canonicalize_news(evidence())
        self.assertEqual(diff_news(None, first).status, "NEW")
        self.assertEqual(diff_news(first, canonicalize_news(evidence())).status, "NO_CHANGE")
        changed = canonicalize_news(evidence(body="<h1>Тарифы FBS</h1><p>С 20 августа 2026 года логистика 120 RUB.</p>"))
        result = diff_news(first, changed)
        self.assertEqual((result.status, result.classification, result.severity), ("UPDATED", "REVIEW", "ACTION_REQUIRED"))

    def test_effective_date_change_is_updated_review(self):
        first = canonicalize_news(evidence())
        changed = canonicalize_news(evidence(body="<h1>Тарифы FBS</h1><p>С 21 августа 2026 года логистика 100 RUB.</p>"))
        result = diff_news(first, changed)
        self.assertEqual((result.status, result.classification), ("UPDATED", "REVIEW"))

    def test_listing_reorder_does_not_change_fingerprint(self):
        first = canonicalize_news(evidence())
        second = canonicalize_news(evidence(canonical_url="https://seller.ozon.ru/media/news/other/", title="Документы"))
        self.assertEqual(listing_fingerprint((first, second)), listing_fingerprint((second, first)))

    def test_tracking_url_change_does_not_change_article(self):
        first = canonicalize_news(evidence())
        second = canonicalize_news(evidence(canonical_url="https://seller.ozon.ru/media/news/fbs-tariffs/?utm_campaign=x&gclid=secret"))
        self.assertEqual(first.canonical_sha256, second.canonical_sha256)

    def test_non_ozon_evidence_url_is_rejected(self):
        with self.assertRaises(NewsEvidenceError):
            canonicalize_news(evidence(canonical_url="https://example.com/news"))


if __name__ == "__main__":
    unittest.main()
