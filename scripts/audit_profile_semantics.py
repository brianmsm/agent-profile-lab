#!/usr/bin/env python3
"""Cross-specification audit of profile semantics and model reachability.

No inference calls. Repeated configurations are classified, not rejected just for
being equal. Optional --activities exhaustively checks all declared complexity /
impact combinations and records cross-language comparison hashes.
"""
from __future__ import annotations
import argparse,csv,hashlib,itertools,json
from collections import Counter,defaultdict
from pathlib import Path
from activity_allocation import derive_activity,inventory_pools,load_policy
from harness_contracts import load_harnesses
from profile_semantics import EFFORT_ORDER
ROOT=Path(__file__).resolve().parents[1]

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()

def configuration(snapshot,pid,layer):
    meta=snapshot['meta'][pid];routes=snapshot['routeDetails'][pid]
    def ref(r):
        if r is None:return None
        value=[snapshot['catalog'][r['modelKey']]['selector'],r['effort']]
        if layer in ('originAware','contractAware'):value.append(r.get('origin'))
        return value
    output={}
    for role,r in sorted(routes.items()):
        if layer=='activeNative' and not r['enabled']:continue
        output[role]=[ref(r),r['enabled']]
        if layer!='activeNative':output[role]+=[ref(r['fallback']),ref(r['accelerator'])]
        if layer=='contractAware':output[role].append(r['condition'])
    return [meta['harness'],meta.get('targetId'),meta.get('runtime'),snapshot['runtimePolicies'][pid],output]

def inspect_baselines(snapshot,root=ROOT):
    contracts=load_harnesses(root);offerings=json.loads((root/'catalog/offerings.json').read_text())['offerings']
    usage={key:Counter() for key in snapshot['catalog']};errors=[]
    for pid,routes in snapshot['routeDetails'].items():
        meta=snapshot['meta'][pid];gate=snapshot['domainContracts'][meta['domain']]['gate']
        for role,r in routes.items():
            state='active' if r['enabled'] else 'disabled'
            usage[r['modelKey']][state+'Primary']+=1
            if gate not in r['condition']:errors.append([pid,role,'domain-gate-mismatch'])
            primary=(r['modelKey'],r['effort'],r.get('origin'))
            for slot in ('fallback','accelerator'):
                ref=r[slot]
                if ref:
                    usage[ref['modelKey']][state+slot.title()]+=1
                    if (ref['modelKey'],ref['effort'],ref.get('origin'))==primary:errors.append([pid,role,slot,'same-route-reserve'])
            if r['enabled'] and contracts[meta['harness']]['roles'][role]['functionId']=='visual-inspection':
                for slot,ref in [('primary',r),('fallback',r['fallback']),('accelerator',r['accelerator'])]:
                    if ref and snapshot['catalog'][ref['modelKey']]['vision'] is not True:errors.append([pid,role,slot,'missing-declared-image-input'])
    signatures={layer:{pid:digest(configuration(snapshot,pid,layer)) for pid in snapshot['meta']} for layer in ('activeNative','allRoutes','originAware','contractAware')}
    groups={};summary={}
    for layer,mapping in signatures.items():
        buckets=defaultdict(list)
        for pid,hash in mapping.items():buckets[hash].append(pid)
        groups[layer]=[{'sha256':h,'profiles':ps} for h,ps in buckets.items() if len(ps)>1]
        summary[layer]={'distinct':len(buckets),'duplicateGroups':len(groups[layer]),'profilesInDuplicateGroups':sum(len(g['profiles']) for g in groups[layer]),'largestGroup':max(map(len,buckets.values()))}
    dim_pairs={};counts={}
    for dimension in ('objective','domain','portfolio'):
        buckets=defaultdict(list);pairs=[];pair_counts=Counter()
        for pid,m in snapshot['meta'].items():buckets[tuple(m[k] for k in ('harness','portfolio','domain','objective') if k!=dimension)].append(pid)
        for bucket in buckets.values():
            for a,b in itertools.combinations(bucket,2):
                if signatures['activeNative'][a]!=signatures['activeNative'][b]:continue
                x,y=sorted([snapshot['meta'][a][dimension],snapshot['meta'][b][dimension]])
                equivalence={layer:mapping[a]==mapping[b] for layer,mapping in signatures.items()}
                if dimension=='domain':reason='declared-apps-cybersecurity-template' if {x,y}=={'apps','cybersecurity'} else 'same-primaries-different-task-contracts'
                elif dimension=='portfolio':reason='same-primaries-check-reserves-plan-and-unused-resources'
                else:reason='same-primaries-objective-saturation-or-review-gap'
                pairs.append({'a':a,'b':b,'equivalent':equivalence,'classification':reason});pair_counts[x+' / '+y]+=1
        dim_pairs[dimension]=pairs;counts[dimension]=dict(pair_counts.most_common())
    model_report={}
    for key,n in usage.items():
        o=offerings[key]
        if n['activePrimary']:status='selected-in-reference-primaries'
        elif n['activeFallback'] or n['activeAccelerator']:status='auxiliary-only-in-reference'
        elif n['disabledPrimary'] or n['disabledFallback']:status='dormant-roles-only'
        elif o.get('status')=='candidate':status='explicit-candidate-not-in-automatic-donor-recipes'
        elif key=='nan_mimo':status='historical-not-in-current-account'
        else:status='no-automatic-recipe-not-an-evaluated-loser'
        model_report[key]={'modelId':o['modelId'],'label':snapshot['catalog'][key]['name'],'accessRoute':o['defaultAccessRouteId'],'catalogStatus':o.get('status','baseline-catalog'),'selectionStatus':status,'counts':dict(n)}
    critical={'files':0,'downgradeCount':0,'noChangeFiles':0};by_selector={m['selector']:m for m in snapshot['catalog'].values()}
    for path in (root/'profiles/gentle-shell-variants/critical-review').glob('*.export.json'):
        native=json.loads(path.read_text());base_path=root/'profiles/gentle-shell'/path.name.replace('-critical-review.export.json','.export.json')
        base=json.loads(base_path.read_text());critical['files']+=1
        if native['config']==base['config']:critical['noChangeFiles']+=1
        for role,cfg in native['config'].items():
            old=base['config'][role]
            if role not in contracts['gentle-shell']['criticalRoles']:
                if cfg!=old:errors.append([path.name,role,'noncritical-variant-drift'])
                continue
            if cfg['model']!=old['model']:errors.append([path.name,role,'critical-model-drift'])
            current=cfg.get('thinking','');before=old.get('thinking','');allowed=by_selector[cfg['model']]['efforts']
            if current and current not in allowed:errors.append([path.name,role,'unsupported-critical-effort'])
            if current and before and EFFORT_ORDER.index(current)<EFFORT_ORDER.index(before):
                errors.append([path.name,role,'critical-effort-reduced']);critical['downgradeCount']+=1
    return {'profiles':len(snapshot['meta']),'assignments':snapshot['stats']['rows'],'activePrimaries':sum(n['activePrimary'] for n in usage.values()),'offeringUsage':model_report,'duplicates':summary,'equalActiveNativeByDimension':counts,'criticalVariants':critical,'errors':errors},groups,dim_pairs

def inspect_activities(s,root=ROOT,output=None):
    policy=load_policy(root);contracts=load_harnesses(root);errors=[];cases=[];counts=Counter();usage=Counter();retained=Counter();native_groups=defaultdict(list)
    fields=('sourceProfile','portfolio','routes','runtime','coordinatorPool','offloadPool','limitations','activityPlan')
    populations=[pid for pid,m in s['meta'].items() if len(inventory_pools(s['portfolios'][m['portfolio']]))>=2]
    for index,pid in enumerate(populations):
        for impact in (False,True):
            previous=None
            for level in ('bounded','standard','complex'):
                activity={'complexity':level,'highImpact':impact}
                try:
                    result=derive_activity(pid,s['routeDetails'],s['meta'],s['portfolios'],s['runtimePolicies'],s['catalog'],contracts,activity,policy)
                    original=s['routeDetails'][result['sourceProfile']];plan=result['activityPlan'];counts['cases']+=1;counts['blocked:'+str(plan['blockedReason'])]+=1
                    if not plan['changes']:counts['noChanges']+=1
                    if plan['blockedReason'] and result['routes']!=original:raise ValueError('Blocked activity changes its coordinator reference')
                    if result['runtime']!=s['runtimePolicies'][result['sourceProfile']]:raise ValueError('Runtime changed')
                    changed={x['role']:x for x in plan['changes']}
                    if set(changed)|{x['role'] for x in plan['retained']}!=set(original):raise ValueError('Missing per-role explanation')
                    if previous is not None and not set(changed)<=previous:raise ValueError('Increasing complexity expanded delegated role set')
                    previous=set(changed)
                    allowed=inventory_pools(s['portfolios'][result['portfolio']]);gate=s['domainContracts'][s['meta'][pid]['domain']]['gate']
                    for role,route in result['routes'].items():
                        function=contracts[s['meta'][pid]['harness']]['roles'][role]['functionId']
                        if (function in policy['protectedFunctions'] or not original[role]['enabled']) and route!=original[role]:raise ValueError('Protected/disabled role drift')
                        if gate not in route['condition']:raise ValueError('Activity lost domain gate')
                        if route['enabled']:usage[route['modelKey']]+=1
                        for ref in [route,route['fallback'],route['accelerator']]:
                            if not ref:continue
                            model=s['catalog'][ref['modelKey']]
                            if model['pool'] not in allowed:raise ValueError('Unavailable pool')
                            if ref['effort'] and ref['effort'] not in model['efforts']:raise ValueError('Unsupported effort')
                        if role in changed:
                            decision=changed[role];donor=s['routeDetails'][decision['sourceProfile']][role];source_meta=s['meta'][decision['sourceProfile']]
                            if any(source_meta[k]!=s['meta'][pid][k] for k in ('harness','domain','objective')):raise ValueError('Donor contract mismatch')
                            if donor['condition'] not in route['condition']:raise ValueError('Donor condition lost')
                            if route['origin']!=donor['origin']:raise ValueError('Donor origin lost')
                            if route['fallback']!={k:original[role][k] for k in ('modelKey','effort','origin')}:raise ValueError('Original fallback lost')
                        elif route!=original[role]:raise ValueError('Unexplained route change')
                    retained.update(r['reason'] for r in plan['retained'])
                    common={key:result[key] for key in fields}
                    case_id=pid+'|'+level+'|'+str(impact).lower()
                    cases.append({'id':case_id,'profileId':pid,'activity':activity,'sha256':digest(common)})
                    native_groups[digest([s['meta'][pid]['targetId'],result['runtime'],{role:[r['modelKey'],r['effort']] for role,r in result['routes'].items() if r['enabled']}])].append(case_id)
                except Exception as e:errors.append({'profileId':pid,'activity':activity,'error':str(e)})
        if index%200==0:print(f'Checked activity inventories: {index}/{len(populations)}',flush=True)
    if output:
        (output/'activity-parity-hashes.json').write_text(json.dumps(cases,ensure_ascii=False,separators=(',',':'))+'\n')
    return {'inventoryProfiles':len(populations),'counts':dict(counts),'distinctActiveNativeConfigurations':len(native_groups),'activePrimaryOfferings':dict(usage),'retainedReasons':dict(retained),'errors':errors}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--activities',action='store_true');parser.add_argument('--output',default='validation/profile-semantics');args=parser.parse_args()
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT):raise ValueError('Audit output must stay in repository scope')
    output.mkdir(parents=True,exist_ok=True)
    snapshot=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_bytes());report,groups,pairs=inspect_baselines(snapshot)
    (output/'duplicate-groups.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2)+'\n')
    (output/'dimension-equalities.json').write_text(json.dumps(pairs,ensure_ascii=False,indent=2)+'\n')
    if args.activities:report['activities']=inspect_activities(snapshot,output=output)
    report['interpretation']='Counts describe configured roles, not measured workload or model quality. Equal native selections can have different origins, conditions and intent. Catalog candidates are not automatically ranked.'
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('offeringUsage','equalActiveNativeByDimension')},ensure_ascii=False,indent=2))
    if report['errors'] or report.get('activities',{}).get('errors'):raise SystemExit(1)
if __name__=='__main__':main()
