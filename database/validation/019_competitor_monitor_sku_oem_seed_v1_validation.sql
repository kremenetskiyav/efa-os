-- Post-deployment validation for
-- 019_competitor_monitor_sku_oem_seed_v1.sql.
-- The validation transaction is read-only and leaves no database changes.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

DO $$
BEGIN
    IF (SELECT count(*) FROM public.competitor_sku_profiles) <> 5 THEN
        RAISE EXCEPTION 'Expected exactly five competitor SKU profiles';
    END IF;

    IF EXISTS (
        WITH expected AS (
            SELECT *
              FROM (
                VALUES
                    (
                        'УФ 001Б'::text, 234::numeric, 224::numeric, 30::numeric,
                        'EFA_OEM_REFERENCE_V1'::text, 'CONFIRMED'::text,
                        'CONFIRMED'::text, 'ACTIVE'::text, ARRAY[]::text[]
                    ),
                    (
                        'УФ 002Б'::text, 224::numeric, 254::numeric, 36::numeric,
                        'EFA_OEM_REFERENCE_V1'::text, 'CONFIRMED'::text,
                        'CONFIRMED'::text, 'ACTIVE'::text, ARRAY[]::text[]
                    ),
                    (
                        'УФ 003Б'::text, 238::numeric, 194::numeric, 20::numeric,
                        'EFA_OEM_REFERENCE_V1'::text, 'NEEDS_VERIFICATION'::text,
                        'NEEDS_VERIFICATION'::text, 'HOLD'::text,
                        ARRAY['SIZE_CONFLICT']::text[]
                    ),
                    (
                        'УФ 004Б'::text, 235::numeric, 254::numeric, 30::numeric,
                        'EFA_OEM_REFERENCE_V1'::text, 'CONFIRMED'::text,
                        'CONFIRMED'::text, 'ACTIVE'::text, ARRAY[]::text[]
                    ),
                    (
                        'УФ 005Б'::text, 178::numeric, 285::numeric, 30::numeric,
                        'EFA_OEM_REFERENCE_V1'::text, 'CONFIRMED'::text,
                        'CONFIRMED'::text, 'ACTIVE'::text, ARRAY[]::text[]
                    )
              ) AS values_table(
                  offer_id,
                  reference_length_mm,
                  reference_width_mm,
                  reference_height_mm,
                  dimensions_source,
                  dimensions_status,
                  verification_status,
                  watchlist_state,
                  quality_flags
              )
        ),
        differences AS (
            SELECT
                COALESCE(e.offer_id, p.offer_id) AS offer_id
              FROM expected e
              FULL JOIN public.competitor_sku_profiles p
                ON p.offer_id = e.offer_id
             WHERE e.offer_id IS NULL
                OR p.offer_id IS NULL
                OR p.reference_length_mm IS DISTINCT FROM e.reference_length_mm
                OR p.reference_width_mm IS DISTINCT FROM e.reference_width_mm
                OR p.reference_height_mm IS DISTINCT FROM e.reference_height_mm
                OR p.dimensions_source IS DISTINCT FROM e.dimensions_source
                OR p.dimensions_status IS DISTINCT FROM e.dimensions_status
                OR p.verification_status IS DISTINCT FROM e.verification_status
                OR p.watchlist_state IS DISTINCT FROM e.watchlist_state
                OR p.quality_flags IS DISTINCT FROM e.quality_flags
        )
        SELECT 1 FROM differences
    ) THEN
        RAISE EXCEPTION 'Competitor SKU profile seed differs from reference v1';
    END IF;
END $$;

DO $$
BEGIN
    IF (SELECT count(*) FROM public.competitor_sku_oems) <> 12 THEN
        RAISE EXCEPTION 'Expected exactly twelve competitor SKU OEM rows';
    END IF;

    IF EXISTS (
        WITH expected AS (
            SELECT *
              FROM (
                VALUES
                    ('УФ 001Б'::text, '80292SLJ013'::text, true),
                    ('УФ 002Б'::text, '6R0820367'::text, false),
                    ('УФ 002Б'::text, 'JZW819653F'::text, false),
                    ('УФ 003Б'::text, '97133F2000'::text, false),
                    ('УФ 003Б'::text, '97133F2100'::text, false),
                    ('УФ 003Б'::text, '97133F2200'::text, false),
                    ('УФ 004Б'::text, '5Q0819644A'::text, false),
                    ('УФ 004Б'::text, '5Q0819653'::text, false),
                    ('УФ 004Б'::text, '5Q0819669'::text, false),
                    ('УФ 005Б'::text, '647975'::text, false),
                    ('УФ 005Б'::text, '6479C2'::text, false),
                    ('УФ 005Б'::text, '647941'::text, false)
              ) AS values_table(offer_id, oem_value, is_primary)
        ),
        differences AS (
            SELECT COALESCE(e.offer_id, o.offer_id) AS offer_id
              FROM expected e
              FULL JOIN public.competitor_sku_oems o
                ON o.offer_id = e.offer_id
               AND o.oem_normalized = e.oem_value
             WHERE e.offer_id IS NULL
                OR o.offer_id IS NULL
                OR o.oem_raw IS DISTINCT FROM e.oem_value
                OR o.oem_normalized IS DISTINCT FROM e.oem_value
                OR o.confidence IS DISTINCT FROM 'HIGH'
                OR o.source_ref IS DISTINCT FROM 'EFA_OEM_REFERENCE_V1'
                OR o.is_primary IS DISTINCT FROM e.is_primary
                OR o.active IS DISTINCT FROM true
        )
        SELECT 1 FROM differences
    ) THEN
        RAISE EXCEPTION 'Competitor SKU OEM seed differs from reference v1';
    END IF;

    IF EXISTS (
        SELECT offer_id
          FROM public.competitor_sku_oems
         GROUP BY offer_id
        HAVING count(*) <> CASE offer_id
            WHEN 'УФ 001Б' THEN 1
            WHEN 'УФ 002Б' THEN 2
            WHEN 'УФ 003Б' THEN 3
            WHEN 'УФ 004Б' THEN 3
            WHEN 'УФ 005Б' THEN 3
            ELSE 0
        END
    ) THEN
        RAISE EXCEPTION 'Unexpected OEM distribution by offer_id';
    END IF;

    IF EXISTS (
        SELECT offer_id, oem_normalized
          FROM public.competitor_sku_oems
         GROUP BY offer_id, oem_normalized
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Duplicate normalized OEM exists inside one SKU';
    END IF;

    IF EXISTS (
        SELECT oem_normalized
          FROM public.competitor_sku_oems
         GROUP BY oem_normalized
        HAVING count(DISTINCT offer_id) > 1
    ) THEN
        RAISE EXCEPTION 'Cross-SKU normalized OEM duplicate exists';
    END IF;

    IF (SELECT count(*) FROM public.competitor_sku_oems WHERE confidence = 'HIGH') <> 12
       OR (SELECT count(*) FROM public.competitor_sku_oems WHERE active) <> 12
       OR (SELECT count(*) FROM public.competitor_sku_oems WHERE oem_raw = oem_normalized) <> 12
       OR (SELECT count(*) FROM public.competitor_sku_oems WHERE offer_id = 'УФ 001Б' AND is_primary) <> 1
       OR (SELECT count(*) FROM public.competitor_sku_oems WHERE offer_id <> 'УФ 001Б' AND is_primary) <> 0 THEN
        RAISE EXCEPTION 'OEM confidence/active/normalization/primary contract failed';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.competitor_product_families)
       OR EXISTS (SELECT 1 FROM public.competitor_listings)
       OR EXISTS (SELECT 1 FROM public.competitor_watchlist_memberships)
       OR EXISTS (SELECT 1 FROM public.competitor_search_runs)
       OR EXISTS (SELECT 1 FROM public.competitor_observations)
       OR EXISTS (SELECT 1 FROM public.competitor_reviews)
       OR EXISTS (SELECT 1 FROM public.competitor_findings) THEN
        RAISE EXCEPTION 'Competitor Monitor seed contaminated non-seed tables';
    END IF;
END $$;

DO $$
DECLARE
    matched_products integer;
BEGIN
    SELECT count(*)
      INTO matched_products
      FROM (
        VALUES
            ('УФ 001Б'::text, 4861934525::bigint),
            ('УФ 002Б'::text, 4861934539::bigint),
            ('УФ 003Б'::text, 4861934541::bigint),
            ('УФ 004Б'::text, 4861934500::bigint),
            ('УФ 005Б'::text, 4861934542::bigint)
      ) AS expected(offer_id, product_id)
      JOIN public.products p
        ON p.offer_id = expected.offer_id
       AND p.product_id = expected.product_id;

    IF matched_products <> 5
       OR to_regclass('public.product_snapshots') IS NULL
       OR to_regclass('public.change_events') IS NULL THEN
        RAISE EXCEPTION 'Existing EFA reference objects are incomplete';
    END IF;
END $$;

SELECT
    (SELECT count(*) FROM public.competitor_sku_profiles) AS profile_rows,
    (SELECT count(*) FROM public.competitor_sku_oems) AS oem_rows,
    (SELECT count(*) FROM public.products) AS products_rows_observed,
    (SELECT count(*) FROM public.product_snapshots) AS product_snapshots_rows_observed,
    (SELECT count(*) FROM public.change_events) AS change_events_rows_observed,
    'PASS' AS status;

ROLLBACK;
