#!/usr/bin/env python3
"""Lock objective pairs sharing primary native selectors.

116 identical complete routes mean the *configurations* match, not measured
performance. Use --refresh only after inspecting source changes. Checks use
--verify to fail on an unreviewed difference.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import argparse,hashlib,json
from audit_profile_semantics import inspect_baselines,configuration,canonical
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'policies/objective-equivalence-ledger.json'
CLASSES={
 'same-effective-configuration':'All executable configuration, reserves, origin and conditions match. Performance and cost have not been compared.',
 'distinct-auxiliary-routing':'Same active primaries but different reserves, accelerators or disabled routes; do not merge manifests.',
 'distinct-operational-contract':'Same model selectors and auxiliary routes but different operational conditions; do not merge contracts.',
 'distinct-resource-origin':'Same selectors but different authorization route or credential origin; no equivalence of account access.'
}
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def collect(snapshot):
    _,_,dimensions=inspect_baselines(snapshot)
    pairs=[]
    for pair in dimensions['objective']:
        a,b=pair['a'],pair['b']
        eq=pair['equivalent']
        if eq['contractAware']:classification='same-effective-configuration'
        elif not eq['allRoutes']:classification='distinct-auxiliary-routing'
        elif not eq['originAware']:classification='distinct-resource-origin'
        else:classification='distinct-operational-contract'
        meta=snapshot['meta'][a]
        assert all(snapshot['meta'][a][k]==snapshot['meta'][b][k] for k in ('harness','domain','portfolio'))
        pairs.append({'a':a,'b':b,'harness':meta['harness'],'domain':meta['domain'],'portfolio':meta['portfolio'],
          'objectives':sorted([snapshot['meta'][a]['objective'],snapshot['meta'][b]['objective']]),
          'classification':classification,'sameActiveMain':True,'sameAllRoutes':eq['allRoutes'],
          'sameResourceOrigins':eq['originAware'],'sameConditions':eq['contractAware'],
          'activeNativeFingerprint':digest(configuration(snapshot,a,'activeNative')),
          **({'contractFingerprint':digest(configuration(snapshot,a,'contractAware'))} if eq['contractAware'] else {})})
    pairs.sort(key=lambda x:(x['a'],x['b']))
    summary=Counter(r['classification'] for r in pairs)
    domains=Counter(r['domain'] for r in pairs if r['classification']=='same-effective-configuration')
    assert len(pairs)==212,(len(pairs),summary)
    assert summary=={'same-effective-configuration':116,'distinct-auxiliary-routing':88,'distinct-operational-contract':8},summary
    return {'schemaVersion':1,'origin':'audit_profile_semantics.inspect_baselines',
       'method':'Exact source profile comparison; not a model ranking or experimental test.',
       'baselineProfiles':len(snapshot['meta']),
       'assignmentSourceSha256':hashlib.sha256((ROOT/'data/assignment-shards/manifest.json').read_bytes()).hexdigest(),
       'comparisonFields':['native-primary-and-effort','inactive-routes','reserves-and-accelerators','access-origin','role-conditions','runtime'],
       'classes':CLASSES,'summary':dict(summary),'completeEqualsByDomain':dict(sorted(domains.items())),
       'pairs':pairs,
       'policy':'Do not invent objective differences or claim improvement when the native configuration is identical.'}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--refresh',action='store_true',help='Explicitly refresh only after reviewing source decisions')
    modes.add_argument('--verify',action='store_true',help='Verify committed dispositions against current original routes')
    args=parser.parse_args()
    snapshot=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_bytes())
    report=collect(snapshot)
    if args.refresh:DEST.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    else:
        if not DEST.exists():raise SystemExit('Objective ledger missing; review source and run --refresh')
        if json.loads(DEST.read_bytes())!=report:raise SystemExit('Objective dispositions changed; inspect source before --refresh')
    print(json.dumps({'verified':not args.refresh,'pairs':len(report['pairs']),
       'completeEqual':report['summary']['same-effective-configuration'],
       'differentAuxiliary':report['summary']['distinct-auxiliary-routing'],
       'differentConditions':report['summary']['distinct-operational-contract'],'inferencesSent':0},
       ensure_ascii=False))
if __name__=='__main__':main()
