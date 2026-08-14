-- Snapshot Layer v1
-- Architecture references:
--   docs/architecture/SNAPSHOT_LAYER_V1.md
--   docs/architecture/SNAPSHOT_LAYER_DDL_DESIGN_V1.md
--
-- This migration creates only Snapshot Layer v1 tables and indexes.
-- It does not alter existing tables, views, or n8n workflows.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS snapshot_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key text NOT NULL,
    run_type text NOT NULL,
    business_date date NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    status text NOT NULL,
    source_watermark timestamptz,
    products_expected integer,
    products_snapshotted integer NOT NULL DEFAULT 0,
    products_invalid integer NOT NULL DEFAULT 0,
    trigger_reference text,
    error_summary text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT snapshot_runs_idempotency_key_key UNIQUE (idempotency_key),
    CONSTRAINT snapshot_runs_run_type_check CHECK (run_type = 'daily'),
    CONSTRAINT snapshot_runs_status_check CHECK (
        status IN ('running', 'success', 'partial', 'failed')
    ),
    CONSTRAINT snapshot_runs_counts_check CHECK (
        COALESCE(products_expected, 0) >= 0
        AND products_snapshotted >= 0
        AND products_invalid >= 0
    ),
    CONSTRAINT snapshot_runs_completed_after_started_check CHECK (
        completed_at IS NULL OR completed_at >= started_at
    ),
    CONSTRAINT snapshot_runs_success_completed_check CHECK (
        status <> 'success' OR completed_at IS NOT NULL
    )
);

COMMENT ON TABLE snapshot_runs IS
    'Audit record for one Snapshot Layer daily collection attempt after OZON Phase A.';
COMMENT ON COLUMN snapshot_runs.idempotency_key IS
    'Deterministic key preventing duplicate processing of the same logical n8n run.';
COMMENT ON COLUMN snapshot_runs.business_date IS
    'Operational date calculated in Europe/Moscow.';
COMMENT ON COLUMN snapshot_runs.source_watermark IS
    'Latest source timestamp included in this run.';
COMMENT ON COLUMN snapshot_runs.status IS
    'Run state: running, success, partial, or failed.';

CREATE INDEX IF NOT EXISTS idx_snapshot_runs_business_date_status
    ON snapshot_runs (business_date DESC, status);
CREATE INDEX IF NOT EXISTS idx_snapshot_runs_trigger_reference
    ON snapshot_runs (trigger_reference)
    WHERE trigger_reference IS NOT NULL;

CREATE TABLE IF NOT EXISTS product_snapshots (
    snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL,
    offer_id text NOT NULL,
    snapshot_at timestamptz NOT NULL,
    business_date date NOT NULL,
    current_price numeric(14, 2),
    price_updated_from_ozon timestamptz,
    cost_price_used numeric(14, 2),
    fbo_stock integer,
    fbs_stock integer,
    rfbs_stock integer,
    reserved_stock integer,
    source_name text NOT NULL,
    data_quality_status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT product_snapshots_run_offer_key UNIQUE (run_id, offer_id),
    CONSTRAINT product_snapshots_run_id_fkey FOREIGN KEY (run_id)
        REFERENCES snapshot_runs (run_id) ON DELETE RESTRICT,
    CONSTRAINT product_snapshots_offer_id_fkey FOREIGN KEY (offer_id)
        REFERENCES products (offer_id) ON DELETE RESTRICT,
    CONSTRAINT product_snapshots_quality_check CHECK (
        data_quality_status IN ('valid', 'partial', 'invalid')
    ),
    CONSTRAINT product_snapshots_source_check CHECK (
        source_name = 'ozon_phase_a'
    ),
    CONSTRAINT product_snapshots_nonnegative_price_check CHECK (
        current_price IS NULL OR current_price >= 0
    ),
    CONSTRAINT product_snapshots_nonnegative_stock_check CHECK (
        (fbo_stock IS NULL OR fbo_stock >= 0)
        AND (fbs_stock IS NULL OR fbs_stock >= 0)
        AND (rfbs_stock IS NULL OR rfbs_stock >= 0)
        AND (reserved_stock IS NULL OR reserved_stock >= 0)
    ),
    CONSTRAINT product_snapshots_valid_price_check CHECK (
        data_quality_status <> 'valid'
        OR (current_price IS NOT NULL AND price_updated_from_ozon IS NOT NULL)
    )
);

COMMENT ON TABLE product_snapshots IS
    'Immutable per-product state captured by one Snapshot Layer run.';
COMMENT ON COLUMN product_snapshots.run_id IS
    'Snapshot run that produced this immutable state.';
COMMENT ON COLUMN product_snapshots.offer_id IS
    'Canonical product identifier from products.offer_id.';
COMMENT ON COLUMN product_snapshots.snapshot_at IS
    'UTC timestamp when the Snapshot Layer state was captured.';
COMMENT ON COLUMN product_snapshots.business_date IS
    'Operational date calculated in Europe/Moscow.';
COMMENT ON COLUMN product_snapshots.current_price IS
    'Latest valid price from ozon_price_history.price.';
COMMENT ON COLUMN product_snapshots.price_updated_from_ozon IS
    'UTC timestamp of the source price point in Ozon.';
COMMENT ON COLUMN product_snapshots.data_quality_status IS
    'Source data quality: valid, partial, or invalid.';

CREATE INDEX IF NOT EXISTS idx_product_snapshots_offer_snapshot_at
    ON product_snapshots (offer_id, snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_product_snapshots_business_date_quality
    ON product_snapshots (business_date, data_quality_status);

CREATE TABLE IF NOT EXISTS change_events (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type text NOT NULL,
    offer_id text NOT NULL,
    detected_at timestamptz NOT NULL DEFAULT now(),
    business_date date NOT NULL,
    old_snapshot_id uuid NOT NULL,
    new_snapshot_id uuid NOT NULL,
    metric text NOT NULL,
    old_value numeric(14, 2) NOT NULL,
    new_value numeric(14, 2) NOT NULL,
    absolute_change numeric(14, 2) NOT NULL,
    change_percent numeric(10, 4),
    severity text NOT NULL,
    rule_id text NOT NULL,
    idempotency_key text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'new',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT change_events_idempotency_key_key UNIQUE (idempotency_key),
    CONSTRAINT change_events_offer_id_fkey FOREIGN KEY (offer_id)
        REFERENCES products (offer_id) ON DELETE RESTRICT,
    CONSTRAINT change_events_old_snapshot_id_fkey FOREIGN KEY (old_snapshot_id)
        REFERENCES product_snapshots (snapshot_id) ON DELETE RESTRICT,
    CONSTRAINT change_events_new_snapshot_id_fkey FOREIGN KEY (new_snapshot_id)
        REFERENCES product_snapshots (snapshot_id) ON DELETE RESTRICT,
    CONSTRAINT change_events_type_metric_check CHECK (
        event_type = 'PRICE_CHANGED' AND metric = 'current_price'
    ),
    CONSTRAINT change_events_distinct_snapshots_check CHECK (
        old_snapshot_id <> new_snapshot_id
    ),
    CONSTRAINT change_events_nonnegative_values_check CHECK (
        old_value >= 0 AND new_value >= 0
    ),
    CONSTRAINT change_events_severity_check CHECK (
        severity IN ('low', 'medium', 'high', 'critical')
    ),
    CONSTRAINT change_events_status_check CHECK (
        status IN ('new', 'analyzed', 'acknowledged', 'ignored')
    )
);

COMMENT ON TABLE change_events IS
    'Immutable detected change between two product snapshots; v1 supports PRICE_CHANGED only.';
COMMENT ON COLUMN change_events.old_snapshot_id IS
    'Previous valid snapshot used as the comparison baseline.';
COMMENT ON COLUMN change_events.new_snapshot_id IS
    'New valid snapshot that triggered the event.';
COMMENT ON COLUMN change_events.idempotency_key IS
    'Deterministic key preventing duplicate events for the same snapshots and rule.';
COMMENT ON COLUMN change_events.parameters IS
    'Rule thresholds, source watermark, and non-authoritative event context.';

CREATE INDEX IF NOT EXISTS idx_change_events_offer_detected_at
    ON change_events (offer_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_events_status_detected_at
    ON change_events (status, detected_at);
CREATE INDEX IF NOT EXISTS idx_change_events_new_snapshot_id
    ON change_events (new_snapshot_id);
