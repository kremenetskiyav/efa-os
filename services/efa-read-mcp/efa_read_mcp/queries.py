"""Fixed, schema-qualified SELECT statements for the eight MCP tools."""

LIST_PRODUCTS = """
SELECT
    offer_id,
    sku,
    product_name,
    brand,
    is_archived,
    price_observed_at,
    stock_snapshot_at
FROM mcp_read.product_overview
WHERE ($1::boolean OR is_archived IS NOT TRUE)
ORDER BY offer_id ASC
"""

GET_PRODUCT_OVERVIEW = """
SELECT
    offer_id,
    sku,
    ozon_product_id,
    product_name,
    brand,
    is_archived,
    product_observed_at,
    current_price,
    current_price_since,
    price_observed_at,
    price_checked_at,
    cost_price,
    cost_basis,
    stock_snapshot_at,
    fbo_present,
    fbs_present,
    rfbs_present,
    total_present,
    total_reserved,
    out_of_stock,
    stock_data_quality_status,
    confirmed_units_at_current_price,
    multi_line_units_excluded_at_current_price,
    unmatched_finance_units_at_current_price,
    current_price_economics_status,
    regional_logistics_status,
    regional_signal,
    regional_data_quality
FROM mcp_read.product_overview
WHERE offer_id = $1
ORDER BY offer_id ASC
LIMIT 1
"""

GET_PRICE_HISTORY = """
SELECT
    offer_id,
    observed_at,
    price,
    previous_price,
    absolute_change,
    change_percent,
    min_price,
    marketing_price,
    marketing_seller_price,
    is_latest
FROM mcp_read.product_price_history
WHERE offer_id = $1
  AND observed_at >= $2::date
  AND observed_at < ($3::date + 1)
ORDER BY observed_at DESC, offer_id ASC
LIMIT $4
"""

GET_STOCK_HISTORY = """
SELECT
    offer_id,
    snapshot_at,
    fbo_present,
    fbo_reserved,
    fbs_present,
    fbs_reserved,
    rfbs_present,
    rfbs_reserved,
    total_present,
    total_reserved,
    previous_total_present,
    previous_total_reserved,
    total_present_change,
    total_reserved_change,
    data_quality_status,
    is_latest
FROM mcp_read.product_stock_history
WHERE offer_id = $1
  AND snapshot_at >= $2::date
  AND snapshot_at < ($3::date + 1)
ORDER BY snapshot_at DESC, offer_id ASC
LIMIT $4
"""

GET_DAILY_PERFORMANCE = """
SELECT
    offer_id,
    business_date,
    ordered_units,
    ordered_revenue,
    demand_collected_at,
    demand_quality_status,
    delivered_units,
    return_events,
    returned_units,
    finance_matched_lines,
    finance_matched_delivered_units,
    multi_line_excluded_units,
    unmatched_finance_units,
    confirmed_revenue,
    commission_expense,
    logistics_expense,
    other_expenses,
    cost_of_goods,
    payout,
    profit_before_tax,
    profit_per_unit,
    profit_margin_percent,
    cost_basis,
    economics_quality_status,
    postings_collection_status,
    postings_collected_at,
    returns_collection_status,
    returns_collected_at,
    finance_collection_status,
    finance_collected_at
FROM mcp_read.product_daily_performance
WHERE offer_id = $1
  AND business_date BETWEEN $2::date AND $3::date
ORDER BY business_date DESC, offer_id ASC
LIMIT $4
"""

GET_REGION_LOGISTICS = """
SELECT
    offer_id,
    cluster_from,
    cluster_to,
    orders_count,
    avg_logistics,
    baseline_logistics,
    logistics_delta,
    logistics_delta_percent,
    avg_revenue,
    baseline_revenue,
    logistics_rate_percent,
    baseline_logistics_rate_percent,
    logistics_rate_delta_pp,
    confidence,
    data_from,
    data_through,
    rule_version
FROM mcp_read.product_region_logistics
WHERE offer_id = $1
  AND (
      $2::text IS NULL
      OR CASE confidence
          WHEN 'VERY_HIGH' THEN 4
          WHEN 'HIGH' THEN 3
          WHEN 'MEDIUM' THEN 2
          WHEN 'LOW' THEN 1
          ELSE 0
      END >= CASE $2::text
          WHEN 'VERY_HIGH' THEN 4
          WHEN 'HIGH' THEN 3
          WHEN 'MEDIUM' THEN 2
          WHEN 'LOW' THEN 1
          ELSE 0
      END
  )
ORDER BY
    CASE confidence
        WHEN 'VERY_HIGH' THEN 4
        WHEN 'HIGH' THEN 3
        WHEN 'MEDIUM' THEN 2
        WHEN 'LOW' THEN 1
        ELSE 0
    END DESC,
    orders_count DESC NULLS LAST,
    cluster_from ASC NULLS LAST,
    cluster_to ASC NULLS LAST
LIMIT $3
"""

GET_PROMOTION_STATE = """
SELECT
    offer_id,
    ozon_promotion_id,
    promotion_title,
    promotion_type,
    participation_state,
    add_mode,
    starts_at,
    ends_at,
    observed_price,
    promotion_price,
    max_promotion_price,
    current_boost,
    min_boost,
    max_boost,
    observed_at,
    data_quality_status
FROM mcp_read.product_promotion_state
WHERE offer_id = $1
  AND (
      $2::boolean IS FALSE
      OR (
          (starts_at IS NULL OR starts_at <= CURRENT_TIMESTAMP)
          AND (ends_at IS NULL OR ends_at >= CURRENT_TIMESTAMP)
      )
  )
ORDER BY observed_at DESC NULLS LAST, ozon_promotion_id ASC
"""

GET_CPC_DAILY = """
SELECT
    business_date,
    data_scope,
    offer_id,
    campaigns_count,
    active_campaigns_count,
    views,
    clicks,
    ctr_percent,
    spend,
    attributed_orders,
    attributed_revenue,
    product_gmv,
    drr_percent,
    general_drr_percent,
    average_bid,
    data_quality_status,
    collection_status,
    observed_at
FROM mcp_read.product_cpc_daily
WHERE business_date BETWEEN $2::date AND $3::date
  AND (
      $1::text IS NULL
      OR (data_scope = 'PRODUCT' AND offer_id = $1)
      OR (data_scope = 'ACCOUNT' AND offer_id IS NULL)
  )
  AND ($4::text IS NULL OR data_scope = $4)
ORDER BY
    business_date DESC,
    CASE data_scope WHEN 'ACCOUNT' THEN 1 WHEN 'PRODUCT' THEN 2 ELSE 3 END ASC,
    offer_id ASC NULLS FIRST
LIMIT $5
"""


QUERY_BY_TOOL = {
    "list_products": LIST_PRODUCTS,
    "get_product_overview": GET_PRODUCT_OVERVIEW,
    "get_price_history": GET_PRICE_HISTORY,
    "get_stock_history": GET_STOCK_HISTORY,
    "get_daily_performance": GET_DAILY_PERFORMANCE,
    "get_region_logistics": GET_REGION_LOGISTICS,
    "get_promotion_state": GET_PROMOTION_STATE,
    "get_cpc_daily": GET_CPC_DAILY,
}

SOURCE_BY_TOOL = {
    "list_products": "mcp_read.product_overview",
    "get_product_overview": "mcp_read.product_overview",
    "get_price_history": "mcp_read.product_price_history",
    "get_stock_history": "mcp_read.product_stock_history",
    "get_daily_performance": "mcp_read.product_daily_performance",
    "get_region_logistics": "mcp_read.product_region_logistics",
    "get_promotion_state": "mcp_read.product_promotion_state",
    "get_cpc_daily": "mcp_read.product_cpc_daily",
}
