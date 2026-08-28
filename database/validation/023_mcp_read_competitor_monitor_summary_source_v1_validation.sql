-- Post-deployment validation for
-- 023_mcp_read_competitor_monitor_summary_source_v1.sql.
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
            ('competitor_latest_finding_set'),
            ('competitor_findings'),
            ('competitor_monitoring_coverage')
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
        RAISE EXCEPTION 'Migration 023 view contract differs: %', object_differences;
    END IF;

    IF (
        SELECT count(*)
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relkind = 'v'
    ) <> 10 THEN
        RAISE EXCEPTION 'Expected ten approved mcp_read views after Migration 023';
    END IF;
END
$objects$;

DO $columns$
DECLARE
    column_differences text;
BEGIN
    WITH expected(view_name, ordinal_position, column_name, data_type) AS (
        VALUES
            ('competitor_latest_finding_set', 1, 'finding_set_id', 'uuid'),
            ('competitor_latest_finding_set', 2, 'set_key', 'text'),
            ('competitor_latest_finding_set', 3, 'persistence_contract_version', 'text'),
            ('competitor_latest_finding_set', 4, 'finding_set_contract_version', 'text'),
            ('competitor_latest_finding_set', 5, 'source_analysis_contract_version', 'text'),
            ('competitor_latest_finding_set', 6, 'source_findings_sha256', 'text'),
            ('competitor_latest_finding_set', 7, 'source_findings_semantic_sha256', 'text'),
            ('competitor_latest_finding_set', 8, 'source_analysis_sha256', 'text'),
            ('competitor_latest_finding_set', 9, 'previous_source_kind', 'text'),
            ('competitor_latest_finding_set', 10, 'previous_derived_batch_id', 'text'),
            ('competitor_latest_finding_set', 11, 'previous_reference_at', 'timestamp with time zone'),
            ('competitor_latest_finding_set', 12, 'previous_captured_through', 'timestamp with time zone'),
            ('competitor_latest_finding_set', 13, 'current_source_kind', 'text'),
            ('competitor_latest_finding_set', 14, 'current_derived_batch_id', 'text'),
            ('competitor_latest_finding_set', 15, 'current_reference_at', 'timestamp with time zone'),
            ('competitor_latest_finding_set', 16, 'current_captured_through', 'timestamp with time zone'),
            ('competitor_latest_finding_set', 17, 'expected_findings_count', 'integer'),
            ('competitor_latest_finding_set', 18, 'applied_at', 'timestamp with time zone'),
            ('competitor_findings', 1, 'finding_id', 'uuid'),
            ('competitor_findings', 2, 'finding_set_id', 'uuid'),
            ('competitor_findings', 3, 'finding_kind', 'text'),
            ('competitor_findings', 4, 'offer_id', 'text'),
            ('competitor_findings', 5, 'product_family_id', 'uuid'),
            ('competitor_findings', 6, 'listing_id', 'uuid'),
            ('competitor_findings', 7, 'old_observation_id', 'uuid'),
            ('competitor_findings', 8, 'new_observation_id', 'uuid'),
            ('competitor_findings', 9, 'topic', 'text'),
            ('competitor_findings', 10, 'metric', 'text'),
            ('competitor_findings', 11, 'severity', 'text'),
            ('competitor_findings', 12, 'confidence', 'text'),
            ('competitor_findings', 13, 'status', 'text'),
            ('competitor_findings', 14, 'evidence', 'jsonb'),
            ('competitor_findings', 15, 'details', 'jsonb'),
            ('competitor_findings', 16, 'finding_key', 'text'),
            ('competitor_findings', 17, 'first_detected_at', 'timestamp with time zone'),
            ('competitor_findings', 18, 'last_detected_at', 'timestamp with time zone'),
            ('competitor_monitoring_coverage', 1, 'offer_id', 'text'),
            ('competitor_monitoring_coverage', 2, 'watchlist_state', 'text'),
            ('competitor_monitoring_coverage', 3, 'source_reason', 'text'),
            ('competitor_monitoring_coverage', 4, 'active_monitored', 'boolean')
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
               'competitor_latest_finding_set',
               'competitor_findings',
               'competitor_monitoring_coverage'
           )
           AND a.attnum > 0
           AND NOT a.attisdropped
    ),
    differences AS (
        SELECT
            COALESCE(e.view_name, a.view_name) AS view_name,
            COALESCE(e.ordinal_position, a.ordinal_position) AS ordinal_position
          FROM expected e
          FULL JOIN actual a
            ON a.view_name = e.view_name
           AND a.ordinal_position = e.ordinal_position
         WHERE e.column_name IS DISTINCT FROM a.column_name
            OR e.data_type IS DISTINCT FROM a.data_type
    )
    SELECT string_agg(
               d.view_name || '[' || d.ordinal_position || ']',
               ', ' ORDER BY d.view_name, d.ordinal_position
           )
      INTO column_differences
      FROM differences d;

    IF column_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 023 return-column contract differs: %',
            column_differences;
    END IF;
END
$columns$;

DO $definitions$
DECLARE
    definition_differences text;
    dependency_differences text;
BEGIN
    WITH expected(view_name, definition) AS (
        VALUES
            (
                'competitor_latest_finding_set',
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
    expected_findings_count,
    applied_at
   FROM public.competitor_finding_sets s
  WHERE finding_set_contract_version = 'competitor_finding_set.v1'::text
  ORDER BY current_reference_at DESC, applied_at DESC, finding_set_id DESC
 LIMIT 1;$view$
            ),
            (
                'competitor_findings',
                $view$SELECT finding_id,
    finding_set_id,
    finding_kind,
    offer_id,
    product_family_id,
    listing_id,
    old_observation_id,
    new_observation_id,
    topic,
    metric,
    severity,
    confidence,
    status,
    evidence,
    details,
    finding_key,
    first_detected_at,
    last_detected_at
   FROM public.competitor_findings f;$view$
            ),
            (
                'competitor_monitoring_coverage',
                $view$SELECT offer_id,
    watchlist_state,
    NULLIF(btrim(notes), ''::text) AS source_reason,
    watchlist_state = 'ACTIVE'::text AND (EXISTS ( SELECT 1
           FROM public.competitor_watchlist_memberships m
          WHERE m.offer_id = p.offer_id AND m.valid_to IS NULL AND (m.membership_status = ANY (ARRAY['CONTROL'::text, 'PRIMARY'::text, 'RESERVE'::text])))) AS active_monitored
   FROM public.competitor_sku_profiles p;$view$
            )
    ),
    actual AS (
        SELECT
            c.relname::text AS view_name,
            pg_get_viewdef(c.oid, true) AS definition
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relname IN (
               'competitor_latest_finding_set',
               'competitor_findings',
               'competitor_monitoring_coverage'
           )
    ),
    differences AS (
        SELECT COALESCE(e.view_name, a.view_name) AS view_name
          FROM expected e
          FULL JOIN actual a USING (view_name)
         WHERE lower(regexp_replace(btrim(e.definition), '[[:space:]]+', ' ', 'g'))
               IS DISTINCT FROM
               lower(regexp_replace(btrim(a.definition), '[[:space:]]+', ' ', 'g'))
    )
    SELECT string_agg(d.view_name, ', ' ORDER BY d.view_name)
      INTO definition_differences
      FROM differences d;

    IF definition_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 023 exact view definitions differ: %',
            definition_differences;
    END IF;

    WITH expected(view_name, source_table) AS (
        VALUES
            ('competitor_latest_finding_set', 'competitor_finding_sets'),
            ('competitor_findings', 'competitor_findings'),
            ('competitor_monitoring_coverage', 'competitor_sku_profiles'),
            ('competitor_monitoring_coverage', 'competitor_watchlist_memberships')
    ),
    actual AS (
        SELECT u.view_name::text, u.table_name::text AS source_table
          FROM information_schema.view_table_usage u
         WHERE u.view_schema = 'mcp_read'
           AND u.view_name IN (
               'competitor_latest_finding_set',
               'competitor_findings',
               'competitor_monitoring_coverage'
           )
           AND u.table_schema = 'public'
    ),
    differences AS (
        SELECT COALESCE(e.view_name, a.view_name) AS view_name,
               COALESCE(e.source_table, a.source_table) AS source_table
          FROM expected e
          FULL JOIN actual a USING (view_name, source_table)
         WHERE e.view_name IS NULL OR a.view_name IS NULL
    )
    SELECT string_agg(
               d.view_name || '->' || d.source_table,
               ', ' ORDER BY d.view_name, d.source_table
           )
      INTO dependency_differences
      FROM differences d;

    IF dependency_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 023 source dependencies differ: %',
            dependency_differences;
    END IF;
END
$definitions$;

DO $source_rls$
DECLARE
    source_differences text;
BEGIN
    WITH expected(table_name) AS (
        VALUES
            ('competitor_finding_sets'),
            ('competitor_findings'),
            ('competitor_sku_profiles'),
            ('competitor_watchlist_memberships')
    ),
    actual AS (
        SELECT
            c.relname::text AS table_name,
            c.relkind,
            pg_get_userbyid(c.relowner) AS owner_name,
            c.relrowsecurity,
            c.relforcerowsecurity
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname IN (
               'competitor_finding_sets',
               'competitor_findings',
               'competitor_sku_profiles',
               'competitor_watchlist_memberships'
           )
    )
    SELECT string_agg(e.table_name, ', ' ORDER BY e.table_name)
      INTO source_differences
      FROM expected e
      LEFT JOIN actual a USING (table_name)
     WHERE a.table_name IS NULL
        OR a.relkind <> 'r'
        OR a.owner_name <> 'efa'
        OR a.relrowsecurity
        OR a.relforcerowsecurity;

    IF source_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Source table ownership/type/RLS contract differs: %',
            source_differences;
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
               'competitor_latest_finding_set',
               'competitor_findings',
               'competitor_monitoring_coverage'
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
           'competitor_latest_finding_set',
           'competitor_findings',
           'competitor_monitoring_coverage'
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
               'competitor_latest_finding_set',
               'competitor_findings',
               'competitor_monitoring_coverage'
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
                SELECT
                    x.grantee,
                    x.grantor,
                    x.privilege_type,
                    x.is_grantable
                  FROM aclexplode(acldefault('r', owner_oid)) x
                UNION ALL
                SELECT reader_oid, owner_oid, 'SELECT'::text, false
            ),
            actual AS (
                SELECT
                    x.grantee,
                    x.grantor,
                    x.privilege_type,
                    x.is_grantable
                  FROM pg_class c
                  CROSS JOIN LATERAL aclexplode(
                      COALESCE(c.relacl, acldefault('r', c.relowner))
                  ) x
                 WHERE c.oid = target_view
            )
            (
                SELECT * FROM actual
                EXCEPT ALL
                SELECT * FROM expected
            )
            UNION ALL
            (
                SELECT * FROM expected
                EXCEPT ALL
                SELECT * FROM actual
            )
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
          CROSS JOIN LATERAL aclexplode(
              COALESCE(c.relacl, acldefault('r', c.relowner))
          ) acl
         WHERE c.oid IN (
                   'public.competitor_finding_sets'::regclass,
                   'public.competitor_findings'::regclass,
                   'public.competitor_sku_profiles'::regclass,
                   'public.competitor_watchlist_memberships'::regclass
               )
           AND acl.grantee = ANY (array_prepend(0::oid, restricted_roles))
    ) OR EXISTS (
        SELECT 1
          FROM unnest(
                   ARRAY['efa_mcp_reader', 'efa_mcp_readonly']::text[]
               ) restricted(role_name)
         CROSS JOIN unnest(
                   ARRAY[
                       'public.competitor_finding_sets'::regclass::oid,
                       'public.competitor_findings'::regclass::oid,
                       'public.competitor_sku_profiles'::regclass::oid,
                       'public.competitor_watchlist_memberships'::regclass::oid
                   ]
               ) target(table_oid)
         WHERE has_table_privilege(restricted.role_name, target.table_oid, 'SELECT')
            OR has_table_privilege(restricted.role_name, target.table_oid, 'INSERT')
            OR has_table_privilege(restricted.role_name, target.table_oid, 'UPDATE')
            OR has_table_privilege(restricted.role_name, target.table_oid, 'DELETE')
            OR has_table_privilege(restricted.role_name, target.table_oid, 'TRUNCATE')
            OR has_table_privilege(restricted.role_name, target.table_oid, 'REFERENCES')
            OR has_table_privilege(restricted.role_name, target.table_oid, 'TRIGGER')
    ) THEN
        RAISE EXCEPTION 'Raw competitor table ACL is not closed';
    END IF;
END
$raw_acl$;

DO $source_equivalence$
BEGIN
    IF EXISTS (
        (
            SELECT *
              FROM mcp_read.competitor_latest_finding_set
            EXCEPT ALL
            SELECT *
              FROM (
                  SELECT
                      s.finding_set_id,
                      s.set_key,
                      s.persistence_contract_version,
                      s.finding_set_contract_version,
                      s.source_analysis_contract_version,
                      s.source_findings_sha256,
                      s.source_findings_semantic_sha256,
                      s.source_analysis_sha256,
                      s.previous_source_kind,
                      s.previous_derived_batch_id,
                      s.previous_reference_at,
                      s.previous_captured_through,
                      s.current_source_kind,
                      s.current_derived_batch_id,
                      s.current_reference_at,
                      s.current_captured_through,
                      s.expected_findings_count,
                      s.applied_at
                    FROM public.competitor_finding_sets s
                   WHERE s.finding_set_contract_version =
                         'competitor_finding_set.v1'
                   ORDER BY
                       s.current_reference_at DESC,
                       s.applied_at DESC,
                       s.finding_set_id DESC
                   LIMIT 1
              ) latest_source
        )
        UNION ALL
        (
            SELECT *
              FROM (
                  SELECT
                      s.finding_set_id,
                      s.set_key,
                      s.persistence_contract_version,
                      s.finding_set_contract_version,
                      s.source_analysis_contract_version,
                      s.source_findings_sha256,
                      s.source_findings_semantic_sha256,
                      s.source_analysis_sha256,
                      s.previous_source_kind,
                      s.previous_derived_batch_id,
                      s.previous_reference_at,
                      s.previous_captured_through,
                      s.current_source_kind,
                      s.current_derived_batch_id,
                      s.current_reference_at,
                      s.current_captured_through,
                      s.expected_findings_count,
                      s.applied_at
                    FROM public.competitor_finding_sets s
                   WHERE s.finding_set_contract_version =
                         'competitor_finding_set.v1'
                   ORDER BY
                       s.current_reference_at DESC,
                       s.applied_at DESC,
                       s.finding_set_id DESC
                   LIMIT 1
              ) latest_source
            EXCEPT ALL
            SELECT *
              FROM mcp_read.competitor_latest_finding_set
        )
    ) THEN
        RAISE EXCEPTION 'Latest Finding Set rows are not exactly source-equivalent';
    END IF;

    IF EXISTS (
        (
            SELECT *
              FROM mcp_read.competitor_findings
            EXCEPT ALL
            SELECT
                f.finding_id,
                f.finding_set_id,
                f.finding_kind,
                f.offer_id,
                f.product_family_id,
                f.listing_id,
                f.old_observation_id,
                f.new_observation_id,
                f.topic,
                f.metric,
                f.severity,
                f.confidence,
                f.status,
                f.evidence,
                f.details,
                f.finding_key,
                f.first_detected_at,
                f.last_detected_at
              FROM public.competitor_findings f
        )
        UNION ALL
        (
            SELECT
                f.finding_id,
                f.finding_set_id,
                f.finding_kind,
                f.offer_id,
                f.product_family_id,
                f.listing_id,
                f.old_observation_id,
                f.new_observation_id,
                f.topic,
                f.metric,
                f.severity,
                f.confidence,
                f.status,
                f.evidence,
                f.details,
                f.finding_key,
                f.first_detected_at,
                f.last_detected_at
              FROM public.competitor_findings f
            EXCEPT ALL
            SELECT *
              FROM mcp_read.competitor_findings
        )
    ) THEN
        RAISE EXCEPTION 'Finding rows are not exactly source-equivalent';
    END IF;

    IF EXISTS (
        (
            SELECT
                v.offer_id,
                v.watchlist_state,
                v.source_reason,
                v.active_monitored
              FROM mcp_read.competitor_monitoring_coverage v
            EXCEPT ALL
            SELECT
                p.offer_id,
                p.watchlist_state,
                NULLIF(btrim(p.notes), '') AS source_reason,
                (
                    p.watchlist_state = 'ACTIVE'
                    AND EXISTS (
                        SELECT 1
                          FROM public.competitor_watchlist_memberships m
                         WHERE m.offer_id = p.offer_id
                           AND m.valid_to IS NULL
                           AND m.membership_status IN (
                               'CONTROL', 'PRIMARY', 'RESERVE'
                           )
                    )
                ) AS active_monitored
              FROM public.competitor_sku_profiles p
        )
        UNION ALL
        (
            SELECT
                p.offer_id,
                p.watchlist_state,
                NULLIF(btrim(p.notes), '') AS source_reason,
                (
                    p.watchlist_state = 'ACTIVE'
                    AND EXISTS (
                        SELECT 1
                          FROM public.competitor_watchlist_memberships m
                         WHERE m.offer_id = p.offer_id
                           AND m.valid_to IS NULL
                           AND m.membership_status IN (
                               'CONTROL', 'PRIMARY', 'RESERVE'
                           )
                    )
                ) AS active_monitored
              FROM public.competitor_sku_profiles p
            EXCEPT ALL
            SELECT
                v.offer_id,
                v.watchlist_state,
                v.source_reason,
                v.active_monitored
              FROM mcp_read.competitor_monitoring_coverage v
        )
    ) THEN
        RAISE EXCEPTION 'Monitoring coverage rows are not exactly source-equivalent';
    END IF;
END
$source_equivalence$;

DO $existing_surfaces$
DECLARE
    view_differences text;
    function_differences text;
BEGIN
    WITH expected(view_name, fingerprint) AS (
        VALUES
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
                    (
                        SELECT string_agg(x.option, ',' ORDER BY x.option)
                          FROM unnest(c.reloptions) x(option)
                    ),
                    ''
                ),
                COALESCE(
                    (
                        SELECT string_agg(
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
                           AND NOT a.attisdropped
                    ),
                    ''
                ),
                pg_get_viewdef(c.oid, true),
                COALESCE(
                    (
                        SELECT string_agg(
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
                                   COALESCE(
                                       c.relacl,
                                       acldefault('r', c.relowner)
                                   )
                               ) x
                    ),
                    ''
                )
            )) AS fingerprint
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relname IN (
               'product_overview',
               'product_price_history',
               'product_stock_history',
               'product_daily_performance',
               'product_region_logistics',
               'product_promotion_state',
               'product_cpc_daily'
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
                E'\n',
                p.proname,
                pg_get_function_identity_arguments(p.oid),
                pg_get_function_result(p.oid),
                pg_get_userbyid(p.proowner),
                p.prosecdef,
                p.provolatile,
                p.proparallel,
                COALESCE(
                    (
                        SELECT string_agg(x.option, ',' ORDER BY x.option)
                          FROM unnest(p.proconfig) x(option)
                    ),
                    ''
                ),
                pg_get_functiondef(p.oid),
                COALESCE(
                    (
                        SELECT string_agg(
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
                                   COALESCE(
                                       p.proacl,
                                       acldefault('f', p.proowner)
                                   )
                               ) x
                    ),
                    ''
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

    IF NOT has_function_privilege(
           'efa_mcp_reader',
           'mcp_read.product_period_economics(date,date)',
           'EXECUTE'
       ) OR NOT has_function_privilege(
           'efa_mcp_readonly',
           'mcp_read.product_period_economics(date,date)',
           'EXECUTE'
       ) THEN
        RAISE EXCEPTION 'Existing product_period_economics effective ACL changed';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
          CROSS JOIN LATERAL aclexplode(
              COALESCE(p.proacl, acldefault('f', p.proowner))
          ) acl
         WHERE p.oid =
               'mcp_read.product_period_economics(date,date)'::regprocedure
           AND acl.grantee = 0
           AND acl.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC unexpectedly executes product_period_economics';
    END IF;
END
$existing_surfaces$;

SELECT
    (SELECT count(*) FROM mcp_read.competitor_latest_finding_set) AS latest_set_rows,
    (
        SELECT count(*)
          FROM mcp_read.competitor_findings f
         WHERE f.finding_set_id = (
             SELECT s.finding_set_id
               FROM mcp_read.competitor_latest_finding_set s
         )
    ) AS latest_set_finding_rows,
    (
        SELECT count(*)
          FROM mcp_read.competitor_monitoring_coverage
    ) AS portfolio_sku_count,
    (
        SELECT count(*)
          FROM mcp_read.competitor_monitoring_coverage
         WHERE active_monitored
    ) AS active_monitored_sku_count,
    has_table_privilege(
        'efa_mcp_readonly',
        'mcp_read.competitor_latest_finding_set',
        'SELECT'
    ) AS readonly_latest_set_select,
    has_table_privilege(
        'efa_mcp_readonly',
        'mcp_read.competitor_findings',
        'SELECT'
    ) AS readonly_findings_select,
    has_table_privilege(
        'efa_mcp_readonly',
        'mcp_read.competitor_monitoring_coverage',
        'SELECT'
    ) AS readonly_coverage_select,
    'PASS' AS status;

ROLLBACK;
