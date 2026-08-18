CREATE TABLE commercial_experiments (
    experiment_id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL REFERENCES products(offer_id) ON DELETE RESTRICT,
    experiment_type TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    target_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    unit_limit INTEGER,
    duration_limit_days INTEGER,
    loss_limit NUMERIC(14,2),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT commercial_experiments_status_check
        CHECK (status IN ('PLANNED', 'ACTIVE', 'PAUSED', 'COMPLETED', 'STOPPED', 'CANCELLED')),
    CONSTRAINT commercial_experiments_config_check
        CHECK (jsonb_typeof(target_config) = 'object'),
    CONSTRAINT commercial_experiments_limits_check
        CHECK (
            (unit_limit IS NULL OR unit_limit > 0)
            AND (duration_limit_days IS NULL OR duration_limit_days > 0)
            AND (loss_limit IS NULL OR loss_limit >= 0)
        ),
    CONSTRAINT commercial_experiments_dates_check
        CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX commercial_experiments_offer_status_idx
    ON commercial_experiments (offer_id, status, created_at DESC);

INSERT INTO commercial_experiments (
    experiment_id,
    offer_id,
    experiment_type,
    status,
    started_at,
    ended_at,
    target_config,
    unit_limit,
    duration_limit_days,
    loss_limit,
    notes
) VALUES (
    'FBS-UF004B-4118344-V0.1',
    'УФ 004Б',
    'OZON_ACTION_FBS',
    'ACTIVE',
    NULL,
    NULL,
    '{
      "action_id": "4118344",
      "action_title": "Акция для товаров со схемой FBS",
      "seller_price_rub": 899,
      "action_ui_price_rub": 865,
      "elastic_boost_pct": 15,
      "elastic_boost_intentionally_changed": false,
      "cpc_enabled": false
    }'::jsonb,
    5,
    5,
    500.00,
    'Exact experiment start timestamp was not durably recorded; started_at is intentionally NULL and performance attribution is unavailable.'
);
