-- Competitor Monitor Data Layer v1.
--
-- This migration creates the isolated competitor-data contour only. It does
-- not seed OEMs or listings, alter existing product/snapshot tables, create
-- collectors, or add automated price actions.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $$
BEGIN
    IF to_regclass('public.products') IS NULL THEN
        RAISE EXCEPTION 'Required table public.products is missing';
    END IF;

    IF to_regprocedure('gen_random_uuid()') IS NULL THEN
        RAISE EXCEPTION 'Required function gen_random_uuid() is missing';
    END IF;
END $$;

CREATE TABLE public.competitor_sku_profiles (
    offer_id text NOT NULL,
    reference_length_mm numeric(10, 3),
    reference_width_mm numeric(10, 3),
    reference_height_mm numeric(10, 3),
    dimensions_source text,
    dimensions_status text,
    verification_status text NOT NULL,
    watchlist_state text NOT NULL,
    quality_flags text[] NOT NULL DEFAULT ARRAY[]::text[],
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_sku_profiles_pkey PRIMARY KEY (offer_id),
    CONSTRAINT competitor_sku_profiles_offer_id_fkey FOREIGN KEY (offer_id)
        REFERENCES public.products (offer_id) ON DELETE RESTRICT,
    CONSTRAINT competitor_sku_profiles_dimensions_check CHECK (
        (reference_length_mm IS NULL OR reference_length_mm > 0)
        AND (reference_width_mm IS NULL OR reference_width_mm > 0)
        AND (reference_height_mm IS NULL OR reference_height_mm > 0)
    ),
    CONSTRAINT competitor_sku_profiles_verification_status_check CHECK (
        btrim(verification_status) <> ''
    ),
    CONSTRAINT competitor_sku_profiles_watchlist_state_check CHECK (
        watchlist_state IN ('ACTIVE', 'HOLD', 'DISABLED')
    ),
    CONSTRAINT competitor_sku_profiles_quality_flags_check CHECK (
        array_position(quality_flags, NULL) IS NULL
    ),
    CONSTRAINT competitor_sku_profiles_timestamps_check CHECK (
        updated_at >= created_at
    )
);

COMMENT ON TABLE public.competitor_sku_profiles IS
    'Per-EFA-SKU monitoring configuration; dimensions and verification conflicts remain explicit.';

CREATE TABLE public.competitor_sku_oems (
    sku_oem_id uuid NOT NULL DEFAULT gen_random_uuid(),
    offer_id text NOT NULL,
    oem_raw text NOT NULL,
    oem_normalized text NOT NULL,
    confidence text NOT NULL,
    source_ref text NOT NULL,
    is_primary boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_sku_oems_pkey PRIMARY KEY (sku_oem_id),
    CONSTRAINT competitor_sku_oems_offer_id_fkey FOREIGN KEY (offer_id)
        REFERENCES public.products (offer_id) ON DELETE RESTRICT,
    CONSTRAINT competitor_sku_oems_offer_normalized_key UNIQUE (
        offer_id,
        oem_normalized
    ),
    CONSTRAINT competitor_sku_oems_offer_sku_oem_key UNIQUE (
        offer_id,
        sku_oem_id
    ),
    CONSTRAINT competitor_sku_oems_values_check CHECK (
        btrim(oem_raw) <> ''
        AND btrim(oem_normalized) <> ''
        AND btrim(source_ref) <> ''
    ),
    CONSTRAINT competitor_sku_oems_confidence_check CHECK (
        confidence IN ('HIGH', 'MEDIUM', 'LOW', 'MISMATCH')
    )
);

COMMENT ON TABLE public.competitor_sku_oems IS
    'Confirmed EFA OEM registry with source spelling and separately stored normalized form.';

CREATE INDEX competitor_sku_oems_normalized_idx
    ON public.competitor_sku_oems (oem_normalized);

CREATE TABLE public.competitor_product_families (
    product_family_id uuid NOT NULL DEFAULT gen_random_uuid(),
    brand_raw text,
    brand_normalized text,
    part_number_raw text,
    part_number_normalized text,
    product_name text NOT NULL,
    carbon_confidence text NOT NULL,
    verification_status text NOT NULL,
    quality_flags text[] NOT NULL DEFAULT ARRAY[]::text[],
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_product_families_pkey PRIMARY KEY (product_family_id),
    CONSTRAINT competitor_product_families_values_check CHECK (
        btrim(product_name) <> ''
        AND btrim(verification_status) <> ''
        AND (brand_normalized IS NULL OR btrim(brand_normalized) <> '')
        AND (
            part_number_normalized IS NULL
            OR btrim(part_number_normalized) <> ''
        )
    ),
    CONSTRAINT competitor_product_families_carbon_confidence_check CHECK (
        carbon_confidence IN (
            'CONFIRMED',
            'PROBABLE',
            'NON_CARBON',
            'UNKNOWN'
        )
    ),
    CONSTRAINT competitor_product_families_quality_flags_check CHECK (
        array_position(quality_flags, NULL) IS NULL
    ),
    CONSTRAINT competitor_product_families_timestamps_check CHECK (
        updated_at >= created_at
    )
);

COMMENT ON TABLE public.competitor_product_families IS
    'Competitor product identity independent from OEM values and individual Ozon listings.';

CREATE TABLE public.competitor_listings (
    listing_id uuid NOT NULL DEFAULT gen_random_uuid(),
    product_family_id uuid NOT NULL,
    ozon_product_id bigint NOT NULL,
    seller_key text NOT NULL,
    seller_id text,
    seller_name text,
    listing_url text,
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    lifecycle_status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_listings_pkey PRIMARY KEY (listing_id),
    CONSTRAINT competitor_listings_product_family_id_fkey
        FOREIGN KEY (product_family_id)
        REFERENCES public.competitor_product_families (product_family_id)
        ON DELETE RESTRICT,
    CONSTRAINT competitor_listings_product_seller_key UNIQUE (
        ozon_product_id,
        seller_key
    ),
    CONSTRAINT competitor_listings_values_check CHECK (
        ozon_product_id > 0
        AND btrim(seller_key) <> ''
        AND btrim(lifecycle_status) <> ''
        AND (listing_url IS NULL OR btrim(listing_url) <> '')
    ),
    CONSTRAINT competitor_listings_timestamps_check CHECK (
        last_seen_at >= first_seen_at
        AND updated_at >= created_at
    )
);

COMMENT ON TABLE public.competitor_listings IS
    'One concrete Ozon product-and-seller listing; seller_key may be a stable v1 fallback.';

CREATE TABLE public.competitor_watchlist_memberships (
    membership_id uuid NOT NULL DEFAULT gen_random_uuid(),
    offer_id text NOT NULL,
    listing_id uuid NOT NULL,
    membership_status text NOT NULL,
    matched_oem_set text[] NOT NULL DEFAULT ARRAY[]::text[],
    oem_confidence text NOT NULL,
    decision_reason text NOT NULL,
    quality_flags text[] NOT NULL DEFAULT ARRAY[]::text[],
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_watchlist_memberships_pkey PRIMARY KEY (membership_id),
    CONSTRAINT competitor_watchlist_memberships_offer_id_fkey
        FOREIGN KEY (offer_id)
        REFERENCES public.products (offer_id) ON DELETE RESTRICT,
    CONSTRAINT competitor_watchlist_memberships_listing_id_fkey
        FOREIGN KEY (listing_id)
        REFERENCES public.competitor_listings (listing_id) ON DELETE RESTRICT,
    CONSTRAINT competitor_watchlist_memberships_status_check CHECK (
        membership_status IN ('PRIMARY', 'RESERVE', 'EXCLUDE', 'CONTROL')
    ),
    CONSTRAINT competitor_watchlist_memberships_oem_confidence_check CHECK (
        oem_confidence IN ('HIGH', 'MEDIUM', 'LOW', 'MISMATCH')
    ),
    CONSTRAINT competitor_watchlist_memberships_values_check CHECK (
        btrim(decision_reason) <> ''
        AND array_position(matched_oem_set, NULL) IS NULL
        AND array_position(quality_flags, NULL) IS NULL
    ),
    CONSTRAINT competitor_watchlist_memberships_validity_check CHECK (
        valid_to IS NULL OR valid_to >= valid_from
    )
);

COMMENT ON TABLE public.competitor_watchlist_memberships IS
    'Historical EFA SKU-to-listing watchlist decisions; closed memberships are retained.';

CREATE UNIQUE INDEX competitor_watchlist_one_active_pair_uidx
    ON public.competitor_watchlist_memberships (offer_id, listing_id)
    WHERE valid_to IS NULL;

CREATE INDEX competitor_watchlist_active_status_idx
    ON public.competitor_watchlist_memberships (
        offer_id,
        membership_status
    )
    WHERE valid_to IS NULL;

CREATE TABLE public.competitor_search_runs (
    search_run_id uuid NOT NULL DEFAULT gen_random_uuid(),
    offer_id text NOT NULL,
    sku_oem_id uuid,
    query_kind text NOT NULL,
    query_text_exact text NOT NULL,
    query_normalized text NOT NULL,
    region_key text NOT NULL,
    location_label text,
    captured_at timestamptz NOT NULL,
    status text NOT NULL,
    page_count_observed integer,
    result_count_observed integer,
    collection_ref text NOT NULL,
    raw_source_ref text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_search_runs_pkey PRIMARY KEY (search_run_id),
    CONSTRAINT competitor_search_runs_offer_id_fkey FOREIGN KEY (offer_id)
        REFERENCES public.products (offer_id) ON DELETE RESTRICT,
    CONSTRAINT competitor_search_runs_offer_sku_oem_fkey
        FOREIGN KEY (offer_id, sku_oem_id)
        REFERENCES public.competitor_sku_oems (offer_id, sku_oem_id)
        ON DELETE RESTRICT,
    CONSTRAINT competitor_search_runs_collection_ref_key UNIQUE (collection_ref),
    CONSTRAINT competitor_search_runs_query_kind_check CHECK (
        query_kind IN ('OEM', 'MARKET', 'SCOUT')
    ),
    CONSTRAINT competitor_search_runs_values_check CHECK (
        btrim(query_text_exact) <> ''
        AND btrim(query_normalized) <> ''
        AND btrim(region_key) <> ''
        AND btrim(status) <> ''
        AND btrim(collection_ref) <> ''
        AND (location_label IS NULL OR btrim(location_label) <> '')
        AND (raw_source_ref IS NULL OR btrim(raw_source_ref) <> '')
    ),
    CONSTRAINT competitor_search_runs_counts_check CHECK (
        (page_count_observed IS NULL OR page_count_observed >= 0)
        AND (result_count_observed IS NULL OR result_count_observed >= 0)
    )
);

COMMENT ON TABLE public.competitor_search_runs IS
    'One captured execution of one exact competitor search query and location context.';

CREATE INDEX competitor_search_history_idx
    ON public.competitor_search_runs (
        offer_id,
        query_normalized,
        region_key,
        captured_at DESC
    );

CREATE TABLE public.competitor_observations (
    observation_id uuid NOT NULL DEFAULT gen_random_uuid(),
    search_run_id uuid NOT NULL,
    listing_id uuid NOT NULL,
    membership_id uuid,
    captured_at timestamptz NOT NULL,
    page_number integer,
    position_on_page integer,
    rank integer,
    ad_flag boolean,
    bank_price numeric(14, 2),
    other_payment_price numeric(14, 2),
    old_price numeric(14, 2),
    currency text,
    rating numeric(3, 2),
    reviews_count_observed integer,
    reviews_scope text NOT NULL,
    purchase_count_observed integer,
    purchase_indicator_raw text,
    availability_status text NOT NULL,
    availability_raw text,
    observed_oem_raw text,
    observed_dimensions_raw text,
    observed_length_mm numeric(10, 3),
    observed_width_mm numeric(10, 3),
    observed_height_mm numeric(10, 3),
    carbon_claim_raw text,
    origin_raw text,
    quality_status text NOT NULL,
    quality_flags text[] NOT NULL DEFAULT ARRAY[]::text[],
    source_ref text NOT NULL,
    raw_ref text,
    observation_ref text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_observations_pkey PRIMARY KEY (observation_id),
    CONSTRAINT competitor_observations_search_run_id_fkey
        FOREIGN KEY (search_run_id)
        REFERENCES public.competitor_search_runs (search_run_id)
        ON DELETE RESTRICT,
    CONSTRAINT competitor_observations_listing_id_fkey
        FOREIGN KEY (listing_id)
        REFERENCES public.competitor_listings (listing_id) ON DELETE RESTRICT,
    CONSTRAINT competitor_observations_membership_id_fkey
        FOREIGN KEY (membership_id)
        REFERENCES public.competitor_watchlist_memberships (membership_id)
        ON DELETE RESTRICT,
    CONSTRAINT competitor_observations_observation_ref_key UNIQUE (
        observation_ref
    ),
    CONSTRAINT competitor_observations_position_check CHECK (
        (page_number IS NULL OR page_number > 0)
        AND (position_on_page IS NULL OR position_on_page > 0)
        AND (rank IS NULL OR rank > 0)
    ),
    CONSTRAINT competitor_observations_prices_check CHECK (
        (bank_price IS NULL OR bank_price >= 0)
        AND (other_payment_price IS NULL OR other_payment_price >= 0)
        AND (old_price IS NULL OR old_price >= 0)
        AND (currency IS NULL OR btrim(currency) <> '')
        AND (
            (bank_price IS NULL AND other_payment_price IS NULL AND old_price IS NULL)
            OR currency IS NOT NULL
        )
    ),
    CONSTRAINT competitor_observations_rating_count_check CHECK (
        (rating IS NULL OR rating BETWEEN 0 AND 5)
        AND (
            reviews_count_observed IS NULL
            OR reviews_count_observed >= 0
        )
        AND (
            purchase_count_observed IS NULL
            OR purchase_count_observed >= 0
        )
    ),
    CONSTRAINT competitor_observations_reviews_scope_check CHECK (
        reviews_scope IN ('LISTING', 'PRODUCT_FAMILY', 'UNKNOWN')
    ),
    CONSTRAINT competitor_observations_dimensions_check CHECK (
        (observed_length_mm IS NULL OR observed_length_mm > 0)
        AND (observed_width_mm IS NULL OR observed_width_mm > 0)
        AND (observed_height_mm IS NULL OR observed_height_mm > 0)
    ),
    CONSTRAINT competitor_observations_values_check CHECK (
        btrim(availability_status) <> ''
        AND btrim(quality_status) <> ''
        AND btrim(source_ref) <> ''
        AND btrim(observation_ref) <> ''
        AND (raw_ref IS NULL OR btrim(raw_ref) <> '')
        AND array_position(quality_flags, NULL) IS NULL
    )
);

COMMENT ON TABLE public.competitor_observations IS
    'Append-only factual competitor observations; unknown facts are NULL/UNKNOWN and comparison_price is deliberately absent.';

CREATE UNIQUE INDEX competitor_observations_run_position_uidx
    ON public.competitor_observations (
        search_run_id,
        page_number,
        position_on_page
    )
    WHERE page_number IS NOT NULL AND position_on_page IS NOT NULL;

CREATE INDEX competitor_observations_search_rank_idx
    ON public.competitor_observations (search_run_id, rank);

CREATE INDEX competitor_observations_listing_history_idx
    ON public.competitor_observations (listing_id, captured_at DESC);

CREATE TABLE public.competitor_reviews (
    review_id uuid NOT NULL DEFAULT gen_random_uuid(),
    listing_id uuid NOT NULL,
    source_review_id text,
    published_at timestamptz,
    rating numeric(2, 1),
    text text,
    pros text,
    cons text,
    author_marker text,
    reviews_scope text NOT NULL,
    dedupe_key text NOT NULL,
    fingerprint text NOT NULL,
    quality_flags text[] NOT NULL DEFAULT ARRAY[]::text[],
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_reviews_pkey PRIMARY KEY (review_id),
    CONSTRAINT competitor_reviews_listing_id_fkey FOREIGN KEY (listing_id)
        REFERENCES public.competitor_listings (listing_id) ON DELETE RESTRICT,
    CONSTRAINT competitor_reviews_dedupe_key_key UNIQUE (dedupe_key),
    CONSTRAINT competitor_reviews_scope_check CHECK (
        reviews_scope IN ('LISTING', 'PRODUCT_FAMILY', 'UNKNOWN')
    ),
    CONSTRAINT competitor_reviews_values_check CHECK (
        (source_review_id IS NULL OR btrim(source_review_id) <> '')
        AND (rating IS NULL OR rating BETWEEN 1 AND 5)
        AND btrim(dedupe_key) <> ''
        AND btrim(fingerprint) <> ''
        AND array_position(quality_flags, NULL) IS NULL
    ),
    CONSTRAINT competitor_reviews_timestamps_check CHECK (
        last_seen_at >= first_seen_at
    )
);

COMMENT ON TABLE public.competitor_reviews IS
    'Deduplicated listing reviews with only a non-personal author marker when available.';

CREATE INDEX competitor_reviews_listing_published_idx
    ON public.competitor_reviews (listing_id, published_at DESC);

CREATE TABLE public.competitor_findings (
    finding_id uuid NOT NULL DEFAULT gen_random_uuid(),
    finding_kind text NOT NULL,
    offer_id text NOT NULL,
    product_family_id uuid,
    listing_id uuid,
    old_observation_id uuid,
    new_observation_id uuid,
    topic text NOT NULL,
    metric text NOT NULL,
    severity text NOT NULL,
    confidence text NOT NULL,
    status text NOT NULL,
    evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    finding_key text NOT NULL,
    first_detected_at timestamptz NOT NULL,
    last_detected_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitor_findings_pkey PRIMARY KEY (finding_id),
    CONSTRAINT competitor_findings_offer_id_fkey FOREIGN KEY (offer_id)
        REFERENCES public.products (offer_id) ON DELETE RESTRICT,
    CONSTRAINT competitor_findings_product_family_id_fkey
        FOREIGN KEY (product_family_id)
        REFERENCES public.competitor_product_families (product_family_id)
        ON DELETE RESTRICT,
    CONSTRAINT competitor_findings_listing_id_fkey FOREIGN KEY (listing_id)
        REFERENCES public.competitor_listings (listing_id) ON DELETE RESTRICT,
    CONSTRAINT competitor_findings_old_observation_id_fkey
        FOREIGN KEY (old_observation_id)
        REFERENCES public.competitor_observations (observation_id)
        ON DELETE RESTRICT,
    CONSTRAINT competitor_findings_new_observation_id_fkey
        FOREIGN KEY (new_observation_id)
        REFERENCES public.competitor_observations (observation_id)
        ON DELETE RESTRICT,
    CONSTRAINT competitor_findings_finding_key_key UNIQUE (finding_key),
    CONSTRAINT competitor_findings_kind_check CHECK (
        finding_kind IN ('ISSUE', 'SIGNAL')
    ),
    CONSTRAINT competitor_findings_values_check CHECK (
        btrim(topic) <> ''
        AND btrim(metric) <> ''
        AND btrim(severity) <> ''
        AND btrim(confidence) <> ''
        AND btrim(status) <> ''
        AND btrim(finding_key) <> ''
        AND jsonb_typeof(evidence) = 'array'
        AND jsonb_typeof(details) = 'object'
    ),
    CONSTRAINT competitor_findings_observations_check CHECK (
        old_observation_id IS NULL
        OR new_observation_id IS NULL
        OR old_observation_id <> new_observation_id
    ),
    CONSTRAINT competitor_findings_timestamps_check CHECK (
        last_detected_at >= first_detected_at
        AND updated_at >= created_at
    )
);

COMMENT ON TABLE public.competitor_findings IS
    'Persisted Competitor Monitor issues and signals with structured evidence and provenance links.';

CREATE INDEX competitor_findings_offer_kind_status_last_idx
    ON public.competitor_findings (
        offer_id,
        finding_kind,
        status,
        last_detected_at DESC
    );

COMMIT;
