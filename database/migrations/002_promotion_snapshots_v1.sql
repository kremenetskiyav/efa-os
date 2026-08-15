-- Unapplied Promotions Persistence Contract v0.1.
CREATE TABLE promotion_runs (
  run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  collection_ref text NOT NULL UNIQUE,
  collected_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status IN ('running','success','failed')),
  actions_count integer NOT NULL DEFAULT 0 CHECK (actions_count >= 0),
  participating_records integer NOT NULL DEFAULT 0 CHECK (participating_records >= 0),
  candidate_records integer NOT NULL DEFAULT 0 CHECK (candidate_records >= 0),
  unique_product_ids integer NOT NULL DEFAULT 0 CHECK (unique_product_ids >= 0),
  mapped_offer_ids integer NOT NULL DEFAULT 0 CHECK (mapped_offer_ids >= 0),
  unmapped_product_ids integer NOT NULL DEFAULT 0 CHECK (unmapped_product_ids >= 0),
  mapping_status text NOT NULL CHECK (mapping_status IN ('valid','partial','invalid')),
  error_summary text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE promotion_snapshots (
  snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES promotion_runs(run_id) ON DELETE RESTRICT,
  action_id bigint NOT NULL,
  action_title text,
  action_type text,
  action_start_at timestamptz,
  action_end_at timestamptz,
  source_list_type text NOT NULL CHECK (source_list_type IN ('PARTICIPATING','CANDIDATE')),
  product_id bigint NOT NULL,
  offer_id text REFERENCES products(offer_id) ON DELETE RESTRICT,
  add_mode text,
  price numeric CHECK (price IS NULL OR price >= 0),
  action_price numeric CHECK (action_price IS NULL OR action_price >= 0),
  max_action_price numeric CHECK (max_action_price IS NULL OR max_action_price >= 0),
  data_quality_status text NOT NULL CHECK (data_quality_status IN ('valid','review','invalid')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (run_id, action_id, source_list_type, product_id)
);
CREATE INDEX promotion_runs_collected_at_idx ON promotion_runs (collected_at DESC);
CREATE INDEX promotion_snapshots_offer_created_idx ON promotion_snapshots (offer_id, created_at DESC);
CREATE INDEX promotion_snapshots_action_source_idx ON promotion_snapshots (action_id, source_list_type);
CREATE INDEX promotion_snapshots_run_idx ON promotion_snapshots (run_id);
