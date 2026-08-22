-- Post-deployment validation for
-- 015_mcp_read_product_period_economics_v1.sql.
-- The validation transaction is read-only and leaves no database changes.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    function_oid oid := 'mcp_read.product_period_economics(date,date)'::regprocedure;
    function_source text;
BEGIN
    SELECT p.prosrc
      INTO function_source
      FROM pg_proc p
     WHERE p.oid = function_oid;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_proc p
          JOIN pg_language l ON l.oid = p.prolang
         WHERE p.oid = function_oid
           AND l.lanname = 'sql'
           AND p.provolatile = 's'
           AND p.prosecdef
           AND p.pronargs = 2
           AND p.proargtypes = '1082 1082'::oidvector
           AND p.proconfig @> ARRAY['search_path=pg_catalog']::text[]
           AND pg_get_userbyid(p.proowner) = 'efa'
    ) THEN
        RAISE EXCEPTION 'Function security, language, volatility, signature, search_path, or owner is invalid';
    END IF;

    IF function_source ~* '\m(insert|update|delete|merge|execute|alter|create|drop|truncate|copy|call|do)\M' THEN
        RAISE EXCEPTION 'Function body contains a prohibited statement';
    END IF;

    IF function_source NOT LIKE '%public.products%'
       OR function_source NOT LIKE '%public.postings%'
       OR function_source NOT LIKE '%public.returns%'
       OR function_source NOT LIKE '%public.finance_operations%' THEN
        RAISE EXCEPTION 'Function does not use fully qualified raw table names';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_proc p
          CROSS JOIN LATERAL aclexplode(
              COALESCE(p.proacl, acldefault('f', p.proowner))
          ) acl
         WHERE p.oid = 'mcp_read.product_period_economics(date,date)'::regprocedure
           AND acl.grantee = 0
           AND acl.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC must not execute product_period_economics';
    END IF;

    IF NOT has_function_privilege('efa_mcp_reader', 'mcp_read.product_period_economics(date,date)', 'EXECUTE')
       OR NOT has_function_privilege('efa_mcp_readonly', 'mcp_read.product_period_economics(date,date)', 'EXECUTE') THEN
        RAISE EXCEPTION 'Existing MCP read roles cannot execute product_period_economics';
    END IF;

    IF has_table_privilege('efa_mcp_readonly', 'public.products', 'SELECT')
       OR has_table_privilege('efa_mcp_readonly', 'public.postings', 'SELECT')
       OR has_table_privilege('efa_mcp_readonly', 'public.returns', 'SELECT')
       OR has_table_privilege('efa_mcp_readonly', 'public.finance_operations', 'SELECT') THEN
        RAISE EXCEPTION 'efa_mcp_readonly gained direct raw-table SELECT';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM mcp_read.product_period_economics(date '2026-08-21', date '2026-08-20')
    ) THEN
        RAISE EXCEPTION 'Reversed period must return no rows';
    END IF;

    IF EXISTS (
        SELECT 1 FROM mcp_read.product_period_economics(date '2026-01-01', date '2026-04-04')
    ) THEN
        RAISE EXCEPTION 'Period wider than 93 calendar days must return no rows';
    END IF;
END $$;

DO $$
DECLARE
    failed_skus text;
BEGIN
    WITH expected(sku, pbt, margin, profit_per_unit, delivered, returned) AS (
        VALUES
            ('УФ 001Б', numeric '193.54', numeric '10.33', numeric '64.5133', 3, 0),
            ('УФ 002Б', numeric '-6.43', NULL::numeric, NULL::numeric, 0, 0),
            ('УФ 003Б', numeric '24.92', numeric '4.16', numeric '24.9200', 1, 0),
            ('УФ 004Б', numeric '-212.51', NULL::numeric, NULL::numeric, 1, 1),
            ('УФ 005Б', numeric '79.40', numeric '11.90', numeric '79.4000', 1, 0)
    ), actual AS (
        SELECT *
        FROM mcp_read.product_period_economics(date '2026-08-14', date '2026-08-20')
    )
    SELECT STRING_AGG(e.sku, ', ' ORDER BY e.sku)
      INTO failed_skus
      FROM expected e
      LEFT JOIN actual a ON a.sku = e.sku
     WHERE a.sku IS NULL
        OR ABS(a.profit_before_tax - e.pbt) > numeric '0.01'
        OR a.margin_before_tax IS DISTINCT FROM e.margin
        OR a.profit_per_unit IS DISTINCT FROM e.profit_per_unit
        OR a.delivered_units IS DISTINCT FROM e.delivered
        OR a.returned_units IS DISTINCT FROM e.returned;

    IF failed_skus IS NOT NULL THEN
        RAISE EXCEPTION 'Golden reconciliation failed for: %', failed_skus;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM mcp_read.product_period_economics(date '2026-08-14', date '2026-08-20') e
         WHERE e.profit_before_tax IS NOT NULL
           AND ABS(
               e.profit_before_tax
               - (
                   e.gross_sales
                   - e.commission
                   - e.acquiring
                   - e.services
                   - e.return_operations
                   - e.cogs
               )
           ) > numeric '0.0001'
    ) THEN
        RAISE EXCEPTION 'PBT signed-component identity failed';
    END IF;
END $$;

SELECT
    e.sku,
    e.delivered_units,
    e.returned_units,
    e.net_sold_units,
    ROUND(e.gross_sales, 2) AS gross_sales,
    ROUND(e.commission, 2) AS commission,
    ROUND(e.acquiring, 2) AS acquiring,
    ROUND(e.services, 2) AS services,
    ROUND(e.return_operations, 2) AS return_operations,
    ROUND(e.cogs, 2) AS cogs,
    ROUND(e.profit_before_tax, 2) AS profit_before_tax,
    e.profit_per_unit,
    e.margin_before_tax,
    CASE
        WHEN ABS(e.profit_before_tax - x.expected_pbt) <= numeric '0.01' THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM mcp_read.product_period_economics(date '2026-08-14', date '2026-08-20') e
JOIN (
    VALUES
        ('УФ 001Б', numeric '193.54'),
        ('УФ 002Б', numeric '-6.43'),
        ('УФ 003Б', numeric '24.92'),
        ('УФ 004Б', numeric '-212.51'),
        ('УФ 005Б', numeric '79.40')
) AS x(sku, expected_pbt) ON x.sku = e.sku
ORDER BY e.sku;

ROLLBACK;
