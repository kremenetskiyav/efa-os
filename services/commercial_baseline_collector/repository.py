"""Transactional, immutable persistence for daily commercial flows."""
from __future__ import annotations

from typing import Any, Callable

try:
    from .database import map_skus_with_cursor
except ImportError:
    from database import map_skus_with_cursor


class PersistenceError(RuntimeError):
    pass


def _map_rows(cursor: Any, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[int]]:
    skus = {row["sku"] for row in rows}
    mapping = map_skus_with_cursor(cursor, skus)
    normalized = []
    for source in rows:
        row = dict(source)
        row["offer_id"] = mapping.get(row["sku"])
        row["data_quality_status"] = "valid" if row["offer_id"] else "review"
        normalized.append(row)
    return normalized, skus - set(mapping)


def persist_seller_demand(collection: dict[str, Any], connection_factory: Callable[[], Any]) -> dict[str, Any]:
    connection = connection_factory()
    try:
        cursor = connection.cursor()
        rows, unmapped = _map_rows(cursor, collection["rows"])
        if unmapped:
            raise PersistenceError("seller demand contains unmapped SKU")
        inserted = 0
        replayed = 0
        for row in rows:
            cursor.execute(
                """SELECT sku, ordered_revenue, ordered_units, source
                     FROM seller_product_demand_daily
                    WHERE offer_id=%s AND business_date=%s""",
                (row["offer_id"], row["business_date"]),
            )
            existing = cursor.fetchone()
            logical = (row["sku"], row["ordered_revenue"], row["ordered_units"], row["source"])
            if existing is not None:
                if tuple(existing) != logical:
                    raise PersistenceError("immutable seller demand row conflicts with existing data")
                replayed += 1
                continue
            cursor.execute(
                """INSERT INTO seller_product_demand_daily
                       (collection_ref, offer_id, sku, business_date, ordered_revenue,
                        ordered_units, collected_at, source, data_quality_status)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (row["collection_ref"], row["offer_id"], row["sku"], row["business_date"],
                 row["ordered_revenue"], row["ordered_units"], row["collected_at"], row["source"],
                 row["data_quality_status"]),
            )
            inserted += 1
        connection.commit()
        return {"inserted_records": inserted, "idempotent_records": replayed, "mapped_offer_ids": len(rows), "unmapped_skus": []}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def persist_cpc(collection: dict[str, Any], connection_factory: Callable[[], Any]) -> dict[str, Any]:
    connection = connection_factory()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT run_id, status FROM cpc_collection_runs WHERE collection_ref=%s", (collection["collection_ref"],))
        existing = cursor.fetchone()
        if existing is not None:
            if existing[1] != "success":
                raise PersistenceError("CPC collection_ref belongs to incomplete run")
            connection.rollback()
            return {"run_id": existing[0], "idempotent_replay": True, "inserted_records": 0}
        rows, unmapped = _map_rows(cursor, collection["rows"])
        mapping_status = "valid" if not unmapped else ("partial" if len(unmapped) < len({r['sku'] for r in rows}) else "invalid")
        cursor.execute(
            """INSERT INTO cpc_collection_runs
                   (collection_ref,collected_at,business_date,report_uuid,status,campaigns_count,
                    records_count,mapped_offer_ids,unmapped_skus,mapping_status,source)
                 VALUES (%s,%s,%s,%s,'running',%s,%s,%s,%s,%s,%s) RETURNING run_id""",
            (collection["collection_ref"], collection["collected_at"], collection["business_date"],
             collection["report_uuid"], collection["campaigns_count"], len(rows),
             len({r["offer_id"] for r in rows if r["offer_id"]}), len(unmapped), mapping_status,
             "ozon_performance_statistics_v1"),
        )
        run_id = cursor.fetchone()[0]
        detail_rows = [(
            run_id, row["business_date"], row["campaign_id"], row.get("campaign_state"),
            row.get("campaign_type"), row["sku"], row.get("offer_id"), row["views"], row["clicks"],
            row["ctr"], row["avg_bid"], row["money_spent"], row["orders"], row["orders_money"],
            row["drr"], row["general_drr"], row["product_gmv"], row["price"], row["report_uuid"],
            row["source"], row["data_quality_status"],
        ) for row in rows]
        if detail_rows:
            cursor.executemany(
                """INSERT INTO cpc_advertising_daily
                       (run_id,business_date,campaign_id,campaign_state,campaign_type,sku,offer_id,
                        views,clicks,ctr,avg_bid,money_spent,orders,orders_money,drr,general_drr,
                        product_gmv,price,report_uuid,source,data_quality_status)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                detail_rows,
            )
        cursor.execute("UPDATE cpc_collection_runs SET status='success' WHERE run_id=%s AND status='running'", (run_id,))
        if cursor.rowcount != 1:
            raise PersistenceError("CPC run lifecycle update failed")
        connection.commit()
        return {"run_id": run_id, "idempotent_replay": False, "inserted_records": len(rows), "mapped_offer_ids": len({r['offer_id'] for r in rows if r['offer_id']}), "unmapped_skus": sorted(unmapped), "mapping_status": mapping_status}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
