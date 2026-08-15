"""Runtime PostgreSQL access; credentials are supplied only at runtime."""
import os


def connect_database():
    import psycopg2
    return psycopg2.connect(
        host=os.environ["EFA_DB_HOST"],
        port=os.environ["EFA_DB_PORT"],
        dbname=os.environ["EFA_DB_NAME"],
        user=os.environ["EFA_DB_USER"],
        password=os.environ["EFA_DB_PASSWORD"],
    )


def map_skus_with_cursor(cursor, skus: set[int]) -> dict[int, str]:
    if not skus:
        return {}
    cursor.execute(
        "SELECT sku, offer_id FROM products WHERE sku = ANY(%s)",
        (list(skus),),
    )
    return dict(cursor.fetchall())
