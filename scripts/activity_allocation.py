"""Functional, auditable activity allocations. No optimality/traffic inference.

Pure transformation of canonical role decisions; protected roles, disabled roles,
runtime and reserves stay explicit. The shared JSON policy drives Python and UI.
"""
from copy import deepcopy
from access_catalog import read_json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_policy(root=ROOT):
    policy=read_json(root/'policies/activity-allocation.json')
    validate_policy(policy,root)
    return policy

def validate_policy(policy,root=ROOT):
    if not isinstance(policy,dict) or policy.get('schemaVersion')!=1 or not policy.get('id'):
        raise ValueError('Unknown activity policy schema')
    if set(policy.get('levels',{}))!={'bounded','standard','complex'}:
        raise ValueError('Activity policy must define all three complexity levels')
    pools={'OAI','ANTHROPIC','GO','CC','NAN'}
    priority=policy.get('coordinatorPriority',[])
    if not isinstance(priority,list) or set(priority)!=pools or len(priority)!=len(pools):
        raise ValueError('Activity coordinator priorities must be unique known subscription pools')
    functions=read_json(root/'policies/functions.json')['functions']
    protected=policy.get('protectedFunctions',[])
    if not set(protected)<=functions.keys():raise ValueError('Unknown protected function')
    for level in policy['levels'].values():
        allowed=level.get('functions',[])
        if not isinstance(allowed,list) or len(allowed)!=len(set(allowed)) or not set(allowed)<=functions.keys():
            raise ValueError('Unknown or duplicate function in complexity policy')
        if set(allowed)&set(protected):raise ValueError('A protected function cannot be redistributed')
        if any(not policy.get('conditions',{}).get(f) for f in allowed):raise ValueError('Delegation requires a stated task boundary')
    for mapping in [policy.get('preferredPools',{}),policy.get('complexPreferredPools',{})]:
        for function,order in mapping.items():
            if function not in functions or not isinstance(order,list) or len(order)!=len(set(order)) or not set(order)<=pools:
                raise ValueError('Unknown donor pool/function or duplicate priority')
    return True

def validate_activity(activity, policy):
    if not isinstance(activity,dict) or set(activity)!={'complexity','highImpact'}:
        raise ValueError('activity requires exactly complexity and highImpact')
    if not isinstance(activity['complexity'],str) or activity['complexity'] not in policy['levels'] or type(activity['highImpact']) is not bool:
        raise ValueError('Unknown complexity or non-boolean highImpact')

def inventory_pools(portfolio):
    result=[]
    if portfolio['openai']!='none':result.append('OAI')
    if portfolio.get('claude','none')!='none' or portfolio.get('anthropic')=='True' or portfolio.get('gateway')=='anthropic':result.append('ANTHROPIC')
    if portfolio['gateway'] in ('go','cc'):result.append(portfolio['gateway'].upper())
    if portfolio['nan']=='True':result.append('NAN')
    return result

def derive_activity(profile_id, details, metadata, portfolios, runtime, catalog, contracts, activity, policy=None):
    policy=policy or load_policy();validate_activity(activity,policy)
    if profile_id not in metadata:raise ValueError('Activity inventory profile not found')
    selected=metadata[profile_id];harness=selected['harness'];domain=selected['domain'];objective=selected['objective']
    inventory=portfolios[selected['portfolio']];pools=inventory_pools(inventory)
    if len(pools)<2:raise ValueError('Activity distribution requires at least two subscription resources')
    def source(pool):
        matching=[]
        for pid,info in metadata.items():
            p=portfolios[info['portfolio']]
            if info['harness']!=harness or info['domain']!=domain or info['objective']!=objective or inventory_pools(p)!=[pool]:continue
            if pool=='OAI' and p['openai']!=inventory['openai']:continue
            if pool=='ANTHROPIC':
                # Raw CSV has no claude column; exact tier remains in portfolio id.
                a='max' if 'claude-max' in info['portfolio'] else 'pro'
                b=inventory.get('claude') or ('max' if 'claude-max' in selected['portfolio'] else 'pro')
                if a!=b:continue
            matching.append(pid)
        return sorted(matching)[0] if matching else None
    sources={pool:source(pool) for pool in pools}
    owner=next((p for p in policy['coordinatorPriority'] if sources.get(p)),None)
    if not owner:raise ValueError('No compatible coordinator reference exists for inventory')
    origin=sources[owner];original=details[origin];routes=deepcopy(original)
    blocked='high-impact' if activity['highImpact'] else 'domain-not-approved' if domain in policy['excludedDomains'] else None
    changes=[];retained=[]
    permitted=policy['levels'][activity['complexity']]['functions']
    for role in sorted(original):
        route=original[role];function=contracts[harness]['roles'][role]['functionId']
        reason=blocked or ('disabled-role' if not route['enabled'] else 'protected-function' if function in policy['protectedFunctions'] else 'complexity-boundary' if function not in permitted else None)
        if reason:
            retained.append({'role':role,'functionId':function,'reason':reason});continue
        preferences=policy['complexPreferredPools'].get(function,policy['preferredPools'].get(function,[])) if activity['complexity']=='complex' else policy['preferredPools'].get(function,[])
        found=None
        for pool in preferences:
            donor_id=sources.get(pool)
            if pool==owner or not donor_id:continue
            donor=details[donor_id].get(role)
            if not donor or not donor['enabled'] or catalog[donor['modelKey']]['pool']!=pool:continue
            if donor['modelKey']==route['modelKey'] and donor['effort']==route['effort']:continue
            found=(pool,donor_id,donor);break
        if not found:
            retained.append({'role':role,'functionId':function,'reason':'no-reviewed-compatible-donor'});continue
        pool,donor_id,donor=found
        fallback={'modelKey':route['modelKey'],'effort':route['effort']}
        if route.get('origin'):fallback['origin']=deepcopy(route['origin'])
        condition=policy['conditions'][function]+' '+policy['safetyCondition']+' '+route['condition']
        if donor['condition'] and donor['condition'] not in condition:
            condition+=' Condiciones de la referencia donante: '+donor['condition']
        rationale=f"Candidata por función {function}; complejidad {activity['complexity']}. Referencia donante: {donor_id}/{role}. Coordinación y reserva: {origin}/{role}. No es una recomendación calibrada. "+donor['rationale']
        routes[role]={**deepcopy(route),'modelKey':donor['modelKey'],'effort':donor['effort'],'fallback':fallback,'condition':condition,'rationale':rationale}
        if donor.get('origin'):routes[role]['origin']=deepcopy(donor['origin'])
        changes.append({'role':role,'functionId':function,'pool':pool,'sourceProfile':donor_id,'fromModelKey':route['modelKey'],'toModelKey':donor['modelKey'],'fromEffort':route['effort'],'toEffort':donor['effort']})
    plan={'policyId':policy['id'],'complexity':activity['complexity'],'highImpact':activity['highImpact'],'blockedReason':blocked,
          'inventoryProfile':profile_id,'changes':changes,'retained':retained,'state':'candidate-not-calibrated'}
    return {'sourceProfile':origin,'portfolio':selected['portfolio'],'routes':routes,'runtime':deepcopy(runtime[origin]),'coordinatorPool':owner,
            'offloadPool':'+'.join(sorted({c['pool'] for c in changes})) or None,'limitations':list(policy['limitations']),'activityPlan':plan}
