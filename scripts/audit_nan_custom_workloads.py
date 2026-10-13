#!/usr/bin/env python3
"""Representative cross-language workload editor → static/hybrid → export audit.

All inputs are hypothetical. This has no API calls or installed profile writes.
"""
from __future__ import annotations
import json,hashlib
from copy import deepcopy
from pathlib import Path
from nan_custom_workload import new_custom_workload,validate_custom_workload
from nan_static_profiles import ROOT,derive_nan_static
from nan_static_hybrid import derive_nan_hybrid

def main():
    snapshot=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_bytes())
    original=hashlib.sha256(json.dumps(snapshot['routeDetails'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    scenarios=json.loads((ROOT/'policies/nan-static-workloads.json').read_bytes())['scenarios']
    cases=[];passed=0;rejected=0;changed=0
    for harness in ['gentle-shell','omp']:
      for domain in ['research','apps']:
       for baseline in ['routine','mixed','implementation']:
        for kind in ['nan-only','hybrid-worker']:
         portfolio='nan' if kind=='nan-only' else 'pro100-go-nan'
         profile=f'{harness}--{portfolio}-{domain}-balanced'
         for mutation in ['exploration','implementation','status','scaled']:
          rows=deepcopy(scenarios[baseline]['functionWorkload'])
          if mutation=='exploration':rows['bounded-exploration']['callsPerMonth']*=4
          elif mutation=='implementation':rows['bounded-implementation']['callsPerMonth']*=4
          elif mutation=='status':rows['status-reporting']['callsPerMonth']*=8
          else:
            for row in rows.values():row['callsPerMonth']=row['callsPerMonth']//2
          custom=new_custom_workload(baseline,'Carga '+mutation+' 💡','Hipótesis para '+domain,rows)
          validate_custom_workload(custom)
          for trials in [False,True]:
            sample={'profileId':profile,'scenario':baseline,'mode':kind,'trial':trials,'customWorkload':custom,
               'complexity':'bounded','status':'unknown'}
            try:
              result=(derive_nan_static(snapshot,profile,baseline,trials,custom_workload=custom)
                if kind=='nan-only' else derive_nan_hybrid(snapshot,profile,baseline,trials,complexity='bounded',
                                                           mode='hybrid-worker',custom_workload=custom))
              plan=result['nanStaticPlan']
              assert plan['customWorkload']==custom and plan['scenario']=='custom'
              assert custom['fingerprint'] in result['id']
              assert plan['qualityGuard']['trialFractionOfExpectedNaN']<=plan['qualityGuard']['trialShareCap']+1e-12
              sample.update(status='ok',expected=result)
              changed+=len(plan['changes'])
              passed+=1
            except ValueError as exc:
              sample.update(status='rejected',reason=str(exc));rejected+=1
            cases.append(sample)
    assert hashlib.sha256(json.dumps(snapshot['routeDetails'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==original
    output=ROOT/'validation/nan-custom-parity.json'
    output.write_text(json.dumps(cases,ensure_ascii=False,separators=(',',':'))+'\n')
    report={'cases':len(cases),'generated':passed,'rejected':rejected,'roleChangesAcrossRepeatedCases':changed,
        'baselineSha256':original,'corpusUnchanged':True,'providerInferenceCalls':0}
    (ROOT/'validation/nan-custom-python-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
