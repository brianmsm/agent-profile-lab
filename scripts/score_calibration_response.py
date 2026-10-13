#!/usr/bin/env python3
"""Score an existing response against a synthetic pilot oracle. No model execution."""
from pathlib import Path
import argparse,json,math
ROOT=Path(__file__).resolve().parents[1]
def equal(actual,expected,tolerance=0,unordered=False):
    if type(expected) in (int,float):return type(actual) in (int,float) and math.isfinite(actual) and abs(actual-expected)<=tolerance
    if type(actual)!=type(expected):return False
    if isinstance(expected,dict):return set(actual)==set(expected) and all(equal(actual[k],v,tolerance,unordered) for k,v in expected.items())
    if isinstance(expected,list):
        if len(actual)!=len(expected):return False
        if unordered:return sorted(json.dumps(x,sort_keys=True) for x in actual)==sorted(json.dumps(x,sort_keys=True) for x in expected)
        return all(equal(a,b,tolerance,unordered) for a,b in zip(actual,expected))
    return actual==expected

def score(fixture,response,response_kind):
    if response_kind not in {'unverified-response','synthetic-oracle-test'}:raise ValueError('No runtime verification is established by this scorer')
    return {'fixture':fixture['id'],'strictPass':equal(response,fixture['expected'],fixture.get('tolerance',0),fixture.get('unorderedLists',False)),
            'responseKind':response_kind,'roleCalibrationEstablished':False,'modelCalls':0,
            'meaning':'Oracle match only; no claim of a representative benchmark, independent trial or verified model origin.'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture',required=True);p.add_argument('--response',required=True);p.add_argument('--response-kind',choices=['unverified-response','synthetic-oracle-test'],default='unverified-response');a=p.parse_args()
    fixtures=json.loads((ROOT/'evaluations/fixtures/pilot.json').read_text())['fixtures'];f=next((f for f in fixtures if f['id']==a.fixture),None)
    if not f:raise ValueError('Unknown fixture')
    print(json.dumps(score(f,json.loads(Path(a.response).read_text()),a.response_kind),indent=2))
if __name__=='__main__':main()
