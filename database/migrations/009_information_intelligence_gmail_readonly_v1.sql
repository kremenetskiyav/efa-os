-- Prepared only. Apply only after backup and explicit owner approval.
-- Narrowly extends the applied v0.1 Information Intelligence contract for Gmail evidence.
ALTER TABLE information_sources
    DROP CONSTRAINT information_sources_retrieval_method_check,
    ADD CHECK (retrieval_method IN (
        'PUBLIC_HTTP', 'MANUAL_BOOTSTRAP', 'PUBLIC_HTTP_OR_MANUAL_BOOTSTRAP',
        'MANUAL_EVIDENCE', 'GMAIL_READ_ONLY'
    ));

ALTER TABLE information_change_events
    DROP CONSTRAINT information_change_events_event_kind_check,
    ADD CHECK (event_kind IN (
        'API_CONTRACT_CHANGE', 'LEGAL_DOCUMENT_CHANGE', 'NEWS_EVENT',
        'MANUAL_EVIDENCE', 'EMAIL_EVENT'
    ));
