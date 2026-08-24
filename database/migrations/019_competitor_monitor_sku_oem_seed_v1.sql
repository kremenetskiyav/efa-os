-- Competitor Monitor SKU profile and confirmed OEM registry seed v1.
--
-- Source: EFA_OEM_REFERENCE_V1.
-- This migration seeds only competitor_sku_profiles and competitor_sku_oems.
-- It does not create product families, listings, watchlist memberships, search
-- runs, observations, reviews, findings, or any existing EFA product data.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    matched_products integer;
BEGIN
    IF to_regclass('public.products') IS NULL
       OR to_regclass('public.competitor_sku_profiles') IS NULL
       OR to_regclass('public.competitor_sku_oems') IS NULL
       OR to_regclass('public.competitor_product_families') IS NULL
       OR to_regclass('public.competitor_listings') IS NULL
       OR to_regclass('public.competitor_watchlist_memberships') IS NULL
       OR to_regclass('public.competitor_search_runs') IS NULL
       OR to_regclass('public.competitor_observations') IS NULL
       OR to_regclass('public.competitor_reviews') IS NULL
       OR to_regclass('public.competitor_findings') IS NULL THEN
        RAISE EXCEPTION 'Migration 018 schema is incomplete';
    END IF;

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

    IF matched_products <> 5 THEN
        RAISE EXCEPTION 'Expected products.offer_id/product_id mapping is incomplete';
    END IF;

    IF EXISTS (SELECT 1 FROM public.competitor_sku_profiles)
       OR EXISTS (SELECT 1 FROM public.competitor_sku_oems) THEN
        RAISE EXCEPTION 'Competitor SKU profile/OEM seed state is not empty';
    END IF;

    IF EXISTS (SELECT 1 FROM public.competitor_product_families)
       OR EXISTS (SELECT 1 FROM public.competitor_listings)
       OR EXISTS (SELECT 1 FROM public.competitor_watchlist_memberships)
       OR EXISTS (SELECT 1 FROM public.competitor_search_runs)
       OR EXISTS (SELECT 1 FROM public.competitor_observations)
       OR EXISTS (SELECT 1 FROM public.competitor_reviews)
       OR EXISTS (SELECT 1 FROM public.competitor_findings) THEN
        RAISE EXCEPTION 'Competitor Monitor clean seed precondition failed';
    END IF;
END $$;

INSERT INTO public.competitor_sku_profiles (
    offer_id,
    reference_length_mm,
    reference_width_mm,
    reference_height_mm,
    dimensions_source,
    dimensions_status,
    verification_status,
    watchlist_state,
    quality_flags
) VALUES
    (
        'УФ 001Б', 234, 224, 30,
        'EFA_OEM_REFERENCE_V1', 'CONFIRMED', 'CONFIRMED', 'ACTIVE',
        ARRAY[]::text[]
    ),
    (
        'УФ 002Б', 224, 254, 36,
        'EFA_OEM_REFERENCE_V1', 'CONFIRMED', 'CONFIRMED', 'ACTIVE',
        ARRAY[]::text[]
    ),
    (
        'УФ 003Б', 238, 194, 20,
        'EFA_OEM_REFERENCE_V1', 'NEEDS_VERIFICATION',
        'NEEDS_VERIFICATION', 'HOLD', ARRAY['SIZE_CONFLICT']::text[]
    ),
    (
        'УФ 004Б', 235, 254, 30,
        'EFA_OEM_REFERENCE_V1', 'CONFIRMED', 'CONFIRMED', 'ACTIVE',
        ARRAY[]::text[]
    ),
    (
        'УФ 005Б', 178, 285, 30,
        'EFA_OEM_REFERENCE_V1', 'CONFIRMED', 'CONFIRMED', 'ACTIVE',
        ARRAY[]::text[]
    );

INSERT INTO public.competitor_sku_oems (
    offer_id,
    oem_raw,
    oem_normalized,
    confidence,
    source_ref,
    is_primary,
    active
) VALUES
    ('УФ 001Б', '80292SLJ013', '80292SLJ013', 'HIGH', 'EFA_OEM_REFERENCE_V1', true, true),
    ('УФ 002Б', '6R0820367', '6R0820367', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 002Б', 'JZW819653F', 'JZW819653F', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 003Б', '97133F2000', '97133F2000', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 003Б', '97133F2100', '97133F2100', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 003Б', '97133F2200', '97133F2200', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 004Б', '5Q0819644A', '5Q0819644A', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 004Б', '5Q0819653', '5Q0819653', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 004Б', '5Q0819669', '5Q0819669', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 005Б', '647975', '647975', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 005Б', '6479C2', '6479C2', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true),
    ('УФ 005Б', '647941', '647941', 'HIGH', 'EFA_OEM_REFERENCE_V1', false, true);

COMMIT;
