-- Post-deployment validation for
-- 024_mcp_read_competitor_daily_cycle_source_v1.sql.
-- The validation transaction is read-only and leaves no database changes.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog;

DO $objects$
DECLARE
    object_differences text;
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Expected database efa, got %', current_database();
    END IF;

    IF (
        SELECT pg_get_userbyid(n.nspowner)
          FROM pg_namespace n
         WHERE n.nspname = 'mcp_read'
    ) IS DISTINCT FROM 'efa' THEN
        RAISE EXCEPTION 'Schema mcp_read is missing or is not owned by efa';
    END IF;

    WITH expected(view_name) AS (
        VALUES
            ('competitor_reference_plan_source'),
            ('competitor_snapshot_runs'),
            ('competitor_snapshot_observations'),
            ('competitor_finding_sets_reconciliation')
    )
    SELECT string_agg(e.view_name, ', ' ORDER BY e.view_name)
      INTO object_differences
      FROM expected e
     WHERE NOT EXISTS (
         SELECT 1
           FROM pg_class c
           JOIN pg_namespace n ON n.oid = c.relnamespace
          WHERE n.nspname = 'mcp_read'
            AND c.relname = e.view_name
            AND c.relkind = 'v'
            AND pg_get_userbyid(c.relowner) = 'efa'
            AND c.reloptions IS NOT DISTINCT FROM
                ARRAY['security_barrier=true']::text[]
     );

    IF object_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 024 view contract differs: %',
            object_differences;
    END IF;

    IF (
        SELECT count(*)
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relkind = 'v'
    ) <> 14 THEN
        RAISE EXCEPTION 'Expected fourteen approved mcp_read views after Migration 024';
    END IF;

    IF (
        SELECT count(*)
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'mcp_read'
    ) <> 1 THEN
        RAISE EXCEPTION 'Expected one approved mcp_read function after Migration 024';
    END IF;
END
$objects$;

DO $columns$
DECLARE
    column_differences text;
BEGIN
    WITH expected(view_name, ordinal_position, column_name, data_type) AS (
        VALUES
            ('competitor_reference_plan_source', 1, 'record_kind', 'text'),
            ('competitor_reference_plan_source', 2, 'offer_id', 'text'),
            ('competitor_reference_plan_source', 3, 'watchlist_state', 'text'),
            ('competitor_reference_plan_source', 4, 'sku_oem_id', 'uuid'),
            ('competitor_reference_plan_source', 5, 'query_text_exact', 'text'),
            ('competitor_reference_plan_source', 6, 'query_normalized', 'text'),
            ('competitor_reference_plan_source', 7, 'oem_active', 'boolean'),
            ('competitor_reference_plan_source', 8, 'oem_created_at', 'timestamp with time zone'),
            ('competitor_reference_plan_source', 9, 'membership_id', 'uuid'),
            ('competitor_reference_plan_source', 10, 'membership_status', 'text'),
            ('competitor_reference_plan_source', 11, 'matched_oem_set', 'text[]'),
            ('competitor_reference_plan_source', 12, 'valid_from', 'timestamp with time zone'),
            ('competitor_reference_plan_source', 13, 'valid_to', 'timestamp with time zone'),
            ('competitor_reference_plan_source', 14, 'listing_id', 'uuid'),
            ('competitor_reference_plan_source', 15, 'product_family_id', 'uuid'),
            ('competitor_reference_plan_source', 16, 'ozon_product_id', 'bigint'),
            ('competitor_reference_plan_source', 17, 'seller_id', 'text'),
            ('competitor_reference_plan_source', 18, 'product_name', 'text'),
            ('competitor_snapshot_runs', 1, 'search_run_id', 'uuid'),
            ('competitor_snapshot_runs', 2, 'offer_id', 'text'),
            ('competitor_snapshot_runs', 3, 'sku_oem_id', 'uuid'),
            ('competitor_snapshot_runs', 4, 'query_kind', 'text'),
            ('competitor_snapshot_runs', 5, 'query_text_exact', 'text'),
            ('competitor_snapshot_runs', 6, 'query_normalized', 'text'),
            ('competitor_snapshot_runs', 7, 'region_key', 'text'),
            ('competitor_snapshot_runs', 8, 'location_label', 'text'),
            ('competitor_snapshot_runs', 9, 'captured_at', 'timestamp with time zone'),
            ('competitor_snapshot_runs', 10, 'status', 'text'),
            ('competitor_snapshot_runs', 11, 'page_count_observed', 'integer'),
            ('competitor_snapshot_runs', 12, 'result_count_observed', 'integer'),
            ('competitor_snapshot_runs', 13, 'collection_ref', 'text'),
            ('competitor_snapshot_runs', 14, 'raw_source_ref', 'text'),
            ('competitor_snapshot_observations', 1, 'observation_id', 'uuid'),
            ('competitor_snapshot_observations', 2, 'search_run_id', 'uuid'),
            ('competitor_snapshot_observations', 3, 'listing_id', 'uuid'),
            ('competitor_snapshot_observations', 4, 'membership_id', 'uuid'),
            ('competitor_snapshot_observations', 5, 'ozon_product_id', 'bigint'),
            ('competitor_snapshot_observations', 6, 'membership_status', 'text'),
            ('competitor_snapshot_observations', 7, 'captured_at', 'timestamp with time zone'),
            ('competitor_snapshot_observations', 8, 'enrichment_captured_at', 'timestamp with time zone'),
            ('competitor_snapshot_observations', 9, 'page_number', 'integer'),
            ('competitor_snapshot_observations', 10, 'position_on_page', 'integer'),
            ('competitor_snapshot_observations', 11, 'rank', 'integer'),
            ('competitor_snapshot_observations', 12, 'ad_flag', 'boolean'),
            ('competitor_snapshot_observations', 13, 'bank_price', 'numeric(14,2)'),
            ('competitor_snapshot_observations', 14, 'other_payment_price', 'numeric(14,2)'),
            ('competitor_snapshot_observations', 15, 'old_price', 'numeric(14,2)'),
            ('competitor_snapshot_observations', 16, 'currency', 'text'),
            ('competitor_snapshot_observations', 17, 'rating', 'numeric(3,2)'),
            ('competitor_snapshot_observations', 18, 'reviews_count_observed', 'integer'),
            ('competitor_snapshot_observations', 19, 'reviews_scope', 'text'),
            ('competitor_snapshot_observations', 20, 'purchase_count_observed', 'integer'),
            ('competitor_snapshot_observations', 21, 'purchase_indicator_raw', 'text'),
            ('competitor_snapshot_observations', 22, 'availability_status', 'text'),
            ('competitor_snapshot_observations', 23, 'availability_raw', 'text'),
            ('competitor_snapshot_observations', 24, 'observed_oem_raw', 'text'),
            ('competitor_snapshot_observations', 25, 'observed_dimensions_raw', 'text'),
            ('competitor_snapshot_observations', 26, 'observed_length_mm', 'numeric(10,3)'),
            ('competitor_snapshot_observations', 27, 'observed_width_mm', 'numeric(10,3)'),
            ('competitor_snapshot_observations', 28, 'observed_height_mm', 'numeric(10,3)'),
            ('competitor_snapshot_observations', 29, 'carbon_claim_raw', 'text'),
            ('competitor_snapshot_observations', 30, 'origin_raw', 'text'),
            ('competitor_snapshot_observations', 31, 'quality_status', 'text'),
            ('competitor_snapshot_observations', 32, 'quality_flags', 'text[]'),
            ('competitor_snapshot_observations', 33, 'source_ref', 'text'),
            ('competitor_snapshot_observations', 34, 'raw_ref', 'text'),
            ('competitor_snapshot_observations', 35, 'observation_ref', 'text'),
            ('competitor_finding_sets_reconciliation', 1, 'finding_set_id', 'uuid'),
            ('competitor_finding_sets_reconciliation', 2, 'set_key', 'text'),
            ('competitor_finding_sets_reconciliation', 3, 'persistence_contract_version', 'text'),
            ('competitor_finding_sets_reconciliation', 4, 'finding_set_contract_version', 'text'),
            ('competitor_finding_sets_reconciliation', 5, 'source_analysis_contract_version', 'text'),
            ('competitor_finding_sets_reconciliation', 6, 'source_findings_sha256', 'text'),
            ('competitor_finding_sets_reconciliation', 7, 'source_findings_semantic_sha256', 'text'),
            ('competitor_finding_sets_reconciliation', 8, 'source_analysis_sha256', 'text'),
            ('competitor_finding_sets_reconciliation', 9, 'previous_source_kind', 'text'),
            ('competitor_finding_sets_reconciliation', 10, 'previous_derived_batch_id', 'text'),
            ('competitor_finding_sets_reconciliation', 11, 'previous_reference_at', 'timestamp with time zone'),
            ('competitor_finding_sets_reconciliation', 12, 'previous_captured_through', 'timestamp with time zone'),
            ('competitor_finding_sets_reconciliation', 13, 'current_source_kind', 'text'),
            ('competitor_finding_sets_reconciliation', 14, 'current_derived_batch_id', 'text'),
            ('competitor_finding_sets_reconciliation', 15, 'current_reference_at', 'timestamp with time zone'),
            ('competitor_finding_sets_reconciliation', 16, 'current_captured_through', 'timestamp with time zone'),
            ('competitor_finding_sets_reconciliation', 17, 'expected_findings_count', 'integer')
    ),
    actual AS (
        SELECT
            c.relname::text AS view_name,
            a.attnum::integer AS ordinal_position,
            a.attname::text AS column_name,
            format_type(a.atttypid, a.atttypmod) AS data_type
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          JOIN pg_attribute a ON a.attrelid = c.oid
         WHERE n.nspname = 'mcp_read'
           AND c.relname IN (
               'competitor_reference_plan_source',
               'competitor_snapshot_runs',
               'competitor_snapshot_observations',
               'competitor_finding_sets_reconciliation'
           )
           AND a.attnum > 0
           AND NOT a.attisdropped
    ),
    differences AS (
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        UNION ALL
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(
               d.view_name || ':' || d.ordinal_position || ':' ||
               d.column_name || ':' || d.data_type,
               ', ' ORDER BY d.view_name, d.ordinal_position
           )
      INTO column_differences
      FROM differences d;

    IF column_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 024 exact column contracts differ: %',
            column_differences;
    END IF;
END
$columns$;

DO $definitions_dependencies$
DECLARE
    definition_differences text;
    dependency_differences text;
BEGIN
    WITH expected(view_name, definition) AS (
        VALUES
            (
                'competitor_reference_plan_source',
                $view$SELECT 'PROFILE'::text AS record_kind,
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
 SELECT 'SKU_OEM'::text AS record_kind,
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
 SELECT 'MEMBERSHIP_QUERY'::text AS record_kind,
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
     JOIN public.competitor_product_families f ON f.product_family_id = l.product_family_id
     CROSS JOIN LATERAL unnest(m.matched_oem_set) q(query_text_exact)
     LEFT JOIN public.competitor_sku_oems o ON o.offer_id = m.offer_id AND o.oem_normalized = q.query_text_exact;$view$
            ),
            (
                'competitor_snapshot_runs',
                $view$SELECT search_run_id,
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
   FROM public.competitor_search_runs r;$view$
            ),
            (
                'competitor_snapshot_observations',
                $view$SELECT o.observation_id,
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
     LEFT JOIN public.competitor_watchlist_memberships m ON m.membership_id = o.membership_id;$view$
            ),
            (
                'competitor_finding_sets_reconciliation',
                $view$SELECT finding_set_id,
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
   FROM public.competitor_finding_sets s;$view$
            )
    ),
    actual AS (
        SELECT c.relname::text AS view_name, pg_get_viewdef(c.oid, true) AS definition
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relname IN (
               'competitor_reference_plan_source',
               'competitor_snapshot_runs',
               'competitor_snapshot_observations',
               'competitor_finding_sets_reconciliation'
           )
    ),
    differences AS (
        SELECT COALESCE(e.view_name, a.view_name) AS view_name
          FROM expected e
          FULL JOIN actual a USING (view_name)
         WHERE regexp_replace(btrim(e.definition), '[[:space:]]+', ' ', 'g')
               IS DISTINCT FROM
               regexp_replace(btrim(a.definition), '[[:space:]]+', ' ', 'g')
    )
    SELECT string_agg(d.view_name, ', ' ORDER BY d.view_name)
      INTO definition_differences
      FROM differences d;

    IF definition_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 024 exact view definitions differ: %',
            definition_differences;
    END IF;

    WITH expected(view_name, source_table) AS (
        VALUES
            ('competitor_reference_plan_source', 'competitor_sku_profiles'),
            ('competitor_reference_plan_source', 'competitor_sku_oems'),
            ('competitor_reference_plan_source', 'competitor_watchlist_memberships'),
            ('competitor_reference_plan_source', 'competitor_listings'),
            ('competitor_reference_plan_source', 'competitor_product_families'),
            ('competitor_snapshot_runs', 'competitor_search_runs'),
            ('competitor_snapshot_observations', 'competitor_observations'),
            ('competitor_snapshot_observations', 'competitor_listings'),
            ('competitor_snapshot_observations', 'competitor_watchlist_memberships'),
            ('competitor_finding_sets_reconciliation', 'competitor_finding_sets')
    ),
    actual AS (
        SELECT u.view_name::text, u.table_name::text AS source_table
          FROM information_schema.view_table_usage u
         WHERE u.view_schema = 'mcp_read'
           AND u.view_name IN (
               'competitor_reference_plan_source',
               'competitor_snapshot_runs',
               'competitor_snapshot_observations',
               'competitor_finding_sets_reconciliation'
           )
           AND u.table_schema = 'public'
    ),
    differences AS (
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        UNION ALL
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(
               d.view_name || ':' || d.source_table,
               ', ' ORDER BY d.view_name, d.source_table
           )
      INTO dependency_differences
      FROM differences d;

    IF dependency_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 024 exact source dependencies differ: %',
            dependency_differences;
    END IF;
END
$definitions_dependencies$;

DO $reference_invariants$
BEGIN
    -- Every historical membership is exposed by the reference-plan source.
    -- Array values are already canonical competitor_sku_oems.oem_normalized
    -- values, so comparison remains exact and does not introduce normalization.
    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships m
         WHERE m.matched_oem_set IS NULL
            OR cardinality(m.matched_oem_set) = 0
    ) THEN
        RAISE EXCEPTION 'Reference-plan membership has NULL or empty matched_oem_set';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships m
         WHERE array_position(m.matched_oem_set, NULL) IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Reference-plan membership has NULL matched_oem_set element';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships m
         WHERE cardinality(m.matched_oem_set) <> (
             SELECT count(DISTINCT q.query_text_exact)
               FROM unnest(m.matched_oem_set) q(query_text_exact)
         )
    ) THEN
        RAISE EXCEPTION 'Reference-plan membership has duplicate normalized OEM';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships m
          CROSS JOIN LATERAL unnest(m.matched_oem_set) WITH ORDINALITY
               q(query_text_exact, element_ordinal)
         WHERE (
             SELECT count(*)
               FROM public.competitor_sku_oems o
              WHERE o.offer_id = m.offer_id
                AND o.oem_normalized = q.query_text_exact
         ) <> 1
    ) THEN
        RAISE EXCEPTION 'Reference-plan membership OEM does not resolve exactly once';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM mcp_read.competitor_reference_plan_source v
         WHERE v.record_kind = 'MEMBERSHIP_QUERY'
           AND (
               v.query_text_exact IS NULL
               OR v.sku_oem_id IS NULL
               OR v.query_normalized IS DISTINCT FROM v.query_text_exact
           )
    ) THEN
        RAISE EXCEPTION 'MEMBERSHIP_QUERY contains an unresolved or NULL query';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM mcp_read.competitor_reference_plan_source v
         WHERE v.record_kind = 'MEMBERSHIP_QUERY'
         GROUP BY v.membership_id, v.query_text_exact
        HAVING count(*) <> 1
    ) THEN
        RAISE EXCEPTION 'MEMBERSHIP_QUERY deterministic grain is duplicated';
    END IF;
END
$reference_invariants$;

DO $reference_invariant_cases$
DECLARE
    case_differences text;
BEGIN
    WITH synthetic_oems(offer_id, oem_normalized) AS (
        VALUES
            ('SKU', 'OEM1'),
            ('SKU', 'OEM2'),
            ('SKU', 'AMBIGUOUS'),
            ('SKU', 'AMBIGUOUS')
    ),
    cases(case_name, offer_id, matched_oem_set, expected_valid) AS (
        VALUES
            ('EMPTY', 'SKU', ARRAY[]::text[], false),
            ('DUPLICATE', 'SKU', ARRAY['OEM1', 'OEM1']::text[], false),
            ('UNKNOWN', 'SKU', ARRAY['UNKNOWN']::text[], false),
            ('AMBIGUOUS', 'SKU', ARRAY['AMBIGUOUS']::text[], false),
            ('VALID', 'SKU', ARRAY['OEM1', 'OEM2']::text[], true)
    ),
    evaluated AS (
        SELECT
            c.case_name,
            c.expected_valid,
            c.matched_oem_set IS NOT NULL
            AND cardinality(c.matched_oem_set) > 0
            AND array_position(c.matched_oem_set, NULL) IS NULL
            AND cardinality(c.matched_oem_set) = (
                SELECT count(DISTINCT q.query_text_exact)
                  FROM unnest(c.matched_oem_set) q(query_text_exact)
            )
            AND NOT EXISTS (
                SELECT 1
                  FROM unnest(c.matched_oem_set) WITH ORDINALITY
                       q(query_text_exact, element_ordinal)
                 WHERE (
                     SELECT count(*)
                       FROM synthetic_oems o
                      WHERE o.offer_id = c.offer_id
                        AND o.oem_normalized = q.query_text_exact
                 ) <> 1
            ) AS actual_valid
          FROM cases c
    )
    SELECT string_agg(e.case_name, ', ' ORDER BY e.case_name)
      INTO case_differences
      FROM evaluated e
     WHERE e.actual_valid IS DISTINCT FROM e.expected_valid;

    IF case_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Reference invariant negative cases differ: %',
            case_differences;
    END IF;
END
$reference_invariant_cases$;

DO $source_rls$
DECLARE
    source_differences text;
BEGIN
    SELECT string_agg(c.relname, ', ' ORDER BY c.relname)
      INTO source_differences
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
       );

    IF source_differences IS NOT NULL OR (
        SELECT count(*)
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
    ) <> 8 THEN
        RAISE EXCEPTION 'Source ownership/type/RLS contract differs: %',
            COALESCE(source_differences, 'missing source');
    END IF;
END
$source_rls$;

DO $rules_triggers$
DECLARE
    rule_differences text;
    trigger_differences text;
BEGIN
    WITH targets AS (
        SELECT c.oid, c.relname::text AS view_name
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relname IN (
               'competitor_reference_plan_source',
               'competitor_snapshot_runs',
               'competitor_snapshot_observations',
               'competitor_finding_sets_reconciliation'
           )
    ),
    rule_state AS (
        SELECT
            t.view_name,
            count(r.oid) AS rule_count,
            count(r.oid) FILTER (
                WHERE r.rulename = '_RETURN'
                  AND r.ev_type = '1'
                  AND r.ev_enabled = 'O'
                  AND r.is_instead
            ) AS exact_return_count
          FROM targets t
          LEFT JOIN pg_rewrite r ON r.ev_class = t.oid
         GROUP BY t.view_name
    )
    SELECT string_agg(s.view_name, ', ' ORDER BY s.view_name)
      INTO rule_differences
      FROM rule_state s
     WHERE s.rule_count <> 1 OR s.exact_return_count <> 1;

    IF rule_differences IS NOT NULL THEN
        RAISE EXCEPTION 'View rewrite-rule contract differs: %', rule_differences;
    END IF;

    SELECT string_agg(c.relname, ', ' ORDER BY c.relname)
      INTO trigger_differences
      FROM pg_trigger t
      JOIN pg_class c ON c.oid = t.tgrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'mcp_read'
       AND c.relname IN (
           'competitor_reference_plan_source',
           'competitor_snapshot_runs',
           'competitor_snapshot_observations',
           'competitor_finding_sets_reconciliation'
       )
       AND NOT t.tgisinternal;

    IF trigger_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Unexpected non-internal view triggers: %',
            trigger_differences;
    END IF;
END
$rules_triggers$;

DO $acl$
DECLARE
    target_view oid;
    target_name text;
    owner_oid oid := 'efa'::regrole::oid;
    reader_oid oid := 'efa_mcp_reader'::regrole::oid;
    readonly_oid oid := 'efa_mcp_readonly'::regrole::oid;
BEGIN
    IF NOT has_schema_privilege('efa_mcp_reader', 'mcp_read', 'USAGE')
       OR has_schema_privilege('efa_mcp_reader', 'mcp_read', 'CREATE')
       OR NOT has_schema_privilege('efa_mcp_readonly', 'mcp_read', 'USAGE')
       OR has_schema_privilege('efa_mcp_readonly', 'mcp_read', 'CREATE')
       OR has_schema_privilege('efa_mcp_reader', 'public', 'USAGE')
       OR has_schema_privilege('efa_mcp_readonly', 'public', 'USAGE')
       OR has_schema_privilege('efa_mcp_reader', 'public', 'CREATE')
       OR has_schema_privilege('efa_mcp_readonly', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'MCP schema ACL contract differs';
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
        RAISE EXCEPTION 'PUBLIC has a direct schema privilege';
    END IF;

    FOR target_name, target_view IN
        SELECT c.relname, c.oid
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relname IN (
               'competitor_reference_plan_source',
               'competitor_snapshot_runs',
               'competitor_snapshot_observations',
               'competitor_finding_sets_reconciliation'
           )
         ORDER BY c.relname
    LOOP
        IF NOT has_table_privilege('efa_mcp_reader', target_view, 'SELECT')
           OR NOT has_table_privilege('efa_mcp_readonly', target_view, 'SELECT')
           OR has_table_privilege('efa_mcp_reader', target_view, 'INSERT')
           OR has_table_privilege('efa_mcp_reader', target_view, 'UPDATE')
           OR has_table_privilege('efa_mcp_reader', target_view, 'DELETE')
           OR has_table_privilege('efa_mcp_reader', target_view, 'TRUNCATE')
           OR has_table_privilege('efa_mcp_reader', target_view, 'REFERENCES')
           OR has_table_privilege('efa_mcp_reader', target_view, 'TRIGGER')
           OR has_table_privilege('efa_mcp_readonly', target_view, 'INSERT')
           OR has_table_privilege('efa_mcp_readonly', target_view, 'UPDATE')
           OR has_table_privilege('efa_mcp_readonly', target_view, 'DELETE')
           OR has_table_privilege('efa_mcp_readonly', target_view, 'TRUNCATE')
           OR has_table_privilege('efa_mcp_readonly', target_view, 'REFERENCES')
           OR has_table_privilege('efa_mcp_readonly', target_view, 'TRIGGER') THEN
            RAISE EXCEPTION 'Effective SELECT-only ACL differs for %', target_name;
        END IF;

        IF EXISTS (
            WITH expected AS (
                SELECT x.grantee, x.grantor, x.privilege_type, x.is_grantable
                  FROM aclexplode(acldefault('r', owner_oid)) x
                UNION ALL
                SELECT reader_oid, owner_oid, 'SELECT'::text, false
            ),
            actual AS (
                SELECT x.grantee, x.grantor, x.privilege_type, x.is_grantable
                  FROM pg_class c
                  CROSS JOIN LATERAL aclexplode(
                      COALESCE(c.relacl, acldefault('r', c.relowner))
                  ) x
                 WHERE c.oid = target_view
            )
            (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
            UNION ALL
            (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        ) OR EXISTS (
            SELECT 1
              FROM pg_class c
              CROSS JOIN LATERAL aclexplode(
                  COALESCE(c.relacl, acldefault('r', c.relowner))
              ) acl
             WHERE c.oid = target_view
               AND acl.grantee = readonly_oid
        ) THEN
            RAISE EXCEPTION 'Direct ACL differs for %', target_name;
        END IF;
    END LOOP;
END
$acl$;

DO $raw_acl$
DECLARE
    restricted_roles oid[];
BEGIN
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
        RAISE EXCEPTION 'Raw competitor table CRUD ACL is not closed';
    END IF;
END
$raw_acl$;

DO $source_equivalence$
BEGIN
    IF EXISTS (
        (
            SELECT * FROM mcp_read.competitor_reference_plan_source
            EXCEPT ALL
            (
                SELECT
                    'PROFILE'::text,
                    p.offer_id,
                    p.watchlist_state,
                    NULL::uuid,
                    NULL::text,
                    NULL::text,
                    NULL::boolean,
                    NULL::timestamptz,
                    NULL::uuid,
                    NULL::text,
                    NULL::text[],
                    NULL::timestamptz,
                    NULL::timestamptz,
                    NULL::uuid,
                    NULL::uuid,
                    NULL::bigint,
                    NULL::text,
                    NULL::text
                FROM public.competitor_sku_profiles p
                UNION ALL
                SELECT
                    'SKU_OEM'::text,
                    p.offer_id,
                    p.watchlist_state,
                    o.sku_oem_id,
                    NULL::text,
                    o.oem_normalized,
                    o.active,
                    o.created_at,
                    NULL::uuid,
                    NULL::text,
                    NULL::text[],
                    NULL::timestamptz,
                    NULL::timestamptz,
                    NULL::uuid,
                    NULL::uuid,
                    NULL::bigint,
                    NULL::text,
                    NULL::text
                FROM public.competitor_sku_profiles p
                JOIN public.competitor_sku_oems o ON o.offer_id = p.offer_id
                UNION ALL
                SELECT
                    'MEMBERSHIP_QUERY'::text,
                    p.offer_id,
                    p.watchlist_state,
                    o.sku_oem_id,
                    q.query_text_exact,
                    o.oem_normalized,
                    o.active,
                    o.created_at,
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
                 AND o.oem_normalized = q.query_text_exact
            )
        )
        UNION ALL
        (
            (
                SELECT
                    'PROFILE'::text,
                    p.offer_id,
                    p.watchlist_state,
                    NULL::uuid,
                    NULL::text,
                    NULL::text,
                    NULL::boolean,
                    NULL::timestamptz,
                    NULL::uuid,
                    NULL::text,
                    NULL::text[],
                    NULL::timestamptz,
                    NULL::timestamptz,
                    NULL::uuid,
                    NULL::uuid,
                    NULL::bigint,
                    NULL::text,
                    NULL::text
                FROM public.competitor_sku_profiles p
                UNION ALL
                SELECT
                    'SKU_OEM'::text,
                    p.offer_id,
                    p.watchlist_state,
                    o.sku_oem_id,
                    NULL::text,
                    o.oem_normalized,
                    o.active,
                    o.created_at,
                    NULL::uuid,
                    NULL::text,
                    NULL::text[],
                    NULL::timestamptz,
                    NULL::timestamptz,
                    NULL::uuid,
                    NULL::uuid,
                    NULL::bigint,
                    NULL::text,
                    NULL::text
                FROM public.competitor_sku_profiles p
                JOIN public.competitor_sku_oems o ON o.offer_id = p.offer_id
                UNION ALL
                SELECT
                    'MEMBERSHIP_QUERY'::text,
                    p.offer_id,
                    p.watchlist_state,
                    o.sku_oem_id,
                    q.query_text_exact,
                    o.oem_normalized,
                    o.active,
                    o.created_at,
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
                 AND o.oem_normalized = q.query_text_exact
            )
            EXCEPT ALL
            SELECT * FROM mcp_read.competitor_reference_plan_source
        )
    ) THEN
        RAISE EXCEPTION 'Reference-plan rows are not exactly source-equivalent';
    END IF;

    IF EXISTS (
        (SELECT * FROM mcp_read.competitor_snapshot_runs
         EXCEPT ALL
         SELECT search_run_id, offer_id, sku_oem_id, query_kind,
                query_text_exact, query_normalized, region_key, location_label,
                captured_at, status, page_count_observed, result_count_observed,
                collection_ref, raw_source_ref
           FROM public.competitor_search_runs)
        UNION ALL
        (SELECT search_run_id, offer_id, sku_oem_id, query_kind,
                query_text_exact, query_normalized, region_key, location_label,
                captured_at, status, page_count_observed, result_count_observed,
                collection_ref, raw_source_ref
           FROM public.competitor_search_runs
         EXCEPT ALL
         SELECT * FROM mcp_read.competitor_snapshot_runs)
    ) THEN
        RAISE EXCEPTION 'Snapshot-run rows are not exactly source-equivalent';
    END IF;

    IF EXISTS (
        (SELECT * FROM mcp_read.competitor_snapshot_observations
         EXCEPT ALL
         SELECT o.observation_id, o.search_run_id, o.listing_id, o.membership_id,
                l.ozon_product_id, m.membership_status, o.captured_at,
                o.enrichment_captured_at, o.page_number, o.position_on_page,
                o.rank, o.ad_flag, o.bank_price, o.other_payment_price,
                o.old_price, o.currency, o.rating, o.reviews_count_observed,
                o.reviews_scope, o.purchase_count_observed,
                o.purchase_indicator_raw, o.availability_status,
                o.availability_raw, o.observed_oem_raw,
                o.observed_dimensions_raw, o.observed_length_mm,
                o.observed_width_mm, o.observed_height_mm, o.carbon_claim_raw,
                o.origin_raw, o.quality_status, o.quality_flags, o.source_ref,
                o.raw_ref, o.observation_ref
           FROM public.competitor_observations o
           JOIN public.competitor_listings l ON l.listing_id = o.listing_id
           LEFT JOIN public.competitor_watchlist_memberships m
             ON m.membership_id = o.membership_id)
        UNION ALL
        (SELECT o.observation_id, o.search_run_id, o.listing_id, o.membership_id,
                l.ozon_product_id, m.membership_status, o.captured_at,
                o.enrichment_captured_at, o.page_number, o.position_on_page,
                o.rank, o.ad_flag, o.bank_price, o.other_payment_price,
                o.old_price, o.currency, o.rating, o.reviews_count_observed,
                o.reviews_scope, o.purchase_count_observed,
                o.purchase_indicator_raw, o.availability_status,
                o.availability_raw, o.observed_oem_raw,
                o.observed_dimensions_raw, o.observed_length_mm,
                o.observed_width_mm, o.observed_height_mm, o.carbon_claim_raw,
                o.origin_raw, o.quality_status, o.quality_flags, o.source_ref,
                o.raw_ref, o.observation_ref
           FROM public.competitor_observations o
           JOIN public.competitor_listings l ON l.listing_id = o.listing_id
           LEFT JOIN public.competitor_watchlist_memberships m
             ON m.membership_id = o.membership_id
         EXCEPT ALL
         SELECT * FROM mcp_read.competitor_snapshot_observations)
    ) THEN
        RAISE EXCEPTION 'Snapshot-observation rows are not exactly source-equivalent';
    END IF;

    IF EXISTS (
        (SELECT * FROM mcp_read.competitor_finding_sets_reconciliation
         EXCEPT ALL
         SELECT finding_set_id, set_key, persistence_contract_version,
                finding_set_contract_version, source_analysis_contract_version,
                source_findings_sha256, source_findings_semantic_sha256,
                source_analysis_sha256, previous_source_kind,
                previous_derived_batch_id, previous_reference_at,
                previous_captured_through, current_source_kind,
                current_derived_batch_id, current_reference_at,
                current_captured_through, expected_findings_count
           FROM public.competitor_finding_sets)
        UNION ALL
        (SELECT finding_set_id, set_key, persistence_contract_version,
                finding_set_contract_version, source_analysis_contract_version,
                source_findings_sha256, source_findings_semantic_sha256,
                source_analysis_sha256, previous_source_kind,
                previous_derived_batch_id, previous_reference_at,
                previous_captured_through, current_source_kind,
                current_derived_batch_id, current_reference_at,
                current_captured_through, expected_findings_count
           FROM public.competitor_finding_sets
         EXCEPT ALL
         SELECT * FROM mcp_read.competitor_finding_sets_reconciliation)
    ) THEN
        RAISE EXCEPTION 'Finding-set reconciliation rows are not exactly source-equivalent';
    END IF;
END
$source_equivalence$;

DO $historical_contract$
DECLARE
    t1_reference constant timestamptz := '2026-08-26T06:14:43.028Z';
    query_count integer;
    slot_count integer;
    t0_runs integer;
    t0_observations integer;
    t1_runs integer;
    t1_observations integer;
BEGIN
    SELECT count(DISTINCT (offer_id, query_text_exact)), count(*)
      INTO query_count, slot_count
      FROM mcp_read.competitor_reference_plan_source
     WHERE record_kind = 'MEMBERSHIP_QUERY'
       AND membership_status IN ('CONTROL', 'PRIMARY', 'RESERVE')
       AND valid_from <= t1_reference
       AND (valid_to IS NULL OR t1_reference < valid_to)
       AND oem_created_at <= t1_reference
       AND sku_oem_id IS NOT NULL
       AND query_text_exact IS NOT NULL
       AND query_normalized IS NOT NULL;

    IF query_count <> 9 OR slot_count <> 87 THEN
        RAISE EXCEPTION 'Historical T1 reference plan differs: queries %, slots %',
            query_count, slot_count;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM mcp_read.competitor_reference_plan_source
         WHERE record_kind = 'MEMBERSHIP_QUERY'
           AND membership_status IN ('CONTROL', 'PRIMARY', 'RESERVE')
           AND valid_from <= t1_reference
           AND (valid_to IS NULL OR t1_reference < valid_to)
           AND (
               query_text_exact IS NULL
               OR sku_oem_id IS NULL
               OR query_normalized IS DISTINCT FROM query_text_exact
               OR NOT query_text_exact = ANY (matched_oem_set)
           )
    ) THEN
        RAISE EXCEPTION 'Historical T1 membership/OEM reconciliation differs';
    END IF;

    SELECT
        count(DISTINCT r.search_run_id),
        count(o.observation_id)
      INTO t0_runs, t0_observations
      FROM mcp_read.competitor_snapshot_runs r
      JOIN mcp_read.competitor_snapshot_observations o
        ON o.search_run_id = r.search_run_id
     WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%';

    SELECT
        count(DISTINCT r.search_run_id),
        count(o.observation_id)
      INTO t1_runs, t1_observations
      FROM mcp_read.competitor_snapshot_runs r
      JOIN mcp_read.competitor_snapshot_observations o
        ON o.search_run_id = r.search_run_id
     WHERE r.collection_ref LIKE 'cm-snapshot-v1:run:%';

    IF t0_runs <> 9 OR t0_observations <> 87
       OR t1_runs <> 9 OR t1_observations <> 87 THEN
        RAISE EXCEPTION 'T0/T1 snapshot-history contract differs: T0 %/%, T1 %/%',
            t0_runs, t0_observations, t1_runs, t1_observations;
    END IF;

    IF EXISTS (
        WITH batches(source_kind, reference_at) AS (
            SELECT
                CASE
                    WHEN r.collection_ref LIKE 'cm-baseline-v1:run:%'
                        THEN 'T0'
                    ELSE 'T1'
                END,
                min(r.captured_at)
              FROM mcp_read.competitor_snapshot_runs r
             WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%'
                OR r.collection_ref LIKE 'cm-snapshot-v1:run:%'
             GROUP BY 1
        ),
        expected_queries AS (
            SELECT DISTINCT
                b.source_kind,
                v.offer_id,
                v.query_text_exact
              FROM batches b
              JOIN mcp_read.competitor_reference_plan_source v
                ON v.record_kind = 'MEMBERSHIP_QUERY'
               AND v.membership_status IN ('CONTROL', 'PRIMARY', 'RESERVE')
               AND v.valid_from <= b.reference_at
               AND (v.valid_to IS NULL OR b.reference_at < v.valid_to)
               AND v.oem_created_at <= b.reference_at
               AND v.sku_oem_id IS NOT NULL
        ),
        actual_queries AS (
            SELECT DISTINCT
                CASE
                    WHEN r.collection_ref LIKE 'cm-baseline-v1:run:%'
                        THEN 'T0'
                    ELSE 'T1'
                END AS source_kind,
                r.offer_id,
                r.query_text_exact
              FROM mcp_read.competitor_snapshot_runs r
             WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%'
                OR r.collection_ref LIKE 'cm-snapshot-v1:run:%'
        )
        (SELECT * FROM expected_queries EXCEPT ALL SELECT * FROM actual_queries)
        UNION ALL
        (SELECT * FROM actual_queries EXCEPT ALL SELECT * FROM expected_queries)
    ) THEN
        RAISE EXCEPTION 'T0/T1 exact query sets differ from historical reference plans';
    END IF;

    IF EXISTS (
        WITH batches(source_kind, reference_at) AS (
            SELECT
                CASE
                    WHEN r.collection_ref LIKE 'cm-baseline-v1:run:%'
                        THEN 'T0'
                    ELSE 'T1'
                END,
                min(r.captured_at)
              FROM mcp_read.competitor_snapshot_runs r
             WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%'
                OR r.collection_ref LIKE 'cm-snapshot-v1:run:%'
             GROUP BY 1
        ),
        expected_slots AS (
            SELECT
                b.source_kind,
                v.offer_id,
                v.query_text_exact,
                v.ozon_product_id
              FROM batches b
              JOIN mcp_read.competitor_reference_plan_source v
                ON v.record_kind = 'MEMBERSHIP_QUERY'
               AND v.membership_status IN ('CONTROL', 'PRIMARY', 'RESERVE')
               AND v.valid_from <= b.reference_at
               AND (v.valid_to IS NULL OR b.reference_at < v.valid_to)
               AND v.oem_created_at <= b.reference_at
               AND v.sku_oem_id IS NOT NULL
        ),
        actual_slots AS (
            SELECT
                CASE
                    WHEN r.collection_ref LIKE 'cm-baseline-v1:run:%'
                        THEN 'T0'
                    ELSE 'T1'
                END AS source_kind,
                r.offer_id,
                r.query_text_exact,
                o.ozon_product_id
              FROM mcp_read.competitor_snapshot_runs r
              JOIN mcp_read.competitor_snapshot_observations o
                ON o.search_run_id = r.search_run_id
             WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%'
                OR r.collection_ref LIKE 'cm-snapshot-v1:run:%'
        )
        (SELECT * FROM expected_slots EXCEPT ALL SELECT * FROM actual_slots)
        UNION ALL
        (SELECT * FROM actual_slots EXCEPT ALL SELECT * FROM expected_slots)
    ) THEN
        RAISE EXCEPTION 'T0/T1 exact logical slots differ from historical reference plans';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM mcp_read.competitor_snapshot_runs r
         WHERE (r.collection_ref LIKE 'cm-baseline-v1:run:%'
                OR r.collection_ref LIKE 'cm-snapshot-v1:run:%')
           AND r.status <> 'SUCCESS'
    ) OR (
        SELECT count(DISTINCT r.region_key)
          FROM mcp_read.competitor_snapshot_runs r
         WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%'
            OR r.collection_ref LIKE 'cm-snapshot-v1:run:%'
    ) <> 1 THEN
        RAISE EXCEPTION 'T0/T1 run status or region contract differs';
    END IF;

    IF (SELECT count(*) FROM mcp_read.competitor_snapshot_runs) <> 18
       OR (SELECT count(*) FROM mcp_read.competitor_snapshot_observations) <> 174 THEN
        RAISE EXCEPTION 'Expected current snapshot history 18/174';
    END IF;
END
$historical_contract$;

DO $existing_surfaces$
DECLARE
    view_differences text;
    function_differences text;
BEGIN
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
                E'\n', c.relname, c.relkind::text,
                pg_get_userbyid(c.relowner),
                COALESCE(
                    (SELECT string_agg(x.option, ',' ORDER BY x.option)
                       FROM unnest(c.reloptions) x(option)), ''
                ),
                COALESCE(
                    (SELECT string_agg(
                                format('%s:%s:%s', a.attnum, a.attname,
                                       format_type(a.atttypid, a.atttypmod)),
                                ',' ORDER BY a.attnum)
                       FROM pg_attribute a
                      WHERE a.attrelid = c.oid
                        AND a.attnum > 0
                        AND NOT a.attisdropped), ''
                ),
                pg_get_viewdef(c.oid, true),
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
                                COALESCE(c.relacl, acldefault('r', c.relowner))
                            ) x), ''
                )
            )) AS fingerprint
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relname IN (
               'competitor_findings',
               'competitor_latest_finding_set',
               'competitor_monitoring_coverage',
               'product_cpc_daily',
               'product_daily_performance',
               'product_overview',
               'product_price_history',
               'product_promotion_state',
               'product_region_logistics',
               'product_stock_history'
           )
    ),
    differences AS (
        SELECT COALESCE(e.view_name, a.view_name) AS view_name
          FROM expected e
          FULL JOIN actual a USING (view_name)
         WHERE e.fingerprint IS DISTINCT FROM a.fingerprint
    )
    SELECT string_agg(d.view_name, ', ' ORDER BY d.view_name)
      INTO view_differences
      FROM differences d;

    IF view_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Existing view fingerprints differ: %', view_differences;
    END IF;

    WITH expected(function_name, fingerprint) AS (
        VALUES (
            'product_period_economics(date,date)',
            'cf16870f884f2177f2ff4492c6344502'
        )
    ),
    actual AS (
        SELECT
            'product_period_economics(date,date)'::text AS function_name,
            md5(concat_ws(
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
            )) AS fingerprint
          FROM pg_proc p
         WHERE p.oid = to_regprocedure(
             'mcp_read.product_period_economics(date,date)'
         )
    ),
    differences AS (
        SELECT COALESCE(e.function_name, a.function_name) AS function_name
          FROM expected e
          FULL JOIN actual a USING (function_name)
         WHERE e.fingerprint IS DISTINCT FROM a.fingerprint
    )
    SELECT string_agg(d.function_name, ', ' ORDER BY d.function_name)
      INTO function_differences
      FROM differences d;

    IF function_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Existing function fingerprint differs: %',
            function_differences;
    END IF;
END
$existing_surfaces$;

SELECT
    (SELECT count(*) FROM mcp_read.competitor_snapshot_runs) AS search_runs,
    (SELECT count(*) FROM mcp_read.competitor_snapshot_observations) AS observations,
    (SELECT count(*) FROM mcp_read.competitor_finding_sets_reconciliation) AS finding_sets,
    has_table_privilege(
        'efa_mcp_readonly',
        'mcp_read.competitor_reference_plan_source',
        'SELECT'
    ) AS readonly_reference_plan_select,
    has_table_privilege(
        'efa_mcp_readonly',
        'mcp_read.competitor_snapshot_runs',
        'SELECT'
    ) AS readonly_snapshot_runs_select,
    has_table_privilege(
        'efa_mcp_readonly',
        'mcp_read.competitor_snapshot_observations',
        'SELECT'
    ) AS readonly_snapshot_observations_select,
    has_table_privilege(
        'efa_mcp_readonly',
        'mcp_read.competitor_finding_sets_reconciliation',
        'SELECT'
    ) AS readonly_finding_sets_select;

ROLLBACK;
