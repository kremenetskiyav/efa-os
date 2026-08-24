-- Post-deployment validation for
-- 020_competitor_monitor_initial_watchlist_seed_v1.sql.
-- The validation transaction is read-only and leaves no database changes.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

DO $$
BEGIN
    IF (SELECT count(*) FROM public.competitor_product_families) <> 38 THEN
        RAISE EXCEPTION 'Expected exactly 38 competitor product families';
    END IF;

    IF EXISTS (
        WITH expected (
            product_name,
            brand_normalized,
            part_number_normalized,
            carbon_confidence,
            verification_status,
            quality_flags
        ) AS (
            VALUES
                ('RAF Filter RSTC001HOY'::text, 'RAF FILTER'::text, 'RSTC001HOY'::text, 'CONFIRMED'::text, 'CONFIRMED'::text, ARRAY[]::text[]),
                ('RAF Filter RF001HOY', 'RAF FILTER', 'RF001HOY', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('TOTACHI TCA-237K', 'TOTACHI', 'TCA-237K', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('MANN-FILTER CUK2358', 'MANN FILTER', 'CUK2358', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('AMD JFC67C', 'AMD', 'JFC67C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('LGN FILTER FC-165C', 'LGN FILTER', 'FC-165C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('ASIN FC267C', 'ASIN', 'FC267C', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
                ('HAWKCAR HW7224A', 'HAWKCAR', 'HW7224A', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('EFA УФ 001Б', 'EFA', 'УФ 001Б', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('Dashiwa ZAM6R0819653C', 'DASHIWA', 'ZAM6R0819653C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('ERIK GUSCHER EGC100022', 'ERIK GUSCHER', 'EGC100022', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('RAF Filter RSTC004VO', 'RAF FILTER', 'RSTC004VO', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('Мавико M241005C', 'МАВИКО', 'M241005C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('OptimalParts OPC006B', 'OPTIMALPARTS', 'OPC006B', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('MANN FILTER CUK26010', 'MANN FILTER', 'CUK26010', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('ALCARO / UNKNOWN PART NUMBER / УФ 002Б', 'ALCARO', NULL, 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
                ('RAF antibacterial / UNKNOWN PART NUMBER / УФ 002Б', 'RAF ANTIBACTERIAL', NULL, 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
                ('EFA УФ 002Б', 'EFA', 'УФ 002Б', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('RAF Filter RSTC001SK', 'RAF FILTER', 'RSTC001SK', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('Dashiwa ZAM5Q0819669C', 'DASHIWA', 'ZAM5Q0819669C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('AR-Distribution ARD5Q0819653A', 'AR-DISTRIBUTION', 'ARD5Q0819653A', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('LGN FILTER FC-130C', 'LGN FILTER', 'FC-130C', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('TSN 9.7.898', 'TSN', '9.7.898', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('MANN FILTER CUK26009', 'MANN FILTER', 'CUK26009', 'CONFIRMED', 'NEEDS_VERIFICATION', ARRAY['SIZE_CONFLICT']::text[]),
                ('RAF antibacterial / UNKNOWN PART NUMBER / УФ 004Б', 'RAF ANTIBACTERIAL', NULL, 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
                ('KUJIWA KUK0197', 'KUJIWA', 'KUK0197', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
                ('EFA УФ 004Б', 'EFA', 'УФ 004Б', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('RAF Filter RSTC001CITY', 'RAF FILTER', 'RSTC001CITY', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('RAF Filter RF001CITY', 'RAF FILTER', 'RF001CITY', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('AR-Distribution ARD6479C2A', 'AR-DISTRIBUTION', 'ARD6479C2A', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[]),
                ('IBERIS / UNKNOWN PART NUMBER / УФ 005Б', 'IBERIS', NULL, 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
                ('MARSHALL MC5014K', 'MARSHALL', 'MC5014K', 'CONFIRMED', 'NEEDS_VERIFICATION', ARRAY['SIZE_CONFLICT']::text[]),
                ('R&D FRND4813', 'R&D', 'FRND4813', 'CONFIRMED', 'NEEDS_VERIFICATION', ARRAY['SIZE_CONFLICT']::text[]),
                ('HAWKCAR HW7221A', 'HAWKCAR', 'HW7221A', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
                ('SCT SAK 177', 'SCT', 'SAK 177', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
                ('NORDFIL CN1066K', 'NORDFIL', 'CN1066K', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY['SIZE_CONFLICT']::text[]),
                ('SUFIX SSC-1012', 'SUFIX', 'SSC-1012', 'PROBABLE', 'NEEDS_VERIFICATION', ARRAY[]::text[]),
                ('EFA УФ 005Б', 'EFA', 'УФ 005Б', 'CONFIRMED', 'CONFIRMED', ARRAY[]::text[])
        ),
        differences AS (
            SELECT COALESCE(e.product_name, f.product_name) AS product_name
              FROM expected e
              FULL JOIN public.competitor_product_families f
                ON f.product_name = e.product_name
             WHERE e.product_name IS NULL
                OR f.product_name IS NULL
                OR f.brand_normalized IS DISTINCT FROM e.brand_normalized
                OR f.part_number_normalized IS DISTINCT FROM e.part_number_normalized
                OR f.carbon_confidence IS DISTINCT FROM e.carbon_confidence
                OR f.verification_status IS DISTINCT FROM e.verification_status
                OR f.quality_flags IS DISTINCT FROM e.quality_flags
        )
        SELECT 1 FROM differences
    ) THEN
        RAISE EXCEPTION 'Product-family seed differs from approved identities';
    END IF;
END $$;

DO $$
BEGIN
    IF (SELECT count(*) FROM public.competitor_watchlist_memberships) <> 41 THEN
        RAISE EXCEPTION 'Expected exactly 41 competitor watchlist memberships';
    END IF;

    IF EXISTS (
        WITH expected (
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
        ),
        actual AS (
            SELECT
                w.offer_id,
                l.ozon_product_id,
                l.seller_key,
                l.seller_id,
                w.membership_status,
                w.matched_oem_set,
                w.oem_confidence,
                w.decision_reason,
                w.quality_flags,
                w.valid_from,
                w.valid_to
              FROM public.competitor_watchlist_memberships w
              JOIN public.competitor_listings l
                ON l.listing_id = w.listing_id
        ),
        differences AS (
            SELECT COALESCE(e.offer_id, a.offer_id) AS offer_id
              FROM expected e
              FULL JOIN actual a
                ON a.offer_id = e.offer_id
               AND a.ozon_product_id = e.ozon_product_id
               AND a.seller_id = e.seller_id
               AND a.seller_key = 'OZON:' || e.seller_id
             WHERE e.offer_id IS NULL
                OR a.offer_id IS NULL
                OR a.membership_status IS DISTINCT FROM e.membership_status
                OR a.matched_oem_set IS DISTINCT FROM e.matched_oem_set
                OR a.oem_confidence IS DISTINCT FROM e.oem_confidence
                OR a.decision_reason IS DISTINCT FROM e.decision_reason
                OR a.quality_flags IS DISTINCT FROM e.quality_flags
                OR a.valid_from IS DISTINCT FROM TIMESTAMPTZ '2026-08-23 00:00:00+00'
                OR a.valid_to IS NOT NULL
        )
        SELECT 1 FROM differences
    ) THEN
        RAISE EXCEPTION 'Watchlist membership seed differs from approved contract';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        WITH expected (offer_id, primary_count, reserve_count, control_count) AS (
            VALUES
                ('УФ 001Б'::text, 6::bigint, 4::bigint, 1::bigint),
                ('УФ 002Б'::text, 6::bigint, 2::bigint, 1::bigint),
                ('УФ 003Б'::text, 0::bigint, 0::bigint, 0::bigint),
                ('УФ 004Б'::text, 5::bigint, 4::bigint, 1::bigint),
                ('УФ 005Б'::text, 3::bigint, 7::bigint, 1::bigint)
        ),
        actual AS (
            SELECT
                p.offer_id,
                count(*) FILTER (WHERE w.membership_status = 'PRIMARY') AS primary_count,
                count(*) FILTER (WHERE w.membership_status = 'RESERVE') AS reserve_count,
                count(*) FILTER (WHERE w.membership_status = 'CONTROL') AS control_count
              FROM public.competitor_sku_profiles p
              LEFT JOIN public.competitor_watchlist_memberships w
                ON w.offer_id = p.offer_id
               AND w.valid_to IS NULL
             GROUP BY p.offer_id
        )
        SELECT 1
          FROM expected e
          JOIN actual a USING (offer_id)
         WHERE a.primary_count <> e.primary_count
            OR a.reserve_count <> e.reserve_count
            OR a.control_count <> e.control_count
    ) THEN
        RAISE EXCEPTION 'Per-SKU PRIMARY/RESERVE/CONTROL distribution is incorrect';
    END IF;

    IF EXISTS (
        SELECT offer_id
          FROM public.competitor_watchlist_memberships
         WHERE valid_to IS NULL
         GROUP BY offer_id
        HAVING count(*) FILTER (WHERE membership_status = 'PRIMARY') > 6
    ) THEN
        RAISE EXCEPTION 'A SKU has more than six active PRIMARY memberships';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships w
          JOIN public.competitor_listings l USING (listing_id)
          JOIN public.competitor_product_families f USING (product_family_id)
         WHERE w.membership_status = 'PRIMARY'
           AND f.carbon_confidence <> 'CONFIRMED'
    ) THEN
        RAISE EXCEPTION 'PRIMARY contains a non-confirmed carbon family';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships w
          JOIN public.competitor_listings l USING (listing_id)
          JOIN public.competitor_product_families f USING (product_family_id)
         WHERE f.carbon_confidence = 'PROBABLE'
           AND w.membership_status <> 'RESERVE'
    ) THEN
        RAISE EXCEPTION 'PROBABLE carbon is present outside RESERVE';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships w
          JOIN public.competitor_listings l USING (listing_id)
          JOIN public.competitor_product_families f USING (product_family_id)
         WHERE (
                'SIZE_CONFLICT' = ANY(w.quality_flags)
                OR 'SIZE_CONFLICT' = ANY(f.quality_flags)
               )
           AND w.membership_status <> 'RESERVE'
    ) THEN
        RAISE EXCEPTION 'SIZE_CONFLICT is present outside RESERVE';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM public.competitor_sku_profiles
         WHERE offer_id = 'УФ 003Б'
           AND watchlist_state = 'HOLD'
           AND verification_status = 'NEEDS_VERIFICATION'
           AND 'SIZE_CONFLICT' = ANY(quality_flags)
    ) OR EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships
         WHERE offer_id = 'УФ 003Б'
    ) THEN
        RAISE EXCEPTION 'УФ 003Б HOLD/no-membership contract failed';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM public.competitor_watchlist_memberships w
          CROSS JOIN LATERAL unnest(w.matched_oem_set) AS matched(oem_normalized)
         WHERE NOT EXISTS (
            SELECT 1
              FROM public.competitor_sku_oems o
             WHERE o.offer_id = w.offer_id
               AND o.oem_normalized = matched.oem_normalized
               AND o.active
         )
    ) THEN
        RAISE EXCEPTION 'matched_oem_set contains an OEM outside the same active SKU registry';
    END IF;

    IF EXISTS (
        SELECT offer_id, listing_id
          FROM public.competitor_watchlist_memberships
         WHERE valid_to IS NULL
         GROUP BY offer_id, listing_id
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Duplicate active offer_id/listing_id membership exists';
    END IF;

    IF EXISTS (SELECT 1 FROM public.competitor_search_runs)
       OR EXISTS (SELECT 1 FROM public.competitor_observations)
       OR EXISTS (SELECT 1 FROM public.competitor_reviews)
       OR EXISTS (SELECT 1 FROM public.competitor_findings) THEN
        RAISE EXCEPTION 'Operational competitor tables are not empty';
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

DO $$
BEGIN
    IF (SELECT count(*) FROM public.competitor_listings) <> 41 THEN
        RAISE EXCEPTION 'Expected exactly 41 competitor listings';
    END IF;

    IF EXISTS (
        WITH expected (product_name, ozon_product_id, seller_id, seller_name) AS (
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
        ),
        actual AS (
            SELECT
                f.product_name,
                l.ozon_product_id,
                l.seller_name,
                l.seller_key,
                l.seller_id,
                l.listing_url,
                l.first_seen_at,
                l.last_seen_at,
                l.lifecycle_status
              FROM public.competitor_listings l
              JOIN public.competitor_product_families f
                ON f.product_family_id = l.product_family_id
        ),
        differences AS (
            SELECT COALESCE(e.ozon_product_id, a.ozon_product_id) AS ozon_product_id
              FROM expected e
              FULL JOIN actual a
                ON a.ozon_product_id = e.ozon_product_id
               AND a.seller_key = 'OZON:' || e.seller_id
             WHERE e.ozon_product_id IS NULL
                OR a.ozon_product_id IS NULL
                OR a.product_name IS DISTINCT FROM e.product_name
                OR a.seller_name IS DISTINCT FROM e.seller_name
                OR a.seller_id IS DISTINCT FROM e.seller_id
                OR a.listing_url IS NOT NULL
                OR a.first_seen_at IS DISTINCT FROM TIMESTAMPTZ '2026-08-23 00:00:00+00'
                OR a.last_seen_at IS DISTINCT FROM TIMESTAMPTZ '2026-08-23 00:00:00+00'
                OR a.lifecycle_status IS DISTINCT FROM 'ACTIVE'
        )
        SELECT 1 FROM differences
    ) THEN
        RAISE EXCEPTION 'Listing seed or family mapping differs from approved identities';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.competitor_listings
         WHERE seller_id IS NULL
            OR seller_name IS NULL
            OR seller_id !~ '^[0-9]+$'
            OR seller_key IS DISTINCT FROM 'OZON:' || seller_id
    ) THEN
        RAISE EXCEPTION 'Ozon seller identity policy failed';
    END IF;

    IF EXISTS (
        SELECT seller_id
          FROM public.competitor_listings
         GROUP BY seller_id
        HAVING count(DISTINCT seller_key) <> 1
            OR count(DISTINCT seller_name) <> 1
    ) THEN
        RAISE EXCEPTION 'One seller_id maps to multiple keys or names';
    END IF;

    IF (SELECT count(*) FROM public.competitor_listings WHERE seller_id IS NOT NULL) <> 41
       OR (SELECT count(DISTINCT seller_id) FROM public.competitor_listings) <> 25
       OR (SELECT count(*) FROM public.competitor_listings WHERE seller_key LIKE 'NAME:%') <> 0
       OR (SELECT count(*) FROM public.competitor_listings WHERE seller_key NOT LIKE 'OZON:%') <> 0
       OR (SELECT count(*) FROM public.competitor_listings WHERE seller_name LIKE '%…%') <> 0 THEN
        RAISE EXCEPTION 'Seller identity completeness/cardinality/truncation contract failed';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.competitor_listings
         WHERE seller_name IN (
            'PARTKOM – для людей…',
            'PARTKOM',
            'HAWK автофильтры от…',
            'HAWK',
            'AMD – Официальный м…',
            'МД',
            'DASHIWA'
         )
    ) THEN
        RAISE EXCEPTION 'A known truncated seller alias remains';
    END IF;

    IF (SELECT count(*) FROM public.competitor_listings WHERE seller_id = '24838' AND seller_key = 'OZON:24838') <> 9
       OR (SELECT count(*) FROM public.competitor_listings WHERE seller_id = '4767584' AND seller_key = 'OZON:4767584') <> 4
       OR (SELECT count(*) FROM public.competitor_listings WHERE seller_id = '92752' AND seller_key = 'OZON:92752') <> 3
       OR (SELECT count(*) FROM public.competitor_listings WHERE seller_id = '1382964' AND seller_key = 'OZON:1382964') <> 2
       OR (SELECT count(*) FROM public.competitor_listings WHERE seller_id = '1498853' AND seller_key = 'OZON:1498853') <> 2
       OR (SELECT count(*) FROM public.competitor_listings WHERE seller_id = '2713958' AND seller_key = 'OZON:2713958') <> 2 THEN
        RAISE EXCEPTION 'Known multi-listing seller identity counts are incorrect';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM public.competitor_listings
         WHERE ozon_product_id = 519757297
           AND seller_name = 'AR-Distribution'
           AND seller_id = '402554'
           AND seller_key = 'OZON:402554'
    ) OR NOT EXISTS (
        SELECT 1
          FROM public.competitor_listings
         WHERE ozon_product_id = 4381338927
           AND seller_name = 'AR-Distribution'
           AND seller_id = '4654179'
           AND seller_key = 'OZON:4654179'
    ) OR (
        SELECT count(DISTINCT seller_key)
          FROM public.competitor_listings
         WHERE seller_name = 'AR-Distribution'
    ) <> 2 THEN
        RAISE EXCEPTION 'AR-Distribution distinct seller identity contract failed';
    END IF;

    IF (SELECT count(*) FROM public.competitor_listings WHERE seller_name = 'ЭФА') <> 4
       OR (SELECT count(DISTINCT seller_id) FROM public.competitor_listings WHERE seller_name = 'ЭФА') <> 1
       OR NOT EXISTS (
            SELECT 1
              FROM public.competitor_listings
             WHERE seller_name = 'ЭФА'
               AND seller_id = '4767584'
               AND seller_key = 'OZON:4767584'
       ) THEN
        RAISE EXCEPTION 'EFA control seller identity contract failed';
    END IF;
END $$;

SELECT
    (SELECT count(*) FROM public.competitor_product_families) AS product_family_rows,
    (SELECT count(*) FROM public.competitor_listings) AS listing_rows,
    (SELECT count(*) FROM public.competitor_watchlist_memberships) AS membership_rows,
    (SELECT count(*) FROM public.competitor_watchlist_memberships WHERE membership_status = 'PRIMARY') AS primary_rows,
    (SELECT count(*) FROM public.competitor_watchlist_memberships WHERE membership_status = 'RESERVE') AS reserve_rows,
    (SELECT count(*) FROM public.competitor_watchlist_memberships WHERE membership_status = 'CONTROL') AS control_rows,
    (SELECT count(DISTINCT seller_id) FROM public.competitor_listings) AS unique_seller_ids,
    (SELECT count(*) FROM public.competitor_listings WHERE seller_key LIKE 'NAME:%') AS name_key_rows,
    (SELECT count(*) FROM public.products) AS products_rows_observed,
    (SELECT count(*) FROM public.product_snapshots) AS product_snapshots_rows_observed,
    (SELECT count(*) FROM public.change_events) AS change_events_rows_observed,
    'PASS' AS status;

ROLLBACK;
