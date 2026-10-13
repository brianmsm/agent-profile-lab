#!/usr/bin/env python3
"""Verify canonical snapshot access against versioned inputs, without regeneration.

For the bundled corpus only. External candidate imports have their own browser
contract and are not required to equal these baseline selections.
"""
from pathlib import Path
import csv, json
from access_catalog import load_catalog, compatibility_models, read_json
from harness_contracts import load_harnesses
from prepare_data import load_decisions, partition_decisions
from dashboard_strategies import build_strategy_collections
from dashboard_access import decorate_access
ROOT=Path(__file__).resolve().parents[1]

def expected_projection(root=ROOT):
    access_catalog=load_catalog(root)
    decisions,_=load_decisions(root)
    rows,_=partition_decisions(decisions,load_harnesses(root))
    with (root/'data/portfolios.csv').open(encoding='utf-8-sig',newline='') as handle:
        portfolios={r['id']:r for r in csv.DictReader(handle)}
    with (root/'data/omp-runtime-policies.csv').open(encoding='utf-8-sig',newline='') as handle:
        policies=list(csv.DictReader(handle))
    details,runtime,strategies=build_strategy_collections(rows,compatibility_models(access_catalog),portfolios,policies)
    meta={r['profile_id']:{k:r[k] for k in ('portfolio','harness','domain','objective')} for r in rows}
    compact={key:{} for key in access_catalog['offerings']}
    access=decorate_access(root,compact,portfolios,meta,details,strategies)
    return {'access':access,'meta':meta,'routeDetails':details,'runtimePolicies':runtime,'strategies':strategies},compact

def validate_projection(snapshot, expected, catalog):
    for name,value in expected.items():
        if snapshot.get(name)!=value:
            raise ValueError(f'Canonical access projection differs from inputs: {name}')
    for key,fields in catalog.items():
        if key not in snapshot['catalog'] or any(snapshot['catalog'][key].get(field)!=value for field,value in fields.items()):
            raise ValueError(f'Canonical offering identity differs: {key}')

def main():
    snapshot=read_json(ROOT/'dashboard/public/data/snapshot.json')
    expected,catalog=expected_projection()
    validate_projection(snapshot,expected,catalog)
    print(json.dumps({'accessProjection':'PASS','profiles':len(expected['meta']),
        'strategies':len(expected['strategies']),'resourceInventories':len(expected['access']['resourcesByPortfolio']),
        'inputsHashed':len(expected['access']['inputSha256']),'credentialDispatch':'not-enforced','inferencesSent':0}))

if __name__=='__main__':main()
