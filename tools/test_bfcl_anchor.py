"""Negative controls: recompressed self-consistency cannot authorize changed BFCL data."""
from __future__ import annotations
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_public_release import ROOT, verify_approved_bfcl_rows

class VerifiedBFCL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approved=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_bytes())['benchmarks']
    def test_approved_original_3241(self):
        r=verify_approved_bfcl_rows(self.approved)
        self.assertEqual(r['count'],3241)
    def test_ambiguous_json_duplicate_key_cannot_be_canonicalized(self):
        from strict_data_formats import json_loads_strict
        for malformed in (
            '{"benchmarks":[{"value":9.99,"value":77.47}]}',
            '{"measurements":[{"id":"synthetic","id":"approved"}]}',
        ):
            with self.assertRaisesRegex(ValueError,'Duplicate JSON key'):
                json_loads_strict(malformed)

    def test_single_changed_numeric_value_and_new_self_hash_fail(self):
        forged=copy.deepcopy(self.approved)
        forged[0]['value']=forged[0]['value']-0.7747
        # A refreshed JSON and delivery SHA would agree with this forged list;
        # the *independent* baseline must still reject it.
        with self.assertRaisesRegex(ValueError,'independently approved Git corpus'):
            verify_approved_bfcl_rows(forged)
    def test_reordered_or_replaced_identity_fails(self):
        for forged in [list(reversed(self.approved)),copy.deepcopy(self.approved)]:
            if forged[0] is not self.approved[-1]:
                forged[0]['measurement']['id']='observation-synthetic-fake'
            with self.assertRaises(ValueError):verify_approved_bfcl_rows(forged)
if __name__=='__main__':unittest.main()
