#!/usr/bin/env python3
"""Exhaustive admissible recipe/offering/context audit; no inference or installs."""
import json,hashlib
from pathlib import Path
from collections import Counter
from selection_candidates import ROOT,load_review,derive_candidate,digest,validate_review_evidence
from access_catalog import load_catalog
from harness_contracts import load_harnesses
from activity_allocation import load_policy

def main():
    snapshot=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_text());review=load_review();validate_review_evidence(snapshot)
    environment=load_catalog(),load_harnesses(),load_policy();policy=review[0];catalog=environment[0]
    out=ROOT/'validation/reviewed-candidates';out.mkdir(parents=True,exist_ok=True)
    cases=[];noops=Counter();errors=[];usage=Counter();role_counts=Counter();rejected_impact=0
    original_hash=digest(snapshot['routeDetails'])
    for pid,meta in snapshot['meta'].items():
        resources=snapshot['access']['resourcesByPortfolio'][meta['portfolio']]
        for r in policy['recipes']:
            if meta['domain'] not in r['domains'] or meta['objective'] not in r['objectives']:continue
            for offer in r['offeringKeys']:
                route=catalog['offerings'][offer]['defaultAccessRouteId']
                if not any(x['accessRouteId']==route for x in resources):continue
                for complexity in r['complexities']:
                    activity={'complexity':complexity,'highImpact':False}
                    try:
                        p=derive_candidate(snapshot,pid,r['id'],offer,activity,review=review,environment=environment)
                        cases.append({'profileId':pid,'recipeId':r['id'],'offeringKey':offer,'activity':activity,'sha256':digest(p)})
                        usage[offer]+=1;role_counts[offer]+=len(p['selectionReview']['changes'])
                        changed={c['role'] for c in p['selectionReview']['changes']};original=snapshot['routeDetails'][pid]
                        for role,info in p['routes'].items():
                            function=environment[1][meta['harness']]['roles'][role]['functionId']
                            assert info['enabled']==original[role]['enabled']
                            if function in policy['protectedFunctions'] or role not in changed:assert info==original[role]
                            else:
                                assert info['fallback']=={k:original[role][k] for k in ['modelKey','effort','origin']}
                                assert info['accelerator']==original[role]['accelerator']
                                assert snapshot['domainContracts'][meta['domain']]['gate'] in info['condition']
                        assert p['runtime']==snapshot['runtimePolicies'][pid]
                        try:derive_candidate(snapshot,pid,r['id'],offer,{**activity,'highImpact':True},review=review,environment=environment)
                        except ValueError:rejected_impact+=1
                        else:raise AssertionError('High-impact case accepted')
                    except ValueError as e:
                        if str(e).startswith('No effective changes:'):noops[r['id']]+=1
                        else:errors.append({'profileId':pid,'recipe':r['id'],'offering':offer,'activity':activity,'error':str(e)})
                    except AssertionError as e:errors.append({'profileId':pid,'recipe':r['id'],'offering':offer,'error':str(e)})
    assert digest(snapshot['routeDetails'])==original_hash
    (out/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,separators=(',',':'))+'\n')
    report={'reviewId':policy['id'],'recipes':len(policy['recipes']),'candidateCases':len(cases),'offeringConfigurations':dict(usage),'changedPrimarySlotsByOffering':dict(role_counts),'highImpactRejected':rejected_impact,'noOpRecipesSkipped':dict(noops),'allInputsUnmodified':True,'errors':errors,'inferencesSent':0}
    (out/'python-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
