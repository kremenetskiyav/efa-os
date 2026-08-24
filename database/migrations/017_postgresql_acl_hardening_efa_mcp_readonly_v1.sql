-- PostgreSQL ACL hardening for the efa_mcp_readonly contour, v1.
--
-- Production pre-migration ACL snapshot (2026-08-24T05:34:58+00:00):
--   database efa owner efa: datacl = NULL
--   schema public owner pg_database_owner:
--     {pg_database_owner=UC/pg_database_owner,=U/pg_database_owner}
--   schema mcp_read owner efa:
--     {efa=UC/efa,efa_mcp_reader=U/efa}
--   each of the nine LO routines below owner efa: proacl = NULL
--   pg_default_acl for owner efa: no rows
--   mcp_read.product_period_economics(date,date) owner efa:
--     {efa=X/efa,efa_mcp_reader=X/efa}
--
-- Exact rollback to the snapshot above, if required:
--   BEGIN;
--   GRANT TEMPORARY ON DATABASE efa TO PUBLIC;
--   GRANT EXECUTE ON FUNCTION pg_catalog.lo_creat(integer) TO PUBLIC;
--   GRANT EXECUTE ON FUNCTION pg_catalog.lo_create(oid) TO PUBLIC;
--   GRANT EXECUTE ON FUNCTION pg_catalog.lo_from_bytea(oid, bytea) TO PUBLIC;
--   GRANT EXECUTE ON FUNCTION pg_catalog.lo_open(oid, integer) TO PUBLIC;
--   GRANT EXECUTE ON FUNCTION pg_catalog.lo_put(oid, bigint, bytea) TO PUBLIC;
--   GRANT EXECUTE ON FUNCTION pg_catalog.lo_truncate(integer, integer) TO PUBLIC;
--   GRANT EXECUTE ON FUNCTION pg_catalog.lo_truncate64(integer, bigint) TO PUBLIC;
--   GRANT EXECUTE ON FUNCTION pg_catalog.lo_unlink(oid) TO PUBLIC;
--   GRANT EXECUTE ON FUNCTION pg_catalog.lowrite(integer, bytea) TO PUBLIC;
--   GRANT USAGE ON SCHEMA public TO PUBLIC;
--   REVOKE USAGE ON SCHEMA public FROM efa;
--   ALTER DEFAULT PRIVILEGES FOR ROLE efa
--       GRANT EXECUTE ON FUNCTIONS TO PUBLIC;
--   COMMIT;
--
-- The migration deliberately does not change CONNECT, role attributes,
-- memberships, mcp_read grants, raw relation ACLs, object owners, or existing
-- application-function ACLs.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    expected_login_roles text[] := ARRAY['efa', 'efa_mcp_readonly'];
    actual_login_roles text[];
    lo_signature_count integer;
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Expected database efa, got %', current_database();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'efa'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'efa_mcp_reader'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'efa_mcp_readonly'
    ) THEN
        RAISE EXCEPTION 'One or more required roles are missing';
    END IF;

    SELECT array_agg(r.rolname ORDER BY r.rolname)
      INTO actual_login_roles
      FROM pg_roles r
     WHERE r.rolcanlogin
       AND r.rolname NOT LIKE 'pg\_%' ESCAPE '\'
       AND r.rolname <> 'postgres';

    IF actual_login_roles IS DISTINCT FROM expected_login_roles THEN
        RAISE EXCEPTION 'Unexpected application LOGIN roles: %', actual_login_roles;
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

    IF to_regprocedure('mcp_read.product_period_economics(date,date)') IS NULL THEN
        RAISE EXCEPTION 'Approved product_period_economics function is missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_proc p
         WHERE p.oid =
               'mcp_read.product_period_economics(date,date)'::regprocedure
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
         WHERE p.oid =
               'mcp_read.product_period_economics(date,date)'::regprocedure
           AND acl.grantee = 0
           AND acl.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC unexpectedly executes product_period_economics';
    END IF;

    IF NOT has_function_privilege(
        'efa_mcp_reader',
        'mcp_read.product_period_economics(date,date)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'efa_mcp_reader cannot execute product_period_economics';
    END IF;

    SELECT count(*)
      INTO lo_signature_count
      FROM pg_proc p
     WHERE p.oid IN (
        to_regprocedure('pg_catalog.lo_creat(integer)'),
        to_regprocedure('pg_catalog.lo_create(oid)'),
        to_regprocedure('pg_catalog.lo_from_bytea(oid,bytea)'),
        to_regprocedure('pg_catalog.lo_open(oid,integer)'),
        to_regprocedure('pg_catalog.lo_put(oid,bigint,bytea)'),
        to_regprocedure('pg_catalog.lo_truncate(integer,integer)'),
        to_regprocedure('pg_catalog.lo_truncate64(integer,bigint)'),
        to_regprocedure('pg_catalog.lo_unlink(oid)'),
        to_regprocedure('pg_catalog.lowrite(integer,bytea)')
    );

    IF lo_signature_count <> 9 THEN
        RAISE EXCEPTION 'Expected nine exact write-capable LO signatures, got %',
            lo_signature_count;
    END IF;
END $$;

REVOKE TEMPORARY ON DATABASE efa FROM PUBLIC;

REVOKE EXECUTE ON FUNCTION pg_catalog.lo_creat(integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_catalog.lo_create(oid) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_catalog.lo_from_bytea(oid, bytea) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_catalog.lo_open(oid, integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_catalog.lo_put(oid, bigint, bytea) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_catalog.lo_truncate(integer, integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_catalog.lo_truncate64(integer, bigint) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_catalog.lo_unlink(oid) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_catalog.lowrite(integer, bytea) FROM PUBLIC;

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO efa;

ALTER DEFAULT PRIVILEGES FOR ROLE efa
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

COMMIT;
