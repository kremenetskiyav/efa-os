-- Competitor Monitor semi-automated daily-cycle read surface v1.
--
-- Adds four narrow, owner-executed security-barrier views in mcp_read.
-- Raw public.competitor_* ACLs remain closed; no write path is exposed.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog;

DO $preconditions$
DECLARE
    missing_columns text;
    existing_differences text;
    function_fingerprint text;
    restricted_roles oid[];
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Expected database efa, got %', current_database();
    END IF;

    IF current_user <> 'efa' THEN
        RAISE EXCEPTION 'Migration 024 must run as role efa, got %', current_user;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'efa_mcp_reader')
       OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'efa_mcp_readonly') THEN
        RAISE EXCEPTION 'Required MCP read roles are missing';
    END IF;

    IF (
        SELECT count(*)
          FROM pg_auth_members m
          JOIN pg_roles member_role ON member_role.oid = m.member
         WHERE member_role.rolname = 'efa_mcp_readonly'
    ) <> 1 OR NOT EXISTS (
        SELECT 1
          FROM pg_auth_members m
          JOIN pg_roles granted_role ON granted_role.oid = m.roleid
          JOIN pg_roles member_role ON member_role.oid = m.member
         WHERE member_role.rolname = 'efa_mcp_readonly'
           AND granted_role.rolname = 'efa_mcp_reader'
           AND NOT m.admin_option
    ) THEN
        RAISE EXCEPTION 'Unexpected efa_mcp_readonly membership state';
    END IF;

    IF (
        SELECT pg_get_userbyid(n.nspowner)
          FROM pg_namespace n
         WHERE n.nspname = 'mcp_read'
    ) IS DISTINCT FROM 'efa' THEN
        RAISE EXCEPTION 'Schema mcp_read is missing or is not owned by efa';
    END IF;

    IF NOT has_schema_privilege('efa_mcp_reader', 'mcp_read', 'USAGE')
       OR has_schema_privilege('efa_mcp_reader', 'mcp_read', 'CREATE')
       OR NOT has_schema_privilege('efa_mcp_readonly', 'mcp_read', 'USAGE')
       OR has_schema_privilege('efa_mcp_readonly', 'mcp_read', 'CREATE')
       OR has_schema_privilege('efa_mcp_reader', 'public', 'USAGE')
       OR has_schema_privilege('efa_mcp_readonly', 'public', 'USAGE')
       OR has_schema_privilege('efa_mcp_reader', 'public', 'CREATE')
       OR has_schema_privilege('efa_mcp_readonly', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Existing MCP schema privilege contract changed';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_namespace n
          CROSS JOIN LATERAL aclexplode(
              COALESCE(n.nspacl, acldefault('n', n.nspowner))
          ) acl
         WHERE n.nspname IN ('mcp_read', 'public')
           AND acl.grantee = 0
    ) THEN
        RAISE EXCEPTION 'PUBLIC unexpectedly has direct schema privileges';
    END IF;

    WITH expected(view_name, fingerprint) AS (
        VALUES
            ('competitor_findings', '6759ff1adad6100b788c1d5b7f9117bb'),
            ('competitor_latest_finding_set', '5d9f281b91e93bf632bb051ca24c214c'),
            ('competitor_monitoring_coverage', '4b3eacc90de2fc55ed2482d3c25e4d51'),
            ('product_cpc_daily', '170e9b0cb92470913effb495d51f3454'),
            ('product_daily_performance', '8d2d33577e07257be5502bbcc38a7f58'),
            ('product_overview', '614b70abec38215dc76749ec35ca2b25'),
            ('product_price_history', '7b3478e8e101a2841f7a0e47062ded36'),
            ('product_promotion_state', 'f8cc1bb0b02685f7f9b2c8fbbbe5e396'),
            ('product_region_logistics', 'db21649bf2b4e72cf1cda2adb2d5b4db'),
            ('product_stock_history', 'a126790040a3871ba553dff3015ed428')
    ),
    actual AS (
        SELECT
            c.relname::text AS view_name,
            md5(concat_ws(
                E'\n',
                c.relname,
                c.relkind::text,
                pg_get_userbyid(c.relowner),
                COALESCE(
                    (SELECT string_agg(x.option, ',' ORDER BY x.option)
                       FROM unnest(c.reloptions) x(option)),
                    ''
                ),
                COALESCE(
                    (SELECT string_agg(
                                format(
                                    '%s:%s:%s',
                                    a.attnum,
                                    a.attname,
                                    format_type(a.atttypid, a.atttypmod)
                                ),
                                ',' ORDER BY a.attnum
                            )
                       FROM pg_attribute a
                      WHERE a.attrelid = c.oid
                        AND a.attnum > 0
                        AND NOT a.attisdropped),
                    ''
                ),
                pg_get_viewdef(c.oid, true),
                COALESCE(
                    (SELECT string_agg(
                                format(
                                    '%s:%s:%s:%s',
                                    CASE
                                        WHEN x.grantee = 0 THEN 'PUBLIC'
                                        ELSE pg_get_userbyid(x.grantee)
                                    END,
                                    pg_get_userbyid(x.grantor),
                                    x.privilege_type,
                                    x.is_grantable
                                ),
                                ',' ORDER BY
                                    CASE
                                        WHEN x.grantee = 0 THEN 'PUBLIC'
                                        ELSE pg_get_userbyid(x.grantee)
                                    END,
                                    pg_get_userbyid(x.grantor),
                                    x.privilege_type,
                                    x.is_grantable
                            )
                       FROM aclexplode(
                                COALESCE(c.relacl, acldefault('r', c.relowner))
                            ) x),
                    ''
                )
            )) AS fingerprint
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relkind = 'v'
    ),
    differences AS (
        SELECT COALESCE(e.view_name, a.view_name) AS view_name
          FROM expected e
          FULL JOIN actual a USING (view_name)
         WHERE e.fingerprint IS DISTINCT FROM a.fingerprint
    )
    SELECT string_agg(d.view_name, ', ' ORDER BY d.view_name)
      INTO existing_differences
      FROM differences d;

    IF existing_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Existing ten-view mcp_read contract changed: %',
            existing_differences;
    END IF;

    SELECT md5(concat_ws(
               E'\n', p.proname, pg_get_function_identity_arguments(p.oid),
               pg_get_function_result(p.oid), pg_get_userbyid(p.proowner),
               p.prosecdef, p.provolatile, p.proparallel,
               COALESCE(
                   (SELECT string_agg(x.option, ',' ORDER BY x.option)
                      FROM unnest(p.proconfig) x(option)), ''
               ),
               pg_get_functiondef(p.oid),
               COALESCE(
                   (SELECT string_agg(
                               format(
                                   '%s:%s:%s:%s',
                                   CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                        ELSE pg_get_userbyid(x.grantee) END,
                                   pg_get_userbyid(x.grantor),
                                   x.privilege_type, x.is_grantable
                               ),
                               ',' ORDER BY
                                   CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                        ELSE pg_get_userbyid(x.grantee) END,
                                   pg_get_userbyid(x.grantor),
                                   x.privilege_type, x.is_grantable)
                      FROM aclexplode(
                               COALESCE(p.proacl, acldefault('f', p.proowner))
                           ) x), ''
               )
           ))
      INTO function_fingerprint
      FROM pg_proc p
     WHERE p.oid = to_regprocedure(
         'mcp_read.product_period_economics(date,date)'
     );

    IF function_fingerprint IS DISTINCT FROM
       'cf16870f884f2177f2ff4492c6344502' THEN
        RAISE EXCEPTION 'Existing product_period_economics fingerprint changed';
    END IF;

    IF to_regclass('mcp_read.competitor_reference_plan_source') IS NOT NULL
       OR to_regclass('mcp_read.competitor_snapshot_runs') IS NOT NULL
       OR to_regclass('mcp_read.competitor_snapshot_observations') IS NOT NULL
       OR to_regclass('mcp_read.competitor_finding_sets_reconciliation') IS NOT NULL THEN
        RAISE EXCEPTION 'One or more Migration 024 objects already exist';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM unnest(ARRAY[
              'competitor_sku_profiles',
              'competitor_sku_oems',
              'competitor_product_families',
              'competitor_listings',
              'competitor_watchlist_memberships',
              'competitor_search_runs',
              'competitor_observations',
              'competitor_finding_sets'
          ]::text[]) source(table_name)
         WHERE to_regclass('public.' || source.table_name) IS NULL
    ) THEN
        RAISE EXCEPTION 'One or more daily-cycle source tables are missing';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname IN (
               'competitor_sku_profiles',
               'competitor_sku_oems',
               'competitor_product_families',
               'competitor_listings',
               'competitor_watchlist_memberships',
               'competitor_search_runs',
               'competitor_observations',
               'competitor_finding_sets'
           )
           AND (
               c.relkind <> 'r'
               OR pg_get_userbyid(c.relowner) <> 'efa'
               OR c.relrowsecurity
               OR c.relforcerowsecurity
           )
    ) THEN
        RAISE EXCEPTION 'Daily-cycle source ownership/type/RLS contract changed';
    END IF;

    WITH expected(table_name, column_name, data_type, not_null) AS (
        VALUES
            ('competitor_sku_profiles', 'offer_id', 'text', true),
            ('competitor_sku_profiles', 'watchlist_state', 'text', true),
            ('competitor_sku_oems', 'sku_oem_id', 'uuid', true),
            ('competitor_sku_oems', 'offer_id', 'text', true),
            ('competitor_sku_oems', 'oem_normalized', 'text', true),
            ('competitor_sku_oems', 'active', 'boolean', true),
            ('competitor_sku_oems', 'created_at', 'timestamp with time zone', true),
            ('competitor_product_families', 'product_family_id', 'uuid', true),
            ('competitor_product_families', 'product_name', 'text', true),
            ('competitor_listings', 'listing_id', 'uuid', true),
            ('competitor_listings', 'product_family_id', 'uuid', true),
            ('competitor_listings', 'ozon_product_id', 'bigint', true),
            ('competitor_listings', 'seller_id', 'text', false),
            ('competitor_watchlist_memberships', 'membership_id', 'uuid', true),
            ('competitor_watchlist_memberships', 'offer_id', 'text', true),
            ('competitor_watchlist_memberships', 'listing_id', 'uuid', true),
            ('competitor_watchlist_memberships', 'membership_status', 'text', true),
            ('competitor_watchlist_memberships', 'matched_oem_set', 'text[]', true),
            ('competitor_watchlist_memberships', 'valid_from', 'timestamp with time zone', true),
            ('competitor_watchlist_memberships', 'valid_to', 'timestamp with time zone', false),
            ('competitor_search_runs', 'search_run_id', 'uuid', true),
            ('competitor_search_runs', 'offer_id', 'text', true),
            ('competitor_search_runs', 'sku_oem_id', 'uuid', false),
            ('competitor_search_runs', 'query_kind', 'text', true),
            ('competitor_search_runs', 'query_text_exact', 'text', true),
            ('competitor_search_runs', 'query_normalized', 'text', true),
            ('competitor_search_runs', 'region_key', 'text', true),
            ('competitor_search_runs', 'location_label', 'text', false),
            ('competitor_search_runs', 'captured_at', 'timestamp with time zone', true),
            ('competitor_search_runs', 'status', 'text', true),
            ('competitor_search_runs', 'page_count_observed', 'integer', false),
            ('competitor_search_runs', 'result_count_observed', 'integer', false),
            ('competitor_search_runs', 'collection_ref', 'text', true),
            ('competitor_search_runs', 'raw_source_ref', 'text', false),
            ('competitor_observations', 'observation_id', 'uuid', true),
            ('competitor_observations', 'search_run_id', 'uuid', true),
            ('competitor_observations', 'listing_id', 'uuid', true),
            ('competitor_observations', 'membership_id', 'uuid', false),
            ('competitor_observations', 'captured_at', 'timestamp with time zone', true),
            ('competitor_observations', 'enrichment_captured_at', 'timestamp with time zone', false),
            ('competitor_observations', 'page_number', 'integer', false),
            ('competitor_observations', 'position_on_page', 'integer', false),
            ('competitor_observations', 'rank', 'integer', false),
            ('competitor_observations', 'ad_flag', 'boolean', false),
            ('competitor_observations', 'bank_price', 'numeric(14,2)', false),
            ('competitor_observations', 'other_payment_price', 'numeric(14,2)', false),
            ('competitor_observations', 'old_price', 'numeric(14,2)', false),
            ('competitor_observations', 'currency', 'text', false),
            ('competitor_observations', 'rating', 'numeric(3,2)', false),
            ('competitor_observations', 'reviews_count_observed', 'integer', false),
            ('competitor_observations', 'reviews_scope', 'text', true),
            ('competitor_observations', 'purchase_count_observed', 'integer', false),
            ('competitor_observations', 'purchase_indicator_raw', 'text', false),
            ('competitor_observations', 'availability_status', 'text', true),
            ('competitor_observations', 'availability_raw', 'text', false),
            ('competitor_observations', 'observed_oem_raw', 'text', false),
            ('competitor_observations', 'observed_dimensions_raw', 'text', false),
            ('competitor_observations', 'observed_length_mm', 'numeric(10,3)', false),
            ('competitor_observations', 'observed_width_mm', 'numeric(10,3)', false),
            ('competitor_observations', 'observed_height_mm', 'numeric(10,3)', false),
            ('competitor_observations', 'carbon_claim_raw', 'text', false),
            ('competitor_observations', 'origin_raw', 'text', false),
            ('competitor_observations', 'quality_status', 'text', true),
            ('competitor_observations', 'quality_flags', 'text[]', true),
            ('competitor_observations', 'source_ref', 'text', true),
            ('competitor_observations', 'raw_ref', 'text', false),
            ('competitor_observations', 'observation_ref', 'text', true),
            ('competitor_finding_sets', 'finding_set_id', 'uuid', true),
            ('competitor_finding_sets', 'set_key', 'text', true),
            ('competitor_finding_sets', 'persistence_contract_version', 'text', true),
            ('competitor_finding_sets', 'finding_set_contract_version', 'text', true),
            ('competitor_finding_sets', 'source_analysis_contract_version', 'text', true),
            ('competitor_finding_sets', 'source_findings_sha256', 'text', true),
            ('competitor_finding_sets', 'source_findings_semantic_sha256', 'text', true),
            ('competitor_finding_sets', 'source_analysis_sha256', 'text', true),
            ('competitor_finding_sets', 'previous_source_kind', 'text', true),
            ('competitor_finding_sets', 'previous_derived_batch_id', 'text', true),
            ('competitor_finding_sets', 'previous_reference_at', 'timestamp with time zone', true),
            ('competitor_finding_sets', 'previous_captured_through', 'timestamp with time zone', true),
            ('competitor_finding_sets', 'current_source_kind', 'text', true),
            ('competitor_finding_sets', 'current_derived_batch_id', 'text', true),
            ('competitor_finding_sets', 'current_reference_at', 'timestamp with time zone', true),
            ('competitor_finding_sets', 'current_captured_through', 'timestamp with time zone', true),
            ('competitor_finding_sets', 'expected_findings_count', 'integer', true)
    )
    SELECT string_agg(
               e.table_name || '.' || e.column_name,
               ', ' ORDER BY e.table_name, e.column_name
           )
      INTO missing_columns
      FROM expected e
     WHERE NOT EXISTS (
         SELECT 1
           FROM pg_attribute a
          WHERE a.attrelid = to_regclass('public.' || e.table_name)
            AND a.attname = e.column_name
            AND format_type(a.atttypid, a.atttypmod) = e.data_type
            AND a.attnotnull = e.not_null
            AND a.attnum > 0
            AND NOT a.attisdropped
     );

    IF missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Required source column contract changed: %', missing_columns;
    END IF;

    -- The reference-plan surface exposes every historical membership row.
    -- matched_oem_set already stores canonical oem_normalized values; no new
    -- normalization, current active-state filter, or silent repair is allowed.
    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships m
         WHERE m.matched_oem_set IS NULL
            OR cardinality(m.matched_oem_set) = 0
            OR array_position(m.matched_oem_set, NULL) IS NOT NULL
            OR cardinality(m.matched_oem_set) <> (
                SELECT count(DISTINCT q.query_text_exact)
                  FROM unnest(m.matched_oem_set) q(query_text_exact)
            )
            OR EXISTS (
                SELECT 1
                  FROM unnest(m.matched_oem_set) WITH ORDINALITY
                       q(query_text_exact, element_ordinal)
                 WHERE (
                     SELECT count(*)
                       FROM public.competitor_sku_oems o
                      WHERE o.offer_id = m.offer_id
                        AND o.oem_normalized = q.query_text_exact
                 ) <> 1
            )
    ) THEN
        RAISE EXCEPTION 'Historical membership matched_oem_set contract changed';
    END IF;

    SELECT array_agg(r.oid ORDER BY r.rolname)
      INTO restricted_roles
      FROM pg_roles r
     WHERE r.rolname IN ('efa_mcp_reader', 'efa_mcp_readonly');

    IF cardinality(restricted_roles) IS DISTINCT FROM 2 THEN
        RAISE EXCEPTION 'Required MCP read roles are missing';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(
              COALESCE(c.relacl, acldefault('r', c.relowner))
          ) acl
         WHERE n.nspname = 'public'
           AND c.relname LIKE 'competitor_%'
           AND c.relkind IN ('r', 'p')
           AND acl.grantee = ANY (array_prepend(0::oid, restricted_roles))
           AND acl.privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
    ) OR EXISTS (
        SELECT 1
          FROM unnest(
                   ARRAY['efa_mcp_reader', 'efa_mcp_readonly']::text[]
               ) restricted(role_name)
          CROSS JOIN LATERAL (
              SELECT c.oid
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname = 'public'
                 AND c.relname LIKE 'competitor_%'
                 AND c.relkind IN ('r', 'p')
          ) target
         WHERE has_table_privilege(restricted.role_name, target.oid, 'SELECT')
            OR has_table_privilege(restricted.role_name, target.oid, 'INSERT')
            OR has_table_privilege(restricted.role_name, target.oid, 'UPDATE')
            OR has_table_privilege(restricted.role_name, target.oid, 'DELETE')
    ) THEN
        RAISE EXCEPTION 'Direct/effective raw competitor-table CRUD ACL is not closed';
    END IF;
END
$preconditions$;

CREATE VIEW mcp_read.competitor_reference_plan_source
WITH (security_barrier = true)
AS
SELECT
    'PROFILE'::text AS record_kind,
    p.offer_id,
    p.watchlist_state,
    NULL::uuid AS sku_oem_id,
    NULL::text AS query_text_exact,
    NULL::text AS query_normalized,
    NULL::boolean AS oem_active,
    NULL::timestamp with time zone AS oem_created_at,
    NULL::uuid AS membership_id,
    NULL::text AS membership_status,
    NULL::text[] AS matched_oem_set,
    NULL::timestamp with time zone AS valid_from,
    NULL::timestamp with time zone AS valid_to,
    NULL::uuid AS listing_id,
    NULL::uuid AS product_family_id,
    NULL::bigint AS ozon_product_id,
    NULL::text AS seller_id,
    NULL::text AS product_name
FROM public.competitor_sku_profiles p
UNION ALL
SELECT
    'SKU_OEM'::text AS record_kind,
    p.offer_id,
    p.watchlist_state,
    o.sku_oem_id,
    NULL::text AS query_text_exact,
    o.oem_normalized AS query_normalized,
    o.active AS oem_active,
    o.created_at AS oem_created_at,
    NULL::uuid AS membership_id,
    NULL::text AS membership_status,
    NULL::text[] AS matched_oem_set,
    NULL::timestamp with time zone AS valid_from,
    NULL::timestamp with time zone AS valid_to,
    NULL::uuid AS listing_id,
    NULL::uuid AS product_family_id,
    NULL::bigint AS ozon_product_id,
    NULL::text AS seller_id,
    NULL::text AS product_name
FROM public.competitor_sku_profiles p
JOIN public.competitor_sku_oems o ON o.offer_id = p.offer_id
UNION ALL
SELECT
    'MEMBERSHIP_QUERY'::text AS record_kind,
    p.offer_id,
    p.watchlist_state,
    o.sku_oem_id,
    q.query_text_exact,
    o.oem_normalized AS query_normalized,
    o.active AS oem_active,
    o.created_at AS oem_created_at,
    m.membership_id,
    m.membership_status,
    m.matched_oem_set,
    m.valid_from,
    m.valid_to,
    l.listing_id,
    l.product_family_id,
    l.ozon_product_id,
    l.seller_id,
    f.product_name
FROM public.competitor_watchlist_memberships m
JOIN public.competitor_sku_profiles p ON p.offer_id = m.offer_id
JOIN public.competitor_listings l ON l.listing_id = m.listing_id
JOIN public.competitor_product_families f
  ON f.product_family_id = l.product_family_id
CROSS JOIN LATERAL unnest(m.matched_oem_set) q(query_text_exact)
LEFT JOIN public.competitor_sku_oems o
  ON o.offer_id = m.offer_id
 AND o.oem_normalized = q.query_text_exact;

CREATE VIEW mcp_read.competitor_snapshot_runs
WITH (security_barrier = true)
AS
SELECT
    search_run_id,
    offer_id,
    sku_oem_id,
    query_kind,
    query_text_exact,
    query_normalized,
    region_key,
    location_label,
    captured_at,
    status,
    page_count_observed,
    result_count_observed,
    collection_ref,
    raw_source_ref
FROM public.competitor_search_runs r;

CREATE VIEW mcp_read.competitor_snapshot_observations
WITH (security_barrier = true)
AS
SELECT
    o.observation_id,
    o.search_run_id,
    o.listing_id,
    o.membership_id,
    l.ozon_product_id,
    m.membership_status,
    o.captured_at,
    o.enrichment_captured_at,
    o.page_number,
    o.position_on_page,
    o.rank,
    o.ad_flag,
    o.bank_price,
    o.other_payment_price,
    o.old_price,
    o.currency,
    o.rating,
    o.reviews_count_observed,
    o.reviews_scope,
    o.purchase_count_observed,
    o.purchase_indicator_raw,
    o.availability_status,
    o.availability_raw,
    o.observed_oem_raw,
    o.observed_dimensions_raw,
    o.observed_length_mm,
    o.observed_width_mm,
    o.observed_height_mm,
    o.carbon_claim_raw,
    o.origin_raw,
    o.quality_status,
    o.quality_flags,
    o.source_ref,
    o.raw_ref,
    o.observation_ref
FROM public.competitor_observations o
JOIN public.competitor_listings l ON l.listing_id = o.listing_id
LEFT JOIN public.competitor_watchlist_memberships m
  ON m.membership_id = o.membership_id;

CREATE VIEW mcp_read.competitor_finding_sets_reconciliation
WITH (security_barrier = true)
AS
SELECT
    finding_set_id,
    set_key,
    persistence_contract_version,
    finding_set_contract_version,
    source_analysis_contract_version,
    source_findings_sha256,
    source_findings_semantic_sha256,
    source_analysis_sha256,
    previous_source_kind,
    previous_derived_batch_id,
    previous_reference_at,
    previous_captured_through,
    current_source_kind,
    current_derived_batch_id,
    current_reference_at,
    current_captured_through,
    expected_findings_count
FROM public.competitor_finding_sets s;

ALTER VIEW mcp_read.competitor_reference_plan_source OWNER TO efa;
ALTER VIEW mcp_read.competitor_snapshot_runs OWNER TO efa;
ALTER VIEW mcp_read.competitor_snapshot_observations OWNER TO efa;
ALTER VIEW mcp_read.competitor_finding_sets_reconciliation OWNER TO efa;

REVOKE ALL PRIVILEGES ON TABLE
    mcp_read.competitor_reference_plan_source,
    mcp_read.competitor_snapshot_runs,
    mcp_read.competitor_snapshot_observations,
    mcp_read.competitor_finding_sets_reconciliation
FROM PUBLIC, efa_mcp_readonly;

GRANT SELECT ON TABLE
    mcp_read.competitor_reference_plan_source,
    mcp_read.competitor_snapshot_runs,
    mcp_read.competitor_snapshot_observations,
    mcp_read.competitor_finding_sets_reconciliation
TO efa_mcp_reader;

COMMENT ON VIEW mcp_read.competitor_reference_plan_source IS
    'Minimal factual profile, OEM, and historical membership source for deterministic Competitor Monitor reference-plan reconstruction.';

COMMENT ON VIEW mcp_read.competitor_snapshot_runs IS
    'Factual Competitor Monitor search-run history required for batch identity and idempotency reconciliation.';

COMMENT ON VIEW mcp_read.competitor_snapshot_observations IS
    'Factual Competitor Monitor observation history with stable listing identity and captured membership status.';

COMMENT ON VIEW mcp_read.competitor_finding_sets_reconciliation IS
    'All persisted finding-set manifests required for generic dry-run idempotency and conflict reconciliation.';

COMMIT;
