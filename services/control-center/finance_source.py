"""LEGACY_UNUSED in Control Center: retained fixed MCP diagnostic queries.

Active finance reads W06 structured snapshots. No caller SQL/credential persistence.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

MCP_URL = 'https://mcp.efa-os.ru/mcp'
DAILY_FIELDS = (
    'offer_id,business_date,ordered_units,ordered_revenue,demand_collected_at,'
    'demand_quality_status,delivered_units,returned_units,postings_collection_status,'
    'postings_collected_at,returns_collection_status,returns_collected_at,'
    'finance_collection_status,finance_collected_at'
)


class SourceUnavailable(Exception):
    """Safe, non-sensitive error category only."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceUnavailable('MCP_REDIRECT_REJECTED')


class McpFinanceSource:
    def __init__(self, token=None, url=None, opener=None):
        self.token = token if token is not None else os.getenv('EFA_MCP_BEARER_TOKEN')
        self.url = url or os.getenv('EFA_FINANCE_MCP_URL', MCP_URL)
        if self.url != MCP_URL:
            raise SourceUnavailable('UNAPPROVED_MCP_ENDPOINT')
        if not self.token:
            raise SourceUnavailable('MCP_CREDENTIAL_UNAVAILABLE')
        self.opener = opener or build_opener(NoRedirect())

    def query(self, sql):
        payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'query_analytics',
                              'arguments': {'query': sql, 'max_rows': 500}}}
        request = Request(self.url, data=json.dumps(payload).encode(), method='POST',
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Content-Type': 'application/json',
                                   'Accept': 'application/json, text/event-stream'})
        try:
            with self.opener.open(request, timeout=8) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise SourceUnavailable('MCP_RESPONSE_TOO_LARGE')
            envelope = json.loads(raw)
            result = envelope.get('result', {})
            if envelope.get('error') or result.get('isError'):
                raise SourceUnavailable('MCP_READ_FAILED')
            data = result.get('structuredContent')
            if data is None:
                data = json.loads(next(c['text'] for c in result['content'] if c['type'] == 'text'))
            columns, rows = data['columns'], data['rows']
            if (data.get('truncated') is not False or data['row_count'] != len(rows)
                    or len(rows) > 500 or len(set(columns)) != len(columns)
                    or not all(isinstance(c, str) for c in columns)
                    or not all(isinstance(r, list) and len(r) == len(columns) for r in rows)):
                raise SourceUnavailable('MCP_INCOMPLETE_RESPONSE')
            return [dict(zip(columns, row)) for row in rows]
        except SourceUnavailable:
            raise
        except HTTPError as exc:
            raise SourceUnavailable('MCP_AUTH_REJECTED' if exc.code in (401, 403) else 'MCP_HTTP_FAILED') from None
        except Exception:
            raise SourceUnavailable('MCP_UNAVAILABLE') from None

    def fetch(self, start: date, end: date):
        # Bounds are dates derived by the application, never interpolated user SQL.
        if not isinstance(start, date) or not isinstance(end, date) or not 0 <= (end-start).days <= 62:
            raise SourceUnavailable('INVALID_SOURCE_WINDOW')
        bounds = f"business_date BETWEEN '{start.isoformat()}'::date AND '{end.isoformat()}'::date"
        queries = {
            'products': 'SELECT offer_id,sku,cost_price,cost_basis,product_observed_at '
                        'FROM mcp_read.product_overview ORDER BY offer_id',
            'daily': f'SELECT {DAILY_FIELDS} FROM mcp_read.product_daily_performance '
                     f'WHERE {bounds} ORDER BY business_date,offer_id',
            'cpc': 'SELECT business_date,data_scope,offer_id,spend,collection_status,'
                   f'data_quality_status,observed_at FROM mcp_read.product_cpc_daily WHERE {bounds} '
                   'ORDER BY business_date,data_scope,offer_id',
        }
        data, errors = {}, {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {key: executor.submit(self.query, sql) for key, sql in queries.items()}
            for key, future in futures.items():
                try:
                    data[key] = future.result()
                except SourceUnavailable as exc:
                    data[key] = []
                    errors[key] = str(exc)
        return {**data, 'errors': errors, 'transport': 'EFA_READ_MCP_HTTPS'}
