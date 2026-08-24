-- Post-deployment validation for
-- 017_postgresql_acl_hardening_efa_mcp_readonly_v1.sql.
-- The validation transaction is read-only and leaves no database changes.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

DO $$
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Expected database efa, got %', current_database();
    END IF;

    IF NOT has_database_privilege('efa_mcp_readonly', 'efa', 'CONNECT')
       OR has_database_privilege('efa_mcp_readonly', 'efa', 'TEMPORARY')
       OR has_database_privilege('efa_mcp_readonly', 'efa', 'CREATE') THEN
        RAISE EXCEPTION 'Unexpected database privileges for efa_mcp_readonly';
    END IF;

    IF NOT has_database_privilege('efa', 'efa', 'TEMPORARY') THEN
        RAISE EXCEPTION 'Database owner efa lost effective TEMPORARY';
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

    IF NOT has_schema_privilege('efa_mcp_readonly', 'mcp_read', 'USAGE')
       OR has_schema_privilege('efa_mcp_readonly', 'mcp_read', 'CREATE')
       OR has_schema_privilege('efa_mcp_readonly', 'public', 'USAGE')
       OR has_schema_privilege('efa_mcp_readonly', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Unexpected schema privileges for efa_mcp_readonly';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
           AND (
               has_table_privilege('efa_mcp_readonly', c.oid, 'SELECT')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'INSERT')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'UPDATE')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'DELETE')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'TRUNCATE')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'REFERENCES')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'TRIGGER')
           )
    ) THEN
        RAISE EXCEPTION 'efa_mcp_readonly has a raw public relation privilege';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
           AND n.nspname NOT LIKE 'pg\_%' ESCAPE '\'
           AND c.relkind = 'S'
           AND (
               has_sequence_privilege('efa_mcp_readonly', c.oid, 'USAGE')
               OR has_sequence_privilege('efa_mcp_readonly', c.oid, 'SELECT')
               OR has_sequence_privilege('efa_mcp_readonly', c.oid, 'UPDATE')
           )
    ) THEN
        RAISE EXCEPTION 'efa_mcp_readonly has a non-system sequence privilege';
    END IF;
END $$;

DO $$
DECLARE
    lo_oid oid;
    lo_signature text;
BEGIN
    FOREACH lo_signature IN ARRAY ARRAY[
        'pg_catalog.lo_creat(integer)',
        'pg_catalog.lo_create(oid)',
        'pg_catalog.lo_from_bytea(oid,bytea)',
        'pg_catalog.lo_open(oid,integer)',
        'pg_catalog.lo_put(oid,bigint,bytea)',
        'pg_catalog.lo_truncate(integer,integer)',
        'pg_catalog.lo_truncate64(integer,bigint)',
        'pg_catalog.lo_unlink(oid)',
        'pg_catalog.lowrite(integer,bytea)'
    ] LOOP
        lo_oid := to_regprocedure(lo_signature);

        IF lo_oid IS NULL THEN
            RAISE EXCEPTION 'Missing LO signature: %', lo_signature;
        END IF;

        IF has_function_privilege('efa_mcp_readonly', lo_oid, 'EXECUTE') THEN
            RAISE EXCEPTION 'efa_mcp_readonly can execute %', lo_signature;
        END IF;
    END LOOP;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_default_acl d
         WHERE d.defaclrole = 'efa'::regrole
           AND d.defaclnamespace = 0
           AND d.defaclobjtype = 'f'
    ) THEN
        RAISE EXCEPTION 'Global default function ACL for owner efa is missing';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_default_acl d
          CROSS JOIN LATERAL aclexplode(d.defaclacl) acl
         WHERE d.defaclrole = 'efa'::regrole
           AND d.defaclnamespace = 0
           AND d.defaclobjtype = 'f'
           AND acl.grantee = 0
           AND acl.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'Future efa-owned functions still grant PUBLIC EXECUTE';
    END IF;
END $$;

DO $$
DECLARE
    approved_function oid :=
        'mcp_read.product_period_economics(date,date)'::regprocedure;
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_proc p
         WHERE p.oid = approved_function
           AND pg_get_userbyid(p.proowner) = 'efa'
           AND p.prosecdef
           AND p.proconfig @> ARRAY['search_path=pg_catalog']::text[]
    ) THEN
        RAISE EXCEPTION 'Approved function security contract changed';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
          CROSS JOIN LATERAL aclexplode(
              COALESCE(p.proacl, acldefault('f', p.proowner))
          ) acl
         WHERE p.oid = approved_function
           AND acl.grantee = 0
           AND acl.privilege_type = 'EXECUTE'
    ) OR NOT has_function_privilege('efa_mcp_reader', approved_function, 'EXECUTE')
       OR NOT has_function_privilege('efa_mcp_readonly', approved_function, 'EXECUTE') THEN
        RAISE EXCEPTION 'Approved function EXECUTE ACL is invalid';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
           AND n.nspname NOT LIKE 'pg\_%' ESCAPE '\'
           AND has_schema_privilege('efa_mcp_readonly', n.oid, 'USAGE')
           AND has_function_privilege('efa_mcp_readonly', p.oid, 'EXECUTE')
           AND p.oid <> approved_function
    ) THEN
        RAISE EXCEPTION 'efa_mcp_readonly can execute a non-allowlisted application routine';
    END IF;
END $$;

DO $$
BEGIN
    IF (SELECT count(*) FROM pg_views WHERE schemaname = 'mcp_read') <> 7 THEN
        RAISE EXCEPTION 'Expected exactly seven approved mcp_read views';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'mcp_read'
           AND c.relkind = 'v'
           AND (
               NOT has_table_privilege('efa_mcp_readonly', c.oid, 'SELECT')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'INSERT')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'UPDATE')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'DELETE')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'TRUNCATE')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'REFERENCES')
               OR has_table_privilege('efa_mcp_readonly', c.oid, 'TRIGGER')
           )
    ) THEN
        RAISE EXCEPTION 'Approved mcp_read views are not SELECT-only';
    END IF;
END $$;

SELECT
    has_database_privilege('efa_mcp_readonly', 'efa', 'CONNECT') AS db_connect,
    has_database_privilege('efa_mcp_readonly', 'efa', 'TEMPORARY') AS db_temp,
    has_database_privilege('efa_mcp_readonly', 'efa', 'CREATE') AS db_create,
    has_schema_privilege('efa_mcp_readonly', 'mcp_read', 'USAGE') AS mcp_read_usage,
    has_schema_privilege('efa_mcp_readonly', 'mcp_read', 'CREATE') AS mcp_read_create,
    has_schema_privilege('efa_mcp_readonly', 'public', 'USAGE') AS public_usage,
    has_schema_privilege('efa_mcp_readonly', 'public', 'CREATE') AS public_create,
    has_function_privilege(
        'efa_mcp_readonly',
        'mcp_read.product_period_economics(date,date)',
        'EXECUTE'
    ) AS approved_function_execute,
    'PASS' AS status;

ROLLBACK;
