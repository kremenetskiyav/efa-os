"""Private HTTP adapter for the read-only recommendation function tool."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from config import ConfigurationError, load_database_config, load_recommendation_config
from database import DatabaseError
from tools import ToolInputError, get_price_profit_recommendations


TOOL_PATH = "/v1/get_price_profit_recommendations"


def normalize_transport_arguments(payload: object) -> dict[str, object]:
    """Convert n8n's placeholder value `null` to the function contract's null."""
    if not isinstance(payload, dict):
        raise ToolInputError("request body must be a JSON object")
    return {key: None if value == "null" else value for key, value in payload.items()}


def run_tool(payload: object) -> dict[str, object]:
    """Run the existing tool with its normal read-only database configuration."""
    return get_price_profit_recommendations(
        normalize_transport_arguments(payload), load_database_config(), load_recommendation_config()
    )


class RecommendationToolHandler(BaseHTTPRequestHandler):
    """Serve one local-only JSON endpoint and no administrative endpoints."""
    server_version = "EFARecommendationTool/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "tool": "get_price_profit_recommendations"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != TOOL_PATH:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length))
            self._send_json(HTTPStatus.OK, run_tool(payload))
        except (json.JSONDecodeError, ToolInputError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_arguments", "message": str(error)})
        except (ConfigurationError, DatabaseError):
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "recommendations_unavailable"})

    def log_message(self, format: str, *args: Any) -> None:
        """Avoid writing request payloads or product data to container logs."""

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    ThreadingHTTPServer(("0.0.0.0", 8080), RecommendationToolHandler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
