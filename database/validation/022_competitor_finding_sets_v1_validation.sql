-- Post-deployment, pre-seed validation for
-- 022_competitor_finding_sets_v1.sql.
-- The validation transaction is read-only and leaves no database changes.
--
-- Latest-set readers must filter the target finding_set_contract_version and
-- use deterministic ordering:
--   current_reference_at DESC, applied_at DESC, finding_set_id DESC.

\set ON_ERROR_STOP on

BEGIN;
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    expected record;
    actual_owner text;
    actual_kind "char";
    actual_persistence "char";
    row_security boolean;
    force_row_security boolean;
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Expected database efa, got %', current_database();
    END IF;

    FOR expected IN
        SELECT *
          FROM (
            VALUES
                ('competitor_finding_sets'::text, 'efa'::text),
                ('competitor_findings', 'efa')
          ) AS v(table_name, owner_name)
    LOOP
        IF to_regclass('public.' || expected.table_name) IS NULL THEN
            RAISE EXCEPTION 'Required table public.% is missing',
                expected.table_name;
        END IF;

        SELECT
            pg_get_userbyid(c.relowner),
            c.relkind,
            c.relpersistence,
            c.relrowsecurity,
            c.relforcerowsecurity
          INTO
            actual_owner,
            actual_kind,
            actual_persistence,
            row_security,
            force_row_security
          FROM pg_class c
         WHERE c.oid = ('public.' || expected.table_name)::regclass;

        IF actual_owner IS DISTINCT FROM expected.owner_name
           OR actual_kind IS DISTINCT FROM 'r'::"char"
           OR actual_persistence IS DISTINCT FROM 'p'::"char"
           OR row_security IS DISTINCT FROM false
           OR force_row_security IS DISTINCT FROM false THEN
            RAISE EXCEPTION
                'Invalid table contract for public.%: owner %, kind %, persistence %, RLS %, force RLS %',
                expected.table_name,
                actual_owner,
                actual_kind,
                actual_persistence,
                row_security,
                force_row_security;
        END IF;
    END LOOP;
END $$;

DO $$
DECLARE
    column_differences text[];
BEGIN
    WITH expected (
        table_name,
        attnum,
        attname,
        data_type,
        attnotnull,
        default_expr
    ) AS (
        VALUES
            ('competitor_finding_sets'::text, 1, 'finding_set_id'::text, 'uuid'::text, true, 'gen_random_uuid()'::text),
            ('competitor_finding_sets', 2, 'set_key', 'text', true, NULL),
            ('competitor_finding_sets', 3, 'persistence_contract_version', 'text', true, NULL),
            ('competitor_finding_sets', 4, 'finding_set_contract_version', 'text', true, NULL),
            ('competitor_finding_sets', 5, 'source_analysis_contract_version', 'text', true, NULL),
            ('competitor_finding_sets', 6, 'source_findings_sha256', 'text', true, NULL),
            ('competitor_finding_sets', 7, 'source_findings_semantic_sha256', 'text', true, NULL),
            ('competitor_finding_sets', 8, 'source_analysis_sha256', 'text', true, NULL),
            ('competitor_finding_sets', 9, 'previous_source_kind', 'text', true, NULL),
            ('competitor_finding_sets', 10, 'previous_derived_batch_id', 'text', true, NULL),
            ('competitor_finding_sets', 11, 'previous_reference_at', 'timestamp with time zone', true, NULL),
            ('competitor_finding_sets', 12, 'previous_captured_through', 'timestamp with time zone', true, NULL),
            ('competitor_finding_sets', 13, 'current_source_kind', 'text', true, NULL),
            ('competitor_finding_sets', 14, 'current_derived_batch_id', 'text', true, NULL),
            ('competitor_finding_sets', 15, 'current_reference_at', 'timestamp with time zone', true, NULL),
            ('competitor_finding_sets', 16, 'current_captured_through', 'timestamp with time zone', true, NULL),
            ('competitor_finding_sets', 17, 'expected_findings_count', 'integer', true, NULL),
            ('competitor_finding_sets', 18, 'applied_at', 'timestamp with time zone', true, 'now()'),
            ('competitor_finding_sets', 19, 'created_at', 'timestamp with time zone', true, 'now()'),
            ('competitor_findings', 1, 'finding_id', 'uuid', true, 'gen_random_uuid()'),
            ('competitor_findings', 2, 'finding_kind', 'text', true, NULL),
            ('competitor_findings', 3, 'offer_id', 'text', true, NULL),
            ('competitor_findings', 4, 'product_family_id', 'uuid', false, NULL),
            ('competitor_findings', 5, 'listing_id', 'uuid', false, NULL),
            ('competitor_findings', 6, 'old_observation_id', 'uuid', false, NULL),
            ('competitor_findings', 7, 'new_observation_id', 'uuid', false, NULL),
            ('competitor_findings', 8, 'topic', 'text', true, NULL),
            ('competitor_findings', 9, 'metric', 'text', true, NULL),
            ('competitor_findings', 10, 'severity', 'text', true, NULL),
            ('competitor_findings', 11, 'confidence', 'text', true, NULL),
            ('competitor_findings', 12, 'status', 'text', true, NULL),
            ('competitor_findings', 13, 'evidence', 'jsonb', true, '''[]''::jsonb'),
            ('competitor_findings', 14, 'details', 'jsonb', true, '''{}''::jsonb'),
            ('competitor_findings', 15, 'finding_key', 'text', true, NULL),
            ('competitor_findings', 16, 'first_detected_at', 'timestamp with time zone', true, NULL),
            ('competitor_findings', 17, 'last_detected_at', 'timestamp with time zone', true, NULL),
            ('competitor_findings', 18, 'created_at', 'timestamp with time zone', true, 'now()'),
            ('competitor_findings', 19, 'updated_at', 'timestamp with time zone', true, 'now()'),
            ('competitor_findings', 20, 'finding_set_id', 'uuid', true, NULL)
    ),
    actual AS (
        SELECT
            c.relname::text AS table_name,
            a.attnum::integer AS attnum,
            a.attname::text AS attname,
            format_type(a.atttypid, a.atttypmod) AS data_type,
            a.attnotnull,
            pg_get_expr(ad.adbin, ad.adrelid) AS default_expr,
            a.attidentity,
            a.attgenerated,
            a.attacl
          FROM pg_attribute a
          JOIN pg_class c ON c.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          LEFT JOIN pg_attrdef ad
            ON ad.adrelid = a.attrelid
           AND ad.adnum = a.attnum
         WHERE n.nspname = 'public'
           AND c.relname IN (
               'competitor_finding_sets',
               'competitor_findings'
           )
           AND a.attnum > 0
           AND NOT a.attisdropped
    ),
    differences AS (
        SELECT format(
                   '%s.%s',
                   COALESCE(e.table_name, a.table_name),
                   COALESCE(e.attname, a.attname, '<missing>')
               ) AS column_name
          FROM expected e
          FULL JOIN actual a USING (table_name, attnum)
         WHERE e.attname IS DISTINCT FROM a.attname
            OR e.data_type IS DISTINCT FROM a.data_type
            OR e.attnotnull IS DISTINCT FROM a.attnotnull
            OR e.default_expr IS DISTINCT FROM a.default_expr
            OR a.attidentity IS DISTINCT FROM ''
            OR a.attgenerated IS DISTINCT FROM ''
            OR a.attacl IS NOT NULL
    )
    SELECT array_agg(d.column_name ORDER BY d.column_name)
      INTO column_differences
      FROM differences d;

    IF column_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Column contract differs: %', column_differences;
    END IF;
END $$;

DO $$
DECLARE
    constraint_differences text[];
BEGIN
    WITH expected (
        table_name,
        constraint_name,
        constraint_type,
        constraint_columns,
        definition
    ) AS (
        VALUES
            ('competitor_finding_sets'::text, 'competitor_finding_sets_pkey'::text, 'p'::text, ARRAY[1]::smallint[], 'PRIMARY KEY (finding_set_id)'::text),
            ('competitor_finding_sets', 'competitor_finding_sets_set_key_key', 'u', ARRAY[2]::smallint[], 'UNIQUE (set_key)'),
            ('competitor_finding_sets', 'competitor_finding_sets_snapshot_pair_key', 'u', ARRAY[4, 9, 10, 13, 14]::smallint[], 'UNIQUE (finding_set_contract_version, previous_source_kind, previous_derived_batch_id, current_source_kind, current_derived_batch_id)'),
            ('competitor_finding_sets', 'competitor_finding_sets_values_check', 'c', ARRAY[2, 3, 4, 5, 9, 10, 13, 14]::smallint[], 'CHECK (btrim(set_key) <> ''''::text AND btrim(persistence_contract_version) <> ''''::text AND btrim(finding_set_contract_version) <> ''''::text AND btrim(source_analysis_contract_version) <> ''''::text AND btrim(previous_source_kind) <> ''''::text AND btrim(previous_derived_batch_id) <> ''''::text AND btrim(current_source_kind) <> ''''::text AND btrim(current_derived_batch_id) <> ''''::text)'),
            ('competitor_finding_sets', 'competitor_finding_sets_hashes_check', 'c', ARRAY[6, 7, 8]::smallint[], 'CHECK (source_findings_sha256 ~ ''^[0-9a-f]{64}$''::text AND source_findings_semantic_sha256 ~ ''^[0-9a-f]{64}$''::text AND source_analysis_sha256 ~ ''^[0-9a-f]{64}$''::text)'),
            ('competitor_finding_sets', 'competitor_finding_sets_timestamps_check', 'c', ARRAY[12, 11, 16, 15]::smallint[], 'CHECK (previous_captured_through >= previous_reference_at AND current_captured_through >= current_reference_at AND current_reference_at > previous_reference_at)'),
            ('competitor_finding_sets', 'competitor_finding_sets_expected_count_check', 'c', ARRAY[17]::smallint[], 'CHECK (expected_findings_count >= 0)'),
            ('competitor_findings', 'competitor_findings_pkey', 'p', ARRAY[1]::smallint[], 'PRIMARY KEY (finding_id)'),
            ('competitor_findings', 'competitor_findings_finding_key_key', 'u', ARRAY[15]::smallint[], 'UNIQUE (finding_key)'),
            ('competitor_findings', 'competitor_findings_offer_id_fkey', 'f', ARRAY[3]::smallint[], 'FOREIGN KEY (offer_id) REFERENCES products(offer_id) ON DELETE RESTRICT'),
            ('competitor_findings', 'competitor_findings_product_family_id_fkey', 'f', ARRAY[4]::smallint[], 'FOREIGN KEY (product_family_id) REFERENCES competitor_product_families(product_family_id) ON DELETE RESTRICT'),
            ('competitor_findings', 'competitor_findings_listing_id_fkey', 'f', ARRAY[5]::smallint[], 'FOREIGN KEY (listing_id) REFERENCES competitor_listings(listing_id) ON DELETE RESTRICT'),
            ('competitor_findings', 'competitor_findings_old_observation_id_fkey', 'f', ARRAY[6]::smallint[], 'FOREIGN KEY (old_observation_id) REFERENCES competitor_observations(observation_id) ON DELETE RESTRICT'),
            ('competitor_findings', 'competitor_findings_new_observation_id_fkey', 'f', ARRAY[7]::smallint[], 'FOREIGN KEY (new_observation_id) REFERENCES competitor_observations(observation_id) ON DELETE RESTRICT'),
            ('competitor_findings', 'competitor_findings_finding_set_id_fkey', 'f', ARRAY[20]::smallint[], 'FOREIGN KEY (finding_set_id) REFERENCES competitor_finding_sets(finding_set_id) ON DELETE RESTRICT'),
            ('competitor_findings', 'competitor_findings_kind_check', 'c', ARRAY[2]::smallint[], 'CHECK (finding_kind = ANY (ARRAY[''ISSUE''::text, ''SIGNAL''::text]))'),
            ('competitor_findings', 'competitor_findings_values_check', 'c', ARRAY[8, 9, 10, 11, 12, 15, 13, 14]::smallint[], 'CHECK (btrim(topic) <> ''''::text AND btrim(metric) <> ''''::text AND btrim(severity) <> ''''::text AND btrim(confidence) <> ''''::text AND btrim(status) <> ''''::text AND btrim(finding_key) <> ''''::text AND jsonb_typeof(evidence) = ''array''::text AND jsonb_typeof(details) = ''object''::text)'),
            ('competitor_findings', 'competitor_findings_observations_check', 'c', ARRAY[6, 7]::smallint[], 'CHECK (old_observation_id IS NULL OR new_observation_id IS NULL OR old_observation_id <> new_observation_id)'),
            ('competitor_findings', 'competitor_findings_timestamps_check', 'c', ARRAY[17, 16, 19, 18]::smallint[], 'CHECK (last_detected_at >= first_detected_at AND updated_at >= created_at)')
    ),
    actual AS (
        SELECT
            r.relname::text AS table_name,
            c.conname::text AS constraint_name,
            c.contype::text AS constraint_type,
            c.conkey AS constraint_columns,
            regexp_replace(
                pg_get_constraintdef(c.oid, true),
                '[[:space:]]+',
                '',
                'g'
            ) AS normalized_definition,
            c.convalidated
          FROM pg_constraint c
          JOIN pg_class r ON r.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = r.relnamespace
         WHERE n.nspname = 'public'
           AND r.relname IN (
               'competitor_finding_sets',
               'competitor_findings'
           )
    ),
    differences AS (
        SELECT format(
                   '%s.%s',
                   COALESCE(e.table_name, a.table_name),
                   COALESCE(e.constraint_name, a.constraint_name)
               ) AS constraint_name
          FROM expected e
          FULL JOIN actual a USING (table_name, constraint_name)
         WHERE e.constraint_type IS DISTINCT FROM a.constraint_type
            OR e.constraint_columns IS DISTINCT FROM a.constraint_columns
            OR regexp_replace(
                   e.definition,
                   '[[:space:]]+',
                   '',
                   'g'
               ) IS DISTINCT FROM a.normalized_definition
            OR a.convalidated IS DISTINCT FROM true
    )
    SELECT array_agg(d.constraint_name ORDER BY d.constraint_name)
      INTO constraint_differences
      FROM differences d;

    IF constraint_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Constraint contract differs: %',
            constraint_differences;
    END IF;
END $$;

DO $$
DECLARE
    foreign_key_differences text[];
BEGIN
    WITH expected (
        constraint_name,
        source_columns,
        target_table,
        target_columns,
        delete_action,
        update_action,
        match_type
    ) AS (
        VALUES
            ('competitor_findings_offer_id_fkey'::text, ARRAY[3]::smallint[], 'public.products'::regclass::oid, ARRAY[1]::smallint[], 'r'::"char", 'a'::"char", 's'::"char"),
            ('competitor_findings_product_family_id_fkey', ARRAY[4]::smallint[], 'public.competitor_product_families'::regclass::oid, ARRAY[1]::smallint[], 'r'::"char", 'a'::"char", 's'::"char"),
            ('competitor_findings_listing_id_fkey', ARRAY[5]::smallint[], 'public.competitor_listings'::regclass::oid, ARRAY[1]::smallint[], 'r'::"char", 'a'::"char", 's'::"char"),
            ('competitor_findings_old_observation_id_fkey', ARRAY[6]::smallint[], 'public.competitor_observations'::regclass::oid, ARRAY[1]::smallint[], 'r'::"char", 'a'::"char", 's'::"char"),
            ('competitor_findings_new_observation_id_fkey', ARRAY[7]::smallint[], 'public.competitor_observations'::regclass::oid, ARRAY[1]::smallint[], 'r'::"char", 'a'::"char", 's'::"char"),
            ('competitor_findings_finding_set_id_fkey', ARRAY[20]::smallint[], 'public.competitor_finding_sets'::regclass::oid, ARRAY[1]::smallint[], 'r'::"char", 'a'::"char", 's'::"char")
    ),
    actual AS (
        SELECT
            c.conname::text AS constraint_name,
            c.conkey AS source_columns,
            c.confrelid AS target_table,
            c.confkey AS target_columns,
            c.confdeltype AS delete_action,
            c.confupdtype AS update_action,
            c.confmatchtype AS match_type,
            c.convalidated
          FROM pg_constraint c
         WHERE c.conrelid = 'public.competitor_findings'::regclass
           AND c.contype = 'f'
    ),
    differences AS (
        SELECT COALESCE(e.constraint_name, a.constraint_name) AS constraint_name
          FROM expected e
          FULL JOIN actual a USING (constraint_name)
         WHERE e.source_columns IS DISTINCT FROM a.source_columns
            OR e.target_table IS DISTINCT FROM a.target_table
            OR e.target_columns IS DISTINCT FROM a.target_columns
            OR e.delete_action IS DISTINCT FROM a.delete_action
            OR e.update_action IS DISTINCT FROM a.update_action
            OR e.match_type IS DISTINCT FROM a.match_type
            OR a.convalidated IS DISTINCT FROM true
    )
    SELECT array_agg(d.constraint_name ORDER BY d.constraint_name)
      INTO foreign_key_differences
      FROM differences d;

    IF foreign_key_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Foreign-key contract differs: %',
            foreign_key_differences;
    END IF;
END $$;

DO $$
DECLARE
    index_differences text[];
BEGIN
    WITH expected (
        table_name,
        index_name,
        is_unique,
        is_primary,
        definition
    ) AS (
        VALUES
            ('competitor_finding_sets'::text, 'competitor_finding_sets_pkey'::text, true, true, 'CREATE UNIQUE INDEX competitor_finding_sets_pkey ON public.competitor_finding_sets USING btree (finding_set_id)'::text),
            ('competitor_finding_sets', 'competitor_finding_sets_set_key_key', true, false, 'CREATE UNIQUE INDEX competitor_finding_sets_set_key_key ON public.competitor_finding_sets USING btree (set_key)'),
            ('competitor_finding_sets', 'competitor_finding_sets_snapshot_pair_key', true, false, 'CREATE UNIQUE INDEX competitor_finding_sets_snapshot_pair_key ON public.competitor_finding_sets USING btree (finding_set_contract_version, previous_source_kind, previous_derived_batch_id, current_source_kind, current_derived_batch_id)'),
            ('competitor_finding_sets', 'competitor_finding_sets_current_reference_at_idx', false, false, 'CREATE INDEX competitor_finding_sets_current_reference_at_idx ON public.competitor_finding_sets USING btree (current_reference_at DESC)'),
            ('competitor_findings', 'competitor_findings_pkey', true, true, 'CREATE UNIQUE INDEX competitor_findings_pkey ON public.competitor_findings USING btree (finding_id)'),
            ('competitor_findings', 'competitor_findings_finding_key_key', true, false, 'CREATE UNIQUE INDEX competitor_findings_finding_key_key ON public.competitor_findings USING btree (finding_key)'),
            ('competitor_findings', 'competitor_findings_offer_kind_status_last_idx', false, false, 'CREATE INDEX competitor_findings_offer_kind_status_last_idx ON public.competitor_findings USING btree (offer_id, finding_kind, status, last_detected_at DESC)'),
            ('competitor_findings', 'competitor_findings_finding_set_id_idx', false, false, 'CREATE INDEX competitor_findings_finding_set_id_idx ON public.competitor_findings USING btree (finding_set_id)')
    ),
    actual AS (
        SELECT
            t.relname::text AS table_name,
            i.relname::text AS index_name,
            x.indisunique AS is_unique,
            x.indisprimary AS is_primary,
            regexp_replace(
                pg_get_indexdef(x.indexrelid),
                '[[:space:]]+',
                '',
                'g'
            ) AS normalized_definition,
            pg_get_expr(x.indpred, x.indrelid) AS predicate,
            x.indisvalid,
            x.indisready,
            x.indislive
          FROM pg_index x
          JOIN pg_class i ON i.oid = x.indexrelid
          JOIN pg_class t ON t.oid = x.indrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace
         WHERE n.nspname = 'public'
           AND t.relname IN (
               'competitor_finding_sets',
               'competitor_findings'
           )
    ),
    differences AS (
        SELECT format(
                   '%s.%s',
                   COALESCE(e.table_name, a.table_name),
                   COALESCE(e.index_name, a.index_name)
               ) AS index_name
          FROM expected e
          FULL JOIN actual a USING (table_name, index_name)
         WHERE e.is_unique IS DISTINCT FROM a.is_unique
            OR e.is_primary IS DISTINCT FROM a.is_primary
            OR regexp_replace(
                   e.definition,
                   '[[:space:]]+',
                   '',
                   'g'
               ) IS DISTINCT FROM a.normalized_definition
            OR a.predicate IS NOT NULL
            OR a.indisvalid IS DISTINCT FROM true
            OR a.indisready IS DISTINCT FROM true
            OR a.indislive IS DISTINCT FROM true
    )
    SELECT array_agg(d.index_name ORDER BY d.index_name)
      INTO index_differences
      FROM differences d;

    IF index_differences IS NOT NULL THEN
        RAISE EXCEPTION 'Index contract differs: %', index_differences;
    END IF;
END $$;

DO $$
DECLARE
    table_oids oid[] := ARRAY[
        'public.competitor_finding_sets'::regclass::oid,
        'public.competitor_findings'::regclass::oid
    ];
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
         WHERE c.oid = ANY (table_oids)
           AND acl.grantee = ANY (array_prepend(0::oid, restricted_roles))
           AND acl.privilege_type IN (
               'SELECT',
               'INSERT',
               'UPDATE',
               'DELETE',
               'TRUNCATE',
               'REFERENCES',
               'TRIGGER'
           )
    ) THEN
        RAISE EXCEPTION 'Unexpected direct PUBLIC/MCP read-role table ACL';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM unnest(
                   ARRAY['efa_mcp_reader', 'efa_mcp_readonly']::text[]
               ) AS restricted(role_name)
          CROSS JOIN unnest(table_oids) AS target(table_oid)
         WHERE has_table_privilege(
                   restricted.role_name,
                   target.table_oid,
                   'SELECT'
               )
            OR has_table_privilege(
                   restricted.role_name,
                   target.table_oid,
                   'INSERT'
               )
            OR has_table_privilege(
                   restricted.role_name,
                   target.table_oid,
                   'UPDATE'
               )
            OR has_table_privilege(
                   restricted.role_name,
                   target.table_oid,
                   'DELETE'
               )
    ) THEN
        RAISE EXCEPTION 'An MCP read role has effective finding-table CRUD';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.competitor_finding_sets)
       OR EXISTS (SELECT 1 FROM public.competitor_findings) THEN
        RAISE EXCEPTION
            'Validation 022 requires post-migration, pre-seed empty tables';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_trigger t
         WHERE t.tgrelid IN (
             'public.competitor_finding_sets'::regclass,
             'public.competitor_findings'::regclass
         )
           AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'Unexpected user trigger on Finding Set tables';
    END IF;
END $$;

SELECT
    19 AS finding_set_columns_checked,
    20 AS findings_columns_checked,
    7 AS finding_set_constraints_checked,
    12 AS findings_constraints_checked,
    4 AS finding_set_indexes_checked,
    4 AS findings_indexes_checked,
    2 AS owners_checked,
    2 AS restricted_roles_checked,
    (SELECT count(*) FROM public.competitor_finding_sets) AS finding_set_rows,
    (SELECT count(*) FROM public.competitor_findings) AS finding_rows,
    'PASS' AS status;

ROLLBACK;
