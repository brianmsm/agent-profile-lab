#!/usr/bin/env python3
"""Explicit lossless migration from the archived 20-function workload revision.

Old file is never overwritten. Copies its review workload to the newly separated
classifier only after acknowledgement; this is inherited hypothesis, not usage.
"""
from __future__ import annotations
import argparse,json
from copy import deepcopy
from pathlib import Path
from access_catalog import read_json
from nan_custom_workload import ROOT,known_functions,new_custom_workload,rules
OLD_SHA='702785699dceabdf8ef2028b411d2bb98251a749685f295d73a6946bc128ab87'
FIELDS={'schemaVersion','kind','policyId','sourceWorkloadSha256','baseScenario','label','description','functionWorkload','fingerprint'}
def old_fingerprint(value):
    names=sorted(value['functionWorkload'])
    payload=[value['kind'],value['policyId'],value['sourceWorkloadSha256'],value['baseScenario'],value['label'],value['description'],[[key,value['functionWorkload'][key]['callsPerMonth'],value['functionWorkload'][key]['totalTokensPerCall']] for key in names]]
    a,b=14695981039346656037,7809847782465536322;mask=(1<<64)-1
    for byte in json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode():a=((a^byte)*1099511628211)&mask;b=((b^byte)*1099511628211)&mask
    return f'{a:016x}{b:016x}'
def migrate(value,acknowledge=False,root=ROOT):
    if not acknowledge:raise ValueError('Explicit acknowledgement of inherited classifier workload required')
    policy=rules(root)
    if not isinstance(value,dict) or set(value)!=FIELDS or type(value['schemaVersion']) is not int or value['schemaVersion']!=1 or value['kind']!=policy['kind'] or value['policyId']!=policy['policyId'] or value['sourceWorkloadSha256']!=OLD_SHA:raise ValueError('Not the reviewed legacy workload revision')
    rows=value['functionWorkload'];expected=set(known_functions(root))-{'auxiliary-classification'}
    if not isinstance(rows,dict) or set(rows)!=expected:raise ValueError('Legacy function coverage mismatch; cannot drop unknown fields')
    # Full current validation after copying retains all original numeric/text constraints.
    new_rows=deepcopy(rows);new_rows['auxiliary-classification']=deepcopy(rows['independent-review'])
    result=new_custom_workload(value['baseScenario'],value['label'],value['description'],new_rows,root)
    if value['fingerprint']!=old_fingerprint(value):raise ValueError('Legacy fingerprint mismatch')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--confirm-inherited-assumption',action='store_true');a=p.parse_args()
    if a.input.stat().st_size>rules()['maxImportBytes']:raise ValueError('Oversized workload')
    if a.output.exists() or a.output.is_symlink() or a.output.resolve()==a.input.resolve():raise ValueError('Use a new output file; original must remain untouched')
    result=migrate(read_json(a.input),a.confirm_inherited_assumption)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'migrated':True,'oldFunctions':20,'newFunctions':21,'originalPreserved':True,'usageMeasured':False,'output':str(a.output)},ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,TypeError,KeyError) as e:raise SystemExit('Migration refused: '+str(e))
