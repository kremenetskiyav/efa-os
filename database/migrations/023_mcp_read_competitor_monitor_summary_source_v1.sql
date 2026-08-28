-- Competitor Monitor Summary source read surface v1.
--
-- Adds three narrow, read-only source views for the committed
-- competitor_monitor_summary.v1 Python builder. The views expose no write
-- path and do not grant direct access to public competitor tables.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog;

DO $preconditions$
DECLARE
    missing_columns text;
    restricted_roles oid[];
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Expected database efa, got %', current_database();
    END IF;

    IF current_user <> 'efa' THEN
        RAISE EXCEPTION 'Migration 023 must run as role efa, got %', current_user;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'efa_mcp_reader')
       OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'efa_mcp_readonly') THEN
        RAISE EXCEPTION 'Required MCP read roles are missing';
    END IF;

    IF (
        SELECT count(*)
          FROM pg_auth_members m
          JOIN pg_roles member_role ON member_role.oid = m.member
         WHERE member_role.rolname = 'efa_mcp_readonly'
    ) <> 1 OR NOT EXISTS (
        SELECT 1
          FROM pg_auth_members m
          JOIN pg_roles granted_role ON granted_role.oid = m.roleid
          JOIN pg_roles member_role ON member_role.oid = m.member
         WHERE member_role.rolname = 'efa_mcp_readonly'
           AND granted_role.rolname = 'efa_mcp_reader'
           AND NOT m.admin_option
    ) THEN
        RAISE EXCEPTION 'Unexpected efa_mcp_readonly membership state';
    END IF;

    IF (
        SELECT pg_get_userbyid(n.nspowner)
          FROM pg_namespace n
         WHERE n.nspname = 'mcp_read'
    ) IS DISTINCT FROM 'efa' THEN
        RAISE EXCEPTION 'Schema mcp_read is missing or is not owned by efa';
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

    IF (
        SELECT count(*)
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relkind = 'v'
           AND c.relname IN (
               'product_overview',
               'product_price_history',
               'product_stock_history',
               'product_daily_performance',
               'product_region_logistics',
               'product_promotion_state',
               'product_cpc_daily'
           )
           AND pg_get_userbyid(c.relowner) = 'efa'
           AND c.reloptions IS NOT DISTINCT FROM
               ARRAY['security_barrier=true']::text[]
           AND has_table_privilege('efa_mcp_reader', c.oid, 'SELECT')
           AND has_table_privilege('efa_mcp_readonly', c.oid, 'SELECT')
           AND NOT has_table_privilege('efa_mcp_reader', c.oid, 'INSERT')
           AND NOT has_table_privilege('efa_mcp_reader', c.oid, 'UPDATE')
           AND NOT has_table_privilege('efa_mcp_reader', c.oid, 'DELETE')
           AND NOT has_table_privilege('efa_mcp_readonly', c.oid, 'INSERT')
           AND NOT has_table_privilege('efa_mcp_readonly', c.oid, 'UPDATE')
           AND NOT has_table_privilege('efa_mcp_readonly', c.oid, 'DELETE')
    ) <> 7 OR (
        SELECT count(*)
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relkind = 'v'
    ) <> 7 THEN
        RAISE EXCEPTION 'Existing seven-view mcp_read contract changed';
    END IF;

    IF to_regprocedure('mcp_read.product_period_economics(date,date)') IS NULL
       OR NOT EXISTS (
           SELECT 1
             FROM pg_proc p
            WHERE p.oid =
                  'mcp_read.product_period_economics(date,date)'::regprocedure
              AND pg_get_userbyid(p.proowner) = 'efa'
              AND p.prosecdef
              AND p.provolatile = 's'
              AND p.proparallel = 'u'
              AND p.proconfig IS NOT DISTINCT FROM
                  ARRAY['search_path=pg_catalog']::text[]
              AND has_function_privilege('efa_mcp_reader', p.oid, 'EXECUTE')
              AND has_function_privilege('efa_mcp_readonly', p.oid, 'EXECUTE')
       ) THEN
        RAISE EXCEPTION 'Existing product_period_economics contract changed';
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

    IF to_regclass('mcp_read.competitor_latest_finding_set') IS NOT NULL
       OR to_regclass('mcp_read.competitor_findings') IS NOT NULL
       OR to_regclass('mcp_read.competitor_monitoring_coverage') IS NOT NULL THEN
        RAISE EXCEPTION 'One or more Migration 023 objects already exist';
    END IF;

    IF to_regclass('public.competitor_finding_sets') IS NULL
       OR to_regclass('public.competitor_findings') IS NULL
       OR to_regclass('public.competitor_sku_profiles') IS NULL
       OR to_regclass('public.competitor_watchlist_memberships') IS NULL THEN
        RAISE EXCEPTION 'One or more Competitor Monitor source tables are missing';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
         WHERE c.oid IN (
                   'public.competitor_finding_sets'::regclass,
                   'public.competitor_findings'::regclass,
                   'public.competitor_sku_profiles'::regclass,
                   'public.competitor_watchlist_memberships'::regclass
               )
           AND (
               c.relkind <> 'r'
               OR pg_get_userbyid(c.relowner) <> 'efa'
               OR c.relrowsecurity
               OR c.relforcerowsecurity
           )
    ) THEN
        RAISE EXCEPTION 'Competitor Monitor source ownership/type/RLS contract changed';
    END IF;

    WITH expected(table_name, column_name, data_type, not_null) AS (
        VALUES
            ('competitor_finding_sets', 'finding_set_id', 'uuid', true),
            ('competitor_finding_sets', 'set_key', 'text', true),
            ('competitor_finding_sets', 'persistence_contract_version', 'text', true),
            ('competitor_finding_sets', 'finding_set_contract_version', 'text', true),
            ('competitor_finding_sets', 'source_analysis_contract_version', 'text', true),
            ('competitor_finding_sets', 'source_findings_sha256', 'text', true),
            ('competitor_finding_sets', 'source_findings_semantic_sha256', 'text', true),
            ('competitor_finding_sets', 'source_analysis_sha256', 'text', true),
            ('competitor_finding_sets', 'previous_source_kind', 'text', true),
            ('competitor_finding_sets', 'previous_derived_batch_id', 'text', true),
            ('competitor_finding_sets', 'previous_reference_at', 'timestamp with time zone', true),
            ('competitor_finding_sets', 'previous_captured_through', 'timestamp with time zone', true),
            ('competitor_finding_sets', 'current_source_kind', 'text', true),
            ('competitor_finding_sets', 'current_derived_batch_id', 'text', true),
            ('competitor_finding_sets', 'current_reference_at', 'timestamp with time zone', true),
            ('competitor_finding_sets', 'current_captured_through', 'timestamp with time zone', true),
            ('competitor_finding_sets', 'expected_findings_count', 'integer', true),
            ('competitor_finding_sets', 'applied_at', 'timestamp with time zone', true),
            ('competitor_findings', 'finding_id', 'uuid', true),
            ('competitor_findings', 'finding_set_id', 'uuid', true),
            ('competitor_findings', 'finding_kind', 'text', true),
            ('competitor_findings', 'offer_id', 'text', true),
            ('competitor_findings', 'product_family_id', 'uuid', false),
            ('competitor_findings', 'listing_id', 'uuid', false),
            ('competitor_findings', 'old_observation_id', 'uuid', false),
            ('competitor_findings', 'new_observation_id', 'uuid', false),
            ('competitor_findings', 'topic', 'text', true),
            ('competitor_findings', 'metric', 'text', true),
            ('competitor_findings', 'severity', 'text', true),
            ('competitor_findings', 'confidence', 'text', true),
            ('competitor_findings', 'status', 'text', true),
            ('competitor_findings', 'evidence', 'jsonb', true),
            ('competitor_findings', 'details', 'jsonb', true),
            ('competitor_findings', 'finding_key', 'text', true),
            ('competitor_findings', 'first_detected_at', 'timestamp with time zone', true),
            ('competitor_findings', 'last_detected_at', 'timestamp with time zone', true),
            ('competitor_sku_profiles', 'offer_id', 'text', true),
            ('competitor_sku_profiles', 'watchlist_state', 'text', true),
            ('competitor_sku_profiles', 'notes', 'text', false),
            ('competitor_watchlist_memberships', 'offer_id', 'text', true),
            ('competitor_watchlist_memberships', 'membership_status', 'text', true),
            ('competitor_watchlist_memberships', 'valid_to', 'timestamp with time zone', false)
    )
    SELECT string_agg(
               e.table_name || '.' || e.column_name,
               ', ' ORDER BY e.table_name, e.column_name
           )
      INTO missing_columns
      FROM expected e
     WHERE NOT EXISTS (
         SELECT 1
           FROM pg_attribute a
          WHERE a.attrelid = to_regclass('public.' || e.table_name)
            AND a.attname = e.column_name
            AND format_type(a.atttypid, a.atttypmod) = e.data_type
            AND a.attnotnull = e.not_null
            AND a.attnum > 0
            AND NOT a.attisdropped
     );

    IF missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Required source column contract changed: %', missing_columns;
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
        RAISE EXCEPTION 'Direct/effective raw competitor-table ACL is not closed';
    END IF;
END
$preconditions$;

CREATE VIEW mcp_read.competitor_latest_finding_set
WITH (security_barrier = true)
AS
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
WHERE s.finding_set_contract_version = 'competitor_finding_set.v1'
ORDER BY
    s.current_reference_at DESC,
    s.applied_at DESC,
    s.finding_set_id DESC
LIMIT 1;

CREATE VIEW mcp_read.competitor_findings
WITH (security_barrier = true)
AS
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
FROM public.competitor_findings f;

CREATE VIEW mcp_read.competitor_monitoring_coverage
WITH (security_barrier = true)
AS
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
               AND m.membership_status IN ('CONTROL', 'PRIMARY', 'RESERVE')
        )
    ) AS active_monitored
FROM public.competitor_sku_profiles p;

ALTER VIEW mcp_read.competitor_latest_finding_set OWNER TO efa;
ALTER VIEW mcp_read.competitor_findings OWNER TO efa;
ALTER VIEW mcp_read.competitor_monitoring_coverage OWNER TO efa;

REVOKE ALL PRIVILEGES ON TABLE
    mcp_read.competitor_latest_finding_set,
    mcp_read.competitor_findings,
    mcp_read.competitor_monitoring_coverage
FROM PUBLIC, efa_mcp_readonly;

GRANT SELECT ON TABLE
    mcp_read.competitor_latest_finding_set,
    mcp_read.competitor_findings,
    mcp_read.competitor_monitoring_coverage
TO efa_mcp_reader;

COMMENT ON VIEW mcp_read.competitor_latest_finding_set IS
    'Latest persisted competitor_finding_set.v1 manifest for the Competitor Monitor Summary v1 builder.';

COMMENT ON VIEW mcp_read.competitor_findings IS
    'Persisted Competitor Monitor findings; consumers select the exact finding_set_id returned by competitor_latest_finding_set.';

COMMENT ON VIEW mcp_read.competitor_monitoring_coverage IS
    'Dynamic per-EFA-SKU monitoring coverage using active current CONTROL/PRIMARY/RESERVE memberships.';

COMMIT;
