"""Regression checks for active role contracts and preserved decision precedents."""
import csv, hashlib, json, unittest
from pathlib import Path
from harness_contracts import load_harnesses, roles_for, bounded_roles
from prepare_data import load_decisions, partition_decisions
from generate_native_profiles import native_text
ROOT=Path(__file__).resolve().parents[1]

class ContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts=load_harnesses()
        cls.decisions,_=load_decisions()
        cls.active,cls.retired=partition_decisions(cls.decisions,cls.contracts)
    def test_gentle_role_contract(self):
        self.assertEqual(len(self.contracts['gentle-shell']['roles']),13)
        self.assertEqual(len(roles_for(self.contracts['gentle-shell'],'agent-use','balanced')),11)
        self.assertEqual(bounded_roles(self.contracts['gentle-shell']),{'gentle-ai-explore'})
    def test_retired_decisions_are_preserved_but_not_active(self):
        self.assertEqual(len(self.retired),16224)
        self.assertEqual(len(self.active),33414)
        self.assertEqual(len({r['profile_id'] for r in self.active}),2496)
        self.assertTrue(all(not r['role'].startswith('sdd-') for r in self.active))
    def test_active_data_exactly_preserves_remaining_decisions(self):
        with (ROOT/'data/assignments.csv').open(encoding='utf-8-sig',newline='') as fh:
            self.assertEqual(list(csv.DictReader(fh)),self.active)
    def test_portable_precedents_cover_every_retired_assignment(self):
        data=json.loads((ROOT/'policies/functional-precedents.json').read_text())
        self.assertEqual(data['sourceDecisions'],len(self.retired))
        self.assertEqual(sum(len(p['sourceProfiles']) for p in data['precedents'].values()),len(self.retired))
        self.assertEqual(data['status'],'precedents-not-calibration')
    def test_unknown_roles_fail_closed(self):
        row={**self.active[0],'role':'invented-role'}
        with self.assertRaises(ValueError):partition_decisions([row],self.contracts)
    def test_unknown_harness_fails_closed(self):
        row={**self.active[0],'harness':'unknown'}
        with self.assertRaises(ValueError):partition_decisions([row],self.contracts)
    def test_unknown_native_harness_is_not_treated_as_omp(self):
        with self.assertRaises(ValueError):native_text('demo','unknown',{},None)
    def test_profile_name_must_be_safe(self):
        for name in ['../unsafe','constructor','a'*65]:
            with self.assertRaises(ValueError):native_text(name,'gentle-shell',{})
    def test_pinned_parser_matches_upstream_blobs(self):
        expected={'agent-profiles.ts':'f4c953460160b7198dd8d6293f9cb43050826ea6',
                  'model-routing-authority.ts':'ee2a30c021e622853338e293506e5875b1a11be7'}
        for name,sha in expected.items():
            data=(ROOT/'tests/vendor/gentle-shell-4.0.0'/name).read_bytes()
            self.assertEqual(hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest(),sha)

if __name__=='__main__':unittest.main()
