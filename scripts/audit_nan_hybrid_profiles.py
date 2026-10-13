#!/usr/bin/env python3
"""Deterministic quality/harness property sweep for static-hybrid NaN candidates.

Does not call any model or service and does not alter native installed profiles.
"""
from __future__ import annotations
import json,hashlib
from pathlib import Path
from collections import Counter
from nan_static_hybrid import derive_nan_hybrid
from nan_static_profiles import ROOT
from activity_allocation import derive_activity,load_policy
from harness_contracts import load_harnesses
def checksum(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode()).hexdigest()
def main():
    s=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_text())
    policy=json.loads((ROOT/'policies/nan-static-composition.json').read_text())
    contracts=load_harnesses()
    before=checksum(s['routeDetails']);cases=[];blocked=Counter();failures=[]
    for harness in ('gentle-shell','omp'):
      for portfolio in ('pro100-go-nan','pro100-claude-go-nan'):
       for domain in ('research','apps'):
        for objective in ('balanced','best'):
         pid=f'{harness}--{portfolio}-{domain}-{objective}'
         for scenario in ('routine','mixed','implementation'):
          for complexity,mode in (('standard','hybrid-preserve'),('standard','hybrid-assist'),
                                  ('bounded','hybrid-assist'),('bounded','hybrid-worker')):
           for include_trials in (False,True):
            try:
             p=derive_nan_hybrid(s,pid,scenario,include_trials,complexity,False,mode)
             origin=derive_activity(pid,s['routeDetails'],s['meta'],s['portfolios'],
                 s['runtimePolicies'],s['catalog'],contracts,
                 {'complexity':complexity,'highImpact':False},load_policy())
             old=origin['routes'];c=p['nanStaticPlan']['composition'];changes={x['role'] for x in p['nanStaticPlan']['changes']}
             helpers={x['role'] for x in c['helperOffloads']}
             assert p['portfolio']==s['meta'][pid]['portfolio'] and p['sourceProfile']==origin['sourceProfile']
             assert p['runtime']==origin['runtime']
             assert len(helpers)<=policy['compositionModes'][mode]['helperOffloads']
             assert p['nanStaticPlan']['qualityGuard']['trialFractionOfExpectedNaN']<=p['nanStaticPlan']['qualityGuard']['trialShareCap']+1e-12
             for role,r in p['routes'].items():
                function=contracts[harness]['roles'][role]['functionId']
                assert old[role]['enabled']==r['enabled']
                if function in policy['notAutomaticallyDelegable'] and role not in helpers:
                    assert r==old[role]
                if role not in helpers and role not in changes:assert r==old[role]
                if old[role]['modelKey'] not in ('nan_glm','nan_ds','nan_qwen','nan_mf') and role not in helpers:
                    assert r['modelKey']==old[role]['modelKey']
             for role in helpers:
                assert old[role]['modelKey'] not in ('nan_glm','nan_ds','nan_qwen','nan_mf')
                assert function not in ('coordination','independent-review','critical-review') if (function:=contracts[harness]['roles'][role]['functionId']) else False
                assert p['routes'][role]['fallback']['modelKey']==old[role]['modelKey']
             if mode=='hybrid-preserve':assert not helpers
             if mode=='hybrid-worker':assert complexity=='bounded'
             try:derive_nan_hybrid(s,pid,scenario,include_trials,complexity,True,mode)
             except ValueError:pass
             else:raise AssertionError('High impact unexpectedly admitted')
             cases.append({'id':pid,'scenario':scenario,'trials':include_trials,'complexity':complexity,'mode':mode,'expected':p})
            except ValueError as e:
             if any(str(e).startswith(reason) for reason in ('No effective static candidate','No eligible bounded native role')):
              blocked['no-effective-changes']+=1
             else:failures.append({'id':pid,'scenario':scenario,'mode':mode,'error':str(e)})
            except (AssertionError,KeyError) as e:
             failures.append({'id':pid,'scenario':scenario,'mode':mode,'error':repr(e)})
    assert checksum(s['routeDetails'])==before
    dest=ROOT/'validation/nan-hybrid-parity.json'
    dest.write_text(json.dumps(cases,ensure_ascii=False,separators=(',',':'))+'\n')
    receipt={'cases':len(cases),'qualityAndNativeChecks':len(cases),'blocked':dict(blocked),
             'failures':failures,'baselineSha256':before,'unmodified':True,'inferencesSent':0}
    (ROOT/'validation/nan-hybrid-python-report.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
