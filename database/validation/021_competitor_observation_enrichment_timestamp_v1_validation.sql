-- Post-deployment validation for
-- 021_competitor_observation_enrichment_timestamp_v1.sql.
-- The validation transaction is read-only and leaves no database changes.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    column_type text;
    column_not_null boolean;
    column_has_default boolean;
    column_identity "char";
    column_generated "char";
    column_acl aclitem[];
BEGIN
    SELECT
        format_type(a.atttypid, a.atttypmod),
        a.attnotnull,
        ad.adbin IS NOT NULL,
        a.attidentity,
        a.attgenerated,
        a.attacl
      INTO
        column_type,
        column_not_null,
        column_has_default,
        column_identity,
        column_generated,
        column_acl
      FROM pg_attribute a
      LEFT JOIN pg_attrdef ad
        ON ad.adrelid = a.attrelid
       AND ad.adnum = a.attnum
     WHERE a.attrelid = 'public.competitor_observations'::regclass
       AND a.attname = 'enrichment_captured_at'
       AND a.attnum > 0
       AND NOT a.attisdropped;

    IF column_type IS DISTINCT FROM 'timestamp with time zone'
       OR column_not_null IS DISTINCT FROM false
       OR column_has_default IS DISTINCT FROM false
       OR column_identity IS DISTINCT FROM ''
       OR column_generated IS DISTINCT FROM ''
       OR column_acl IS NOT NULL THEN
        RAISE EXCEPTION 'Invalid enrichment_captured_at column contract';
    END IF;
END $$;

DO $$
DECLARE
    missing_constraints text[];
    unexpected_constraint_count integer;
BEGIN
    SELECT array_agg(expected.constraint_name ORDER BY expected.constraint_name)
      INTO missing_constraints
      FROM (
        VALUES
            ('competitor_observations_pkey', 'p'),
            ('competitor_observations_search_run_id_fkey', 'f'),
            ('competitor_observations_listing_id_fkey', 'f'),
            ('competitor_observations_membership_id_fkey', 'f'),
            ('competitor_observations_observation_ref_key', 'u'),
            ('competitor_observations_position_check', 'c'),
            ('competitor_observations_prices_check', 'c'),
            ('competitor_observations_rating_count_check', 'c'),
            ('competitor_observations_reviews_scope_check', 'c'),
            ('competitor_observations_dimensions_check', 'c'),
            ('competitor_observations_values_check', 'c')
      ) AS expected(constraint_name, constraint_type)
     WHERE NOT EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.conrelid = 'public.competitor_observations'::regclass
           AND c.conname = expected.constraint_name
           AND c.contype = expected.constraint_type::"char"
           AND (c.contype <> 'c' OR c.convalidated)
     );

    SELECT count(*)
      INTO unexpected_constraint_count
      FROM pg_constraint c
     WHERE c.conrelid = 'public.competitor_observations'::regclass;

    IF missing_constraints IS NOT NULL OR unexpected_constraint_count <> 11 THEN
        RAISE EXCEPTION 'Observation constraints changed unexpectedly: missing %, count %',
            missing_constraints,
            unexpected_constraint_count;
    END IF;
END $$;

DO $$
DECLARE
    expected record;
    actual_definition text;
    actual_predicate text;
    actual_unique boolean;
    observation_index_count integer;
BEGIN
    FOR expected IN
        SELECT *
          FROM (
            VALUES
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
            RAISE EXCEPTION 'Missing or invalid observation index: %',
                expected.index_name;
        END IF;
    END LOOP;

    SELECT count(*)
      INTO observation_index_count
      FROM pg_index i
     WHERE i.indrelid = 'public.competitor_observations'::regclass;

    IF observation_index_count <> 5 THEN
        RAISE EXCEPTION 'Unexpected observation index count: %',
            observation_index_count;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.competitor_search_runs)
       OR EXISTS (SELECT 1 FROM public.competitor_observations)
       OR EXISTS (SELECT 1 FROM public.competitor_reviews)
       OR EXISTS (SELECT 1 FROM public.competitor_findings) THEN
        RAISE EXCEPTION 'Competitor Monitor history is not empty';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_trigger t
         WHERE t.tgrelid = 'public.competitor_observations'::regclass
           AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'Unexpected user trigger on competitor_observations';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM information_schema.columns c
         WHERE c.table_schema = 'public'
           AND c.table_name = 'competitor_observations'
           AND c.column_name = 'comparison_price'
    ) THEN
        RAISE EXCEPTION 'comparison_price must remain absent';
    END IF;
END $$;

SELECT
    true AS enrichment_captured_at_nullable_timestamptz,
    11 AS observation_constraints_checked,
    5 AS observation_indexes_checked,
    true AS competitor_history_empty,
    'PASS' AS status;

ROLLBACK;
