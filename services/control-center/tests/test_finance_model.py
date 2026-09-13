import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import finance_model as fm
from read_model import Document

NOW = datetime(2026, 9, 12, 18, tzinfo=timezone.utc)


class FinanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'agents'
        self.root.mkdir()
        self.period = fm.period_options(NOW)[4]

    def tearDown(self):
        self.temp.cleanup()

    def snapshot(self, items, **extra):
        data = {'schema_version': 'efa.control_center.finance.v3',
                'observed_at': '2026-09-12T17:00:00Z',
                'valid_until': '2026-09-13T00:00:00Z', 'periods': items, **extra}
        (self.root / 'CONTROL_CENTER_FINANCE_V3.json').write_text(json.dumps(data), encoding='utf-8')

    def source_metric(self, raw, **extra):
        return {**fm.metric(raw, self.period, source='REPORTS/W06/test.md',
                           observed_at='2026-09-12T17:00:00Z'), **extra}

    def item(self, **metrics):
        return {'period': {k: self.period[k] for k in ('from', 'to')},
                'portfolio': metrics, 'skus': []}

    def fixture_report(self):
        # Deliberately explicit table fixture: no dependency on untracked reports.
        table = '''# Audit
Date: 2026-09-11
Compiled: 2026-09-12
Period: 2026-08-01 — 2026-08-31
Confirmed portfolio result after CPC+CPO: 17,484.01 ₽ / 11.76% SELLER-SIDE PROXY, before tax and Premium.

| SKU | Ordered units / ordered revenue | Delivered / returned / net units | Seller realization | Proxy contribution before advertising | Settlement-matched SKU CPC | Proxy contribution after matched CPC | Proxy margin after matched CPC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UF001 | 20 / 12466 | 57 / 0 / 57 | 34600 | 3098.88 / 8.96% | 172.13 | 2926.75 | 8.46% |
| UF002 | 7 / 4662 | 33 / 0 / 33 | 22027 | 2547.48 / 11.57% | 57.82 | 2489.66 | 11.30% |
| UF003 | 34 / 20994 | 60 / 0 / 60 | 37199 | 4791.61 / 12.88% | 267.98 | 4523.63 | 12.16% |
| UF004 | 10 / 8050 | 40 / 2 / 38 | 30556 | 5276.85 / 17.27% | 305.74 | 4971.11 | 16.27% |
| UF005 | 22 / 16590 | 34 / 0 / 34 | 24261 | 3838.42 / 15.82% | 168.33 | 3670.09 | 15.13% |
| Portfolio | 93 / 62762 | 224 / 2 / 222 | 148643 | 19553.24 / 13.15% | 972 | 18581.24 | 12.50% |

| Component | August observed amount | Allocation status |
| --- | --- | --- |
| CPC | 1901.18 | Partial |
| CPO | 129 | Unallocated |
| Premium subscription | 9990 | Unallocated |
| Other account-level charge | 39.05 | Unallocated |

| SKU | Commission | Acquiring | Forward logistics | Return logistics | Last mile | Processing | Return processing | Other attributable | COGS proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UF001 | 14593.32 | 271.59 | 5837 | 79 | 618.21 | 640 | 0 | 0 | 9462 |
| UF002 | 9211.30 | 123.70 | 3374 | 168 | 375.52 | 320 | 0 | 0 | 5907 |
| UF003 | 15761.10 | 295.06 | 5714 | 0 | 577.23 | 580 | 0 | 0 | 9480 |
| UF004 | 12835.12 | 237.69 | 4093 | 330 | 486.34 | 420 | 30 | 45 | 6802 |
| UF005 | 10276.96 | 251.01 | 3324 | 92 | 356.61 | 340 | 0 | 138 | 5644 |
| Total | 62677.80 | 1179.05 | 22342 | 669 | 2413.91 | 2300 | 30 | 183 | 37295 |
'''
        path = self.root.parent / 'REPORTS/W06/AUDIT/2026-09-11/W06_EFA_ALL_SKU_AUGUST_UNIT_ECONOMICS_AUDIT_V1.md'
        path.parent.mkdir(parents=True)
        path.write_text(table, encoding='utf-8')
        return path

    def test_moscow_calendar_and_leap_previous_month(self):
        periods = {p['id']: p for p in fm.period_options(datetime(2024, 2, 29, 22, tzinfo=timezone.utc))}
        self.assertEqual('2024-03-01', periods['today']['from'])
        self.assertEqual('2024-02-29', periods['previous_month']['to'])
        self.assertEqual('2024-02-23', periods['last7']['from'])
        self.assertEqual('2024-02-29', periods['last7']['to'])
        self.assertEqual(7, len(periods))

    def test_missing_is_null_for_all_five_skus(self):
        data = fm.build_finance(self.root, NOW)
        for view in data['views'].values():
            self.assertFalse(view['available'])
            self.assertEqual(5, len(view['skus']))
            self.assertTrue(all(m['value'] is None for m in view['portfolio'].values()))

    def test_august_period_is_not_current_and_never_forecast_profit(self):
        self.fixture_report()
        data = fm.build_finance(self.root, NOW)
        self.assertEqual('this_month', data['default_period'])
        self.assertFalse(data['views']['previous_month']['available'])
        self.assertFalse(data['views']['this_month']['available'])
        self.assertFalse(data['views']['today']['available'])
        p = data['views']['august2026']['portfolio']
        self.assertEqual('17484.01', p['contribution']['value'])
        self.assertEqual('11.76', p['margin']['value'])
        self.assertEqual('19553.24', p['contribution_before_ads']['value'])
        self.assertEqual('SELLER_SIDE_PROXY', p['contribution']['mode'])
        self.assertEqual('INSUFFICIENT_SETTLEMENT_DATA', p['contribution']['settlement_status'])
        self.assertIsNone(p['settlement_profit']['value'])
        self.assertIsNone(p['profit_before_tax']['value'])
        self.assertEqual('SETTLEMENT_AWARE', p['seller_realization']['mode'])
        self.assertEqual('order_date', p['ordered_units']['cohort'])

    def test_actual_per_sku_contributions_and_bridge(self):
        self.fixture_report()
        view = fm.build_finance(self.root, NOW)['views']['august2026']
        self.assertEqual(['2926.75', '2489.66', '4523.63', '4971.11', '3670.09'],
                         [s['metrics']['contribution']['value'] for s in view['skus']])
        recon = {r['metric']: r for r in view['reconciliation']}
        self.assertEqual('PASS', recon['seller_realization']['status'])
        self.assertEqual('PASS', recon['ordered_units']['status'])
        self.assertEqual('91833.81', view['portfolio']['ozon_expenses']['value'])
        self.assertEqual('39.05', recon['ozon_expenses']['difference'])
        self.assertEqual('37295', view['portfolio']['cogs']['value'])
        self.assertEqual('SELLER_SIDE_PROXY', view['skus'][0]['metrics']['cogs']['mode'])
        self.assertEqual('-1097.23', recon['contribution']['difference'])
        self.assertEqual('1058.18', view['bridge']['unallocated_advertising'])
        self.assertEqual(Decimal(0), Decimal(view['bridge']['unexplained_difference']))
        self.assertEqual('PASS', view['bridge']['status'])

    def test_report_period_metadata_required(self):
        path = self.fixture_report()
        path.write_text(path.read_text(encoding='utf-8').replace('Period:', 'Wrong period:'), encoding='utf-8')
        self.assertFalse(fm.build_finance(self.root, NOW)['views']['august2026']['available'])

    def test_snapshot_exact_period_values_and_provenance(self):
        item = self.item(seller_realization=self.source_metric('500'))
        item['skus'] = [{'sku': 'UF001', 'metrics': {'seller_realization': self.source_metric('500')}}]
        self.snapshot([item])
        view = fm.build_finance(self.root, NOW)['views']['this_month']
        self.assertEqual('500', view['portfolio']['seller_realization']['value'])
        self.assertIsNone(view['skus'][1]['metrics']['seller_realization']['value'])
        self.assertEqual('INSUFFICIENT_DATA', view['reconciliation'][0]['status'])

    def test_expired_future_invalid_period_and_source_fail_closed(self):
        for extra in ({'valid_until': '2026-09-11T00:00:00Z'}, {'observed_at': '2026-09-13T00:00:00Z'}):
            self.snapshot([self.item(seller_realization=self.source_metric('100'))], **extra)
            self.assertFalse(fm.build_finance(self.root, NOW)['views']['this_month']['available'])
        for bad in ({'source': '../.env'}, {'value': 'NaN'}, {'value': True}, {'mode': 'MAGIC'},
                    {'period': {'from': '2026-08-01', 'to': '2026-08-31'}}):
            self.snapshot([self.item(seller_realization=self.source_metric('100', **bad))])
            self.assertFalse(fm.build_finance(self.root, NOW)['views']['this_month']['available'])

    def test_buyer_price_is_not_accepted_as_financial_metric(self):
        self.snapshot([self.item(buyer_price=self.source_metric('500'))])
        data = fm.build_finance(self.root, NOW)
        self.assertFalse(data['views']['this_month']['available'])
        self.assertTrue(data['data_gaps'])

    def test_atomic_rejection_after_valid_first_item(self):
        item = self.item(seller_realization=self.source_metric('500'))
        self.snapshot([item, {**item, 'period': {'from': '1900-01-01', 'to': '1900-01-02'}}])
        self.assertFalse(fm.build_finance(self.root, NOW)['views']['this_month']['available'])

    def test_final_profit_requires_settlement_mode_and_final_confirmation(self):
        for mode, status, accepted in [('SELLER_SIDE_PROXY', 'FINAL_SETTLEMENT', False),
                                      ('SETTLEMENT_AWARE', 'INSUFFICIENT_SETTLEMENT_DATA', False),
                                      ('SETTLEMENT_AWARE', 'FINAL_SETTLEMENT', True)]:
            self.snapshot([self.item(settlement_profit=self.source_metric('500', mode=mode, settlement_status=status))])
            self.assertEqual(accepted, fm.build_finance(self.root, NOW)['views']['this_month']['available'])

    def test_different_cohorts_do_not_reconcile(self):
        view = fm.blank(self.period)
        view['portfolio']['seller_realization'] = self.source_metric('500')
        for sku in view['skus']:
            sku['metrics']['seller_realization'] = self.source_metric('100', cohort='order_cohort')
        self.assertEqual('INSUFFICIENT_DATA', fm.reconcile(view)[0]['status'])

    def test_source_numbers_only_and_missing_costs_remain_unknown(self):
        self.assertEqual(Decimal('17484.01'), fm.amount('17,484.01 ₽'))
        self.assertIsNone(fm.amount('profit 17000'))
        view = fm.blank(self.period)
        self.assertIsNone(fm.add_known(view['portfolio'], fm.EXPENSES))


if __name__ == '__main__':
    unittest.main()
