CREATE TABLE cpc_collection_runs (
  run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  collection_ref text NOT NULL UNIQUE,
  collected_at timestamptz NOT NULL,
  business_date date NOT NULL,
  report_uuid uuid NOT NULL,
  status text NOT NULL CHECK (status IN ('running','success')),
  campaigns_count integer NOT NULL DEFAULT 0 CHECK (campaigns_count >= 0),
  records_count integer NOT NULL DEFAULT 0 CHECK (records_count >= 0),
  mapped_offer_ids integer NOT NULL DEFAULT 0 CHECK (mapped_offer_ids >= 0),
  unmapped_skus integer NOT NULL DEFAULT 0 CHECK (unmapped_skus >= 0),
  mapping_status text NOT NULL CHECK (mapping_status IN ('valid','partial','invalid')),
  source text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cpc_advertising_daily (
  cpc_daily_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES cpc_collection_runs(run_id) ON DELETE RESTRICT,
  business_date date NOT NULL,
  campaign_id bigint NOT NULL,
  campaign_state text,
  campaign_type text,
  sku bigint NOT NULL,
  offer_id text REFERENCES products(offer_id) ON DELETE RESTRICT,
  views integer NOT NULL CHECK (views >= 0),
  clicks integer NOT NULL CHECK (clicks >= 0),
  ctr numeric NOT NULL CHECK (ctr >= 0),
  avg_bid numeric NOT NULL CHECK (avg_bid >= 0),
  money_spent numeric NOT NULL CHECK (money_spent >= 0),
  orders integer NOT NULL CHECK (orders >= 0),
  orders_money numeric NOT NULL CHECK (orders_money >= 0),
  drr numeric NOT NULL CHECK (drr >= 0),
  general_drr numeric NOT NULL CHECK (general_drr >= 0),
  product_gmv numeric NOT NULL CHECK (product_gmv >= 0),
  price numeric NOT NULL CHECK (price >= 0),
  report_uuid uuid NOT NULL,
  source text NOT NULL,
  data_quality_status text NOT NULL CHECK (data_quality_status IN ('valid','review','invalid')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (business_date, campaign_id, sku)
);

CREATE INDEX cpc_collection_runs_date_idx
  ON cpc_collection_runs (business_date DESC, collected_at DESC);
CREATE INDEX cpc_daily_offer_date_idx
  ON cpc_advertising_daily (offer_id, business_date DESC);
CREATE INDEX cpc_daily_campaign_date_idx
  ON cpc_advertising_daily (campaign_id, business_date DESC);
CREATE INDEX cpc_daily_run_idx ON cpc_advertising_daily (run_id);
