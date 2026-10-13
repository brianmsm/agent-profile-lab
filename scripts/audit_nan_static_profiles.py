#!/usr/bin/env python3
"""Frozen cross-language corpus sample and exact static-allocation property audit."""
from __future__ import annotations
from pathlib import Path
from collections import Counter
import argparse,json,hashlib
from nan_static_profiles import ROOT,derive_nan_static,load_static_policy
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--all',action='store_true',help='Sweep all profiles instead of frozen representative cases')
    args=ap.parse_args()
    snapshot=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_text())
    load_static_policy()
    cases=[];issues=[];blocked=Counter();unchanged=Counter();changesByModel=Counter()
    scenarioList=('routine','mixed','implementation')
    candidates=list(snapshot['meta'])
    if not args.all:
        candidates=[pid for pid in candidates if
            snapshot['meta'][pid]['portfolio'] in ('nan','pro100-go-nan','pro100-claude-go-nan')
            and snapshot['meta'][pid]['domain'] in ('research','apps')
            and snapshot['meta'][pid]['objective'] in ('balanced','best')]
    # No hypothetical data is written to canonical profiles.
    before=hashlib.sha256(json.dumps(snapshot['routeDetails'],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    for pid in candidates:
        if snapshot['portfolios'][snapshot['meta'][pid]['portfolio']]['nan']!='True':continue
        for scenario in scenarioList:
            for trial in (False,True):
                if snapshot['meta'][pid]['domain'] in ('agent-use','cybersecurity'):
                    blocked['excluded-domain']+=1;continue
                try:
                    p=derive_nan_static(snapshot,pid,scenario,trial)
                    plan=p['nanStaticPlan']
                    routeOld=snapshot['routeDetails'][pid]
                    changed={row['role'] for row in plan['changes']}
                    for role,r in p['routes'].items():
                        assert r['enabled']==routeOld[role]['enabled']
                        if role not in changed:assert r==routeOld[role]
                        else:
                            assert routeOld[role]['modelKey'].startswith('nan_'),(pid,role,'non-NaN demoted')
                            prior=routeOld[role]['fallback'] if routeOld[role]['fallback'] else {k:routeOld[role][k] for k in ('modelKey','effort','origin')}
                            if prior['modelKey']==r['modelKey'] and prior['effort']==r['effort']:prior=None
                            assert r['fallback']==prior
                    assert p['runtime']==snapshot['runtimePolicies'][pid]
                    assert set(p['routes'])==set(routeOld)
                    assert abs(sum(x['expectedTokenShare'] for x in plan['byModel'].values())-1)<1e-12
                    assert 0<=plan['distanceFromQuotaTarget']<=1
                    for row in plan['changes']:changesByModel[row['toModelKey']]+=1
                    cases.append({'id':pid,'scenario':scenario,'includeTrials':trial,'expected':p})
                except ValueError as e:
                    msg=str(e)
                    if msg.startswith('No effective static candidate') or msg.startswith('No eligible bounded'):unchanged[msg]+=1
                    else:issues.append({'id':pid,'scenario':scenario,'trials':trial,'error':msg})
    current=hashlib.sha256(json.dumps(snapshot['routeDetails'],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    assert current==before,'Source baseline was modified'
    output=ROOT/'validation/nan-static-parity.json'
    output.write_text(json.dumps(cases,ensure_ascii=False,separators=(',',':'))+'\n')
    report={'cases':len(cases),'blocked':dict(blocked),'noOp':dict(unchanged),'issues':issues[:50],
        'changedRolesByNewModel':dict(changesByModel),'sourceRoutesUnmodified':True,
        'sourceRouteSha256':current,'evidenceObservationsUnchanged':True,'inferencesSent':0}
    (ROOT/'validation/nan-static-python-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if issues:raise SystemExit(1)
if __name__=='__main__':main()
