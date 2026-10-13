"""Independent regressions for semantic errors missed by shape-only validators."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import csv,json,unittest
import profile_compiler as pc
from profile_semantics import critical_review_config,require_distinct_reserves
from access_catalog import load_catalog
from harness_contracts import load_harnesses
from activity_allocation import derive_activity
ROOT=Path(__file__).resolve().parents[1]
class SemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=load_catalog();cls.contracts=load_harnesses()
        cls.g=pc.load_baseline('gentle-shell--plus-apps-balanced','matrix',ROOT,cls.catalog,cls.contracts)
        cls.o=pc.load_baseline('omp--plus-cc-apps-balanced','matrix',ROOT,cls.catalog,cls.contracts)
    def compile(self,base=None,**kwargs):
        base=deepcopy(base or self.g)
        req={'schemaVersion':1,'targetId':'omp@18.8.7' if base['harness']=='omp' else 'gentle-shell@4.0.0+pi@1.1.0','baseProfile':base['profileId'],**kwargs}
        with patch.object(pc,'load_baseline',return_value=base):return pc.compile_request(req)
    def test_critical_variant_never_lowers_high_xhigh_or_max(self):
        for effort in ['low','medium','high','xhigh','max']:
            config={'review':{'model':'x/model','thinking':effort},'worker':{'model':'x/model','thinking':'low'}}
            catalog={'x/model':{'allowed_efforts':['low','medium','high','xhigh','max']}}
            before=deepcopy(config);out=critical_review_config(config,['review'],catalog)
            self.assertEqual(out['review']['thinking'],{'low':'high','medium':'high','high':'high','xhigh':'xhigh','max':'max'}[effort])
            self.assertEqual(out['worker'],config['worker']);self.assertEqual(config,before)
    def test_critical_variant_cannot_invent_effort_for_ungraded_route(self):
        config={'review':{'model':'x/ungraded'}}
        self.assertEqual(critical_review_config(config,['review'],{'x/ungraded':{'allowed_efforts':[]}}),config)
    def test_critical_variant_rejects_unsupported_or_unordered_source_effort(self):
        for catalog in [{'x/model':{'allowed_efforts':['low']}},{'x/model':{'allowed_efforts':['ultra']}}]:
            with self.assertRaises(ValueError):critical_review_config({'review':{'model':'x/model','thinking':'high'}},['review'],catalog)
    def test_visual_primary_override_requires_image_capability(self):
        with self.assertRaisesRegex(ValueError,'declared image'):
            self.compile(self.o,roles={'vision':{'modelId':'xiaomi:mimo-v2.6-flash','accessRouteId':'command-goat','effort':'','reason':'Test incompatible override'}})
    def test_visual_fallback_override_requires_image_capability(self):
        with self.assertRaisesRegex(ValueError,'declared image'):
            self.compile(self.o,roles={'vision':{'reason':'Test reserve','fallback':{'modelId':'xiaomi:mimo-v2.6-pro','accessRouteId':'command-goat','effort':'','reason':'Text-only reserve should fail'}}})
    def test_auxiliary_mixed_auth_namespace_rejected_even_with_spend_consent(self):
        resources=[{'id':'chatgpt-main','accessRouteId':'chatgpt-siwc','credentialRef':'chatgpt-main','plan':'plus'},{'id':'api-test','accessRouteId':'openai-api','credentialRef':'api-test','plan':'metered'}]
        with self.assertRaisesRegex(ValueError,'Ambiguous provider'):
            self.compile(resources=resources,accessRemap={'chatgpt-legacy':'chatgpt-siwc'},meteredAuthorization={'allowed':True,'maxAmount':1,'currency':'USD'},roles={'orchestrator':{'reason':'Test','fallback':{'modelId':'openai:gpt-6.1-sol','accessRouteId':'openai-api','resourceId':'api-test','effort':'high','reason':'Distinct API account'}}})
    def test_reserve_override_justification_is_preserved(self):
        result=self.compile(roles={'orchestrator':{'reason':'A deliberate candidate','fallback':{'modelId':'openai:gpt-6.1-sol','accessRouteId':'chatgpt-legacy','effort':'max','reason':'Budgeted escalation after failed acceptance gate'}}})
        self.assertEqual(result['manifest']['roles']['orchestrator']['fallback']['rationale'],'Budgeted escalation after failed acceptance gate')
    def test_same_effective_route_cannot_be_its_own_fallback(self):
        row=self.g['routes']['orchestrator'];offer=self.catalog['offerings'][row['modelKey']]
        with self.assertRaisesRegex(ValueError,'repeats the same'):
            self.compile(roles={'orchestrator':{'reason':'Test duplicate','fallback':{'modelId':offer['modelId'],'accessRouteId':offer['defaultAccessRouteId'],'effort':row['effort'],'reason':'Identical route is not resilience'}}})
    def test_same_model_other_effort_or_other_resource_is_not_equated(self):
        primary={'selector':'x/model','effort':'medium','accessRouteId':'r','resourceId':'one','credentialRef':'one','plan':'p'}
        for field,value in [('effort','high'),('resourceId','two')]:
            require_distinct_reserves({**primary,'fallback':{**primary,field:value}},'test')
    def test_default_filenames_distinguish_selection_policy(self):
        outputs=[self.compile(selectionPolicy=policy)['native']['filename'] for policy in ['matrix','openai-led','nan-volume']]
        self.assertEqual(len(set(outputs)),3)
    def test_nan_strategy_cannot_invent_a_subscription_from_a_policy_name(self):
        with self.assertRaisesRegex(ValueError,'cannot invent a subscription'):
            pc.load_baseline('gentle-shell--plus-apps-balanced','nan-volume',ROOT,self.catalog,self.contracts)
        valid=pc.load_baseline('gentle-shell--plus-nan-apps-balanced','nan-volume',ROOT,self.catalog,self.contracts)
        self.assertEqual(valid['portfolio']['nan'],'True')
    def test_donor_specific_conditions_are_not_discarded(self):
        s=json.loads((ROOT/'dashboard/tests/fixtures/activity-fixture.json').read_text());pid='gentle-shell--pro100-go-nan-research-balanced'
        s['routeDetails']['gentle-shell--go-research-balanced']['gentle-ai-worker']['condition']+=' Extra restriction: bounded files only.'
        r=derive_activity(pid,s['routeDetails'],s['meta'],s['portfolios'],s['runtimePolicies'],s['catalog'],self.contracts,{'complexity':'standard','highImpact':False})
        condition=r['routes']['gentle-ai-worker']['condition']
        self.assertIn('Extra restriction: bounded files only.',condition);self.assertIn(s['domainContracts']['research']['gate'],condition)
    def test_active_source_rows_have_own_domain_gate_not_copied_app_gate(self):
        domains=json.loads((ROOT/'data/domain-objective-contracts.json').read_text())['domains']
        with (ROOT/'data/assignments.csv').open(encoding='utf-8-sig',newline='') as file:
            for row in csv.DictReader(file):self.assertIn(domains[row['domain']]['gate'],row['quality_gate'],row['profile_id']+'/'+row['role'])
if __name__=='__main__':unittest.main()
