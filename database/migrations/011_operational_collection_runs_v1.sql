CREATE TABLE operational_collection_runs (
    source TEXT NOT NULL,
    business_date DATE NOT NULL,
    collection_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    window_from TIMESTAMPTZ NOT NULL,
    window_to TIMESTAMPTZ NOT NULL,
    pages_count INTEGER NOT NULL DEFAULT 0,
    records_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT operational_collection_runs_pkey
        PRIMARY KEY (source, business_date),
    CONSTRAINT operational_collection_runs_source_check
        CHECK (source IN ('POSTINGS', 'RETURNS', 'FINANCE')),
    CONSTRAINT operational_collection_runs_status_check
        CHECK (status IN ('SUCCESS', 'SUCCESS_ZERO', 'FAILED')),
    CONSTRAINT operational_collection_runs_counts_check
        CHECK (pages_count >= 0 AND records_count >= 0),
    CONSTRAINT operational_collection_runs_success_error_check
        CHECK (
            (status = 'FAILED' AND error_message IS NOT NULL)
            OR
            (status IN ('SUCCESS', 'SUCCESS_ZERO') AND error_message IS NULL)
        ),
    CONSTRAINT operational_collection_runs_zero_check
        CHECK (status <> 'SUCCESS_ZERO' OR records_count = 0),
    CONSTRAINT operational_collection_runs_window_check
        CHECK (window_to > window_from)
);

CREATE INDEX operational_collection_runs_freshness_idx
    ON operational_collection_runs (source, business_date DESC, completed_at DESC)
    WHERE status IN ('SUCCESS', 'SUCCESS_ZERO');
