"""Regression tests for assurance, history preflight and conservative taxonomy migration."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import hashlib,json,unittest
from unittest.mock import patch
import selection_candidates as selections
from profile_compiler import compile_request
from preflight_profile import ROOT,preflight,check_inputs,source_path
from profile_assurance import fallback_kind,assess_resolved
from migrate_nan_workload import migrate,old_fingerprint,OLD_SHA
from nan_custom_workload import new_custom_workload

class Remediation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.bundle=compile_request({'schemaVersion':1,'baseProfile':'omp--nan-agent-use-balanced','targetId':'omp@18.8.7','selectionPolicy':'matrix'})
 def test_current_artifact_not_operational_certificate(self):
  r=preflight(self.bundle['manifest'],self.bundle['native']['content'].encode(),'18.8.7')
  self.assertTrue(r['artifactCurrent']);self.assertFalse(r['readyForOperation']);self.assertEqual(r['providerCalls'],0)
 def test_version_drift_blocks_without_faking_breakage(self):
  r=preflight(self.bundle['manifest'],self.bundle['native']['content'].encode(),'18.9.2')
  self.assertFalse(r['artifactCurrent']);self.assertFalse(r['runtimeVersionMatches']);self.assertTrue(r['nativeHashMatches'])
 def test_stale_inputs_and_native_corruption_rejected(self):
  m=deepcopy(self.bundle['manifest']);m['inputsSha256']['contracts/harnesses.json']='0'*64
  self.assertFalse(preflight(m,self.bundle['native']['content'].encode())['artifactCurrent'])
  self.assertFalse(preflight(self.bundle['manifest'],b'corruption')['artifactCurrent'])
 def test_stripped_source_or_role_fields_cannot_pass(self):
  for change in ('inputs','roles','semantic'):
   m=deepcopy(self.bundle['manifest'])
   if change=='inputs':m['inputsSha256']={}
   elif change=='roles':m['roles'].pop('commit')
   else:m['roles']['judge']['functionId']='independent-review'
   if change=='inputs':
    with self.assertRaises(ValueError):preflight(m,self.bundle['native']['content'].encode())
   else:self.assertFalse(preflight(m,self.bundle['native']['content'].encode())['artifactCurrent'])
 def test_manifest_cannot_read_unrelated_local_files(self):
  for bad in ('../keys','/etc/passwd','catalog/../../secret','runtime/auth.json','data/private.json','scripts\\..\\auth.json'):
   with self.assertRaises(ValueError):source_path(ROOT,bad)
 def test_function_evidence_cannot_claim_unmeasured_calibration_or_omit_scope(self):
  policy=selections.load_review()[0];real_read=selections.read_json
  for change in ('missing','calibrated','foreign-reference','empty-criterion','empty-transfer'):
   candidate=deepcopy(policy);recipe=candidate['recipes'][0];key=next(iter(recipe['functionEvidence']));mapping=recipe['functionEvidence'][key]
   if change=='missing':recipe['functionEvidence'].pop(key)
   elif change=='calibrated':mapping['tier']='E3-direct';mapping['routeCalibration']='measured'
   elif change=='foreign-reference':mapping['evidenceRefs']=['observation-not-in-recipe']
   elif change=='empty-criterion':mapping['acceptanceCriterion']=''
   else:mapping['transferLimit']=''
   def reading(path):return candidate if path==ROOT/selections.POLICY else real_read(path)
   # Controlled in-memory fault after hash verification: exercise semantic guard,
   # never bless altered policy hashes or write a forged source approval.
   with patch.object(selections,'read_json',side_effect=reading):
    with self.assertRaises(ValueError):selections.load_review()
 def test_judge_is_classifier_not_independent_review(self):
  self.assertEqual(self.bundle['manifest']['roles']['judge']['functionId'],'auxiliary-classification')
  a=self.bundle['manifest']['assurance'];self.assertIn('uniform-auxiliary-effort',a['flags']);self.assertEqual(a['reviewIndependence'],'not-measured')
  self.assertIn('judge',a['auxiliariesMatchingCoordinator']);self.assertEqual(a['disabledRoles'],2)
 def test_effort_alternative_not_provider_failover(self):
  a={'selector':'synthetic/a','effort':'low','accessRouteId':'x','resourceId':'same'}
  self.assertEqual(fallback_kind(a,{**a,'effort':'high'}),'effort-alternative')
  self.assertEqual(fallback_kind(a,{**a,'resourceId':'other'}),'different-access-resource')
  self.assertEqual(fallback_kind(a,{**a,'selector':'synthetic/b'}),'different-model-same-access')
  self.assertEqual(fallback_kind(a,None),'none')
 def test_critical_panel_uniformity_not_hidden_by_other_reviewers(self):
  r={'selector':'synthetic/critical','effort':'high','accessRouteId':'x','offeringKey':'text','enabled':True,'fallback':None,'functionId':'critical-review'}
  other={**r,'functionId':'independent-review','selector':'synthetic/other'}
  summary=assess_resolved({'critical-a':r,'critical-b':deepcopy(r),'other-review':other},'gentle-shell','apps',{})
  self.assertEqual(summary['distinctReviewRoutes'],2);self.assertEqual(summary['distinctCriticalReviewRoutes'],1)
  self.assertIn('shared-review-route',summary['flags'])
 def test_visual_absence_and_review_uniformity_are_not_quality_scores(self):
  r={'selector':'synthetic/text','effort':'high','accessRouteId':'x','offeringKey':'text','enabled':True,'fallback':None,'functionId':'critical-review'}
  a=assess_resolved({'a':r,'b':deepcopy(r)},'gentle-shell','web',{'text':{'compatibility':{'vision':False}}})
  self.assertIn('no-image-route',a['flags']);self.assertIn('shared-review-route',a['flags']);self.assertEqual(a['routeCalibration'],'not-measured')
 def legacy(self):
  rows=json.loads((ROOT/'policies/nan-static-workloads.json').read_bytes())['scenarios']['mixed']['functionWorkload']
  old={k:v for k,v in rows.items() if k!='auxiliary-classification'}
  x={'schemaVersion':1,'kind':'nan-custom-workload','policyId':'nan-static-workload-v1','sourceWorkloadSha256':OLD_SHA,'baseScenario':'mixed','label':'Anterior','description':'Hipótesis antigua','functionWorkload':old}
  x['fingerprint']=old_fingerprint(x);return x
 def test_legacy_migration_requires_consent_and_preserves_old_rows(self):
  old=self.legacy();copy=deepcopy(old)
  with self.assertRaises(ValueError):migrate(old)
  new=migrate(old,True);self.assertEqual(old,copy);self.assertEqual(len(new['functionWorkload']),21)
  self.assertEqual({k:v for k,v in new['functionWorkload'].items() if k!='auxiliary-classification'},old['functionWorkload'])
  self.assertEqual(new['functionWorkload']['auxiliary-classification'],old['functionWorkload']['independent-review'])
 def test_legacy_migration_rejects_forgery_or_omissions(self):
  for change in ('fingerprint','unknown-function','old-schema'):
   x=self.legacy()
   if change=='fingerprint':x['fingerprint']='0'*32
   elif change=='unknown-function':x['functionWorkload']['new-unknown']={'callsPerMonth':1,'totalTokensPerCall':1}
   else:x['sourceWorkloadSha256']='0'*64
   with self.assertRaises(ValueError):migrate(x,True)
if __name__=='__main__':unittest.main()
