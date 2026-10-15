"""Offline, deterministic compilation of reviewed baseline/candidate profiles.

Never reads credential files, invokes a model, installs a profile or promises
that a native provider selector enforces the declared billing identity.
"""
from __future__ import annotations
import csv, hashlib, json, math, re
from copy import deepcopy
from pathlib import Path
from access_catalog import ROOT, load_catalog, compatibility_models, target_for, resolve_binding
from harness_contracts import load_harnesses, roles_for
from prepare_data import load_decisions, partition_decisions
from strict_data_formats import json_loads_strict
from dashboard_strategies import build_strategy_collections
from generate_native_profiles import native_text
from resource_economics import validate_funding
from profile_semantics import require_visual_capability, require_distinct_reserves
from profile_assurance import assess_resolved

REF = re.compile(r'^[A-Za-z][A-Za-z0-9._-]{0,95}$')
REQUEST_FIELDS = {'schemaVersion','targetId','baseProfile','selectionPolicy','name','resources',
                  'accessRemap','roles','meteredAuthorization','declaredEnvironment','funding','fundingAsOf','activity'}
RESOURCE_FIELDS = {'id','accessRouteId','credentialRef','plan'}
SELECTION_FIELDS = {'modelId','accessRouteId','resourceId','effort','reason','fallback','accelerator'}

# Independent preflight reads the exact compiler dependency inventory. Keep one source of truth.
COMPILATION_INPUTS=tuple(dict.fromkeys(['contracts/harnesses.json','policies/functions.json','catalog/models.json','catalog/offerings.json',
            'catalog/access-routes.json','catalog/resource-plans.json','data/assignment-shards/manifest.json','data/portfolios.csv',
            'data/domain-objective-contracts.json','data/omp-runtime-policies.csv','scripts/profile_compiler.py',
            'scripts/access_catalog.py','scripts/dashboard_strategies.py','scripts/generate_native_profiles.py','scripts/profile_semantics.py',
            'scripts/harness_contracts.py','scripts/prepare_data.py','policies/functions.json',
            'policies/activity-allocation.json','scripts/activity_allocation.py','catalog/account-inventory.json','catalog/pricing.json','catalog/resource-benefits.json','scripts/resource_economics.py','policies/assurance-contract.json','scripts/profile_assurance.py',
            'scripts/reviewed_policy_contract.py','scripts/reviewed_git_anchors.py',
            'scripts/strict_data_formats.py','scripts/verify_source_amendment.py',
            'scripts/reviewed_native_blobs.py','scripts/metadata_contracts.py']))



def own_shape(value, allowed, label, required=()):
    if not isinstance(value,dict) or set(value)-set(allowed) or not set(required)<=set(value):
        raise ValueError(f'{label}: unknown or missing fields')


def reference(value, label):
    if not isinstance(value,str) or not REF.fullmatch(value) or value.lower().startswith(('sk-','sk_','bearer','token-')):
        raise ValueError(f'{label}: use a non-secret reference label, not a credential or path')
    return value


def source_resources(portfolio: dict, access_remap: dict) -> list[dict]:
    """Declared baseline resource expectations; never inspected account availability."""
    resources=[]
    if portfolio['openai']!='none':
        resources.append({'id':'chatgpt-main','accessRouteId':'chatgpt-legacy',
                          'credentialRef':'chatgpt-main','plan':portfolio['openai']})
    if portfolio.get('anthropic')=='True' or portfolio['gateway']=='anthropic':
        resources.append({'id':'claude-main','accessRouteId':'claude-subscription',
                          'credentialRef':'claude-main','plan':'max' if 'claude-max' in portfolio['id'] else 'pro'})
    if portfolio['gateway'] in ('go','cc'):
        route='opencode-go' if portfolio['gateway']=='go' else 'command-goat'
        resources.append({'id':route+'-main','accessRouteId':route,'credentialRef':route+'-main','plan':route})
    if portfolio['nan']=='True':
        resources.append({'id':'nan-main','accessRouteId':'nan','credentialRef':'nan-main','plan':'nan-standard'})
    for resource in resources:
        target=access_remap.get(resource['accessRouteId'],resource['accessRouteId'])
        if target != resource['accessRouteId'] and not {target, resource['accessRouteId']} <= {'chatgpt-legacy','chatgpt-siwc'}:
            raise ValueError('Changing billing/service requires an explicit resource inventory; no inferred API access')
        resource['accessRouteId']=target
    return resources


def validate_resources(resources: list, catalog: dict) -> dict:
    if not isinstance(resources,list): raise ValueError('resources must be a list')
    result={}
    for item in resources:
        own_shape(item,RESOURCE_FIELDS,'resource',RESOURCE_FIELDS)
        for field in ['id','credentialRef','plan']: reference(item[field],'resource.'+field)
        if item['id'] in result: raise ValueError('Duplicate resource id')
        if item['accessRouteId'] not in catalog['routes']: raise ValueError('Unknown resource access route')
        route=catalog['routes'][item['accessRouteId']]
        plan=catalog['resourcePlans'].get(route['service']+'|'+item['plan'])
        if not plan or plan['billing']!=route['billing']: raise ValueError('Resource plan does not match service/billing')
        result[item['id']]=deepcopy(item)
    return result


def validate_metered(authorization, required: bool):
    if authorization is None:
        if required: raise ValueError('Metered API requires explicit authorization and a declared monetary limit')
        return None
    own_shape(authorization,{'allowed','maxAmount','currency'},'meteredAuthorization',{'allowed','maxAmount','currency'})
    amount=authorization['maxAmount']
    if authorization['allowed'] is not True or type(amount) not in (int,float) or not math.isfinite(amount) or amount<=0:
        raise ValueError('Metered authorization must explicitly allow a finite positive amount')
    if not isinstance(authorization['currency'],str) or not re.fullmatch(r'[A-Z]{3}',authorization['currency']):
        raise ValueError('Metered authorization requires an ISO-style currency')
    return {**authorization,'enforcement':'declarative-only; not a provider spending cap'}


def native_name(value: str) -> str:
    if not isinstance(value,str): raise ValueError('Profile name must be a string')
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',value) and value not in {'constructor','prototype'}:
        return value
    slug=re.sub('[^A-Za-z0-9._-]','-',value)
    if not slug or not slug[0].isalnum(): slug='profile-'+slug
    return slug[:43]+'-'+hashlib.sha256(value.encode()).hexdigest()[:20]


def load_baseline(profile_id: str, policy: str, root: Path, catalog: dict, contracts: dict, activity=None) -> dict:
    if not isinstance(profile_id,str) or not profile_id: raise ValueError('A baseProfile id is required')
    if policy not in {'matrix','openai-led','nan-volume','activity-distributed'}: raise ValueError('Unknown selection policy')
    decisions,_=load_decisions(root)
    rows,_=partition_decisions(decisions,contracts)
    with (root/'data/portfolios.csv').open(encoding='utf-8-sig',newline='') as fh:
        portfolios={r['id']:r for r in csv.DictReader(fh)}
    with (root/'data/omp-runtime-policies.csv').open(encoding='utf-8-sig',newline='') as fh:
        policies=list(csv.DictReader(fh))
    selected=[r for r in rows if r['profile_id']==profile_id]
    if not selected: raise ValueError('Unknown baseline profile')
    r=selected[0]
    details,runtime,strategies=build_strategy_collections(rows,compatibility_models(catalog),portfolios,policies)
    origin=profile_id
    portfolio_id=r['portfolio']
    activity_plan=None
    if policy=='activity-distributed':
        from activity_allocation import derive_activity,load_policy
        metadata={r['profile_id']:{k:r[k] for k in ('portfolio','harness','domain','objective')} for r in rows}
        candidate=derive_activity(profile_id,details,metadata,portfolios,runtime,{m['key']:m for m in compatibility_models(catalog)},contracts,activity,load_policy(root))
        origin=candidate['sourceProfile'];portfolio_id=candidate['portfolio'];routes=candidate['routes'];activity_plan=candidate['activityPlan']
    elif policy!='matrix':
        if policy=='nan-volume' and portfolios[portfolio_id]['nan']!='True':
            raise ValueError('NaN strategy requires NaN in the selected baseline inventory; a policy cannot invent a subscription')
        plan=portfolios[portfolio_id]['openai']
        if plan=='none': raise ValueError('This strategy requires an available ChatGPT baseline resource')
        origin=f"{r['harness']}--{plan}-{r['domain']}-{r['objective']}"
        strategy=strategies.get(origin+'::'+policy)
        if strategy is None: raise ValueError('Strategy unavailable for this domain/target')
        routes=strategy['routes']; portfolio_id=strategy['portfolio']
    else: routes=details[profile_id]
    selected_rows={row['role']:row for row in rows if row['profile_id']==origin}
    donor_rows={}
    if activity_plan:
        donor_keys={(d['sourceProfile'],d['role']) for d in activity_plan['changes']}
        donor_rows={row['role']:row for row in rows if (row['profile_id'],row['role']) in donor_keys}
        if len(donor_rows)!=len(activity_plan['changes']):
            raise ValueError('Missing source decision for an activity donor')
    pol=next((p for p in policies if p['profile_id']==origin),None)
    return {'profileId':profile_id,'sourceProfile':origin,'harness':r['harness'],'domain':r['domain'],
            'objective':r['objective'],'portfolio':portfolios[portfolio_id], 'routes':deepcopy(routes),
            'rows':selected_rows,'runtimePolicy':pol, 'selectionPolicy':policy,'activityPlan':activity_plan,'activityDonorRows':donor_rows}


def compile_request(request: dict, root: Path=ROOT) -> dict:
    # A coherent reissued manifest may reflect unreviewed local policy.
    from reviewed_policy_contract import verify_reviewed_policy
    verify_reviewed_policy(root)
    own_shape(request,REQUEST_FIELDS,'request',{'schemaVersion','targetId','baseProfile'})
    if type(request['schemaVersion']) is not int or request['schemaVersion']!=1: raise ValueError('Unsupported compiler request version')
    catalog=load_catalog(root); contracts=load_harnesses(root)
    target=target_for(catalog,request['targetId'],contracts)
    policy=request.get('selectionPolicy','matrix')
    if policy!='activity-distributed' and 'activity' in request:raise ValueError('activity only applies to activity-distributed; never ignore it silently')
    baseline=load_baseline(request['baseProfile'],policy,root,catalog,contracts,request.get('activity'))
    if target['harness']!=baseline['harness']: raise ValueError('Baseline belongs to a different harness')
    contract=contracts[baseline['harness']]
    remap=request.get('accessRemap',{})
    if not isinstance(remap,dict): raise ValueError('accessRemap must be an object')
    for old,new in remap.items():
        if old not in catalog['routes'] or not isinstance(new,str) or new not in catalog['routes']:
            raise ValueError('Unknown access-route remapping')
    supplied=request.get('resources')
    resources=validate_resources(supplied if supplied is not None else source_resources(baseline['portfolio'],remap),catalog)
    overrides=request.get('roles',{})
    if not isinstance(overrides,dict) or set(overrides)-set(baseline['routes']):
        raise ValueError('Unknown role override; retired/unsupported roles cannot be reinstated')
    if overrides and policy!='matrix':
        raise ValueError('Explicit overrides require matrix policy; cannot bypass protected strategy roles')
    for role, override in overrides.items():
        own_shape(override,SELECTION_FIELDS,f'roles.{role}')
        if not isinstance(override.get('reason'),str) or not override['reason'].strip():
            raise ValueError('Each explicit role override must explain its decision')
    metered=False
    def selection(base: dict, patch: dict | None, label: str, enabled: bool) -> dict:
        nonlocal metered
        patch=patch or {}
        own_shape(patch,SELECTION_FIELDS,label)
        offering=catalog['offerings'][base['modelKey']]
        model_id=patch.get('modelId',offering['modelId'])
        old_route=offering['defaultAccessRouteId']
        route_id=patch.get('accessRouteId',remap.get(old_route,old_route))
        effort=patch.get('effort',base['effort'])
        if not isinstance(model_id,str) or not isinstance(route_id,str) or not isinstance(effort,str):
            raise ValueError('Model, route and effort must be strings')
        bound=resolve_binding(catalog,target,model_id,route_id,effort)
        matches=[r for r in resources.values() if r['accessRouteId']==route_id]
        wanted=patch.get('resourceId')
        if wanted is not None:
            if not isinstance(wanted,str) or wanted not in resources: raise ValueError('Unknown resource reference')
            matches=[resources[wanted]] if resources[wanted]['accessRouteId']==route_id else []
        if len(matches)!=1:
            if not enabled and not matches:
                return {**bound,'resourceId':None,'credentialRef':None,'plan':None,'bindingStatus':'inactive-unbound'}
            raise ValueError(f'{label}: exactly one declared resource is required for {route_id}; specify resourceId when ambiguous')
        resource=matches[0]
        plan=catalog['resourcePlans'][bound['service']+'|'+resource['plan']]
        if 'allowedModelIds' in plan and model_id not in plan['allowedModelIds']:
            raise ValueError('Model is not in the declared account inventory')
        if enabled and bound['billing']=='metered':metered=True
        return {**bound,'resourceId':resource['id'],'credentialRef':resource['credentialRef'],
                'plan':resource['plan'],'bindingStatus':'declared-not-enforced'}
    resolved={}; namespace_owners={}
    for role in roles_for(contract,baseline['domain'],baseline['objective']):
        old=baseline['routes'][role]; patch=overrides.get(role,{})
        item=selection(old,patch,role,old['enabled'])
        item.update({'enabled':old['enabled'],'functionId':contract['roles'][role]['functionId'],
                     'condition':old['condition'],'rationale':patch.get('reason',old['rationale'])})
        for slot in ['fallback','accelerator']:
            aux=old[slot]
            if slot in patch:
                aux_patch=patch[slot]
                if aux_patch is None: item[slot]=None;continue
                own_shape(aux_patch,SELECTION_FIELDS-{'fallback','accelerator'},f'{role}.{slot}',{'modelId','accessRouteId','reason'})
                if not isinstance(aux_patch['reason'],str) or not aux_patch['reason'].strip():raise ValueError('Reserve override needs rationale')
                aux_base=aux or {'modelKey':old['modelKey'],'effort':old['effort']}
                item[slot]=selection(aux_base,aux_patch,role+'.'+slot,old['enabled'])
                item[slot]['rationale']=aux_patch['reason']
            else:
                item[slot]=selection(aux,None,role+'.'+slot,old['enabled']) if aux else None
        require_distinct_reserves(item,role)
        if item['enabled']:
            for slot,bound in [('primary',item),('fallback',item['fallback']),('accelerator',item['accelerator'])]:
                if bound is None: continue
                offering=catalog['offerings'][bound['offeringKey']]['compatibility']
                require_visual_capability(item['functionId'],offering.get('vision'),role+'.'+slot)
                owner=(bound['accessRouteId'],bound['resourceId'],bound['credentialRef'],bound['authentication'],bound['billing'])
                provider=bound['provider']
                if provider in namespace_owners and namespace_owners[provider]!=owner:
                    raise ValueError(f'Ambiguous provider credential namespace {provider}; native profiles cannot select different accounts/auth for primaries or reserves. Use isolated runtimes or an explicitly supported dispatcher.')
                namespace_owners[provider]=owner
        source=baseline['rows'][role]
        item['decisionEvidence']={'kind':'reviewed-baseline' if role not in overrides else 'explicit-candidate',
            'sourceDecisionId':source['decision_id'],'sourceIds':json.loads(source['source_ids']),
            'sourceProfile':baseline['sourceProfile'],'benchmarkInference':'No ranking or route calibration inferred.'}
        if baseline['activityPlan']:
            decision=next((d for d in baseline['activityPlan']['changes'] if d['role']==role),None)
            if decision:
                donor=baseline['activityDonorRows'][role]
                item['decisionEvidence'].update(kind='policy-derived-candidate',
                    donorProfile=decision['sourceProfile'],donorDecisionId=donor['decision_id'],
                    donorSourceIds=json.loads(donor['source_ids']),policyId=baseline['activityPlan']['policyId'])
        resolved[role]=item
    authorization=validate_metered(request.get('meteredAuthorization'),metered)
    funding=validate_funding(request.get('funding'),resources,catalog,authorization,request.get('fundingAsOf'),root)
    environment=request.get('declaredEnvironment')
    if environment is not None:
        if not isinstance(environment,dict):raise ValueError('declaredEnvironment must map provider to expected resource')
        for provider,binding in environment.items():
            own_shape(binding,{'accessRouteId','resourceId','credentialRef'},'declaredEnvironment',{'accessRouteId','resourceId','credentialRef'})
            for field in binding:reference(binding[field],'declaredEnvironment.'+field)
        for provider,owner in namespace_owners.items():
            expected={'accessRouteId':owner[0],'resourceId':owner[1],'credentialRef':owner[2]}
            if environment.get(provider)!=expected:
                raise ValueError(f'Declared environment disagrees with required auth binding for {provider}')
    default_name=baseline['profileId'].split('--',1)[-1]
    if baseline['activityPlan']:
        default_name+='--activity-'+baseline['activityPlan']['complexity']+('-high-impact' if baseline['activityPlan']['highImpact'] else '')
    elif policy!='matrix':
        default_name+='--'+policy
    raw_name=request.get('name',default_name)
    name=native_name(raw_name)
    config={role:{'model':item['selector'],**({'thinking':item['effort']} if item['effort'] else {})}
            for role,item in resolved.items() if item['enabled'] or baseline['harness']=='omp'}
    text=native_text(name,baseline['harness'],config,baseline['runtimePolicy'])
    filename=name+('.export.json' if baseline['harness']=='gentle-shell' else '.yaml')
    inputs=COMPILATION_INPUTS
    domain_contract=json_loads_strict((root/'data/domain-objective-contracts.json').read_bytes())['domains'][baseline['domain']]
    manifest={'format':'agent-profile-lab.compiled-profile','schemaVersion':1,
        'status':'candidate' if remap or overrides or policy!='matrix' else 'baseline-projection',
        'targetId':request['targetId'],'harness':target['harness'],'harnessVersion':target['harnessVersion'],
        'runtime':target['runtime'],'profileName':name,'domain':baseline['domain'],'objective':baseline['objective'],
        'sourceProfile':baseline['sourceProfile'],'selectionPolicy':policy,
        'activityPlan':baseline['activityPlan'],'referencePortfolio':baseline['portfolio']['id'],
        'referencePortfolioMeaning':'Decision source only; not an estimate of the current resource inventory cost.',
        'resources':list(resources.values()),'resourceEvidence':'user-declared' if supplied is not None else 'baseline-expected-not-inspected',
        'meteredAuthorization':authorization,'funding':funding,'domainContract':domain_contract,'roles':resolved,
        'assurance':assess_resolved(resolved,baseline['harness'],baseline['domain'],catalog['offerings']),
        # An untrusted manifest is reproducible only when its declared request
        # rebuilds the exact native bytes and full contract metadata. This is
        # not a signature or authentication of user intent.
        'compilationRequest':deepcopy(request),
        'nativeArtifact':{'filename':filename,'sha256':hashlib.sha256(text.encode()).hexdigest(),'encoding':'utf-8'},
        'inputsSha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in inputs},
        'validation':{'structural':'passed','credentialDispatch':'not-enforced',
                      'environment':'declaration-matches' if environment is not None else 'not-checked',
                      'entitlement':'not-verified','modelEffortAcceptance':'not-verified-on-target',
                      'performance':'not-calibrated','inferencesSent':0},
        'limitations':[
            'Native configuration does not enforce the authentication, account or billing expectation; perform a separate runtime preflight.',
            'A --api-key override, stored credentials, inherited child environment or account rotation can change which resource is used.',
            'Fallbacks and accelerators are recorded, not installed or automatically dispatched by the native export.',
            'Namespace or model-label agreement does not prove checkpoint, effort or performance equivalence.',
            'Declared API budget is not a technically enforced provider spending limit.',
            *contract['limitations']]}
    return {'native':{'filename':filename,'content':text},'manifest':manifest}


def verify_native(manifest: dict, content: bytes) -> bool:
    return (manifest.get('format')=='agent-profile-lab.compiled-profile'
            and manifest.get('nativeArtifact',{}).get('sha256')==hashlib.sha256(content).hexdigest())
