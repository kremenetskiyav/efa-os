-- Prepared only. Do not apply before backup and explicit deployment approval.
CREATE TABLE information_sources (
    source_id text PRIMARY KEY,
    title text NOT NULL,
    canonical_url text UNIQUE,
    source_type text NOT NULL,
    source_authority text NOT NULL,
    api_family text,
    business_domains jsonb NOT NULL DEFAULT '[]'::jsonb,
    retrieval_method text NOT NULL,
    document_format text,
    monitoring_priority text NOT NULL DEFAULT 'NORMAL',
    source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (source_type IN ('OPENAPI','NEWS','LEGAL_DOCUMENT','MANUAL_EVIDENCE','EMAIL')),
    CHECK (source_authority IN ('LEVEL_1','LEVEL_2','LEVEL_3','LEVEL_4')),
    CHECK (api_family IS NULL OR api_family IN ('SELLER','PERFORMANCE')),
    CHECK (retrieval_method IN ('PUBLIC_HTTP','MANUAL_BOOTSTRAP','PUBLIC_HTTP_OR_MANUAL_BOOTSTRAP','MANUAL_EVIDENCE')),
    CHECK (monitoring_priority IN ('LOW','NORMAL','HIGH','CRITICAL')),
    CHECK (jsonb_typeof(business_domains) = 'array'),
    CHECK (jsonb_typeof(source_metadata) = 'object')
);

CREATE TABLE information_source_snapshots (
    snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id text NOT NULL REFERENCES information_sources(source_id) ON DELETE RESTRICT,
    observed_at timestamptz,
    retrieved_at timestamptz NOT NULL,
    raw_sha256 text NOT NULL,
    canonical_sha256 text NOT NULL,
    raw_byte_size bigint NOT NULL,
    content_type text,
    document_format text,
    version_marker text,
    effective_at timestamptz,
    last_update_marker text,
    canonical_structure jsonb NOT NULL,
    snapshot_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_reference text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id,canonical_sha256),
    CHECK (raw_byte_size >= 0),
    CHECK (raw_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(canonical_structure) IN ('object','array')),
    CHECK (jsonb_typeof(snapshot_metadata) = 'object')
);

CREATE TABLE information_source_checks (
    check_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    check_ref text NOT NULL UNIQUE,
    source_id text NOT NULL REFERENCES information_sources(source_id) ON DELETE RESTRICT,
    checked_at timestamptz NOT NULL,
    status text NOT NULL,
    http_status integer,
    content_type text,
    redirect_state text,
    raw_byte_size bigint NOT NULL DEFAULT 0,
    snapshot_id uuid REFERENCES information_source_snapshots(snapshot_id) ON DELETE RESTRICT,
    previous_snapshot_id uuid REFERENCES information_source_snapshots(snapshot_id) ON DELETE RESTRICT,
    error_summary text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (status IN ('SUCCESS','SUCCESS_ZERO','BASELINE_CREATED','SOURCE_UNAVAILABLE','HTTP_FAILED','PARSE_FAILED','CONTRACT_CHANGED','DIFF_FAILED','STALE')),
    CHECK (http_status IS NULL OR http_status BETWEEN 100 AND 599),
    CHECK (raw_byte_size >= 0)
);

CREATE TABLE information_change_events (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key text NOT NULL UNIQUE,
    source_id text NOT NULL REFERENCES information_sources(source_id) ON DELETE RESTRICT,
    previous_snapshot_id uuid REFERENCES information_source_snapshots(snapshot_id) ON DELETE RESTRICT,
    current_snapshot_id uuid NOT NULL REFERENCES information_source_snapshots(snapshot_id) ON DELETE RESTRICT,
    event_kind text NOT NULL,
    classification text NOT NULL,
    changed_units jsonb NOT NULL DEFAULT '[]'::jsonb,
    numeric_changes jsonb NOT NULL DEFAULT '[]'::jsonb,
    watch_concepts jsonb NOT NULL DEFAULT '[]'::jsonb,
    business_domains jsonb NOT NULL DEFAULT '[]'::jsonb,
    affected_components jsonb NOT NULL DEFAULT '[]'::jsonb,
    severity text NOT NULL,
    requires_action boolean NOT NULL,
    confidence text NOT NULL,
    review_status text NOT NULL DEFAULT 'PENDING',
    evidence_references jsonb NOT NULL DEFAULT '[]'::jsonb,
    event_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (previous_snapshot_id IS NULL OR previous_snapshot_id <> current_snapshot_id),
    CHECK (event_kind IN ('API_CONTRACT_CHANGE','LEGAL_DOCUMENT_CHANGE','NEWS_EVENT','MANUAL_EVIDENCE')),
    CHECK (classification IN ('NON_BREAKING','BREAKING','REVIEW','INFO_ONLY','ADDED','REMOVED','MODIFIED','MOVED_OR_RENUMBERED','UNKNOWN')),
    CHECK (severity IN ('INFO','WATCH','ACTION_REQUIRED','CRITICAL')),
    CHECK (confidence IN ('LOW','MEDIUM','HIGH')),
    CHECK (review_status IN ('PENDING','REVIEWED','DISMISSED','ACTIONED')),
    CHECK (jsonb_typeof(changed_units) = 'array'),
    CHECK (jsonb_typeof(numeric_changes) = 'array'),
    CHECK (jsonb_typeof(watch_concepts) = 'array'),
    CHECK (jsonb_typeof(business_domains) = 'array'),
    CHECK (jsonb_typeof(affected_components) = 'array'),
    CHECK (jsonb_typeof(evidence_references) = 'array'),
    CHECK (jsonb_typeof(event_metadata) = 'object')
);

CREATE INDEX idx_information_checks_source_time ON information_source_checks (source_id,checked_at DESC);
CREATE INDEX idx_information_snapshots_source_time ON information_source_snapshots (source_id,retrieved_at DESC);
CREATE INDEX idx_information_events_source_time ON information_change_events (source_id,created_at DESC);
CREATE INDEX idx_information_events_severity_review ON information_change_events (severity,review_status,created_at DESC);
