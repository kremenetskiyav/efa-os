-- Post-deployment validation for
-- 018_competitor_monitor_data_layer_v1.sql.
-- The validation transaction is read-only and leaves no database changes.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    missing_tables text[];
BEGIN
    SELECT array_agg(expected.table_name ORDER BY expected.table_name)
      INTO missing_tables
      FROM (
        VALUES
            ('competitor_sku_profiles'),
            ('competitor_sku_oems'),
            ('competitor_product_families'),
            ('competitor_listings'),
            ('competitor_watchlist_memberships'),
            ('competitor_search_runs'),
            ('competitor_observations'),
            ('competitor_reviews'),
            ('competitor_findings')
      ) AS expected(table_name)
     WHERE to_regclass('public.' || expected.table_name) IS NULL;

    IF missing_tables IS NOT NULL THEN
        RAISE EXCEPTION 'Missing Competitor Monitor tables: %', missing_tables;
    END IF;
END $$;

DO $$
DECLARE
    missing_constraints text[];
BEGIN
    SELECT array_agg(expected.constraint_name ORDER BY expected.constraint_name)
      INTO missing_constraints
      FROM (
        VALUES
            ('competitor_sku_profiles', 'competitor_sku_profiles_pkey', 'p'),
            ('competitor_sku_profiles', 'competitor_sku_profiles_offer_id_fkey', 'f'),
            ('competitor_sku_oems', 'competitor_sku_oems_pkey', 'p'),
            ('competitor_sku_oems', 'competitor_sku_oems_offer_id_fkey', 'f'),
            ('competitor_sku_oems', 'competitor_sku_oems_offer_normalized_key', 'u'),
            ('competitor_sku_oems', 'competitor_sku_oems_offer_sku_oem_key', 'u'),
            ('competitor_product_families', 'competitor_product_families_pkey', 'p'),
            ('competitor_listings', 'competitor_listings_pkey', 'p'),
            ('competitor_listings', 'competitor_listings_product_family_id_fkey', 'f'),
            ('competitor_listings', 'competitor_listings_product_seller_key', 'u'),
            ('competitor_watchlist_memberships', 'competitor_watchlist_memberships_pkey', 'p'),
            ('competitor_watchlist_memberships', 'competitor_watchlist_memberships_offer_id_fkey', 'f'),
            ('competitor_watchlist_memberships', 'competitor_watchlist_memberships_listing_id_fkey', 'f'),
            ('competitor_search_runs', 'competitor_search_runs_pkey', 'p'),
            ('competitor_search_runs', 'competitor_search_runs_offer_id_fkey', 'f'),
            ('competitor_search_runs', 'competitor_search_runs_offer_sku_oem_fkey', 'f'),
            ('competitor_search_runs', 'competitor_search_runs_collection_ref_key', 'u'),
            ('competitor_observations', 'competitor_observations_pkey', 'p'),
            ('competitor_observations', 'competitor_observations_search_run_id_fkey', 'f'),
            ('competitor_observations', 'competitor_observations_listing_id_fkey', 'f'),
            ('competitor_observations', 'competitor_observations_membership_id_fkey', 'f'),
            ('competitor_observations', 'competitor_observations_observation_ref_key', 'u'),
            ('competitor_reviews', 'competitor_reviews_pkey', 'p'),
            ('competitor_reviews', 'competitor_reviews_listing_id_fkey', 'f'),
            ('competitor_reviews', 'competitor_reviews_dedupe_key_key', 'u'),
            ('competitor_findings', 'competitor_findings_pkey', 'p'),
            ('competitor_findings', 'competitor_findings_offer_id_fkey', 'f'),
            ('competitor_findings', 'competitor_findings_product_family_id_fkey', 'f'),
            ('competitor_findings', 'competitor_findings_listing_id_fkey', 'f'),
            ('competitor_findings', 'competitor_findings_old_observation_id_fkey', 'f'),
            ('competitor_findings', 'competitor_findings_new_observation_id_fkey', 'f'),
            ('competitor_findings', 'competitor_findings_finding_key_key', 'u')
      ) AS expected(table_name, constraint_name, constraint_type)
     WHERE NOT EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.conrelid = ('public.' || expected.table_name)::regclass
           AND c.conname = expected.constraint_name
           AND c.contype = expected.constraint_type::"char"
     );

    IF missing_constraints IS NOT NULL THEN
        RAISE EXCEPTION 'Missing or invalid PK/FK/UNIQUE constraints: %',
            missing_constraints;
    END IF;
END $$;

DO $$
DECLARE
    missing_checks text[];
BEGIN
    SELECT array_agg(expected.constraint_name ORDER BY expected.constraint_name)
      INTO missing_checks
      FROM (
        VALUES
            ('competitor_sku_profiles', 'competitor_sku_profiles_watchlist_state_check'),
            ('competitor_sku_oems', 'competitor_sku_oems_confidence_check'),
            ('competitor_product_families', 'competitor_product_families_carbon_confidence_check'),
            ('competitor_watchlist_memberships', 'competitor_watchlist_memberships_status_check'),
            ('competitor_watchlist_memberships', 'competitor_watchlist_memberships_oem_confidence_check'),
            ('competitor_search_runs', 'competitor_search_runs_query_kind_check'),
            ('competitor_observations', 'competitor_observations_reviews_scope_check'),
            ('competitor_reviews', 'competitor_reviews_scope_check'),
            ('competitor_findings', 'competitor_findings_kind_check')
      ) AS expected(table_name, constraint_name)
     WHERE NOT EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.conrelid = ('public.' || expected.table_name)::regclass
           AND c.conname = expected.constraint_name
           AND c.contype = 'c'
           AND c.convalidated
     );

    IF missing_checks IS NOT NULL THEN
        RAISE EXCEPTION 'Missing or unvalidated expected CHECK constraints: %',
            missing_checks;
    END IF;
END $$;

DO $$
DECLARE
    expected record;
    actual_definition text;
    actual_predicate text;
    actual_unique boolean;
BEGIN
    FOR expected IN
        SELECT *
          FROM (
        VALUES
            (
                'competitor_sku_oems_normalized_idx',
                false,
                '(oem_normalized)',
                NULL
            ),
            (
                'competitor_watchlist_one_active_pair_uidx',
                true,
                '(offer_id, listing_id)',
                '(valid_to IS NULL)'
            ),
            (
                'competitor_watchlist_active_status_idx',
                false,
                '(offer_id, membership_status)',
                '(valid_to IS NULL)'
            ),
            (
                'competitor_search_history_idx',
                false,
                '(offer_id, query_normalized, region_key, captured_at DESC)',
                NULL
            ),
            (
                'competitor_observations_run_position_uidx',
                true,
                '(search_run_id, page_number, position_on_page)',
                '((page_number IS NOT NULL) AND (position_on_page IS NOT NULL))'
            ),
            (
                'competitor_observations_search_rank_idx',
                false,
                '(search_run_id, rank)',
                NULL
            ),
            (
                'competitor_observations_listing_history_idx',
                false,
                '(listing_id, captured_at DESC)',
                NULL
            ),
            (
                'competitor_reviews_listing_published_idx',
                false,
                '(listing_id, published_at DESC)',
                NULL
            ),
            (
                'competitor_findings_offer_kind_status_last_idx',
                false,
                '(offer_id, finding_kind, status, last_detected_at DESC)',
                NULL
            )
          ) AS v(index_name, is_unique, key_sql, predicate_sql)
    LOOP
        SELECT
            i.indisunique,
            pg_get_indexdef(i.indexrelid),
            pg_get_expr(i.indpred, i.indrelid)
          INTO actual_unique, actual_definition, actual_predicate
          FROM pg_index i
         WHERE i.indexrelid = to_regclass('public.' || expected.index_name);

        IF actual_definition IS NULL
           OR actual_unique IS DISTINCT FROM expected.is_unique
           OR position(expected.key_sql IN actual_definition) = 0
           OR actual_predicate IS DISTINCT FROM expected.predicate_sql THEN
            RAISE EXCEPTION 'Missing or invalid critical index: %',
                expected.index_name;
        END IF;
    END LOOP;
END $$;

DO $$
DECLARE
    nullable_contract_count integer;
BEGIN
    SELECT count(*)
      INTO nullable_contract_count
      FROM information_schema.columns c
      JOIN (
        VALUES
            ('competitor_search_runs', 'sku_oem_id'),
            ('competitor_observations', 'membership_id'),
            ('competitor_observations', 'page_number'),
            ('competitor_observations', 'position_on_page'),
            ('competitor_observations', 'rank'),
            ('competitor_observations', 'ad_flag'),
            ('competitor_observations', 'bank_price'),
            ('competitor_observations', 'other_payment_price'),
            ('competitor_observations', 'old_price'),
            ('competitor_observations', 'rating'),
            ('competitor_observations', 'reviews_count_observed'),
            ('competitor_observations', 'purchase_count_observed'),
            ('competitor_observations', 'observed_length_mm'),
            ('competitor_observations', 'observed_width_mm'),
            ('competitor_observations', 'observed_height_mm'),
            ('competitor_reviews', 'source_review_id'),
            ('competitor_reviews', 'published_at'),
            ('competitor_reviews', 'rating'),
            ('competitor_reviews', 'author_marker')
      ) AS expected(table_name, column_name)
        ON c.table_schema = 'public'
       AND c.table_name = expected.table_name
       AND c.column_name = expected.column_name
       AND c.is_nullable = 'YES';

    IF nullable_contract_count <> 19 THEN
        RAISE EXCEPTION 'UNKNOWN/nullability contract is incomplete (%/19)',
            nullable_contract_count;
    END IF;

    IF position('UNKNOWN' IN pg_get_constraintdef(
        (
            SELECT c.oid
              FROM pg_constraint c
             WHERE c.conrelid = 'public.competitor_product_families'::regclass
               AND c.conname =
                   'competitor_product_families_carbon_confidence_check'
        )
    )) = 0 OR position('UNKNOWN' IN pg_get_constraintdef(
        (
            SELECT c.oid
              FROM pg_constraint c
             WHERE c.conrelid = 'public.competitor_observations'::regclass
               AND c.conname = 'competitor_observations_reviews_scope_check'
        )
    )) = 0 OR position('UNKNOWN' IN pg_get_constraintdef(
        (
            SELECT c.oid
              FROM pg_constraint c
             WHERE c.conrelid = 'public.competitor_reviews'::regclass
               AND c.conname = 'competitor_reviews_scope_check'
        )
    )) = 0 THEN
        RAISE EXCEPTION 'Expected UNKNOWN status semantics are missing';
    END IF;
END $$;

DO $$
DECLARE
    competitor_tables oid[] := ARRAY[
        'public.competitor_sku_profiles'::regclass::oid,
        'public.competitor_sku_oems'::regclass::oid,
        'public.competitor_product_families'::regclass::oid,
        'public.competitor_listings'::regclass::oid,
        'public.competitor_watchlist_memberships'::regclass::oid,
        'public.competitor_search_runs'::regclass::oid,
        'public.competitor_observations'::regclass::oid,
        'public.competitor_reviews'::regclass::oid,
        'public.competitor_findings'::regclass::oid
    ];
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.contype = 'f'
           AND (
               (
                   c.conrelid = ANY (competitor_tables)
                   AND c.confrelid IN (
                       'public.product_snapshots'::regclass,
                       'public.change_events'::regclass
                   )
               )
               OR (
                   c.confrelid = ANY (competitor_tables)
                   AND c.conrelid IN (
                       'public.product_snapshots'::regclass,
                       'public.change_events'::regclass
                   )
               )
           )
    ) THEN
        RAISE EXCEPTION 'Competitor tables are coupled to product_snapshots/change_events';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.contype = 'f'
           AND c.conrelid = ANY (competitor_tables)
           AND c.confrelid = 'public.products'::regclass
           AND (c.confdeltype NOT IN ('a', 'r') OR c.confupdtype <> 'a')
    ) THEN
        RAISE EXCEPTION 'A products FK can cascade writes into competitor data';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.contype = 'f'
           AND c.conrelid = 'public.products'::regclass
           AND c.confrelid = ANY (competitor_tables)
    ) THEN
        RAISE EXCEPTION 'public.products unexpectedly depends on competitor data';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_trigger t
         WHERE t.tgrelid = ANY (competitor_tables)
           AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'Unexpected write-capable trigger exists on a competitor table';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM information_schema.columns c
         WHERE c.table_schema = 'public'
           AND c.table_name = 'competitor_observations'
           AND c.column_name = 'comparison_price'
    ) THEN
        RAISE EXCEPTION 'comparison_price must not be stored as a collector fact';
    END IF;
END $$;

DO $$
DECLARE
    hold_constraint text;
BEGIN
    SELECT pg_get_constraintdef(c.oid)
      INTO hold_constraint
      FROM pg_constraint c
     WHERE c.conrelid = 'public.competitor_sku_profiles'::regclass
       AND c.conname = 'competitor_sku_profiles_watchlist_state_check';

    IF hold_constraint IS NULL OR position('HOLD' IN hold_constraint) = 0 THEN
        RAISE EXCEPTION 'competitor_sku_profiles does not allow HOLD';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.conrelid = 'public.competitor_sku_profiles'::regclass
           AND c.confrelid =
               'public.competitor_watchlist_memberships'::regclass
    ) OR EXISTS (
        SELECT 1
          FROM pg_trigger t
         WHERE t.tgrelid IN (
             'public.competitor_sku_profiles'::regclass,
             'public.competitor_watchlist_memberships'::regclass
         )
           AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'HOLD profile is incorrectly coupled to a PRIMARY membership';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships m
          JOIN public.competitor_listings l
            ON l.listing_id = m.listing_id
          JOIN public.competitor_product_families f
            ON f.product_family_id = l.product_family_id
         WHERE m.valid_to IS NULL
           AND m.membership_status = 'PRIMARY'
           AND f.carbon_confidence = 'NON_CARBON'
    ) THEN
        RAISE EXCEPTION 'An active PRIMARY membership points to NON_CARBON';
    END IF;
END $$;

SELECT
    9 AS competitor_tables,
    19 AS nullable_unknown_fields_checked,
    true AS sku_003b_hold_without_primary_supported,
    true AS non_carbon_primary_absent,
    true AS snapshot_change_event_decoupled,
    'PASS' AS status;

ROLLBACK;
