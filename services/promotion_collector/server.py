"""Private, in-memory bridge endpoint for verified Ozon promotion responses."""
from __future__ import annotations
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
try:
    from .database import map_product_ids
except ImportError:  # Docker executes server.py as a script.
    from database import map_product_ids

PATH = "/v1/promotions/collect"

class PayloadError(ValueError): pass

def collect(payload: object, mapper=map_product_ids) -> dict[str, object]:
    if not isinstance(payload, dict): raise PayloadError("payload must be an object")
    required = {"collection_ref", "collected_at", "actions", "action_details"}
    if set(payload) != required: raise PayloadError("payload must contain exactly collection_ref, collected_at, actions, action_details")
    if not isinstance(payload["collection_ref"], str) or not payload["collection_ref"].strip(): raise PayloadError("collection_ref must be a non-empty string")
    if not isinstance(payload["collected_at"], str) or not isinstance(payload["actions"], list) or not isinstance(payload["action_details"], list): raise PayloadError("invalid collection field type")
    action_ids = {item.get("id") for item in payload["actions"] if isinstance(item, dict) and item.get("id") is not None}
    participating = candidate = 0; product_ids: set[int] = set(); errors: list[str] = []
    for detail in payload["action_details"]:
        if not isinstance(detail, dict) or set(detail) != {"action_id", "products", "candidates"}: raise PayloadError("invalid action_details item")
        action_id = detail["action_id"]
        if action_id not in action_ids: errors.append(f"unknown_action_id:{action_id}")
        for key, counter in (("products", "participating"), ("candidates", "candidate")):
            records = detail[key]
            if not isinstance(records, list): raise PayloadError(f"{key} must be a list")
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get("id"), int): raise PayloadError(f"{key} record requires integer id")
                product_ids.add(record["id"])
            if counter == "participating": participating += len(records)
            else: candidate += len(records)
    mapped=mapper(product_ids); unmapped=sorted(product_ids-set(mapped))
    if unmapped: errors.append("unmapped_product_ids")
    return {"read_only": True, "collection_ref": payload["collection_ref"], "actions_count": len(payload["actions"]), "participating_records": participating, "candidate_records": candidate, "unique_product_ids": len(product_ids), "mapped_offer_ids": len(set(mapped.values())), "unmapped_product_ids": unmapped, "mapping_status": "valid" if not unmapped else "review", "errors": errors}

class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != PATH: return self._send(HTTPStatus.NOT_FOUND,{"error":"not_found"})
        try: self._send(HTTPStatus.OK, collect(json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))) )
        except (json.JSONDecodeError, PayloadError) as error: self._send(HTTPStatus.BAD_REQUEST,{"error":"invalid_payload","message":str(error)})
    def do_GET(self) -> None:
        self._send(HTTPStatus.OK,{"status":"ok","service":"promotions-collector"}) if self.path == "/health" else self._send(HTTPStatus.NOT_FOUND,{"error":"not_found"})
    def log_message(self, format: str, *args: Any) -> None: pass
    def _send(self,status: HTTPStatus,payload:dict[str,object])->None:
        body=json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)

if __name__ == "__main__": ThreadingHTTPServer(("0.0.0.0",8080),Handler).serve_forever()
