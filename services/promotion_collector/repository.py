"""Transactional persistence for normalized promotion collections."""
from __future__ import annotations

from typing import Any, Callable, Iterable
try:
    from .database import map_product_ids_with_cursor
except ImportError:
    from database import map_product_ids_with_cursor


class PersistenceError(RuntimeError):
    """Raised when a collection cannot safely be persisted."""


def get_run_by_collection_ref(cursor: Any, collection_ref: str) -> dict[str, Any] | None:
    cursor.execute(
        """SELECT run_id, collection_ref, collected_at, status, actions_count,
                  participating_records, candidate_records, unique_product_ids,
                  mapped_offer_ids, unmapped_product_ids, mapping_status,
                  error_summary, created_at
             FROM promotion_runs
            WHERE collection_ref = %s""",
        (collection_ref,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    columns = (
        "run_id", "collection_ref", "collected_at", "status", "actions_count",
        "participating_records", "candidate_records", "unique_product_ids",
        "mapped_offer_ids", "unmapped_product_ids", "mapping_status",
        "error_summary", "created_at",
    )
    return dict(zip(columns, row))


def create_run(cursor: Any, collection: dict[str, Any]) -> Any:
    cursor.execute(
        """INSERT INTO promotion_runs
               (collection_ref, collected_at, status, mapping_status)
             VALUES (%s, %s, 'running', %s)
          RETURNING run_id""",
        (collection["collection_ref"], collection["collected_at"], collection["mapping_status"]),
    )
    return cursor.fetchone()[0]


def insert_snapshots(cursor: Any, run_id: Any, snapshots: Iterable[dict[str, Any]]) -> None:
    rows = [
        (
            run_id, row["action_id"], row.get("action_title"), row.get("action_type"),
            row.get("action_start_at"), row.get("action_end_at"), row["source_list_type"],
            row["product_id"], row.get("offer_id"), row.get("add_mode"), row.get("price"),
            row.get("action_price"), row.get("max_action_price"), row["data_quality_status"],
        )
        for row in snapshots
    ]
    if not rows:
        return
    cursor.executemany(
        """INSERT INTO promotion_snapshots
               (run_id, action_id, action_title, action_type, action_start_at,
                action_end_at, source_list_type, product_id, offer_id, add_mode,
                price, action_price, max_action_price, data_quality_status)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        rows,
    )


def mark_run_success(cursor: Any, run_id: Any, collection: dict[str, Any]) -> None:
    cursor.execute(
        """UPDATE promotion_runs
              SET status = 'success', actions_count = %s,
                  participating_records = %s, candidate_records = %s,
                  unique_product_ids = %s, mapped_offer_ids = %s,
                  unmapped_product_ids = %s, mapping_status = %s,
                  error_summary = %s
            WHERE run_id = %s AND status = 'running'""",
        (
            collection["actions_count"], collection["participating_records"],
            collection["candidate_records"], collection["unique_product_ids"],
            collection["mapped_offer_ids"], collection["unmapped_product_ids_count"],
            collection["mapping_status"], collection.get("error_summary"), run_id,
        ),
    )
    if cursor.rowcount != 1:
        raise PersistenceError("current promotion run could not be marked successful")


def persist_collection(
    collection: dict[str, Any],
    connection_factory: Callable[[], Any],
) -> dict[str, Any]:
    connection = connection_factory()
    try:
        cursor = connection.cursor()
        existing = get_run_by_collection_ref(cursor, collection["collection_ref"])
        if existing is not None:
            if existing["status"] != "success":
                raise PersistenceError("collection_ref belongs to a non-successful run")
            connection.rollback()
            return {"run_id": existing["run_id"], "idempotent_replay": True}

        run_id = create_run(cursor, collection)
        product_ids = {row["product_id"] for row in collection["snapshots"]}
        mapped = map_product_ids_with_cursor(cursor, product_ids)
        snapshots = []
        for source in collection["snapshots"]:
            row = dict(source)
            row["offer_id"] = mapped.get(row["product_id"])
            row["data_quality_status"] = "valid" if row["offer_id"] is not None else "review"
            snapshots.append(row)
        unresolved = product_ids - set(mapped)
        persisted = {
            **collection,
            "snapshots": snapshots,
            "mapped_offer_ids": len(set(mapped.values())),
            "unmapped_product_ids_count": len(unresolved),
            "mapping_status": "valid" if not unresolved else ("partial" if mapped else "invalid"),
            "error_summary": "unmapped_product_ids" if unresolved else None,
        }
        insert_snapshots(cursor, run_id, snapshots)
        mark_run_success(cursor, run_id, persisted)
        connection.commit()
        return {"run_id": run_id, "idempotent_replay": False}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
