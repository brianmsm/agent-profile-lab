#!/usr/bin/env python3
"""Generate a randomized, paired, offline trial plan without invoking a model.

Control experiments vary effort within the same catalog route. They are trial
candidates, never new recommended baselines; all costs/results start unknown.
"""
from __future__ import annotations
import argparse,hashlib,json,random
from pathlib import Path
from access_catalog import ROOT,read_json

def trial_plan(snapshot,profile_id,role_ids,repetitions=5,seed=20261014,allow_higher_effort=False):
    if type(repetitions) is not int or not 2<=repetitions<=30:raise ValueError('Use 2–30 paired repetitions, not an unbounded run')
    if profile_id not in snapshot['meta']:raise ValueError('Unknown reference profile')
    if not role_ids or len(role_ids)!=len(set(role_ids)):raise ValueError('Select distinct roles')
    meta=snapshot['meta'][profile_id];routes=snapshot['routeDetails'][profile_id];fixtures=read_json(ROOT/'evaluations/fixtures/adversarial-roles.json')['fixtures']
    functions=read_json(ROOT/'contracts/harnesses.json')['harnesses'][meta['harness']]['roles']
    rows=[];unmapped=[]
    for role in role_ids:
        if role not in routes or not routes[role]['enabled']:raise ValueError('Unknown or disabled role: '+role)
        r=routes[role];f=functions[role]['functionId'];matched=[x for x in fixtures if f in x['functions'] and meta['domain'] in x['domains']]
        if not matched:unmapped.append({'role':role,'function':f,'reason':'No acceptance fixture for this function; no inferred result.'});continue
        allowed=snapshot['catalog'][r['modelKey']]['efforts']
        order=['minimal','low','medium','high','xhigh','max']
        if r['effort'] not in order or r['effort'] not in allowed:
            unmapped.append({'role':role,'function':f,'reason':'Unknown effort/allowed route; manual compatibility review required.'});continue
        alternatives=[r['effort']]+[e for e in order if e in allowed and e!=r['effort']
            and (allow_higher_effort or order.index(e)<order.index(r['effort']))]
        for fixture in matched:
            fixture_hash=hashlib.sha256(json.dumps(fixture,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            for repeat in range(repetitions):
                pair=f'{role}/{fixture["id"]}/{repeat+1}'
                for effort in alternatives:
                    rows.append({'pairId':pair,'profileId':profile_id,'role':role,'functionId':f,'fixtureId':fixture['id'],'fixtureSHA256':fixture_hash,'repeat':repeat+1,
                      'arm':'baseline' if effort==r['effort'] else 'effort-candidate','modelKey':r['modelKey'],'selector':snapshot['catalog'][r['modelKey']]['selector'],
                      'effort':effort,'targetId':meta.get('targetId'),'origin':r.get('origin'),
                      'result':None,'accepted':None,'inputTokens':None,'outputTokens':None,'timeToAcceptanceSeconds':None,'attempts':None,'costAmount':None,'costCurrency':None})
    random.Random(seed).shuffle(rows)
    for i,r in enumerate(rows):r['order']=i+1
    return {'schemaVersion':1,'state':'planned-not-executed','profileId':profile_id,'seed':seed,'repetitions':repetitions,'higherEffortArmsExplicitlyRequested':allow_higher_effort,
      'design':'Paired role/fixture/repetition; randomized arm order; same route and acceptance criteria; no winner inferred.',
      'authorization':{'inferenceApproved':False,'spendApproved':False,'budget':None},'modelCalls':0,'rows':rows,'unmappedFunctions':unmapped,
      'requiredBeforeExecution':['explicit-account-and-budget-approval','exact-runtime-and-endpoint-identity','acceptance-oracle-fixed-before-responses','fresh-context-and-order-control','attempt-cost-and-token-logging','human-review-of-high-impact-results'],
      'promotionRule':'No promotion from source scores, oracle self-tests or unchecked response logs. Compare accepted output, false positives, retries and total latency/cost with uncertainty; retain baseline when evidence is inconclusive.'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',required=True);p.add_argument('--roles',nargs='+',required=True);p.add_argument('--repetitions',type=int,default=5);p.add_argument('--seed',type=int,default=20261014);p.add_argument('--output',type=Path,required=True);p.add_argument('--allow-higher-effort',action='store_true',help='Plan more expensive arms explicitly, without authorizing any inference or spend');a=p.parse_args()
    if a.output.exists() or a.output.is_symlink():raise ValueError('Use a new output; never overwrite results')
    s=read_json(ROOT/'dashboard/public/data/snapshot.json');plan=trial_plan(s,a.profile,a.roles,a.repetitions,a.seed,a.allow_higher_effort)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:f.write(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'plannedCases':len(plan['rows']),'unmapped':plan['unmappedFunctions'],'modelCalls':0,'authorization':plan['authorization'],'output':str(a.output)},ensure_ascii=False))
if __name__=='__main__':main()
