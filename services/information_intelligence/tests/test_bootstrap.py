from pathlib import Path
import gzip
import tempfile
import unittest

from services.information_intelligence.bootstrap import preview_local_snapshot


FIXTURE = Path(__file__).parent / "fixtures" / "base.json"


class BootstrapTests(unittest.TestCase):
    def test_manual_snapshot_is_validated_but_not_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "seller-openapi.json"
            source.write_bytes(FIXTURE.read_bytes())
            result = preview_local_snapshot("SELLER_API_OPENAPI", source)
        self.assertEqual(result["status"], "BASELINE_CREATED")
        self.assertFalse(result["persisted"])
        self.assertEqual(result["paths_count"], 1)

    def test_compressed_outside_git_snapshot_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "seller-openapi.json.gz"
            source.write_bytes(gzip.compress(FIXTURE.read_bytes()))
            result = preview_local_snapshot("SELLER_API_OPENAPI", source)
        self.assertEqual(result["status"], "BASELINE_CREATED")


if __name__ == "__main__":
    unittest.main()
