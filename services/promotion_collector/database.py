"""Runtime PostgreSQL access for mapping and explicitly enabled persistence."""
import os
def connect_database():
    import psycopg2
    return psycopg2.connect(host=os.environ["EFA_DB_HOST"],port=os.environ["EFA_DB_PORT"],dbname=os.environ["EFA_DB_NAME"],user=os.environ["EFA_DB_USER"],password=os.environ["EFA_DB_PASSWORD"])

def map_product_ids_with_cursor(cursor, product_ids: set[int]) -> dict[int,str]:
    if not product_ids: return {}
    cursor.execute("SELECT product_id, offer_id FROM products WHERE product_id = ANY(%s)",(list(product_ids),))
    return dict(cursor.fetchall())

def map_product_ids(product_ids: set[int]) -> dict[int,str]:
    if not product_ids: return {}
    import psycopg2
    with psycopg2.connect(host=os.environ["EFA_DB_HOST"],port=os.environ["EFA_DB_PORT"],dbname=os.environ["EFA_DB_NAME"],user=os.environ["EFA_DB_USER"],password=os.environ["EFA_DB_PASSWORD"],options="-c default_transaction_read_only=on") as conn:
        with conn.cursor() as cur:
            return map_product_ids_with_cursor(cur,product_ids)
