"""Static hybrid NaN composition: function admission, quality budgets and native export."""
from __future__ import annotations
import json,unittest
from copy import deepcopy
from nan_static_hybrid import derive_nan_hybrid
from nan_static_profiles import load_static_policy
from compile_nan_static_profile import compile_static
from profile_compiler import verify_native
from access_catalog import ROOT
from harness_contracts import load_harnesses
from activity_allocation import derive_activity,load_policy
class HybridTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.s=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_text())
  cls.contracts=load_harnesses();cls.policy=load_policy()
 def make(self,h='omp',domain='research',objective='balanced',complexity='bounded',
          trials=True,mode='hybrid-worker',scenario='mixed',portfolio='pro100-go-nan',snapshot=None):
  return derive_nan_hybrid(snapshot or self.s,f'{h}--{portfolio}-{domain}-{objective}',scenario,trials,
    complexity,False,mode)
 def test_hybrid_preserves_inventory_and_reference_protection(self):
  for h in ['gentle-shell','omp']:
   pid=f'{h}--pro100-go-nan-research-balanced'
   p=self.make(h=h)
   base=derive_activity(pid,self.s['routeDetails'],self.s['meta'],self.s['portfolios'],
      self.s['runtimePolicies'],self.s['catalog'],self.contracts,
      {'complexity':'bounded','highImpact':False},self.policy)
   self.assertEqual(p['portfolio'],'pro100-go-nan')
   self.assertEqual(p['runtime'],base['runtime'])
   helpers={r['role'] for r in p['nanStaticPlan']['composition']['helperOffloads']}
   for role,new in p['routes'].items():
    old=base['routes'][role]
    fun=self.contracts[h]['roles'][role]['functionId']
    self.assertEqual(new['enabled'],old['enabled'])
    if fun in ('coordination','critical-review','independent-review','architecture','memory-maintenance'):
     self.assertEqual(new,old)
    if old['modelKey'] not in ('nan_glm','nan_ds','nan_mf','nan_qwen') and role not in helpers:
     self.assertEqual(new['modelKey'],old['modelKey'])
   self.assertTrue(helpers)
 def test_closed_helper_additions_are_explicit_and_versioned(self):
  for h,role in [('gentle-shell','gentle-ai-verify'),('omp','commit')]:
   p=self.make(h=h,mode='hybrid-assist')
   hset={x['role'] for x in p['nanStaticPlan']['composition']['helperOffloads']}
   self.assertIn(role,hset)
   self.assertTrue(p['nanStaticPlan']['composition']['sourceCoordinatorProfile'])
   self.assertIn('Híbrido NaN',p['routes'][role]['rationale'] if p['routes'][role]['modelKey']=='nan_glm' else p['routes'][role]['condition'])
 def test_worker_requires_bounded_complexity_and_opt_in(self):
  with self.assertRaisesRegex(ValueError,'bounded complexity'):
   self.make(complexity='standard')
  with self.assertRaisesRegex(ValueError,'High-impact'):
   derive_nan_hybrid(self.s,'omp--pro100-go-nan-research-balanced','mixed',True,'bounded',True,'hybrid-worker')
 def test_trials_are_not_automatic_and_quality_cap_depends_on_objective(self):
  for obj,cap in [('balanced',.30),('best',.15),('economy',.35)]:
   p=self.make(objective=obj,trials=True)
   self.assertEqual(p['nanStaticPlan']['qualityGuard']['trialShareCap'],cap)
   self.assertLessEqual(p['nanStaticPlan']['qualityGuard']['trialFractionOfExpectedNaN'],cap+1e-12)
  strict=self.make(trials=False)
  self.assertEqual(strict['nanStaticPlan']['qualityGuard']['trialExpectedTokens'],0)
 def test_sensitivity_is_explicit_scenario_not_statistical_interval(self):
  p=self.make()
  a=p['nanStaticPlan']['sensitivity']
  self.assertLessEqual(a['minimumCornerDistance'],a['maximumCornerDistance'])
  self.assertIn('not confidence',a['meaning'])
  self.assertFalse(p['nanStaticPlan']['workloadObserved'])
 def test_unsupported_access_and_domains_fail_closed(self):
  for domain in ('agent-use','cybersecurity'):
   with self.assertRaisesRegex(ValueError,'Excluded'):
    self.make(domain=domain)
  with self.assertRaises(ValueError):
   self.make(portfolio='nan')
 def test_approval_stale_does_not_reuse_old_hybrid_contract(self):
  s=deepcopy(self.s)
  s['access']['inputSha256']['policies/nan-static-composition.json']='0'*64
  with self.assertRaisesRegex(ValueError,'Snapshot is not pinned'):self.make(snapshot=s)
 def test_no_false_distinct_preset_on_same_roles(self):
  with self.assertRaisesRegex(ValueError,'No effective'):
   self.make(h='gentle-shell',complexity='standard',mode='hybrid-assist')
 def test_native_artifacts_for_two_harnesses_have_exact_origins(self):
  for h in ['gentle-shell','omp']:
   pid=f'{h}--pro100-go-nan-research-balanced'
   bundle=compile_static(self.s,pid,'mixed',True,composition_mode='hybrid-worker',complexity='bounded')
   self.assertTrue(verify_native(bundle['manifest'],bundle['native']['content'].encode()))
   self.assertEqual(bundle['manifest']['selectionPolicy'],'nan-hybrid')
   self.assertEqual(bundle['manifest']['nanStaticPlan']['composition']['mode'],'hybrid-worker')
   self.assertIn('nan/',bundle['native']['content'])
   self.assertEqual(bundle['manifest']['validation']['inferencesSent'],0)
if __name__=='__main__':unittest.main()
