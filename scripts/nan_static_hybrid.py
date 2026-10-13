#!/usr/bin/env python3
"""Explicit hybrid composition: existing activity routing + quality-gated NaN helpers,
then fixed proportional NaN-role selection. No API calls, no profile installs.
"""
from __future__ import annotations
from copy import deepcopy
from access_catalog import ROOT,load_catalog,target_for,resolve_binding
from activity_allocation import derive_activity,load_policy as load_activity_policy
from nan_static_profiles import derive_nan_static,load_static_policy,check_revision
from nan_quota_balance import KEYS
from nan_custom_workload import validate_custom_workload

def derive_nan_hybrid(snapshot,profile_id,scenario='mixed',include_trials=False,
                      complexity='standard',high_impact=False,mode='hybrid-assist',
                      root=ROOT,environment=None,custom_workload=None):
    env=environment or load_static_policy(root)
    policy,approval,quota_policy,inventory,offerings,contracts,composition=env
    if mode not in ('hybrid-preserve','hybrid-assist','hybrid-worker'):
        raise ValueError('Unknown hybrid composition')
    if high_impact or complexity not in ('bounded','standard','complex'):
        raise ValueError('High-impact or unknown complexity is not admitted')
    if mode=='hybrid-worker' and complexity!='bounded':
        raise ValueError('Bounded worker mode requires bounded complexity')
    check_revision(snapshot,approval)
    if profile_id not in snapshot['meta']:raise ValueError('Unknown source inventory')
    meta=snapshot['meta'][profile_id]
    if meta['domain'] in quota_policy['excludedDomains']:
        raise ValueError('Excluded domain from NaN helper composition')
    custom=validate_custom_workload(custom_workload,root) if custom_workload is not None else None
    if custom and custom['baseScenario']!=scenario:
        raise ValueError('Custom workload must match the base scenario')
    activity_policy=load_activity_policy(root)
    activity=derive_activity(profile_id,snapshot['routeDetails'],snapshot['meta'],
        snapshot['portfolios'],snapshot['runtimePolicies'],snapshot['catalog'],
        contracts,{'complexity':complexity,'highImpact':False},activity_policy)
    routes=deepcopy(activity['routes'])
    helpers=[]
    if mode in ('hybrid-assist','hybrid-worker'):
        workload=custom['functionWorkload'] if custom else policy['scenarios'][scenario]['functionWorkload']
        all_tokens=sum(workload[contracts[meta['harness']]['roles'][role]['functionId']]['callsPerMonth']*
            workload[contracts[meta['harness']]['roles'][role]['functionId']]['totalTokensPerCall']
            for role,route in routes.items() if route['enabled'])
        mode_contract=composition['compositionModes'][mode]
        max_helpers=mode_contract['helperOffloads']
        max_added=int(all_tokens*mode_contract['maxShareOfTotal'])
        added=0
        resources=snapshot['access']['resourcesByPortfolio'][meta['portfolio']]
        nan_resources=[r for r in resources if r['accessRouteId']=='nan']
        if len(nan_resources)!=1:
            raise ValueError('One unambiguous NaN resource is required in a hybrid')
        resource=nan_resources[0]
        cat=load_catalog(root)
        target=target_for(cat,meta['targetId'],contracts)
        donors=[pid for pid,m in snapshot['meta'].items()
            if m['harness']==meta['harness'] and m['domain']==meta['domain']
            and m['objective']==meta['objective']
            and snapshot['portfolios'][m['portfolio']]['nan']=='True'
            and snapshot['portfolios'][m['portfolio']]['openai']=='none'
            and snapshot['portfolios'][m['portfolio']]['claude']=='none'
            and snapshot['portfolios'][m['portfolio']]['gateway']=='none']
        if len(donors)!=1:
            raise ValueError('No uniquely identified NaN-only donor for hybrid target')
        donor_id=donors[0]
        native=snapshot['routeDetails'][donor_id]
        permitted=activity_policy['levels'][complexity]['functions']
        functions=(composition['compositionModes'][mode].get('additionalFunctions',[])+composition['helperFunctionsInPriorityOrder'])
        for function in functions:
            if len(helpers)>=max_helpers:break
            if function not in permitted or function in quota_policy['excludedFunctions']:
                continue
            for role,route in sorted(routes.items()):
                if len(helpers)>=max_helpers:break
                if not route['enabled'] or route['modelKey'] in KEYS:
                    continue
                if contracts[meta['harness']]['roles'][role]['functionId']!=function:
                    continue
                donor=native.get(role)
                if not donor or not donor['enabled'] or donor['modelKey'] not in ('nan_ds','nan_glm'):
                    continue
                if quota_policy['functions'].get(function,{}).get(donor['modelKey'])!='eligible':
                    continue
                burden=workload[function]['callsPerMonth']*workload[function]['totalTokensPerCall']
                if not burden or added+burden>max_added:continue
                offering=offerings[donor['modelKey']]
                origin={'modelId':offering['modelId'],'accessRouteId':resource['accessRouteId'],
                    'resourceId':resource['id'],'credentialRef':resource['credentialRef'],'plan':resource['plan']}
                resolve_binding(cat,target,offering['modelId'],resource['accessRouteId'],donor['effort'])
                old=deepcopy(route)
                rollback={'modelKey':old['modelKey'],'effort':old['effort'],'origin':deepcopy(old['origin'])}
                condition=old['condition']+' '+composition['qualityFirst']+' '+donor['condition']+' Rol auxiliar cerrado con aceptación comprobable; no se ejecutan reservas automáticamente.'
                routes[role]={**old,'modelKey':donor['modelKey'],'effort':donor['effort'],
                    'origin':origin,'fallback':rollback,'condition':condition,
                    'rationale':'Híbrido NaN auxiliar; donante '+donor_id+'/'+role+
                    '. El cambio es una propuesta condicionada a calidad, no una mejora demostrada.'}
                helpers.append({'role':role,'functionId':function,'sourceProfile':donor_id,
                    'fromModelKey':old['modelKey'],'toModelKey':donor['modelKey'],
                    'expectedMonthlyTokens':burden,'classification':'eligible',
                    'reason':'Función de bajo riesgo delimitada con donante nativo y recurso NaN declarado.'})
                added+=burden
    base={**activity,'routes':routes,
        'meta':{**snapshot['meta'][activity['sourceProfile']],'portfolio':meta['portfolio']},
        'portfolio':meta['portfolio'],'compositionMode':mode,'helperOffloads':helpers}
    candidate=derive_nan_static(snapshot,profile_id,scenario,include_trials,high_impact,root,env,base,custom)
    return candidate
