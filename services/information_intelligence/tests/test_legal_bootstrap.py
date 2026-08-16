import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from services.information_intelligence.legal import LegalDocumentError
from services.information_intelligence.legal_bootstrap import preview_legal_snapshot
from services.information_intelligence.legal_pdf import PDFExtraction


class LegalBootstrapTests(unittest.TestCase):
    def test_gzip_official_html_preview_is_not_persisted(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "contract.html.gz"
            path.write_bytes(gzip.compress("<h1>Договор</h1><p>1.1. Комиссия 42%</p>".encode("utf-8")))
            result = preview_legal_snapshot("OZON_SELLER_AGREEMENT", path)
            self.assertEqual(result["status"], "BASELINE_PREVIEW_READY")
            self.assertFalse(result["persisted"])
            self.assertIn("SELLER_COMMISSION", result["watch_concepts"])

    def test_antibot_file_is_rejected(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "contract.html"
            path.write_text("<html>captcha</html>", encoding="utf-8")
            with self.assertRaises(LegalDocumentError):
                preview_legal_snapshot("OZON_SELLER_AGREEMENT", path)

    @patch("services.information_intelligence.legal_pdf.extract_pdf_text")
    def test_pdf_text_layer_preview_uses_pdf_raw_hash_and_semantic_text(self, extract):
        extract.return_value = PDFExtraction(2, "Договор\n1.1. Комиссия 42%", len("Договор\n1.1. Комиссия 42%".encode()), {"/Title": "Договор"}, 2)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "contract.pdf"
            path.write_bytes(b"%PDF-1.7\nminimal")
            result = preview_legal_snapshot("OZON_SELLER_AGREEMENT", path)
            self.assertEqual(result["status"], "BASELINE_PREVIEW_READY")
            self.assertEqual(result["pdf_extraction"]["page_count"], 2)
            self.assertTrue(result["pdf_extraction"]["text_extractable"])
            self.assertIn("SELLER_COMMISSION", result["watch_concepts"])


if __name__ == "__main__":
    unittest.main()
