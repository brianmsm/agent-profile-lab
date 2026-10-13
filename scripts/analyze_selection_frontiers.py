#!/usr/bin/env python3
"""Observed within-model effort trade-offs; never a calibrated global ranking."""
import json
from pathlib import Path
from collections import defaultdict
from selection_candidates import ROOT

def main():
    snapshot=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_text());registry=snapshot['benchmarkRegistry']
    metrics=['mergeability','functional-correctness','output-tokens','cost','duration'];groups=defaultdict(dict)
    for row in snapshot['benchmarks']:
        m=row['measurement'];prefix='FrontierCode v1_1 main '
        if not m['modelId'] or m['modelRelation']!='published-label' or row['sourceId']!='FCDATA' or m['scope']!='current' or m['issueIds'] or not row['benchmark'].startswith(prefix):continue
        metric=row['benchmark'][len(prefix):]
        if metric not in metrics or not isinstance(row['value'],(int,float)):continue
        protocol=registry['protocols'][m['protocolId']]
        key=(m['modelId'],protocol['harness'],protocol['subset'],str(protocol['tasks']),row['model'])
        effort=groups[key].setdefault(row['effort'],{'evidence':{}})
        if metric in effort:raise ValueError('Duplicate metric in one effort scope')
        effort[metric]=row['value'];effort['evidence'][metric]=m['id']
    report=[]
    for key,efforts in groups.items():
        observations=[]
        for effort,point in efforts.items():
            dominated=[]
            for other,compare in efforts.items():
                if effort==other or not all(k in point and k in compare for k in ['mergeability','cost']):continue
                if compare['mergeability']>=point['mergeability'] and compare['cost']<=point['cost'] and (compare['mergeability']>point['mergeability'] or compare['cost']<point['cost']):dominated.append(other)
            observations.append({'effort':effort,**point,'observedMergeabilityCostDominators':dominated})
        report.append({'modelId':key[0],'publishedVariantLabel':key[4],'harness':key[1],'subset':key[2],'tasks':key[3],'efforts':observations})
    result={'source':'Frozen current FrontierCode v1_1 main observations','interpretation':'Dominance is descriptive in two selected means only, with no significance claim. Functional correctness, failures, review costs and per-task heterogeneity can change the decision. No cross-harness/model frontiers or API-to-subscription cost transfer.','groups':report}
    out=ROOT/'validation/reviewed-candidates';out.mkdir(exist_ok=True,parents=True);(out/'effort-frontiers.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'groups':len(report),'underlyingObservations':sum(len(r['evidence']) for g in report for r in g['efforts'])}))
if __name__=='__main__':main()
