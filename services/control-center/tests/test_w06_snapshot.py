import copy
import json
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import finance_model as fm
import w06_snapshot as w06

NOW = datetime(2026, 9, 13, 7, tzinfo=timezone.utc)


class W06SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.period = next(p for p in fm.period_options(NOW) if p['id'] == 'this_month')
        self.doc = w06.empty(self.period, NOW, 'INSUFFICIENT_DATA')

    def observed(self):
        doc = copy.deepcopy(self.doc)
        doc.update(source_status='AVAILABLE', financial_mode='OBSERVED', warnings=[])
        doc['freshness'] = {'status': 'FRESH', 'observed_at': NOW.isoformat(),
                            'valid_until': (NOW+timedelta(hours=2)).isoformat()}
        doc['evidence'] = [{'source': 'W06/verified-report.md',
                            'source_timestamp': NOW.isoformat(),
                            'confirmation': 'TEST_VERIFIED',
                            'limitation': 'test fixture'}]
        doc['portfolio']['seller_realization'] = '987.65'
        doc['portfolio']['contribution_rub'] = '123.45'
        for field in ('seller_realization', 'contribution_rub'):
            doc['portfolio']['field_metadata'][field] = {
                'source': 'W06/verified-report.md', 'semantic': field,
                'source_timestamp': NOW.isoformat(), 'confidence': 'MEDIUM',
                'financial_mode': 'OBSERVED',
                'basis': 'SELLER_REALIZATION' if field == 'seller_realization' else 'W06_REPORTED'}
        for row in doc['reconciliation']['fields']:
            row['portfolio'] = doc['portfolio'][row['field']]
        return doc

    def test_missing_is_not_zero_and_has_five_identities(self):
        snap = w06.build(self.root, NOW)['snapshots']['CURRENT_MONTH']
        self.assertEqual('MISSING', snap['metadata']['load_status'])
        self.assertEqual(w06.MESSAGES['MISSING'], snap['metadata']['message'])
        self.assertEqual(set(w06.IDENTITIES.values()), {s['ozon_sku'] for s in snap['skus']})
        self.assertTrue(all(snap['portfolio'][f] is None for f in w06.FIELDS))

    def test_reader_copies_w06_values_and_never_computes_profit(self):
        doc = self.observed()
        w06.publish(self.root, doc, NOW)
        result = w06.build(self.root, NOW)
        snap = result['snapshots']['CURRENT_MONTH']
        self.assertEqual('987.65', snap['portfolio']['seller_realization'])
        self.assertEqual('123.45', snap['portfolio']['contribution_rub'])
        self.assertIsNone(snap['portfolio']['profit_rub'])
        self.assertEqual(doc['reconciliation'], snap['reconciliation'])
        self.assertEqual('123.45', result['views']['this_month']['portfolio']['contribution']['value'])
        self.assertIsNone(result['views']['this_month']['portfolio']['settlement_profit']['value'])

    def test_stale_keeps_provenance_and_requests_w06_refresh(self):
        w06.publish(self.root, self.observed(), NOW)
        snap = w06.build(self.root, NOW+timedelta(hours=3))['snapshots']['CURRENT_MONTH']
        self.assertEqual('STALE', snap['metadata']['load_status'])
        self.assertEqual(w06.MESSAGES['STALE'], snap['metadata']['message'])
        self.assertTrue(snap['provider_check']['refresh_required'])
        self.assertEqual(NOW.isoformat(), snap['freshness']['observed_at'])

    def test_sku_order_cannot_swap_financial_values(self):
        doc = self.observed()
        first = doc['skus'][0]
        first['ordered_units'] = '7'
        first['field_metadata']['ordered_units'] = {
            'semantic': 'ordered_units', 'source': 'W06/verified-report.md',
            'source_timestamp': NOW.isoformat(), 'confidence': 'MEDIUM',
            'financial_mode': 'OBSERVED'}
        doc['skus'].reverse()
        w06.publish(self.root, doc, NOW)
        rows = w06.build(self.root, NOW)['views']['this_month']['skus']
        self.assertEqual('UF001', rows[0]['sku'])
        self.assertEqual('7', rows[0]['metrics']['ordered_units']['value'])
        self.assertIsNone(rows[-1]['metrics']['ordered_units']['value'])

    def test_rolling_period_does_not_relabel_yesterdays_amount(self):
        w06.publish(self.root, self.observed(), NOW)
        snap = w06.build(self.root, NOW+timedelta(days=1))['snapshots']['CURRENT_MONTH']
        self.assertEqual('STALE', snap['metadata']['load_status'])
        self.assertIsNone(snap['portfolio']['seller_realization'])

    def test_buyer_price_and_unclosed_profit_rejected(self):
        doc = self.observed()
        doc['portfolio']['field_metadata']['seller_realization']['basis'] = 'BUYER_PRICE'
        with self.assertRaisesRegex(ValueError, 'BUYER_PRICE'):
            w06.validate(doc, NOW)
        doc = self.observed()
        doc['portfolio']['profit_rub'] = '123.45'
        doc['portfolio']['field_metadata']['profit_rub'] = {
            'source': 'W06/verified-report.md', 'semantic': 'profit_rub',
            'source_timestamp': NOW.isoformat(), 'confidence': 'MEDIUM',
            'financial_mode': 'OBSERVED'}
        with self.assertRaisesRegex(ValueError, 'UNCONFIRMED_PROFIT'):
            w06.validate(doc, NOW)

    def test_presentation_cannot_override_realization(self):
        doc = self.observed()
        doc['portfolio']['presentation_metrics'] = {'seller_realization': {'value': '100'}}
        with self.assertRaisesRegex(ValueError, 'PRESENTATION_OVERRIDE'):
            w06.validate(doc, NOW)

    def test_invalid_and_future_snapshot_fail_closed(self):
        path = w06.directory(self.root) / 'CURRENT_FINANCE_SNAPSHOT_V1.json'
        path.parent.mkdir(parents=True)
        for content in ('{broken', json.dumps({**self.doc, 'generated_at': (NOW+timedelta(days=1)).isoformat()})):
            path.write_text(content, encoding='utf-8')
            snap = w06.build(self.root, NOW)['snapshots']['CURRENT_MONTH']
            self.assertEqual('INVALID', snap['metadata']['load_status'])
            self.assertIsNone(snap['portfolio']['seller_realization'])

    def test_duplicate_skus_and_nan_rejected(self):
        doc = copy.deepcopy(self.doc)
        doc['skus'][0] = doc['skus'][1]
        with self.assertRaisesRegex(ValueError, 'FIVE_SKUS'):
            w06.validate(doc, NOW)
        doc = self.observed()
        doc['portfolio']['seller_realization'] = 'NaN'
        with self.assertRaisesRegex(ValueError, 'NONFINITE'):
            w06.validate(doc, NOW)

    def test_no_network_database_legacy_collector_or_old_brief_in_status(self):
        with patch.object(app, 'OZON_AGENTS_ROOT', self.root), \
             patch.object(app, 'read_database', side_effect=AssertionError('DB forbidden')), \
             patch.object(app, '_tcp_online', side_effect=AssertionError('TCP forbidden')), \
             patch.object(app, 'delivery_configuration', side_effect=AssertionError('n8n forbidden')), \
             patch.object(app, 'collector_snapshot', side_effect=AssertionError('collector forbidden')), \
             patch.object(app, 'report_snapshot', side_effect=AssertionError('old report forbidden')):
            result = app.build_status()
        self.assertNotIn('n8n', result['system'])
        self.assertNotIn('collectors_ok', result['system'])
        self.assertEqual([], result['collectors'])
        self.assertEqual('LEGACY_UNUSED', result['legacy_systems']['classification'])

    def test_snapshot_source_get_is_allowlisted_and_post_is_rejected(self):
        path = w06.publish(self.root, self.doc, NOW)
        relative = path.relative_to(self.root).as_posix()
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(app, 'OZON_AGENTS_ROOT', self.root):
                base = f'http://127.0.0.1:{server.server_port}/agent-source?path='
                # Use a controlled model clock: source allowlist is the real provider.
                with patch.object(app.read_model, 'build', return_value={'sources': [relative]}):
                    with urllib.request.urlopen(base+relative, timeout=3) as response:
                        self.assertEqual(w06.SCHEMA, json.load(response)['schema'])
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(base+'CONTROL_CENTER_STATE.json', timeout=3)
                    self.assertEqual(404, error.exception.code)
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(urllib.request.Request(base+relative, data=b'{}', method='POST'), timeout=3)
                    self.assertEqual(501, error.exception.code)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_all_seven_periods_no_august_substitution(self):
        period = next(p for p in fm.period_options(NOW) if p['id'] == 'august2026')
        doc = w06.empty(period, NOW)
        doc['freshness']['status'] = 'HISTORICAL_REFERENCE'
        with self.assertRaisesRegex(ValueError, 'HISTORICAL_CANNOT'):
            w06.publish(self.root, doc, NOW)
        w06.publish(self.root, doc, NOW, current=False)
        result = w06.build(self.root, NOW)
        self.assertEqual(7, len(result['snapshots']))
        self.assertEqual('HISTORICAL_REFERENCE', result['snapshots']['AUGUST_2026']['metadata']['load_status'])
        for preset, snap in result['snapshots'].items():
            if preset != 'AUGUST_2026':
                self.assertEqual('MISSING', snap['metadata']['load_status'])

    def test_rolling_finance_periods_exclude_unfinished_today(self):
        periods = {item['id']: item for item in fm.period_options(NOW)}
        self.assertEqual(('2026-09-06', '2026-09-12'),
                         (periods['last7']['from'], periods['last7']['to']))
        self.assertEqual(('2026-09-01', '2026-09-12'),
                         (periods['this_month']['from'], periods['this_month']['to']))

    def test_dated_publication_is_immutable_and_idempotent(self):
        path = w06.publish(self.root, self.doc, NOW, current=False)
        self.assertEqual(path, w06.publish(self.root, self.doc, NOW, current=False))
        self.doc['warnings'].append('another result')
        with self.assertRaisesRegex(ValueError, 'DATED_SNAPSHOT_CONFLICT'):
            w06.publish(self.root, self.doc, NOW, current=False)

    def test_w07_rejects_reconciliation_that_disagrees_with_values(self):
        doc = self.observed()
        doc['reconciliation']['fields'][0]['portfolio'] = '1'
        with self.assertRaisesRegex(ValueError, 'RECONCILIATION_PORTFOLIO_MISMATCH'):
            w06.audit(doc, NOW)
        for row in doc['reconciliation']['fields']:
            row['portfolio'] = doc['portfolio'][row['field']]
        self.assertEqual('FRESH', w06.audit(doc, NOW)['freshness'])
        self.assertEqual('STALE', w06.audit(doc, NOW+timedelta(hours=3))['freshness'])

    def partial_semantic(self):
        doc = copy.deepcopy(self.doc)
        doc.update(source_status='PARTIAL', financial_mode='MIXED_OBSERVED_PROXY',
                   warnings=['INSUFFICIENT_SETTLEMENT_DATA'])
        source_a, source_b, source_c = 'EFA_READ_MCP', 'OZON_UNIT_ECONOMICS', 'OZON_ACCRUALS'
        doc['evidence'] = [
            {'source': source, 'source_timestamp': NOW.isoformat(),
             'confirmation': 'TEST_VERIFIED', 'limitation': 'fixture'}
            for source in (source_a, source_b, source_c)]
        doc['layers'] = {
            'demand': {'source_status': 'AVAILABLE', 'financial_mode': 'OBSERVED',
                       'freshness': 'UNKNOWN', 'confidence': 'HIGH',
                       'date_basis': 'SELLER_ANALYTICS_DAY',
                       'cohort_basis': 'RAW_ORDERED_DEMAND', 'source': source_a},
            'operational_economics': {
                'source_status': 'PARTIAL', 'financial_mode': 'OBSERVED',
                'freshness': 'UNKNOWN', 'confidence': 'MEDIUM',
                'date_basis': 'ORDER_CREATED_PERIOD', 'cohort_basis': 'ORDER_COHORT',
                'source': source_b},
            'account_finance': {'source_status': 'AVAILABLE', 'financial_mode': 'OBSERVED',
                                'freshness': 'UNKNOWN', 'confidence': 'HIGH',
                                'date_basis': 'ACCRUAL_DATE', 'cohort_basis': 'ACCOUNT',
                                'source': source_c},
            'cost': {'source_status': 'PARTIAL', 'financial_mode': 'SELLER_SIDE_PROXY',
                     'freshness': 'UNKNOWN', 'confidence': 'LOW',
                     'date_basis': 'CURRENT_VALUE', 'cohort_basis': 'CURRENT_COGS_PROXY',
                     'source': source_b},
            'settlement': {'source_status': 'INSUFFICIENT_DATA',
                           'financial_mode': 'INSUFFICIENT_DATA', 'freshness': 'NO_DATA',
                           'confidence': 'UNKNOWN', 'date_basis': None,
                           'cohort_basis': 'FINAL_NOT_AVAILABLE', 'source': None},
        }
        doc['source_comparisons'] = [{
            'metric': 'УФ 002Б:ordered_units', 'source_a': source_a, 'value_a': '1',
            'basis_a': {'metric_definition': 'ORDERED_DEMAND', 'date_basis': 'DAY',
                        'cohort_basis': 'RAW', 'lifecycle_state': 'PROVISIONAL'},
            'source_b': source_b, 'value_b': '0',
            'basis_b': {'metric_definition': 'ELIGIBLE_ORDER', 'date_basis': 'ORDER_DATE',
                        'cohort_basis': 'UNIT_ECONOMICS', 'lifecycle_state': 'PROVISIONAL'},
            'classification': 'UNRESOLVED_BUT_SEMANTICALLY_EXPLAINABLE',
            'unresolved_reason': 'status timing unavailable'}]
        return doc

    def test_semantic_difference_is_partial_valid_and_publishable(self):
        doc = self.partial_semantic()
        self.assertEqual('PARTIAL_VALID', w06.audit(doc, NOW)['audit_result'])
        self.assertTrue(w06.publish(self.root, doc, NOW).is_file())

    def test_incomplete_demand_keeps_independent_layers_publishable(self):
        doc = self.partial_semantic()
        doc['layers']['demand'].update(
            source_status='INCOMPLETE', financial_mode='INSUFFICIENT_DATA',
            confidence='UNKNOWN')
        doc['layers']['operational_economics']['source_status'] = 'AVAILABLE'
        for entity in [doc['portfolio'], *doc['skus']]:
            for field in ('ordered_units', 'ordered_revenue'):
                entity[field] = None
                entity['field_metadata'][field] = {
                    'semantic': field, 'source': 'EFA_READ_MCP',
                    'source_timestamp': NOW.isoformat(), 'confidence': 'UNKNOWN',
                    'financial_mode': 'INSUFFICIENT_DATA',
                    'missing_reason': 'EFA_DEMAND_INCOMPLETE'}
        for row in doc['reconciliation']['fields']:
            if row['field'] in {'ordered_units', 'ordered_revenue'}:
                row.update(portfolio=None, sku_sum=None, gap=None,
                           status='INSUFFICIENT_DATA')
        doc['source_comparisons'] = []
        doc['warnings'].append(
            'EFA_DEMAND_INCOMPLETE:coverage=9/12;missing_dates=2026-09-03,2026-09-08,2026-09-10')
        self.assertEqual('PARTIAL_VALID', w06.audit(doc, NOW)['audit_result'])
        self.assertTrue(w06.publish(self.root, doc, NOW).is_file())
        view = w06.build(self.root, NOW)['views']['this_month']
        self.assertIsNone(view['portfolio']['ordered_units']['value'])
        self.assertEqual('EFA_DEMAND_INCOMPLETE',
                         view['portfolio']['ordered_units']['missing_reason'])
        self.assertIsNone(view['portfolio']['contribution']['value'])
        self.assertIsNone(view['portfolio']['settlement_profit']['value'])

    def test_true_conflict_still_blocks_publication(self):
        doc = self.partial_semantic()
        doc['source_comparisons'][0]['classification'] = 'TRUE_DATA_CONFLICT'
        self.assertEqual('TRUE_DATA_CONFLICT', w06.audit(doc, NOW)['audit_result'])
        with self.assertRaisesRegex(ValueError, 'TRUE_DATA_CONFLICT'):
            w06.publish(self.root, doc, NOW)

    def test_structural_failure_has_explicit_w07_outcome(self):
        doc = self.partial_semantic()
        del doc['layers']['settlement']
        result = w06.audit_outcome(doc, NOW)
        self.assertEqual('STRUCTURAL_FAIL', result['audit_result'])
        self.assertEqual('FAIL', result['schema'])
        with self.assertRaisesRegex(ValueError, 'FINANCIAL_LAYERS_REQUIRED'):
            w06.publish(self.root, doc, NOW)

    def test_split_returns_and_unallocated_portfolio_advertising(self):
        doc = self.partial_semantic()
        for field, value, source, basis in (
                ('buyer_returned_units', '0', 'OZON_UNIT_ECONOMICS', 'BUYER_RETURN'),
                ('logistic_return_units', '1', 'EFA_READ_MCP', 'LOGISTICS_RETURN')):
            doc['skus'][-1][field] = value
            doc['skus'][-1]['field_metadata'][field] = {
                'semantic': field, 'source': source, 'source_timestamp': NOW.isoformat(),
                'confidence': 'HIGH', 'financial_mode': 'OBSERVED',
                'cohort_basis': basis}
        doc['portfolio']['advertising_cpc'] = '644.49'
        doc['portfolio']['advertising_cpo'] = '690.30'
        doc['portfolio']['advertising_total'] = '1334.79'
        for field in ('advertising_cpc', 'advertising_cpo', 'advertising_total'):
            doc['portfolio']['field_metadata'][field] = {
                'semantic': field, 'source': 'OZON_ACCRUALS',
                'source_timestamp': NOW.isoformat(), 'confidence': 'HIGH',
                'financial_mode': 'OBSERVED'}
        w06.validate(doc, NOW)
        self.assertIsNone(doc['skus'][-1]['returned_units'])
        self.assertTrue(all(s['advertising_total'] is None for s in doc['skus']))
        self.assertIsNone(doc['portfolio']['contribution_rub'])
        self.assertIsNone(doc['portfolio']['profit_rub'])

    def test_control_center_exposes_split_returns_without_zeroing_missing_results(self):
        doc = self.partial_semantic()
        doc['portfolio']['buyer_returned_units'] = '1'
        doc['portfolio']['logistic_return_units'] = '2'
        for field, source in (('buyer_returned_units', 'OZON_UNIT_ECONOMICS'),
                              ('logistic_return_units', 'EFA_READ_MCP')):
            doc['portfolio']['field_metadata'][field] = {
                'semantic': field, 'source': source, 'source_timestamp': NOW.isoformat(),
                'confidence': 'HIGH', 'financial_mode': 'OBSERVED'}
        w06.publish(self.root, doc, NOW)
        view = w06.build(self.root, NOW)['views']['this_month']['portfolio']
        self.assertEqual('1', view['buyer_returned_units']['value'])
        self.assertEqual('2', view['logistic_return_units']['value'])
        self.assertIsNone(view['returned_units']['value'])
        self.assertIsNone(view['contribution']['value'])
        self.assertIsNone(view['settlement_profit']['value'])




    def test_partial_semantic_safety_failure_is_structural_and_not_publishable(self):
        doc = self.partial_semantic()
        doc['portfolio']['contribution_rub'] = '1'
        doc['portfolio']['field_metadata']['contribution_rub'] = {
            'semantic': 'contribution_rub', 'source': 'OZON_UNIT_ECONOMICS',
            'source_timestamp': NOW.isoformat(), 'confidence': 'LOW',
            'financial_mode': 'OBSERVED'}
        next(row for row in doc['reconciliation']['fields']
             if row['field'] == 'contribution_rub')['portfolio'] = '1'
        self.assertEqual('STRUCTURAL_FAIL', w06.audit(doc, NOW)['audit_result'])
        with self.assertRaisesRegex(ValueError, 'PARTIAL_SEMANTICS_INVALID'):
            w06.publish(self.root, doc, NOW)

    def test_w07_accepts_one_portfolio_proxy_and_rejects_double_advertising(self):
        doc = self.partial_semantic()
        calc = 'W06_CALCULATION'
        doc['evidence'].append({
            'source': calc, 'source_timestamp': NOW.isoformat(),
            'confirmation': 'TEST_VERIFIED', 'limitation': 'proxy fixture'})
        expense_fields = ('ozon_commission', 'acquiring', 'logistics',
                          'processing', 'last_mile', 'other_costs')
        for sku in doc['skus']:
            sku['seller_realization'] = '100'
            sku['field_metadata']['seller_realization'] = {
                'semantic': 'seller_realization', 'source': 'OZON_UNIT_ECONOMICS',
                'source_timestamp': NOW.isoformat(), 'confidence': 'MEDIUM',
                'financial_mode': 'OBSERVED', 'basis': 'SELLER_REALIZATION',
                'cohort_basis': 'ORDER_COHORT'}
            for field in expense_fields:
                sku[field] = '1'
                sku['field_metadata'][field] = {
                    'semantic': field, 'source': 'OZON_UNIT_ECONOMICS',
                    'source_timestamp': NOW.isoformat(), 'confidence': 'MEDIUM',
                    'financial_mode': 'OBSERVED'}
            sku['cogs'] = '10'
            sku['field_metadata']['cogs'] = {
                'semantic': 'cogs', 'source': 'OZON_UNIT_ECONOMICS',
                'source_timestamp': NOW.isoformat(), 'confidence': 'LOW',
                'financial_mode': 'SELLER_SIDE_PROXY', 'basis': 'CURRENT_COGS_PROXY',
                'cohort_basis': 'ORDER_COHORT', 'current_cogs_per_unit': '10',
                'quantity_basis_used': 1,
                'missing_components': ['historical_effective_cogs']}
            sku['presentation_metrics'] = {
                'ozon_expenses': {'value': '6', 'source': 'OZON_UNIT_ECONOMICS',
                                  'period': {'from': self.period['from'], 'to': self.period['to']}},
                'contribution_before_ads': {'value': '84', 'source': calc,
                                            'period': {'from': self.period['from'], 'to': self.period['to']}},
                'margin_before_ads': {'value': '84', 'source': calc,
                                      'period': {'from': self.period['from'], 'to': self.period['to']}}}
        portfolio = doc['portfolio']
        portfolio['seller_realization'] = '500'
        portfolio['field_metadata']['seller_realization'] = {
            'semantic': 'seller_realization', 'source': 'OZON_UNIT_ECONOMICS',
            'source_timestamp': NOW.isoformat(), 'confidence': 'MEDIUM',
            'financial_mode': 'OBSERVED', 'basis': 'SELLER_REALIZATION'}
        for field in expense_fields:
            portfolio[field] = '5'
            portfolio['field_metadata'][field] = {
                'semantic': field, 'source': 'OZON_UNIT_ECONOMICS',
                'source_timestamp': NOW.isoformat(), 'confidence': 'MEDIUM',
                'financial_mode': 'OBSERVED'}
        portfolio['cogs'] = '50'
        portfolio['field_metadata']['cogs'] = {
            'semantic': 'cogs', 'source': 'OZON_UNIT_ECONOMICS',
            'source_timestamp': NOW.isoformat(), 'confidence': 'LOW',
            'financial_mode': 'SELLER_SIDE_PROXY',
            'missing_components': ['historical_effective_cogs']}
        portfolio['advertising_total'] = '20'
        portfolio['field_metadata']['advertising_total'] = {
            'semantic': 'advertising_total', 'source': 'OZON_ACCRUALS',
            'source_timestamp': NOW.isoformat(), 'confidence': 'HIGH',
            'financial_mode': 'OBSERVED'}
        portfolio['contribution_rub'] = '400'
        portfolio['contribution_pct'] = '80'
        for field in ('contribution_rub', 'contribution_pct'):
            portfolio['field_metadata'][field] = {
                'semantic': field, 'source': calc, 'source_timestamp': NOW.isoformat(),
                'confidence': 'LOW', 'financial_mode': 'SELLER_SIDE_PROXY',
                'advertising_application': 'PORTFOLIO_ONLY_ONCE',
                'missing_components': ['historical_effective_cogs', 'tax']}
        portfolio['presentation_metrics'] = {
            'ozon_expenses': {'value': '30', 'source': 'OZON_UNIT_ECONOMICS',
                              'period': {'from': self.period['from'], 'to': self.period['to']}},
            'contribution_before_ads': {'value': '420', 'source': calc,
                                        'period': {'from': self.period['from'], 'to': self.period['to']}},
            'margin_before_ads': {'value': '84', 'source': calc,
                                  'period': {'from': self.period['from'], 'to': self.period['to']}},
            'proxy_result': {'value': '400', 'source': calc,
                             'period': {'from': self.period['from'], 'to': self.period['to']}}}
        for row in doc['reconciliation']['fields']:
            field = row['field']
            row['portfolio'] = portfolio[field]
            parts = [w06.number(sku[field]) for sku in doc['skus']]
            subtotal = sum(parts) if all(value is not None for value in parts) else None
            total = w06.number(portfolio[field])
            row['sku_sum'] = str(subtotal) if subtotal is not None else None
            row['gap'] = (str(total - subtotal)
                          if total is not None and subtotal is not None else None)
            row['status'] = ('PASS' if row['gap'] == '0'
                             else 'GAP' if row['gap'] is not None
                             else 'INSUFFICIENT_DATA')
        self.assertEqual('PASS', w06.audit(doc, NOW)['contribution_proxy'])
        self.assertEqual('PARTIAL_VALID', w06.audit(doc, NOW)['audit_result'])
        portfolio['contribution_rub'] = '380'
        next(row for row in doc['reconciliation']['fields']
             if row['field'] == 'contribution_rub')['portfolio'] = '380'
        portfolio['presentation_metrics']['proxy_result']['value'] = '380'
        self.assertEqual('STRUCTURAL_FAIL', w06.audit(doc, NOW)['audit_result'])

    def test_structural_validation_failure_has_explicit_w07_outcome(self):
        doc = self.partial_semantic()
        doc['portfolio']['returned_units'] = '1'
        outcome = w06.audit_outcome(doc, NOW)
        self.assertEqual('STRUCTURAL_FAIL', outcome['audit_result'])
        self.assertIn('GENERIC_RETURNED_UNITS_FORBIDDEN', outcome['blocker'])


if __name__ == '__main__':
    unittest.main()
