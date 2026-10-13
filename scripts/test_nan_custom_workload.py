"""Strict user-workload regressions, including parity-compatible UTF-8 fields."""
from __future__ import annotations
import unittest,json,tempfile
from pathlib import Path
from copy import deepcopy
from nan_custom_workload import new_custom_workload,validate_custom_workload,from_file,ROOT
from nan_static_profiles import derive_nan_static
from nan_static_hybrid import derive_nan_hybrid
from compile_nan_static_profile import compile_static
from profile_compiler import verify_native
class CustomWorkload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads((ROOT/'policies/nan-static-workloads.json').read_bytes())['scenarios']['mixed']['functionWorkload']
    def new(self,rows=None,label='Mi carga semanal',description='Hipótesis editable'):
        return new_custom_workload('mixed',label,description,rows or self.rows)
    def test_matches_browser_fingerprint_fixture(self):
        x=self.new()
        self.assertEqual(x['fingerprint'],'8b155d39d28f23f37ee76f5439be9810')
        self.assertEqual(len(x['functionWorkload']),20)
        self.assertEqual(x['functionWorkload'],self.rows)
    def test_source_is_never_mutated(self):
        before=deepcopy(self.rows)
        changed=deepcopy(self.rows);changed['bounded-implementation']['callsPerMonth']=777
        x=self.new(changed)
        self.assertNotEqual(x['fingerprint'],self.new()['fingerprint'])
        self.assertEqual(before,self.rows)
    def test_invalid_fields_numbers_and_duplicate_fingerprint_rejected(self):
        for mutate in [lambda x:x.update(apiKey='secret'),lambda x:x.update(policyId='older'),lambda x:x.update(sourceWorkloadSha256='0'*64),
                       lambda x:x.update(fingerprint='f'*32),
                       lambda x:x['functionWorkload'].pop('status-reporting'),
                       lambda x:x['functionWorkload'].update(unreviewed={'callsPerMonth':12,'totalTokensPerCall':30}),
                       lambda x:x['functionWorkload']['coordination'].update(callsPerMonth=-2),
                       lambda x:x['functionWorkload']['coordination'].update(callsPerMonth=1.5),
                       lambda x:x['functionWorkload']['coordination'].update(callsPerMonth=True),
                       lambda x:x['functionWorkload']['bounded-exploration'].update(totalTokensPerCall=0)]:
            x=self.new();mutate(x)
            with self.assertRaises(ValueError):validate_custom_workload(x)
    def test_emoji_and_accented_text_validate_same_utf16_limit_as_javascript(self):
        x=self.new(label='Mi escena 💡',description='Texto con símbolos Ω y 🦊')
        self.assertEqual(validate_custom_workload(x),x)
        for label in ['',' Inicio','a'*65,'A\nB','💡'*33,'\ud800']:
            with self.assertRaises(ValueError):self.new(label=label)
        with self.assertRaises(ValueError):self.new(description='\ud800')
    def test_zero_calls_valid_but_zero_workload_not_a_success_claim(self):
        rows=deepcopy(self.rows)
        for value in rows.values():value['callsPerMonth']=0
        x=self.new(rows)
        self.assertEqual(sum(v['callsPerMonth']*v['totalTokensPerCall'] for v in x['functionWorkload'].values()),0)
    def test_custom_scenario_changes_native_analysis_and_preserves_baselines(self):
        s=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_bytes())
        original=json.dumps(s['routeDetails'],sort_keys=True)
        rows=deepcopy(self.rows)
        rows['bounded-implementation']['callsPerMonth']*=4
        custom=self.new(rows)
        profile='gentle-shell--nan-research-balanced'
        initial=derive_nan_static(s,profile,'mixed',True)
        alternate=derive_nan_static(s,profile,'mixed',True,custom_workload=custom)
        self.assertNotEqual(initial['id'],alternate['id'])
        self.assertEqual(alternate['nanStaticPlan']['customWorkload'],custom)
        self.assertNotEqual(initial['nanStaticPlan']['expectedTokensAllEnabledRoles'],alternate['nanStaticPlan']['expectedTokensAllEnabledRoles'])
        self.assertEqual(json.dumps(s['routeDetails'],sort_keys=True),original)
        artifact=compile_static(s,profile,'mixed',True,custom_workload=custom)
        self.assertTrue(verify_native(artifact['manifest'],artifact['native']['content'].encode()))
        self.assertEqual(artifact['manifest']['nanStaticPlan']['customWorkload'],custom)
    def test_hybrid_custom_workload_and_base_mismatch_rejected(self):
        s=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_bytes())
        custom=self.new()
        alternate=derive_nan_hybrid(s,'omp--pro100-go-nan-research-balanced','mixed',True,complexity='bounded',mode='hybrid-worker',custom_workload=custom)
        self.assertEqual(alternate['nanStaticPlan']['customWorkload'],custom)
        with self.assertRaisesRegex(ValueError,'base scenario'):
            derive_nan_static(s,'omp--nan-research-balanced','routine',True,custom_workload=custom)
    def test_load_from_file_enforces_size_and_schema(self):
        x=self.new()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'scenario.json'
            p.write_text(json.dumps(x,ensure_ascii=False))
            self.assertEqual(from_file(p),x)
            p.write_bytes(b' '*65537)
            with self.assertRaises(ValueError):from_file(p)
            p.write_text(json.dumps({**x,'secret':'data'}))
            with self.assertRaises(ValueError):from_file(p)
if __name__=='__main__':unittest.main()
