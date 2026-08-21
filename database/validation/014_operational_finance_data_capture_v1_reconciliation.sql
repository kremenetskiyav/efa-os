-- Golden reconciliation for the official Ozon unit-economics period
-- 2026-08-14 through 2026-08-20 (inclusive).
--
-- The expected PBT values identify the five-row acceptance fixture only.
-- The calculation contains no SKU-specific or operation-specific adjustment.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

WITH
params AS (
    SELECT
        timestamp '2026-08-14 00:00:00' AS from_ts,
        timestamp '2026-08-21 00:00:00' AS to_ts,
        date '2026-08-14' AS from_date,
        date '2026-08-21' AS to_date
),
expected(offer_id, ozon_pbt, sort_order) AS (
    VALUES
        ('УФ 001Б', numeric '193.54', 1),
        ('УФ 002Б', numeric '-6.43', 2),
        ('УФ 003Б', numeric '24.92', 3),
        ('УФ 004Б', numeric '-212.51', 4),
        ('УФ 005Б', numeric '79.40', 5)
),
product_scope AS (
    SELECT p.offer_id, p.sku, p.cost_price
    FROM public.products p
    JOIN expected e ON e.offer_id = p.offer_id
),
finance_period AS (
    SELECT
        f.*,
        COALESCE(NULLIF(f.offer_id, ''), p.offer_id) AS resolved_offer_id
    FROM public.finance_operations f
    JOIN product_scope p ON p.sku = f.sku
    CROSS JOIN params q
    WHERE f.operation_date >= q.from_ts
      AND f.operation_date < q.to_ts
),
delivered AS (
    SELECT
        f.resolved_offer_id AS offer_id,
        SUM(f.accruals_for_sale)::numeric AS gross_sales,
        SUM(f.sale_commission)::numeric AS commission,
        SUM(po.quantity)::numeric AS delivered_units,
        COUNT(*) FILTER (WHERE po.quantity IS NULL) AS missing_delivery_quantity
    FROM finance_period f
    CROSS JOIN params q
    LEFT JOIN public.postings po
      ON po.posting_number = f.posting_number
     AND po.offer_id = f.resolved_offer_id
     AND po.sku = f.sku
    WHERE f.operation_type = 'OperationAgentDeliveredToCustomer'
      AND f.order_date >= q.from_ts
      AND f.order_date < q.to_ts
    GROUP BY f.resolved_offer_id
),
sale_services AS (
    SELECT
        f.resolved_offer_id AS offer_id,
        SUM((service.item->>'price')::numeric)::numeric AS services
    FROM finance_period f
    CROSS JOIN params q
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(f.services_json) = 'array' THEN f.services_json
            ELSE '[]'::jsonb
        END
    ) AS service(item)
    WHERE f.operation_type = 'OperationAgentDeliveredToCustomer'
      AND (
          (f.order_date >= q.from_ts AND f.order_date < q.to_ts)
          OR service.item->>'name' = 'MarketplaceServiceItemDeliveryToHandoverPlaceOzon'
      )
    GROUP BY f.resolved_offer_id
),
acquiring AS (
    SELECT
        f.resolved_offer_id AS offer_id,
        SUM(f.amount)::numeric AS acquiring
    FROM finance_period f
    CROSS JOIN params q
    WHERE f.operation_type = 'MarketplaceRedistributionOfAcquiringOperation'
      AND (
          (f.order_date >= q.from_ts AND f.order_date < q.to_ts)
          OR f.amount > 0
      )
    GROUP BY f.resolved_offer_id
),
real_return_rows AS (
    SELECT
        r.offer_id,
        r.sku,
        r.quantity,
        CASE
            WHEN r.posting_number ~ '^[^-]+-[^-]+-[^-]+$'
                THEN regexp_replace(r.posting_number, '-[^-]+$', '')
            ELSE r.posting_number
        END AS posting_key
    FROM public.returns r
    JOIN expected e ON e.offer_id = r.offer_id
    CROSS JOIN params q
    WHERE r.type = 'ClientReturn'
      AND (r.logistic_return_date AT TIME ZONE 'Europe/Moscow')::date >= q.from_date
      AND (r.logistic_return_date AT TIME ZONE 'Europe/Moscow')::date < q.to_date
),
real_returns AS (
    SELECT offer_id, SUM(quantity)::numeric AS returned_units
    FROM real_return_rows
    GROUP BY offer_id
),
real_return_keys AS (
    SELECT DISTINCT offer_id, sku, posting_key
    FROM real_return_rows
),
return_operations AS (
    SELECT
        f.resolved_offer_id AS offer_id,
        SUM(f.amount)::numeric AS return_operations
    FROM finance_period f
    JOIN real_return_keys r
      ON r.offer_id = f.resolved_offer_id
     AND r.sku IS NOT DISTINCT FROM f.sku
     AND r.posting_key = CASE
         WHEN f.posting_number ~ '^[^-]+-[^-]+-[^-]+$'
             THEN regexp_replace(f.posting_number, '-[^-]+$', '')
         ELSE f.posting_number
     END
    WHERE f.operation_type IN (
        'ClientReturnAgentOperation',
        'OperationReturnGoodsFBSofRMS',
        'OperationMarketplacePackageMaterialsProvision',
        'OperationMarketplacePackageRedistribution'
    )
    GROUP BY f.resolved_offer_id
),
components AS (
    SELECT
        e.offer_id,
        COALESCE(d.gross_sales, 0)::numeric AS gross_sales,
        COALESCE(d.commission, 0)::numeric AS commission,
        COALESCE(a.acquiring, 0)::numeric AS acquiring,
        COALESCE(s.services, 0)::numeric AS services,
        COALESCE(ro.return_operations, 0)::numeric AS return_operations,
        COALESCE(d.delivered_units, 0)::numeric AS delivered_units,
        COALESCE(rr.returned_units, 0)::numeric AS returned_units,
        (
            p.cost_price
            * (COALESCE(d.delivered_units, 0) - COALESCE(rr.returned_units, 0))
        )::numeric AS cogs,
        COALESCE(d.missing_delivery_quantity, 0) AS missing_delivery_quantity,
        e.ozon_pbt,
        e.sort_order
    FROM expected e
    JOIN product_scope p ON p.offer_id = e.offer_id
    LEFT JOIN delivered d ON d.offer_id = e.offer_id
    LEFT JOIN acquiring a ON a.offer_id = e.offer_id
    LEFT JOIN sale_services s ON s.offer_id = e.offer_id
    LEFT JOIN real_returns rr ON rr.offer_id = e.offer_id
    LEFT JOIN return_operations ro ON ro.offer_id = e.offer_id
),
reconciled AS (
    SELECT
        c.*,
        (
            gross_sales
            + commission
            + acquiring
            + services
            + return_operations
            - cogs
        )::numeric AS calculated_pbt
    FROM components c
)
SELECT
    offer_id,
    ROUND(gross_sales, 2) AS gross_sales,
    ROUND(commission, 2) AS commission,
    ROUND(acquiring, 2) AS acquiring,
    ROUND(services, 2) AS services,
    ROUND(return_operations, 2) AS return_operations,
    ROUND(cogs, 2) AS cogs,
    delivered_units,
    returned_units,
    ROUND(calculated_pbt, 2) AS calculated_pbt,
    ozon_pbt,
    ROUND(calculated_pbt - ozon_pbt, 2) AS difference,
    CASE
        WHEN missing_delivery_quantity <> 0 THEN 'FAIL_MISSING_QUANTITY'
        WHEN ABS(calculated_pbt - ozon_pbt) <= numeric '0.01' THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM reconciled
ORDER BY sort_order;

ROLLBACK;
