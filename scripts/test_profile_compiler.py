"""Fail-closed route, credential, billing and artifact compiler regressions."""
from copy import deepcopy
from unittest.mock import patch
import json, unittest
from pathlib import Path
import profile_compiler as pc
from access_catalog import load_catalog, compatibility_models, resolve_binding, target_for, read_json
from harness_contracts import load_harnesses
ROOT=Path(__file__).resolve().parents[1]

class CompilerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=load_catalog(); cls.contracts=load_harnesses()
        cls.base=pc.load_baseline('gentle-shell--plus-apps-balanced','matrix',ROOT,cls.catalog,cls.contracts)
        cls.omp=pc.load_baseline('omp--plus-apps-balanced','matrix',ROOT,cls.catalog,cls.contracts)
    def request(self,**kwargs):
        return {'schemaVersion':1,'baseProfile':'gentle-shell--plus-apps-balanced',
                'targetId':'gentle-shell@4.0.0+pi@1.1.0',**kwargs}
    def run_compile(self,request):
        # Catalog/schema/resolver/serialization/manifest execute normally. Only the
        # already validated static baseline materialization is reused for unit speed.
        base=self.omp if request['baseProfile'].startswith('omp--') else self.base
        with patch.object(pc,'load_baseline',return_value=deepcopy(base)):
            return pc.compile_request(request)
    def api_resources(self,siwc=False):
        return [{'id':'api-main','accessRouteId':'openai-api','credentialRef':'api-main','plan':'metered'},
                {'id':'chatgpt-main','accessRouteId':'chatgpt-siwc' if siwc else 'chatgpt-legacy','credentialRef':'chatgpt-main','plan':'plus'}]
    def authorization(self):return {'allowed':True,'maxAmount':2,'currency':'USD'}
    def test_boolean_schema_version_is_not_an_integer_contract(self):
        with self.assertRaisesRegex(ValueError,'version'):
            self.run_compile(self.request(schemaVersion=True))
    def test_model_identity_does_not_conflate_route(self):
        c=self.catalog
        self.assertEqual(c['offerings']['oa_luna']['modelId'],c['offerings']['go_luna']['modelId'])
        self.assertNotEqual(c['offerings']['oa_luna']['defaultAccessRouteId'],c['offerings']['go_luna']['defaultAccessRouteId'])
        self.assertEqual(c['offerings']['nan_ds']['identityRelation'],'candidate-alias')
    def test_legacy_and_siwc_have_distinct_auth_and_selectors(self):
        legacy=self.run_compile(self.request());new=self.run_compile(self.request(accessRemap={'chatgpt-legacy':'chatgpt-siwc'}))
        a=legacy['manifest']['roles']['orchestrator'];b=new['manifest']['roles']['orchestrator']
        self.assertTrue(a['selector'].startswith('openai-codex/'));self.assertTrue(b['selector'].startswith('openai/'))
        self.assertEqual(a['modelId'],b['modelId']);self.assertNotEqual(a['authentication'],b['authentication'])
        self.assertEqual(b['billing'],'subscription')
    def test_manifest_hash_and_tamper(self):
        result=self.run_compile(self.request())
        self.assertTrue(pc.verify_native(result['manifest'],result['native']['content'].encode()))
        self.assertFalse(pc.verify_native(result['manifest'],(result['native']['content']+' ').encode()))
    def test_deterministic_pair(self):
        self.assertEqual(self.run_compile(self.request()),self.run_compile(self.request()))
    def test_no_sdd_native_roles(self):
        native=json.loads(self.run_compile(self.request())['native']['content'])
        self.assertEqual(len(native['config']),13)
        self.assertFalse(any(r.startswith('sdd-') for r in native['config']))
    def test_unknown_target_fails(self):
        with self.assertRaisesRegex(ValueError,'Unsupported target'):
            self.run_compile(self.request(targetId='gentle-shell@4.0.0+pi@9.0.0'))
    def test_wrong_harness_fails(self):
        with self.assertRaisesRegex(ValueError,'different harness'):
            self.run_compile(self.request(targetId='omp@18.8.7'))
    def test_omp_does_not_silently_substitute_siwc(self):
        req=self.request(baseProfile='omp--plus-apps-balanced',targetId='omp@18.8.7',accessRemap={'chatgpt-legacy':'chatgpt-siwc'})
        with self.assertRaisesRegex(ValueError,'unsupported'):
            self.run_compile(req)
    def test_omp_legacy_serialization(self):
        result=self.run_compile(self.request(baseProfile='omp--plus-apps-balanced',targetId='omp@18.8.7'))
        self.assertIn('openai-codex/',result['native']['content'])
        self.assertIn('enabled: false',result['native']['content'])
    def test_paid_route_cannot_be_inferred_from_subscription(self):
        with self.assertRaisesRegex(ValueError,'explicit resource inventory'):
            self.run_compile(self.request(accessRemap={'chatgpt-legacy':'openai-api'}))
    def test_metered_authorization_is_mandatory(self):
        req=self.request(accessRemap={'chatgpt-legacy':'openai-api'},resources=self.api_resources()[:1])
        with self.assertRaisesRegex(ValueError,'Metered API requires'):
            self.run_compile(req)
    def test_metered_explicit_request_is_candidate_not_calibrated(self):
        req=self.request(accessRemap={'chatgpt-legacy':'openai-api'},resources=self.api_resources()[:1],meteredAuthorization=self.authorization())
        result=self.run_compile(req);m=result['manifest']
        self.assertEqual(m['status'],'candidate');self.assertEqual(m['roles']['orchestrator']['billing'],'metered')
        self.assertEqual(m['validation']['entitlement'],'not-verified')
        self.assertIn('declarative-only',m['meteredAuthorization']['enforcement'])
    def test_budget_limits_cannot_be_missing_nonfinite_boolean_or_negative(self):
        for value in [True,-1,0,float('inf'),float('nan'),'2']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                pc.validate_metered({'allowed':True,'maxAmount':value,'currency':'USD'},True)
    def test_no_credential_material_in_resources(self):
        for resource in [{**self.api_resources()[0],'apiKey':'secret'},
                         {**self.api_resources()[0],'credentialRef':'sk-private-secret'},
                         {**self.api_resources()[0],'credentialRef':'/home/user/auth.json'}]:
            with self.assertRaises(ValueError):pc.validate_resources([resource],self.catalog)
    def test_unknown_request_fields_rejected(self):
        with self.assertRaises(ValueError):self.run_compile(self.request(apiKey='do-not-accept'))
    def test_same_provider_different_auth_is_not_representable(self):
        override={'orchestrator':{'accessRouteId':'openai-api','resourceId':'api-main','reason':'Explicit test candidate'}}
        req=self.request(accessRemap={'chatgpt-legacy':'chatgpt-siwc'},resources=self.api_resources(True),
                         roles=override,meteredAuthorization=self.authorization())
        with self.assertRaisesRegex(ValueError,'Ambiguous provider credential namespace'):
            self.run_compile(req)
    def test_same_provider_different_account_is_not_representable(self):
        resources=[{'id':'first','accessRouteId':'chatgpt-legacy','credentialRef':'first','plan':'plus'},
                   {'id':'second','accessRouteId':'chatgpt-legacy','credentialRef':'second','plan':'plus'}]
        # Every primary explicitly bound, so the test reaches provider collision.
        roles={role:{'resourceId':'first','reason':'Explicit account'} for role in self.base['routes']}
        roles['orchestrator']['resourceId']='second'
        # Baseline reserves also need disambiguation; remove them explicitly here.
        for row in roles.values():row.update(fallback=None,accelerator=None)
        with self.assertRaisesRegex(ValueError,'Ambiguous provider credential namespace'):
            self.run_compile(self.request(resources=resources,roles=roles))
    def test_multiple_resources_require_explicit_selection(self):
        resources=[{'id':id,'accessRouteId':'chatgpt-legacy','credentialRef':id,'plan':'plus'} for id in ['one','two']]
        with self.assertRaisesRegex(ValueError,'exactly one'):
            self.run_compile(self.request(resources=resources))
    def test_paid_fallback_also_requires_consent(self):
        fallback={'modelId':'openai:gpt-6.1-sol','accessRouteId':'openai-api','resourceId':'api-main','effort':'medium','reason':'Explicit reserve'}
        with self.assertRaisesRegex(ValueError,'Metered API requires'):
            self.run_compile(self.request(resources=self.api_resources(),roles={'orchestrator':{'reason':'Reserve test','fallback':fallback}}))
    def test_unsupported_effort_not_silently_downgraded(self):
        with self.assertRaisesRegex(ValueError,'Unsupported effort'):
            self.run_compile(self.request(roles={'orchestrator':{'effort':'ultra','reason':'Test'}}))
    def test_retired_roles_cannot_be_reinstated(self):
        with self.assertRaisesRegex(ValueError,'Unknown role override'):
            self.run_compile(self.request(roles={'sdd-design':{'reason':'Test'}}))
    def test_override_requires_rationale(self):
        with self.assertRaisesRegex(ValueError,'explain'):
            self.run_compile(self.request(roles={'orchestrator':{'effort':'high'}}))
    def test_declared_environment_must_match_but_is_not_remote_verification(self):
        req=self.request(declaredEnvironment={'openai-codex':{'accessRouteId':'chatgpt-legacy','resourceId':'chatgpt-main','credentialRef':'chatgpt-main'}})
        result=self.run_compile(req)
        self.assertEqual(result['manifest']['validation']['environment'],'declaration-matches')
        req['declaredEnvironment']['openai-codex']['credentialRef']='wrong'
        with self.assertRaisesRegex(ValueError,'disagrees'):
            self.run_compile(req)
    def test_resources_do_not_confuse_plan_and_service(self):
        bad={**self.api_resources()[0],'plan':'plus'}
        with self.assertRaisesRegex(ValueError,'plan does not match'):
            pc.validate_resources([bad],self.catalog)
    def test_native_versions_bound_in_manifest(self):
        m=self.run_compile(self.request())['manifest']
        self.assertEqual(m['harnessVersion'],'4.0.0');self.assertEqual(m['runtime']['version'],'1.1.0')
        self.assertEqual(m['validation']['inferencesSent'],0)

if __name__=='__main__':unittest.main()
