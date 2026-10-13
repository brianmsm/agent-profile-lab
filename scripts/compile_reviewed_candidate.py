#!/usr/bin/env python3
"""Export an explicitly selected reviewed candidate; no provider calls or installs."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from copy import deepcopy
from access_catalog import ROOT,read_json
from selection_candidates import derive_candidate,load_review,validate_review_evidence,POLICY,EVIDENCE,APPROVAL,file_sha
from profile_compiler import compile_request
from compile_profile import publish_bundle,local_path

def compile_candidate(snapshot,profile_id,recipe_id,offering_key,activity,root=ROOT):
    review=load_review(root);validate_review_evidence(snapshot,root)
    p=derive_candidate(snapshot,profile_id,recipe_id,offering_key,activity,root,review)
    roles={}
    for change in p['selectionReview']['changes']:
        role=change['role'];r=p['routes'][role];o=r['origin'];f=r['fallback'];fo=f['origin']
        roles[role]={'modelId':o['modelId'],'accessRouteId':o['accessRouteId'],'resourceId':o['resourceId'],'effort':r['effort'],'reason':r['rationale'],
                     'fallback':{'modelId':fo['modelId'],'accessRouteId':fo['accessRouteId'],'resourceId':fo['resourceId'],'effort':f['effort'],'reason':'Conservar el principal de referencia ante fallo de aceptación.'}}
    name=(recipe_id+'-'+offering_key)[:42]+'-'+hashlib.sha256(p['id'].encode()).hexdigest()[:16]
    request={'schemaVersion':1,'baseProfile':profile_id,'targetId':p['meta']['targetId'],'name':name,'resources':snapshot['access']['resourcesByPortfolio'][p['portfolio']],'roles':roles}
    bundle=compile_request(request,root)
    m=bundle['manifest']
    # Never annotate a different native configuration with an imported candidate's rationale.
    for role,expected in p['routes'].items():
        actual=m['roles'][role]
        for slot in ('primary','fallback','accelerator'):
            src=expected if slot=='primary' else expected[slot]
            dst=actual if slot=='primary' else actual[slot]
            if (src is None)!=(dst is None):raise ValueError('Snapshot and source compiler disagree on reserves')
            if src:
                if src['effort']!=dst['effort'] or any(src['origin'][k]!=dst[k] for k in ('modelId','accessRouteId','resourceId','credentialRef','plan')):
                    raise ValueError('Snapshot candidate and current source compiler differ; regenerate the snapshot')
    m['compiler']='reviewed-candidate-cli';m['selectionPolicy']='reviewed-candidate'
    m['selectionReview']={**deepcopy(p['selectionReview']),'evidence':[review[1]['observations'][id] for id in p['selectionReview']['evidenceRefs']]}
    for change in p['selectionReview']['changes']:
        role=change['role'];m['roles'][role]['condition']=p['routes'][role]['condition']
        m['roles'][role]['decisionEvidence'].update(kind='evidence-reviewed-candidate',reviewId=review[0]['id'],recipeId=recipe_id,evidenceRefs=p['selectionReview']['evidenceRefs'])
    m['limitations']+=p['limitations']
    for path in [POLICY,EVIDENCE,APPROVAL,'scripts/selection_candidates.py','scripts/compile_reviewed_candidate.py']:
        m['inputsSha256'][path]=file_sha(root/path)
    return bundle

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',required=True);parser.add_argument('--recipe',required=True);parser.add_argument('--offering',required=True)
    parser.add_argument('--complexity',choices=['bounded','standard','complex'],default='standard');parser.add_argument('--high-impact',action='store_true')
    parser.add_argument('--output',default='generated/reviewed-candidates');parser.add_argument('--overwrite',action='store_true')
    args=parser.parse_args();snapshot=read_json(ROOT/'dashboard/public/data/snapshot.json')
    bundle=compile_candidate(snapshot,args.profile,args.recipe,args.offering,{'complexity':args.complexity,'highImpact':args.high_impact})
    native,manifest=publish_bundle(bundle,local_path(args.output),args.overwrite)
    print(json.dumps({'native':str(native.relative_to(ROOT)),'manifest':str(manifest.relative_to(ROOT)),'status':bundle['manifest']['status'],'recipe':args.recipe,'inferencesSent':0},ensure_ascii=False))
if __name__=='__main__':main()
