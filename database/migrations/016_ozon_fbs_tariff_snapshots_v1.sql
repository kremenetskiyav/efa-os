-- Immutable observations from Ozon POST /v5/product/info/prices.
-- This table is observation history, NOT change-only history.
-- Phase 2B will insert one row per product on every successful price collection
-- run, even when the observed tariff values have not changed.
CREATE TABLE ozon_fbs_tariff_snapshots (
    snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    price_collection_run_id uuid NOT NULL
        REFERENCES price_collection_runs(run_id) ON DELETE RESTRICT,
    product_id bigint NOT NULL,
    offer_id text NOT NULL REFERENCES products(offer_id) ON DELETE RESTRICT,
    observed_at timestamptz NOT NULL,
    sales_percent_fbs numeric NOT NULL
        CHECK (sales_percent_fbs >= 0 AND sales_percent_fbs <= 100),
    fbs_deliv_to_customer_amount numeric NOT NULL
        CHECK (fbs_deliv_to_customer_amount >= 0),
    acquiring numeric CHECK (acquiring IS NULL OR acquiring >= 0),
    fbs_direct_flow_trans_min_amount numeric
        CHECK (
            fbs_direct_flow_trans_min_amount IS NULL
            OR fbs_direct_flow_trans_min_amount >= 0
        ),
    fbs_direct_flow_trans_max_amount numeric
        CHECK (
            fbs_direct_flow_trans_max_amount IS NULL
            OR fbs_direct_flow_trans_max_amount >= 0
        ),
    fbs_return_flow_amount numeric
        CHECK (fbs_return_flow_amount IS NULL OR fbs_return_flow_amount >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (price_collection_run_id, product_id),
    CHECK (
        fbs_direct_flow_trans_min_amount IS NULL
        OR fbs_direct_flow_trans_max_amount IS NULL
        OR fbs_direct_flow_trans_min_amount <= fbs_direct_flow_trans_max_amount
    )
);

COMMENT ON TABLE ozon_fbs_tariff_snapshots IS
    'Immutable FBS tariff observation history from Ozon product price runs; one row per product and successful run, including unchanged observations.';

COMMENT ON COLUMN ozon_fbs_tariff_snapshots.sales_percent_fbs IS
    'Raw base FBS commission percentage from Ozon; no EFA adjustment is applied.';

COMMENT ON COLUMN ozon_fbs_tariff_snapshots.acquiring IS
    'Diagnostic raw monetary acquiring value from Ozon; not the Calculator V1 forecast acquiring rate.';

CREATE INDEX ozon_fbs_tariff_snapshots_product_observed_idx
    ON ozon_fbs_tariff_snapshots (product_id, observed_at DESC);
