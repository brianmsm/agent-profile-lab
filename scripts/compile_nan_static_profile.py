#!/usr/bin/env python3
"""Export reviewed, hypothetical static NaN quota profiles without model calls."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from copy import deepcopy
from access_catalog import ROOT,read_json
from nan_static_profiles import derive_nan_static,load_static_policy,POLICY_SOURCES,digest
from nan_static_hybrid import derive_nan_hybrid
from nan_custom_workload import from_file
from profile_compiler import compile_request
from compile_profile import publish_bundle,local_path

def compile_static(snapshot,profile_id,scenario='mixed',include_trials=False,
                  high_impact=False,root=ROOT,composition_mode='nan-only',complexity='standard',custom_workload=None):
    if composition_mode=='nan-only':
        p=derive_nan_static(snapshot,profile_id,scenario,include_trials,high_impact,root,custom_workload=custom_workload)
    else:
        p=derive_nan_hybrid(snapshot,profile_id,scenario,include_trials,complexity,
                            high_impact,composition_mode,root,custom_workload=custom_workload)
    original=snapshot['routeDetails'][p['sourceProfile']]
    roles={}
    def changed(left,right):
        if (left is None)!=(right is None):return True
        if left is None:return False
        return left['modelKey']!=right['modelKey'] or left['effort']!=right['effort'] or left['origin']!=right['origin']
    def patch_slot(value,reason):
        if value is None:return None
        origin=value['origin']
        return {'modelId':origin['modelId'],'accessRouteId':origin['accessRouteId'],
          'resourceId':origin['resourceId'],'effort':value['effort'],'reason':reason}
    for role,r in p['routes'].items():
        old=original[role]
        if not (changed(r,old) or changed(r['fallback'],old['fallback'])
                or changed(r['accelerator'],old['accelerator'])):
            continue
        if r['enabled']!=old['enabled']:
            raise ValueError('An existing role was incorrectly enabled or disabled')
        roles[role]={**patch_slot(r,r['rationale']),
            'fallback':patch_slot(r['fallback'],'Reserva declarada por el perfil; no se instala automáticamente.'),
            'accelerator':patch_slot(r['accelerator'],'Acelerador declarado por el perfil, no instalado.')}
    if not roles:raise ValueError('No executable difference with source profile')
    name='nan-'+composition_mode+'-'+scenario+('-trial' if include_trials else '-strict')
    name+='-'+hashlib.sha256(p['id'].encode()).hexdigest()[:16]
    request={'schemaVersion':1,'baseProfile':p['sourceProfile'],'targetId':p['meta']['targetId'],
        'name':name,'resources':snapshot['access']['resourcesByPortfolio'][p['portfolio']],'roles':roles}
    bundle=compile_request(request,root)
    manifest=bundle['manifest']
    for role,expected in p['routes'].items():
        actual=manifest['roles'][role]
        for slot in ('primary','fallback','accelerator'):
            source=expected if slot=='primary' else expected[slot]
            target=actual if slot=='primary' else actual[slot]
            if (source is None)!=(target is None):
                raise ValueError('Native compiler and candidate disagree on reserves')
            if source and (source['effort']!=target['effort'] or any(
                source['origin'][field]!=target[field] for field in
                ('modelId','accessRouteId','resourceId','credentialRef','plan'))):
                raise ValueError('Native compiler and candidate have different model origins or efforts')
        if expected['enabled']!=actual['enabled']:
            raise ValueError('Native compiler unexpectedly changed role activity')
        actual['condition']=expected['condition']
    manifest['compiler']='nan-static-cli'
    manifest['selectionPolicy']=p['kind']
    manifest['nanStaticPlan']=deepcopy(p['nanStaticPlan'])
    manifest['activityPlan']=deepcopy(p.get('activityPlan'))
    manifest['sourceInventoryProfile']=profile_id
    manifest['limitations']+=p['limitations']
    for file in [*POLICY_SOURCES,'policies/nan-static-approval.json',
                 'scripts/compile_nan_static_profile.py']:
        manifest['inputsSha256'][file]=digest(root/file)
    return bundle

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile',required=True)
    ap.add_argument('--scenario',choices=['routine','mixed','implementation'],default='mixed')
    ap.add_argument('--include-trials',action='store_true')
    ap.add_argument('--composition',choices=['nan-only','hybrid-preserve','hybrid-assist','hybrid-worker'],
                    default='nan-only')
    ap.add_argument('--complexity',choices=['bounded','standard','complex'],default='standard')
    ap.add_argument('--high-impact',action='store_true')
    ap.add_argument('--output',default='generated/nan-static')
    ap.add_argument('--overwrite',action='store_true')
    ap.add_argument('--custom-workload',type=Path,help='Local validated JSON with all function counts and estimated tokens')
    args=ap.parse_args()
    snapshot=read_json(ROOT/'dashboard/public/data/snapshot.json')
    custom=from_file(args.custom_workload) if args.custom_workload else None
    bundle=compile_static(snapshot,args.profile,args.scenario,args.include_trials,args.high_impact,composition_mode=args.composition,complexity=args.complexity,custom_workload=custom)
    native,manifest=publish_bundle(bundle,local_path(args.output),args.overwrite)
    print(json.dumps({'native':str(native.relative_to(ROOT)),'manifest':str(manifest.relative_to(ROOT)),
        'state':'candidate-not-calibrated','inferencesSent':0},ensure_ascii=False))
if __name__=='__main__':main()
