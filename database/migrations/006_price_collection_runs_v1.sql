CREATE TABLE price_collection_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_ref text NOT NULL UNIQUE,
    collected_at timestamptz NOT NULL,
    status text NOT NULL,
    products_count integer NOT NULL DEFAULT 0,
    changed_records integer NOT NULL DEFAULT 0,
    unchanged_records integer NOT NULL DEFAULT 0,
    unmapped_products integer NOT NULL DEFAULT 0,
    data_quality_status text NOT NULL,
    error_summary text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (status IN ('running', 'success', 'failed')),
    CHECK (products_count >= 0 AND changed_records >= 0 AND unchanged_records >= 0 AND unmapped_products >= 0),
    CHECK (data_quality_status IN ('valid', 'review', 'invalid'))
);

CREATE INDEX idx_price_collection_runs_collected_at
    ON price_collection_runs (collected_at DESC);
