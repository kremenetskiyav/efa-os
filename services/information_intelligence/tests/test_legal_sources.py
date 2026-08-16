import unittest

from services.information_intelligence.legal_sources import LEGAL_SOURCES


class LegalSourceRegistryTests(unittest.TestCase):
    def test_only_confirmed_source_has_canonical_official_url(self):
        confirmed = [source for source in LEGAL_SOURCES if source.canonical_url]
        self.assertEqual([source.source_id for source in confirmed], ["OZON_SELLER_AGREEMENT"])
        self.assertTrue(confirmed[0].canonical_url.startswith("https://docs.ozon.ru/"))
        self.assertEqual(confirmed[0].applicability_status, "NEEDS_ACCOUNT_APPLICABILITY_CONFIRMATION")

    def test_unconfirmed_urls_are_explicit_gaps(self):
        unresolved = [source for source in LEGAL_SOURCES if not source.canonical_url]
        self.assertEqual(len(unresolved), 3)
        self.assertTrue(all(source.retrieval_capability == "NEEDS_SOURCE_CONFIRMATION" for source in unresolved))

    def test_registry_covers_required_business_domains(self):
        domains = {domain for source in LEGAL_SOURCES for domain in source.business_domains}
        self.assertTrue({"FBS", "FBO", "COMMISSION", "LOGISTICS", "RETURNS", "PROMOTION", "ADVERTISING", "FINANCE", "DOCUMENTS", "PRICING"} <= domains)


if __name__ == "__main__":
    unittest.main()
