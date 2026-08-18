BEGIN;

LOCK TABLE cpc_collection_runs IN SHARE ROW EXCLUSIVE MODE;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM cpc_collection_runs
     GROUP BY business_date
    HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION 'cpc_collection_runs contains duplicate business_date values';
  END IF;
END $$;

ALTER TABLE cpc_collection_runs
  DROP CONSTRAINT IF EXISTS cpc_collection_runs_status_check;

ALTER TABLE cpc_collection_runs
  ALTER COLUMN report_uuid DROP NOT NULL,
  ADD COLUMN lifecycle_state text,
  ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN last_status_check_at timestamptz,
  ADD COLUMN status_check_count integer NOT NULL DEFAULT 0,
  ADD COLUMN report_state text,
  ADD COLUMN error_code text,
  ADD COLUMN error_message text,
  ADD COLUMN completed_at timestamptz,
  ADD COLUMN campaigns jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN poll_lease_token uuid,
  ADD COLUMN poll_lease_until timestamptz,
  ADD COLUMN attention_reason text;

UPDATE cpc_collection_runs
   SET lifecycle_state = CASE
         WHEN status = 'success' AND records_count = 0 THEN 'SUCCESS_ZERO'
         WHEN status = 'success' THEN 'SUCCESS_NONZERO'
         ELSE 'FAILED'
       END,
       status = CASE WHEN status = 'success' THEN 'success' ELSE 'failed' END,
       report_state = CASE WHEN status = 'success' THEN 'LEGACY_COMPLETE' ELSE 'LEGACY_INCOMPLETE' END,
       updated_at = GREATEST(created_at, collected_at),
       completed_at = CASE WHEN status = 'success' THEN collected_at ELSE now() END,
       error_code = CASE WHEN status = 'success' THEN NULL ELSE 'LEGACY_INCOMPLETE_RUN' END,
       error_message = CASE WHEN status = 'success' THEN NULL ELSE 'Incomplete CPC run migrated to FAILED' END;

ALTER TABLE cpc_collection_runs
  ALTER COLUMN lifecycle_state SET NOT NULL,
  ADD CONSTRAINT cpc_collection_runs_status_check
    CHECK (status IN ('pending','success','failed','stuck')),
  ADD CONSTRAINT cpc_collection_runs_lifecycle_state_check
    CHECK (lifecycle_state IN ('PENDING','SUCCESS_ZERO','SUCCESS_NONZERO','FAILED','STUCK')),
  ADD CONSTRAINT cpc_collection_runs_status_check_count_check
    CHECK (status_check_count >= 0),
  ADD CONSTRAINT cpc_collection_runs_report_required_check
    CHECK (
      lifecycle_state NOT IN ('SUCCESS_ZERO','SUCCESS_NONZERO')
      OR (report_uuid IS NOT NULL AND completed_at IS NOT NULL)
    ),
  ADD CONSTRAINT cpc_collection_runs_lease_pair_check
    CHECK (
      (poll_lease_token IS NULL AND poll_lease_until IS NULL)
      OR (poll_lease_token IS NOT NULL AND poll_lease_until IS NOT NULL)
    );

CREATE UNIQUE INDEX cpc_collection_runs_business_date_uq
  ON cpc_collection_runs (business_date);
CREATE UNIQUE INDEX cpc_collection_runs_report_uuid_uq
  ON cpc_collection_runs (report_uuid)
  WHERE report_uuid IS NOT NULL;
CREATE INDEX cpc_collection_runs_pending_poll_idx
  ON cpc_collection_runs (created_at, last_status_check_at)
  WHERE lifecycle_state = 'PENDING';

INSERT INTO cpc_collection_runs (
  collection_ref,
  collected_at,
  business_date,
  report_uuid,
  status,
  campaigns_count,
  records_count,
  mapped_offer_ids,
  unmapped_skus,
  mapping_status,
  source,
  created_at,
  lifecycle_state,
  updated_at,
  last_status_check_at,
  status_check_count,
  report_state,
  error_code,
  error_message,
  campaigns,
  attention_reason
)
VALUES (
  'cpc-day-2026-08-17',
  '2026-08-18T06:41:26.263349Z'::timestamptz,
  DATE '2026-08-17',
  '191827e5-2c73-429a-9ce1-34b48f560a46'::uuid,
  CASE WHEN now() - '2026-08-18T06:41:26.263349Z'::timestamptz >= interval '2 hours' THEN 'stuck' ELSE 'pending' END,
  5,
  0,
  0,
  0,
  'valid',
  'ozon_performance_statistics_v1',
  '2026-08-18T06:41:26.263349Z'::timestamptz,
  CASE WHEN now() - '2026-08-18T06:41:26.263349Z'::timestamptz >= interval '2 hours' THEN 'STUCK' ELSE 'PENDING' END,
  now(),
  now(),
  2,
  'NOT_STARTED',
  CASE WHEN now() - '2026-08-18T06:41:26.263349Z'::timestamptz >= interval '2 hours' THEN 'REPORT_STUCK' ELSE NULL END,
  CASE WHEN now() - '2026-08-18T06:41:26.263349Z'::timestamptz >= interval '2 hours' THEN 'Performance report remained pending beyond 2 hours' ELSE NULL END,
  '[
    {"id":"29798579","title":"УФ 004Б","state":"CAMPAIGN_STATE_INACTIVE","advObjectType":"SKU"},
    {"id":"29798564","title":"УФ 001Б","state":"CAMPAIGN_STATE_INACTIVE","advObjectType":"SKU"},
    {"id":"29798552","title":"УФ 002Б","state":"CAMPAIGN_STATE_INACTIVE","advObjectType":"SKU"},
    {"id":"29798536","title":"УФ 003Б","state":"CAMPAIGN_STATE_INACTIVE","advObjectType":"SKU"},
    {"id":"29676455","title":"УФ 005Б","state":"CAMPAIGN_STATE_INACTIVE","advObjectType":"SKU"}
  ]'::jsonb,
  CASE WHEN now() - '2026-08-18T06:41:26.263349Z'::timestamptz >= interval '2 hours' THEN 'REPORT_STUCK: owner review required before replacement' ELSE NULL END
)
ON CONFLICT (business_date) DO NOTHING;

DO $$
DECLARE
  migrated_uuid uuid;
BEGIN
  SELECT report_uuid
    INTO migrated_uuid
    FROM cpc_collection_runs
   WHERE business_date = DATE '2026-08-17';
  IF migrated_uuid IS DISTINCT FROM '191827e5-2c73-429a-9ce1-34b48f560a46'::uuid THEN
    RAISE EXCEPTION '2026-08-17 CPC lifecycle conflicts with the approved report UUID';
  END IF;
END $$;

COMMIT;
