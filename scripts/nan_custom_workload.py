"""Strict, local editor contract for monthly function workload assumptions.

The fingerprint is for deterministic identity across Python/browser, not an
attestation of quality or a provider usage receipt.
"""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[1]
RULES_FILE='policies/nan-custom-workload.json'
def rules(root=ROOT):return json.loads((root/RULES_FILE).read_bytes())
def known_functions(root=ROOT):return sorted(json.loads((root/'policies/functions.json').read_bytes())['functions'])
def as_int(value,lower,upper):return type(value) is int and lower<=value<=upper
def utf16_units(value):return len(value.encode('utf-16-le',errors='surrogatepass'))//2
def fingerprint(scenario,label,description,rows,root=ROOT):
    settings=rules(root)
    source_hash=json.loads((root/'policies/nan-static-approval.json').read_bytes())['inputSha256']['policies/nan-static-workloads.json']
    source=[settings['kind'],settings['policyId'],source_hash,scenario,label,description,
            [[name,rows[name]['callsPerMonth'],rows[name]['totalTokensPerCall']]
             for name in known_functions(root)]]
    raw=json.dumps(source,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    mask=(1<<64)-1
    a,b=14695981039346656037,7809847782465536322
    for byte in raw:
        a=((a^byte)*1099511628211)&mask
        b=((b^byte)*1099511628211)&mask
    return f'{a:016x}{b:016x}'
def validate_custom_workload(value,root=ROOT):
    policy=rules(root)
    if not isinstance(value,dict) or set(value)!={'schemaVersion','kind','policyId','sourceWorkloadSha256','baseScenario','label','description','functionWorkload','fingerprint'}:
        raise ValueError('Invalid NaN custom workload schema or extra fields')
    if (value['schemaVersion']!=1 or type(value['schemaVersion']) is not int
        or value['kind']!=policy['kind'] or value['policyId']!=policy['policyId']):
        raise ValueError('NaN custom workload uses a different policy')
    hash_value=json.loads((root/'policies/nan-static-approval.json').read_bytes())['inputSha256']['policies/nan-static-workloads.json']
    if value['sourceWorkloadSha256']!=hash_value:
        raise ValueError('Custom workload belongs to another revision of the official base scenario')
    scenario=value['baseScenario']
    bases=json.loads((root/'policies/nan-static-workloads.json').read_bytes())['scenarios']
    if not isinstance(scenario,str) or scenario not in bases:raise ValueError('Unknown base workload scenario')
    label,description=value['label'],value['description']
    if not isinstance(label,str) or not label.strip() or label!=label.strip() or utf16_units(label)>policy['maxLabelLength'] or re.search(r'[\x00-\x1f\x7f\ud800-\udfff]',label):
        raise ValueError('Invalid custom workload label')
    if not isinstance(description,str) or utf16_units(description)>policy['maxDescriptionLength'] or re.search(r'[\x00-\x1f\x7f\ud800-\udfff]',description):
        raise ValueError('Invalid custom workload description')
    raw=value['functionWorkload']
    functions=known_functions(root)
    if not isinstance(raw,dict) or set(raw)!=set(functions):
        raise ValueError('Custom workload must contain exactly the current functions')
    result={}
    for name in functions:
        row=raw[name]
        if not isinstance(row,dict) or set(row)!={'callsPerMonth','totalTokensPerCall'}:
            raise ValueError('Unknown or missing counters for '+name)
        calls,tokens=row['callsPerMonth'],row['totalTokensPerCall']
        if not as_int(calls,0,policy['maxCallsPerMonth']) or not as_int(tokens,0,policy['maxTotalTokensPerCall']) or calls and not tokens:
            raise ValueError('Invalid monthly workload for '+name)
        result[name]={'callsPerMonth':calls,'totalTokensPerCall':tokens}
    digest=fingerprint(scenario,label,description,result,root)
    if value['fingerprint']!=digest:raise ValueError('Inconsistent custom workload fingerprint')
    return dict(schemaVersion=1,kind=policy['kind'],policyId=policy['policyId'],sourceWorkloadSha256=hash_value,
                baseScenario=scenario,label=label,description=description,
                functionWorkload=result,fingerprint=digest)
def new_custom_workload(scenario,label,description,workload,root=ROOT):
    value=dict(schemaVersion=1,kind=rules(root)['kind'],policyId=rules(root)['policyId'],sourceWorkloadSha256=json.loads((root/'policies/nan-static-approval.json').read_bytes())['inputSha256']['policies/nan-static-workloads.json'],
        baseScenario=scenario,label=label,description=description,
        functionWorkload=deepcopy(workload))
    value['fingerprint']=fingerprint(scenario,label,description,value['functionWorkload'],root)
    return validate_custom_workload(value,root)
def from_file(path:Path,root=ROOT):
    if path.stat().st_size>rules(root)['maxImportBytes']:raise ValueError('Custom workload file too large')
    return validate_custom_workload(json.loads(path.read_bytes()),root)
