-- Post-deployment validation for migration
-- 014_operational_finance_data_capture_v1.sql.
-- The validation transaction is read-only and leaves no database changes.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    invalid_columns text;
BEGIN
    WITH expected(table_name, column_name, data_type) AS (
        VALUES
            ('postings', 'in_process_at', 'timestamp with time zone'),
            ('finance_operations', 'order_date', 'timestamp without time zone'),
            ('finance_operations', 'services_json', 'jsonb')
    )
    SELECT STRING_AGG(
               e.table_name || '.' || e.column_name,
               ', ' ORDER BY e.table_name, e.column_name
           )
      INTO invalid_columns
      FROM expected e
      LEFT JOIN information_schema.columns c
        ON c.table_schema = 'public'
       AND c.table_name = e.table_name
       AND c.column_name = e.column_name
     WHERE c.column_name IS NULL
        OR c.data_type <> e.data_type
        OR c.is_nullable <> 'YES'
        OR c.column_default IS NOT NULL;

    IF invalid_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing or invalid nullable capture columns: %', invalid_columns;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM public.finance_operations f
         WHERE f.services_json IS NOT NULL
           AND jsonb_typeof(f.services_json) <> 'array'
    ) THEN
        RAISE EXCEPTION 'finance_operations.services_json contains a non-array value';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.finance_operations f
          CROSS JOIN LATERAL jsonb_array_elements(
              CASE
                  WHEN jsonb_typeof(f.services_json) = 'array' THEN f.services_json
                  ELSE '[]'::jsonb
              END
          ) AS service(item)
         WHERE f.services_json IS NOT NULL
           AND (
               jsonb_typeof(service.item) <> 'object'
               OR NOT (service.item ? 'name')
               OR NOT (service.item ? 'price')
           )
    ) THEN
        RAISE EXCEPTION 'finance_operations.services_json contains an item without name or price';
    END IF;
END $$;

SELECT
    COUNT(*) FILTER (WHERE in_process_at IS NOT NULL) AS postings_with_in_process_at,
    COUNT(*) AS postings_total
FROM public.postings
WHERE shipment_date >= timestamptz '2026-08-13 00:00:00+03'
  AND shipment_date < timestamptz '2026-08-21 00:00:00+03';

SELECT
    COUNT(*) FILTER (WHERE order_date IS NOT NULL) AS finance_with_order_date,
    COUNT(*) FILTER (WHERE services_json IS NOT NULL) AS finance_with_services_json,
    COUNT(*) AS finance_total
FROM public.finance_operations
WHERE operation_date >= timestamp '2026-08-14 00:00:00'
  AND operation_date < timestamp '2026-08-21 00:00:00';

SELECT
    f.operation_id,
    service.item->>'name' AS service_name,
    (service.item->>'price')::numeric AS price
FROM public.finance_operations f
CROSS JOIN LATERAL jsonb_array_elements(
    CASE
        WHEN jsonb_typeof(f.services_json) = 'array' THEN f.services_json
        ELSE '[]'::jsonb
    END
) AS service(item)
WHERE f.operation_id IN (59946801354, 60139891868)
  AND service.item->>'name' = 'MarketplaceServiceItemDeliveryToHandoverPlaceOzon'
ORDER BY f.operation_id;

SELECT
    posting_number,
    in_process_at,
    in_process_at AT TIME ZONE 'Europe/Moscow' AS in_process_at_moscow
FROM public.postings
WHERE posting_number IN ('92563708-0444-1', '06617065-0405-1')
ORDER BY posting_number;

SELECT
    operation_id,
    posting_number,
    order_date
FROM public.finance_operations
WHERE posting_number LIKE '92563708-0444%'
   OR posting_number LIKE '06617065-0405%'
ORDER BY order_date, operation_id;

SELECT 1 AS product_daily_performance_smoke
FROM mcp_read.product_daily_performance
LIMIT 1;

SELECT 1 AS orders_profit_smoke
FROM public.vw_orders_profit_final
LIMIT 1;

ROLLBACK;
