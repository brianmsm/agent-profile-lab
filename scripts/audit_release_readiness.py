#!/usr/bin/env python3
"""Non-publishing safety and attribution preflight for a LOCAL research repository.

Default generates a private report in ignored validation/. --release fails closed
until rights/privacy/license decisions are documented and all sources cleared.
No upload, network, permission changes, or file content excerpts.
"""
from __future__ import annotations
import argparse,json,re,subprocess
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/distribution-readiness.json'
CREDENTIAL_PATTERNS={
    'private-key-header':re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'github-token':re.compile(rb'(?:ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{25,}'),
    'openai-shaped-api-token':re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b'),
    'bearer-token':re.compile(rb'\bBearer[ \t]+[A-Za-z0-9_.~-]{40,}\b')
}
PERSONAL_PATTERNS={
    'absolute-user-home':re.compile(rb'/(?:home|Users)/[A-Za-z0-9._-]{2,}/'),
}
REDACTED_SCOPE={'filesTracked':0,'scannedTextFiles':0,'uninspectedLargeOrBinaryFiles':0,
                'candidateCredentialMatches':0}
def matches_in_content(content:bytes,patterns=CREDENTIAL_PATTERNS):
    return {label:len(pattern.findall(content)) for label,pattern in patterns.items() if pattern.search(content)}
def tracked_files(root=ROOT):
    out=subprocess.check_output(['git','ls-files','-z'],cwd=root)
    return [root/name.decode('utf-8','surrogateescape') for name in out.split(b'\0') if name]
def scan(root=ROOT,max_file_bytes=5_000_000):
    files=tracked_files(root)
    categories=Counter();secret_findings=[];personal_findings=[];uninspected=[]
    total_bytes=0;scanned=0
    for path in files:
        if not path.is_file():raise ValueError('Git-tracked source missing: '+str(path.relative_to(root)))
        rel=path.relative_to(root).as_posix()
        size=path.stat().st_size;total_bytes+=size
        if rel.startswith(('evidence/captures/','evidence/supplemental/','tests/vendor/')):
            categories['third-party-capture-or-vendor']+=1
        if rel.startswith('docs/'):categories['docs']+=1
        if size>max_file_bytes:
            uninspected.append({'path':rel,'sizeBytes':size,'reason':'exceeds-bounded-scan'})
            continue
        data=path.read_bytes()
        if b'\0' in data[:min(len(data),16384)]:
            uninspected.append({'path':rel,'sizeBytes':size,'reason':'binary'})
            continue
        scanned+=1
        for label,count in matches_in_content(data).items():
            secret_findings.append({'path':rel,'pattern':label,'matchCount':count})
        for label,count in matches_in_content(data,PERSONAL_PATTERNS).items():
            personal_findings.append({'path':rel,'pattern':label,'matchCount':count})
    license_file=(root/'LICENSE').exists() or (root/'LICENSE.md').exists()
    rights_proof=(root/'policies/publication-authorizations.json').exists()
    unresolved=[
        'No principal project LICENSE decision is recorded.' if not license_file else None,
        'No explicit redistribution clearance manifest for third-party captures/vendor inputs.' if not rights_proof else None,
        'No remote publication destination is configured or requested.',
        'Tracked captures and provider content require scope-specific licensing and privacy review.'
    ]
    unresolved=[x for x in unresolved if x]
    if secret_findings:unresolved.append('Potential credential-like strings need manual review without revealing their contents.')
    if personal_findings:unresolved.append('Absolute local user paths need privacy review before distribution.')
    if uninspected:unresolved.append('Some tracked files require a separate full-file review.')
    return {'schemaVersion':1,'scope':'local-git-tracked-contents','noPublish':True,
        'trackedFiles':len(files),'trackedBytes':total_bytes,'scannedTextFiles':scanned,
        'thirdPartyCaptureOrVendorFiles':categories['third-party-capture-or-vendor'],
        'uninspectedFiles':uninspected,'uninspectedCount':len(uninspected),
        'sensitiveCandidates':secret_findings,'sensitiveCandidateCount':sum(x['matchCount'] for x in secret_findings),
        'personalPathCandidates':personal_findings,'personalPathCandidateCount':sum(x['matchCount'] for x in personal_findings),
        'projectLicensePresent':license_file,'rightsClearanceManifestPresent':rights_proof,
        'publicationReady':not unresolved,'blockers':unresolved,
        'limitations':['Regex scanning does not prove absence of all secrets, copyrighted content or personal data.',
                       'Code/benchmark licences do not automatically cover redistributed logs, datasets, website HTML or screenshots.',
                       'Only explicitly tracked files are in scope; generated local outputs are not scanned for publication.',
                       'A clean audit does not grant publication permission.'],
        'providerCalls':0,'uploads':0}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',action='store_true',help='Fail closed unless publication is cleared')
    args=parser.parse_args()
    report=scan()
    OUT.parent.mkdir(exist_ok=True,parents=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('uninspectedFiles','sensitiveCandidates','personalPathCandidates','limitations')},ensure_ascii=False,indent=2))
    if args.release and not report['publicationReady']:
        raise SystemExit('NOT CLEARED: no release or remote publication is authorized. See validation/distribution-readiness.json.')
if __name__=='__main__':main()
