import unittest,json
from score_calibration_response import ROOT,score
class OracleTests(unittest.TestCase):
    def fixtures(self):return json.loads((ROOT/'evaluations/fixtures/pilot.json').read_text())['fixtures']
    def test_synthetic_expected_responses_pass_without_becoming_model_runs(self):
        for f in self.fixtures():
            r=score(f,f['expected'],'synthetic-oracle-test');self.assertTrue(r['strictPass']);self.assertFalse(r['roleCalibrationEstablished']);self.assertEqual(r['modelCalls'],0)
    def test_missing_extra_wrong_types_fail(self):
        for f in self.fixtures():
            self.assertFalse(score(f,{},'synthetic-oracle-test')['strictPass'])
        f=self.fixtures()[0];bad={**f['expected'],'total_trials':True};self.assertFalse(score(f,bad,'synthetic-oracle-test')['strictPass'])
    def test_unweighted_rates_and_hallucinated_gamma_fail(self):
        f=self.fixtures()[0];self.assertFalse(score(f,{**f['expected'],'overall':(.9+1/90)/2},'synthetic-oracle-test')['strictPass'])
        f=self.fixtures()[2];self.assertFalse(score(f,{**f['expected'],'gamma':7},'synthetic-oracle-test')['strictPass'])
    def test_review_oracle_penalizes_a_redundant_but_harmless_zero_filter_claim(self):
        f=self.fixtures()[1]
        self.assertFalse(score(f,['empty-input','missing-denominator','zero-removal'],'synthetic-oracle-test')['strictPass'])
    def test_invented_verified_model_kind_is_rejected(self):
        with self.assertRaises(ValueError):score(self.fixtures()[0],{},'verified-model-execution')
if __name__=='__main__':unittest.main()
