"""Independent property, lifecycle, quality and concurrency tests; no network."""
from __future__ import annotations
import concurrent.futures
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from copy import deepcopy
from pathlib import Path
from nan_quota_balance import ROOT,KEYS,load_config,validate_usage,plan_nan_task,simulate_nan_tasks
from nan_quota_dispatch import choose,finish,connect,validate_target
from nan_quota_usage import normalized_report,parse_models,private_write
NOW=datetime(2026,10,10,12,0,tzinfo=timezone.utc)
def usage(source='provider-normalized',verified=('nan_ds','nan_glm'),approximate=False,consumed=None):
    return {'schemaVersion':1,'month':'2026-10','observedAt':'2026-10-10T11:55:00Z','source':source,
      'approximate':approximate,'consumed':consumed or dict(nan_qwen=0,nan_ds=1400000,nan_mf=0,nan_glm=944900000),'verifiedOffers':list(verified)}
def task(**changes):
    return {'taskId':'t1','functionId':'bounded-exploration','domain':'research','modality':'text',
      'estimatedInputTokens':12000,'estimatedTotalTokens':35000,'includeTrials':False,'closedTask':True,
      'acceptanceOracle':True,'highImpact':False,'headroomFraction':.02,**changes}
class Balancer(unittest.TestCase):
    def test_current_inventory_is_one_source_of_quota_truth(self):
        policy,models,offers=load_config()
        self.assertEqual(set(models),set(KEYS));self.assertEqual(sum(row['monthlyTokens'] for row in models.values()),6500000000)
        self.assertNotIn('nan_mimo',models)
    def test_unknown_and_old_month_are_not_zero(self):
        self.assertEqual(plan_nan_task(None,task(),NOW)['status'],'unknown-usage')
        self.assertEqual(plan_nan_task(usage(),task(),datetime(2026,11,1,tzinfo=timezone.utc))['status'],'unknown-usage')
    def test_screenshot_is_not_authoritative_for_reservation(self):
        u=usage('account-screenshot',(),True)
        self.assertFalse(plan_nan_task(u,task(),NOW)['usedAsActual'])
        self.assertEqual(plan_nan_task(u,task(),NOW,require_verified=True)['status'],'unknown-usage')
    def test_quality_first_and_trial_opt_in(self):
        self.assertEqual(plan_nan_task(usage(),task(),NOW)['selected'],'nan_ds')
        self.assertEqual(plan_nan_task(usage(),task(includeTrials=True),NOW)['selected'],'nan_mf')
        self.assertEqual(plan_nan_task(usage(),task(acceptanceOracle=False),NOW)['status'],'blocked')
        self.assertEqual(plan_nan_task(usage(),task(highImpact=True),NOW)['status'],'blocked')
        self.assertEqual(plan_nan_task(usage(),task(functionId='critical-review'),NOW)['status'],'blocked')
        self.assertEqual(plan_nan_task(usage(),task(domain='agent-use'),NOW)['status'],'blocked')
    def test_modality_and_context_are_hard_gates(self):
        u=usage('hypothetical',(),True,{k:0 for k in KEYS})
        self.assertEqual(plan_nan_task(u,task(includeTrials=True,modality='audio'),NOW)['selected'],'nan_mf')
        decision=plan_nan_task(u,task(includeTrials=True,estimatedInputTokens=200000,estimatedTotalTokens=240000),NOW)
        self.assertIn('contexto',next(c for c in decision['candidates'] if c['offeringKey']=='nan_qwen')['reason'])
        self.assertFalse(next(c for c in plan_nan_task(u,task(includeTrials=True,functionId='bounded-implementation'),NOW)['candidates'] if c['offeringKey']=='nan_qwen')['eligible'])
    def test_no_usage_corruption_and_balanced_over_many_tasks(self):
        u=usage('hypothetical',(),True,{k:0 for k in KEYS});copy=deepcopy(u)
        s=simulate_nan_tasks(u,task(includeTrials=True,estimatedInputTokens=10000,estimatedTotalTokens=100000),500,NOW)
        self.assertEqual(s['planned'],500);self.assertEqual(u,copy)
        qs={k:r['monthlyTokens'] for k,r in load_config()[1].items()}
        progress=[s['projected'][k]/qs[k] for k in KEYS]
        self.assertLessEqual(max(progress)-min(progress),100000/500000000+1e-12)
    def test_usage_rejects_floats_negative_extra_fields_or_fake_dates(self):
        baseline=usage();self.assertEqual(validate_usage(baseline),baseline)
        for bad in ({**baseline,'consumed':{**baseline['consumed'],'nan_glm':-1}},
                    {**baseline,'consumed':{**baseline['consumed'],'nan_glm':12.3}},
                    {**baseline,'consumed':{'nan_ds':12}},
                    {**baseline,'api_key':'secret'},
                    {**baseline,'observedAt':'2026-10-10T11:55:00'},
                    {**baseline,'month':'2026-11'},
                    {**baseline,'verifiedOffers':['nan_ds','nan_ds']}):
            with self.assertRaises(ValueError):validate_usage(bad)
    def test_request_idempotency_atomic_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'state.sqlite';u=usage();t=task()
            first=choose(path,u,t,NOW,write=True);self.assertEqual(first['selected'],'nan_ds')
            self.assertEqual(choose(path,u,t,NOW,write=True)['status'],'existing')
            with self.assertRaises(ValueError):choose(path,u,{**t,'estimatedTotalTokens':35001},NOW,write=True)
            with self.assertRaises(ValueError):finish(path,'t1','release',None,NOW)
            self.assertEqual(finish(path,'t1','settle',37000,NOW)['status'],'settled')
            self.assertTrue(finish(path,'t1','settle',37000,NOW)['idempotent'])
            with self.assertRaises(ValueError):finish(path,'t1','settle',37001,NOW)
            next_choice=choose(path,u,task(taskId='t2'),NOW,write=True)
            self.assertEqual(next_choice['selected'],'nan_ds')
            self.assertEqual(finish(path,'t2','release',None,NOW,confirm_not_sent=True)['status'],'released')
            conn=connect(path,False)
            try:self.assertEqual(conn.execute("SELECT COUNT(*) FROM requests WHERE status='settled'").fetchone()[0],1)
            finally:conn.close()
    def test_global_concurrency_blocks_replacement_not_forces_unfit(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'state.sqlite';u=usage(verified=('nan_ds',))
            for i in range(7):
                d=choose(path,u,task(taskId=f't-{i}'),NOW,write=True)
                self.assertEqual(d['selected'],'nan_ds')
            final=choose(path,u,task(taskId='t-extra'),NOW,write=True)
            self.assertEqual(final['status'],'no-eligible')
            self.assertEqual(finish(path,'t-0','release',None,NOW,confirm_not_sent=True)['status'],'released')
            self.assertEqual(choose(path,u,task(taskId='t-next'),NOW,write=True)['status'],'selected')
    def test_cli_native_role_target_cannot_impersonate_coordinator_or_custom_role(self):
        self.assertEqual(validate_target('gentle-shell','gentle-ai-worker','bounded-implementation','research','balanced')['role'],'gentle-ai-worker')
        self.assertEqual(validate_target('omp','task','bounded-implementation','apps','balanced')['role'],'task')
        for params in [('gentle-shell','orchestrator','bounded-implementation','research','balanced'),
                       ('gentle-shell','gentle-ai-worker','bounded-exploration','research','balanced'),
                       ('omp','judge','independent-review','research','balanced'),
                       ('omp','memory','memory-maintenance','research','balanced'),
                       ('omp','not-a-role','bounded-implementation','research','balanced')]:
            with self.assertRaises(ValueError):validate_target(*params)
    def test_provider_month_totals_are_not_confused_with_paged_daily_rows(self):
        report={'object':'usage.report','start_date':'2026-10-01','end_date':'2026-10-10','has_more':True,'next_cursor':'opaque',
          'data':[{'date':'2026-10-10','model':'glm5.3-flash','total_tokens':4}],
          'totals':{'total_tokens':44000,'by_model':[{'model':'glm5.3-flash','total_tokens':40000,'prompt_tokens':25000,'completion_tokens':15000},
                   {'model':'deepseek-v4-flash','total_tokens':1000},{'model':'gemma4','total_tokens':3000}]}}
        snapshot=normalized_report(report,NOW,['nan_glm'])
        self.assertEqual(snapshot['consumed']['nan_glm'],40000)
        self.assertEqual(snapshot['consumed']['nan_qwen'],0)
        self.assertEqual(snapshot['consumed']['nan_ds'],1000)
        self.assertEqual(snapshot['verifiedOffers'],['nan_glm'])
        self.assertEqual(parse_models({'data':[{'id':'deepseek-v4-flash'},{'id':'qwen3.8-flash'},{'id':'glm5.3'}]}),['nan_qwen','nan_ds'])
        for broken in [{**report,'end_date':'2026-10-09'},
                       {**report,'totals':{'total_tokens':44000}},
                       {**report,'totals':{**report['totals'],'by_model':report['totals']['by_model']*2}},
                       {**report,'totals':{**report['totals'],'total_tokens':43999}}]:
            with self.assertRaises(ValueError):normalized_report(broken,NOW)
    def test_provider_usage_file_is_private_and_cannot_be_accidentally_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'month.json'
            private_write(path,usage(),False)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):private_write(path,usage('hypothetical',(),True),False)
            self.assertEqual(validate_usage(__import__('json').loads(path.read_text()))['source'],'provider-normalized')
            private_write(path,usage('hypothetical',(),True),True)
            self.assertEqual(validate_usage(__import__('json').loads(path.read_text()))['source'],'hypothetical')
    def test_concurrent_identical_task_id_only_reserves_once(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'state.sqlite';u=usage()
            def reserve(_):return choose(path,u,task(),NOW,write=True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                result=list(ex.map(reserve,range(8)))
            self.assertEqual(sum(x['status']=='selected' for x in result),1)
            self.assertEqual(sum(x['status']=='existing' for x in result),7)
    def test_observed_counter_reconciliation_does_not_double_count_settled_work(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'state.sqlite';u=usage()
            choose(path,u,task(),NOW,write=True)
            finish(path,'t1','settle',38000,NOW+timedelta(minutes=5))
            later=deepcopy(u);later['observedAt']='2026-10-10T12:10:00Z';later['consumed']['nan_ds']+=38000
            from nan_quota_dispatch import ledger
            conn=connect(path,False)
            try:self.assertEqual(ledger(conn,'2026-10',later['observedAt'])['reserved']['nan_ds'],0)
            finally:conn.close()
if __name__=='__main__':unittest.main()
