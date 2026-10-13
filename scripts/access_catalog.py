"""Published model identity is independent of access, billing and native provider."""
from __future__ import annotations
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/+~-]{0,160}$')

def read_json(path: Path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError(f'Duplicate JSON key in {path.name}: {key}')
            result[key] = value
        return result
    def reject(value): raise ValueError(f'Nonfinite JSON number: {value}')
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique, parse_constant=reject)

def load_catalog(root: Path = ROOT) -> dict:
    models = read_json(root/'catalog/models.json')
    offerings = read_json(root/'catalog/offerings.json')
    access = read_json(root/'catalog/access-routes.json')
    plans = read_json(root/'catalog/resource-plans.json')
    if any(doc.get('schemaVersion') != 1 for doc in [models,offerings,access,plans]):
        raise ValueError('Unsupported access catalog schema')
    result = {'models':models['models'], 'offerings':offerings['offerings'],
              'compatibilityOrder':offerings['compatibilityOrder'], 'resourcePlans':plans['plans'], **{k:access[k] for k in ['routes','targets','modelBindings']}}
    if len(result['compatibilityOrder']) != len(set(result['compatibilityOrder'])) or set(result['compatibilityOrder']) != set(result['offerings']):
        raise ValueError('Offering order does not match catalog keys')
    for id, model in result['models'].items():
        if not SAFE_ID.fullmatch(id) or not model.get('name') or not model.get('publisher'):
            raise ValueError(f'Invalid published model: {id}')
    for id, route in result['routes'].items():
        if not SAFE_ID.fullmatch(id) or route['billing'] not in {'subscription','metered'}:
            raise ValueError(f'Invalid access route: {id}')
        if route['authentication'] not in {'oauth-legacy','siwc-oauth','oauth','api-key'}:
            raise ValueError(f'Unknown authentication mechanism: {id}')
    for key, offering in result['offerings'].items():
        if offering['modelId'] not in result['models'] or offering['defaultAccessRouteId'] not in result['routes']:
            raise ValueError(f'Offering has missing model/route: {key}')
        if offering['compatibility']['key'] != key: raise ValueError('Offering key mismatch')
    for key, binding in result['modelBindings'].items():
        if key != binding['modelId']+'|'+binding['accessRouteId']:
            raise ValueError(f'Binding identity mismatch: {key}')
        if binding['modelId'] not in result['models'] or binding['accessRouteId'] not in result['routes']:
            raise ValueError(f'Binding has unknown references: {key}')
        if not SAFE_ID.fullmatch(binding['nativeModelId']) or not isinstance(binding['efforts'],list):
            raise ValueError(f'Unsafe model identifier: {key}')
        offering = result['offerings'].get(binding['offeringKey'])
        if not offering or offering['modelId'] != binding['modelId']:
            raise ValueError(f'Binding/offer mismatch: {key}')
        if binding['identityRelation'] not in {'published-label','candidate-alias'}:
            raise ValueError(f'Unknown identity evidence: {key}')
    for id, target in result['targets'].items():
        if target.get('supportsPerRoleCredentials') is not False:
            raise ValueError(f'Unimplemented credential-dispatch claim: {id}')
        for route, provider in target['providers'].items():
            if route not in result['routes'] or not re.fullmatch(r'[a-z][a-z0-9-]*',provider):
                raise ValueError(f'Invalid target provider: {id}/{route}')
    return result

def compatibility_models(catalog: dict) -> list[dict]:
    return [catalog['offerings'][key]['compatibility'] for key in catalog['compatibilityOrder']]

def target_for(catalog: dict, target_id: str, contracts: dict) -> dict:
    target = catalog['targets'].get(target_id)
    if target is None: raise ValueError(f'Unsupported target/version: {target_id}')
    contract = contracts.get(target['harness'])
    if not contract or contract['harnessVersion'] != target['harnessVersion'] or contract['runtime'] != target['runtime']:
        raise ValueError(f'Target differs from reviewed harness contract: {target_id}')
    return target

def resolve_binding(catalog: dict, target: dict, model_id: str, route_id: str, effort: str) -> dict:
    if route_id not in target['providers']:
        raise ValueError(f'Access route {route_id} unsupported in this target; no automatic substitution')
    binding = catalog['modelBindings'].get(model_id+'|'+route_id)
    if binding is None: raise ValueError(f'No reviewed model/access binding: {model_id} via {route_id}')
    if binding.get('availability')=='historical-not-in-current-inventory':
        raise ValueError('Model is historical and not in the confirmed current account inventory')
    if effort and effort not in binding['efforts']:
        raise ValueError(f'Unsupported effort {effort}: {model_id} via {route_id}')
    route = catalog['routes'][route_id]
    provider = target['providers'][route_id]
    return {'modelId':model_id,'accessRouteId':route_id,'selector':provider+'/'+binding['nativeModelId'],
            'provider':provider,'effort':effort,'service':route['service'],'authentication':route['authentication'],
            'billing':route['billing'],'offeringKey':binding['offeringKey'],'identityRelation':binding['identityRelation'],
            'availability':binding['availability'],'routeCalibration':'not-established'}
