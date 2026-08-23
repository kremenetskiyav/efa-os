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
        cursor.execute(
            """SELECT run_id,status,lifecycle_state,report_uuid,business_date
                 FROM cpc_collection_runs
                WHERE collection_ref=%s
                FOR UPDATE""",
            (collection["collection_ref"],),
        )
        existing = cursor.fetchone()
        if existing is None:
            raise PersistenceError("CPC lifecycle is not registered")
        if existing[2] in {"SUCCESS_ZERO", "SUCCESS_NONZERO"}:
            connection.rollback()
            return {"run_id": existing[0], "idempotent_replay": True, "inserted_records": 0}
        if existing[2] != "PENDING":
            raise PersistenceError(f"CPC lifecycle cannot persist from {existing[2]}")
        if str(existing[3]) != collection["report_uuid"]:
            raise PersistenceError("CPC report UUID does not match its lifecycle")
        if str(existing[4]) != collection["business_date"]:
            raise PersistenceError("CPC business_date does not match its lifecycle")
        if any(row["business_date"] != collection["business_date"] for row in collection["rows"]):
            raise PersistenceError("CPC report contains a different business_date")
        rows, unmapped = _map_rows(cursor, collection["rows"])
        mapping_status = "valid" if not unmapped else ("partial" if len(unmapped) < len({r['sku'] for r in rows}) else "invalid")
        run_id = existing[0]
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
        lifecycle_state = "SUCCESS_NONZERO" if rows else "SUCCESS_ZERO"
        cursor.execute(
            """UPDATE cpc_collection_runs
                  SET status='success',lifecycle_state=%s,collected_at=%s,updated_at=now(),
                      completed_at=now(),campaigns_count=%s,records_count=%s,
                      mapped_offer_ids=%s,unmapped_skus=%s,mapping_status=%s,
                      error_code=NULL,error_message=NULL,attention_reason=NULL,
                      poll_lease_token=NULL,poll_lease_until=NULL
                WHERE run_id=%s AND lifecycle_state='PENDING'""",
            (lifecycle_state, collection["collected_at"], collection["campaigns_count"], len(rows),
             len({r["offer_id"] for r in rows if r["offer_id"]}), len(unmapped), mapping_status, run_id),
        )
        if cursor.rowcount != 1:
            raise PersistenceError("CPC run lifecycle update failed")
        connection.commit()
        return {"run_id": run_id, "idempotent_replay": False, "inserted_records": len(rows),
                "mapped_offer_ids": len({r['offer_id'] for r in rows if r['offer_id']}),
                "unmapped_skus": sorted(unmapped), "mapping_status": mapping_status,
                "lifecycle_state": lifecycle_state}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def persist_prices(collection: dict[str, Any], connection_factory: Callable[[], Any]) -> dict[str, Any]:
    connection = connection_factory()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT run_id, status, products_count, changed_records, unchanged_records FROM price_collection_runs WHERE collection_ref=%s", (collection["collection_ref"],))
        existing = cursor.fetchone()
        if existing is not None:
            if existing[1] != "success":
                raise PersistenceError("price collection_ref belongs to incomplete run")
            connection.rollback()
            return {"run_id": existing[0], "idempotent_replay": True, "products_count": existing[2], "changed_records": existing[3], "unchanged_records": existing[4]}

        product_ids = [row["product_id"] for row in collection["rows"]]
        cursor.execute("""SELECT p.product_id, p.offer_id, p.price, p.old_price, p.min_price,
                                  p.marketing_price,
                                  (SELECT h.marketing_seller_price FROM ozon_price_history h
                                    WHERE h.product_id=p.product_id ORDER BY h.updated_from_ozon DESC,h.id DESC LIMIT 1)
                             FROM products p WHERE p.product_id = ANY(%s) FOR UPDATE""", (product_ids,))
        current = {row[0]: row[1:] for row in cursor.fetchall()}
        unmapped = sorted(set(product_ids) - set(current))
        mismatched = [row["product_id"] for row in collection["rows"] if current.get(row["product_id"], (None,))[0] != row["offer_id"]]
        if unmapped or mismatched or len(current) != len(collection["rows"]):
            raise PersistenceError("price payload does not map exactly to canonical products")

        cursor.execute("""INSERT INTO price_collection_runs
            (collection_ref,collected_at,status,products_count,data_quality_status)
            VALUES (%s,%s,'running',%s,'valid') RETURNING run_id""",
            (collection["collection_ref"], collection["collected_at"], len(collection["rows"])))
        run_id = cursor.fetchone()[0]
        changed = 0
        for row in collection["rows"]:
            previous = current[row["product_id"]]
            values = (row["price"], row["old_price"], row["min_price"], row["marketing_price"], row["marketing_seller_price"])
            is_changed = tuple(previous[1:]) != values
            cursor.execute("""UPDATE products SET price=%s,old_price=%s,min_price=%s,marketing_price=%s,
                updated_from_ozon=%s WHERE product_id=%s AND offer_id=%s""",
                (*values[:4], collection["collected_at"], row["product_id"], previous[0]))
            if cursor.rowcount != 1:
                raise PersistenceError("canonical product update failed")
            if is_changed:
                cursor.execute("""INSERT INTO ozon_price_history
                    (product_id,offer_id,price,old_price,min_price,marketing_price,marketing_seller_price,updated_from_ozon)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (row["product_id"], previous[0], row["price"], row["old_price"], row["min_price"],
                     row["marketing_price"], row["marketing_seller_price"], collection["collected_at"]))
                changed += 1
            cursor.execute("""INSERT INTO ozon_fbs_tariff_snapshots
                (price_collection_run_id,product_id,offer_id,observed_at,sales_percent_fbs,
                 fbs_deliv_to_customer_amount,acquiring,fbs_direct_flow_trans_min_amount,
                 fbs_direct_flow_trans_max_amount,fbs_return_flow_amount)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (run_id, row["product_id"], previous[0], collection["collected_at"],
                 row["sales_percent_fbs"], row["fbs_deliv_to_customer_amount"], row["acquiring"],
                 row["fbs_direct_flow_trans_min_amount"], row["fbs_direct_flow_trans_max_amount"],
                 row["fbs_return_flow_amount"]))
        unchanged = len(collection["rows"]) - changed
        cursor.execute("""UPDATE price_collection_runs SET status='success',changed_records=%s,
            unchanged_records=%s WHERE run_id=%s AND status='running'""", (changed, unchanged, run_id))
        if cursor.rowcount != 1:
            raise PersistenceError("price run lifecycle update failed")
        connection.commit()
        return {"run_id": run_id, "idempotent_replay": False, "products_count": len(collection["rows"]),
                "changed_records": changed, "unchanged_records": unchanged, "unmapped_products": [] ,
                "collection_status": "SUCCESS_CHANGED" if changed else "SUCCESS_UNCHANGED"}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
