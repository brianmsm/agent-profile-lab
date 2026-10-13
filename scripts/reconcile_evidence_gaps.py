#!/usr/bin/env python3
"""Freeze or verify residual *typed-evidence* gaps from the actual current corpus.

Never updates raw numeric data, guesses a metric unit, or makes model calls.
The dated review protects new source adapter coverage against silent regressions.
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter,defaultdict
import argparse,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/'policies/evidence-source-dispositions.json'
OUTPUT=ROOT/'docs/EVIDENCE_GAP_DISPOSITIONS.json'
def analyze(root=ROOT):
    snapshot=json.loads((root/'dashboard/public/data/snapshot.json').read_bytes())
    policy=json.loads((root/'policies/evidence-source-dispositions.json').read_bytes())
    rows=snapshot['benchmarks']
    opaque=[r for r in rows if r['measurement']['kind']=='unclassified']
    mirror=[r for r in rows if r['benchmark']=='AA mirror — Intelligence index']
    assert len(mirror)==678
    assert all(r['measurement']['kind']=='index' and not r['measurement']['decisionEligible'] and
               'opaque-protocol' in r['measurement']['issueIds'] for r in mirror)
    assert len(opaque)==554,len(opaque)
    harness=[r for r in rows if r['sourceId']=='BR-HARNESSRANK-DATA']
    assert len(harness)==44
    assert all(not r['measurement']['decisionEligible'] and
               'harnessrank-historical-harness' in r['measurement']['issueIds'] for r in harness)
    captures=json.loads((root/'sources/reviewed-captures.json').read_bytes())['captures']
    capture_by_id={r['id']:r for r in captures}
    for name,source in policy['sources'].items():
        if source['captureId'] not in capture_by_id:raise ValueError('Missing reviewed capture: '+name)
        if name=='harnessrank':
            if len(harness)!=source['numericObservations']:raise ValueError('HarnessRank source count changed')
        elif any(r['sourceId']==source['sourceId'] for r in rows):
            raise ValueError('Context-only source acquired numeric scores without review: '+name)
    groups=defaultdict(list)
    for row in opaque:
        m=row['measurement']
        groups[(row['sourceId'],row['benchmark'],row['unit'],tuple(m['issueIds']))].append(row)
    evidence=[]
    for (source,benchmark,unit,issues),values in groups.items():
        evidence.append({'sourceId':source,'benchmark':benchmark,'unit':unit,
          'count':len(values),'issueIds':list(issues),
          'sourceUrl':values[0]['source'],
          'disposition':'requires-exact-metric-and-protocol-review; not-ranked',
          'exampleObservationId':values[0]['measurement']['id']})
    evidence.sort(key=lambda x:(-x['count'],x['sourceId'],x['benchmark'],x['unit']))
    bysource=Counter(x['sourceId'] for x in opaque)
    assert bysource.get('BR-QWEN',0)==74
    total=len(rows)
    return {'schemaVersion':1,'corpusDateBasis':'Frozen raw captures; current means not superseded, not a recent model inference.',
       'sourceReviewDate':policy['reviewDate'],'baseObservationCountBeforeHarnessRank':72546,
       'observations':total,'newHarnessRankCells':len(harness),
       'typedMirrorIndexCellsStillIneligible':len(mirror),
       'mirrorIndexWithPublishedModelLinkStillIneligible':sum(r['measurement']['modelId'] is not None for r in mirror),
       'unclassifiedMetricCells':len(opaque),
       'unclassifiedPublisherQwenCells':bysource['BR-QWEN'],
       'remainingOtherUnclassifiedCells':len(opaque)-bysource['BR-QWEN'],
       'unclassifiedBySource':dict(sorted(bysource.items())),
       'unknownMetricGroups':evidence,
       'externalSourceDispositions':policy['sources'],
       'allOriginalNumericValuesPreserved':True,
       'anyAutomaticallyPromotedOpaqueRow':False,
       'redFlags':['Unknown publisher score units are not percentages just because they fall between zero and 100.',
                   'AA-mirror index is now typed as an index, but still has no established evaluation protocol. Some published model names link, without proving route or score comparability.',
                   'HarnessRank historical runs do not calibrate current Pi/Gentle/OMP/Codex harness behavior.',
                   'Large biological benchmark data are not rehosted or partially downloaded for a fake score.'],
       'sourceReviewSha256':hashlib.sha256((root/'policies/evidence-source-dispositions.json').read_bytes()).hexdigest(),
       'noProviderInferenceCalls':True}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--refresh',action='store_true')
    mode.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    current=analyze(ROOT)
    if args.refresh:OUTPUT.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n')
    elif not OUTPUT.exists() or json.loads(OUTPUT.read_bytes())!=current:
        raise SystemExit('Evidence gap dispositions are stale; inspect captured source/version changes before refreshing')
    print(json.dumps({'verified':not args.refresh,'observations':current['observations'],
       'harnessRankCells':current['newHarnessRankCells'],'typedButIneligibleMirror':current['typedMirrorIndexCellsStillIneligible'],
       'unclassified':current['unclassifiedMetricCells'],
       'retainedQwenUnknownUnits':current['unclassifiedPublisherQwenCells'],
       'sourceDispositions':{k:v['status'] for k,v in current['externalSourceDispositions'].items()},
       'inferencesSent':0},ensure_ascii=False))
if __name__=='__main__':main()
