-- MCP financial period economics v1
--
-- Adds one bounded, read-only range function over the raw operational finance
-- tables. The function keeps daily demand and lifecycle facts in
-- mcp_read.product_daily_performance unchanged.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE FUNCTION mcp_read.product_period_economics(
    p_from_date date,
    p_to_date date
)
RETURNS TABLE (
    sku text,
    from_date date,
    to_date date,
    delivered_units integer,
    returned_units integer,
    net_sold_units integer,
    gross_sales numeric,
    commission numeric,
    acquiring numeric,
    services numeric,
    return_operations numeric,
    cogs numeric,
    profit_before_tax numeric,
    profit_per_unit numeric,
    margin_before_tax numeric
)
LANGUAGE sql
STABLE
SECURITY DEFINER
RETURNS NULL ON NULL INPUT
SET search_path = pg_catalog
AS $function$
WITH
params AS (
    SELECT
        p_from_date AS from_date,
        p_to_date AS to_date,
        p_from_date::timestamp AS from_ts,
        (p_to_date + 1)::timestamp AS to_ts
    WHERE p_to_date >= p_from_date
      AND p_to_date - p_from_date <= 92
),
product_scope AS (
    SELECT
        p.offer_id AS sku,
        p.sku AS ozon_sku,
        p.cost_price
    FROM public.products p
    CROSS JOIN params q
),
finance_period AS (
    SELECT
        f.*,
        p.sku AS resolved_sku
    FROM public.finance_operations f
    JOIN product_scope p ON p.ozon_sku = f.sku
    CROSS JOIN params q
    WHERE f.operation_date >= q.from_ts
      AND f.operation_date < q.to_ts
),
capture_gaps AS (
    SELECT
        f.resolved_sku AS sku,
        COUNT(*) FILTER (
            WHERE f.operation_type = 'OperationAgentDeliveredToCustomer'
              AND (
                  f.order_date IS NULL
                  OR f.accruals_for_sale IS NULL
                  OR f.sale_commission IS NULL
                  OR f.services_json IS NULL
                  OR jsonb_typeof(f.services_json) <> 'array'
              )
        ) + COUNT(*) FILTER (
            WHERE f.operation_type = 'MarketplaceRedistributionOfAcquiringOperation'
              AND (
                  f.amount IS NULL
                  OR (f.amount <= 0 AND f.order_date IS NULL)
              )
        ) AS missing_required_fields
    FROM finance_period f
    GROUP BY f.resolved_sku
),
delivered AS (
    SELECT
        f.resolved_sku AS sku,
        SUM(f.accruals_for_sale)::numeric AS gross_sales,
        SUM(f.sale_commission)::numeric AS signed_commission,
        SUM(po.quantity)::integer AS delivered_units,
        COUNT(*) FILTER (WHERE po.quantity IS NULL) AS missing_delivery_quantity
    FROM finance_period f
    CROSS JOIN params q
    LEFT JOIN public.postings po
      ON po.posting_number = f.posting_number
     AND po.offer_id = f.resolved_sku
     AND po.sku = f.sku
    WHERE f.operation_type = 'OperationAgentDeliveredToCustomer'
      AND f.order_date >= q.from_ts
      AND f.order_date < q.to_ts
    GROUP BY f.resolved_sku
),
sale_services AS (
    SELECT
        f.resolved_sku AS sku,
        SUM((service.item->>'price')::numeric)::numeric AS signed_services
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
    GROUP BY f.resolved_sku
),
acquiring_operations AS (
    SELECT
        f.resolved_sku AS sku,
        SUM(f.amount)::numeric AS signed_acquiring
    FROM finance_period f
    CROSS JOIN params q
    WHERE f.operation_type = 'MarketplaceRedistributionOfAcquiringOperation'
      AND (
          (f.order_date >= q.from_ts AND f.order_date < q.to_ts)
          OR f.amount > 0
      )
    GROUP BY f.resolved_sku
),
real_return_rows AS (
    SELECT
        r.offer_id AS sku,
        r.sku AS ozon_sku,
        r.quantity,
        CASE
            WHEN r.posting_number ~ '^[^-]+-[^-]+-[^-]+$'
                THEN regexp_replace(r.posting_number, '-[^-]+$', '')
            ELSE r.posting_number
        END AS posting_key
    FROM public.returns r
    JOIN product_scope p ON p.sku = r.offer_id
    CROSS JOIN params q
    WHERE r.type = 'ClientReturn'
      AND (r.logistic_return_date AT TIME ZONE 'Europe/Moscow')::date >= q.from_date
      AND (r.logistic_return_date AT TIME ZONE 'Europe/Moscow')::date <= q.to_date
),
real_returns AS (
    SELECT
        r.sku,
        SUM(r.quantity)::integer AS returned_units,
        COUNT(*) FILTER (WHERE r.quantity IS NULL) AS missing_return_quantity
    FROM real_return_rows r
    GROUP BY r.sku
),
real_return_keys AS (
    SELECT DISTINCT r.sku, r.ozon_sku, r.posting_key
    FROM real_return_rows r
),
return_finance_operations AS (
    SELECT
        f.resolved_sku AS sku,
        SUM(f.amount)::numeric AS signed_return_operations
    FROM finance_period f
    JOIN real_return_keys r
      ON r.sku = f.resolved_sku
     AND r.ozon_sku IS NOT DISTINCT FROM f.sku
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
    GROUP BY f.resolved_sku
),
components AS (
    SELECT
        p.sku,
        q.from_date,
        q.to_date,
        COALESCE(d.delivered_units, 0)::integer AS delivered_units,
        COALESCE(r.returned_units, 0)::integer AS returned_units,
        (
            COALESCE(d.delivered_units, 0)
            - COALESCE(r.returned_units, 0)
        )::integer AS net_sold_units,
        COALESCE(d.gross_sales, 0)::numeric AS gross_sales,
        (-COALESCE(d.signed_commission, 0))::numeric AS commission,
        (-COALESCE(a.signed_acquiring, 0))::numeric AS acquiring,
        (-COALESCE(s.signed_services, 0))::numeric AS services,
        (-COALESCE(ro.signed_return_operations, 0))::numeric AS return_operations,
        CASE
            WHEN p.cost_price IS NULL
             AND COALESCE(d.delivered_units, 0) <> COALESCE(r.returned_units, 0)
                THEN NULL::numeric
            ELSE (
                COALESCE(p.cost_price, 0)
                * (
                    COALESCE(d.delivered_units, 0)
                    - COALESCE(r.returned_units, 0)
                )
            )::numeric
        END AS cogs,
        (
            COALESCE(g.missing_required_fields, 0) = 0
            AND COALESCE(d.missing_delivery_quantity, 0) = 0
            AND COALESCE(r.missing_return_quantity, 0) = 0
        ) AS source_complete
    FROM product_scope p
    CROSS JOIN params q
    LEFT JOIN capture_gaps g ON g.sku = p.sku
    LEFT JOIN delivered d ON d.sku = p.sku
    LEFT JOIN sale_services s ON s.sku = p.sku
    LEFT JOIN acquiring_operations a ON a.sku = p.sku
    LEFT JOIN real_returns r ON r.sku = p.sku
    LEFT JOIN return_finance_operations ro ON ro.sku = p.sku
),
calculated AS (
    SELECT
        c.*,
        CASE
            WHEN NOT c.source_complete OR c.cogs IS NULL THEN NULL::numeric
            ELSE (
                c.gross_sales
                - c.commission
                - c.acquiring
                - c.services
                - c.return_operations
                - c.cogs
            )::numeric
        END AS calculated_pbt
    FROM components c
)
SELECT
    c.sku,
    c.from_date,
    c.to_date,
    c.delivered_units,
    c.returned_units,
    c.net_sold_units,
    c.gross_sales,
    c.commission,
    c.acquiring,
    c.services,
    c.return_operations,
    c.cogs,
    c.calculated_pbt AS profit_before_tax,
    CASE
        WHEN c.calculated_pbt IS NULL OR c.net_sold_units <= 0 THEN NULL::numeric
        ELSE ROUND(c.calculated_pbt / c.net_sold_units, 4)
    END AS profit_per_unit,
    CASE
        WHEN c.calculated_pbt IS NULL
          OR c.gross_sales <= 0
          OR c.net_sold_units <= 0 THEN NULL::numeric
        ELSE TRUNC(c.calculated_pbt / c.gross_sales * 100, 2)
    END AS margin_before_tax
FROM calculated c
ORDER BY c.sku
$function$;

ALTER FUNCTION mcp_read.product_period_economics(date, date) OWNER TO efa;

REVOKE ALL ON FUNCTION mcp_read.product_period_economics(date, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION mcp_read.product_period_economics(date, date) TO efa_mcp_reader;

COMMENT ON FUNCTION mcp_read.product_period_economics(date, date) IS
    'Read-only Ozon financial-period economics for an inclusive Europe/Moscow date range up to 93 days; current non-historic COGS; CPC excluded.';

COMMIT;
