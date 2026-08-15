"""Private read-only HTTP bridge for the deterministic Daily Commercial Brief."""
from __future__ import annotations

import json
import tempfile
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from .brief import build_brief, last_completed_business_date
from .config import load_database_config
from .database import fetch_brief_sources
from .delivery import brief_id
from .renderers import render_email_html, render_pdf, render_telegram_text


BriefLoader = Callable[[date], dict[str, Any]]


def load_brief(business_date: date) -> dict[str, Any]:
    """Load the existing deterministic brief through a read-only DB session."""
    return build_brief(
        fetch_brief_sources(load_database_config(), business_date),
        business_date,
    )


def _business_date(target: str, *, today_resolver: Callable[[], date]) -> date:
    values = parse_qs(urlsplit(target).query)
    raw = values.get("date", [None])[0]
    if raw is None:
        return today_resolver()
    try:
        return date.fromisoformat(raw)
    except ValueError as error:
        raise ValueError("date must use YYYY-MM-DD") from error


def _metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "business_date": payload["business_date"],
        "brief_id": brief_id(payload),
        "data_quality": payload["data_quality"],
    }


class DailyBriefApplication:
    def __init__(
        self,
        loader: BriefLoader = load_brief,
        *,
        default_date: Callable[[], date] = last_completed_business_date,
        telegram_renderer: Callable[[dict[str, Any]], str] = render_telegram_text,
        email_renderer: Callable[[dict[str, Any]], str] = render_email_html,
        pdf_renderer: Callable[[dict[str, Any], str | Path], Path] = render_pdf,
    ) -> None:
        self.loader = loader
        self.default_date = default_date
        self.telegram_renderer = telegram_renderer
        self.email_renderer = email_renderer
        self.pdf_renderer = pdf_renderer

    def handle(self, method: str, target: str) -> tuple[HTTPStatus, str, bytes]:
        parsed = urlsplit(target)
        if method != "GET":
            return self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method_not_allowed"})
        if parsed.path == "/health":
            return self._json(HTTPStatus.OK, {"status": "ok", "service": "efa-daily-brief", "read_only": True})
        routes = {
            "/v1/daily-brief": "json",
            "/v1/daily-brief/telegram": "telegram",
            "/v1/daily-brief/email": "email",
            "/v1/daily-brief/pdf": "pdf",
        }
        route = routes.get(parsed.path)
        if route is None:
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        try:
            business_date = _business_date(target, today_resolver=self.default_date)
            payload = self.loader(business_date)
        except ValueError as error:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "message": str(error)})
        except Exception:
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "brief_unavailable"})
        try:
            if route == "json":
                return self._json(HTTPStatus.OK, payload)
            if route == "telegram":
                return self._json(HTTPStatus.OK, {**_metadata(payload), "text": self.telegram_renderer(payload)})
            if route == "email":
                return self._json(HTTPStatus.OK, {
                    **_metadata(payload),
                    "subject": f"OZON Daily Commercial Brief — {payload['business_date']}",
                    "html": self.email_renderer(payload),
                })
            with tempfile.TemporaryDirectory(prefix="efa-daily-brief-") as directory:
                path = self.pdf_renderer(payload, Path(directory) / "brief.pdf")
                body = Path(path).read_bytes()
            return HTTPStatus.OK, "application/pdf", body
        except Exception:
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "render_failed"})

    @staticmethod
    def _json(status: HTTPStatus, payload: dict[str, Any]) -> tuple[HTTPStatus, str, bytes]:
        return status, "application/json; charset=utf-8", json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
        ).encode("utf-8")


APPLICATION = DailyBriefApplication()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._send(*APPLICATION.handle("GET", self.path))

    def do_POST(self) -> None:
        self._send(*APPLICATION.handle("POST", self.path))

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()


if __name__ == "__main__":
    main()
