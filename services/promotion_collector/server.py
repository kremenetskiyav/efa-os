"""Private, in-memory bridge endpoint for verified Ozon promotion responses."""
from __future__ import annotations
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
try:
    from .database import connect_database, map_product_ids
    from .repository import persist_collection
except ImportError:  # Docker executes server.py as a script.
    from database import connect_database, map_product_ids
    from repository import persist_collection

PATH = "/v1/promotions/collect"

class PayloadError(ValueError): pass

def _prepare(payload: object, mapper=map_product_ids) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(payload, dict): raise PayloadError("payload must be an object")
    required = {"collection_ref", "collected_at", "actions", "action_details"}
    allowed = required | {"persist"}
    if not required.issubset(payload) or not set(payload).issubset(allowed): raise PayloadError("payload must contain collection_ref, collected_at, actions, action_details and optional persist")
    if "persist" in payload and not isinstance(payload["persist"], bool): raise PayloadError("persist must be a boolean")
    if not isinstance(payload["collection_ref"], str) or not payload["collection_ref"].strip(): raise PayloadError("collection_ref must be a non-empty string")
    if not isinstance(payload["collected_at"], str) or not isinstance(payload["actions"], list) or not isinstance(payload["action_details"], list): raise PayloadError("invalid collection field type")
    actions = {item.get("id"): item for item in payload["actions"] if isinstance(item, dict) and isinstance(item.get("id"), int)}
    action_ids = set(actions)
    participating = candidate = 0; product_ids: set[int] = set(); errors: list[str] = []
    logical_keys: set[tuple[int, str, int]] = set(); normalized: list[dict[str, object]] = []
    for detail in payload["action_details"]:
        if not isinstance(detail, dict) or set(detail) != {"action_id", "products", "candidates"}: raise PayloadError("invalid action_details item")
        action_id = detail["action_id"]
        if action_id not in action_ids: raise PayloadError(f"unknown_action_id:{action_id}")
        action = actions[action_id]
        for key, counter, source_type in (("products", "participating", "PARTICIPATING"), ("candidates", "candidate", "CANDIDATE")):
            records = detail[key]
            if not isinstance(records, list): raise PayloadError(f"{key} must be a list")
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get("id"), int): raise PayloadError(f"{key} record requires integer id")
                product_id = record["id"]; product_ids.add(product_id)
                logical_key = (action_id, source_type, product_id)
                if logical_key in logical_keys: raise PayloadError(f"duplicate_detail:{action_id}:{source_type}:{product_id}")
                logical_keys.add(logical_key)
                normalized.append({"action_id":action_id,"action_title":action.get("title"),"action_type":action.get("action_type"),"action_start_at":action.get("date_start"),"action_end_at":action.get("date_end"),"source_list_type":source_type,"product_id":product_id,"add_mode":record.get("add_mode"),"price":record.get("price"),"action_price":record.get("action_price"),"max_action_price":record.get("max_action_price"),"current_boost":record.get("current_boost"),"min_boost":record.get("min_boost"),"max_boost":record.get("max_boost")})
            if counter == "participating": participating += len(records)
            else: candidate += len(records)
    mapped=mapper(product_ids); unmapped=sorted(product_ids-set(mapped))
    if unmapped: errors.append("unmapped_product_ids")
    for row in normalized:
        row["offer_id"] = mapped.get(row["product_id"])
        row["data_quality_status"] = "valid" if row["offer_id"] is not None else "review"
    mapping_status = "valid" if not unmapped else ("partial" if mapped else "invalid")
    summary = {"read_only": not payload.get("persist",False), "collection_ref": payload["collection_ref"], "actions_count": len(payload["actions"]), "participating_records": participating, "candidate_records": candidate, "unique_product_ids": len(product_ids), "mapped_offer_ids": len(set(mapped.values())), "unmapped_product_ids": unmapped, "mapping_status": mapping_status, "errors": errors}
    persistence = {**summary,"collected_at":payload["collected_at"],"unmapped_product_ids_count":len(unmapped),"error_summary":";".join(errors) or None,"snapshots":normalized}
    return summary, persistence

def collect(payload: object, mapper=map_product_ids, persister=persist_collection, connection_factory=connect_database) -> dict[str, object]:
    summary, persistence = _prepare(payload, mapper)
    if isinstance(payload,dict) and payload.get("persist") is True:
        result=persister(persistence,connection_factory)
        summary.update({"persisted":True,**result})
    else: summary["persisted"]=False
    return summary

class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != PATH: return self._send(HTTPStatus.NOT_FOUND,{"error":"not_found"})
        try: self._send(HTTPStatus.OK, collect(json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))) )
        except (json.JSONDecodeError, PayloadError) as error: self._send(HTTPStatus.BAD_REQUEST,{"error":"invalid_payload","message":str(error)})
        except Exception: self._send(HTTPStatus.INTERNAL_SERVER_ERROR,{"error":"persistence_failed"})
    def do_GET(self) -> None:
        self._send(HTTPStatus.OK,{"status":"ok","service":"promotions-collector"}) if self.path == "/health" else self._send(HTTPStatus.NOT_FOUND,{"error":"not_found"})
    def log_message(self, format: str, *args: Any) -> None: pass
    def _send(self,status: HTTPStatus,payload:dict[str,object])->None:
        body=json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)

if __name__ == "__main__": ThreadingHTTPServer(("0.0.0.0",8080),Handler).serve_forever()
