"""Explicitly refresh source-derived profile test fixtures after reviewed changes.

Not run automatically by tests: inspect and commit the changed snapshots and
expected parity records together. Tests add independent semantic invariants.
"""
import json
from pathlib import Path
from activity_allocation import derive_activity
from harness_contracts import load_harnesses
ROOT=Path(__file__).resolve().parents[1]
def main():
    source=json.loads((ROOT/'dashboard/public/data/snapshot.json').read_text())
    directory=ROOT/'dashboard/tests/fixtures'
    for name in ('access-snapshot.json','activity-fixture.json'):
        path=directory/name;fixture=json.loads(path.read_text())
        for key in ('meta','routeDetails','routing','runtimePolicies','strategies','portfolios','catalog'):
            fixture[key]={id:source[key][id] for id in fixture[key]}
        fixture['domainContracts']=source['domainContracts']
        fixture['access']={**source['access'],'resourcesByPortfolio':{id:source['access']['resourcesByPortfolio'][id] for id in fixture['portfolios']}}
        fixture['stats']={**source['stats'],'profiles':len(fixture['meta']),'groups':len(fixture['meta']),'portfolios':len(fixture['portfolios']),'models':len(fixture['catalog']),'rows':sum(map(len,fixture['routeDetails'].values()))}
        path.write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n')
    s=json.loads((directory/'activity-fixture.json').read_text());cases=json.loads((directory/'activity-parity.json').read_text());contracts=load_harnesses()
    for case in cases:
        case['result']=derive_activity(case['profileId'],s['routeDetails'],s['meta'],s['portfolios'],s['runtimePolicies'],s['catalog'],contracts,case['settings'])
    (directory/'activity-parity.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
    print(f'Refreshed 2 frozen source subsets and {len(cases)} cross-language parity cases; review the diff.')
if __name__=='__main__':main()
