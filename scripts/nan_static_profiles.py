#!/usr/bin/env python3
"""Static, workload-weighted NaN model allocations. Never consumes API quotas.

One fixed selector per eligible native role. All quota denominators start at 100%.
The optimizer chooses among quality-gated models, not among arbitrary aliases.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
from itertools import product
from pathlib import Path
import json
from access_catalog import ROOT, read_json, load_catalog, target_for, resolve_binding
from harness_contracts import load_harnesses,roles_for
from nan_quota_balance import load_config, KEYS
from nan_custom_workload import validate_custom_workload
from nan_quota_optimizer import solve_exact_expanded
from profile_compiler import validate_resources

POLICY_FILE = 'policies/nan-static-workloads.json'
APPROVAL_FILE = 'policies/nan-static-approval.json'
POLICY_SOURCES = (
    POLICY_FILE, 'policies/nan-quota-balancing.json',
    'catalog/account-inventory.json', 'catalog/offerings.json', 'catalog/access-routes.json',
    'catalog/resource-plans.json', 'contracts/harnesses.json', 'policies/functions.json',
    'scripts/nan_static_profiles.py', 'dashboard/src/nanStaticProfiles.ts',
    'scripts/nan_static_hybrid.py','policies/nan-static-composition.json',
    'policies/activity-allocation.json','scripts/activity_allocation.py','dashboard/src/activityProfiles.ts','policies/nan-custom-workload.json',
    'scripts/nan_custom_workload.py','dashboard/src/nanCustomWorkload.ts',
    'scripts/nan_quota_optimizer.py','dashboard/src/nanQuotaOptimizer.ts',
)
def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()

def load_static_policy(root=ROOT):
    approval = read_json(root/APPROVAL_FILE)
    policy = read_json(root/POLICY_FILE)
    if approval.get('id') != policy.get('id') or policy.get('schemaVersion') != 1 or approval.get('schemaVersion') != 1:
        raise ValueError('Static NaN policy and approval versions differ')
    if set(approval.get('inputSha256', {})) != set(POLICY_SOURCES) or any(
        digest(root/file) != approval['inputSha256'][file] for file in POLICY_SOURCES
    ):
        raise ValueError('Static NaN inputs changed without explicit policy approval')
    quota_policy, inventory, offerings = load_config(root)
    contracts = load_harnesses(root)
    functions = read_json(root/'policies/functions.json')['functions']
    if set(policy['scenarios']) != {'routine','mixed','implementation'}:
        raise ValueError('Incomplete workload scenarios')
    if policy['sourceQuotaPolicy'] != 'policies/nan-quota-balancing.json':
        raise ValueError('Static scenario must reuse NaN eligibility policy')
    for scenario in policy['scenarios'].values():
        if set(scenario['functionWorkload']) != set(functions):
            raise ValueError('Function workload assumptions incomplete')
        for workload in scenario['functionWorkload'].values():
            if set(workload) != {'callsPerMonth','totalTokensPerCall'} or any(
                type(v) is not int or v < 0 or v > 10**8 for v in workload.values()
            ):
                raise ValueError('Workload assumptions invalid')
    composition=read_json(root/'policies/nan-static-composition.json')
    if composition.get('schemaVersion')!=1 or composition.get('sourceStaticPolicy')!=POLICY_FILE:
        raise ValueError('Invalid NaN composition review')
    if set(composition.get('compositionModes',{}))!={'nan-only','hybrid-preserve','hybrid-assist','hybrid-worker'}:
        raise ValueError('Incomplete composition contract')
    if set(composition.get('trialShareCapByObjective',{}))!={'economy','balanced','speed','best'}:
        raise ValueError('Incomplete quality exposure contract')
    return policy, approval, quota_policy, inventory, offerings, contracts, composition

def check_revision(snapshot, approval):
    if not snapshot.get('access') or any(
        snapshot['access']['inputSha256'].get(file) != approval['inputSha256'][file] for file in POLICY_SOURCES
    ):
        raise ValueError('Snapshot is not pinned to the static NaN review; regenerate it')

def derive_nan_static(snapshot, profile_id, scenario='mixed', include_trials=False, high_impact=False,
                      root=ROOT, environment=None, base=None, custom_workload=None):
    policy, approval, qp, inventory, offerings, contracts, composition = environment or load_static_policy(root)
    check_revision(snapshot, approval)
    if type(include_trials) is not bool or type(high_impact) is not bool or scenario not in policy['scenarios']:
        raise ValueError('Invalid static strategy settings')
    if profile_id not in snapshot['meta']:
        raise ValueError('Source profile does not exist')
    meta = snapshot['meta'][profile_id]
    if meta['domain'] in qp['excludedDomains'] or high_impact:
        raise ValueError('High-impact or excluded domain cannot use static offloading')
    if snapshot['portfolios'][meta['portfolio']]['nan'] != 'True':
        raise ValueError('This exact source portfolio does not include NaN')
    cat = load_catalog(root)
    target = target_for(cat, meta['targetId'], contracts)
    if meta['harness']!=target['harness'] or meta['harnessVersion']!=target['harnessVersion'] or meta['runtime']!=target['runtime']:
        raise ValueError('Snapshot runtime metadata conflicts with the pinned harness contract')
    resources = snapshot['access']['resourcesByPortfolio'][meta['portfolio']]
    validate_resources(resources, cat)
    nan_resources = [r for r in resources if r['accessRouteId'] == 'nan']
    if len(nan_resources) != 1:
        raise ValueError('One explicit NaN subscription resource required')
    resource = nan_resources[0]
    original = base['routes'] if base is not None else snapshot['routeDetails'][profile_id]
    if base is not None and (base['portfolio']!=meta['portfolio'] or base['meta']['harness']!=meta['harness']
        or base['meta']['domain']!=meta['domain'] or base['meta']['objective']!=meta['objective']):
        raise ValueError('Composed routes do not match their declared inventory and harness context')
    if set(original)!=set(roles_for(contracts[meta['harness']],meta['domain'],meta['objective'])):
        raise ValueError('Native role set differs from the pinned harness contract')
    role_contracts = contracts[meta['harness']]['roles']
    custom=validate_custom_workload(custom_workload,root) if custom_workload is not None else None
    if custom is not None and custom['baseScenario']!=scenario:
        raise ValueError('Custom workload does not match the selected base scenario')
    assumptions={'label':custom['label'],'description':custom['description'],
                 'functionWorkload':custom['functionWorkload']} if custom else policy['scenarios'][scenario]
    workload=assumptions['functionWorkload']
    new_routes = deepcopy(original)
    options_by_role = []
    expected_all = 0
    fixed = {k:0 for k in KEYS}
    by_role = []
    eligible = []
    catalog_quotas = {k:inventory[k]['monthlyTokens'] for k in KEYS}
    quota_total = sum(catalog_quotas.values())
    for role, route in sorted(original.items()):
        if not route['enabled']:
            continue
        function = role_contracts[role]['functionId']
        burden = workload[function]['callsPerMonth'] * workload[function]['totalTokensPerCall']
        expected_all += burden
        by_role.append({'role':role,'functionId':function,'assumedCalls':workload[function]['callsPerMonth'],
            'assumedTotalTokensPerCall':workload[function]['totalTokensPerCall'],'estimatedMonthlyTokens':burden})
        # Never demote an OpenAI/Claude/Go/Command principal for a quota target.
        # This strategy balances only the work *already allocated to NaN*.
        if route['modelKey'] not in KEYS:
            continue
        if function in qp['excludedFunctions'] or function not in qp['functions'] or burden==0:
            if route['modelKey'] in fixed:
                fixed[route['modelKey']] += burden
            continue
        if function not in qp['functions']:
            continue
        candidate_keys = []
        for key in KEYS:
            status = qp['functions'][function].get(key)
            if status is None or (status=='trial' and not include_trials):
                continue
            if workload[function]['totalTokensPerCall'] > inventory[key]['reportedContext']*qp['maximumInputFractionOfReportedContext']:
                continue
            effort = route['effort'] if route['modelKey']==key else ''
            if key == 'nan_glm' and route['modelKey'] != key:
                # Reuse the exact effort of the equivalent NaN-only native role if present.
                donor = next((pid for pid,m in snapshot['meta'].items()
                    if m['harness']==meta['harness'] and m['domain']==meta['domain']
                    and m['objective']==meta['objective'] and snapshot['portfolios'][m['portfolio']]['nan']=='True'
                    and snapshot['portfolios'][m['portfolio']]['openai']=='none'
                    and snapshot['portfolios'][m['portfolio']]['claude']=='none'
                    and snapshot['portfolios'][m['portfolio']]['gateway']=='none'
                    and snapshot['routeDetails'][pid][role]['modelKey']=='nan_glm'), None)
                if donor:
                    effort = snapshot['routeDetails'][donor][role]['effort']
                else:
                    effort = 'medium'
            try:
                resolve_binding(cat, target, offerings[key]['modelId'], resource['accessRouteId'], effort)
            except ValueError:
                continue
            candidate_keys.append((key, effort))
        if not candidate_keys:
            if route['modelKey'] in fixed:
                fixed[route['modelKey']] += burden
            continue
        eligible.append((role,function,burden,route,candidate_keys))
        options_by_role.append([x[0] for x in candidate_keys])
    if not eligible:
        raise ValueError('No eligible bounded native role; zero changes rather than false balanced profile')

    total_nan = sum(fixed.values()) + sum(r[2] for r in eligible)
    if total_nan<=0:
        raise ValueError('No expected NaN tokens in this workload scenario')
    best = None
    best_key = None
    trial_cap_bps = round(10000*composition['trialShareCapByObjective'][meta['objective']]) if include_trials else 0
    if len(eligible)>10:
        expanded=[(burden,route['modelKey'],tuple(k for k,effort in options))
            for role,function,burden,route,options in eligible]
        solved=solve_exact_expanded(expanded,fixed,catalog_quotas,trial_cap_bps)
        best_key=(solved['errorNumerator'],solved['trialTokens'],solved['changes'],tuple(solved['choices']))
        best=(tuple(solved['choices']),solved['totals'])
    else:
      for choices in product(*options_by_role):
          totals = dict(fixed)
          changes = 0
          for (role,function,burden,route,opts),chosen in zip(eligible,choices):
              totals[chosen] += burden
              if route['modelKey'] != chosen:
                  changes += 1
          trial_tokens = totals['nan_qwen']+totals['nan_mf']
          if trial_tokens*10000 > total_nan*trial_cap_bps:
              continue
          error = sum(abs(totals[k]*quota_total-total_nan*catalog_quotas[k]) for k in KEYS)
          # Quality constraints precede quota optimization. Ties prefer less
          # experimental work and fewer substitutions, never a fictitious score.
          comparison = (error,trial_tokens,changes,choices)
          if best_key is None or comparison<best_key:
              best_key = comparison
              best = (choices, totals)
    if best is None:
        raise ValueError('No quality-admissible allocation within trial exposure cap')
    chosen, totals = best
    # Do not create a duplicate candidate if the optimization leaves the exact native config unchanged.
    changes = []
    for (role,function,burden,route,options),key in zip(eligible,chosen):
        effort = next(e for k,e in options if k==key)
        if route['modelKey']==key:
            continue
        offering = offerings[key]
        origin = {'modelId':offering['modelId'],'accessRouteId':resource['accessRouteId'],
                  'resourceId':resource['id'],'credentialRef':resource['credentialRef'],'plan':resource['plan']}
        prior = deepcopy(route.get('fallback')) or {
            'modelKey':route['modelKey'],'effort':route['effort'],'origin':deepcopy(route['origin'])}
        if prior['modelKey']==key and prior['effort']==effort:
            prior=None
        condition = (route['condition'] + ' Selector estático hipotético, sólo subtarea cerrada con fuentes,'
            ' oráculo de aceptación y verificación por el propietario; sin acceso delegado a decisiones críticas.'
            ' No es routing adaptativo ni un límite de tokens impuesto por el proveedor.'
            + (' Modelo trial sin equivalencia demostrada: ejecutar piloto y conservar la reserva anterior.'
                if qp['functions'][function][key]=='trial' else ''))
        rationale = (f'NaN reparto proporcional estático ({policy["id"]}, escenario {"custom-"+custom["fingerprint"] if custom else scenario}); '
            f'estimados {burden} tokens mensuales para {role} bajo supuestos no calibrados. '
            'El optimizador minimiza la distancia de cuotas dentro de modelos aptos. '
            'Principal anterior preservado como reserva declarativa; no instalado. '
            'El perfil nativo no impone calidad ni reparto real.')
        after = {**deepcopy(route),'modelKey':key,'effort':effort,'origin':origin,'fallback':prior,
                 'condition':condition,'rationale':rationale}
        if after.get('accelerator') and after['accelerator']['origin']==origin and after['accelerator']['effort']==effort:
            after['accelerator'] = None
        new_routes[role] = after
        changes.append({'role':role,'functionId':function,'fromModelKey':route['modelKey'],
            'toModelKey':key,'fromEffort':route['effort'],'toEffort':effort,
            'expectedMonthlyTokens':burden,'admission':qp['functions'][function][key]})
    if not changes and not (base is not None and base.get('helperOffloads')):
        raise ValueError('No effective static candidate; matching reference remains available')
    expected_total = sum(totals.values())
    error = best_key[0]
    tv = error/(2*expected_total*quota_total)
    by_model = {key:{
        'offeringKey':key,'quota':catalog_quotas[key],'expectedTokens':totals[key],
        'expectedTokenShare':totals[key]/expected_total,'targetQuotaShare':catalog_quotas[key]/quota_total,
        'expectedFractionOfQuota':totals[key]/catalog_quotas[key],
        'idealFractionOfQuota':expected_total/quota_total,
        'differencePercentagePoints':100*(totals[key]/expected_total-catalog_quotas[key]/quota_total),
        'trialOnly':key in ('nan_qwen','nan_mf'),
    } for key in KEYS}
    coordinator = next(new_routes.get(role) for role in ('orchestrator','default') if role in new_routes)
    lower_bps=round(composition['uncertainty']['lowerTokenFactor']*10000)
    upper_bps=round(composition['uncertainty']['upperTokenFactor']*10000)
    stress=[]
    for factors in product((lower_bps,upper_bps),repeat=len(KEYS)):
        adjusted={key:totals[key]*factors[i] for i,key in enumerate(KEYS)}
        total=sum(adjusted.values())
        if total:
            stress.append(sum(abs(adjusted[k]*quota_total-total*catalog_quotas[k]) for k in KEYS)/(2*total*quota_total))
    guard={'trialShareCap':trial_cap_bps/10000,
        'trialExpectedTokens':totals['nan_qwen']+totals['nan_mf'],
        'trialFractionOfExpectedNaN':(totals['nan_qwen']+totals['nan_mf'])/expected_total,
        'qualityFirst':'role eligibility and trial-exposure hard limits; not an empirical model-quality score'}
    static_plan = {'policyId':policy['id'],'scenario':'custom' if custom else scenario,'scenarioLabel':assumptions['label'],
        'includeTrials':include_trials,'quotasStartAtFull':True,'workloadObserved':False,'state':'candidate-not-calibrated',
        'expectedTokensAllEnabledRoles':expected_all,'expectedTokensOnNaN':expected_total,
        'expectedShareNaNOfAllRoles':expected_total/expected_all if expected_all else 0,
        'distanceFromQuotaTarget':tv,'distanceMetric':'total-variation-of-model-token-shares-vs-quota-shares',
        'scenarioAssumptions':deepcopy(assumptions),'byModel':by_model,'byRole':by_role,'changes':changes,
        **({'customWorkload':deepcopy(custom)} if custom else {}),
        'qualityGuard':guard,'sensitivity':{
          'minimumCornerDistance':min(stress),'maximumCornerDistance':max(stress),
          'lowerFactor':lower_bps/10000,'upperFactor':upper_bps/10000,
          'meaning':'16 stress scenarios on model token consumption; not confidence bounds'},
        'limitations':deepcopy(policy['qualityGates'])}
    if base is not None:
        static_plan['composition']={'mode':base['compositionMode'],
            'activityPlan':deepcopy(base['activityPlan']),
            'helperOffloads':deepcopy(base.get('helperOffloads',[])),
            'activityInventoryProfile':profile_id,'qualityPolicyId':composition['id'],
            'sourceCoordinatorProfile':base['sourceProfile']}
    id = profile_id + (('::nan-hybrid-'+base['compositionMode']+'-') if base is not None else '::nan-static-') + ('custom-'+custom['fingerprint'] if custom else scenario) + ('-trials' if include_trials else '-strict')
    return {'id':id,'kind':'nan-hybrid' if base is not None else 'nan-static',
        'sourceProfile':base['sourceProfile'] if base is not None else profile_id,
        'portfolio':meta['portfolio'],'meta':deepcopy(base['meta']) if base is not None else deepcopy(meta),
        'routes':new_routes,
        'runtime':deepcopy(base['runtime']) if base is not None else deepcopy(snapshot['runtimePolicies'][profile_id]),
        'coordinatorPool':snapshot['catalog'][coordinator['modelKey']]['pool'],
        'offloadPool':'NAN','limitations':deepcopy(policy['qualityGates'])+
          (deepcopy(composition['limitations']) if base is not None else []),
        'aliases':[id],'nanStaticPlan':static_plan,
        **({'activityPlan':deepcopy(base['activityPlan'])} if base is not None else {})}

if __name__=='__main__':
    s=read_json(ROOT/'dashboard/public/data/snapshot.json')
    import sys
    try:
        p=derive_nan_static(s,sys.argv[1] if len(sys.argv)>1 else 'gentle-shell--nan-research-balanced',
            scenario=sys.argv[2] if len(sys.argv)>2 else 'mixed',include_trials='--trials' in sys.argv)
        print(json.dumps({'profile':p['id'],'changes':p['nanStaticPlan']['changes'],
            'byModel':p['nanStaticPlan']['byModel'],'distance':p['nanStaticPlan']['distanceFromQuotaTarget']},
            indent=2,ensure_ascii=False))
    except ValueError as e:
        raise SystemExit(str(e))
