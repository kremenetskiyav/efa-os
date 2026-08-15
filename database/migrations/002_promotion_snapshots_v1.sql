-- Apply manually only after a successful authenticated dry-run confirms payload fields.
-- Immutable, idempotent promotion participation snapshots; no existing Phase A table changes.
CREATE TABLE promotion_snapshots (
  id bigserial PRIMARY KEY,
  snapshot_at timestamptz NOT NULL,
  action_id bigint NOT NULL,
  action_title text,
  action_type text,
  action_start_at timestamptz,
  action_end_at timestamptz,
  participation_status text NOT NULL,
  product_id bigint,
  offer_id text,
  current_price numeric,
  action_price numeric,
  min_price numeric,
  source_kind text NOT NULL,
  source_identifier text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (snapshot_at, action_id, product_id, offer_id, participation_status, source_kind, source_identifier)
);
CREATE INDEX promotion_snapshots_offer_snapshot_idx ON promotion_snapshots (offer_id, snapshot_at DESC);
