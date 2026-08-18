"""Private HTTP bridge; Ozon credentials and direct API calls are prohibited."""
from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

try:
    from .cpc_lifecycle import LifecycleError, claim_pending, prepare_lifecycle, record_report_status, register_report
    from .database import connect_database
    from .normalization import (PayloadError, normalize_cpc, normalize_cpc_prepare,
                                normalize_cpc_registration, normalize_cpc_status,
                                normalize_prices, normalize_seller_demand)
    from .repository import persist_cpc, persist_prices, persist_seller_demand
except ImportError:
    from cpc_lifecycle import LifecycleError, claim_pending, prepare_lifecycle, record_report_status, register_report
    from database import connect_database
    from normalization import (PayloadError, normalize_cpc, normalize_cpc_prepare,
                               normalize_cpc_registration, normalize_cpc_status,
                               normalize_prices, normalize_seller_demand)
    from repository import persist_cpc, persist_prices, persist_seller_demand

SELLER_PATH = "/v1/commercial/seller-demand/collect"
CPC_PATH = "/v1/commercial/cpc/collect"
PRICE_PATH = "/v1/commercial/prices/collect"
CPC_PREPARE_PATH = "/v1/commercial/cpc/lifecycle/prepare"
CPC_REGISTER_PATH = "/v1/commercial/cpc/lifecycle/register"
CPC_CLAIM_PATH = "/v1/commercial/cpc/lifecycle/claim"
CPC_STATUS_PATH = "/v1/commercial/cpc/lifecycle/status"


def collect(path: str, payload: object, connection_factory=connect_database) -> dict[str, Any]:
    collection = normalize_seller_demand(payload) if path == SELLER_PATH else (normalize_cpc(payload) if path == CPC_PATH else normalize_prices(payload))
    summary = {
        "read_only_api": True,
        "collection_ref": collection["collection_ref"],
        "records": len(collection["rows"]),
        "persisted": False,
    }
    if collection["persist"]:
        result = persist_seller_demand(collection, connection_factory) if collection["kind"] == "seller_demand" else (persist_cpc(collection, connection_factory) if collection["kind"] == "cpc" else persist_prices(collection, connection_factory))
        summary.update({"persisted": True, **result})
    return summary


def lifecycle(path: str, payload: object, connection_factory=connect_database) -> dict[str, Any]:
    if path == CPC_PREPARE_PATH:
        return prepare_lifecycle(normalize_cpc_prepare(payload), connection_factory)
    if path == CPC_REGISTER_PATH:
        return register_report(normalize_cpc_registration(payload), connection_factory)
    if path == CPC_CLAIM_PATH:
        return claim_pending(connection_factory)
    if path == CPC_STATUS_PATH:
        return record_report_status(normalize_cpc_status(payload), connection_factory)
    raise PayloadError("unsupported lifecycle path")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        paths = {SELLER_PATH, CPC_PATH, PRICE_PATH, CPC_PREPARE_PATH, CPC_REGISTER_PATH,
                 CPC_CLAIM_PATH, CPC_STATUS_PATH}
        if self.path not in paths:
            return self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            result = collect(self.path, payload) if self.path in {SELLER_PATH, CPC_PATH, PRICE_PATH} else lifecycle(self.path, payload)
            self._send(HTTPStatus.OK, result)
        except (json.JSONDecodeError, PayloadError) as error:
            self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid_payload", "message": str(error)})
        except LifecycleError as error:
            self._send(HTTPStatus.CONFLICT, {"error": "lifecycle_conflict", "message": str(error)})
        except Exception:
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "persistence_failed"})

    def do_GET(self) -> None:
        self._send(HTTPStatus.OK, {"status": "ok", "service": "commercial-baseline-collector", "cpc_lifecycle": "async_v1"}) if self.path == "/health" else self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
