-- Prepared only. Do not apply before backup and explicit deployment approval.
CREATE TABLE information_sources (
    source_id text PRIMARY KEY,
    canonical_url text NOT NULL UNIQUE,
    source_type text NOT NULL,
    source_authority text NOT NULL,
    api_family text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (source_type IN ('OPENAPI','NEWS','LEGAL_DOCUMENT','SELLER_NOTIFICATION','EMAIL')),
    CHECK (source_authority IN ('LEVEL_1','LEVEL_2','LEVEL_3','LEVEL_4')),
    CHECK (api_family IS NULL OR api_family IN ('SELLER','PERFORMANCE'))
);

CREATE TABLE information_source_snapshots (
    snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id text NOT NULL REFERENCES information_sources(source_id) ON DELETE RESTRICT,
    retrieved_at timestamptz NOT NULL,
    raw_sha256 text NOT NULL,
    canonical_sha256 text NOT NULL,
    raw_byte_size bigint NOT NULL,
    content_type text,
    spec_version text,
    api_version text,
    structural_contract jsonb NOT NULL,
    evidence_reference text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id,canonical_sha256),
    CHECK (raw_byte_size >= 0),
    CHECK (raw_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE information_source_checks (
    check_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    check_ref text NOT NULL UNIQUE,
    source_id text NOT NULL REFERENCES information_sources(source_id) ON DELETE RESTRICT,
    checked_at timestamptz NOT NULL,
    status text NOT NULL,
    http_status integer,
    content_type text,
    raw_byte_size bigint NOT NULL DEFAULT 0,
    snapshot_id uuid REFERENCES information_source_snapshots(snapshot_id) ON DELETE RESTRICT,
    previous_snapshot_id uuid REFERENCES information_source_snapshots(snapshot_id) ON DELETE RESTRICT,
    error_summary text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (status IN ('SUCCESS','SUCCESS_ZERO','BASELINE_CREATED','SOURCE_UNAVAILABLE','HTTP_FAILED','PARSE_FAILED','CONTRACT_CHANGED','DIFF_FAILED')),
    CHECK (http_status IS NULL OR http_status BETWEEN 100 AND 599),
    CHECK (raw_byte_size >= 0)
);

CREATE TABLE information_change_events (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id text NOT NULL REFERENCES information_sources(source_id) ON DELETE RESTRICT,
    previous_snapshot_id uuid NOT NULL REFERENCES information_source_snapshots(snapshot_id) ON DELETE RESTRICT,
    current_snapshot_id uuid NOT NULL REFERENCES information_source_snapshots(snapshot_id) ON DELETE RESTRICT,
    classification text NOT NULL,
    changed_contract_paths jsonb NOT NULL,
    affected_components jsonb NOT NULL,
    severity text NOT NULL,
    requires_action boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id,previous_snapshot_id,current_snapshot_id),
    CHECK (previous_snapshot_id <> current_snapshot_id),
    CHECK (classification IN ('NON_BREAKING','BREAKING','REVIEW','INFO_ONLY')),
    CHECK (severity IN ('INFO','WATCH','ACTION_REQUIRED','CRITICAL'))
);

CREATE INDEX idx_information_checks_source_time ON information_source_checks (source_id,checked_at DESC);
CREATE INDEX idx_information_snapshots_source_time ON information_source_snapshots (source_id,retrieved_at DESC);
CREATE INDEX idx_information_events_source_time ON information_change_events (source_id,created_at DESC);
