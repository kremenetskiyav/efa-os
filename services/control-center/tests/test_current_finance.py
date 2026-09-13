import copy
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import current_finance as cf
import finance_model as fm
from finance_source import McpFinanceSource, SourceUnavailable, NoRedirect
import test_finance_model

NOW = datetime(2026, 9, 12, 18, tzinfo=timezone.utc)


def fixture():
    products = [{'offer_id': offer, 'sku': 100+i, 'cost_price': '166',
                 'cost_basis': 'CURRENT_NOT_HISTORISED'} for i, offer in enumerate(cf.SKU_MAP)]
    daily = []
    for product in products:
        daily.append({'offer_id': product['offer_id'], 'business_date': '2026-09-11',
                      'ordered_units': 2, 'ordered_revenue': '100', 'demand_quality_status': 'valid',
                      'demand_collected_at': '2026-09-12T04:10:00Z', 'delivered_units': 1,
                      'returned_units': 0, 'postings_collection_status': 'SUCCESS',
                      'postings_collected_at': '2026-09-12T02:40:00Z',
                      'returns_collection_status': 'SUCCESS', 'returns_collected_at': '2026-09-12T02:40:01Z',
                      'finance_collection_status': 'FAILED', 'finance_collected_at': '2026-09-12T02:40:20Z',
                      'confirmed_revenue': '999999', 'profit_before_tax': '999999', 'buyer_price': '999999'})
    return {'products': products, 'daily': daily, 'cpc': [], 'errors': {}, 'transport': 'TEST'}


def period(key='yesterday', now=NOW):
    return next(p for p in fm.period_options(now) if p['id'] == key)


class CurrentFinanceTests(unittest.TestCase):
    def test_contract_returns_portfolio_all_five_mapped_skus_and_all_fields(self):
        snap = cf.live_snapshot(period(), fixture(), NOW)
        self.assertEqual('efa_finance_snapshot_v1', snap['schema_version'])
        self.assertEqual(5, len(snap['skus']))
        for entity in [snap['portfolio'], *snap['skus']]:
            self.assertTrue(set(cf.FIELDS).issubset(entity))
            self.assertEqual('2026-09-11', entity['period_start'])
            self.assertEqual('2026-09-11', entity['period_end'])
            self.assertFalse(entity['complete_costs'])
        self.assertEqual(list(cf.SKU_MAP), [s['efa_sku'] for s in snap['skus']])
        self.assertTrue(all(s['ozon_sku'] is not None for s in snap['skus']))

    def test_buyer_price_and_daily_financial_fields_are_never_realization(self):
        snap = cf.live_snapshot(period(), fixture(), NOW)
        for entity in [snap['portfolio'], *snap['skus']]:
            for field in ('seller_realization', 'delivered_revenue', 'profit_rub', 'contribution_rub', 'cogs'):
                self.assertIsNone(entity[field])
        self.assertEqual('500', snap['portfolio']['ordered_revenue'])

    def test_missing_row_is_not_zero_or_partial_total(self):
        data = fixture()
        data['daily'].pop()
        snap = cf.live_snapshot(period(), data, NOW)
        self.assertIsNone(snap['portfolio']['ordered_units'])
        self.assertIsNone(snap['skus'][-1]['ordered_units'])
        self.assertEqual('NO_DATA', snap['portfolio']['field_metadata']['ordered_units']['freshness'])
        self.assertEqual('8', snap['portfolio']['field_metadata']['ordered_units']['observed_subtotal'])
        self.assertEqual('INSUFFICIENT_DATA', snap['reconciliation']['status'])

    def test_duplicate_and_unconfirmed_rows_invalidate_complete_period(self):
        for mutate in ('duplicate', 'missing_quality', 'nan', 'future'):
            data = fixture()
            if mutate == 'duplicate': data['daily'].append(copy.deepcopy(data['daily'][0]))
            elif mutate == 'missing_quality': data['daily'][0]['demand_quality_status'] = None
            elif mutate == 'nan': data['daily'][0]['ordered_units'] = 'NaN'
            else: data['daily'][0]['demand_collected_at'] = '2026-10-01T00:00:00Z'
            snap = cf.live_snapshot(period(), data, NOW)
            self.assertIsNone(snap['portfolio']['ordered_units'], mutate)

    def test_confirmed_zero_survives_without_finance_zero(self):
        data = fixture()
        for row in data['daily']: row['ordered_units'] = row['ordered_revenue'] = 0
        snap = cf.live_snapshot(period(), data, NOW)
        self.assertEqual('0', snap['portfolio']['ordered_units'])
        self.assertIsNone(snap['portfolio']['profit_rub'])
        self.assertIsNone(snap['portfolio']['advertising_total'])

    def test_moscow_boundaries_and_partial_day(self):
        now = datetime(2026, 9, 30, 22, tzinfo=timezone.utc)
        p = period('today', now)
        self.assertEqual('2026-10-01', p['from'])
        for key in ('today', 'last30'):
            snap = cf.live_snapshot(period(key, now), fixture(), now)
            self.assertEqual('PARTIAL_DAY', snap['portfolio']['settlement_status'])
        for key in ('yesterday', 'last7', 'this_month'):
            self.assertEqual('PROVISIONAL', cf.live_snapshot(
                period(key, now), fixture(), now)['portfolio']['settlement_status'])

    def test_sku_sum_reconciles_and_detects_changes(self):
        snap = cf.live_snapshot(period(), fixture(), NOW)
        rows = {r['field']: r for r in snap['reconciliation']['fields']}
        self.assertEqual('PASS', rows['ordered_revenue']['status'])
        self.assertEqual('0', rows['ordered_revenue']['gap'])
        snap['portfolio']['ordered_revenue'] = '505'
        rows = {r['field']: r for r in cf.reconciliation(snap['portfolio'], snap['skus'])['fields']}
        self.assertEqual('5', rows['ordered_revenue']['gap'])

    def test_reconciliation_rejects_different_period_or_cohort(self):
        for mismatch in ('period', 'cohort', 'mode'):
            snap = cf.live_snapshot(period(), fixture(), NOW)
            if mismatch == 'period':
                snap['skus'][0]['period_end'] = '2026-09-10'
            else:
                snap['skus'][0]['field_metadata']['ordered_revenue'][mismatch] = 'different'
            rows = {r['field']: r for r in cf.reconciliation(snap['portfolio'], snap['skus'])['fields']}
            self.assertIsNone(rows['ordered_revenue']['gap'])
            self.assertEqual('INCOMPARABLE_BASIS', rows['ordered_revenue']['reason'])

    def test_contribution_is_not_profit_and_every_required_cost_is_gated(self):
        for missing in cf.REQUIRED_COSTS:
            entity = cf.blank_entity(period(), 'test', NOW)
            entity.update(mode='SETTLEMENT_AWARE', settlement_status='FINAL_SETTLEMENT',
                          complete_costs=True, cost_completeness=dict.fromkeys(cf.REQUIRED_COSTS, True),
                          contribution_rub='100', profit_rub='80', profit_pct='8')
            entity['cost_completeness'][missing] = False
            cf.enforce_profit(entity)
            self.assertIsNone(entity['profit_rub'], missing)
            self.assertIsNone(entity['profit_pct'])
            self.assertEqual('100', entity['contribution_rub'])

    def test_campaign_spend_remains_evidence_not_settlement(self):
        data = fixture()
        data['cpc'] = [{'business_date': '2026-09-11', 'data_scope': 'ACCOUNT', 'offer_id': None,
                        'spend': '200', 'collection_status': 'SUCCESS_NONZERO',
                        'data_quality_status': 'valid', 'observed_at': '2026-09-12T04:35:00Z'}]
        snap = cf.live_snapshot(period(), data, NOW)
        self.assertEqual('200', snap['metadata']['campaign_metrics']['rows'][0]['spend'])
        self.assertIsNone(snap['portfolio']['advertising_cpc'])
        self.assertTrue(all(s['advertising_total'] is None for s in snap['skus']))

    def test_freshness_uses_success_not_recent_failed_attempt(self):
        rows = [{'state': 'SUCCESS', 'at': '2026-09-08T02:40:00Z'},
                {'state': 'FAILED', 'at': '2026-09-12T02:40:00Z'}]
        value = cf.health(rows, 'state', 'at', NOW)
        self.assertEqual('STALE', value['status'])
        self.assertEqual('2026-09-08T02:40:00+00:00', value['observed_at'])
        self.assertEqual('FAILED', value['last_attempt_status'])
        for hours, expected in ((20, 'FRESH'), (27, 'DELAYED'), (51, 'STALE')):
            self.assertEqual(expected, cf.freshness((NOW-timedelta(hours=hours)).isoformat(), NOW))
        self.assertEqual('NO_DATA', cf.freshness(None, NOW))

    def test_outage_returns_contract_without_august_substitution(self):
        class Broken:
            def fetch(self, start, end): raise RuntimeError('sensitive DSN must not escape')
        service = cf.FinanceService(factory=Broken)
        with tempfile.TemporaryDirectory() as directory:
            finance = cf.attach_legacy(fm.build_finance(Path(directory), NOW), NOW, service)
        self.assertEqual('this_month', finance['default_period'])
        self.assertFalse(finance['views']['this_month']['available'])
        self.assertEqual(5, len(finance['snapshots']['CURRENT_MONTH']['skus']))
        self.assertNotIn('sensitive', json.dumps(finance))

    def test_cached_response_is_isolated_and_expiration_does_not_serve_old_values(self):
        class Source:
            def __init__(self): self.fail = False; self.calls = 0
            def fetch(self, start, end):
                self.calls += 1
                if self.fail: raise SourceUnavailable('MCP_UNAVAILABLE')
                return fixture()
        source = Source()
        service = cf.FinanceService(factory=lambda: source)
        options = fm.period_options(NOW)
        first = service.source_data(options, NOW)
        first['daily'].clear()
        self.assertEqual(5, len(service.source_data(options, NOW)['daily']))
        self.assertEqual(1, source.calls)
        service.cached_at -= 61
        source.fail = True
        self.assertEqual([], service.source_data(options, NOW)['daily'])

    def test_august_only_explicit_preset_and_account_costs_not_allocated(self):
        helper = test_finance_model.FinanceTests()
        helper.setUp()
        try:
            helper.fixture_report()
            class Source:
                def fetch(self, start, end): return fixture()
            finance = cf.attach_legacy(fm.build_finance(helper.root, NOW), NOW, cf.FinanceService(factory=Source))
            historical = finance['snapshots']['AUGUST_2026']
            self.assertEqual('17484.01', historical['portfolio']['contribution_rub'])
            self.assertIsNone(historical['portfolio']['profit_rub'])
            self.assertEqual('-1097.23', historical['reconciliation']['reconciliation_gap_rub'])
            self.assertEqual('1058.18', historical['reconciliation']['gap_reasons'][0]['amount_rub'])
            self.assertEqual('39.05', historical['reconciliation']['gap_reasons'][1]['amount_rub'])
            self.assertEqual('1901.18', historical['portfolio']['advertising_cpc'])
            self.assertEqual('129', historical['portfolio']['advertising_cpo'])
            self.assertTrue(all(s['advertising_cpo'] is None for s in historical['skus']))
            for preset, snap in finance['snapshots'].items():
                if preset != 'AUGUST_2026': self.assertIsNone(snap['portfolio']['contribution_rub'])
            self.assertFalse(finance['views']['previous_month']['available'])
        finally: helper.tearDown()

    def test_finance_api_is_get_only_validates_period_and_degrades_gracefully(self):
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict('os.environ', {'EFA_FINANCE_SOURCE': 'disabled'}):
                base = f'http://127.0.0.1:{server.server_port}/api/finance'
                with urllib.request.urlopen(base+'?period=TODAY', timeout=4) as response:
                    data = json.load(response)
                self.assertEqual('efa_finance_snapshot_v1', data['schema_version'])
                self.assertEqual(5, len(data['skus']))
                for suffix in ('?period=ALL', '?period=TODAY&period=YESTERDAY', '?sql=SELECT'):
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(base+suffix, timeout=4)
                    self.assertEqual(400, caught.exception.code)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(urllib.request.Request(base, data=b'{}', method='POST'), timeout=4)
                self.assertEqual(501, caught.exception.code)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)


class SourceTests(unittest.TestCase):
    def test_credentials_never_redirect_and_endpoint_is_pinned(self):
        with self.assertRaises(SourceUnavailable):
            McpFinanceSource(token='test-only', url='https://other.invalid/mcp')
        with self.assertRaises(SourceUnavailable):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')

    def test_transport_is_only_fixed_analytics_reads_and_masked_errors(self):
        captured = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return json.dumps({'result': {'structuredContent': {
                'columns': ['offer_id'], 'rows': [], 'row_count': 0, 'truncated': False}}}).encode()
        class Opener:
            def open(self, request, timeout): captured.append(request); return Response()
        source = McpFinanceSource(token='test-only', opener=Opener())
        result = source.fetch(datetime(2026, 9, 1).date(), datetime(2026, 9, 12).date())
        self.assertEqual({}, result['errors'])
        self.assertEqual(3, len(captured))
        for request in captured:
            body = json.loads(request.data)
            self.assertEqual('query_analytics', body['params']['name'])
            self.assertTrue(body['params']['arguments']['query'].startswith('SELECT '))
            self.assertNotIn('profit_before_tax', body['params']['arguments']['query'])


if __name__ == '__main__': unittest.main()
