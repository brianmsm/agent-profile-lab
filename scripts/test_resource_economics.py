import unittest,json
from resource_economics import estimate_request, validate_funding
from access_catalog import load_catalog, resolve_binding
class EconomicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=load_catalog();cls.target=cls.c['targets']['gentle-shell@4.0.0+pi@1.1.0']
    def counts(self,**kwargs):return {'input':0,'cacheRead':0,'cacheWrite':0,'output':0,**kwargs}
    def test_threshold_uses_all_request_input(self):
        a=estimate_request('anthropic:claude-haiku-5-5',self.counts(input=1,cacheRead=99999,output=10),'2026-10-10')
        b=estimate_request('anthropic:claude-haiku-5-5',self.counts(input=2,cacheRead=99999,output=10),'2026-10-10')
        self.assertEqual(a['tierMaxInputInclusive'],100000);self.assertIsNone(b['tierMaxInputInclusive'])
    def test_task_total_or_missing_accounting_is_rejected(self):
        with self.assertRaises(ValueError):estimate_request('anthropic:claude-haiku-5-5',{'tokens':1000000},'2026-10-10')
    def test_boolean_tokens_invalid(self):
        with self.assertRaises(ValueError):estimate_request('anthropic:claude-haiku-5-5',self.counts(input=True),'2026-10-10')
    def test_does_not_backdate_price_cut(self):
        with self.assertRaises(ValueError):estimate_request('anthropic:claude-sonnet-5-5',self.counts(cacheRead=1000),'2026-10-01')
    def test_unknown_cache_ttl_is_not_silently_estimated(self):
        with self.assertRaises(ValueError):estimate_request('anthropic:claude-haiku-5-5',self.counts(cacheWrite=100),'2026-10-10',cache_write_ttl='1-hour')
    def test_new_nan_candidates_have_no_fictitious_effort(self):
        for model in ['qwen:qwen3.8-flash','xiaomi:mimo-v2.6-flash']:
            self.assertTrue(resolve_binding(self.c,self.target,model,'nan','')['selector'].startswith('nan/'))
            with self.assertRaises(ValueError):resolve_binding(self.c,self.target,model,'nan','high')
    def test_historical_mimo_not_eligible(self):
        with self.assertRaisesRegex(ValueError,'historical'):resolve_binding(self.c,self.target,'xiaomi:mimo-v2.5','nan','')
    def funding(self,**extra):return {'kind':'included-credit','availableAmount':75,'currency':'USD','observedOn':'2026-10-10','expiresOn':'2026-11-01','organizationRef':'org-main','claimed':True,'benefitId':'claude-max5x-api-credit','eligiblePlan':'max5x',**extra}
    def verify(self,item,amount=2):
        return validate_funding({'api':item},{'api':{'accessRouteId':'anthropic-api'}},self.c,{'allowed':True,'maxAmount':amount,'currency':'USD'},'2026-10-10')
    def test_credit_is_declared_not_enforced(self):self.assertEqual(self.verify(self.funding())['api']['enforcement'],'not-enforced')
    def test_credit_not_auto_granted_to_pro(self):
        with self.assertRaises(ValueError):self.verify(self.funding(eligiblePlan='pro'))
    def test_expired_or_unclaimed_credit_fails(self):
        for item in [self.funding(claimed=False),self.funding(expiresOn='2026-10-10'),self.funding(observedOn='2026-10-11')]:
            with self.assertRaises(ValueError):self.verify(item)
    def test_credit_does_not_authorize_overage(self):
        with self.assertRaises(ValueError):self.verify(self.funding(),76)
    def test_team_credit_requires_seat_counts_and_respects_cap(self):
        item=self.funding(benefitId='claude-team-api-credit',eligiblePlan='team',standardSeats=2,premiumSeats=1,availableAmount=140)
        self.assertEqual(self.verify(item)['api']['availableAmount'],140)
        with self.assertRaises(ValueError):self.verify({**item,'availableAmount':141})
        with self.assertRaises(ValueError):self.verify({k:v for k,v in item.items() if k!='standardSeats'})

    def test_oauth_cannot_claim_api_balance(self):
        with self.assertRaises(ValueError):validate_funding({'x':self.funding()},{'x':{'accessRouteId':'claude-subscription'}},self.c,{'maxAmount':2,'currency':'USD'},'2026-10-10')
if __name__=='__main__':unittest.main()
