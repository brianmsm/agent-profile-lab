"""Independent exhaustive oracle for bounded 12-15-role NaN static allocations."""
from __future__ import annotations
import itertools,unittest
from nan_quota_balance import KEYS
from nan_quota_optimizer import solve_exact_expanded
QUOTAS={'nan_qwen':500,'nan_ds':3000,'nan_mf':1000,'nan_glm':2000}
FIXED={k:0 for k in KEYS}
def oracle(rows,fixed=FIXED,cap=0):
    Q=sum(QUOTAS.values());total=sum(fixed.values())+sum(r[0] for r in rows)
    best=None
    for choices in itertools.product(*(r[2] for r in rows)):
        totals=dict(fixed)
        changes=0
        for (burden,old,options),key in zip(rows,choices):
            totals[key]+=burden
            changes+=key!=old
        trial=totals['nan_qwen']+totals['nan_mf']
        if trial*10000>total*cap:continue
        score=(sum(abs(totals[k]*Q-total*QUOTAS[k]) for k in KEYS),trial,changes,choices)
        if best is None or score<best[0]:best=(score,totals)
    return best
class ExpandedOptimizer(unittest.TestCase):
 def test_twelve_roles_match_a_separate_full_enumeration(self):
    for count in [11,12,14]:
        rows=[(100+(i%4)*70,'nan_glm' if i%3 else 'nan_ds',('nan_ds','nan_glm')) for i in range(count)]
        expected=oracle(rows)
        result=solve_exact_expanded(rows,FIXED,QUOTAS,0)
        self.assertEqual(tuple(result['choices']),expected[0][3])
        self.assertEqual(result['totals'],expected[1])
        self.assertEqual(result['errorNumerator'],expected[0][0])
        self.assertEqual(result['solver'],'exact-branch-and-bound')
 def test_thirteen_roles_trial_exposure_matches_brute_force(self):
    rows=[(100+i%3*80,'nan_ds',('nan_qwen','nan_ds')) for i in range(13)]
    expected=oracle(rows,cap=2500)
    result=solve_exact_expanded(rows,FIXED,QUOTAS,2500)
    self.assertEqual(tuple(result['choices']),expected[0][3])
    self.assertEqual(result['trialTokens'],expected[0][1])
 def test_failed_budget_cannot_claim_an_optimum(self):
    rows=[(100+i%3*10,'nan_ds',('nan_ds','nan_glm')) for i in range(14)]
    with self.assertRaisesRegex(ValueError,'budget exceeded'):
        solve_exact_expanded(rows,FIXED,QUOTAS,0,max_states=1)
 def test_invalid_inputs_blocked(self):
    rows=[(2,'nan_ds',('nan_ds','nan_glm'))]*12
    for args in [{'trial_cap_bps':10001},{'max_states':0},{'fixed':{'nan_ds':0}}]:
        data={'rows':rows,'fixed':FIXED,'quotas':QUOTAS,'trial_cap_bps':0}
        data.update(args)
        with self.assertRaises(ValueError):solve_exact_expanded(**data)
if __name__=='__main__':unittest.main()
