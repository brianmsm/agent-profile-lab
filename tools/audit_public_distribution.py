#!/usr/bin/env python3
"""Textual/privacy and distribution-boundary preflight for an exact local package.

Scanning never gives a legal clearance. It fails if the intended release still
contains a private source archive, likely live credentials or a user-home path.
"""
from pathlib import Path
import os,json,re
ROOT=Path(__file__).resolve().parents[1]
BAD_ROOT_DIRS={'evidence','sources','generated'}
REGENERATED={'data/assignments.csv','data/assignments.csv.gz','data/assignments.json','data/profiles.json','data/model-catalog.json','data/omp-runtime-policies.json','policies/functional-precedents.json'}
BAD_SUFFIXES={'.raw','.pdf','.sqlite','.sqlite3','.db','.env'}
MUST_EXIST=['LICENSE','README.md','THIRD_PARTY_NOTICES.md',
  'data/assignment-shards/manifest.json','data/public-evidence/source-links.json',
  'dashboard/public/data/snapshot.json','tools/verify_public_release.py']
PATTERNS={
    'private-user-home':re.compile(rb'/(?:home|Users)/[A-Za-z0-9_-]+/(?:Documents|\\.config|\\.local|Library)/',re.I),
    'github-access-token':re.compile(rb'(?:ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{25,}'),
    'provider-api-secret':re.compile(rb'\\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\\b'),
    'private-key-PEM':re.compile(rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----'),
    'long-bearer-token':re.compile(rb'\\bBearer[ \\t]+[A-Za-z0-9_.~-]{40,}\\b')
}

def audit():
    failures=[]
    total=0;count=0
    for missing in MUST_EXIST:
        if not (ROOT/missing).is_file():failures.append({'path':missing,'reason':'required-public-file-missing'})
    for file in ROOT.rglob('*'):
        if not file.is_file():continue
        rel=file.relative_to(ROOT)
        if rel.as_posix() in REGENERATED:continue
        parts=rel.parts
        if any(part in {'node_modules','dist','__pycache__','validation','.git'} for part in parts):
            continue
        if file.is_symlink():
            failures.append({'path':rel.as_posix(),'reason':'symlink-not-approved'});continue
        if parts[0] in BAD_ROOT_DIRS:
            failures.append({'path':rel.as_posix(),'reason':'third-party-source-archive-present'})
            continue
        if file.suffix.lower() in BAD_SUFFIXES:
            failures.append({'path':rel.as_posix(),'reason':'binary-capture-not-authorized'})
            continue
        data=file.read_bytes()
        if b'\0' in data[:min(16384,len(data))]:
            if (len(parts)>=4 and parts[:3]==('dashboard','public','data')
                and 'chunks' in parts and file.suffixes[-2:]==['.json','.gz']):
                pass
            else:
                failures.append({'path':rel.as_posix(),'reason':'unexpected-binary-file'})
        for label,pattern in PATTERNS.items():
            if pattern.search(data):
                failures.append({'path':rel.as_posix(),'reason':label})
        total+=len(data);count+=1
    report={'filesScanned':count,'bytesScanned':total,'candidateFailures':failures,
       'publicBoundaryPassed':not failures,'providerInferenceCalls':0,
       'caution':'Neither scanner nor code license clears rights for arbitrary publisher datasets.'}
    if failures:raise ValueError(json.dumps(report,ensure_ascii=False,indent=2)[:12000])
    return report

if __name__=='__main__':print(json.dumps(audit(),indent=2))
