#!/usr/bin/env python3
"""Reconstruct source closure and typed evidence; detect stale metadata/code/datasets."""
from pathlib import Path
import csv,json
from benchmark_semantics import build_semantics,typed_family_coverage
from dashboard_source_coverage import build_source_coverage
from benchmark_io import sha,ROOT

def validate_snapshot(snapshot,expected_rows,expected_registry,root=ROOT):
    if snapshot.get('benchmarks')!=expected_rows:raise ValueError('Benchmark rows/semantics differ from verified normalized sources')
    if snapshot.get('benchmarkRegistry')!=expected_registry:raise ValueError('Typed registry/protocols/hashes are stale or altered')
    if snapshot.get('coverage')!=typed_family_coverage(expected_rows,expected_registry):raise ValueError('Coverage is not derived from declared suites and typed results')
    for path,digest in expected_registry['inputSha256'].items():
        if sha(root/path)!=digest:raise ValueError('Stale typed evidence input '+path)
    ids={r['measurement']['id'] for r in expected_rows}
    if len(ids)!=len(expected_rows):raise ValueError('Duplicate observation identity')
    functions=json.loads((root/'policies/functions.json').read_text())['functions']
    for suite in expected_registry['suites'].values():
        if set(suite['policyFunctionIds'])-functions.keys():raise ValueError('Unknown function in suite mapping')
        if suite['lifecycle']['routeCalibrated'] is not False:raise ValueError('No route experiments have been performed')
    for r in expected_rows:
        m=r['measurement']
        if m['kind']=='cost' and r['value']<0:raise ValueError('Negative cost')
        if m['decisionEligible'] and (m['scope']!='current' or m['issueIds'] or not m['modelId']):raise ValueError('Incorrect screening eligibility')
    return True

def main():
    def rows(path):
        with (ROOT/path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    cat=json.loads((ROOT/'data/model-catalog.json').read_text());ports={r['id']:r for r in rows('data/portfolios.csv')};assignments=rows('data/assignments.csv')
    raw,coverage,_=build_source_coverage(ROOT,cat,ports,assignments)
    expected,registry=build_semantics(raw,coverage,ROOT)
    snapshot=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_text())
    validate_snapshot(snapshot,expected,registry)
    receipt={'result':'PASS','observations':len(expected),'typedMetrics':len(registry['metrics']),'suites':len(registry['suites']),'protocols':len(registry['protocols']),'sourceRevisions':len(registry['revisions']),'routeCalibration':False,'modelCalls':0,'manualUpdatesOnly':True,'inputSha256':registry['inputSha256']}
    (ROOT/'validation/benchmark-validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='inputSha256'}))
if __name__=='__main__':main()
