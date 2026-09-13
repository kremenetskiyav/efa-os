"""Synthetic August profile regressions; no private snapshots or Git required."""
import copy
import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import finance_model as fm
import w06_snapshot as w06

NOW = datetime(2026, 9, 13, 18, tzinfo=timezone.utc)
SOURCE = 'synthetic/august-evidence.md'


def fixture():
    period = {'id': 'august2026', 'from': '2026-08-01', 'to': '2026-08-31'}
    doc = w06.empty(period, NOW)
    doc.update(source_status='PARTIAL', financial_mode='SELLER_SIDE_PROXY',
               warnings=['INSUFFICIENT_SETTLEMENT_DATA', 'Current COGS; historical effective costs unavailable'])
    doc['freshness'] = {'status': 'HISTORICAL_REFERENCE', 'observed_at': NOW.isoformat(), 'valid_until': None}
    doc['evidence'] = [{'source': SOURCE, 'source_timestamp': NOW.isoformat(),
                        'confirmation': 'SYNTHETIC_TEST', 'limitation': 'Not operational evidence'}]
    for entity in [doc['portfolio'], *doc['skus']]:
        portfolio = entity is doc['portfolio']
        entity.update(seller_realization='500' if portfolio else '100',
                      cogs='50' if portfolio else '10',
                      advertising_cpc='13' if portfolio else '2',
                      advertising_cpo='4' if portfolio else None,
                      advertising_total='17' if portfolio else '2',
                      contribution_rub='398' if portfolio else '82',
                      contribution_pct='79.6' if portfolio else '82', complete_costs=False)
        for field in ('ozon_commission', 'acquiring', 'logistics', 'processing', 'last_mile', 'other_costs'):
            entity[field] = '5' if portfolio else '1'
        if portfolio:
            entity['other_costs'] = '10'
        for field in w06.FIELDS:
            if entity[field] is not None:
                entity['field_metadata'][field] = {
                    'semantic': field, 'source': SOURCE, 'source_timestamp': NOW.isoformat(),
                    'confidence': 'LOW', 'financial_mode': 'SELLER_SIDE_PROXY',
                    'basis': 'SELLER_REALIZATION' if field == 'seller_realization' else 'W06_REPORTED',
                    'scope': 'Только сопоставленный со SKU CPC',
                    'missing_components': ['historical_effective_cogs', 'tax', 'settlement_adjustments']}
        values = {'return_logistics': '0', 'return_processing': '0',
                  'ozon_expenses': '35' if portfolio else '6',
                  'contribution_before_ads': '420' if portfolio else '84',
                  'proxy_result': entity['contribution_rub']}
        if portfolio:
            values['premium'] = '99'
        entity['presentation_metrics'] = {key: {
            'value': value, 'source': SOURCE, 'observed_at': NOW.isoformat(),
            'period': {'from': period['from'], 'to': period['to']},
            'mode': 'SELLER_SIDE_PROXY'} for key, value in values.items()}
    rows = []
    for field in ('seller_realization', 'cogs', 'advertising_cpc', 'advertising_total', 'other_costs', 'contribution_rub'):
        total = Decimal(doc['portfolio'][field])
        subtotal = sum(Decimal(s[field]) for s in doc['skus'])
        gap = total - subtotal
        rows.append({'field': field, 'portfolio': str(total), 'sku_sum': str(subtotal),
                     'gap': str(gap), 'status': 'GAP' if gap else 'PASS'})
    doc['reconciliation'] = {
        'fields': rows, 'status': 'GAP', 'allocation_rule': 'NO_SYNTHETIC_ALLOCATION',
        'reconciliation_gap_rub': '-12', 'unexplained_gap_rub': '0',
        'gap_reasons': [
            {'reason': 'UNALLOCATED_ADVERTISING', 'amount_rub': '7'},
            {'reason': 'ACCOUNT_LEVEL_CHARGE', 'amount_rub': '5'},
            {'reason': 'PREMIUM_EXCLUDED_FROM_CONTRIBUTION', 'amount_rub': '99'}],
        'presentation_bridge': {'unallocated_advertising': '7', 'unallocated_other': '5',
                                'unexplained_difference': '0', 'status': 'PASS'}}
    return doc


class AugustProfileTests(unittest.TestCase):
    def test_exact_profile_and_explained_gap(self):
        audit = w06.audit(fixture(), NOW)
        self.assertEqual('PARTIAL_VALID', audit['audit_result'])
        for key in ('schema', 'source_provenance', 'contribution_proxy'):
            self.assertEqual('PASS', audit[key])
        bridge = audit['historical_proxy_bridge']
        self.assertEqual('AUGUST_2026_DIRECT_MATCHED_CPC_V1', bridge['profile'])
        self.assertEqual('398', bridge['portfolio_contribution'])
        self.assertEqual('0.00', bridge['unexplained_gap_rub'])
        self.assertEqual('GAP', audit['reconciliation'])

    def test_audit_preserves_every_input_value(self):
        doc = fixture()
        before = copy.deepcopy(doc)
        w06.audit(doc, NOW)
        self.assertEqual(before, doc)

    def test_unsafe_limits_and_provenance_are_rejected(self):
        changes = {
            'tax': lambda d: d['portfolio'].update(tax='1'),
            'profit': lambda d: d['portfolio'].update(profit_rub='1'),
            'premium': lambda d: d['portfolio']['presentation_metrics']['premium'].update(value='0'),
            'allocation': lambda d: d['reconciliation'].update(allocation_rule='SYNTHETIC'),
            'source': lambda d: d['skus'][0]['presentation_metrics']['contribution_before_ads'].update(source='missing'),
            'cpc_scope': lambda d: d['skus'][0]['field_metadata']['advertising_cpc'].update(scope='allocated'),
            'cogs_limit': lambda d: d['skus'][0]['field_metadata']['contribution_rub'].update(missing_components=['tax']),
            'gap': lambda d: d['reconciliation'].update(unexplained_gap_rub='1'),
            'bridge': lambda d: d['reconciliation']['presentation_bridge'].update(unallocated_other='0'),
            'dates': lambda d: d['period'].update(to='2026-08-30'),
        }
        for name, change in changes.items():
            with self.subTest(case=name):
                doc = fixture()
                change(doc)
                self.assertEqual('STRUCTURAL_FAIL', w06.audit_outcome(doc, NOW)['audit_result'])

    def test_sku_contribution_arithmetic_is_checked(self):
        doc = fixture()
        doc['skus'][0]['presentation_metrics']['contribution_before_ads']['value'] = '85'
        with self.assertRaisesRegex(ValueError, 'AUGUST_PROXY_BEFORE_ADS'):
            w06.audit(doc, NOW)

    def test_reconciliation_rows_are_checked_before_profile(self):
        doc = fixture()
        doc['reconciliation']['fields'][-1]['sku_sum'] = '999'
        with self.assertRaisesRegex(ValueError, 'RECONCILIATION_SKU_SUM_MISMATCH'):
            w06.audit(doc, NOW)

    def test_current_periods_never_use_august_profile(self):
        for period in fm.period_options(NOW):
            if period['id'] == 'august2026':
                continue
            with self.subTest(period=period['id']):
                doc = fixture()
                doc['period'] = {**{k: period[k] for k in ('from', 'to')},
                                 'preset': w06.PRESETS[period['id']], 'timezone': 'Europe/Moscow'}
                doc['freshness']['status'] = 'UNKNOWN'
                doc['financial_mode'] = 'MIXED_OBSERVED_PROXY'
                for entity in [doc['portfolio'], *doc['skus']]:
                    for datum in entity['presentation_metrics'].values():
                        datum['period'] = {k: period[k] for k in ('from', 'to')}
                with patch.object(w06, 'audit_august_direct_cpc') as historical:
                    result = w06.audit(doc, NOW)
                    historical.assert_not_called()
                self.assertEqual('FAIL', result['contribution_proxy'])
                self.assertEqual('STRUCTURAL_FAIL', result['audit_result'])
                self.assertNotIn('historical_proxy_bridge', result)


if __name__ == '__main__':
    unittest.main()
