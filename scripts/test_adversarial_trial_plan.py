import json,unittest
from pathlib import Path
from build_adversarial_trial_plan import ROOT,trial_plan
from score_calibration_response import score
class PlanTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.snapshot=json.loads((ROOT/'dashboard/tests/fixtures/access-snapshot.json').read_bytes())
 def profile(self):return next(k for k,v in self.snapshot['meta'].items() if v['harness']=='omp')
 def test_paired_plans_are_reproducible_not_executed(self):
  a=trial_plan(self.snapshot,self.profile(),['commit','tiny'],2,7);b=trial_plan(self.snapshot,self.profile(),['commit','tiny'],2,7)
  self.assertEqual(a,b);self.assertGreater(len(a['rows']),0);self.assertEqual(a['modelCalls'],0)
  self.assertFalse(a['authorization']['spendApproved']);self.assertTrue(all(r['result'] is None and r['accepted'] is None for r in a['rows']))
  for key in {r['pairId'] for r in a['rows']}:self.assertEqual(sum(r['arm']=='baseline' for r in a['rows'] if r['pairId']==key),1)
 def test_unknown_or_disabled_roles_not_silently_skipped(self):
  for ids in (['not-a-role'],['commit','commit'],['advisor']):
   with self.assertRaises(ValueError):trial_plan(self.snapshot,self.profile(),ids)
 def test_oracle_positive_negative_never_promotes_model(self):
  fixtures=json.loads((ROOT/'evaluations/fixtures/adversarial-roles.json').read_bytes())['fixtures']
  known=json.loads((ROOT/'policies/functions.json').read_bytes())['functions']
  for f in fixtures:
   self.assertTrue(set(f['functions'])<=set(known))
   good=score(f,f['expected'],'synthetic-oracle-test');bad=score(f,{'invented':'result'},'synthetic-oracle-test')
   self.assertTrue(good['strictPass']);self.assertFalse(bad['strictPass']);self.assertFalse(good['roleCalibrationEstablished'])
 def test_no_inference_budget_generated_implicitly(self):
  a=trial_plan(self.snapshot,self.profile(),['plan'],2)
  self.assertIsNone(a['authorization']['budget']);self.assertFalse(a['authorization']['inferenceApproved'])
if __name__=='__main__':unittest.main()
