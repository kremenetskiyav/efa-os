-- Competitor Finding Set persistence manifest v1.
--
-- The manifest records immutable source-artifact and snapshot-pair provenance.
-- Existing finding history must be empty before adding the mandatory link.
-- No finding sets or findings are inserted by this migration.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    column_mismatch_count integer;
    finding_constraint_count integer;
    finding_index_count integer;
BEGIN
    IF current_database() <> 'efa' THEN
        RAISE EXCEPTION 'Expected database efa, got %', current_database();
    END IF;

    IF current_user <> 'efa' THEN
        RAISE EXCEPTION 'Migration 022 must run as role efa, got %', current_user;
    END IF;

    IF to_regclass('public.competitor_findings') IS NULL THEN
        RAISE EXCEPTION 'Required table public.competitor_findings is missing';
    END IF;

    IF (
        SELECT pg_get_userbyid(c.relowner)
          FROM pg_class c
         WHERE c.oid = 'public.competitor_findings'::regclass
    ) IS DISTINCT FROM 'efa' THEN
        RAISE EXCEPTION 'public.competitor_findings must be owned by efa';
    END IF;

    IF to_regclass('public.competitor_finding_sets') IS NOT NULL THEN
        RAISE EXCEPTION 'public.competitor_finding_sets already exists';
    END IF;

    IF to_regprocedure('gen_random_uuid()') IS NULL THEN
        RAISE EXCEPTION 'Required function gen_random_uuid() is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM public.competitor_findings) THEN
        RAISE EXCEPTION 'competitor_findings must be empty before Migration 022';
    END IF;

    WITH expected (
        attnum,
        attname,
        data_type,
        attnotnull,
        default_expr
    ) AS (
        VALUES
            (1, 'finding_id', 'uuid', true, 'gen_random_uuid()'),
            (2, 'finding_kind', 'text', true, NULL),
            (3, 'offer_id', 'text', true, NULL),
            (4, 'product_family_id', 'uuid', false, NULL),
            (5, 'listing_id', 'uuid', false, NULL),
            (6, 'old_observation_id', 'uuid', false, NULL),
            (7, 'new_observation_id', 'uuid', false, NULL),
            (8, 'topic', 'text', true, NULL),
            (9, 'metric', 'text', true, NULL),
            (10, 'severity', 'text', true, NULL),
            (11, 'confidence', 'text', true, NULL),
            (12, 'status', 'text', true, NULL),
            (13, 'evidence', 'jsonb', true, '''[]''::jsonb'),
            (14, 'details', 'jsonb', true, '''{}''::jsonb'),
            (15, 'finding_key', 'text', true, NULL),
            (16, 'first_detected_at', 'timestamp with time zone', true, NULL),
            (17, 'last_detected_at', 'timestamp with time zone', true, NULL),
            (18, 'created_at', 'timestamp with time zone', true, 'now()'),
            (19, 'updated_at', 'timestamp with time zone', true, 'now()')
    ),
    actual AS (
        SELECT
            a.attnum::integer AS attnum,
            a.attname::text AS attname,
            format_type(a.atttypid, a.atttypmod) AS data_type,
            a.attnotnull,
            pg_get_expr(ad.adbin, ad.adrelid) AS default_expr,
            a.attidentity,
            a.attgenerated,
            a.attacl
          FROM pg_attribute a
          LEFT JOIN pg_attrdef ad
            ON ad.adrelid = a.attrelid
           AND ad.adnum = a.attnum
         WHERE a.attrelid = 'public.competitor_findings'::regclass
           AND a.attnum > 0
           AND NOT a.attisdropped
    )
    SELECT count(*)
      INTO column_mismatch_count
      FROM expected e
      FULL JOIN actual a USING (attnum)
     WHERE e.attname IS DISTINCT FROM a.attname
        OR e.data_type IS DISTINCT FROM a.data_type
        OR e.attnotnull IS DISTINCT FROM a.attnotnull
        OR e.default_expr IS DISTINCT FROM a.default_expr
        OR a.attidentity IS DISTINCT FROM ''
        OR a.attgenerated IS DISTINCT FROM ''
        OR a.attacl IS NOT NULL;

    IF column_mismatch_count <> 0 THEN
        RAISE EXCEPTION 'competitor_findings column contract changed (% mismatches)',
            column_mismatch_count;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM (
            VALUES
                ('competitor_findings_pkey', 'p'),
                ('competitor_findings_offer_id_fkey', 'f'),
                ('competitor_findings_product_family_id_fkey', 'f'),
                ('competitor_findings_listing_id_fkey', 'f'),
                ('competitor_findings_old_observation_id_fkey', 'f'),
                ('competitor_findings_new_observation_id_fkey', 'f'),
                ('competitor_findings_finding_key_key', 'u'),
                ('competitor_findings_kind_check', 'c'),
                ('competitor_findings_values_check', 'c'),
                ('competitor_findings_observations_check', 'c'),
                ('competitor_findings_timestamps_check', 'c')
          ) AS expected(constraint_name, constraint_type)
         WHERE NOT EXISTS (
            SELECT 1
              FROM pg_constraint c
             WHERE c.conrelid = 'public.competitor_findings'::regclass
               AND c.conname = expected.constraint_name
               AND c.contype = expected.constraint_type::"char"
               AND (c.contype <> 'c' OR c.convalidated)
         )
    ) THEN
        RAISE EXCEPTION 'competitor_findings constraint contract changed';
    END IF;

    SELECT count(*)
      INTO finding_constraint_count
      FROM pg_constraint c
     WHERE c.conrelid = 'public.competitor_findings'::regclass;

    IF finding_constraint_count <> 11 THEN
        RAISE EXCEPTION 'Expected 11 competitor_findings constraints, got %',
            finding_constraint_count;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.conrelid = 'public.competitor_findings'::regclass
           AND c.contype = 'f'
           AND (c.confdeltype <> 'r' OR c.confupdtype <> 'a')
    ) THEN
        RAISE EXCEPTION 'competitor_findings foreign-key action contract changed';
    END IF;

    SELECT count(*)
      INTO finding_index_count
      FROM pg_index i
     WHERE i.indrelid = 'public.competitor_findings'::regclass;

    IF finding_index_count <> 3
       OR to_regclass('public.competitor_findings_pkey') IS NULL
       OR to_regclass('public.competitor_findings_finding_key_key') IS NULL
       OR to_regclass(
            'public.competitor_findings_offer_kind_status_last_idx'
       ) IS NULL THEN
        RAISE EXCEPTION 'competitor_findings index contract changed';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_trigger t
         WHERE t.tgrelid = 'public.competitor_findings'::regclass
           AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'Unexpected user trigger on competitor_findings';
    END IF;
END $$;

CREATE TABLE public.competitor_finding_sets (
    finding_set_id uuid NOT NULL DEFAULT gen_random_uuid(),
    set_key text NOT NULL,
    persistence_contract_version text NOT NULL,
    finding_set_contract_version text NOT NULL,
    source_analysis_contract_version text NOT NULL,
    source_findings_sha256 text NOT NULL,
    source_findings_semantic_sha256 text NOT NULL,
    source_analysis_sha256 text NOT NULL,
    previous_source_kind text NOT NULL,
    previous_derived_batch_id text NOT NULL,
    previous_reference_at timestamptz NOT NULL,
    previous_captured_through timestamptz NOT NULL,
    current_source_kind text NOT NULL,
    current_derived_batch_id text NOT NULL,
    current_reference_at timestamptz NOT NULL,
    current_captured_through timestamptz NOT NULL,
    expected_findings_count integer NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_finding_sets_pkey PRIMARY KEY (finding_set_id),
    CONSTRAINT competitor_finding_sets_set_key_key UNIQUE (set_key),
    CONSTRAINT competitor_finding_sets_snapshot_pair_key UNIQUE (
        finding_set_contract_version,
        previous_source_kind,
        previous_derived_batch_id,
        current_source_kind,
        current_derived_batch_id
    ),
    CONSTRAINT competitor_finding_sets_values_check CHECK (
        btrim(set_key) <> ''
        AND btrim(persistence_contract_version) <> ''
        AND btrim(finding_set_contract_version) <> ''
        AND btrim(source_analysis_contract_version) <> ''
        AND btrim(previous_source_kind) <> ''
        AND btrim(previous_derived_batch_id) <> ''
        AND btrim(current_source_kind) <> ''
        AND btrim(current_derived_batch_id) <> ''
    ),
    CONSTRAINT competitor_finding_sets_hashes_check CHECK (
        source_findings_sha256 ~ '^[0-9a-f]{64}$'
        AND source_findings_semantic_sha256 ~ '^[0-9a-f]{64}$'
        AND source_analysis_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT competitor_finding_sets_timestamps_check CHECK (
        previous_captured_through >= previous_reference_at
        AND current_captured_through >= current_reference_at
        AND current_reference_at > previous_reference_at
    ),
    CONSTRAINT competitor_finding_sets_expected_count_check CHECK (
        expected_findings_count >= 0
    )
);

COMMENT ON TABLE public.competitor_finding_sets IS
    'Immutable manifests for persisted Competitor Finding Engine result sets.';

CREATE INDEX competitor_finding_sets_current_reference_at_idx
    ON public.competitor_finding_sets (current_reference_at DESC);

ALTER TABLE public.competitor_findings
    ADD COLUMN finding_set_id uuid NOT NULL;

ALTER TABLE public.competitor_findings
    ADD CONSTRAINT competitor_findings_finding_set_id_fkey
    FOREIGN KEY (finding_set_id)
    REFERENCES public.competitor_finding_sets (finding_set_id)
    ON DELETE RESTRICT;

CREATE INDEX competitor_findings_finding_set_id_idx
    ON public.competitor_findings (finding_set_id);

COMMENT ON COLUMN public.competitor_findings.finding_set_id IS
    'Mandatory provenance link to the immutable finding-set manifest.';

COMMIT;
