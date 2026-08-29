-- Read-only validation for Migration 025.
--
-- The SQL validates the database-resident contract. The MCP runtime tool count
-- (exactly nine) and the archived T1 byte-for-byte replay are external review
-- checks because neither the application source nor filesystem artifacts belong
-- inside PostgreSQL validation. Expected external replay results:
--   evidence SHA-256 77c8e862688fccbe61e283c73566a65d0920fc0b18931314c64e68e51ac85b08
--   payload  SHA-256 6449a24a3a68809642b69bf043056fc4b9845c48a973e6d72852be2fbe499852
--   batch ref cm-snapshot-v1:batch:961baa306c34ff7dc6c973e02b49d0c26226864709148fe6c128109e6a68138e

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL timezone = 'UTC';
SET LOCAL search_path = pg_catalog;

DO $validation$
DECLARE
    authoritative constant jsonb := $json$[
      {"reference_ordinal":1,"offer_id":"УФ 001Б","ozon_product_id":796591986,"seller_id":"24838","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":2,"offer_id":"УФ 001Б","ozon_product_id":266328154,"seller_id":"24838","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":3,"offer_id":"УФ 001Б","ozon_product_id":1356342041,"seller_id":"699471","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":4,"offer_id":"УФ 001Б","ozon_product_id":924191375,"seller_id":"92752","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":5,"offer_id":"УФ 001Б","ozon_product_id":3468256200,"seller_id":"1498853","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":6,"offer_id":"УФ 001Б","ozon_product_id":2698014827,"seller_id":"2713958","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":7,"offer_id":"УФ 001Б","ozon_product_id":215996486,"seller_id":"79642","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":8,"offer_id":"УФ 001Б","ozon_product_id":1566524732,"seller_id":"92752","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":9,"offer_id":"УФ 001Б","ozon_product_id":5540658609,"seller_id":"3877579","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":10,"offer_id":"УФ 001Б","ozon_product_id":2022731795,"seller_id":"5936","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":11,"offer_id":"УФ 001Б","ozon_product_id":4601821825,"seller_id":"4767584","matched_oem_set":["80292SLJ013"]},
      {"reference_ordinal":12,"offer_id":"УФ 002Б","ozon_product_id":1201513545,"seller_id":"1382964","matched_oem_set":["6R0820367","JZW819653F"]},
      {"reference_ordinal":13,"offer_id":"УФ 002Б","ozon_product_id":2936478004,"seller_id":"1615605","matched_oem_set":["6R0820367","JZW819653F"]},
      {"reference_ordinal":14,"offer_id":"УФ 002Б","ozon_product_id":618137426,"seller_id":"24838","matched_oem_set":["6R0820367","JZW819653F"]},
      {"reference_ordinal":15,"offer_id":"УФ 002Б","ozon_product_id":1628467740,"seller_id":"1321521","matched_oem_set":["6R0820367","JZW819653F"]},
      {"reference_ordinal":16,"offer_id":"УФ 002Б","ozon_product_id":1480553506,"seller_id":"24838","matched_oem_set":["6R0820367","JZW819653F"]},
      {"reference_ordinal":17,"offer_id":"УФ 002Б","ozon_product_id":1628774540,"seller_id":"660768","matched_oem_set":["6R0820367","JZW819653F"]},
      {"reference_ordinal":18,"offer_id":"УФ 002Б","ozon_product_id":1624364470,"seller_id":"559265","matched_oem_set":["6R0820367","JZW819653F"]},
      {"reference_ordinal":19,"offer_id":"УФ 002Б","ozon_product_id":266346879,"seller_id":"24838","matched_oem_set":["6R0820367","JZW819653F"]},
      {"reference_ordinal":20,"offer_id":"УФ 002Б","ozon_product_id":4642158029,"seller_id":"4767584","matched_oem_set":["6R0820367","JZW819653F"]},
      {"reference_ordinal":21,"offer_id":"УФ 004Б","ozon_product_id":613048940,"seller_id":"24838","matched_oem_set":["5Q0819644A","5Q0819653","5Q0819669"]},
      {"reference_ordinal":22,"offer_id":"УФ 004Б","ozon_product_id":1324012918,"seller_id":"1382964","matched_oem_set":["5Q0819644A","5Q0819653","5Q0819669"]},
      {"reference_ordinal":23,"offer_id":"УФ 004Б","ozon_product_id":519757297,"seller_id":"402554","matched_oem_set":["5Q0819644A","5Q0819653","5Q0819669"]},
      {"reference_ordinal":24,"offer_id":"УФ 004Б","ozon_product_id":1411048042,"seller_id":"1498853","matched_oem_set":["5Q0819644A","5Q0819653","5Q0819669"]},
      {"reference_ordinal":25,"offer_id":"УФ 004Б","ozon_product_id":3011421926,"seller_id":"3512424","matched_oem_set":["5Q0819644A","5Q0819653","5Q0819669"]},
      {"reference_ordinal":26,"offer_id":"УФ 004Б","ozon_product_id":3525756097,"seller_id":"790565","matched_oem_set":["5Q0819644A","5Q0819653","5Q0819669"]},
      {"reference_ordinal":27,"offer_id":"УФ 004Б","ozon_product_id":898384330,"seller_id":"92752","matched_oem_set":["5Q0819653","5Q0819669"]},
      {"reference_ordinal":28,"offer_id":"УФ 004Б","ozon_product_id":227576931,"seller_id":"24838","matched_oem_set":["5Q0819644A","5Q0819669"]},
      {"reference_ordinal":29,"offer_id":"УФ 004Б","ozon_product_id":616223751,"seller_id":"507937","matched_oem_set":["5Q0819644A","5Q0819653","5Q0819669"]},
      {"reference_ordinal":30,"offer_id":"УФ 004Б","ozon_product_id":4642180551,"seller_id":"4767584","matched_oem_set":["5Q0819644A","5Q0819653","5Q0819669"]},
      {"reference_ordinal":31,"offer_id":"УФ 005Б","ozon_product_id":332405695,"seller_id":"24838","matched_oem_set":["647975","6479C2","647941"]},
      {"reference_ordinal":32,"offer_id":"УФ 005Б","ozon_product_id":268629078,"seller_id":"24838","matched_oem_set":["647975","6479C2","647941"]},
      {"reference_ordinal":33,"offer_id":"УФ 005Б","ozon_product_id":4381338927,"seller_id":"4654179","matched_oem_set":["6479C2"]},
      {"reference_ordinal":34,"offer_id":"УФ 005Б","ozon_product_id":1086068777,"seller_id":"1231347","matched_oem_set":["647975","6479C2","647941"]},
      {"reference_ordinal":35,"offer_id":"УФ 005Б","ozon_product_id":215758125,"seller_id":"59211","matched_oem_set":["647975","6479C2","647941"]},
      {"reference_ordinal":36,"offer_id":"УФ 005Б","ozon_product_id":3959121966,"seller_id":"957375","matched_oem_set":["647975","6479C2","647941"]},
      {"reference_ordinal":37,"offer_id":"УФ 005Б","ozon_product_id":2666178947,"seller_id":"2713958","matched_oem_set":["647975","6479C2","647941"]},
      {"reference_ordinal":38,"offer_id":"УФ 005Б","ozon_product_id":2810830876,"seller_id":"2546484","matched_oem_set":["647975","6479C2","647941"]},
      {"reference_ordinal":39,"offer_id":"УФ 005Б","ozon_product_id":658313675,"seller_id":"115929","matched_oem_set":["647975","647941"]},
      {"reference_ordinal":40,"offer_id":"УФ 005Б","ozon_product_id":3968916713,"seller_id":"3960341","matched_oem_set":["647975","6479C2","647941"]},
      {"reference_ordinal":41,"offer_id":"УФ 005Б","ozon_product_id":4671328307,"seller_id":"4767584","matched_oem_set":["647975","6479C2","647941"]}
    ]$json$::jsonb;
    differences text;
    resolved_count integer;
    missing_count integer;
    ambiguous_count integer;
    duplicate_target_count integer;
    business_fingerprint text;
    changed_view_fingerprint text;
    function_fingerprint text;
    expected_queries text[];
    actual_queries text[];
    expected_slots text[];
    actual_slots text[];
    t0_queries text[];
    t1_queries text[];
    t0_slots text[];
    t1_slots text[];
    restricted_roles oid[];
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Validation 025 must run only in database efa';
    END IF;

    IF to_regclass('public.competitor_watchlist_memberships') IS NULL
       OR to_regclass('mcp_read.competitor_reference_plan_source') IS NULL THEN
        RAISE EXCEPTION 'Migration 025 relations are missing';
    END IF;

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

    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
         WHERE c.oid = 'public.competitor_watchlist_memberships'::regclass
           AND c.relkind = 'r' AND c.relpersistence = 'p'
           AND pg_get_userbyid(c.relowner) = 'efa'
           AND NOT c.relrowsecurity AND NOT c.relforcerowsecurity
           AND c.relacl IS NULL
    ) THEN
        RAISE EXCEPTION 'Membership owner/RLS/raw ACL contract differs';
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
            (11, 'created_at', 'timestamp with time zone', true, 'now()'),
            (12, 'reference_ordinal', 'integer', true, NULL)
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
        RAISE EXCEPTION 'Membership exact column contract differs: %', differences;
    END IF;

    WITH expected(conname, contype, definition) AS (
        VALUES
          ('competitor_watchlist_memberships_listing_id_fkey', 'f', 'FOREIGN KEY (listing_id) REFERENCES public.competitor_listings(listing_id) ON DELETE RESTRICT'),
          ('competitor_watchlist_memberships_oem_confidence_check', 'c', 'CHECK (oem_confidence = ANY (ARRAY[''HIGH''::text, ''MEDIUM''::text, ''LOW''::text, ''MISMATCH''::text]))'),
          ('competitor_watchlist_memberships_offer_id_fkey', 'f', 'FOREIGN KEY (offer_id) REFERENCES public.products(offer_id) ON DELETE RESTRICT'),
          ('competitor_watchlist_memberships_pkey', 'p', 'PRIMARY KEY (membership_id)'),
          ('competitor_watchlist_memberships_reference_ordinal_check', 'c', 'CHECK (reference_ordinal > 0)'),
          ('competitor_watchlist_memberships_reference_ordinal_key', 'u', 'UNIQUE (reference_ordinal)'),
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
        RAISE EXCEPTION 'Membership exact constraint contract differs: %', differences;
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
          ('competitor_watchlist_memberships_reference_ordinal_key', 'CREATE UNIQUE INDEX competitor_watchlist_memberships_reference_ordinal_key ON public.competitor_watchlist_memberships USING btree (reference_ordinal)'),
          ('competitor_watchlist_one_active_pair_uidx', 'CREATE UNIQUE INDEX competitor_watchlist_one_active_pair_uidx ON public.competitor_watchlist_memberships USING btree (offer_id, listing_id) WHERE (valid_to IS NULL)')
    ), actual AS (
        SELECT indexname::text, indexdef::text FROM pg_indexes
         WHERE schemaname = 'public'
           AND tablename = 'competitor_watchlist_memberships'
    ), diff AS (
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        UNION ALL
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(indexname, ', ' ORDER BY indexname) INTO differences FROM diff;
    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Membership exact index contract differs: %', differences;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_trigger
         WHERE tgrelid = 'public.competitor_watchlist_memberships'::regclass
           AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION 'Unexpected membership trigger exists';
    END IF;

    WITH a AS (
        SELECT * FROM jsonb_to_recordset(authoritative) AS x(
          reference_ordinal integer, offer_id text, ozon_product_id bigint,
          seller_id text, matched_oem_set text[]
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
           AND m.reference_ordinal = a.reference_ordinal
           AND m.matched_oem_set = a.matched_oem_set
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
           AND m.reference_ordinal = a.reference_ordinal
           AND m.matched_oem_set = a.matched_oem_set
    )
    SELECT count(*) FILTER (WHERE matches = 1),
           count(*) FILTER (WHERE matches = 0),
           count(*) FILTER (WHERE matches > 1),
           (SELECT count(*) FROM (
              SELECT membership_id FROM resolved
               GROUP BY membership_id HAVING count(*) > 1
            ) d)
      INTO resolved_count, missing_count, ambiguous_count, duplicate_target_count
      FROM match_counts;

    IF resolved_count <> 41 OR missing_count <> 0 OR ambiguous_count <> 0
       OR duplicate_target_count <> 0 THEN
        RAISE EXCEPTION
          'Legacy ordinal reconciliation failed: resolved=% missing=% ambiguous=% duplicate_targets=%',
          resolved_count, missing_count, ambiguous_count, duplicate_target_count;
    END IF;

    IF EXISTS (
        SELECT g.ordinal FROM generate_series(1, 41) g(ordinal)
        LEFT JOIN public.competitor_watchlist_memberships m
          ON m.reference_ordinal = g.ordinal
        WHERE m.membership_id IS NULL
    ) OR EXISTS (
        SELECT 1 FROM public.competitor_watchlist_memberships m
         WHERE m.reference_ordinal <= 41
           AND NOT EXISTS (
             SELECT 1
               FROM jsonb_to_recordset(authoritative) AS a(
                 reference_ordinal integer, offer_id text,
                 ozon_product_id bigint, seller_id text,
                 matched_oem_set text[]
               )
              WHERE a.reference_ordinal = m.reference_ordinal
           )
    ) THEN
        RAISE EXCEPTION 'Legacy 1..41 range contains a gap or non-authoritative row';
    END IF;

    WITH a AS (
      SELECT * FROM jsonb_to_recordset(authoritative) AS x(
        reference_ordinal integer, offer_id text, ozon_product_id bigint,
        seller_id text, matched_oem_set text[]
      )
    ), legacy AS (
      SELECT m.* FROM a
      JOIN public.competitor_listings l
        ON l.ozon_product_id = a.ozon_product_id
       AND l.seller_id = a.seller_id
       AND l.seller_key = 'OZON:' || a.seller_id
      JOIN public.competitor_watchlist_memberships m
        ON m.offer_id = a.offer_id AND m.listing_id = l.listing_id
    )
    SELECT md5(string_agg((to_jsonb(m) - 'reference_ordinal')::text,
                          E'\n' ORDER BY m.membership_id::text))
      INTO business_fingerprint FROM legacy m;
    IF business_fingerprint IS DISTINCT FROM '3a577146f850e9bdb816c27b0dd07560' THEN
        RAISE EXCEPTION 'Legacy membership business fingerprint differs';
    END IF;

    IF (SELECT count(*) FROM public.competitor_search_runs) <> 18
       OR (SELECT count(*) FROM public.competitor_observations) <> 174
       OR (SELECT count(*) FROM public.competitor_reviews) <> 0
       OR (SELECT count(*) FROM public.competitor_finding_sets) <> 1
       OR (SELECT count(*) FROM public.competitor_findings) <> 10 THEN
        RAISE EXCEPTION 'Source history counts differ from 18/174/0/1/10';
    END IF;

    WITH expected(attnum, attname, data_type) AS (
      VALUES
        (1,'record_kind','text'),(2,'offer_id','text'),
        (3,'watchlist_state','text'),(4,'sku_oem_id','uuid'),
        (5,'query_text_exact','text'),(6,'query_normalized','text'),
        (7,'oem_active','boolean'),
        (8,'oem_created_at','timestamp with time zone'),
        (9,'membership_id','uuid'),(10,'membership_status','text'),
        (11,'matched_oem_set','text[]'),
        (12,'valid_from','timestamp with time zone'),
        (13,'valid_to','timestamp with time zone'),(14,'listing_id','uuid'),
        (15,'product_family_id','uuid'),(16,'ozon_product_id','bigint'),
        (17,'seller_id','text'),(18,'product_name','text'),
        (19,'reference_ordinal','integer')
    ), actual AS (
      SELECT a.attnum::integer,a.attname::text,
             format_type(a.atttypid,a.atttypmod)
        FROM pg_attribute a
       WHERE a.attrelid='mcp_read.competitor_reference_plan_source'::regclass
         AND a.attnum>0 AND NOT a.attisdropped
    ), diff AS (
      (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
      UNION ALL
      (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(attname, ', ' ORDER BY attnum) INTO differences FROM diff;
    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Reference-plan view column contract differs: %', differences;
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
        RAISE EXCEPTION 'Reference-plan exact definition fingerprint differs';
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM pg_class c
       WHERE c.oid='mcp_read.competitor_reference_plan_source'::regclass
         AND c.relkind='v' AND pg_get_userbyid(c.relowner)='efa'
         AND c.reloptions=ARRAY['security_barrier=true']::text[]
    ) THEN
        RAISE EXCEPTION 'Reference-plan owner/security_barrier differs';
    END IF;

    WITH expected(grantee, privilege_type, is_grantable) AS (
      VALUES
        ('efa','DELETE',false),('efa','INSERT',false),
        ('efa','REFERENCES',false),('efa','SELECT',false),
        ('efa','TRIGGER',false),('efa','TRUNCATE',false),
        ('efa','UPDATE',false),('efa_mcp_reader','SELECT',false)
    ), actual AS (
      SELECT CASE WHEN x.grantee=0 THEN 'PUBLIC'
                  ELSE pg_get_userbyid(x.grantee) END,
             x.privilege_type,x.is_grantable
        FROM pg_class c,
             LATERAL aclexplode(COALESCE(c.relacl,
                         acldefault('r',c.relowner))) x
       WHERE c.oid='mcp_read.competitor_reference_plan_source'::regclass
    ), diff AS (
      (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
      UNION ALL
      (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(grantee||':'||privilege_type, ', ' ORDER BY 1)
      INTO differences FROM diff;
    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Reference-plan direct ACL differs: %', differences;
    END IF;

    IF has_table_privilege('efa_mcp_reader',
           'public.competitor_watchlist_memberships','SELECT')
       OR has_table_privilege('efa_mcp_readonly',
           'public.competitor_watchlist_memberships','SELECT')
       OR NOT has_table_privilege('efa_mcp_reader',
           'mcp_read.competitor_reference_plan_source','SELECT')
       OR NOT has_table_privilege('efa_mcp_readonly',
           'mcp_read.competitor_reference_plan_source','SELECT')
       OR has_table_privilege('efa_mcp_reader',
           'mcp_read.competitor_reference_plan_source','INSERT')
       OR has_table_privilege('efa_mcp_reader',
           'mcp_read.competitor_reference_plan_source','UPDATE')
       OR has_table_privilege('efa_mcp_reader',
           'mcp_read.competitor_reference_plan_source','DELETE')
       OR has_table_privilege('efa_mcp_reader',
           'mcp_read.competitor_reference_plan_source','TRUNCATE')
       OR has_table_privilege('efa_mcp_readonly',
           'mcp_read.competitor_reference_plan_source','INSERT')
       OR has_table_privilege('efa_mcp_readonly',
           'mcp_read.competitor_reference_plan_source','UPDATE')
       OR has_table_privilege('efa_mcp_readonly',
           'mcp_read.competitor_reference_plan_source','DELETE')
       OR has_table_privilege('efa_mcp_readonly',
           'mcp_read.competitor_reference_plan_source','TRUNCATE') THEN
        RAISE EXCEPTION 'Reference-plan effective reader ACL differs';
    END IF;

    IF (SELECT count(*) FROM pg_rewrite
         WHERE ev_class='mcp_read.competitor_reference_plan_source'::regclass) <> 1
       OR NOT EXISTS (
         SELECT 1 FROM pg_rewrite
          WHERE ev_class='mcp_read.competitor_reference_plan_source'::regclass
            AND rulename='_RETURN'
            AND ev_type='1'
            AND ev_enabled='O'
            AND is_instead
       ) OR EXISTS (
         SELECT 1 FROM pg_trigger
          WHERE tgrelid='mcp_read.competitor_reference_plan_source'::regclass
            AND NOT tgisinternal
       ) THEN
        RAISE EXCEPTION 'Reference-plan rule/trigger contract differs';
    END IF;

    WITH expected(source_schema, source_relation) AS (
      VALUES
       ('public','competitor_listings'),
       ('public','competitor_product_families'),
       ('public','competitor_sku_oems'),
       ('public','competitor_sku_profiles'),
       ('public','competitor_watchlist_memberships')
    ), actual AS (
      SELECT DISTINCT sn.nspname::text,sc.relname::text
        FROM pg_rewrite rw
        JOIN pg_depend d ON d.classid='pg_rewrite'::regclass
          AND d.objid=rw.oid AND d.refclassid='pg_class'::regclass
        JOIN pg_class sc ON sc.oid=d.refobjid
        JOIN pg_namespace sn ON sn.oid=sc.relnamespace
       WHERE rw.ev_class='mcp_read.competitor_reference_plan_source'::regclass
         AND d.deptype='n' AND sc.oid<>rw.ev_class
    ), diff AS (
      (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
      UNION ALL
      (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(source_schema||'.'||source_relation, ', ' ORDER BY 1)
      INTO differences FROM diff;
    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Reference-plan dependency contract differs: %', differences;
    END IF;

    WITH expected AS (
      SELECT 'PROFILE'::text AS record_kind,p.offer_id,p.watchlist_state,
        NULL::uuid AS sku_oem_id,NULL::text AS query_text_exact,
        NULL::text AS query_normalized,NULL::boolean AS oem_active,
        NULL::timestamptz AS oem_created_at,NULL::uuid AS membership_id,
        NULL::text AS membership_status,NULL::text[] AS matched_oem_set,
        NULL::timestamptz AS valid_from,NULL::timestamptz AS valid_to,
        NULL::uuid AS listing_id,NULL::uuid AS product_family_id,
        NULL::bigint AS ozon_product_id,NULL::text AS seller_id,
        NULL::text AS product_name,NULL::integer AS reference_ordinal
      FROM public.competitor_sku_profiles p
      UNION ALL
      SELECT 'SKU_OEM'::text,p.offer_id,p.watchlist_state,o.sku_oem_id,
        NULL::text,o.oem_normalized,o.active,o.created_at,NULL::uuid,
        NULL::text,NULL::text[],NULL::timestamptz,NULL::timestamptz,
        NULL::uuid,NULL::uuid,NULL::bigint,NULL::text,NULL::text,NULL::integer
      FROM public.competitor_sku_profiles p
      JOIN public.competitor_sku_oems o ON o.offer_id=p.offer_id
      UNION ALL
      SELECT 'MEMBERSHIP_QUERY'::text,p.offer_id,p.watchlist_state,o.sku_oem_id,
        q.query_text_exact,o.oem_normalized,o.active,o.created_at,
        m.membership_id,m.membership_status,m.matched_oem_set,m.valid_from,
        m.valid_to,l.listing_id,l.product_family_id,l.ozon_product_id,
        l.seller_id,f.product_name,m.reference_ordinal
      FROM public.competitor_watchlist_memberships m
      JOIN public.competitor_sku_profiles p ON p.offer_id=m.offer_id
      JOIN public.competitor_listings l ON l.listing_id=m.listing_id
      JOIN public.competitor_product_families f
        ON f.product_family_id=l.product_family_id
      CROSS JOIN LATERAL unnest(m.matched_oem_set) q(query_text_exact)
      LEFT JOIN public.competitor_sku_oems o
        ON o.offer_id=m.offer_id AND o.oem_normalized=q.query_text_exact
    ), actual AS (
      SELECT * FROM mcp_read.competitor_reference_plan_source
    ), diff AS (
      (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
      UNION ALL
      (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT count(*)::text INTO differences FROM diff;
    IF differences <> '0' THEN
        RAISE EXCEPTION 'Reference-plan source equivalence differs: % rows', differences;
    END IF;

    IF (SELECT count(*) FROM mcp_read.competitor_reference_plan_source
         WHERE record_kind='PROFILE') <> 5
       OR (SELECT count(*) FROM mcp_read.competitor_reference_plan_source
            WHERE record_kind='SKU_OEM') <> 12
       OR (SELECT count(*) FROM mcp_read.competitor_reference_plan_source
            WHERE record_kind='MEMBERSHIP_QUERY' AND reference_ordinal<=41) <> 87 THEN
        RAISE EXCEPTION 'Reference-plan row counts differ from 5/12/87';
    END IF;

    WITH a AS (
      SELECT * FROM jsonb_to_recordset(authoritative) AS x(
        reference_ordinal integer, offer_id text, ozon_product_id bigint,
        seller_id text, matched_oem_set text[]
      )
    ), expected_expanded AS (
      SELECT a.reference_ordinal,a.offer_id,u.query_text_exact,u.oem_ordinal
      FROM a CROSS JOIN LATERAL unnest(a.matched_oem_set)
        WITH ORDINALITY u(query_text_exact,oem_ordinal)
    ), expected_first AS (
      SELECT DISTINCT ON (offer_id,query_text_exact)
        offer_id,query_text_exact,reference_ordinal,oem_ordinal
      FROM expected_expanded
      ORDER BY offer_id,query_text_exact,reference_ordinal,oem_ordinal
    ), expected_query_order AS (
      SELECT row_number() OVER (ORDER BY reference_ordinal,oem_ordinal)::integer AS query_ordinal,
             offer_id,query_text_exact
      FROM expected_first
    ), actual_expanded AS (
      SELECT v.reference_ordinal,v.offer_id,v.query_text_exact,
             array_position(v.matched_oem_set,v.query_text_exact) AS oem_ordinal
      FROM mcp_read.competitor_reference_plan_source v
      WHERE v.record_kind='MEMBERSHIP_QUERY' AND v.reference_ordinal<=41
    ), actual_first AS (
      SELECT DISTINCT ON (offer_id,query_text_exact)
        offer_id,query_text_exact,reference_ordinal,oem_ordinal
      FROM actual_expanded
      ORDER BY offer_id,query_text_exact,reference_ordinal,oem_ordinal
    ), actual_query_order AS (
      SELECT row_number() OVER (ORDER BY reference_ordinal,oem_ordinal)::integer AS query_ordinal,
             offer_id,query_text_exact
      FROM actual_first
    ), expected_slot_rows AS (
      SELECT q.query_ordinal,a.reference_ordinal,q.offer_id,q.query_text_exact,
             a.ozon_product_id
      FROM expected_query_order q JOIN a ON a.offer_id=q.offer_id
       AND q.query_text_exact=ANY(a.matched_oem_set)
    ), actual_slot_rows AS (
      SELECT q.query_ordinal,v.reference_ordinal,q.offer_id,q.query_text_exact,
             v.ozon_product_id
      FROM actual_query_order q
      JOIN mcp_read.competitor_reference_plan_source v
        ON v.record_kind='MEMBERSHIP_QUERY'
       AND v.offer_id=q.offer_id AND v.query_text_exact=q.query_text_exact
       AND v.reference_ordinal<=41
    )
    SELECT
      (SELECT array_agg(format('%s|%s',offer_id,query_text_exact)
                        ORDER BY query_ordinal) FROM expected_query_order),
      (SELECT array_agg(format('%s|%s',offer_id,query_text_exact)
                        ORDER BY query_ordinal) FROM actual_query_order),
      (SELECT array_agg(format('%s|%s|%s',offer_id,query_text_exact,
                              ozon_product_id)
                        ORDER BY query_ordinal,reference_ordinal)
         FROM expected_slot_rows),
      (SELECT array_agg(format('%s|%s|%s',offer_id,query_text_exact,
                              ozon_product_id)
                        ORDER BY query_ordinal,reference_ordinal)
         FROM actual_slot_rows)
    INTO expected_queries,actual_queries,expected_slots,actual_slots;

    IF cardinality(expected_queries)<>9 OR cardinality(actual_queries)<>9
       OR cardinality(expected_slots)<>87 OR cardinality(actual_slots)<>87
       OR expected_queries IS DISTINCT FROM actual_queries
       OR expected_slots IS DISTINCT FROM actual_slots THEN
        RAISE EXCEPTION 'Canonical 9-query/87-slot ordered reconstruction differs';
    END IF;

    WITH query_order AS (
      SELECT row_number() OVER (ORDER BY first_reference,first_oem)::integer AS query_ordinal,
             offer_id,query_text_exact
      FROM (
        SELECT DISTINCT ON (offer_id,query_text_exact)
          offer_id,query_text_exact,reference_ordinal AS first_reference,
          array_position(matched_oem_set,query_text_exact) AS first_oem
        FROM mcp_read.competitor_reference_plan_source
        WHERE record_kind='MEMBERSHIP_QUERY' AND reference_ordinal<=41
        ORDER BY offer_id,query_text_exact,reference_ordinal,
                 array_position(matched_oem_set,query_text_exact)
      ) firsts
    ), history_queries AS (
      SELECT CASE
               WHEN r.collection_ref LIKE 'cm-baseline-v1:run:%' THEN 'T0'
               WHEN r.collection_ref LIKE 'cm-snapshot-v1:run:%' THEN 'T1'
             END AS cycle,
             array_agg(format('%s|%s',r.offer_id,r.query_text_exact)
                       ORDER BY q.query_ordinal) AS sequence
      FROM public.competitor_search_runs r
      JOIN query_order q ON q.offer_id=r.offer_id
                        AND q.query_text_exact=r.query_text_exact
      WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%'
         OR r.collection_ref LIKE 'cm-snapshot-v1:run:%'
      GROUP BY 1
    ), history_slots AS (
      SELECT CASE
               WHEN r.collection_ref LIKE 'cm-baseline-v1:run:%' THEN 'T0'
               WHEN r.collection_ref LIKE 'cm-snapshot-v1:run:%' THEN 'T1'
             END AS cycle,
             array_agg(format('%s|%s|%s',r.offer_id,r.query_text_exact,
                              v.ozon_product_id)
                       ORDER BY q.query_ordinal,v.reference_ordinal) AS sequence
      FROM public.competitor_search_runs r
      JOIN public.competitor_observations o ON o.search_run_id=r.search_run_id
      JOIN mcp_read.competitor_reference_plan_source v
        ON v.record_kind='MEMBERSHIP_QUERY'
       AND v.membership_id=o.membership_id
       AND v.offer_id=r.offer_id
       AND v.query_text_exact=r.query_text_exact
      JOIN query_order q ON q.offer_id=r.offer_id
                        AND q.query_text_exact=r.query_text_exact
      WHERE r.collection_ref LIKE 'cm-baseline-v1:run:%'
         OR r.collection_ref LIKE 'cm-snapshot-v1:run:%'
      GROUP BY 1
    )
    SELECT
      (SELECT sequence FROM history_queries WHERE cycle='T0'),
      (SELECT sequence FROM history_queries WHERE cycle='T1'),
      (SELECT sequence FROM history_slots WHERE cycle='T0'),
      (SELECT sequence FROM history_slots WHERE cycle='T1')
    INTO t0_queries,t1_queries,t0_slots,t1_slots;

    IF t0_queries IS DISTINCT FROM expected_queries
       OR t1_queries IS DISTINCT FROM expected_queries
       OR t0_slots IS DISTINCT FROM expected_slots
       OR t1_slots IS DISTINCT FROM expected_slots THEN
        RAISE EXCEPTION 'T0/T1 ordered query or slot sequence differs';
    END IF;

    WITH expected(view_name, fingerprint) AS (
      VALUES
        ('competitor_finding_sets_reconciliation','ca93216706918764a231230d2a0c7da0'),
        ('competitor_findings','6759ff1adad6100b788c1d5b7f9117bb'),
        ('competitor_latest_finding_set','5d9f281b91e93bf632bb051ca24c214c'),
        ('competitor_monitoring_coverage','4b3eacc90de2fc55ed2482d3c25e4d51'),
        ('competitor_snapshot_observations','05b69587e36824bc16508b688631da49'),
        ('competitor_snapshot_runs','f7496f94bb8175f08635f5d6dd4b3df4'),
        ('product_cpc_daily','170e9b0cb92470913effb495d51f3454'),
        ('product_daily_performance','8d2d33577e07257be5502bbcc38a7f58'),
        ('product_overview','614b70abec38215dc76749ec35ca2b25'),
        ('product_price_history','7b3478e8e101a2841f7a0e47062ded36'),
        ('product_promotion_state','f8cc1bb0b02685f7f9b2c8fbbbe5e396'),
        ('product_region_logistics','db21649bf2b4e72cf1cda2adb2d5b4db'),
        ('product_stock_history','a126790040a3871ba553dff3015ed428')
    ), actual AS (
      SELECT c.relname::text AS view_name,
        md5(concat_ws(E'\n',c.relname,c.relkind::text,
          pg_get_userbyid(c.relowner),
          COALESCE((SELECT string_agg(x.option,',' ORDER BY x.option)
                    FROM unnest(c.reloptions) x(option)),''),
          COALESCE((SELECT string_agg(format('%s:%s:%s',a.attnum,a.attname,
                    format_type(a.atttypid,a.atttypmod)),',' ORDER BY a.attnum)
                    FROM pg_attribute a WHERE a.attrelid=c.oid
                    AND a.attnum>0 AND NOT a.attisdropped),''),
          pg_get_viewdef(c.oid,true),
          COALESCE((SELECT string_agg(format('%s:%s:%s:%s',
                    CASE WHEN x.grantee=0 THEN 'PUBLIC'
                         ELSE pg_get_userbyid(x.grantee) END,
                    pg_get_userbyid(x.grantor),x.privilege_type,x.is_grantable),
                    ',' ORDER BY CASE WHEN x.grantee=0 THEN 'PUBLIC'
                    ELSE pg_get_userbyid(x.grantee) END,
                    pg_get_userbyid(x.grantor),x.privilege_type,x.is_grantable)
                    FROM aclexplode(COALESCE(c.relacl,
                         acldefault('r',c.relowner))) x),''))) AS fingerprint
      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='mcp_read' AND c.relkind='v'
        AND c.relname<>'competitor_reference_plan_source'
    ), diff AS (
      SELECT COALESCE(e.view_name,a.view_name) view_name
      FROM expected e FULL JOIN actual a USING(view_name)
      WHERE e.fingerprint IS DISTINCT FROM a.fingerprint
    )
    SELECT string_agg(view_name,', ' ORDER BY view_name)
      INTO differences FROM diff;
    IF differences IS NOT NULL THEN
      RAISE EXCEPTION 'One of thirteen unchanged MCP views differs: %',differences;
    END IF;

    SELECT md5(concat_ws(E'\n',p.proname,
      pg_get_function_identity_arguments(p.oid),pg_get_function_result(p.oid),
      pg_get_userbyid(p.proowner),p.prosecdef,p.provolatile,p.proparallel,
      COALESCE((SELECT string_agg(x.option,',' ORDER BY x.option)
                FROM unnest(p.proconfig) x(option)),''),
      pg_get_functiondef(p.oid),
      COALESCE((SELECT string_agg(format('%s:%s:%s:%s',
                CASE WHEN x.grantee=0 THEN 'PUBLIC'
                     ELSE pg_get_userbyid(x.grantee) END,
                pg_get_userbyid(x.grantor),x.privilege_type,x.is_grantable),
                ',' ORDER BY CASE WHEN x.grantee=0 THEN 'PUBLIC'
                ELSE pg_get_userbyid(x.grantee) END,
                pg_get_userbyid(x.grantor),x.privilege_type,x.is_grantable)
                FROM aclexplode(COALESCE(p.proacl,
                     acldefault('f',p.proowner))) x),'')))
      INTO function_fingerprint
      FROM pg_proc p
      WHERE p.oid='mcp_read.product_period_economics(date,date)'::regprocedure;
    IF function_fingerprint IS DISTINCT FROM
       'cf16870f884f2177f2ff4492c6344502' THEN
      RAISE EXCEPTION 'product_period_economics fingerprint differs';
    END IF;

    IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n
          ON n.oid=c.relnamespace
         WHERE n.nspname='mcp_read' AND c.relkind='v') <> 14 THEN
      RAISE EXCEPTION 'Approved MCP view count differs from 14';
    END IF;
END
$validation$;

SELECT
  (SELECT count(*) FROM public.competitor_watchlist_memberships) AS memberships,
  (SELECT count(*) FROM public.competitor_watchlist_memberships
    WHERE reference_ordinal BETWEEN 1 AND 41) AS legacy_ordinals,
  (SELECT count(*) FROM public.competitor_search_runs) AS search_runs,
  (SELECT count(*) FROM public.competitor_observations) AS observations,
  (SELECT count(*) FROM public.competitor_reviews) AS reviews,
  (SELECT count(*) FROM public.competitor_finding_sets) AS finding_sets,
  (SELECT count(*) FROM public.competitor_findings) AS findings,
  (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='mcp_read' AND c.relkind='v') AS approved_mcp_views;

ROLLBACK;
