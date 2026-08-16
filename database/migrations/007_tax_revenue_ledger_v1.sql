CREATE TABLE tax_revenue_import_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document text NOT NULL,
    source_reference text NOT NULL UNIQUE,
    source_checksum text NOT NULL UNIQUE,
    source_period text NOT NULL UNIQUE,
    status text NOT NULL,
    events_count integer NOT NULL DEFAULT 0,
    accounting_income numeric NOT NULL DEFAULT 0,
    data_quality_status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (source_period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    CHECK (status IN ('running','success')),
    CHECK (events_count >= 0),
    CHECK (data_quality_status IN ('valid','partial','invalid'))
);

CREATE TABLE tax_revenue_events (
    event_id text PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES tax_revenue_import_runs(run_id) ON DELETE RESTRICT,
    tax_year integer NOT NULL,
    source_period text NOT NULL,
    event_type text NOT NULL,
    posting_number text,
    offer_id text REFERENCES products(offer_id) ON DELETE RESTRICT,
    sku bigint,
    event_date date,
    amount numeric NOT NULL,
    source_document text NOT NULL,
    source_reference text NOT NULL,
    tax_semantics_status text NOT NULL,
    tax_date_status text NOT NULL,
    data_quality_status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (tax_year BETWEEN 2000 AND 9999),
    CHECK (source_period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    CHECK (event_type IN ('REALIZATION','PARTNER_LOYALTY_PAYMENT','RETURN','PARTNER_LOYALTY_REVERSAL','CORRECTION')),
    CHECK (tax_semantics_status IN ('CONFIRMED','PARTIAL','UNKNOWN')),
    CHECK (tax_date_status IN ('CONFIRMED','PERIOD_ONLY','UNKNOWN')),
    CHECK (data_quality_status IN ('valid','partial','invalid')),
    CHECK ((tax_date_status = 'CONFIRMED' AND event_date IS NOT NULL) OR tax_date_status <> 'CONFIRMED')
);

CREATE UNIQUE INDEX uq_tax_revenue_event_logical
    ON tax_revenue_events (source_reference,event_type,COALESCE(posting_number,''),COALESCE(offer_id,''),COALESCE(sku,0),COALESCE(event_date,DATE '0001-01-01'),amount);
CREATE INDEX idx_tax_revenue_events_period ON tax_revenue_events (tax_year,source_period);
CREATE INDEX idx_tax_revenue_events_offer_date ON tax_revenue_events (offer_id,event_date) WHERE offer_id IS NOT NULL;
