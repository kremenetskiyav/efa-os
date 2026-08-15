CREATE TABLE seller_product_demand_daily (
  demand_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  collection_ref text NOT NULL,
  offer_id text NOT NULL REFERENCES products(offer_id) ON DELETE RESTRICT,
  sku bigint NOT NULL,
  business_date date NOT NULL,
  ordered_revenue numeric NOT NULL CHECK (ordered_revenue >= 0),
  ordered_units integer NOT NULL CHECK (ordered_units >= 0),
  collected_at timestamptz NOT NULL,
  source text NOT NULL,
  data_quality_status text NOT NULL CHECK (data_quality_status IN ('valid','review','invalid')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (offer_id, business_date)
);

CREATE INDEX seller_product_demand_offer_date_idx
  ON seller_product_demand_daily (offer_id, business_date DESC);
CREATE INDEX seller_product_demand_sku_date_idx
  ON seller_product_demand_daily (sku, business_date DESC);
