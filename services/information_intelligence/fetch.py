"""One-shot public HTTP retrieval with no retries or authentication."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from typing import Protocol


class PublicSource(Protocol):
    source_id: str
    canonical_url: str


@dataclass(frozen=True)
class FetchResult:
    source_id: str
    canonical_url: str
    retrieved_at: str
    status: str
    http_status: int | None
    content_type: str | None
    raw_bytes: int
    raw_sha256: str | None
    redirect_state: str | None
    body: bytes | None = None
    error: str | None = None

    def summary(self) -> dict:
        result = asdict(self)
        result.pop("body")
        return result


def fetch_once(
    source: PublicSource,
    *,
    timeout: float = 20,
    opener: Callable = urlopen,
) -> FetchResult:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    request = Request(
        source.canonical_url,
        headers={"Accept": getattr(source, "accept", "application/json"), "User-Agent": "efa-os-information-intelligence/0.1"},
        method="GET",
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read()
            http_status = int(getattr(response, "status", 200))
            content_type = response.headers.get_content_type()
            return FetchResult(
                source_id=source.source_id,
                canonical_url=source.canonical_url,
                retrieved_at=retrieved_at,
                status="SUCCESS" if http_status == 200 else "HTTP_FAILED",
                http_status=http_status,
                content_type=content_type,
                raw_bytes=len(body),
                raw_sha256=hashlib.sha256(body).hexdigest(),
                redirect_state="NONE",
                body=body if http_status == 200 else None,
                error=None if http_status == 200 else f"HTTP {http_status}",
            )
    except HTTPError as error:
        status = "SOURCE_UNAVAILABLE" if 300 <= error.code < 400 else "HTTP_FAILED"
        return FetchResult(
            source.source_id, source.canonical_url, retrieved_at, status,
            error.code, error.headers.get_content_type() if error.headers else None,
            0, None, "REDIRECT_BLOCKED" if 300 <= error.code < 400 else "NONE",
            error=f"HTTP {error.code}",
        )
    except (URLError, TimeoutError, OSError) as error:
        return FetchResult(source.source_id, source.canonical_url, retrieved_at, "SOURCE_UNAVAILABLE", None, None, 0, None, None, error=type(error).__name__)
