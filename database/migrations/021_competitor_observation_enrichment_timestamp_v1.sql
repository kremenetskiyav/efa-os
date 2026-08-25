-- Competitor observation enrichment provenance timestamp v1.
--
-- Search-result facts remain tied to captured_at. Product-page facts use the
-- nullable enrichment_captured_at added here. No baseline data is inserted.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $$
BEGIN
    IF to_regclass('public.competitor_observations') IS NULL
       OR to_regclass('public.competitor_search_runs') IS NULL
       OR to_regclass('public.competitor_reviews') IS NULL
       OR to_regclass('public.competitor_findings') IS NULL THEN
        RAISE EXCEPTION 'Required Competitor Monitor history tables are missing';
    END IF;

    IF EXISTS (SELECT 1 FROM public.competitor_search_runs)
       OR EXISTS (SELECT 1 FROM public.competitor_observations)
       OR EXISTS (SELECT 1 FROM public.competitor_reviews)
       OR EXISTS (SELECT 1 FROM public.competitor_findings) THEN
        RAISE EXCEPTION 'Competitor Monitor history must be empty before Migration 021';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'competitor_observations'
           AND column_name = 'enrichment_captured_at'
    ) THEN
        RAISE EXCEPTION 'competitor_observations.enrichment_captured_at already exists';
    END IF;
END $$;

ALTER TABLE public.competitor_observations
    ADD COLUMN enrichment_captured_at timestamptz NULL;

COMMENT ON COLUMN public.competitor_observations.enrichment_captured_at IS
    'Capture time for product-page enrichment facts; NULL when enrichment was not obtained.';

COMMIT;
