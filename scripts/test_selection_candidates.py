"""Reviewed selection regressions: exact evidence, constraints and artifact parity."""
from copy import deepcopy
from pathlib import Path
import json,tempfile,unittest
from selection_candidates import load_review,derive_candidate,validate_review_evidence,ROOT
from compile_reviewed_candidate import compile_candidate
from profile_compiler import verify_native
class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review=load_review();full=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_text())
        # Explicit test subset, not an independently measured benchmark dataset.
        refs=set(cls.review[1]['observations']);cls.s={k:full[k] for k in ['catalog','portfolios','access','domainContracts']}
        ids=[h+'--'+p+'-'+d+'-balanced' for h in ['gentle-shell','omp'] for p in ['claude-pro','pro100-go-nan','pro100-claude-go-nan','nan','go'] for d in ['research','agent-use']]
        for key in ['meta','routeDetails','runtimePolicies']:cls.s[key]={id:full[key][id] for id in ids if id in full[key]}
        cls.s['benchmarks']=[r for r in full['benchmarks'] if r['measurement']['id'] in refs]
        cls.s['benchmarkRegistry']=full['benchmarkRegistry']
    def derive(self,h='gentle-shell',p='pro100-claude-go-nan',recipe='haiku-worker',offering='cl_haiku',complexity='standard',high=False,s=None,domain='research'):
        return derive_candidate(s or self.s,h+'--'+p+'-'+domain+'-balanced',recipe,offering,{'complexity':complexity,'highImpact':high})
    def test_exact_reviewed_cells_resolve_to_current_evidence(self):
        self.assertEqual(validate_review_evidence(self.s)['observations'],42)
    def test_haiku_gets_real_worker_roles_in_both_harnesses(self):
        for h,role in [('gentle-shell','gentle-ai-worker'),('omp','task')]:
            p=self.derive(h=h);self.assertEqual(p['routes'][role]['modelKey'],'cl_haiku');self.assertEqual(p['routes'][role]['effort'],'medium')
    def test_single_claude_subscription_can_propose_haiku(self):
        p=self.derive(p='claude-pro');self.assertTrue(p['selectionReview']['changes']);self.assertEqual(p['coordinatorPool'],'ANTHROPIC')
    def test_no_implicit_haiku_without_claude_access(self):
        with self.assertRaisesRegex(ValueError,'subscription'):self.derive(p='pro100-go-nan')
    def test_high_impact_and_excluded_domains_block_proposal(self):
        for kwargs in [{'high':True},{'domain':'agent-use'}]:
            with self.assertRaisesRegex(ValueError,'not admitted'):self.derive(**kwargs)
    def test_complex_activity_does_not_delegate_implementation(self):
        with self.assertRaisesRegex(ValueError,'not admitted'):self.derive(complexity='complex')
        p=self.derive(recipe='haiku-small',complexity='complex')
        self.assertNotIn('gentle-ai-worker',{c['role'] for c in p['selectionReview']['changes']})
    def test_protected_roles_conditions_and_original_fallbacks_survive(self):
        for h in ['gentle-shell','omp']:
            p=self.derive(h=h);old=self.s['routeDetails'][p['sourceProfile']]
            changed={c['role'] for c in p['selectionReview']['changes']}
            for role,r in p['routes'].items():
                if role not in changed:self.assertEqual(r,old[role])
                else:
                    self.assertEqual(r['fallback'],{k:old[role][k] for k in ['modelKey','effort','origin']})
                    self.assertIn(self.s['domainContracts']['research']['gate'],r['condition'])
            self.assertEqual(p['runtime'],self.s['runtimePolicies'][p['sourceProfile']])
    def test_nan_mimo_is_conditional_and_never_receives_graduated_effort(self):
        p=self.derive(p='nan',recipe='mimo-nan-worker',offering='nan_mf')
        self.assertEqual(p['selectionReview']['admission'],'conditional-access-route')
        self.assertTrue(all(c['toEffort']=='' for c in p['selectionReview']['changes']))
    def test_qwen_alias_and_historical_model_cannot_enter_other_recipes(self):
        for offer in ['nan_qwen','nan_mimo']:
            with self.assertRaisesRegex(ValueError,'pairing'):self.derive(p='nan',recipe='mimo-nan-worker',offering=offer)
    def test_changed_evidence_or_protocol_fails_closed(self):
        for field in ['value','measurement','protocol']:
            s={**self.s,'benchmarks':deepcopy(self.s['benchmarks']),'benchmarkRegistry':deepcopy(self.s['benchmarkRegistry'])}
            row=s['benchmarks'][0]
            if field=='value':row['value']+=1
            elif field=='measurement':row['measurement']['issueIds'].append('test-issue')
            else:s['benchmarkRegistry']['protocols'][row['measurement']['protocolId']]['harness']='different-harness'
            with self.assertRaisesRegex(ValueError,'changed'):validate_review_evidence(s)
    def test_missing_duplicate_and_historical_evidence_are_rejected(self):
        for rows in [self.s['benchmarks'][1:],self.s['benchmarks']+[self.s['benchmarks'][0]]]:
            with self.assertRaises(ValueError):validate_review_evidence({**self.s,'benchmarks':rows})
    def test_stale_review_hash_or_target_cannot_be_reused(self):
        s=deepcopy(self.s);s['access']['inputSha256']['policies/selection-evidence.json']='0'*64
        with self.assertRaisesRegex(ValueError,'regenerate'):self.derive(s=s)
        s=deepcopy(self.s);s['meta']['gentle-shell--pro100-claude-go-nan-research-balanced']['runtime']['version']='unknown'
        with self.assertRaisesRegex(ValueError,'runtime'):self.derive(s=s)
    def test_input_is_not_mutated_and_low_is_not_max_in_disguise(self):
        before=deepcopy(self.s);p=self.derive(h='omp',recipe='haiku-small');self.assertEqual(self.s,before)
        self.assertEqual({c['toEffort'] for c in p['selectionReview']['changes']},{'low'})
    def test_cli_compiler_preserves_candidate_and_exact_evidence_manifest(self):
        p=compile_candidate(self.s,'gentle-shell--pro100-claude-go-nan-research-balanced','haiku-worker','cl_haiku',{'complexity':'standard','highImpact':False})
        self.assertTrue(verify_native(p['manifest'],p['native']['content'].encode()))
        self.assertEqual(p['manifest']['roles']['gentle-ai-worker']['effort'],'medium')
        self.assertEqual(p['manifest']['selectionPolicy'],'reviewed-candidate')
        self.assertEqual(len(p['manifest']['selectionReview']['evidence']),7)
        self.assertEqual(p['manifest']['validation']['inferencesSent'],0)
if __name__=='__main__':unittest.main()
