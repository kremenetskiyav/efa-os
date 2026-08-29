-- Migration 025: persist the immutable legacy membership reference order.
--
-- Authoritative source: Migration 020 membership_seed row order only.
-- The database enforces NOT NULL, positive, and global uniqueness. The owner-
-- managed application contract additionally forbids changing an allocated
-- ordinal, reusing a retired ordinal, renumbering, or compacting gaps. New
-- memberships must receive an explicitly allocated ordinal greater than every
-- ordinal ever allocated. A matched_oem_set change closes the old membership
-- and creates a new membership with a new ordinal.
--
-- Rollback is mechanically possible only before later memberships depend on
-- the ordinal: restore the Migration 024 view definition, drop the two new
-- constraints, then drop reference_ordinal. After later ordinals are allocated,
-- rollback is logically unsafe and requires a separate reviewed migration.
--
-- Explicitly out of scope: Analyzer counts, credentials/launchers, Daily Cycle
-- code, Finding Engine, persistence identity, and any new MCP read surface.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '120s';
SET LOCAL timezone = 'UTC';
SET LOCAL search_path = pg_catalog;

DO $identity_preflight$
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Migration 025 must run only in database efa';
    END IF;

    IF current_user <> 'efa' THEN
        RAISE EXCEPTION 'Migration 025 must run as role efa';
    END IF;

    IF to_regclass('public.competitor_watchlist_memberships') IS NULL
       OR to_regclass('public.competitor_listings') IS NULL THEN
        RAISE EXCEPTION 'Migration 025 source relations are missing';
    END IF;
END
$identity_preflight$;

LOCK TABLE public.competitor_watchlist_memberships IN ACCESS EXCLUSIVE MODE;
LOCK TABLE public.competitor_listings IN SHARE MODE;

DO $preflight$
DECLARE
    authoritative constant jsonb := $json$[
      {"reference_ordinal":1,"offer_id":"УФ 001Б","ozon_product_id":796591986,"seller_id":"24838"},
      {"reference_ordinal":2,"offer_id":"УФ 001Б","ozon_product_id":266328154,"seller_id":"24838"},
      {"reference_ordinal":3,"offer_id":"УФ 001Б","ozon_product_id":1356342041,"seller_id":"699471"},
      {"reference_ordinal":4,"offer_id":"УФ 001Б","ozon_product_id":924191375,"seller_id":"92752"},
      {"reference_ordinal":5,"offer_id":"УФ 001Б","ozon_product_id":3468256200,"seller_id":"1498853"},
      {"reference_ordinal":6,"offer_id":"УФ 001Б","ozon_product_id":2698014827,"seller_id":"2713958"},
      {"reference_ordinal":7,"offer_id":"УФ 001Б","ozon_product_id":215996486,"seller_id":"79642"},
      {"reference_ordinal":8,"offer_id":"УФ 001Б","ozon_product_id":1566524732,"seller_id":"92752"},
      {"reference_ordinal":9,"offer_id":"УФ 001Б","ozon_product_id":5540658609,"seller_id":"3877579"},
      {"reference_ordinal":10,"offer_id":"УФ 001Б","ozon_product_id":2022731795,"seller_id":"5936"},
      {"reference_ordinal":11,"offer_id":"УФ 001Б","ozon_product_id":4601821825,"seller_id":"4767584"},
      {"reference_ordinal":12,"offer_id":"УФ 002Б","ozon_product_id":1201513545,"seller_id":"1382964"},
      {"reference_ordinal":13,"offer_id":"УФ 002Б","ozon_product_id":2936478004,"seller_id":"1615605"},
      {"reference_ordinal":14,"offer_id":"УФ 002Б","ozon_product_id":618137426,"seller_id":"24838"},
      {"reference_ordinal":15,"offer_id":"УФ 002Б","ozon_product_id":1628467740,"seller_id":"1321521"},
      {"reference_ordinal":16,"offer_id":"УФ 002Б","ozon_product_id":1480553506,"seller_id":"24838"},
      {"reference_ordinal":17,"offer_id":"УФ 002Б","ozon_product_id":1628774540,"seller_id":"660768"},
      {"reference_ordinal":18,"offer_id":"УФ 002Б","ozon_product_id":1624364470,"seller_id":"559265"},
      {"reference_ordinal":19,"offer_id":"УФ 002Б","ozon_product_id":266346879,"seller_id":"24838"},
      {"reference_ordinal":20,"offer_id":"УФ 002Б","ozon_product_id":4642158029,"seller_id":"4767584"},
      {"reference_ordinal":21,"offer_id":"УФ 004Б","ozon_product_id":613048940,"seller_id":"24838"},
      {"reference_ordinal":22,"offer_id":"УФ 004Б","ozon_product_id":1324012918,"seller_id":"1382964"},
      {"reference_ordinal":23,"offer_id":"УФ 004Б","ozon_product_id":519757297,"seller_id":"402554"},
      {"reference_ordinal":24,"offer_id":"УФ 004Б","ozon_product_id":1411048042,"seller_id":"1498853"},
      {"reference_ordinal":25,"offer_id":"УФ 004Б","ozon_product_id":3011421926,"seller_id":"3512424"},
      {"reference_ordinal":26,"offer_id":"УФ 004Б","ozon_product_id":3525756097,"seller_id":"790565"},
      {"reference_ordinal":27,"offer_id":"УФ 004Б","ozon_product_id":898384330,"seller_id":"92752"},
      {"reference_ordinal":28,"offer_id":"УФ 004Б","ozon_product_id":227576931,"seller_id":"24838"},
      {"reference_ordinal":29,"offer_id":"УФ 004Б","ozon_product_id":616223751,"seller_id":"507937"},
      {"reference_ordinal":30,"offer_id":"УФ 004Б","ozon_product_id":4642180551,"seller_id":"4767584"},
      {"reference_ordinal":31,"offer_id":"УФ 005Б","ozon_product_id":332405695,"seller_id":"24838"},
      {"reference_ordinal":32,"offer_id":"УФ 005Б","ozon_product_id":268629078,"seller_id":"24838"},
      {"reference_ordinal":33,"offer_id":"УФ 005Б","ozon_product_id":4381338927,"seller_id":"4654179"},
      {"reference_ordinal":34,"offer_id":"УФ 005Б","ozon_product_id":1086068777,"seller_id":"1231347"},
      {"reference_ordinal":35,"offer_id":"УФ 005Б","ozon_product_id":215758125,"seller_id":"59211"},
      {"reference_ordinal":36,"offer_id":"УФ 005Б","ozon_product_id":3959121966,"seller_id":"957375"},
      {"reference_ordinal":37,"offer_id":"УФ 005Б","ozon_product_id":2666178947,"seller_id":"2713958"},
      {"reference_ordinal":38,"offer_id":"УФ 005Б","ozon_product_id":2810830876,"seller_id":"2546484"},
      {"reference_ordinal":39,"offer_id":"УФ 005Б","ozon_product_id":658313675,"seller_id":"115929"},
      {"reference_ordinal":40,"offer_id":"УФ 005Б","ozon_product_id":3968916713,"seller_id":"3960341"},
      {"reference_ordinal":41,"offer_id":"УФ 005Б","ozon_product_id":4671328307,"seller_id":"4767584"}
    ]$json$::jsonb;
    differences text;
    resolved_count integer;
    missing_count integer;
    ambiguous_count integer;
    duplicate_target_count integer;
    unexpected_count integer;
    business_fingerprint text;
    function_fingerprint text;
    restricted_roles oid[];
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_attribute
         WHERE attrelid = 'public.competitor_watchlist_memberships'::regclass
           AND attname = 'reference_ordinal'
           AND attnum > 0
           AND NOT attisdropped
    ) THEN
        RAISE EXCEPTION 'reference_ordinal already exists';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_class c
         WHERE c.oid = 'public.competitor_watchlist_memberships'::regclass
           AND c.relkind = 'r'
           AND c.relpersistence = 'p'
           AND pg_get_userbyid(c.relowner) = 'efa'
           AND NOT c.relrowsecurity
           AND NOT c.relforcerowsecurity
           AND c.relacl IS NULL
    ) THEN
        RAISE EXCEPTION 'Membership relation owner/RLS/ACL baseline differs';
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

    WITH expected(attnum, attname, data_type, not_null, default_expr) AS (
        VALUES
            (1, 'membership_id', 'uuid', true, 'gen_random_uuid()'),
            (2, 'offer_id', 'text', true, NULL),
            (3, 'listing_id', 'uuid', true, NULL),
            (4, 'membership_status', 'text', true, NULL),
            (5, 'matched_oem_set', 'text[]', true, 'ARRAY[]::text[]'),
            (6, 'oem_confidence', 'text', true, NULL),
            (7, 'decision_reason', 'text', true, NULL),
            (8, 'quality_flags', 'text[]', true, 'ARRAY[]::text[]'),
            (9, 'valid_from', 'timestamp with time zone', true, 'now()'),
            (10, 'valid_to', 'timestamp with time zone', false, NULL),
            (11, 'created_at', 'timestamp with time zone', true, 'now()')
    ), actual AS (
        SELECT a.attnum::integer, a.attname::text,
               format_type(a.atttypid, a.atttypmod), a.attnotnull,
               pg_get_expr(d.adbin, d.adrelid)
          FROM pg_attribute a
          LEFT JOIN pg_attrdef d
            ON d.adrelid = a.attrelid AND d.adnum = a.attnum
         WHERE a.attrelid = 'public.competitor_watchlist_memberships'::regclass
           AND a.attnum > 0 AND NOT a.attisdropped
    ), diff AS (
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        UNION ALL
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(attname, ', ' ORDER BY attnum) INTO differences FROM diff;
    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Membership column baseline differs: %', differences;
    END IF;

    WITH expected(conname, contype, definition) AS (
        VALUES
          ('competitor_watchlist_memberships_listing_id_fkey', 'f', 'FOREIGN KEY (listing_id) REFERENCES public.competitor_listings(listing_id) ON DELETE RESTRICT'),
          ('competitor_watchlist_memberships_oem_confidence_check', 'c', 'CHECK (oem_confidence = ANY (ARRAY[''HIGH''::text, ''MEDIUM''::text, ''LOW''::text, ''MISMATCH''::text]))'),
          ('competitor_watchlist_memberships_offer_id_fkey', 'f', 'FOREIGN KEY (offer_id) REFERENCES public.products(offer_id) ON DELETE RESTRICT'),
          ('competitor_watchlist_memberships_pkey', 'p', 'PRIMARY KEY (membership_id)'),
          ('competitor_watchlist_memberships_status_check', 'c', 'CHECK (membership_status = ANY (ARRAY[''PRIMARY''::text, ''RESERVE''::text, ''EXCLUDE''::text, ''CONTROL''::text]))'),
          ('competitor_watchlist_memberships_validity_check', 'c', 'CHECK (valid_to IS NULL OR valid_to >= valid_from)'),
          ('competitor_watchlist_memberships_values_check', 'c', 'CHECK (btrim(decision_reason) <> ''''::text AND array_position(matched_oem_set, NULL::text) IS NULL AND array_position(quality_flags, NULL::text) IS NULL)')
    ), actual AS (
        SELECT conname::text, contype::text, pg_get_constraintdef(oid, true)
          FROM pg_constraint
         WHERE conrelid = 'public.competitor_watchlist_memberships'::regclass
    ), diff AS (
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        UNION ALL
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(conname, ', ' ORDER BY conname) INTO differences FROM diff;
    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Membership constraint baseline differs: %', differences;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.competitor_watchlist_memberships'::regclass
           AND (NOT convalidated OR condeferrable OR condeferred)
    ) THEN
        RAISE EXCEPTION 'Membership constraint validation/deferrability differs';
    END IF;

    WITH expected(indexname, indexdef) AS (
        VALUES
          ('competitor_watchlist_active_status_idx', 'CREATE INDEX competitor_watchlist_active_status_idx ON public.competitor_watchlist_memberships USING btree (offer_id, membership_status) WHERE (valid_to IS NULL)'),
          ('competitor_watchlist_memberships_pkey', 'CREATE UNIQUE INDEX competitor_watchlist_memberships_pkey ON public.competitor_watchlist_memberships USING btree (membership_id)'),
          ('competitor_watchlist_one_active_pair_uidx', 'CREATE UNIQUE INDEX competitor_watchlist_one_active_pair_uidx ON public.competitor_watchlist_memberships USING btree (offer_id, listing_id) WHERE (valid_to IS NULL)')
    ), actual AS (
        SELECT indexname::text, indexdef::text
          FROM pg_indexes
         WHERE schemaname = 'public'
           AND tablename = 'competitor_watchlist_memberships'
    ), diff AS (
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        UNION ALL
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(indexname, ', ' ORDER BY indexname) INTO differences FROM diff;
    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Membership index baseline differs: %', differences;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_trigger
         WHERE tgrelid = 'public.competitor_watchlist_memberships'::regclass
           AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION 'Unexpected membership trigger exists';
    END IF;

    IF (SELECT count(*) FROM public.competitor_watchlist_memberships) <> 41 THEN
        RAISE EXCEPTION 'Expected exactly 41 preexisting memberships';
    END IF;

    WITH a AS (
        SELECT * FROM jsonb_to_recordset(authoritative) AS x(
            reference_ordinal integer, offer_id text,
            ozon_product_id bigint, seller_id text
        )
    ), match_counts AS (
        SELECT a.reference_ordinal, count(m.membership_id)::integer AS matches
          FROM a
          LEFT JOIN public.competitor_listings l
            ON l.ozon_product_id = a.ozon_product_id
           AND l.seller_id = a.seller_id
           AND l.seller_key = 'OZON:' || a.seller_id
          LEFT JOIN public.competitor_watchlist_memberships m
            ON m.offer_id = a.offer_id AND m.listing_id = l.listing_id
         GROUP BY a.reference_ordinal
    ), resolved AS (
        SELECT a.reference_ordinal, m.membership_id
          FROM a
          JOIN public.competitor_listings l
            ON l.ozon_product_id = a.ozon_product_id
           AND l.seller_id = a.seller_id
           AND l.seller_key = 'OZON:' || a.seller_id
          JOIN public.competitor_watchlist_memberships m
            ON m.offer_id = a.offer_id AND m.listing_id = l.listing_id
    )
    SELECT count(*) FILTER (WHERE matches = 1),
           count(*) FILTER (WHERE matches = 0),
           count(*) FILTER (WHERE matches > 1),
           (SELECT count(*) FROM (
                SELECT membership_id FROM resolved
                 GROUP BY membership_id HAVING count(*) > 1
            ) d),
           (SELECT count(*)
              FROM public.competitor_watchlist_memberships m
             WHERE NOT EXISTS (
                 SELECT 1 FROM resolved r WHERE r.membership_id = m.membership_id
             ))
      INTO resolved_count, missing_count, ambiguous_count,
           duplicate_target_count, unexpected_count
      FROM match_counts;

    IF resolved_count <> 41 OR missing_count <> 0 OR ambiguous_count <> 0
       OR duplicate_target_count <> 0 OR unexpected_count <> 0 THEN
        RAISE EXCEPTION
          'Migration 020 identity reconciliation failed: resolved=% missing=% ambiguous=% duplicate_targets=% unexpected=%',
          resolved_count, missing_count, ambiguous_count,
          duplicate_target_count, unexpected_count;
    END IF;

    WITH a AS (
        SELECT * FROM jsonb_to_recordset(authoritative) AS x(
            reference_ordinal integer, offer_id text,
            ozon_product_id bigint, seller_id text
        )
    )
    SELECT md5(string_agg(to_jsonb(m)::text, E'\n' ORDER BY m.membership_id::text))
      INTO business_fingerprint
      FROM public.competitor_watchlist_memberships m;
    IF business_fingerprint IS DISTINCT FROM '3a577146f850e9bdb816c27b0dd07560' THEN
        RAISE EXCEPTION 'Membership business fingerprint differs';
    END IF;

    IF (SELECT count(*) FROM public.competitor_search_runs) <> 18
       OR (SELECT count(*) FROM public.competitor_observations) <> 174
       OR (SELECT count(*) FROM public.competitor_reviews) <> 0
       OR (SELECT count(*) FROM public.competitor_finding_sets) <> 1
       OR (SELECT count(*) FROM public.competitor_findings) <> 10 THEN
        RAISE EXCEPTION 'Competitor source history baseline differs';
    END IF;

    WITH expected(view_name, fingerprint) AS (
        VALUES
          ('competitor_finding_sets_reconciliation', 'ca93216706918764a231230d2a0c7da0'),
          ('competitor_findings', '6759ff1adad6100b788c1d5b7f9117bb'),
          ('competitor_latest_finding_set', '5d9f281b91e93bf632bb051ca24c214c'),
          ('competitor_monitoring_coverage', '4b3eacc90de2fc55ed2482d3c25e4d51'),
          ('competitor_reference_plan_source', 'f40d5b86acb329ea40b2d4e1dbe0a448'),
          ('competitor_snapshot_observations', '05b69587e36824bc16508b688631da49'),
          ('competitor_snapshot_runs', 'f7496f94bb8175f08635f5d6dd4b3df4'),
          ('product_cpc_daily', '170e9b0cb92470913effb495d51f3454'),
          ('product_daily_performance', '8d2d33577e07257be5502bbcc38a7f58'),
          ('product_overview', '614b70abec38215dc76749ec35ca2b25'),
          ('product_price_history', '7b3478e8e101a2841f7a0e47062ded36'),
          ('product_promotion_state', 'f8cc1bb0b02685f7f9b2c8fbbbe5e396'),
          ('product_region_logistics', 'db21649bf2b4e72cf1cda2adb2d5b4db'),
          ('product_stock_history', 'a126790040a3871ba553dff3015ed428')
    ), actual AS (
        SELECT c.relname::text AS view_name,
               md5(concat_ws(E'\n', c.relname, c.relkind::text,
                   pg_get_userbyid(c.relowner),
                   COALESCE((SELECT string_agg(x.option, ',' ORDER BY x.option)
                               FROM unnest(c.reloptions) x(option)), ''),
                   COALESCE((SELECT string_agg(format('%s:%s:%s', a.attnum,
                                      a.attname, format_type(a.atttypid, a.atttypmod)),
                                      ',' ORDER BY a.attnum)
                               FROM pg_attribute a WHERE a.attrelid = c.oid
                                AND a.attnum > 0 AND NOT a.attisdropped), ''),
                   pg_get_viewdef(c.oid, true),
                   COALESCE((SELECT string_agg(format('%s:%s:%s:%s',
                                      CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                           ELSE pg_get_userbyid(x.grantee) END,
                                      pg_get_userbyid(x.grantor), x.privilege_type,
                                      x.is_grantable), ',' ORDER BY
                                      CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                           ELSE pg_get_userbyid(x.grantee) END,
                                      pg_get_userbyid(x.grantor), x.privilege_type,
                                      x.is_grantable)
                               FROM aclexplode(COALESCE(c.relacl,
                                      acldefault('r', c.relowner))) x), '')
               )) AS fingerprint
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read' AND c.relkind = 'v'
    ), diff AS (
        SELECT COALESCE(e.view_name, a.view_name) AS view_name
          FROM expected e FULL JOIN actual a USING (view_name)
         WHERE e.fingerprint IS DISTINCT FROM a.fingerprint
    )
    SELECT string_agg(view_name, ', ' ORDER BY view_name)
      INTO differences FROM diff;
    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Approved fourteen-view MCP contract differs: %', differences;
    END IF;

    SELECT md5(concat_ws(E'\n', p.proname,
               pg_get_function_identity_arguments(p.oid),
               pg_get_function_result(p.oid), pg_get_userbyid(p.proowner),
               p.prosecdef, p.provolatile, p.proparallel,
               COALESCE((SELECT string_agg(x.option, ',' ORDER BY x.option)
                           FROM unnest(p.proconfig) x(option)), ''),
               pg_get_functiondef(p.oid),
               COALESCE((SELECT string_agg(format('%s:%s:%s:%s',
                                  CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                       ELSE pg_get_userbyid(x.grantee) END,
                                  pg_get_userbyid(x.grantor), x.privilege_type,
                                  x.is_grantable), ',' ORDER BY
                                  CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                       ELSE pg_get_userbyid(x.grantee) END,
                                  pg_get_userbyid(x.grantor), x.privilege_type,
                                  x.is_grantable)
                           FROM aclexplode(COALESCE(p.proacl,
                                  acldefault('f', p.proowner))) x), '')
           )) INTO function_fingerprint
      FROM pg_proc p
     WHERE p.oid = to_regprocedure('mcp_read.product_period_economics(date,date)');
    IF function_fingerprint IS DISTINCT FROM 'cf16870f884f2177f2ff4492c6344502' THEN
        RAISE EXCEPTION 'product_period_economics fingerprint differs';
    END IF;
END
$preflight$;

ALTER TABLE public.competitor_watchlist_memberships
    ADD COLUMN reference_ordinal integer;

DO $backfill$
DECLARE
    authoritative constant jsonb := $json$[
      {"reference_ordinal":1,"offer_id":"УФ 001Б","ozon_product_id":796591986,"seller_id":"24838"},{"reference_ordinal":2,"offer_id":"УФ 001Б","ozon_product_id":266328154,"seller_id":"24838"},{"reference_ordinal":3,"offer_id":"УФ 001Б","ozon_product_id":1356342041,"seller_id":"699471"},{"reference_ordinal":4,"offer_id":"УФ 001Б","ozon_product_id":924191375,"seller_id":"92752"},{"reference_ordinal":5,"offer_id":"УФ 001Б","ozon_product_id":3468256200,"seller_id":"1498853"},{"reference_ordinal":6,"offer_id":"УФ 001Б","ozon_product_id":2698014827,"seller_id":"2713958"},{"reference_ordinal":7,"offer_id":"УФ 001Б","ozon_product_id":215996486,"seller_id":"79642"},{"reference_ordinal":8,"offer_id":"УФ 001Б","ozon_product_id":1566524732,"seller_id":"92752"},{"reference_ordinal":9,"offer_id":"УФ 001Б","ozon_product_id":5540658609,"seller_id":"3877579"},{"reference_ordinal":10,"offer_id":"УФ 001Б","ozon_product_id":2022731795,"seller_id":"5936"},{"reference_ordinal":11,"offer_id":"УФ 001Б","ozon_product_id":4601821825,"seller_id":"4767584"},
      {"reference_ordinal":12,"offer_id":"УФ 002Б","ozon_product_id":1201513545,"seller_id":"1382964"},{"reference_ordinal":13,"offer_id":"УФ 002Б","ozon_product_id":2936478004,"seller_id":"1615605"},{"reference_ordinal":14,"offer_id":"УФ 002Б","ozon_product_id":618137426,"seller_id":"24838"},{"reference_ordinal":15,"offer_id":"УФ 002Б","ozon_product_id":1628467740,"seller_id":"1321521"},{"reference_ordinal":16,"offer_id":"УФ 002Б","ozon_product_id":1480553506,"seller_id":"24838"},{"reference_ordinal":17,"offer_id":"УФ 002Б","ozon_product_id":1628774540,"seller_id":"660768"},{"reference_ordinal":18,"offer_id":"УФ 002Б","ozon_product_id":1624364470,"seller_id":"559265"},{"reference_ordinal":19,"offer_id":"УФ 002Б","ozon_product_id":266346879,"seller_id":"24838"},{"reference_ordinal":20,"offer_id":"УФ 002Б","ozon_product_id":4642158029,"seller_id":"4767584"},
      {"reference_ordinal":21,"offer_id":"УФ 004Б","ozon_product_id":613048940,"seller_id":"24838"},{"reference_ordinal":22,"offer_id":"УФ 004Б","ozon_product_id":1324012918,"seller_id":"1382964"},{"reference_ordinal":23,"offer_id":"УФ 004Б","ozon_product_id":519757297,"seller_id":"402554"},{"reference_ordinal":24,"offer_id":"УФ 004Б","ozon_product_id":1411048042,"seller_id":"1498853"},{"reference_ordinal":25,"offer_id":"УФ 004Б","ozon_product_id":3011421926,"seller_id":"3512424"},{"reference_ordinal":26,"offer_id":"УФ 004Б","ozon_product_id":3525756097,"seller_id":"790565"},{"reference_ordinal":27,"offer_id":"УФ 004Б","ozon_product_id":898384330,"seller_id":"92752"},{"reference_ordinal":28,"offer_id":"УФ 004Б","ozon_product_id":227576931,"seller_id":"24838"},{"reference_ordinal":29,"offer_id":"УФ 004Б","ozon_product_id":616223751,"seller_id":"507937"},{"reference_ordinal":30,"offer_id":"УФ 004Б","ozon_product_id":4642180551,"seller_id":"4767584"},
      {"reference_ordinal":31,"offer_id":"УФ 005Б","ozon_product_id":332405695,"seller_id":"24838"},{"reference_ordinal":32,"offer_id":"УФ 005Б","ozon_product_id":268629078,"seller_id":"24838"},{"reference_ordinal":33,"offer_id":"УФ 005Б","ozon_product_id":4381338927,"seller_id":"4654179"},{"reference_ordinal":34,"offer_id":"УФ 005Б","ozon_product_id":1086068777,"seller_id":"1231347"},{"reference_ordinal":35,"offer_id":"УФ 005Б","ozon_product_id":215758125,"seller_id":"59211"},{"reference_ordinal":36,"offer_id":"УФ 005Б","ozon_product_id":3959121966,"seller_id":"957375"},{"reference_ordinal":37,"offer_id":"УФ 005Б","ozon_product_id":2666178947,"seller_id":"2713958"},{"reference_ordinal":38,"offer_id":"УФ 005Б","ozon_product_id":2810830876,"seller_id":"2546484"},{"reference_ordinal":39,"offer_id":"УФ 005Б","ozon_product_id":658313675,"seller_id":"115929"},{"reference_ordinal":40,"offer_id":"УФ 005Б","ozon_product_id":3968916713,"seller_id":"3960341"},{"reference_ordinal":41,"offer_id":"УФ 005Б","ozon_product_id":4671328307,"seller_id":"4767584"}
    ]$json$::jsonb;
    updated_count integer;
    mismatch_count integer;
BEGIN
    WITH a AS (
        SELECT * FROM jsonb_to_recordset(authoritative) AS x(
            reference_ordinal integer, offer_id text,
            ozon_product_id bigint, seller_id text
        )
    )
    UPDATE public.competitor_watchlist_memberships m
       SET reference_ordinal = a.reference_ordinal
      FROM a
      JOIN public.competitor_listings l
        ON l.ozon_product_id = a.ozon_product_id
       AND l.seller_id = a.seller_id
       AND l.seller_key = 'OZON:' || a.seller_id
     WHERE m.offer_id = a.offer_id
       AND m.listing_id = l.listing_id
       AND m.reference_ordinal IS NULL;
    GET DIAGNOSTICS updated_count = ROW_COUNT;

    IF updated_count <> 41 THEN
        RAISE EXCEPTION 'Migration 025 updated % rows instead of 41', updated_count;
    END IF;

    WITH a AS (
        SELECT * FROM jsonb_to_recordset(authoritative) AS x(
            reference_ordinal integer, offer_id text,
            ozon_product_id bigint, seller_id text
        )
    )
    SELECT count(*) INTO mismatch_count
      FROM a
      LEFT JOIN public.competitor_listings l
        ON l.ozon_product_id = a.ozon_product_id
       AND l.seller_id = a.seller_id
       AND l.seller_key = 'OZON:' || a.seller_id
      LEFT JOIN public.competitor_watchlist_memberships m
        ON m.offer_id = a.offer_id AND m.listing_id = l.listing_id
       AND m.reference_ordinal = a.reference_ordinal
     WHERE m.membership_id IS NULL;

    IF mismatch_count <> 0
       OR (SELECT count(*) FROM public.competitor_watchlist_memberships
            WHERE reference_ordinal IS NOT NULL) <> 41
       OR (SELECT min(reference_ordinal) FROM public.competitor_watchlist_memberships) <> 1
       OR (SELECT max(reference_ordinal) FROM public.competitor_watchlist_memberships) <> 41
       OR (SELECT count(DISTINCT reference_ordinal)
             FROM public.competitor_watchlist_memberships) <> 41
       OR EXISTS (
            SELECT g.ordinal
              FROM generate_series(1, 41) g(ordinal)
              LEFT JOIN public.competitor_watchlist_memberships m
                ON m.reference_ordinal = g.ordinal
             WHERE m.membership_id IS NULL
       ) THEN
        RAISE EXCEPTION 'Migration 025 deterministic backfill exactness failed';
    END IF;
END
$backfill$;

ALTER TABLE public.competitor_watchlist_memberships
    ALTER COLUMN reference_ordinal SET NOT NULL,
    ADD CONSTRAINT competitor_watchlist_memberships_reference_ordinal_check
        CHECK (reference_ordinal > 0),
    ADD CONSTRAINT competitor_watchlist_memberships_reference_ordinal_key
        UNIQUE (reference_ordinal);

COMMENT ON COLUMN public.competitor_watchlist_memberships.reference_ordinal IS
    'Stable business ordering identity. Explicit allocation only; never update, renumber, compact, or reuse retired values. New values must exceed every historically allocated ordinal.';

CREATE OR REPLACE VIEW mcp_read.competitor_reference_plan_source
WITH (security_barrier = true) AS
SELECT
    'PROFILE'::text AS record_kind,
    p.offer_id,
    p.watchlist_state,
    NULL::uuid AS sku_oem_id,
    NULL::text AS query_text_exact,
    NULL::text AS query_normalized,
    NULL::boolean AS oem_active,
    NULL::timestamptz AS oem_created_at,
    NULL::uuid AS membership_id,
    NULL::text AS membership_status,
    NULL::text[] AS matched_oem_set,
    NULL::timestamptz AS valid_from,
    NULL::timestamptz AS valid_to,
    NULL::uuid AS listing_id,
    NULL::uuid AS product_family_id,
    NULL::bigint AS ozon_product_id,
    NULL::text AS seller_id,
    NULL::text AS product_name,
    NULL::integer AS reference_ordinal
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
    NULL::timestamptz AS valid_from,
    NULL::timestamptz AS valid_to,
    NULL::uuid AS listing_id,
    NULL::uuid AS product_family_id,
    NULL::bigint AS ozon_product_id,
    NULL::text AS seller_id,
    NULL::text AS product_name,
    NULL::integer AS reference_ordinal
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
    f.product_name,
    m.reference_ordinal
FROM public.competitor_watchlist_memberships m
JOIN public.competitor_sku_profiles p ON p.offer_id = m.offer_id
JOIN public.competitor_listings l ON l.listing_id = m.listing_id
JOIN public.competitor_product_families f
  ON f.product_family_id = l.product_family_id
CROSS JOIN LATERAL unnest(m.matched_oem_set) q(query_text_exact)
LEFT JOIN public.competitor_sku_oems o
  ON o.offer_id = m.offer_id
 AND o.oem_normalized = q.query_text_exact;

ALTER VIEW mcp_read.competitor_reference_plan_source OWNER TO efa;
REVOKE ALL PRIVILEGES ON TABLE mcp_read.competitor_reference_plan_source
    FROM PUBLIC, efa_mcp_readonly;
GRANT SELECT ON TABLE mcp_read.competitor_reference_plan_source
    TO efa_mcp_reader;
COMMENT ON VIEW mcp_read.competitor_reference_plan_source IS
    'Minimal factual profile, OEM, and historical membership source for deterministic Competitor Monitor reference-plan reconstruction. Membership rows expose stable reference_ordinal ordering metadata.';

DO $postconditions$
DECLARE
    business_fingerprint text;
    changed_view_fingerprint text;
    differences text;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_attribute a
         WHERE a.attrelid = 'public.competitor_watchlist_memberships'::regclass
           AND a.attname = 'reference_ordinal'
           AND a.attnum = 12
           AND format_type(a.atttypid, a.atttypmod) = 'integer'
           AND a.attnotnull AND NOT a.atthasdef AND NOT a.attisdropped
    ) THEN
        RAISE EXCEPTION 'reference_ordinal final column contract differs';
    END IF;

    IF (SELECT count(*) FROM public.competitor_watchlist_memberships) <> 41
       OR (SELECT count(*) FROM public.competitor_watchlist_memberships
            WHERE reference_ordinal BETWEEN 1 AND 41) <> 41
       OR (SELECT count(DISTINCT reference_ordinal)
             FROM public.competitor_watchlist_memberships) <> 41 THEN
        RAISE EXCEPTION 'Migration 025 final ordinal population differs';
    END IF;

    SELECT md5(string_agg((to_jsonb(m) - 'reference_ordinal')::text,
                          E'\n' ORDER BY m.membership_id::text))
      INTO business_fingerprint
      FROM public.competitor_watchlist_memberships m;
    IF business_fingerprint IS DISTINCT FROM '3a577146f850e9bdb816c27b0dd07560' THEN
        RAISE EXCEPTION 'Membership business fields changed during Migration 025';
    END IF;

    IF (SELECT count(*) FROM public.competitor_search_runs) <> 18
       OR (SELECT count(*) FROM public.competitor_observations) <> 174
       OR (SELECT count(*) FROM public.competitor_reviews) <> 0
       OR (SELECT count(*) FROM public.competitor_finding_sets) <> 1
       OR (SELECT count(*) FROM public.competitor_findings) <> 10 THEN
        RAISE EXCEPTION 'Migration 025 changed source history counts';
    END IF;

    SELECT md5(concat_ws(E'\n', c.relname, c.relkind::text,
               pg_get_userbyid(c.relowner),
               COALESCE((SELECT string_agg(x.option, ',' ORDER BY x.option)
                           FROM unnest(c.reloptions) x(option)), ''),
               COALESCE((SELECT string_agg(format('%s:%s:%s', a.attnum,
                                  a.attname, format_type(a.atttypid, a.atttypmod)),
                                  ',' ORDER BY a.attnum)
                           FROM pg_attribute a WHERE a.attrelid = c.oid
                            AND a.attnum > 0 AND NOT a.attisdropped), ''),
               pg_get_viewdef(c.oid, true),
               COALESCE((SELECT string_agg(format('%s:%s:%s:%s',
                                  CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                       ELSE pg_get_userbyid(x.grantee) END,
                                  pg_get_userbyid(x.grantor), x.privilege_type,
                                  x.is_grantable), ',' ORDER BY
                                  CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                       ELSE pg_get_userbyid(x.grantee) END,
                                  pg_get_userbyid(x.grantor), x.privilege_type,
                                  x.is_grantable)
                           FROM aclexplode(COALESCE(c.relacl,
                                  acldefault('r', c.relowner))) x), '')
           )) INTO changed_view_fingerprint
      FROM pg_class c
     WHERE c.oid = 'mcp_read.competitor_reference_plan_source'::regclass;
    IF changed_view_fingerprint IS DISTINCT FROM '697112d18462d8f69f1174745d97f5e4' THEN
        RAISE EXCEPTION 'Updated reference-plan view fingerprint differs';
    END IF;

    WITH expected(view_name, fingerprint) AS (
        VALUES
          ('competitor_finding_sets_reconciliation', 'ca93216706918764a231230d2a0c7da0'),
          ('competitor_findings', '6759ff1adad6100b788c1d5b7f9117bb'),
          ('competitor_latest_finding_set', '5d9f281b91e93bf632bb051ca24c214c'),
          ('competitor_monitoring_coverage', '4b3eacc90de2fc55ed2482d3c25e4d51'),
          ('competitor_snapshot_observations', '05b69587e36824bc16508b688631da49'),
          ('competitor_snapshot_runs', 'f7496f94bb8175f08635f5d6dd4b3df4'),
          ('product_cpc_daily', '170e9b0cb92470913effb495d51f3454'),
          ('product_daily_performance', '8d2d33577e07257be5502bbcc38a7f58'),
          ('product_overview', '614b70abec38215dc76749ec35ca2b25'),
          ('product_price_history', '7b3478e8e101a2841f7a0e47062ded36'),
          ('product_promotion_state', 'f8cc1bb0b02685f7f9b2c8fbbbe5e396'),
          ('product_region_logistics', 'db21649bf2b4e72cf1cda2adb2d5b4db'),
          ('product_stock_history', 'a126790040a3871ba553dff3015ed428')
    ), actual AS (
        SELECT c.relname::text AS view_name,
               md5(concat_ws(E'\n', c.relname, c.relkind::text,
                   pg_get_userbyid(c.relowner),
                   COALESCE((SELECT string_agg(x.option, ',' ORDER BY x.option)
                               FROM unnest(c.reloptions) x(option)), ''),
                   COALESCE((SELECT string_agg(format('%s:%s:%s', a.attnum,
                                      a.attname, format_type(a.atttypid, a.atttypmod)),
                                      ',' ORDER BY a.attnum)
                               FROM pg_attribute a WHERE a.attrelid = c.oid
                                AND a.attnum > 0 AND NOT a.attisdropped), ''),
                   pg_get_viewdef(c.oid, true),
                   COALESCE((SELECT string_agg(format('%s:%s:%s:%s',
                                      CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                           ELSE pg_get_userbyid(x.grantee) END,
                                      pg_get_userbyid(x.grantor), x.privilege_type,
                                      x.is_grantable), ',' ORDER BY
                                      CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                                           ELSE pg_get_userbyid(x.grantee) END,
                                      pg_get_userbyid(x.grantor), x.privilege_type,
                                      x.is_grantable)
                               FROM aclexplode(COALESCE(c.relacl,
                                      acldefault('r', c.relowner))) x), '')
               )) AS fingerprint
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read' AND c.relkind = 'v'
           AND c.relname <> 'competitor_reference_plan_source'
    ), diff AS (
        SELECT COALESCE(e.view_name, a.view_name) AS view_name
          FROM expected e FULL JOIN actual a USING (view_name)
         WHERE e.fingerprint IS DISTINCT FROM a.fingerprint
    )
    SELECT string_agg(view_name, ', ' ORDER BY view_name)
      INTO differences FROM diff;
    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Unrelated MCP view changed: %', differences;
    END IF;

    IF EXISTS (
           SELECT 1
             FROM pg_class c,
                  LATERAL aclexplode(COALESCE(
                      c.relacl, acldefault('r', c.relowner)
                  )) acl
            WHERE c.oid =
                  'public.competitor_watchlist_memberships'::regclass
              AND acl.grantee = 0
       ) OR has_table_privilege('efa_mcp_reader',
           'public.competitor_watchlist_memberships', 'SELECT')
       OR has_table_privilege('efa_mcp_readonly',
           'public.competitor_watchlist_memberships', 'SELECT')
       OR NOT has_table_privilege('efa_mcp_reader',
           'mcp_read.competitor_reference_plan_source', 'SELECT')
       OR NOT has_table_privilege('efa_mcp_readonly',
           'mcp_read.competitor_reference_plan_source', 'SELECT')
       OR EXISTS (
           SELECT 1
             FROM pg_class c,
                  LATERAL aclexplode(COALESCE(
                      c.relacl, acldefault('r', c.relowner)
                  )) acl
            WHERE c.oid =
                  'mcp_read.competitor_reference_plan_source'::regclass
              AND acl.grantee = 0
       ) THEN
        RAISE EXCEPTION 'Migration 025 ACL contract differs';
    END IF;

    IF (SELECT count(*)
          FROM pg_rewrite
         WHERE ev_class =
               'mcp_read.competitor_reference_plan_source'::regclass) <> 1
       OR NOT EXISTS (
           SELECT 1
             FROM pg_rewrite
            WHERE ev_class =
                  'mcp_read.competitor_reference_plan_source'::regclass
              AND rulename = '_RETURN'
              AND ev_type = '1'
              AND ev_enabled = 'O'
              AND is_instead
       ) OR EXISTS (
           SELECT 1
             FROM pg_trigger
            WHERE tgrelid =
                  'mcp_read.competitor_reference_plan_source'::regclass
              AND NOT tgisinternal
       ) THEN
        RAISE EXCEPTION 'Migration 025 view rule/trigger contract differs';
    END IF;
END
$postconditions$;

COMMIT;
