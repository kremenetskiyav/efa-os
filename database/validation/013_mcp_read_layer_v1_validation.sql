-- Post-deployment validation for migration 013_mcp_read_layer_v1.sql.
-- Run manually only after the migration is explicitly approved and applied.
-- The validation transaction is read-only and leaves no database changes.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    missing_objects text;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_namespace WHERE nspname = 'mcp_read'
    ) THEN
        RAISE EXCEPTION 'Missing schema mcp_read';
    END IF;

    WITH expected(view_name) AS (
        VALUES
            ('product_overview'),
            ('product_price_history'),
            ('product_stock_history'),
            ('product_daily_performance'),
            ('product_region_logistics'),
            ('product_promotion_state'),
            ('product_cpc_daily')
    )
    SELECT STRING_AGG(e.view_name, ', ' ORDER BY e.view_name)
      INTO missing_objects
      FROM expected e
     WHERE NOT EXISTS (
        SELECT 1
          FROM information_schema.views v
         WHERE v.table_schema = 'mcp_read'
           AND v.table_name = e.view_name
     );

    IF missing_objects IS NOT NULL THEN
        RAISE EXCEPTION 'Missing mcp_read views: %', missing_objects;
    END IF;
END $$;

DO $$
DECLARE
    forbidden_columns text;
BEGIN
    SELECT STRING_AGG(c.table_name || '.' || c.column_name, ', ' ORDER BY c.table_name, c.column_name)
      INTO forbidden_columns
      FROM information_schema.columns c
     WHERE c.table_schema = 'mcp_read'
       AND LOWER(c.column_name) IN (
           'order_number',
           'order_id',
           'posting_number',
           'posting_key',
           'campaign_id',
           'run_id',
           'report_uuid',
           'collection_ref',
           'poll_lease_token',
           'error_message'
       );

    IF forbidden_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Forbidden MCP columns found: %', forbidden_columns;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT offer_id FROM mcp_read.product_overview
        GROUP BY offer_id HAVING COUNT(*) <> 1
    ) THEN RAISE EXCEPTION 'Duplicate product_overview grain'; END IF;

    IF EXISTS (
        SELECT offer_id, observed_at FROM mcp_read.product_price_history
        GROUP BY offer_id, observed_at HAVING COUNT(*) <> 1
    ) THEN RAISE EXCEPTION 'Duplicate product_price_history grain'; END IF;

    IF EXISTS (
        SELECT offer_id, snapshot_at FROM mcp_read.product_stock_history
        GROUP BY offer_id, snapshot_at HAVING COUNT(*) <> 1
    ) THEN RAISE EXCEPTION 'Duplicate product_stock_history grain'; END IF;

    IF EXISTS (
        SELECT offer_id, business_date FROM mcp_read.product_daily_performance
        GROUP BY offer_id, business_date HAVING COUNT(*) <> 1
    ) THEN RAISE EXCEPTION 'Duplicate product_daily_performance grain'; END IF;

    IF EXISTS (
        SELECT offer_id, cluster_from, cluster_to FROM mcp_read.product_region_logistics
        GROUP BY offer_id, cluster_from, cluster_to HAVING COUNT(*) <> 1
    ) THEN RAISE EXCEPTION 'Duplicate product_region_logistics grain'; END IF;

    IF EXISTS (
        SELECT offer_id, ozon_promotion_id, participation_state
        FROM mcp_read.product_promotion_state
        GROUP BY offer_id, ozon_promotion_id, participation_state
        HAVING COUNT(*) <> 1
    ) THEN RAISE EXCEPTION 'Duplicate product_promotion_state grain'; END IF;

    IF EXISTS (
        SELECT business_date, data_scope, offer_id FROM mcp_read.product_cpc_daily
        GROUP BY business_date, data_scope, offer_id HAVING COUNT(*) <> 1
    ) THEN RAISE EXCEPTION 'Duplicate product_cpc_daily grain'; END IF;
END $$;

DO $$
BEGIN
    IF (SELECT COUNT(*) FROM mcp_read.product_overview)
       <> (SELECT COUNT(*) FROM public.products) THEN
        RAISE EXCEPTION 'product_overview must contain exactly one row per products.offer_id';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM mcp_read.product_overview o
          LEFT JOIN public.products p ON p.offer_id = o.offer_id
         WHERE p.offer_id IS NULL
    ) THEN
        RAISE EXCEPTION 'product_overview contains an unknown offer_id';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM mcp_read.product_stock_history h
         WHERE h.is_latest
         GROUP BY h.offer_id
        HAVING COUNT(*) <> 1
    ) THEN
        RAISE EXCEPTION 'Each offer with stock history must have exactly one latest stock row';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM mcp_read.product_overview o
          JOIN (
              SELECT offer_id, MAX(snapshot_at) AS snapshot_at
              FROM public.stock_history
              GROUP BY offer_id
          ) expected ON expected.offer_id = o.offer_id
         WHERE o.stock_snapshot_at IS DISTINCT FROM expected.snapshot_at
    ) THEN
        RAISE EXCEPTION 'product_overview does not use per-offer latest stock';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM mcp_read.product_overview o
         WHERE o.stock_snapshot_at IS NULL
           AND (o.total_present IS NOT NULL OR o.total_reserved IS NOT NULL OR o.out_of_stock IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'Missing stock snapshot was converted to a synthetic value';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM mcp_read.product_overview o
          JOIN LATERAL (
              SELECT h.price, h.updated_from_ozon
              FROM public.ozon_price_history h
              WHERE h.offer_id = o.offer_id AND h.price IS NOT NULL
              ORDER BY h.updated_from_ozon DESC, h.id DESC
              LIMIT 1
          ) expected ON TRUE
         WHERE o.current_price IS DISTINCT FROM expected.price
            OR o.price_observed_at IS DISTINCT FROM expected.updated_from_ozon
    ) THEN
        RAISE EXCEPTION 'Current price differs from the latest price-history observation';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM public.cpc_collection_runs r
          LEFT JOIN mcp_read.product_cpc_daily c
            ON c.business_date = r.business_date
           AND c.data_scope = 'ACCOUNT'
           AND c.offer_id IS NULL
         WHERE r.lifecycle_state = 'SUCCESS_ZERO'
           AND (
               c.business_date IS NULL
               OR c.collection_status IS DISTINCT FROM 'SUCCESS_ZERO'
               OR c.views IS DISTINCT FROM 0
               OR c.clicks IS DISTINCT FROM 0
               OR c.spend IS DISTINCT FROM 0
               OR c.attributed_orders IS DISTINCT FROM 0
               OR c.attributed_revenue IS DISTINCT FROM 0
               OR c.product_gmv IS DISTINCT FROM 0
           )
    ) THEN
        RAISE EXCEPTION 'CPC SUCCESS_ZERO is missing or not represented as an explicit zero account fact';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.cpc_collection_runs r
          JOIN mcp_read.product_cpc_daily c
            ON c.business_date = r.business_date
           AND c.data_scope = 'PRODUCT'
         WHERE r.lifecycle_state = 'SUCCESS_ZERO'
    ) THEN
        RAISE EXCEPTION 'CPC SUCCESS_ZERO created synthetic product rows';
    END IF;
END $$;

DO $$
DECLARE
    expected_matches bigint;
    actual_matches bigint;
    expected_revenue numeric;
    actual_revenue numeric;
    expected_payout numeric;
    actual_payout numeric;
BEGIN
    IF EXISTS (
        SELECT f.posting_key
          FROM public.vw_orders_profit_final f
         GROUP BY f.posting_key
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'vw_orders_profit_final is not unique by its finance join key';
    END IF;

    WITH delivered_lines AS (
        SELECT
            p.posting_number,
            p.sku,
            REGEXP_REPLACE(p.posting_number, '-[0-9]+$', '') AS finance_join_key
        FROM public.postings p
        WHERE p.status = 'delivered'
          AND p.quantity > 0
          AND p.offer_id IS NOT NULL
          AND p.delivering_date IS NOT NULL
        GROUP BY p.posting_number, p.sku
    ), keyed AS (
        SELECT
            d.*,
            COUNT(*) OVER (PARTITION BY d.finance_join_key) AS line_count
        FROM delivered_lines d
    )
    SELECT
        COUNT(*),
        SUM(f.revenue),
        SUM(f.payout)
      INTO expected_matches, expected_revenue, expected_payout
      FROM keyed d
      JOIN public.vw_orders_profit_final f ON f.posting_key = d.finance_join_key
     WHERE d.line_count = 1;

    SELECT
        COALESCE(SUM(p.finance_matched_lines), 0),
        SUM(p.confirmed_revenue),
        SUM(p.payout)
      INTO actual_matches, actual_revenue, actual_payout
      FROM mcp_read.product_daily_performance p;

    IF actual_matches IS DISTINCT FROM expected_matches
       OR actual_revenue IS DISTINCT FROM expected_revenue
       OR actual_payout IS DISTINCT FROM expected_payout THEN
        RAISE EXCEPTION
            'Finance aggregation multiplied or lost data: rows expected %, got %; revenue expected %, got %; payout expected %, got %',
            expected_matches, actual_matches,
            expected_revenue, actual_revenue,
            expected_payout, actual_payout;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM mcp_read.product_daily_performance
         WHERE ordered_units < 0
            OR delivered_units < 0
            OR return_events < 0
            OR returned_units < 0
            OR finance_matched_delivered_units < 0
            OR multi_line_excluded_units < 0
            OR unmatched_finance_units < 0
    ) THEN RAISE EXCEPTION 'Negative performance counts found'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_daily_performance
         WHERE confirmed_revenue = 0 AND profit_margin_percent IS NOT NULL
    ) THEN RAISE EXCEPTION 'Margin must be NULL when confirmed revenue is zero'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_daily_performance
         WHERE confirmed_revenue IS NOT NULL
           AND confirmed_revenue <> 0
           AND profit_before_tax IS NOT NULL
           AND ABS(profit_margin_percent - ROUND(profit_before_tax / confirmed_revenue * 100, 2)) > 0.01
    ) THEN RAISE EXCEPTION 'Profit margin formula mismatch'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_stock_history
         WHERE fbo_present < 0 OR fbs_present < 0 OR rfbs_present < 0
            OR fbo_reserved < 0 OR fbs_reserved < 0 OR rfbs_reserved < 0
            OR total_present < 0 OR total_reserved < 0
    ) THEN RAISE EXCEPTION 'Negative stock values found'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_cpc_daily
         WHERE campaigns_count < 0 OR active_campaigns_count < 0
            OR views < 0 OR clicks < 0 OR spend < 0
            OR attributed_orders < 0 OR attributed_revenue < 0 OR product_gmv < 0
    ) THEN RAISE EXCEPTION 'Negative CPC values found'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_cpc_daily
         WHERE (views = 0 AND ctr_percent IS NOT NULL)
            OR (views <> 0 AND ctr_percent IS DISTINCT FROM ROUND(clicks::numeric / views * 100, 2))
            OR (attributed_revenue = 0 AND drr_percent IS NOT NULL)
            OR (attributed_revenue <> 0 AND drr_percent IS DISTINCT FROM ROUND(spend / attributed_revenue * 100, 2))
            OR (product_gmv = 0 AND general_drr_percent IS NOT NULL)
            OR (product_gmv <> 0 AND general_drr_percent IS DISTINCT FROM ROUND(spend / product_gmv * 100, 2))
    ) THEN RAISE EXCEPTION 'CPC aggregate ratio formula mismatch'; END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM mcp_read.product_price_history WHERE observed_at IS NULL
    ) THEN RAISE EXCEPTION 'Price history freshness timestamp is NULL'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_stock_history WHERE snapshot_at IS NULL
    ) THEN RAISE EXCEPTION 'Stock history freshness timestamp is NULL'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_promotion_state WHERE observed_at IS NULL
    ) THEN RAISE EXCEPTION 'Promotion freshness timestamp is NULL'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_cpc_daily WHERE observed_at IS NULL
    ) THEN RAISE EXCEPTION 'CPC freshness timestamp is NULL'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_overview
         WHERE current_price IS NOT NULL AND price_observed_at IS NULL
    ) THEN RAISE EXCEPTION 'Current price has no observation timestamp'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_region_logistics
         WHERE data_from IS NULL OR data_through IS NULL
    ) THEN RAISE EXCEPTION 'Regional logistics freshness bounds are NULL'; END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_daily_performance
         WHERE (postings_collection_status IS NOT NULL AND postings_collected_at IS NULL)
            OR (returns_collection_status IS NOT NULL AND returns_collected_at IS NULL)
            OR (finance_collection_status IS NOT NULL AND finance_collected_at IS NULL)
    ) THEN RAISE EXCEPTION 'Operational collection status has no freshness timestamp'; END IF;
END $$;

SELECT 'product_overview' AS view_name, COUNT(*) AS row_count FROM mcp_read.product_overview
UNION ALL SELECT 'product_price_history', COUNT(*) FROM mcp_read.product_price_history
UNION ALL SELECT 'product_stock_history', COUNT(*) FROM mcp_read.product_stock_history
UNION ALL SELECT 'product_daily_performance', COUNT(*) FROM mcp_read.product_daily_performance
UNION ALL SELECT 'product_region_logistics', COUNT(*) FROM mcp_read.product_region_logistics
UNION ALL SELECT 'product_promotion_state', COUNT(*) FROM mcp_read.product_promotion_state
UNION ALL SELECT 'product_cpc_daily', COUNT(*) FROM mcp_read.product_cpc_daily
ORDER BY view_name;

ROLLBACK;
