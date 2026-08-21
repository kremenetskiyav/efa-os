\set ON_ERROR_STOP on

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

ALTER TABLE public.postings
    ADD COLUMN in_process_at timestamptz;

ALTER TABLE public.finance_operations
    ADD COLUMN order_date timestamp without time zone,
    ADD COLUMN services_json jsonb;

COMMENT ON COLUMN public.postings.in_process_at IS
    'Ozon FBS posting lifecycle timestamp from postings[].in_process_at; nullable for legacy rows.';

COMMENT ON COLUMN public.finance_operations.order_date IS
    'Ozon finance posting order_date as supplied without timezone; nullable for legacy rows.';

COMMENT ON COLUMN public.finance_operations.services_json IS
    'Full Ozon finance operation services array; nullable for legacy rows.';

COMMIT;
