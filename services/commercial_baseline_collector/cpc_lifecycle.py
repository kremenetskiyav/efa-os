"""Durable CPC asynchronous report lifecycle backed by PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4


PENDING_STATES = frozenset({"NOT_STARTED", "IN_PROGRESS"})
READY_STATES = frozenset({"OK", "COMPLETE", "COMPLETED"})
SUCCESS_STATES = frozenset({"SUCCESS_ZERO", "SUCCESS_NONZERO"})
STUCK_AFTER = timedelta(hours=2)
POLL_LEASE_FOR = timedelta(minutes=5)


class LifecycleError(RuntimeError):
    pass


def classify_report_state(report_state: str) -> str:
    normalized = str(report_state or "").strip().upper()
    if normalized in PENDING_STATES:
        return "PENDING"
    if normalized in READY_STATES:
        return "READY"
    return "FAILED"


def prepare_action(lifecycle_state: str | None) -> str:
    if lifecycle_state is None:
        return "CREATE"
    if lifecycle_state == "PENDING":
        return "PENDING"
    if lifecycle_state in SUCCESS_STATES:
        return "SUCCESS"
    if lifecycle_state in {"FAILED", "STUCK"}:
        return lifecycle_state
    raise LifecycleError(f"Unsupported CPC lifecycle state: {lifecycle_state}")


def is_stuck(created_at: datetime, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    return current - created_at >= STUCK_AFTER


def _row_payload(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "run_id": str(row[0]),
        "collection_ref": row[1],
        "business_date": str(row[2]),
        "report_uuid": str(row[3]) if row[3] else None,
        "lifecycle_state": row[4],
        "report_state": row[5],
        "status_check_count": row[6],
        "campaigns": row[7] or [],
        "created_at": row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8]),
    }


def prepare_lifecycle(target: dict[str, Any], connection_factory: Callable[[], Any]) -> dict[str, Any]:
    connection = connection_factory()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"cpc:{target['business_date']}",),
        )
        cursor.execute(
            """SELECT run_id,collection_ref,business_date,report_uuid,lifecycle_state,
                      report_state,status_check_count,campaigns,created_at
                 FROM cpc_collection_runs
                WHERE business_date=%s
                FOR UPDATE""",
            (target["business_date"],),
        )
        existing = cursor.fetchone()
        if existing is not None:
            result = _row_payload(existing)
            action = prepare_action(result["lifecycle_state"])
            connection.commit()
            return {**result, "action": action, "should_create_report": False, "idempotent": True}

        cursor.execute(
            """INSERT INTO cpc_collection_runs
                   (collection_ref,collected_at,business_date,report_uuid,status,campaigns_count,
                    records_count,mapped_offer_ids,unmapped_skus,mapping_status,source,
                    lifecycle_state,report_state,campaigns)
                 VALUES (%s,%s,%s,NULL,'pending',0,0,0,0,'valid',
                         'ozon_performance_statistics_v1','PENDING','CREATE_RESERVED','[]'::jsonb)
                 RETURNING run_id,collection_ref,business_date,report_uuid,lifecycle_state,
                           report_state,status_check_count,campaigns,created_at""",
            (target["collection_ref"], target["requested_at"], target["business_date"]),
        )
        created = _row_payload(cursor.fetchone())
        connection.commit()
        return {**created, "action": "CREATE", "should_create_report": True, "idempotent": False}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def register_report(registration: dict[str, Any], connection_factory: Callable[[], Any]) -> dict[str, Any]:
    connection = connection_factory()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """SELECT run_id,collection_ref,business_date,report_uuid,lifecycle_state,
                      report_state,status_check_count,campaigns,created_at
                 FROM cpc_collection_runs
                WHERE business_date=%s
                FOR UPDATE""",
            (registration["business_date"],),
        )
        existing = cursor.fetchone()
        if existing is None:
            raise LifecycleError("CPC create reservation does not exist")
        current = _row_payload(existing)
        if current["lifecycle_state"] != "PENDING":
            raise LifecycleError(f"CPC lifecycle is not pending: {current['lifecycle_state']}")
        if current["report_uuid"] and current["report_uuid"] != registration["report_uuid"]:
            raise LifecycleError("CPC business_date already owns a different report UUID")
        if current["report_uuid"] == registration["report_uuid"]:
            connection.commit()
            return {**current, "action": "PENDING", "registered": False, "idempotent": True}

        cursor.execute(
            """UPDATE cpc_collection_runs
                  SET report_uuid=%s,report_state='CREATED',campaigns=%s::jsonb,
                      campaigns_count=%s,updated_at=now()
                WHERE run_id=%s AND lifecycle_state='PENDING' AND report_uuid IS NULL
                RETURNING run_id,collection_ref,business_date,report_uuid,lifecycle_state,
                          report_state,status_check_count,campaigns,created_at""",
            (registration["report_uuid"], registration["campaigns_json"],
             len(registration["campaigns"]), current["run_id"]),
        )
        updated = cursor.fetchone()
        if updated is None:
            raise LifecycleError("CPC report registration lost its reservation")
        result = _row_payload(updated)
        connection.commit()
        return {**result, "action": "PENDING", "registered": True, "idempotent": False}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def claim_pending(connection_factory: Callable[[], Any]) -> dict[str, Any]:
    connection = connection_factory()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """UPDATE cpc_collection_runs
                  SET status='stuck',lifecycle_state='STUCK',updated_at=now(),
                      error_code='REPORT_STUCK',
                      error_message='Performance report remained pending beyond 2 hours',
                      attention_reason='REPORT_STUCK: owner review required before replacement',
                      poll_lease_token=NULL,poll_lease_until=NULL
                WHERE lifecycle_state='PENDING'
                  AND created_at <= now() - interval '2 hours'""",
            (),
        )
        cursor.execute(
            """SELECT run_id,collection_ref,business_date,report_uuid,lifecycle_state,
                      report_state,status_check_count,campaigns,created_at
                 FROM cpc_collection_runs
                WHERE lifecycle_state='PENDING'
                  AND report_uuid IS NOT NULL
                  AND (poll_lease_until IS NULL OR poll_lease_until < now())
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1""",
            (),
        )
        pending = cursor.fetchone()
        if pending is None:
            connection.commit()
            return {"claimed": False, "action": "IDLE", "batch_size": 0}
        item = _row_payload(pending)
        lease_token = str(uuid4())
        cursor.execute(
            """UPDATE cpc_collection_runs
                  SET poll_lease_token=%s,poll_lease_until=now() + interval '5 minutes',updated_at=now()
                WHERE run_id=%s AND lifecycle_state='PENDING'""",
            (lease_token, item["run_id"]),
        )
        if cursor.rowcount != 1:
            raise LifecycleError("CPC pending report could not be leased")
        connection.commit()
        return {**item, "claimed": True, "action": "CHECK_STATUS", "lease_token": lease_token, "batch_size": 1}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def record_report_status(status: dict[str, Any], connection_factory: Callable[[], Any]) -> dict[str, Any]:
    connection = connection_factory()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """SELECT run_id,collection_ref,business_date,report_uuid,lifecycle_state,
                      report_state,status_check_count,campaigns,created_at,
                      poll_lease_token
                 FROM cpc_collection_runs
                WHERE run_id=%s
                FOR UPDATE""",
            (status["run_id"],),
        )
        row = cursor.fetchone()
        if row is None:
            raise LifecycleError("CPC lifecycle run does not exist")
        item = _row_payload(row[:9])
        lease_token = str(row[9]) if row[9] else None
        if lease_token != status["lease_token"]:
            raise LifecycleError("CPC poll lease is missing or expired")
        if item["lifecycle_state"] != "PENDING":
            connection.commit()
            return {**item, "action": item["lifecycle_state"], "idempotent": True}
        if item["report_uuid"] != status["report_uuid"]:
            raise LifecycleError("CPC status UUID does not match its lifecycle")

        report_state = status["report_state"]
        classification = classify_report_state(report_state)
        created_at = row[8]
        if classification == "PENDING" and is_stuck(created_at):
            classification = "STUCK"

        if classification == "PENDING":
            cursor.execute(
                """UPDATE cpc_collection_runs
                      SET report_state=%s,last_status_check_at=now(),
                          status_check_count=status_check_count+1,updated_at=now(),
                          poll_lease_token=NULL,poll_lease_until=NULL,
                          error_code=NULL,error_message=NULL,attention_reason=NULL
                    WHERE run_id=%s
                    RETURNING run_id,collection_ref,business_date,report_uuid,lifecycle_state,
                              report_state,status_check_count,campaigns,created_at""",
                (report_state, item["run_id"]),
            )
            action = "PENDING"
        elif classification == "READY":
            cursor.execute(
                """UPDATE cpc_collection_runs
                      SET report_state=%s,last_status_check_at=now(),
                          status_check_count=status_check_count+1,updated_at=now(),
                          error_code=NULL,error_message=NULL,attention_reason=NULL
                    WHERE run_id=%s
                    RETURNING run_id,collection_ref,business_date,report_uuid,lifecycle_state,
                              report_state,status_check_count,campaigns,created_at""",
                (report_state, item["run_id"]),
            )
            action = "READY"
        else:
            lifecycle_state = "STUCK" if classification == "STUCK" else "FAILED"
            legacy_status = "stuck" if classification == "STUCK" else "failed"
            error_code = "REPORT_STUCK" if classification == "STUCK" else (status.get("error_code") or f"REPORT_{report_state}")
            error_message = "Performance report remained pending beyond 2 hours" if classification == "STUCK" else (status.get("error_message") or f"Performance report entered terminal state: {report_state}")
            attention = f"{error_code}: {error_message}"
            cursor.execute(
                """UPDATE cpc_collection_runs
                      SET status=%s,lifecycle_state=%s,report_state=%s,
                          last_status_check_at=now(),status_check_count=status_check_count+1,
                          updated_at=now(),completed_at=now(),error_code=%s,error_message=%s,
                          attention_reason=%s,poll_lease_token=NULL,poll_lease_until=NULL
                    WHERE run_id=%s
                    RETURNING run_id,collection_ref,business_date,report_uuid,lifecycle_state,
                              report_state,status_check_count,campaigns,created_at""",
                (legacy_status, lifecycle_state, report_state, error_code, error_message,
                 attention, item["run_id"]),
            )
            action = lifecycle_state
        result = _row_payload(cursor.fetchone())
        connection.commit()
        return {**result, "action": action, "idempotent": False}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
