-- Post-deployment validation for
-- 026_competitor_writer_role_acl_v1.sql.
--
-- This validation is strictly read-only. It verifies effective privileges over
-- the complete public and mcp_read relation sets, not only direct positive ACLs.
-- It does not authenticate as the role, execute advisory locks, or issue even
-- zero-row INSERT statements. Those credential/runtime probes remain a separate
-- post-provisioning operation after a password is installed.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog;

DO $validation$
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
    writer_oid oid;
    differences text;
    function_signature text;
    function_oid oid;
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Validation 026 must run only in database efa';
    END IF;

    IF current_user <> 'efa' THEN
        RAISE EXCEPTION 'Validation 026 must run as role efa';
    END IF;

    SELECT oid
      INTO writer_oid
      FROM pg_roles
     WHERE rolname = 'efa_competitor_writer';

    IF writer_oid IS NULL THEN
        RAISE EXCEPTION 'Role efa_competitor_writer is missing';
    END IF;

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

    -- This proves the password credential is absent without selecting or
    -- displaying any verifier. pg_hba authentication routes are operational
    -- configuration and are outside this catalog-only validation.
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

    WITH expected(
        object_kind, object_name, privilege_type, is_grantable
    ) AS (
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
        SELECT 1 FROM pg_database WHERE datdba = writer_oid
    ) OR EXISTS (
        SELECT 1 FROM pg_namespace WHERE nspowner = writer_oid
    ) OR EXISTS (
        SELECT 1 FROM pg_class WHERE relowner = writer_oid
    ) OR EXISTS (
        SELECT 1 FROM pg_proc WHERE proowner = writer_oid
    ) OR EXISTS (
        SELECT 1 FROM pg_type WHERE typowner = writer_oid
    ) OR EXISTS (
        SELECT 1 FROM pg_extension WHERE extowner = writer_oid
    ) THEN
        RAISE EXCEPTION 'efa_competitor_writer unexpectedly owns an object';
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
        RAISE EXCEPTION 'Target relation owner/RLS/trigger contract differs';
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
        RAISE EXCEPTION 'Approved mcp_read view contract differs';
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
END
$validation$;

SELECT
    current_database() AS database_name,
    current_setting('transaction_read_only') AS transaction_read_only,
    (SELECT rolcanlogin FROM pg_roles
      WHERE rolname = 'efa_competitor_writer') AS login,
    has_database_privilege(
        'efa_competitor_writer', 'efa', 'CONNECT'
    ) AS database_connect,
    has_schema_privilege(
        'efa_competitor_writer', 'mcp_read', 'USAGE'
    ) AS mcp_read_usage,
    has_schema_privilege(
        'efa_competitor_writer', 'public', 'USAGE'
    ) AS public_usage,
    (SELECT count(*)
       FROM pg_auth_members
      WHERE member = 'efa_competitor_writer'::regrole
         OR roleid = 'efa_competitor_writer'::regrole) AS membership_edges,
    'PASS' AS status;

ROLLBACK;
