-- Competitor Monitor approved product-family, Ozon-listing, and watchlist seed v1.
--
-- Source: approved Ozon discovery conducted on 2026-08-23.
-- Seller identity verified from official Ozon product/seller pages on 2026-08-24.
-- This migration deliberately stores no price, rank, rating, review, search-run,
-- observation, review, or finding facts.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    matched_profiles integer;
    matched_oems integer;
BEGIN
    IF to_regclass('public.products') IS NULL
       OR to_regclass('public.product_snapshots') IS NULL
       OR to_regclass('public.change_events') IS NULL
       OR to_regclass('public.competitor_sku_profiles') IS NULL
       OR to_regclass('public.competitor_sku_oems') IS NULL
       OR to_regclass('public.competitor_product_families') IS NULL
       OR to_regclass('public.competitor_listings') IS NULL
       OR to_regclass('public.competitor_watchlist_memberships') IS NULL
       OR to_regclass('public.competitor_search_runs') IS NULL
       OR to_regclass('public.competitor_observations') IS NULL
       OR to_regclass('public.competitor_reviews') IS NULL
       OR to_regclass('public.competitor_findings') IS NULL THEN
        RAISE EXCEPTION 'Competitor Monitor schema or required EFA tables are incomplete';
    END IF;

    SELECT count(*)
      INTO matched_profiles
      FROM (
        VALUES
            ('УФ 001Б'::text, 234::numeric, 224::numeric, 30::numeric, 'CONFIRMED'::text, 'ACTIVE'::text, 'CONFIRMED'::text, ARRAY[]::text[]),
            ('УФ 002Б'::text, 224::numeric, 254::numeric, 36::numeric, 'CONFIRMED'::text, 'ACTIVE'::text, 'CONFIRMED'::text, ARRAY[]::text[]),
            (
                'УФ 003Б'::text,
                238::numeric,
                194::numeric,
                20::numeric,
                'NEEDS_VERIFICATION'::text,
                'HOLD'::text,
                'NEEDS_VERIFICATION'::text,
                ARRAY['SIZE_CONFLICT']::text[]
            ),
            ('УФ 004Б'::text, 235::numeric, 254::numeric, 30::numeric, 'CONFIRMED'::text, 'ACTIVE'::text, 'CONFIRMED'::text, ARRAY[]::text[]),
            ('УФ 005Б'::text, 178::numeric, 285::numeric, 30::numeric, 'CONFIRMED'::text, 'ACTIVE'::text, 'CONFIRMED'::text, ARRAY[]::text[])
      ) AS expected(
          offer_id,
          reference_length_mm,
          reference_width_mm,
          reference_height_mm,
          dimensions_status,
          watchlist_state,
          verification_status,
          quality_flags
      )
      JOIN public.competitor_sku_profiles p
        ON p.offer_id = expected.offer_id
       AND p.reference_length_mm = expected.reference_length_mm
       AND p.reference_width_mm = expected.reference_width_mm
       AND p.reference_height_mm = expected.reference_height_mm
       AND p.dimensions_status = expected.dimensions_status
       AND p.watchlist_state = expected.watchlist_state
       AND p.verification_status = expected.verification_status
       AND p.quality_flags = expected.quality_flags;

    IF matched_profiles <> 5
       OR (SELECT count(*) FROM public.competitor_sku_profiles) <> 5 THEN
        RAISE EXCEPTION 'Expected exact five-profile state from Migration 019';
    END IF;

    SELECT count(*)
      INTO matched_oems
      FROM (
        VALUES
            ('УФ 001Б'::text, '80292SLJ013'::text),
            ('УФ 002Б'::text, '6R0820367'::text),
            ('УФ 002Б'::text, 'JZW819653F'::text),
            ('УФ 003Б'::text, '97133F2000'::text),
            ('УФ 003Б'::text, '97133F2100'::text),
            ('УФ 003Б'::text, '97133F2200'::text),
            ('УФ 004Б'::text, '5Q0819644A'::text),
            ('УФ 004Б'::text, '5Q0819653'::text),
            ('УФ 004Б'::text, '5Q0819669'::text),
            ('УФ 005Б'::text, '647975'::text),
            ('УФ 005Б'::text, '6479C2'::text),
            ('УФ 005Б'::text, '647941'::text)
      ) AS expected(offer_id, oem_normalized)
      JOIN public.competitor_sku_oems o
        ON o.offer_id = expected.offer_id
       AND o.oem_normalized = expected.oem_normalized
       AND o.active
       AND o.confidence = 'HIGH';

    IF matched_oems <> 12
       OR (SELECT count(*) FROM public.competitor_sku_oems) <> 12 THEN
        RAISE EXCEPTION 'Expected exact twelve-OEM state from Migration 019';
    END IF;

    IF EXISTS (SELECT 1 FROM public.competitor_product_families)
       OR EXISTS (SELECT 1 FROM public.competitor_listings)
       OR EXISTS (SELECT 1 FROM public.competitor_watchlist_memberships) THEN
        RAISE EXCEPTION 'Initial family/listing/watchlist seed target is not empty';
    END IF;

    IF EXISTS (SELECT 1 FROM public.competitor_search_runs)
       OR EXISTS (SELECT 1 FROM public.competitor_observations)
       OR EXISTS (SELECT 1 FROM public.competitor_reviews)
       OR EXISTS (SELECT 1 FROM public.competitor_findings) THEN
        RAISE EXCEPTION 'Operational competitor tables must be empty before initial seed';
    END IF;
END $$;

INSERT INTO public.competitor_product_families (
    brand_raw,
    brand_normalized,
    part_number_raw,
    part_number_normalized,
    product_name,
    carbon_confidence,
    verification_status,
    quality_flags
) VALUES
    ('RAF Filter', 'RAF FILTER', 'RSTC001HOY', 'RSTC001HOY', 'RAF Filter RSTC001HOY', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('RAF Filter', 'RAF FILTER', 'RF001HOY', 'RF001HOY', 'RAF Filter RF001HOY', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('TOTACHI', 'TOTACHI', 'TCA-237K', 'TCA-237K', 'TOTACHI TCA-237K', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('MANN-FILTER', 'MANN FILTER', 'CUK2358', 'CUK2358', 'MANN-FILTER CUK2358', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('AMD', 'AMD', 'JFC67C', 'JFC67C', 'AMD JFC67C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('LGN FILTER', 'LGN FILTER', 'FC-165C', 'FC-165C', 'LGN FILTER FC-165C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('ASIN', 'ASIN', 'FC267C', 'FC267C', 'ASIN FC267C', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
    ('HAWKCAR', 'HAWKCAR', 'HW7224A', 'HW7224A', 'HAWKCAR HW7224A', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('EFA', 'EFA', 'УФ 001Б', 'УФ 001Б', 'EFA УФ 001Б', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),

    ('Dashiwa', 'DASHIWA', 'ZAM6R0819653C', 'ZAM6R0819653C', 'Dashiwa ZAM6R0819653C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('ERIK GUSCHER', 'ERIK GUSCHER', 'EGC100022', 'EGC100022', 'ERIK GUSCHER EGC100022', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('RAF Filter', 'RAF FILTER', 'RSTC004VO', 'RSTC004VO', 'RAF Filter RSTC004VO', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('Мавико', 'МАВИКО', 'M241005C', 'M241005C', 'Мавико M241005C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('OptimalParts', 'OPTIMALPARTS', 'OPC006B', 'OPC006B', 'OptimalParts OPC006B', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('MANN FILTER', 'MANN FILTER', 'CUK26010', 'CUK26010', 'MANN FILTER CUK26010', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('ALCARO', 'ALCARO', NULL, NULL, 'ALCARO / UNKNOWN PART NUMBER / УФ 002Б', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
    ('RAF antibacterial', 'RAF ANTIBACTERIAL', NULL, NULL, 'RAF antibacterial / UNKNOWN PART NUMBER / УФ 002Б', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
    ('EFA', 'EFA', 'УФ 002Б', 'УФ 002Б', 'EFA УФ 002Б', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),

    ('RAF Filter', 'RAF FILTER', 'RSTC001SK', 'RSTC001SK', 'RAF Filter RSTC001SK', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('Dashiwa', 'DASHIWA', 'ZAM5Q0819669C', 'ZAM5Q0819669C', 'Dashiwa ZAM5Q0819669C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('AR-Distribution', 'AR-DISTRIBUTION', 'ARD5Q0819653A', 'ARD5Q0819653A', 'AR-Distribution ARD5Q0819653A', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('LGN FILTER', 'LGN FILTER', 'FC-130C', 'FC-130C', 'LGN FILTER FC-130C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('TSN', 'TSN', '9.7.898', '9.7.898', 'TSN 9.7.898', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('MANN FILTER', 'MANN FILTER', 'CUK26009', 'CUK26009', 'MANN FILTER CUK26009', 'CONFIRMED', 'NEEDS_VERIFICATION', ARRAY['SIZE_CONFLICT']::text[]),
    ('RAF antibacterial', 'RAF ANTIBACTERIAL', NULL, NULL, 'RAF antibacterial / UNKNOWN PART NUMBER / УФ 004Б', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
    ('KUJIWA', 'KUJIWA', 'KUK0197', 'KUK0197', 'KUJIWA KUK0197', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
    ('EFA', 'EFA', 'УФ 004Б', 'УФ 004Б', 'EFA УФ 004Б', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),

    ('RAF Filter', 'RAF FILTER', 'RSTC001CITY', 'RSTC001CITY', 'RAF Filter RSTC001CITY', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('RAF Filter', 'RAF FILTER', 'RF001CITY', 'RF001CITY', 'RAF Filter RF001CITY', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('AR-Distribution', 'AR-DISTRIBUTION', 'ARD6479C2A', 'ARD6479C2A', 'AR-Distribution ARD6479C2A', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
    ('IBERIS', 'IBERIS', NULL, NULL, 'IBERIS / UNKNOWN PART NUMBER / УФ 005Б', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
    ('MARSHALL', 'MARSHALL', 'MC5014K', 'MC5014K', 'MARSHALL MC5014K', 'CONFIRMED', 'NEEDS_VERIFICATION', ARRAY['SIZE_CONFLICT']::text[]),
    ('R&D', 'R&D', 'FRND4813', 'FRND4813', 'R&D FRND4813', 'CONFIRMED', 'NEEDS_VERIFICATION', ARRAY['SIZE_CONFLICT']::text[]),
    ('HAWKCAR', 'HAWKCAR', 'HW7221A', 'HW7221A', 'HAWKCAR HW7221A', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
    ('SCT', 'SCT', 'SAK 177', 'SAK 177', 'SCT SAK 177', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
    ('NORDFIL', 'NORDFIL', 'CN1066K', 'CN1066K', 'NORDFIL CN1066K', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY['SIZE_CONFLICT']::text[]),
    ('SUFIX', 'SUFIX', 'SSC-1012', 'SSC-1012', 'SUFIX SSC-1012', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
    ('EFA', 'EFA', 'УФ 005Б', 'УФ 005Б', 'EFA УФ 005Б', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]);

WITH listing_seed (
    product_name,
    ozon_product_id,
    seller_id,
    seller_name
) AS (
    VALUES
        ('RAF Filter RSTC001HOY'::text, 796591986::bigint, '24838'::text, 'RAF Parts'::text),
        ('RAF Filter RF001HOY', 266328154, '24838', 'RAF Parts'),
        ('TOTACHI TCA-237K', 1356342041, '699471', 'BURMA АВТОЗАПЧАСТИ'),
        ('MANN-FILTER CUK2358', 924191375, '92752', 'PARTKOM - для людей и авто'),
        ('LGN FILTER FC-165C', 3468256200, '1498853', 'LGN FILTER'),
        ('HAWKCAR HW7224A', 2698014827, '2713958', 'HAWK автофильтры от производителя'),
        ('AMD JFC67C', 215996486, '79642', 'AMD - Официальный магазин'),
        ('RAF Filter RSTC001HOY', 1566524732, '92752', 'PARTKOM - для людей и авто'),
        ('RAF Filter RSTC001HOY', 5540658609, '3877579', 'Магазин Джахау Премиум-2'),
        ('ASIN FC267C', 2022731795, '5936', 'Parts Planet'),
        ('EFA УФ 001Б', 4601821825, '4767584', 'ЭФА'),

        ('Dashiwa ZAM6R0819653C', 1201513545, '1382964', 'DASHIWA Оригинальные фильтра от производителя'),
        ('ERIK GUSCHER EGC100022', 2936478004, '1615605', 'ERIK GUSCHER'),
        ('RAF Filter RSTC004VO', 618137426, '24838', 'RAF Parts'),
        ('Мавико M241005C', 1628467740, '1321521', 'МАВИКО: российский производитель запчастей с 2012 года'),
        ('OptimalParts OPC006B', 1480553506, '24838', 'RAF Parts'),
        ('MANN FILTER CUK26010', 1628774540, '660768', 'Автоликон'),
        ('ALCARO / UNKNOWN PART NUMBER / УФ 002Б', 1624364470, '559265', 'Торговый дом LOTOS'),
        ('RAF antibacterial / UNKNOWN PART NUMBER / УФ 002Б', 266346879, '24838', 'RAF Parts'),
        ('EFA УФ 002Б', 4642158029, '4767584', 'ЭФА'),

        ('RAF Filter RSTC001SK', 613048940, '24838', 'RAF Parts'),
        ('Dashiwa ZAM5Q0819669C', 1324012918, '1382964', 'DASHIWA Оригинальные фильтра от производителя'),
        ('AR-Distribution ARD5Q0819653A', 519757297, '402554', 'AR-Distribution'),
        ('LGN FILTER FC-130C', 1411048042, '1498853', 'LGN FILTER'),
        ('TSN 9.7.898', 3011421926, '3512424', 'Завод-Лаборатория Цитрон'),
        ('MANN FILTER CUK26009', 3525756097, '790565', 'AUTODOPE'),
        ('MANN FILTER CUK26009', 898384330, '92752', 'PARTKOM - для людей и авто'),
        ('RAF antibacterial / UNKNOWN PART NUMBER / УФ 004Б', 227576931, '24838', 'RAF Parts'),
        ('KUJIWA KUK0197', 616223751, '507937', 'ООО "РЕМИКАР"'),
        ('EFA УФ 004Б', 4642180551, '4767584', 'ЭФА'),

        ('RAF Filter RSTC001CITY', 332405695, '24838', 'RAF Parts'),
        ('RAF Filter RF001CITY', 268629078, '24838', 'RAF Parts'),
        ('AR-Distribution ARD6479C2A', 4381338927, '4654179', 'AR-Distribution'),
        ('IBERIS / UNKNOWN PART NUMBER / УФ 005Б', 1086068777, '1231347', 'IXORA'),
        ('MARSHALL MC5014K', 215758125, '59211', 'MARSHALL'),
        ('R&D FRND4813', 3959121966, '957375', 'FutureParts'),
        ('HAWKCAR HW7221A', 2666178947, '2713958', 'HAWK автофильтры от производителя'),
        ('SCT SAK 177', 2810830876, '2546484', 'ТД ЮгТрендАвто'),
        ('NORDFIL CN1066K', 658313675, '115929', 'ООО "Автоэкспресс24"'),
        ('SUFIX SSC-1012', 3968916713, '3960341', 'Партерра - запчасти с гарантией'),
        ('EFA УФ 005Б', 4671328307, '4767584', 'ЭФА')
)
INSERT INTO public.competitor_listings (
    product_family_id,
    ozon_product_id,
    seller_key,
    seller_id,
    seller_name,
    listing_url,
    first_seen_at,
    last_seen_at,
    lifecycle_status
)
SELECT
    f.product_family_id,
    s.ozon_product_id,
    'OZON:' || s.seller_id,
    s.seller_id,
    s.seller_name,
    NULL,
    TIMESTAMPTZ '2026-08-23 00:00:00+00',
    TIMESTAMPTZ '2026-08-23 00:00:00+00',
    'ACTIVE'
  FROM listing_seed s
  JOIN public.competitor_product_families f
    ON f.product_name = s.product_name;

WITH membership_seed (
    offer_id,
    ozon_product_id,
    seller_id,
    membership_status,
    matched_oem_set,
    oem_confidence,
    decision_reason,
    quality_flags
) AS (
    VALUES
        ('УФ 001Б'::text, 796591986::bigint, '24838'::text, 'PRIMARY'::text, ARRAY['80292SLJ013']::text[], 'HIGH'::text, 'INITIAL_WATCHLIST_V1'::text, ARRAY[]::text[]),
        ('УФ 001Б', 266328154, '24838', 'PRIMARY', ARRAY['80292SLJ013']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 001Б', 1356342041, '699471', 'PRIMARY', ARRAY['80292SLJ013']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 001Б', 924191375, '92752', 'PRIMARY', ARRAY['80292SLJ013']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 001Б', 3468256200, '1498853', 'PRIMARY', ARRAY['80292SLJ013']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 001Б', 2698014827, '2713958', 'PRIMARY', ARRAY['80292SLJ013']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 001Б', 215996486, '79642', 'RESERVE', ARRAY['80292SLJ013']::text[], 'MEDIUM', 'RESERVE_OEM_MEDIUM', ARRAY[]::text[]),
        ('УФ 001Б', 1566524732, '92752', 'RESERVE', ARRAY['80292SLJ013']::text[], 'HIGH', 'RESERVE_SECONDARY_SELLER', ARRAY[]::text[]),
        ('УФ 001Б', 5540658609, '3877579', 'RESERVE', ARRAY['80292SLJ013']::text[], 'HIGH', 'RESERVE_ORIGIN_CONFLICT', ARRAY['ORIGIN_CONFLICT']::text[]),
        ('УФ 001Б', 2022731795, '5936', 'RESERVE', ARRAY['80292SLJ013']::text[], 'HIGH', 'RESERVE_PROBABLE_CARBON', ARRAY[]::text[]),
        ('УФ 001Б', 4601821825, '4767584', 'CONTROL', ARRAY['80292SLJ013']::text[], 'HIGH', 'CONTROL_EFA_OWN_CARD', ARRAY[]::text[]),

        ('УФ 002Б', 1201513545, '1382964', 'PRIMARY', ARRAY['6R0820367','JZW819653F']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 002Б', 2936478004, '1615605', 'PRIMARY', ARRAY['6R0820367','JZW819653F']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 002Б', 618137426, '24838', 'PRIMARY', ARRAY['6R0820367','JZW819653F']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 002Б', 1628467740, '1321521', 'PRIMARY', ARRAY['6R0820367','JZW819653F']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 002Б', 1480553506, '24838', 'PRIMARY', ARRAY['6R0820367','JZW819653F']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 002Б', 1628774540, '660768', 'PRIMARY', ARRAY['6R0820367','JZW819653F']::text[], 'MEDIUM', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 002Б', 1624364470, '559265', 'RESERVE', ARRAY['6R0820367','JZW819653F']::text[], 'HIGH', 'RESERVE_PROBABLE_CARBON', ARRAY[]::text[]),
        ('УФ 002Б', 266346879, '24838', 'RESERVE', ARRAY['6R0820367','JZW819653F']::text[], 'HIGH', 'RESERVE_PROBABLE_CARBON', ARRAY[]::text[]),
        ('УФ 002Б', 4642158029, '4767584', 'CONTROL', ARRAY['6R0820367','JZW819653F']::text[], 'HIGH', 'CONTROL_EFA_OWN_CARD', ARRAY[]::text[]),

        ('УФ 004Б', 613048940, '24838', 'PRIMARY', ARRAY['5Q0819644A','5Q0819653','5Q0819669']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 004Б', 1324012918, '1382964', 'PRIMARY', ARRAY['5Q0819644A','5Q0819653','5Q0819669']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 004Б', 519757297, '402554', 'PRIMARY', ARRAY['5Q0819644A','5Q0819653','5Q0819669']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 004Б', 1411048042, '1498853', 'PRIMARY', ARRAY['5Q0819644A','5Q0819653','5Q0819669']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 004Б', 3011421926, '3512424', 'PRIMARY', ARRAY['5Q0819644A','5Q0819653','5Q0819669']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 004Б', 3525756097, '790565', 'RESERVE', ARRAY['5Q0819644A','5Q0819653','5Q0819669']::text[], 'HIGH', 'RESERVE_SIZE_CONFLICT', ARRAY['SIZE_CONFLICT']::text[]),
        ('УФ 004Б', 898384330, '92752', 'RESERVE', ARRAY['5Q0819653','5Q0819669']::text[], 'HIGH', 'RESERVE_SIZE_CONFLICT', ARRAY['SIZE_CONFLICT']::text[]),
        ('УФ 004Б', 227576931, '24838', 'RESERVE', ARRAY['5Q0819644A','5Q0819669']::text[], 'HIGH', 'RESERVE_PROBABLE_CARBON', ARRAY[]::text[]),
        ('УФ 004Б', 616223751, '507937', 'RESERVE', ARRAY['5Q0819644A','5Q0819653','5Q0819669']::text[], 'HIGH', 'RESERVE_PROBABLE_CARBON', ARRAY[]::text[]),
        ('УФ 004Б', 4642180551, '4767584', 'CONTROL', ARRAY['5Q0819644A','5Q0819653','5Q0819669']::text[], 'HIGH', 'CONTROL_EFA_OWN_CARD', ARRAY[]::text[]),

        ('УФ 005Б', 332405695, '24838', 'PRIMARY', ARRAY['647975','6479C2','647941']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 005Б', 268629078, '24838', 'PRIMARY', ARRAY['647975','6479C2','647941']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 005Б', 4381338927, '4654179', 'PRIMARY', ARRAY['6479C2']::text[], 'HIGH', 'INITIAL_WATCHLIST_V1', ARRAY[]::text[]),
        ('УФ 005Б', 1086068777, '1231347', 'RESERVE', ARRAY['647975','6479C2','647941']::text[], 'HIGH', 'RESERVE_PROBABLE_CARBON', ARRAY[]::text[]),
        ('УФ 005Б', 215758125, '59211', 'RESERVE', ARRAY['647975','6479C2','647941']::text[], 'HIGH', 'RESERVE_SIZE_CONFLICT', ARRAY['SIZE_CONFLICT']::text[]),
        ('УФ 005Б', 3959121966, '957375', 'RESERVE', ARRAY['647975','6479C2','647941']::text[], 'HIGH', 'RESERVE_SIZE_CONFLICT', ARRAY['SIZE_CONFLICT']::text[]),
        ('УФ 005Б', 2666178947, '2713958', 'RESERVE', ARRAY['647975','6479C2','647941']::text[], 'HIGH', 'RESERVE_PROBABLE_CARBON', ARRAY[]::text[]),
        ('УФ 005Б', 2810830876, '2546484', 'RESERVE', ARRAY['647975','6479C2','647941']::text[], 'HIGH', 'RESERVE_PROBABLE_CARBON', ARRAY[]::text[]),
        ('УФ 005Б', 658313675, '115929', 'RESERVE', ARRAY['647975','647941']::text[], 'HIGH', 'RESERVE_SIZE_CONFLICT', ARRAY['SIZE_CONFLICT']::text[]),
        ('УФ 005Б', 3968916713, '3960341', 'RESERVE', ARRAY['647975','6479C2','647941']::text[], 'HIGH', 'RESERVE_PROBABLE_CARBON', ARRAY[]::text[]),
        ('УФ 005Б', 4671328307, '4767584', 'CONTROL', ARRAY['647975','6479C2','647941']::text[], 'HIGH', 'CONTROL_EFA_OWN_CARD', ARRAY[]::text[])
)
INSERT INTO public.competitor_watchlist_memberships (
    offer_id,
    listing_id,
    membership_status,
    matched_oem_set,
    oem_confidence,
    decision_reason,
    quality_flags,
    valid_from,
    valid_to
)
SELECT
    s.offer_id,
    l.listing_id,
    s.membership_status,
    s.matched_oem_set,
    s.oem_confidence,
    s.decision_reason,
    s.quality_flags,
    TIMESTAMPTZ '2026-08-23 00:00:00+00',
    NULL
  FROM membership_seed s
  JOIN public.competitor_listings l
    ON l.ozon_product_id = s.ozon_product_id
   AND l.seller_id = s.seller_id
   AND l.seller_key = 'OZON:' || s.seller_id;

DO $$
BEGIN
    IF (SELECT count(*) FROM public.competitor_product_families) <> 38
       OR (SELECT count(*) FROM public.competitor_listings) <> 41
       OR (SELECT count(*) FROM public.competitor_watchlist_memberships) <> 41 THEN
        RAISE EXCEPTION 'Initial watchlist seed row counts are incomplete';
    END IF;

    IF (SELECT count(*) FROM public.competitor_watchlist_memberships WHERE membership_status = 'PRIMARY') <> 20
       OR (SELECT count(*) FROM public.competitor_watchlist_memberships WHERE membership_status = 'RESERVE') <> 17
       OR (SELECT count(*) FROM public.competitor_watchlist_memberships WHERE membership_status = 'CONTROL') <> 4 THEN
        RAISE EXCEPTION 'Initial watchlist membership distribution is incorrect';
    END IF;

    IF EXISTS (SELECT 1 FROM public.competitor_search_runs)
       OR EXISTS (SELECT 1 FROM public.competitor_observations)
       OR EXISTS (SELECT 1 FROM public.competitor_reviews)
       OR EXISTS (SELECT 1 FROM public.competitor_findings) THEN
        RAISE EXCEPTION 'Initial watchlist seed contaminated operational tables';
    END IF;
END $$;

COMMIT;
