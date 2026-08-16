import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from services.information_intelligence.legal import LegalDocumentError
from services.information_intelligence.legal_bootstrap import preview_legal_snapshot


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


if __name__ == "__main__":
    unittest.main()
