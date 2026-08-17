"""Idempotent persistence limited to existing Information Intelligence tables."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable

from .gmail_readonly import NormalizedGmailMessage
from .gmail_routing import EVENT_CANDIDATE, ROUTINE_OPERATIONAL, route_message


SOURCE_ID = "OZON_GMAIL_NOTIFICATIONS"


def _runtime_env_path() -> Path:
    return Path.home() / ".efa-os" / "secrets" / "runtime.env"


def _db_config() -> dict[str, str]:
    values = dict(os.environ)
    if not all(values.get(key) for key in ("EFA_DB_HOST", "EFA_DB_PORT", "EFA_DB_NAME", "EFA_DB_USER", "EFA_DB_PASSWORD")):
        for line in _runtime_env_path().read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values.setdefault(key.strip(), value.strip())
    return {key: values[key] for key in ("EFA_DB_HOST", "EFA_DB_PORT", "EFA_DB_NAME", "EFA_DB_USER", "EFA_DB_PASSWORD")}


def connection_factory() -> Any:
    import psycopg2
    config = _db_config()
    return psycopg2.connect(host=config["EFA_DB_HOST"], port=config["EFA_DB_PORT"], dbname=config["EFA_DB_NAME"], user=config["EFA_DB_USER"], password=config["EFA_DB_PASSWORD"], connect_timeout=5)


def _collection_ref(messages: Iterable[NormalizedGmailMessage]) -> str:
    values = sorted(f"{item.gmail_message_id}:{item.content_hash}" for item in messages)
    digest = hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()
    return f"gmail-readonly:{digest}"


def persist_collection(messages: list[NormalizedGmailMessage], make_connection: Callable[[], Any] = connection_factory) -> dict[str, Any]:
    confirmed = [item for item in messages if item.confirmed_ozon]
    routes = [(item, *route_message(item)) for item in confirmed]
    relevant = [(item, domain) for item, route, domain in routes if route == EVENT_CANDIDATE]
    routine_count = sum(route == ROUTINE_OPERATIONAL for _, route, _ in routes)
    review_count = sum(route != ROUTINE_OPERATIONAL and route != EVENT_CANDIDATE for _, route, _ in routes)
    check_ref = _collection_ref(messages)
    connection = make_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """INSERT INTO information_sources
                   (source_id, title, source_type, source_authority, business_domains,
                    retrieval_method, document_format, monitoring_priority, source_metadata)
                 VALUES (%s, %s, 'EMAIL', 'LEVEL_2', %s::jsonb, 'GMAIL_READ_ONLY',
                         'email', 'HIGH', %s::jsonb)
                 ON CONFLICT (source_id) DO NOTHING""",
            (SOURCE_ID, "Ozon Gmail notifications", json.dumps([]), json.dumps({"authority": "authenticated_official_ozon_email_evidence"})),
        )
        cursor.execute("SELECT check_id FROM information_source_checks WHERE check_ref = %s", (check_ref,))
        if cursor.fetchone() is not None:
            connection.rollback()
            return {"idempotent_replay": True, "routine_operational_count": routine_count,
                    "event_candidate_count": len(relevant), "review_required_count": review_count,
                    "events_created": 0}
        snapshot_ids: list[Any] = []
        for item, domain in relevant:
            structure = {"gmail_message_id": item.gmail_message_id, "rfc_message_id": item.rfc_message_id,
                         "thread_id": item.thread_id, "received_at": item.received_at, "sender": item.sender,
                         "sender_domain": item.sender_domain, "subject": item.subject,
                         "normalized_text": item.normalized_text, "official_links": item.official_links,
                         "attachments": item.attachments, "classification": domain,
                         "header_data_quality": item.header_data_quality}
            cursor.execute(
                """INSERT INTO information_source_snapshots
                       (source_id, observed_at, retrieved_at, raw_sha256, canonical_sha256,
                        raw_byte_size, content_type, document_format, canonical_structure,
                        snapshot_metadata, evidence_reference)
                     VALUES (%s, %s, now(), %s, %s, %s, 'message/rfc822', 'email',
                             %s::jsonb, %s::jsonb, %s)
                     ON CONFLICT (source_id, canonical_sha256)
                     DO NOTHING
                  RETURNING snapshot_id""",
                (SOURCE_ID, item.received_at, item.content_hash, item.content_hash,
                 len(item.normalized_text.encode("utf-8")), json.dumps(structure, ensure_ascii=False),
                 json.dumps({"gmail_message_id": item.gmail_message_id, "thread_id": item.thread_id}),
                 f"gmail:message:{item.gmail_message_id}"),
            )
            existing = cursor.fetchone()
            if existing is None:
                cursor.execute(
                    """SELECT snapshot_id FROM information_source_snapshots
                         WHERE source_id = %s AND canonical_sha256 = %s""",
                    (SOURCE_ID, item.content_hash),
                )
                existing = cursor.fetchone()
            snapshot_id = existing[0]
            snapshot_ids.append(snapshot_id)
            cursor.execute(
                """INSERT INTO information_change_events
                       (event_key, source_id, current_snapshot_id, event_kind, classification,
                        business_domains, severity, requires_action, confidence, evidence_references, event_metadata)
                     VALUES (%s, %s, %s, 'EMAIL_EVENT', 'REVIEW', %s::jsonb, 'WATCH', false,
                             'MEDIUM', %s::jsonb, %s::jsonb)
                     ON CONFLICT (event_key) DO NOTHING""",
                (f"gmail-email:{SOURCE_ID}:{item.gmail_message_id}", SOURCE_ID, snapshot_id,
                 json.dumps([domain]), json.dumps([f"gmail:message:{item.gmail_message_id}"]),
                 json.dumps({"routing": EVENT_CANDIDATE, "classification": domain})),
            )
        status = "SUCCESS" if relevant else "SUCCESS_ZERO"
        cursor.execute(
            """INSERT INTO information_source_checks
                   (check_ref, source_id, checked_at, status, raw_byte_size, snapshot_id, error_summary)
                 VALUES (%s, %s, now(), %s, 0, %s, %s)""",
            (check_ref, SOURCE_ID, status, snapshot_ids[-1] if snapshot_ids else None,
             json.dumps({"confirmed_ozon": len(confirmed), "routine_operational": routine_count,
                         "event_candidates": len(relevant), "review_required": review_count})),
        )
        connection.commit()
        return {"idempotent_replay": False, "routine_operational_count": routine_count,
                "event_candidate_count": len(relevant), "review_required_count": review_count,
                "events_created": len(relevant), "status": status}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
