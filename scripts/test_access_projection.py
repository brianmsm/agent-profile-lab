from copy import deepcopy
import unittest
from validate_access import expected_projection, validate_projection

class AccessProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected,cls.catalog=expected_projection()
    def fixture(self):
        return {**deepcopy(self.expected),'catalog':deepcopy(self.catalog)}
    def test_reconstructed_projection_is_self_consistent(self):
        validate_projection(self.fixture(),self.expected,self.catalog)
    def test_credential_origin_tampering_is_rejected(self):
        snapshot=self.fixture()
        routes=next(iter(snapshot['routeDetails'].values()))
        next(iter(routes.values()))['origin']['credentialRef']='changed'
        with self.assertRaisesRegex(ValueError,'routeDetails'):
            validate_projection(snapshot,self.expected,self.catalog)
    def test_missing_inventory_is_rejected(self):
        snapshot=self.fixture();snapshot['access']['resourcesByPortfolio'].popitem()
        with self.assertRaisesRegex(ValueError,'access'):
            validate_projection(snapshot,self.expected,self.catalog)
    def test_target_version_tampering_is_rejected(self):
        snapshot=self.fixture();next(iter(snapshot['meta'].values()))['harnessVersion']='invented'
        with self.assertRaisesRegex(ValueError,'meta'):
            validate_projection(snapshot,self.expected,self.catalog)
    def test_catalog_identity_tampering_is_rejected(self):
        snapshot=self.fixture();next(iter(snapshot['catalog'].values()))['modelId']='wrong'
        with self.assertRaisesRegex(ValueError,'identity'):
            validate_projection(snapshot,self.expected,self.catalog)
    def test_stale_code_hash_is_rejected(self):
        snapshot=self.fixture();snapshot['access']['inputSha256']['scripts/dashboard_access.py']='0'*64
        with self.assertRaisesRegex(ValueError,'access'):
            validate_projection(snapshot,self.expected,self.catalog)

if __name__=='__main__':unittest.main()
