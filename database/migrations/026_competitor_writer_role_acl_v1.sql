-- Migration 026: least-privilege Competitor Monitor writer role, v1.
--
-- The role is intentionally created with PASSWORD NULL. Credential generation,
-- PostgreSQL password provisioning, local secret-file creation, and any T2 write
-- are separate controlled operations and are not part of this migration.
--
-- Runtime allowlist:
--   SELECT on five approved mcp_read views;
--   INSERT on four immutable competitor history tables;
--   safe pg_catalog metadata and advisory-lock functions through existing
--   system/PUBLIC ACLs.
--
-- Existing PUBLIC EXECUTE on SECURITY INVOKER pgcrypto routines is not changed.
-- The preflight rejects any PUBLIC-executable SECURITY DEFINER routine reachable
-- through public or mcp_read, and the new role receives no direct function grant.
--
-- Business row counts are deliberately not deployment guards: they are mutable
-- operational data and do not identify the schema/ACL contract.
--
-- Exact rollback before password provisioning and use:
--   BEGIN;
--   REVOKE ALL PRIVILEGES ON DATABASE efa
--       FROM efa_competitor_writer;
--   REVOKE ALL PRIVILEGES ON SCHEMA public, mcp_read
--       FROM efa_competitor_writer;
--   REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public, mcp_read
--       FROM efa_competitor_writer;
--   REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public, mcp_read
--       FROM efa_competitor_writer;
--   REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public, mcp_read
--       FROM efa_competitor_writer;
--   DROP ROLE efa_competitor_writer;
--   COMMIT;
-- After credential provisioning, remove the protected local credential as a
-- coordinated operational step. After T2 use, the role still owns no objects,
-- so the database rollback remains mechanically identical; runtime/credential
-- coordination is additionally required.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog;

DO $preflight$
DECLARE
    target_tables CONSTANT text[] := ARRAY[
        'competitor_search_runs',
        'competitor_observations',
        'competitor_finding_sets',
        'competitor_findings'
    ];
    approved_views CONSTANT text[] := ARRAY[
        'competitor_reference_plan_source',
        'competitor_snapshot_runs',
        'competitor_snapshot_observations',
        'competitor_findings',
        'competitor_finding_sets_reconciliation'
    ];
    function_signature text;
    function_oid oid;
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Migration 026 must run only in database efa';
    END IF;

    IF current_user <> 'efa' THEN
        RAISE EXCEPTION 'Migration 026 must run as role efa';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'efa_competitor_writer'
    ) THEN
        RAISE EXCEPTION 'Role efa_competitor_writer already exists';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname = 'efa'
           AND rolcanlogin
           AND rolsuper
           AND rolcreatedb
           AND rolcreaterole
           AND rolinherit
           AND rolreplication
           AND rolbypassrls
    ) OR NOT EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname = 'efa_mcp_reader'
           AND NOT rolcanlogin
           AND NOT rolsuper
           AND NOT rolcreatedb
           AND NOT rolcreaterole
           AND NOT rolinherit
           AND NOT rolreplication
           AND NOT rolbypassrls
    ) OR NOT EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname = 'efa_mcp_readonly'
           AND rolcanlogin
           AND NOT rolsuper
           AND NOT rolcreatedb
           AND NOT rolcreaterole
           AND rolinherit
           AND NOT rolreplication
           AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'Required role baseline differs';
    END IF;

    IF (
        SELECT count(*)
          FROM pg_auth_members m
          JOIN pg_roles member_role ON member_role.oid = m.member
         WHERE member_role.rolname = 'efa_mcp_readonly'
    ) <> 1 OR NOT EXISTS (
        SELECT 1
          FROM pg_auth_members m
          JOIN pg_roles member_role ON member_role.oid = m.member
          JOIN pg_roles granted_role ON granted_role.oid = m.roleid
         WHERE member_role.rolname = 'efa_mcp_readonly'
           AND granted_role.rolname = 'efa_mcp_reader'
           AND NOT m.admin_option
    ) THEN
        RAISE EXCEPTION 'efa_mcp_readonly membership baseline differs';
    END IF;

    IF (
        SELECT pg_get_userbyid(datdba)
          FROM pg_database
         WHERE datname = 'efa'
    ) IS DISTINCT FROM 'efa' THEN
        RAISE EXCEPTION 'Database efa is missing or is not owned by efa';
    END IF;

    IF (
        SELECT pg_get_userbyid(nspowner)
          FROM pg_namespace
         WHERE nspname = 'mcp_read'
    ) IS DISTINCT FROM 'efa' OR (
        SELECT pg_get_userbyid(nspowner)
          FROM pg_namespace
         WHERE nspname = 'public'
    ) IS DISTINCT FROM 'pg_database_owner' THEN
        RAISE EXCEPTION 'Schema owner baseline differs';
    END IF;

    IF (
        SELECT count(*)
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname = ANY (target_tables)
    ) <> 4 OR EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname = ANY (target_tables)
           AND (
               c.relkind <> 'r'
               OR pg_get_userbyid(c.relowner) <> 'efa'
               OR c.relrowsecurity
               OR c.relforcerowsecurity
               OR EXISTS (
                   SELECT 1
                     FROM pg_trigger t
                    WHERE t.tgrelid = c.oid
                      AND NOT t.tgisinternal
               )
           )
    ) THEN
        RAISE EXCEPTION 'Target relation owner/RLS/trigger baseline differs';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname = ANY (target_tables)
           AND NOT con.convalidated
    ) THEN
        RAISE EXCEPTION 'A target relation has an unvalidated constraint';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_attrdef d
          JOIN pg_class c ON c.oid = d.adrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname = ANY (target_tables)
           AND pg_get_expr(d.adbin, d.adrelid) ILIKE '%nextval(%'
    ) THEN
        RAISE EXCEPTION 'A target relation unexpectedly depends on a sequence default';
    END IF;

    IF (
        SELECT count(*)
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relname = ANY (approved_views)
    ) <> 5 OR EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relname = ANY (approved_views)
           AND (
               c.relkind <> 'v'
               OR pg_get_userbyid(c.relowner) <> 'efa'
               OR NOT COALESCE(
                   c.reloptions @> ARRAY['security_barrier=true']::text[],
                   false
               )
           )
    ) THEN
        RAISE EXCEPTION 'Approved mcp_read view baseline differs';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(
              COALESCE(c.relacl, acldefault('r', c.relowner))
          ) acl
         WHERE n.nspname = 'public'
           AND c.relname = ANY (target_tables)
           AND acl.grantee <> c.relowner
    ) THEN
        RAISE EXCEPTION 'A target relation has a non-owner direct ACL';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(
              COALESCE(c.relacl, acldefault('r', c.relowner))
          ) acl
         WHERE n.nspname = 'mcp_read'
           AND c.relname = ANY (approved_views)
           AND acl.grantee <> c.relowner
           AND NOT (
               acl.grantee = 'efa_mcp_reader'::regrole
               AND acl.privilege_type = 'SELECT'
               AND NOT acl.is_grantable
           )
    ) OR EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relname = ANY (approved_views)
           AND NOT has_table_privilege(
               'efa_mcp_reader', c.oid, 'SELECT'
           )
    ) THEN
        RAISE EXCEPTION 'Approved mcp_read view ACL baseline differs';
    END IF;

    IF has_database_privilege('public', 'efa', 'CREATE')
       OR has_database_privilege('public', 'efa', 'TEMPORARY')
       OR has_schema_privilege('public', 'public', 'USAGE')
       OR has_schema_privilege('public', 'public', 'CREATE')
       OR has_schema_privilege('public', 'mcp_read', 'USAGE')
       OR has_schema_privilege('public', 'mcp_read', 'CREATE') THEN
        RAISE EXCEPTION 'PUBLIC database/schema baseline is too broad';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname IN ('public', 'mcp_read')
           AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
           AND (
               has_table_privilege('public', c.oid, 'SELECT')
               OR has_table_privilege('public', c.oid, 'INSERT')
               OR has_table_privilege('public', c.oid, 'UPDATE')
               OR has_table_privilege('public', c.oid, 'DELETE')
               OR has_table_privilege('public', c.oid, 'TRUNCATE')
               OR has_table_privilege('public', c.oid, 'REFERENCES')
               OR has_table_privilege('public', c.oid, 'TRIGGER')
           )
    ) THEN
        RAISE EXCEPTION 'PUBLIC has an effective application relation privilege';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_default_acl d
          LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
          CROSS JOIN LATERAL aclexplode(d.defaclacl) acl
         WHERE acl.grantee = 0
           AND d.defaclobjtype IN ('r', 'S', 'f')
           AND (
               d.defaclnamespace = 0
               OR n.nspname IN ('public', 'mcp_read')
           )
    ) THEN
        RAISE EXCEPTION 'A PUBLIC default ACL could broaden the writer contract';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname IN ('public', 'mcp_read')
           AND p.prosecdef
           AND has_function_privilege('public', p.oid, 'EXECUTE')
    ) THEN
        RAISE EXCEPTION 'PUBLIC can execute a reachable SECURITY DEFINER routine';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_roles r
         WHERE r.rolcanlogin
           AND NOT r.rolsuper
           AND r.rolname NOT LIKE 'pg\_%' ESCAPE '\'
           AND NOT EXISTS (
               SELECT 1
                 FROM unnest(target_tables) target(relname)
                WHERE NOT has_table_privilege(
                    r.oid,
                    format('public.%I', target.relname),
                    'INSERT'
                )
           )
    ) THEN
        RAISE EXCEPTION 'An existing non-superuser LOGIN role already writes all targets';
    END IF;

    FOREACH function_signature IN ARRAY ARRAY[
        'pg_catalog.pg_advisory_xact_lock(bigint)',
        'pg_catalog.hashtextextended(text,bigint)',
        'pg_catalog.now()',
        'pg_catalog.gen_random_uuid()',
        'pg_catalog.format_type(oid,integer)'
    ] LOOP
        function_oid := to_regprocedure(function_signature);

        IF function_oid IS NULL
           OR NOT has_function_privilege('public', function_oid, 'EXECUTE')
           OR (SELECT prosecdef FROM pg_proc WHERE oid = function_oid) THEN
            RAISE EXCEPTION 'Required safe pg_catalog function differs: %',
                function_signature;
        END IF;
    END LOOP;
END
$preflight$;

CREATE ROLE efa_competitor_writer
WITH
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS
    PASSWORD NULL;

ALTER ROLE efa_competitor_writer SET search_path = pg_catalog;

REVOKE ALL PRIVILEGES ON DATABASE efa FROM efa_competitor_writer;
GRANT CONNECT ON DATABASE efa TO efa_competitor_writer;
REVOKE CREATE, TEMPORARY ON DATABASE efa FROM efa_competitor_writer;

REVOKE ALL PRIVILEGES ON SCHEMA public, mcp_read
    FROM efa_competitor_writer;
GRANT USAGE ON SCHEMA public, mcp_read
    TO efa_competitor_writer;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public, mcp_read
    FROM efa_competitor_writer;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public, mcp_read
    FROM efa_competitor_writer;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public, mcp_read
    FROM efa_competitor_writer;

GRANT SELECT ON
    mcp_read.competitor_reference_plan_source,
    mcp_read.competitor_snapshot_runs,
    mcp_read.competitor_snapshot_observations,
    mcp_read.competitor_findings,
    mcp_read.competitor_finding_sets_reconciliation
TO efa_competitor_writer;

GRANT INSERT ON
    public.competitor_search_runs,
    public.competitor_observations,
    public.competitor_finding_sets,
    public.competitor_findings
TO efa_competitor_writer;

DO $postflight$
DECLARE
    target_tables CONSTANT text[] := ARRAY[
        'competitor_search_runs',
        'competitor_observations',
        'competitor_finding_sets',
        'competitor_findings'
    ];
    approved_views CONSTANT text[] := ARRAY[
        'competitor_reference_plan_source',
        'competitor_snapshot_runs',
        'competitor_snapshot_observations',
        'competitor_findings',
        'competitor_finding_sets_reconciliation'
    ];
    writer_oid oid := 'efa_competitor_writer'::regrole;
    differences text;
    function_signature text;
    function_oid oid;
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE oid = writer_oid
           AND rolcanlogin
           AND NOT rolsuper
           AND NOT rolcreatedb
           AND NOT rolcreaterole
           AND NOT rolinherit
           AND NOT rolreplication
           AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'efa_competitor_writer role flags differ';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_authid
         WHERE oid = writer_oid
           AND rolpassword IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'efa_competitor_writer unexpectedly has a password';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members
         WHERE member = writer_oid OR roleid = writer_oid
    ) THEN
        RAISE EXCEPTION 'efa_competitor_writer has a role membership edge';
    END IF;

    IF (
        SELECT array_agg(setting ORDER BY setting)
          FROM pg_db_role_setting s
          CROSS JOIN LATERAL unnest(s.setconfig) setting
         WHERE s.setrole = writer_oid
    ) IS DISTINCT FROM ARRAY['search_path=pg_catalog']::text[] THEN
        RAISE EXCEPTION 'efa_competitor_writer search_path differs';
    END IF;

    IF NOT has_database_privilege(writer_oid, 'efa', 'CONNECT')
       OR has_database_privilege(writer_oid, 'efa', 'CREATE')
       OR has_database_privilege(writer_oid, 'efa', 'TEMPORARY')
       OR NOT has_schema_privilege(writer_oid, 'public', 'USAGE')
       OR has_schema_privilege(writer_oid, 'public', 'CREATE')
       OR NOT has_schema_privilege(writer_oid, 'mcp_read', 'USAGE')
       OR has_schema_privilege(writer_oid, 'mcp_read', 'CREATE') THEN
        RAISE EXCEPTION 'Writer database/schema effective privileges differ';
    END IF;

    WITH expected(object_kind, object_name, privilege_type, is_grantable) AS (
        VALUES
            ('DATABASE', 'efa', 'CONNECT', false),
            ('SCHEMA', 'public', 'USAGE', false),
            ('SCHEMA', 'mcp_read', 'USAGE', false)
    ), actual AS (
        SELECT 'DATABASE'::text, d.datname::text,
               acl.privilege_type, acl.is_grantable
          FROM pg_database d
          CROSS JOIN LATERAL aclexplode(d.datacl) acl
         WHERE d.datname = 'efa'
           AND acl.grantee = writer_oid
        UNION ALL
        SELECT 'SCHEMA'::text, n.nspname::text,
               acl.privilege_type, acl.is_grantable
          FROM pg_namespace n
          CROSS JOIN LATERAL aclexplode(n.nspacl) acl
         WHERE acl.grantee = writer_oid
    ), diff AS (
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        UNION ALL
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(
               format(
                   '%s:%s:%s:%s',
                   object_kind, object_name, privilege_type, is_grantable
               ),
               ', ' ORDER BY object_kind, object_name, privilege_type
           )
      INTO differences
      FROM diff;

    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Writer direct database/schema ACL differs: %', differences;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_database
         WHERE datdba = writer_oid
    ) OR EXISTS (
        SELECT 1
          FROM pg_namespace
         WHERE nspowner = writer_oid
    ) OR EXISTS (
        SELECT 1
          FROM pg_class
         WHERE relowner = writer_oid
    ) OR EXISTS (
        SELECT 1
          FROM pg_proc
         WHERE proowner = writer_oid
    ) OR EXISTS (
        SELECT 1
          FROM pg_type
         WHERE typowner = writer_oid
    ) OR EXISTS (
        SELECT 1
          FROM pg_extension
         WHERE extowner = writer_oid
    ) THEN
        RAISE EXCEPTION 'efa_competitor_writer unexpectedly owns an object';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
           AND CASE
               WHEN c.relname = ANY (target_tables) THEN
                   NOT has_table_privilege(writer_oid, c.oid, 'INSERT')
                   OR has_table_privilege(writer_oid, c.oid, 'SELECT')
                   OR has_table_privilege(writer_oid, c.oid, 'UPDATE')
                   OR has_table_privilege(writer_oid, c.oid, 'DELETE')
                   OR has_table_privilege(writer_oid, c.oid, 'TRUNCATE')
                   OR has_table_privilege(writer_oid, c.oid, 'REFERENCES')
                   OR has_table_privilege(writer_oid, c.oid, 'TRIGGER')
               ELSE
                   has_table_privilege(writer_oid, c.oid, 'SELECT')
                   OR has_table_privilege(writer_oid, c.oid, 'INSERT')
                   OR has_table_privilege(writer_oid, c.oid, 'UPDATE')
                   OR has_table_privilege(writer_oid, c.oid, 'DELETE')
                   OR has_table_privilege(writer_oid, c.oid, 'TRUNCATE')
                   OR has_table_privilege(writer_oid, c.oid, 'REFERENCES')
                   OR has_table_privilege(writer_oid, c.oid, 'TRIGGER')
           END
    ) THEN
        RAISE EXCEPTION 'Writer effective public relation allowlist differs';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
           AND CASE
               WHEN c.relname = ANY (approved_views) THEN
                   NOT has_table_privilege(writer_oid, c.oid, 'SELECT')
                   OR has_table_privilege(writer_oid, c.oid, 'INSERT')
                   OR has_table_privilege(writer_oid, c.oid, 'UPDATE')
                   OR has_table_privilege(writer_oid, c.oid, 'DELETE')
                   OR has_table_privilege(writer_oid, c.oid, 'TRUNCATE')
                   OR has_table_privilege(writer_oid, c.oid, 'REFERENCES')
                   OR has_table_privilege(writer_oid, c.oid, 'TRIGGER')
               ELSE
                   has_table_privilege(writer_oid, c.oid, 'SELECT')
                   OR has_table_privilege(writer_oid, c.oid, 'INSERT')
                   OR has_table_privilege(writer_oid, c.oid, 'UPDATE')
                   OR has_table_privilege(writer_oid, c.oid, 'DELETE')
                   OR has_table_privilege(writer_oid, c.oid, 'TRUNCATE')
                   OR has_table_privilege(writer_oid, c.oid, 'REFERENCES')
                   OR has_table_privilege(writer_oid, c.oid, 'TRIGGER')
           END
    ) THEN
        RAISE EXCEPTION 'Writer effective mcp_read relation allowlist differs';
    END IF;

    WITH expected(
        schema_name, relation_name, privilege_type, is_grantable
    ) AS (
        SELECT 'public', relname, 'INSERT', false
          FROM unnest(target_tables) relname
        UNION ALL
        SELECT 'mcp_read', relname, 'SELECT', false
          FROM unnest(approved_views) relname
    ), actual AS (
        SELECT n.nspname::text, c.relname::text,
               acl.privilege_type, acl.is_grantable
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(c.relacl) acl
         WHERE acl.grantee = writer_oid
    ), diff AS (
        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
        UNION ALL
        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
    )
    SELECT string_agg(
               format(
                   '%s.%s:%s:%s',
                   schema_name, relation_name, privilege_type, is_grantable
               ),
               ', ' ORDER BY schema_name, relation_name, privilege_type
           )
      INTO differences
      FROM diff;

    IF differences IS NOT NULL THEN
        RAISE EXCEPTION 'Writer direct relation ACL differs: %', differences;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relkind = 'S'
           AND n.nspname NOT IN ('pg_catalog', 'information_schema')
           AND n.nspname NOT LIKE 'pg\_%' ESCAPE '\'
           AND (
               has_sequence_privilege(writer_oid, c.oid, 'USAGE')
               OR has_sequence_privilege(writer_oid, c.oid, 'SELECT')
               OR has_sequence_privilege(writer_oid, c.oid, 'UPDATE')
           )
    ) THEN
        RAISE EXCEPTION 'Writer unexpectedly has a non-system sequence privilege';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
          CROSS JOIN LATERAL aclexplode(
              COALESCE(p.proacl, acldefault('f', p.proowner))
          ) acl
         WHERE acl.grantee = writer_oid
           AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    ) THEN
        RAISE EXCEPTION 'Writer unexpectedly has a direct application function grant';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE p.prosecdef
           AND has_schema_privilege(writer_oid, n.oid, 'USAGE')
           AND has_function_privilege(writer_oid, p.oid, 'EXECUTE')
    ) THEN
        RAISE EXCEPTION 'Writer can execute a reachable SECURITY DEFINER routine';
    END IF;

    FOREACH function_signature IN ARRAY ARRAY[
        'pg_catalog.pg_advisory_xact_lock(bigint)',
        'pg_catalog.hashtextextended(text,bigint)',
        'pg_catalog.now()',
        'pg_catalog.gen_random_uuid()',
        'pg_catalog.format_type(oid,integer)'
    ] LOOP
        function_oid := to_regprocedure(function_signature);

        IF function_oid IS NULL
           OR NOT has_function_privilege(writer_oid, function_oid, 'EXECUTE')
           OR (SELECT prosecdef FROM pg_proc WHERE oid = function_oid) THEN
            RAISE EXCEPTION 'Writer required function contract differs: %',
                function_signature;
        END IF;
    END LOOP;

    IF NOT has_schema_privilege(writer_oid, 'pg_catalog', 'USAGE')
       OR NOT has_table_privilege(writer_oid, 'pg_catalog.pg_class', 'SELECT')
       OR NOT has_table_privilege(writer_oid, 'pg_catalog.pg_namespace', 'SELECT')
       OR NOT has_table_privilege(writer_oid, 'pg_catalog.pg_attribute', 'SELECT')
       OR NOT has_table_privilege(writer_oid, 'pg_catalog.pg_constraint', 'SELECT')
       OR NOT has_table_privilege(writer_oid, 'pg_catalog.pg_index', 'SELECT') THEN
        RAISE EXCEPTION 'Writer required pg_catalog metadata access differs';
    END IF;
END
$postflight$;

COMMIT;
