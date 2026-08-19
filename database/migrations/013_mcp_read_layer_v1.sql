-- MCP Read Layer v1
--
-- Creates a curated, read-only data contract for AI/MCP consumers.
-- This migration creates no roles, passwords, grants, or direct access to
-- public schema objects. Apply only after review and explicit approval.

BEGIN;

CREATE SCHEMA mcp_read;

COMMENT ON SCHEMA mcp_read IS
    'Curated EFA OS read contract for AI/MCP consumers; no raw operational identifiers.';

CREATE VIEW mcp_read.product_price_history
WITH (security_barrier = true)
AS
WITH deduplicated AS (
    SELECT DISTINCT ON (h.offer_id, h.updated_from_ozon)
        h.offer_id,
        h.updated_from_ozon AS observed_at,
        h.price,
        h.min_price,
        h.marketing_price,
        h.marketing_seller_price,
        h.id
    FROM public.ozon_price_history h
    WHERE h.price IS NOT NULL
    ORDER BY h.offer_id, h.updated_from_ozon, h.id DESC
), sequenced AS (
    SELECT
        d.offer_id,
        d.observed_at,
        d.price,
        LAG(d.price) OVER (
            PARTITION BY d.offer_id
            ORDER BY d.observed_at, d.id
        ) AS previous_price,
        d.min_price,
        d.marketing_price,
        d.marketing_seller_price,
        ROW_NUMBER() OVER (
            PARTITION BY d.offer_id
            ORDER BY d.observed_at DESC, d.id DESC
        ) = 1 AS is_latest
    FROM deduplicated d
)
SELECT
    s.offer_id,
    s.observed_at,
    s.price,
    s.previous_price,
    CASE
        WHEN s.previous_price IS NULL THEN NULL
        ELSE s.price - s.previous_price
    END AS absolute_change,
    CASE
        WHEN s.previous_price IS NULL OR s.previous_price = 0 THEN NULL
        ELSE ROUND((s.price - s.previous_price) / s.previous_price * 100, 2)
    END AS change_percent,
    s.min_price,
    s.marketing_price,
    s.marketing_seller_price,
    s.is_latest
FROM sequenced s;

COMMENT ON VIEW mcp_read.product_price_history IS
    'Grain: one row per offer_id and price observation timestamp; source: ozon_price_history.';

CREATE VIEW mcp_read.product_stock_history
WITH (security_barrier = true)
AS
WITH summarized AS (
    SELECT
        h.offer_id,
        h.snapshot_at,
        COUNT(*) AS source_rows,
        COUNT(DISTINCT h.type) AS source_types,
        MAX(h.present) FILTER (WHERE h.type = 'fbo') AS fbo_present,
        MAX(h.reserved) FILTER (WHERE h.type = 'fbo') AS fbo_reserved,
        MAX(h.present) FILTER (WHERE h.type = 'fbs') AS fbs_present,
        MAX(h.reserved) FILTER (WHERE h.type = 'fbs') AS fbs_reserved,
        MAX(h.present) FILTER (WHERE h.type = 'rfbs') AS rfbs_present,
        MAX(h.reserved) FILTER (WHERE h.type = 'rfbs') AS rfbs_reserved
    FROM public.stock_history h
    GROUP BY h.offer_id, h.snapshot_at
), totals AS (
    SELECT
        s.*,
        CASE
            WHEN s.source_rows = 3 AND s.source_types = 3
                THEN s.fbo_present + s.fbs_present + s.rfbs_present
            ELSE NULL
        END AS total_present,
        CASE
            WHEN s.source_rows = 3 AND s.source_types = 3
                THEN s.fbo_reserved + s.fbs_reserved + s.rfbs_reserved
            ELSE NULL
        END AS total_reserved,
        CASE
            WHEN s.source_rows = 3 AND s.source_types = 3 THEN 'VALID'
            WHEN s.source_types < 3 THEN 'PARTIAL_MISSING_STOCK_TYPES'
            ELSE 'REVIEW_DUPLICATE_STOCK_TYPES'
        END AS data_quality_status
    FROM summarized s
), sequenced AS (
    SELECT
        t.*,
        LAG(t.total_present) OVER (
            PARTITION BY t.offer_id ORDER BY t.snapshot_at
        ) AS previous_total_present,
        LAG(t.total_reserved) OVER (
            PARTITION BY t.offer_id ORDER BY t.snapshot_at
        ) AS previous_total_reserved,
        ROW_NUMBER() OVER (
            PARTITION BY t.offer_id ORDER BY t.snapshot_at DESC
        ) = 1 AS is_latest
    FROM totals t
)
SELECT
    s.offer_id,
    s.snapshot_at,
    s.fbo_present,
    s.fbo_reserved,
    s.fbs_present,
    s.fbs_reserved,
    s.rfbs_present,
    s.rfbs_reserved,
    s.total_present,
    s.total_reserved,
    s.previous_total_present,
    s.previous_total_reserved,
    CASE
        WHEN s.total_present IS NULL OR s.previous_total_present IS NULL THEN NULL
        ELSE s.total_present - s.previous_total_present
    END AS total_present_change,
    CASE
        WHEN s.total_reserved IS NULL OR s.previous_total_reserved IS NULL THEN NULL
        ELSE s.total_reserved - s.previous_total_reserved
    END AS total_reserved_change,
    s.data_quality_status,
    s.is_latest
FROM sequenced s;

COMMENT ON VIEW mcp_read.product_stock_history IS
    'Grain: one row per offer_id and stock snapshot timestamp; incomplete snapshots remain NULL, never synthetic zero.';

CREATE VIEW mcp_read.product_daily_performance
WITH (security_barrier = true)
AS
WITH demand AS (
    SELECT
        d.offer_id,
        d.business_date,
        d.ordered_units,
        d.ordered_revenue,
        d.collected_at AS demand_collected_at,
        d.data_quality_status AS demand_quality_status
    FROM public.seller_product_demand_daily d
), delivered_lines AS (
    SELECT
        p.posting_number,
        p.sku,
        MAX(p.offer_id) AS offer_id,
        MAX(p.quantity) AS quantity,
        MAX(p.delivering_date) AS delivery_at,
        (MAX(p.delivering_date) AT TIME ZONE 'Europe/Moscow')::date AS business_date,
        REGEXP_REPLACE(p.posting_number, '-[0-9]+$', '') AS finance_join_key
    FROM public.postings p
    WHERE p.status = 'delivered'
      AND p.quantity > 0
      AND p.offer_id IS NOT NULL
      AND p.delivering_date IS NOT NULL
    GROUP BY p.posting_number, p.sku
), keyed_deliveries AS (
    SELECT
        d.*,
        COUNT(*) OVER (PARTITION BY d.finance_join_key) AS finance_join_line_count
    FROM delivered_lines d
), deliveries AS (
    SELECT
        d.offer_id,
        d.business_date,
        SUM(d.quantity)::integer AS delivered_units,
        COUNT(*)::integer AS delivered_lines
    FROM keyed_deliveries d
    GROUP BY d.offer_id, d.business_date
), finance_matches AS (
    SELECT
        d.offer_id,
        d.business_date,
        d.quantity,
        d.finance_join_line_count,
        f.posting_key IS NOT NULL AS has_finance_match,
        f.revenue,
        f.commission,
        f.logistics,
        f.other_expenses,
        f.payout,
        p.cost_price
    FROM keyed_deliveries d
    LEFT JOIN public.vw_orders_profit_final f
      ON f.posting_key = d.finance_join_key
     AND d.finance_join_line_count = 1
    LEFT JOIN public.products p ON p.offer_id = d.offer_id
), finance AS (
    SELECT
        f.offer_id,
        f.business_date,
        COUNT(*) FILTER (
            WHERE f.finance_join_line_count = 1 AND f.has_finance_match
        )::integer AS finance_matched_lines,
        SUM(f.quantity) FILTER (
            WHERE f.finance_join_line_count = 1 AND f.has_finance_match
        )::integer AS finance_matched_delivered_units,
        COALESCE(SUM(f.quantity) FILTER (
            WHERE f.finance_join_line_count > 1
        ), 0)::integer AS multi_line_excluded_units,
        COALESCE(SUM(f.quantity) FILTER (
            WHERE f.finance_join_line_count = 1 AND NOT f.has_finance_match
        ), 0)::integer AS unmatched_finance_units,
        SUM(f.revenue) FILTER (
            WHERE f.finance_join_line_count = 1 AND f.has_finance_match
        ) AS confirmed_revenue,
        SUM(ABS(f.commission)) FILTER (
            WHERE f.finance_join_line_count = 1 AND f.has_finance_match
        ) AS commission_expense,
        SUM(ABS(f.logistics)) FILTER (
            WHERE f.finance_join_line_count = 1 AND f.has_finance_match
        ) AS logistics_expense,
        SUM(ABS(f.other_expenses)) FILTER (
            WHERE f.finance_join_line_count = 1 AND f.has_finance_match
        ) AS other_expenses,
        CASE
            WHEN COUNT(*) FILTER (
                WHERE f.finance_join_line_count = 1
                  AND f.has_finance_match
                  AND f.cost_price IS NULL
            ) > 0 THEN NULL
            ELSE SUM(f.cost_price * f.quantity) FILTER (
                WHERE f.finance_join_line_count = 1 AND f.has_finance_match
            )
        END AS cost_of_goods,
        SUM(f.payout) FILTER (
            WHERE f.finance_join_line_count = 1 AND f.has_finance_match
        ) AS payout,
        CASE
            WHEN COUNT(*) FILTER (
                WHERE f.finance_join_line_count = 1
                  AND f.has_finance_match
                  AND f.cost_price IS NULL
            ) > 0 THEN NULL
            ELSE SUM(
                f.payout + f.other_expenses - f.cost_price * f.quantity
            ) FILTER (
                WHERE f.finance_join_line_count = 1 AND f.has_finance_match
            )
        END AS profit_before_tax,
        COUNT(*) FILTER (
            WHERE f.finance_join_line_count = 1
              AND f.has_finance_match
              AND f.cost_price IS NULL
        )::integer AS missing_current_cost_lines
    FROM finance_matches f
    GROUP BY f.offer_id, f.business_date
), returned AS (
    SELECT
        r.offer_id,
        r.logistic_return_date::date AS business_date,
        COUNT(*)::integer AS return_events,
        SUM(r.quantity)::integer AS returned_units
    FROM public.returns r
    WHERE r.offer_id IS NOT NULL
      AND r.logistic_return_date IS NOT NULL
    GROUP BY r.offer_id, r.logistic_return_date::date
), operational AS (
    SELECT
        o.business_date,
        MAX(o.status) FILTER (WHERE o.source = 'POSTINGS') AS postings_collection_status,
        MAX(o.completed_at) FILTER (WHERE o.source = 'POSTINGS') AS postings_collected_at,
        MAX(o.status) FILTER (WHERE o.source = 'RETURNS') AS returns_collection_status,
        MAX(o.completed_at) FILTER (WHERE o.source = 'RETURNS') AS returns_collected_at,
        MAX(o.status) FILTER (WHERE o.source = 'FINANCE') AS finance_collection_status,
        MAX(o.completed_at) FILTER (WHERE o.source = 'FINANCE') AS finance_collected_at
    FROM public.operational_collection_runs o
    GROUP BY o.business_date
), business_dates AS (
    SELECT d.business_date FROM demand d
    UNION
    SELECT d.business_date FROM deliveries d
    UNION
    SELECT r.business_date FROM returned r
    UNION
    SELECT o.business_date FROM operational o
), product_dates AS (
    SELECT p.offer_id, d.business_date
    FROM public.products p
    CROSS JOIN business_dates d
), combined AS (
    SELECT
        k.offer_id,
        k.business_date,
        d.ordered_units,
        d.ordered_revenue,
        d.demand_collected_at,
        d.demand_quality_status,
        CASE
            WHEN x.delivered_units IS NOT NULL THEN x.delivered_units
            WHEN o.postings_collection_status IN ('SUCCESS', 'SUCCESS_ZERO') THEN 0
            ELSE NULL
        END AS delivered_units,
        CASE
            WHEN r.return_events IS NOT NULL THEN r.return_events
            WHEN o.returns_collection_status IN ('SUCCESS', 'SUCCESS_ZERO') THEN 0
            ELSE NULL
        END AS return_events,
        CASE
            WHEN r.returned_units IS NOT NULL THEN r.returned_units
            WHEN o.returns_collection_status IN ('SUCCESS', 'SUCCESS_ZERO') THEN 0
            ELSE NULL
        END AS returned_units,
        f.finance_matched_lines,
        f.finance_matched_delivered_units,
        COALESCE(f.multi_line_excluded_units, 0) AS multi_line_excluded_units,
        COALESCE(f.unmatched_finance_units, 0) AS unmatched_finance_units,
        f.confirmed_revenue,
        f.commission_expense,
        f.logistics_expense,
        f.other_expenses,
        f.cost_of_goods,
        f.payout,
        f.profit_before_tax,
        COALESCE(f.missing_current_cost_lines, 0) AS missing_current_cost_lines,
        o.postings_collection_status,
        o.postings_collected_at,
        o.returns_collection_status,
        o.returns_collected_at,
        o.finance_collection_status,
        o.finance_collected_at
    FROM product_dates k
    LEFT JOIN demand d
      ON d.offer_id = k.offer_id AND d.business_date = k.business_date
    LEFT JOIN deliveries x
      ON x.offer_id = k.offer_id AND x.business_date = k.business_date
    LEFT JOIN returned r
      ON r.offer_id = k.offer_id AND r.business_date = k.business_date
    LEFT JOIN finance f
      ON f.offer_id = k.offer_id AND f.business_date = k.business_date
    LEFT JOIN operational o ON o.business_date = k.business_date
)
SELECT
    c.offer_id,
    c.business_date,
    c.ordered_units,
    c.ordered_revenue,
    c.demand_collected_at,
    c.demand_quality_status,
    c.delivered_units,
    c.return_events,
    c.returned_units,
    c.finance_matched_lines,
    c.finance_matched_delivered_units,
    c.multi_line_excluded_units,
    c.unmatched_finance_units,
    c.confirmed_revenue,
    c.commission_expense,
    c.logistics_expense,
    c.other_expenses,
    c.cost_of_goods,
    c.payout,
    c.profit_before_tax,
    CASE
        WHEN c.profit_before_tax IS NULL
          OR c.finance_matched_delivered_units IS NULL
          OR c.finance_matched_delivered_units = 0 THEN NULL
        ELSE ROUND(c.profit_before_tax / c.finance_matched_delivered_units, 2)
    END AS profit_per_unit,
    CASE
        WHEN c.profit_before_tax IS NULL
          OR c.confirmed_revenue IS NULL
          OR c.confirmed_revenue = 0 THEN NULL
        ELSE ROUND(c.profit_before_tax / c.confirmed_revenue * 100, 2)
    END AS profit_margin_percent,
    CASE
        WHEN c.finance_matched_lines IS NULL THEN NULL
        WHEN c.missing_current_cost_lines > 0 THEN 'MISSING_CURRENT_COST'
        ELSE 'CURRENT_NOT_HISTORISED'
    END AS cost_basis,
    CASE
        WHEN c.delivered_units IS NULL THEN 'DELIVERY_SOURCE_NOT_CONFIRMED'
        WHEN c.delivered_units = 0 THEN 'NO_DELIVERIES'
        WHEN c.multi_line_excluded_units > 0 THEN 'PARTIAL_MULTI_LINE_EXCLUDED'
        WHEN c.unmatched_finance_units > 0 THEN 'PARTIAL_UNMATCHED_FINANCE'
        WHEN c.missing_current_cost_lines > 0 THEN 'MISSING_CURRENT_COST'
        WHEN c.finance_matched_delivered_units IS NULL THEN 'FINANCE_NOT_CONFIRMED'
        ELSE 'CONFIRMED_CURRENT_COST'
    END AS economics_quality_status,
    c.postings_collection_status,
    c.postings_collected_at,
    c.returns_collection_status,
    c.returns_collected_at,
    c.finance_collection_status,
    c.finance_collected_at
FROM combined c;

COMMENT ON VIEW mcp_read.product_daily_performance IS
    'Grain: one row per offer_id and Moscow business_date; ordered demand, delivery outcomes, returns, and confirmed delivery-date economics remain separate fields.';

CREATE VIEW mcp_read.product_region_logistics
WITH (security_barrier = true)
AS
WITH source_bounds AS (
    SELECT
        MIN(f.operation_date) AS data_from,
        MAX(f.operation_date) AS data_through
    FROM public.posting_logistics l
    JOIN public.postings p ON p.posting_number = l.posting_number
    JOIN public.finance_operations f ON f.posting_number = l.posting_number
    WHERE l.cluster_from IS NOT NULL
      AND l.cluster_to IS NOT NULL
      AND f.operation_type = 'OperationAgentDeliveredToCustomer'
      AND f.accruals_for_sale > 0
)
SELECT
    r.offer_id,
    r.cluster_from,
    r.cluster_to,
    r.orders_count,
    r.avg_logistics,
    r.baseline_logistics,
    r.logistics_delta,
    r.logistics_delta_pct AS logistics_delta_percent,
    r.avg_revenue,
    r.baseline_revenue,
    r.logistics_rate AS logistics_rate_percent,
    r.baseline_logistics_rate AS baseline_logistics_rate_percent,
    r.logistics_rate_delta_pp,
    r.confidence,
    b.data_from,
    b.data_through,
    'public_vw_product_region_analysis_v1'::text AS rule_version
FROM public.vw_product_region_analysis r
CROSS JOIN source_bounds b;

COMMENT ON VIEW mcp_read.product_region_logistics IS
    'Grain: one row per offer_id, cluster_from, and cluster_to; aggregate regional logistics only.';

CREATE VIEW mcp_read.product_promotion_state
WITH (security_barrier = true)
AS
WITH latest_successful_valid_run AS (
    SELECT r.run_id, r.collected_at
    FROM public.promotion_runs r
    WHERE r.status = 'success'
      AND r.mapping_status = 'valid'
    ORDER BY r.collected_at DESC, r.created_at DESC
    LIMIT 1
)
SELECT
    s.offer_id,
    s.action_id AS ozon_promotion_id,
    s.action_title AS promotion_title,
    s.action_type AS promotion_type,
    CASE s.source_list_type
        WHEN 'PARTICIPATING' THEN 'PARTICIPATING'
        WHEN 'CANDIDATE' THEN 'CANDIDATE'
        ELSE NULL
    END AS participation_state,
    s.add_mode,
    s.action_start_at AS starts_at,
    s.action_end_at AS ends_at,
    s.price AS observed_price,
    s.action_price AS promotion_price,
    s.max_action_price AS max_promotion_price,
    s.current_boost,
    s.min_boost,
    s.max_boost,
    r.collected_at AS observed_at,
    s.data_quality_status
FROM public.promotion_snapshots s
JOIN latest_successful_valid_run r ON r.run_id = s.run_id
WHERE s.offer_id IS NOT NULL
  AND s.data_quality_status = 'valid';

COMMENT ON VIEW mcp_read.product_promotion_state IS
    'Grain: one row per offer_id, Ozon promotion, and participation state from the latest successful valid run.';

CREATE VIEW mcp_read.product_cpc_daily
WITH (security_barrier = true)
AS
WITH runs AS (
    SELECT
        r.run_id,
        r.business_date,
        r.lifecycle_state,
        r.mapping_status,
        r.campaigns_count,
        r.collected_at,
        r.completed_at
    FROM public.cpc_collection_runs r
), account_metrics AS (
    SELECT
        d.run_id,
        COUNT(DISTINCT d.campaign_id) FILTER (
            WHERE d.data_quality_status = 'valid'
        )::bigint AS campaigns_count,
        COUNT(DISTINCT d.campaign_id) FILTER (
            WHERE d.data_quality_status = 'valid'
              AND d.campaign_state = 'CAMPAIGN_STATE_ACTIVE'
        )::bigint AS active_campaigns_count,
        SUM(d.views) FILTER (WHERE d.data_quality_status = 'valid')::bigint AS views,
        SUM(d.clicks) FILTER (WHERE d.data_quality_status = 'valid')::bigint AS clicks,
        SUM(d.money_spent) FILTER (WHERE d.data_quality_status = 'valid') AS spend,
        SUM(d.orders) FILTER (WHERE d.data_quality_status = 'valid')::bigint AS attributed_orders,
        SUM(d.orders_money) FILTER (WHERE d.data_quality_status = 'valid') AS attributed_revenue,
        SUM(d.product_gmv) FILTER (WHERE d.data_quality_status = 'valid') AS product_gmv,
        SUM(d.avg_bid * d.clicks) FILTER (
            WHERE d.data_quality_status = 'valid'
        ) AS weighted_bid_total,
        COUNT(*) FILTER (WHERE d.data_quality_status <> 'valid') AS nonvalid_rows
    FROM public.cpc_advertising_daily d
    GROUP BY d.run_id
), product_metrics AS (
    SELECT
        d.run_id,
        d.offer_id,
        COUNT(DISTINCT d.campaign_id) FILTER (
            WHERE d.data_quality_status = 'valid'
        )::bigint AS campaigns_count,
        COUNT(DISTINCT d.campaign_id) FILTER (
            WHERE d.data_quality_status = 'valid'
              AND d.campaign_state = 'CAMPAIGN_STATE_ACTIVE'
        )::bigint AS active_campaigns_count,
        SUM(d.views) FILTER (WHERE d.data_quality_status = 'valid')::bigint AS views,
        SUM(d.clicks) FILTER (WHERE d.data_quality_status = 'valid')::bigint AS clicks,
        SUM(d.money_spent) FILTER (WHERE d.data_quality_status = 'valid') AS spend,
        SUM(d.orders) FILTER (WHERE d.data_quality_status = 'valid')::bigint AS attributed_orders,
        SUM(d.orders_money) FILTER (WHERE d.data_quality_status = 'valid') AS attributed_revenue,
        SUM(d.product_gmv) FILTER (WHERE d.data_quality_status = 'valid') AS product_gmv,
        SUM(d.avg_bid * d.clicks) FILTER (
            WHERE d.data_quality_status = 'valid'
        ) AS weighted_bid_total,
        COUNT(*) FILTER (WHERE d.data_quality_status <> 'valid') AS nonvalid_rows
    FROM public.cpc_advertising_daily d
    WHERE d.offer_id IS NOT NULL
    GROUP BY d.run_id, d.offer_id
), account_rows AS (
    SELECT
        r.business_date,
        'ACCOUNT'::text AS data_scope,
        NULL::text AS offer_id,
        CASE
            WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN r.campaigns_count::bigint
            ELSE a.campaigns_count
        END AS campaigns_count,
        CASE
            WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN 0::bigint
            ELSE a.active_campaigns_count
        END AS active_campaigns_count,
        CASE WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN 0::bigint ELSE a.views END AS views,
        CASE WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN 0::bigint ELSE a.clicks END AS clicks,
        CASE WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN 0::numeric ELSE a.spend END AS spend,
        CASE WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN 0::bigint ELSE a.attributed_orders END AS attributed_orders,
        CASE WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN 0::numeric ELSE a.attributed_revenue END AS attributed_revenue,
        CASE WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN 0::numeric ELSE a.product_gmv END AS product_gmv,
        CASE
            WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN NULL::numeric
            WHEN a.clicks IS NULL OR a.clicks = 0 THEN NULL::numeric
            ELSE ROUND(a.weighted_bid_total / a.clicks, 2)
        END AS average_bid,
        CASE
            WHEN r.lifecycle_state = 'SUCCESS_ZERO' THEN r.mapping_status
            WHEN COALESCE(a.nonvalid_rows, 0) > 0 THEN 'review'
            ELSE r.mapping_status
        END AS data_quality_status,
        r.lifecycle_state AS collection_status,
        COALESCE(r.completed_at, r.collected_at) AS observed_at
    FROM runs r
    LEFT JOIN account_metrics a ON a.run_id = r.run_id
), product_rows AS (
    SELECT
        r.business_date,
        'PRODUCT'::text AS data_scope,
        p.offer_id,
        p.campaigns_count,
        p.active_campaigns_count,
        p.views,
        p.clicks,
        p.spend,
        p.attributed_orders,
        p.attributed_revenue,
        p.product_gmv,
        CASE
            WHEN p.clicks IS NULL OR p.clicks = 0 THEN NULL::numeric
            ELSE ROUND(p.weighted_bid_total / p.clicks, 2)
        END AS average_bid,
        CASE WHEN p.nonvalid_rows > 0 THEN 'review' ELSE 'valid' END AS data_quality_status,
        r.lifecycle_state AS collection_status,
        COALESCE(r.completed_at, r.collected_at) AS observed_at
    FROM runs r
    JOIN product_metrics p ON p.run_id = r.run_id
    WHERE r.lifecycle_state = 'SUCCESS_NONZERO'
)
SELECT
    x.business_date,
    x.data_scope,
    x.offer_id,
    x.campaigns_count,
    x.active_campaigns_count,
    x.views,
    x.clicks,
    CASE
        WHEN x.views IS NULL OR x.views = 0 THEN NULL
        ELSE ROUND(x.clicks::numeric / x.views * 100, 2)
    END AS ctr_percent,
    x.spend,
    x.attributed_orders,
    x.attributed_revenue,
    x.product_gmv,
    CASE
        WHEN x.attributed_revenue IS NULL OR x.attributed_revenue = 0 THEN NULL
        ELSE ROUND(x.spend / x.attributed_revenue * 100, 2)
    END AS drr_percent,
    CASE
        WHEN x.product_gmv IS NULL OR x.product_gmv = 0 THEN NULL
        ELSE ROUND(x.spend / x.product_gmv * 100, 2)
    END AS general_drr_percent,
    x.average_bid,
    x.data_quality_status,
    x.collection_status,
    x.observed_at
FROM (
    SELECT * FROM account_rows
    UNION ALL
    SELECT * FROM product_rows
) x;

COMMENT ON VIEW mcp_read.product_cpc_daily IS
    'Grain: one row per business_date, data_scope, and nullable offer_id; SUCCESS_ZERO is an account-scope fact, never synthetic product data.';

CREATE VIEW mcp_read.product_overview
WITH (security_barrier = true)
AS
WITH deduplicated_prices AS (
    SELECT DISTINCT ON (h.offer_id, h.updated_from_ozon)
        h.offer_id,
        h.updated_from_ozon AS observed_at,
        h.price,
        h.id
    FROM public.ozon_price_history h
    WHERE h.price IS NOT NULL
    ORDER BY h.offer_id, h.updated_from_ozon, h.id DESC
), sequenced_prices AS (
    SELECT
        d.*,
        LAG(d.price) OVER (
            PARTITION BY d.offer_id ORDER BY d.observed_at, d.id
        ) AS previous_price,
        ROW_NUMBER() OVER (
            PARTITION BY d.offer_id ORDER BY d.observed_at DESC, d.id DESC
        ) AS latest_rank
    FROM deduplicated_prices d
), current_prices AS (
    SELECT
        s.offer_id,
        s.price AS current_price,
        s.observed_at AS price_observed_at
    FROM sequenced_prices s
    WHERE s.latest_rank = 1
), current_price_since AS (
    SELECT DISTINCT ON (s.offer_id)
        s.offer_id,
        s.observed_at AS current_price_since
    FROM sequenced_prices s
    WHERE s.price IS DISTINCT FROM s.previous_price
    ORDER BY s.offer_id, s.observed_at DESC
), price_freshness AS (
    SELECT MAX(r.collected_at) AS price_checked_at
    FROM public.price_collection_runs r
    WHERE r.status = 'success'
), stock_summaries AS (
    SELECT
        h.offer_id,
        h.snapshot_at,
        COUNT(*) AS source_rows,
        COUNT(DISTINCT h.type) AS source_types,
        MAX(h.present) FILTER (WHERE h.type = 'fbo') AS fbo_present,
        MAX(h.present) FILTER (WHERE h.type = 'fbs') AS fbs_present,
        MAX(h.present) FILTER (WHERE h.type = 'rfbs') AS rfbs_present,
        MAX(h.reserved) FILTER (WHERE h.type = 'fbo') AS fbo_reserved,
        MAX(h.reserved) FILTER (WHERE h.type = 'fbs') AS fbs_reserved,
        MAX(h.reserved) FILTER (WHERE h.type = 'rfbs') AS rfbs_reserved
    FROM public.stock_history h
    GROUP BY h.offer_id, h.snapshot_at
), latest_stock AS (
    SELECT DISTINCT ON (s.offer_id)
        s.offer_id,
        s.snapshot_at,
        s.fbo_present,
        s.fbs_present,
        s.rfbs_present,
        CASE
            WHEN s.source_rows = 3 AND s.source_types = 3
                THEN s.fbo_present + s.fbs_present + s.rfbs_present
            ELSE NULL
        END AS total_present,
        CASE
            WHEN s.source_rows = 3 AND s.source_types = 3
                THEN s.fbo_reserved + s.fbs_reserved + s.rfbs_reserved
            ELSE NULL
        END AS total_reserved,
        CASE
            WHEN s.source_rows = 3 AND s.source_types = 3 THEN 'VALID'
            WHEN s.source_types < 3 THEN 'PARTIAL_MISSING_STOCK_TYPES'
            ELSE 'REVIEW_DUPLICATE_STOCK_TYPES'
        END AS stock_data_quality_status
    FROM stock_summaries s
    ORDER BY s.offer_id, s.snapshot_at DESC
), delivered_lines AS (
    SELECT
        p.posting_number,
        p.sku,
        MAX(p.offer_id) AS offer_id,
        MAX(p.quantity) AS quantity,
        MAX(p.delivering_date) AS delivery_at,
        REGEXP_REPLACE(p.posting_number, '-[0-9]+$', '') AS finance_join_key
    FROM public.postings p
    WHERE p.status = 'delivered'
      AND p.quantity > 0
      AND p.offer_id IS NOT NULL
      AND p.delivering_date IS NOT NULL
    GROUP BY p.posting_number, p.sku
), keyed_deliveries AS (
    SELECT
        d.*,
        COUNT(*) OVER (PARTITION BY d.finance_join_key) AS finance_join_line_count
    FROM delivered_lines d
), current_price_economics AS (
    SELECT
        d.offer_id,
        COALESCE(SUM(d.quantity) FILTER (
            WHERE d.finance_join_line_count = 1
              AND f.posting_key IS NOT NULL
              AND d.delivery_at >= c.current_price_since
        ), 0)::integer AS confirmed_units_at_current_price,
        COALESCE(SUM(d.quantity) FILTER (
            WHERE d.finance_join_line_count > 1
              AND d.delivery_at >= c.current_price_since
        ), 0)::integer AS multi_line_units_excluded_at_current_price,
        COALESCE(SUM(d.quantity) FILTER (
            WHERE d.finance_join_line_count = 1
              AND f.posting_key IS NULL
              AND d.delivery_at >= c.current_price_since
        ), 0)::integer AS unmatched_finance_units_at_current_price
    FROM keyed_deliveries d
    JOIN current_price_since c ON c.offer_id = d.offer_id
    LEFT JOIN public.vw_orders_profit_final f
      ON f.posting_key = d.finance_join_key
     AND d.finance_join_line_count = 1
    GROUP BY d.offer_id
)
SELECT
    p.offer_id,
    p.sku,
    p.product_id AS ozon_product_id,
    p.name AS product_name,
    p.brand,
    COALESCE(p.archived, false) AS is_archived,
    p.updated_from_ozon AS product_observed_at,
    c.current_price,
    s.current_price_since,
    c.price_observed_at,
    f.price_checked_at,
    p.cost_price,
    CASE
        WHEN p.cost_price IS NULL THEN 'MISSING_CURRENT_COST'
        ELSE 'CURRENT_NOT_HISTORISED'
    END AS cost_basis,
    st.snapshot_at AS stock_snapshot_at,
    st.fbo_present,
    st.fbs_present,
    st.rfbs_present,
    st.total_present,
    st.total_reserved,
    CASE
        WHEN st.total_present IS NULL THEN NULL
        ELSE st.total_present = 0
    END AS out_of_stock,
    st.stock_data_quality_status,
    COALESCE(e.confirmed_units_at_current_price, 0) AS confirmed_units_at_current_price,
    COALESCE(e.multi_line_units_excluded_at_current_price, 0) AS multi_line_units_excluded_at_current_price,
    COALESCE(e.unmatched_finance_units_at_current_price, 0) AS unmatched_finance_units_at_current_price,
    CASE
        WHEN c.current_price IS NULL OR p.cost_price IS NULL THEN 'REVIEW_DATA'
        WHEN COALESCE(e.multi_line_units_excluded_at_current_price, 0) > 0
            THEN 'PARTIAL_MULTI_LINE_EXCLUDED'
        WHEN COALESCE(e.unmatched_finance_units_at_current_price, 0) > 0
            THEN 'PARTIAL_UNMATCHED_FINANCE'
        WHEN COALESCE(e.confirmed_units_at_current_price, 0) >= 10 THEN 'CONFIRMED'
        ELSE 'NOT_YET_CONFIRMED'
    END AS current_price_economics_status,
    r.regional_logistics_status,
    r.regional_signal,
    r.regional_data_quality
FROM public.products p
LEFT JOIN current_prices c ON c.offer_id = p.offer_id
LEFT JOIN current_price_since s ON s.offer_id = p.offer_id
CROSS JOIN price_freshness f
LEFT JOIN latest_stock st ON st.offer_id = p.offer_id
LEFT JOIN current_price_economics e ON e.offer_id = p.offer_id
LEFT JOIN public.vw_product_region_summary r ON r.offer_id = p.offer_id;

COMMENT ON VIEW mcp_read.product_overview IS
    'Grain: exactly one row per products.offer_id; current price, per-offer latest stock, and aggregate quality signals.';

COMMIT;
