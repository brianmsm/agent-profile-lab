"""Adversarial tests of native fixed selectors, quota shares and role eligibility."""
from __future__ import annotations
from copy import deepcopy
import json,unittest
from nan_static_profiles import derive_nan_static,load_static_policy,ROOT
from compile_nan_static_profile import compile_static
from profile_compiler import verify_native
class StaticProfiles(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    raw=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_text())
    keys=['meta','routeDetails','runtimePolicies','portfolios','catalog','access','domainContracts','strategies']
    cls.s={k:raw[k] for k in keys}
 def derive(self,h='gentle-shell',portfolio='nan',scenario='mixed',trials=True,domain='research',objective='balanced',snapshot=None):
    return derive_nan_static(snapshot or self.s,f'{h}--{portfolio}-{domain}-{objective}',scenario,trials)
 def test_quality_policy_and_approval_inputs_are_versioned(self):
    p,a,*_=load_static_policy()
    self.assertEqual(p['schemaVersion'],1)
    self.assertEqual(set(p['scenarios']),{'routine','mixed','implementation'})
    self.assertEqual(a['id'],p['id'])
 def test_four_model_quota_shares_sum_to_one(self):
    for h in ['gentle-shell','omp']:
     for scenario in ['routine','mixed','implementation']:
      p=self.derive(h=h,scenario=scenario)
      plan=p['nanStaticPlan']
      rows=plan['byModel']
      self.assertAlmostEqual(sum(r['expectedTokenShare'] for r in rows.values()),1)
      self.assertAlmostEqual(sum(r['targetQuotaShare'] for r in rows.values()),1)
      self.assertAlmostEqual(plan['distanceFromQuotaTarget'],0.5*sum(abs(r['expectedTokenShare']-r['targetQuotaShare']) for r in rows.values()),12)
      self.assertEqual(plan['expectedTokensOnNaN'],sum(r['expectedTokens'] for r in rows.values()))
      self.assertTrue(plan['quotasStartAtFull'])
      self.assertFalse(plan['workloadObserved'])
 def test_trial_requires_optin(self):
    for h in ['gentle-shell','omp']:
     p=self.derive(h=h,trials=False)
     self.assertFalse(any(c['toModelKey'] in ('nan_mf','nan_qwen') for c in p['nanStaticPlan']['changes']))
     self.assertLessEqual(len(set(c['toModelKey'] for c in p['nanStaticPlan']['changes'])),2)
 def test_four_model_mixed_profile_is_admissible_but_not_guaranteed(self):
    p=self.derive()
    self.assertEqual({k for k,v in p['nanStaticPlan']['byModel'].items() if v['expectedTokens']>0},{'nan_ds','nan_glm','nan_mf','nan_qwen'})
    self.assertGreater(p['nanStaticPlan']['distanceFromQuotaTarget'],0)
 def test_all_non_changed_roles_and_runtime_are_exact(self):
    for h in ['gentle-shell','omp']:
     p=self.derive(h=h)
     source=self.s['routeDetails'][p['sourceProfile']]
     changed={c['role'] for c in p['nanStaticPlan']['changes']}
     self.assertEqual(p['runtime'],self.s['runtimePolicies'][p['sourceProfile']])
     for role,r in p['routes'].items():
      self.assertEqual(r['enabled'],source[role]['enabled'])
      if role not in changed:self.assertEqual(r,source[role])
      else:
       expected_fallback=source[role]['fallback'] if source[role]['fallback'] else {k:source[role][k] for k in ('modelKey','effort','origin')}
       if expected_fallback['modelKey']==r['modelKey'] and expected_fallback['effort']==r['effort']:expected_fallback=None
       self.assertEqual(r['fallback'],expected_fallback)
       self.assertIn(self.s['domainContracts']['research']['gate'],r['condition'])
 def test_no_spoofing_nan_if_subscription_absent(self):
    with self.assertRaisesRegex(ValueError,'include NaN'):self.derive(portfolio='pro100')
 def test_high_impact_and_security_domains_are_blocked(self):
    for dom in ['agent-use','cybersecurity']:
     with self.assertRaisesRegex(ValueError,'excluded'):self.derive(domain=dom)
    with self.assertRaisesRegex(ValueError,'excluded'):derive_nan_static(self.s,'gentle-shell--nan-research-balanced','mixed',True,True)
 def test_stale_review_or_catalog_fails_closed(self):
    s=deepcopy(self.s)
    s['access']['inputSha256']['policies/nan-static-workloads.json']='0'*64
    with self.assertRaisesRegex(ValueError,'regenerate'):self.derive(snapshot=s)
    s=deepcopy(self.s)
    s['meta']['gentle-shell--nan-research-balanced']['runtime']['version']='0.0.0'
    with self.assertRaisesRegex(ValueError,'runtime'):self.derive(snapshot=s)
 def test_original_snapshot_not_mutated(self):
    prior=deepcopy(self.s)
    self.derive()
    self.assertEqual(prior,self.s)
 def test_different_scenarios_are_distinct_hypotheses(self):
    profiles=[self.derive(scenario=k) for k in ['routine','mixed','implementation']]
    self.assertEqual(len({p['id'] for p in profiles}),3)
    self.assertEqual(len({p['nanStaticPlan']['distanceFromQuotaTarget'] for p in profiles}),3)
 def test_static_export_preserves_exact_model_effort_and_conditions(self):
    for h in ['gentle-shell','omp']:
     id=f'{h}--nan-research-balanced'
     bundle=compile_static(self.s,id,'mixed',True)
     self.assertTrue(verify_native(bundle['manifest'],bundle['native']['content'].encode()))
     self.assertEqual(bundle['manifest']['selectionPolicy'],'nan-static')
     plan=bundle['manifest']['nanStaticPlan'];self.assertEqual(plan['state'],'candidate-not-calibrated')
     for row in plan['changes']:
      role=row['role'];detail=bundle['manifest']['roles'][role]
      self.assertEqual(detail['modelId'],self.s['catalog'][row['toModelKey']]['modelId'])
      self.assertEqual(detail['effort'],row['toEffort'])
      self.assertIn('Selector estático hipotético',detail['condition'])
if __name__=='__main__':unittest.main()
