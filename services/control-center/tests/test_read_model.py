import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import read_model as rm

NOW = datetime(2026, 9, 12, 18, tzinfo=timezone.utc)
META = {f'W0{i}': {'name': f'Work {i}', 'mode': 'ON DEMAND' if i in (4, 5) else 'DAILY'} for i in range(9)}

class ReadModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'agents'
        self.root.mkdir()
    def tearDown(self):
        self.temp.cleanup()
    def doc(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding='utf-8')
        return rm.Document(file, self.root)
    def snapshot(self, **extra):
        value = {'schema_version':'efa.control_center.v2','observed_at':'2026-09-12T17:00:00+00:00',
                 'valid_until':'2026-09-13T00:00:00+00:00','queue_complete':True, **extra}
        (self.root / 'CONTROL_CENTER_READ_MODEL_V2.json').write_text(json.dumps(value), encoding='utf-8')
    def event(self, **extra):
        return {'work':'W03','reference':'EXACT-1','status':'EXECUTION_ELIGIBLE',
                'source':'REPORTS/W03/PROPOSALS/example.md','observed_at':'2026-09-12T12:00:00+00:00',
                'valid_until':'2026-09-13T00:00:00+00:00', **extra}
    def test_terminal_execution_closes_exact_reference_and_preserves_other_targets(self):
        records=[self.event(),self.event(reference='EXACT-2'),self.event(status='EXECUTED',observed_at='2026-09-12T13:00:00+00:00')]
        queue,history,gaps=rm.reconcile_actions(records,NOW)
        self.assertEqual(['EXACT-2'],[a['reference'] for a in queue])
        self.assertEqual('EXECUTED',history[0]['status'])
        self.assertEqual([],gaps)
    def test_rejected_closed_cancelled_superseded_absent_from_primary(self):
        queue,history,_=rm.reconcile_actions([self.event(reference=s,status=s) for s in rm.CLOSED_STATES],NOW)
        self.assertEqual([],queue)
        self.assertEqual(len(rm.CLOSED_STATES),len(history))
    def test_expired_missing_validity_and_unknown_state_fail_closed(self):
        for event in (self.event(valid_until=None),self.event(valid_until='2026-09-11T00:00:00Z'),self.event(status='APPROVED')):
            queue,_,gaps=rm.reconcile_actions([event],NOW)
            self.assertEqual([],queue)
            self.assertTrue(gaps)
    def test_conflicting_equal_time_states_do_not_pick_a_winner(self):
        queue,history,gaps=rm.reconcile_actions([self.event(),self.event(status='BLOCKED')],NOW)
        self.assertEqual([],queue+history)
        self.assertIn('Conflicting',gaps[0])
    def test_timezone_ordering_closure_does_not_reopen(self):
        queue,history,_=rm.reconcile_actions([self.event(observed_at='2026-09-12T14:00:00+03:00'),self.event(status='EXECUTED',observed_at='2026-09-12T12:00:00Z')],NOW)
        self.assertEqual([],queue)
        self.assertEqual(1,len(history))
    def test_malformed_records_are_isolated(self):
        for event in (None,{},self.event(work='W99'),self.event(source='../.env'),self.event(observed_at=99),self.event(status=[])):
            self.assertTrue(rm.reconcile_actions([event],NOW)[2])
    def test_missing_snapshot_is_unknown_not_zero(self):
        m=rm.build(self.root,META,NOW)
        self.assertFalse(m['queue_complete'])
        self.assertEqual(5,len(m['portfolio']))
        self.assertTrue(all(w['open_action_count'] is None for w in m['works']))
        self.assertEqual(0,m['commercial']['counts']['cpc']['known'])
        self.assertEqual('UNKNOWN',m['governance']['capability_status'])
    def test_explicit_empty_current_snapshot_confirms_zero(self):
        self.snapshot(actions=[])
        m=rm.build(self.root,META,NOW)
        self.assertTrue(m['queue_complete'])
        self.assertTrue(all(w['open_action_count']==0 for w in m['works']))
    def test_stale_snapshot_cannot_confirm_empty_queue(self):
        self.snapshot(valid_until='2026-09-11T00:00:00Z')
        self.assertFalse(rm.build(self.root,META,NOW)['queue_complete'])
    def test_malformed_snapshot_is_atomic_no_partial_portfolio_override(self):
        good={'value':'ON','source':'REPORTS/W03/example.md','observed_at':'2026-09-12T15:00:00Z','confirmation':'REPORTED'}
        self.snapshot(portfolio=[{'sku':'UF001','cpc':good},{'sku':'UF002','cpc':{'value':'OFF'}}])
        m=rm.build(self.root,META,NOW)
        self.assertEqual('UNKNOWN',m['portfolio'][0]['cpc']['value'])
        self.assertFalse(m['queue_complete'])
    def test_structured_scalar_validation_does_not_crash_counts(self):
        for value in ([],{},True,float('nan')):
            self.snapshot(portfolio=[{'sku':'UF001','cpc':{'value':value,'source':'REPORTS/W03/example.md','observed_at':'2026-09-12T15:00:00Z','confirmation':'REPORTED'}}])
            self.assertFalse(rm.build(self.root,META,NOW)['queue_complete'])
    def test_support_work_cannot_emit_canonical_status(self):
        self.snapshot(works=[{'id':'W03','source':'REPORTS/W03/example.md','observed_at':'2026-09-12T15:00:00Z','canonical_status':'OK'}])
        self.assertFalse(rm.build(self.root,META,NOW)['queue_complete'])
    def test_metadata_parser_ignores_fenced_examples_and_escaped_pipes(self):
        d=self.doc('sample.md','''```markdown
Status: EXECUTED
```
Status: BLOCKED
| Field | Value |
| --- | --- |
| Blocker | one \\| two |
''')
        self.assertEqual('BLOCKED',d.get('Status'))
        self.assertEqual('one \\| two',d.get('Blocker'))
    def test_latest_report_uses_document_date_not_mtime_or_analysis_filename(self):
        old=self.doc('REPORTS/W06/DAILY/2026-09-10/W06_FINANCE_STATUS.md','Date: 2026-09-10\nCycle status: OLD')
        self.doc('REPORTS/W06/DAILY/2026-09-11/W06_FINANCE_STATUS.md','Date: 2026-09-11\nCycle status: DEFERRED / NOT_TRIGGERED\nW06 validation run performed: NO')
        self.doc('REPORTS/W06/ANALYSIS/2026-09-12/random.md','Status: PASS')
        old.path.touch()
        w=rm.build(self.root,META,NOW)['works'][6]
        self.assertEqual('DEFERRED / NOT_TRIGGERED',w['status'])
        self.assertIsNone(w['last_run'])
    def test_execution_poststate_is_not_recommendation_or_buyer_realization(self):
        self.doc('REPORTS/W03/EXECUTION/2026-09-12/example.md','''Execution time: 2026-09-12 12:45 MSK
| SKU | CPC post-state | CPO post-state | Verification |
|---|---|---|---|
| УФ001Б | 123 НЕАКТИВНА | OFF, 12.09.2026 | PASS |
| SKU | Seller-side price post | Site price post | Elastic configured state |
|---|---|---|---|
| УФ001Б | 953 ₽ | 414 ₽ | OFF / NOT_SET |
''')
        p=rm.build(self.root,META,NOW)['portfolio'][0]
        self.assertEqual('OFF',p['cpc']['value'])
        self.assertEqual('953 ₽',p['seller_price']['value'])
        self.assertEqual('414 ₽',p['buyer_price']['value'])
        self.assertEqual('UNKNOWN',p['promotion']['value'])
        self.assertEqual('UNKNOWN',p['contribution']['value'])
    def test_moderation_invalidates_numeric_forecast_and_prior_score(self):
        self.doc('REPORTS/W04/AUDIT/2026-09-12/CONTENT_RATING_V1.md','''Observed: 2026-09-12, 12:58–13:11 MSK
| SKU | Current score | Max without media |
|---|---|---|
| УФ005Б | 65.0 | 77.5 |
''')
        self.doc('REPORTS/W04/CONTENT/2026-09-12/UF005_PUBLISH.md','''Date: 2026-09-12
SKU: ЭФА УФ 005Б
Moderation status: IN PROGRESS / Обновляется
''')
        p=rm.build(self.root,META,NOW)['portfolio'][4]
        self.assertEqual('RECALCULATION PENDING',p['content_rating']['value'])
    def test_active_policy_is_read_and_deprecated_contract_ignored(self):
        self.doc('W03_BOUNDED_AD_EXECUTION_V1.md','Capability status: ACTIVE\nPolicy ID: OLD')
        self.doc('W03_BOUNDED_AD_EXECUTION_POLICY_V2.md','''| Field | Value |
|---|---|
| Policy ID | W03_BOUNDED_AD_EXECUTION_POLICY_V2 |
| Capability status | ACTIVE |
| Global Execution Plane | NOT READY |
| Class | Operations | Owner command gate |
|---|---|---|
| CLASS_A_PROTECTIVE_SPEND_STOP | CPC_PAUSE, CPO_DISABLE | exact execute |
''')
        g=rm.build(self.root,META,NOW)['governance']
        self.assertEqual('ACTIVE',g['capability_status'])
        self.assertEqual('NOT READY',g['global_execution_plane'])
        self.assertEqual('W03_BOUNDED_AD_EXECUTION_POLICY_V2',g['policy'])
        self.assertEqual(1,len(g['classes']))

    def test_observation_sort_uses_instants_across_timezone_offsets(self):
        self.assertLess(rm.observation_key('2026-09-12T14:00:00+03:00'),
                        rm.observation_key('2026-09-12T12:00:00Z'))

    def test_equal_time_portfolio_conflict_preserves_both_sources(self):
        self.doc('REPORTS/W03/EXECUTION/2026-09-12/example.md','''Execution time: 2026-09-12 12:45 MSK
| SKU | CPC post-state | CPO post-state | Verification |
|---|---|---|---|
| УФ001Б | 123 НЕАКТИВНА | OFF | PASS |
''')
        self.snapshot(portfolio=[{'sku':'UF001','cpc':{'value':'ON','source':'REPORTS/W03/new.md',
            'observed_at':'2026-09-12T09:45:00Z','confirmation':'REPORTED'}}])
        value=rm.build(self.root,META,NOW)['portfolio'][0]['cpc']
        self.assertEqual('CONFLICT',value['value'])
        self.assertEqual(['OFF','ON'],[o['value'] for o in value['observations']])

    def test_source_route_serves_allowed_report_and_blocks_traversal(self):
        import app
        import threading
        import urllib.request
        import urllib.error
        from unittest import mock
        source='REPORTS/W00/DAILY/2026-09-12/W00_OWNER_BRIEF.md'
        self.doc(source,'Date: 2026-09-12\nStatus: BLOCKED\n<script>unsafe()</script>')
        server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            base='http://127.0.0.1:'+str(server.server_port)
            with mock.patch.object(app,'OZON_AGENTS_ROOT',self.root):
                with urllib.request.urlopen(base+rm.source_url(source)) as response:
                    body=response.read().decode('utf-8')
                    self.assertEqual(200,response.status)
                    self.assertIn('&lt;script&gt;',body)
                    self.assertNotIn('<script>unsafe()',body)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(base+'/agent-source?path=..%2F.env')
                self.assertEqual(404,error.exception.code)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

if __name__=='__main__': unittest.main()
