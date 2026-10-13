"""Functional allocation safety, deterministic provenance and CLI contracts."""
from collections import Counter
from copy import deepcopy
import json,unittest
from activity_allocation import ROOT,derive_activity,load_policy,validate_activity,validate_policy
from harness_contracts import load_harnesses
from profile_compiler import compile_request

class ActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=json.loads((ROOT/'dashboard/tests/fixtures/activity-fixture.json').read_text())
        cls.expected=json.loads((ROOT/'dashboard/tests/fixtures/activity-parity.json').read_text())
        cls.contracts=load_harnesses();cls.policy=load_policy()
    def derive(self,harness='gentle-shell',portfolio='pro100-go-nan',complexity='standard',high=False,domain='research'):
        s=self.s
        return derive_activity(f'{harness}--{portfolio}-{domain}-balanced',s['routeDetails'],s['meta'],s['portfolios'],s['runtimePolicies'],s['catalog'],self.contracts,{'complexity':complexity,'highImpact':high})
    def test_shared_parity_fixture_matches_current_python_policy(self):
        s=self.s
        for case in self.expected:
            actual=derive_activity(case['profileId'],s['routeDetails'],s['meta'],s['portfolios'],s['runtimePolicies'],s['catalog'],self.contracts,case['settings'])
            self.assertEqual(actual,case['result'])
    def test_requested_inventory_uses_go_and_nan_for_distinct_responsibilities(self):
        for harness in ['gentle-shell','omp']:
            result=self.derive(harness)
            pools=Counter(self.s['catalog'][r['modelKey']]['pool'] for r in result['routes'].values() if r['enabled'])
            self.assertEqual(set(pools),{'OAI','GO','NAN'})
            self.assertEqual(result['coordinatorPool'],'OAI')
    def test_complexity_reduces_changed_roles_without_disabling_them(self):
        for harness in ['gentle-shell','omp']:
            variants=[self.derive(harness,complexity=l) for l in ['bounded','standard','complex']]
            counts=[len(v['activityPlan']['changes']) for v in variants]
            self.assertGreater(counts[0],counts[1]);self.assertGreater(counts[1],counts[2])
            self.assertEqual(len({sum(r['enabled'] for r in v['routes'].values()) for v in variants}),1)
    def test_protected_roles_and_runtime_remain_byte_equivalent(self):
        for harness in ['gentle-shell','omp']:
            v=self.derive(harness,complexity='bounded');base=self.s['routeDetails'][v['sourceProfile']]
            for role,contract in self.contracts[harness]['roles'].items():
                if role in base and (contract['functionId'] in self.policy['protectedFunctions'] or not base[role]['enabled']):self.assertEqual(base[role],v['routes'][role])
            self.assertEqual(v['runtime'],self.s['runtimePolicies'][v['sourceProfile']])
    def test_high_impact_cannot_be_bypassed_by_bounded_complexity(self):
        v=self.derive(complexity='bounded',high=True)
        self.assertEqual(v['routes'],self.s['routeDetails'][v['sourceProfile']]);self.assertEqual(v['activityPlan']['changes'],[])
        self.assertEqual(v['activityPlan']['blockedReason'],'high-impact')
    def test_agent_use_blocked_separately_from_complexity(self):
        v=self.derive(domain='agent-use',complexity='bounded')
        self.assertEqual(v['routes'],self.s['routeDetails'][v['sourceProfile']]);self.assertEqual(v['activityPlan']['blockedReason'],'domain-not-approved')
    def test_unavailable_nan_is_never_invented(self):
        v=self.derive(portfolio='pro100-go')
        self.assertNotIn('NAN',{c['pool'] for c in v['activityPlan']['changes']})
    def test_exact_claude_and_openai_tiers_are_preserved(self):
        for portfolio in ['pro100-claude-go-nan','pro100-claude-max-go-nan']:
            v=self.derive(portfolio=portfolio,complexity='bounded')
            self.assertTrue(v['sourceProfile'].startswith('gentle-shell--pro100-'))
            changes=[c for c in v['activityPlan']['changes'] if c['pool']=='ANTHROPIC']
            self.assertTrue(changes)
            self.assertEqual('claude-max' in changes[0]['sourceProfile'],'claude-max' in portfolio)
    def test_source_inputs_are_immutable_and_reserves_keep_original_origins(self):
        before=deepcopy(self.s);v=self.derive(complexity='bounded')
        self.assertEqual(before,self.s)
        for c in v['activityPlan']['changes']:
            r=v['routes'][c['role']];original=self.s['routeDetails'][v['sourceProfile']][c['role']]
            self.assertEqual(r['fallback'],{k:original[k] for k in ['modelKey','effort','origin']})
            self.assertIn(c['sourceProfile'],r['rationale'])
    def test_no_false_effort_is_assigned_to_nan_deepseek(self):
        v=self.derive();r=v['routes']['gentle-ai-explore'];self.assertEqual(r['effort'],'')
    def test_policy_cannot_demote_reviewers_or_invent_donor_functions(self):
        p=deepcopy(self.policy);p['levels']['bounded']['functions'].append('critical-review')
        with self.assertRaisesRegex(ValueError,'protected'):validate_policy(p)
        p=deepcopy(self.policy);p['preferredPools']['bounded-implementation']=['unsubscribed-api']
        with self.assertRaises(ValueError):validate_policy(p)
        p=deepcopy(self.policy);p['coordinatorPriority'].append('OAI')
        with self.assertRaises(ValueError):validate_policy(p)

    def test_invalid_settings_fail_closed(self):
        for value in [None,{}, {'complexity':'easy','highImpact':False},{'complexity':{},'highImpact':False},{'complexity':'bounded','highImpact':0},{'complexity':'bounded','highImpact':False,'force':True}]:
            with self.assertRaises(ValueError):validate_activity(value,self.policy)
    def test_single_pool_cannot_claim_collaboration(self):
        with self.assertRaisesRegex(ValueError,'two'):self.derive(portfolio='pro100')
    def test_cli_manifest_has_functional_provenance_without_installing_anything(self):
        req={'schemaVersion':1,'baseProfile':'gentle-shell--pro100-go-nan-research-balanced','targetId':'gentle-shell@4.0.0+pi@1.1.0','selectionPolicy':'activity-distributed','activity':{'complexity':'standard','highImpact':False}}
        result=compile_request(req);m=result['manifest']
        self.assertEqual(m['status'],'candidate');self.assertEqual(m['activityPlan']['complexity'],'standard')
        self.assertEqual(m['roles']['gentle-ai-worker']['accessRouteId'],'opencode-go')
        self.assertEqual(m['roles']['gentle-ai-explore']['accessRouteId'],'nan')
        self.assertEqual(m['validation']['inferencesSent'],0)
        self.assertIn('policies/activity-allocation.json',m['inputsSha256'])
        self.assertIn('activity-standard',m['profileName'])
        self.assertEqual(m['roles']['gentle-ai-worker']['decisionEvidence']['kind'],'policy-derived-candidate')
    def test_donor_source_ids_are_distinct_from_coordinator_evidence(self):
        req={'schemaVersion':1,'baseProfile':'gentle-shell--pro100-go-nan-research-balanced','targetId':'gentle-shell@4.0.0+pi@1.1.0','selectionPolicy':'activity-distributed','activity':{'complexity':'standard','highImpact':False}}
        m=compile_request(req)['manifest'];e=m['roles']['gentle-ai-worker']['decisionEvidence']
        self.assertEqual(e['sourceProfile'],'gentle-shell--pro100-research-balanced')
        self.assertEqual(e['donorProfile'],'gentle-shell--go-research-balanced')
        self.assertIn('OAI',e['sourceIds']);self.assertIn('GO',e['donorSourceIds'])
        self.assertNotEqual(e['sourceIds'],e['donorSourceIds'])
        self.assertIsInstance(e['donorDecisionId'],str)
        self.assertNotIn('donorProfile',m['roles']['orchestrator']['decisionEvidence'])

    def test_other_policies_must_not_silently_ignore_activity(self):
        with self.assertRaisesRegex(ValueError,'activity only'):
            compile_request({'schemaVersion':1,'baseProfile':'gentle-shell--pro100-research-balanced','targetId':'gentle-shell@4.0.0+pi@1.1.0','activity':{'complexity':'bounded','highImpact':False}})

if __name__=='__main__':unittest.main()
