from email.message import Message
from io import BytesIO
import unittest
from urllib.error import HTTPError

from services.information_intelligence.fetch import fetch_once
from services.information_intelligence.sources import SOURCES


class Response(BytesIO):
    status = 200

    def __init__(self, body: bytes):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FetchTests(unittest.TestCase):
    def test_success_records_metadata_and_hash(self):
        calls = []
        result = fetch_once(SOURCES[0], opener=lambda request, timeout: calls.append(request) or Response(b"{}"))
        self.assertEqual((result.status, result.http_status, result.content_type, result.raw_bytes), ("SUCCESS", 200, "application/json", 2))
        self.assertEqual(len(result.raw_sha256), 64)
        self.assertEqual(len(calls), 1)

    def test_redirect_failure_is_source_unavailable_without_retry(self):
        calls = []
        def redirect(request, timeout):
            calls.append(request)
            raise HTTPError(request.full_url, 307, "redirect loop", Message(), None)
        result = fetch_once(SOURCES[0], opener=redirect)
        self.assertEqual(result.status, "SOURCE_UNAVAILABLE")
        self.assertEqual(result.redirect_state, "REDIRECT_BLOCKED")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
