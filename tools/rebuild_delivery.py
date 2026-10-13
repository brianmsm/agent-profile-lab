#!/usr/bin/env python3
"""Reconstruct the public compressed delivery from the rights-filtered snapshot.

Does not read the original research workspace and never fetches benchmarks.
"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from dashboard_delivery import build_delivery

def main():
    source=ROOT/'dashboard/public/data/snapshot.json'
    full=json.loads(source.read_bytes())
    if len(full['meta'])!=2496 or len(full['benchmarks'])!=3241:
        raise ValueError('Unexpected public release snapshot; refusing to build a substituted dataset')
    manifest=build_delivery(full,source)
    chunkdir=source.parent/'chunks'
    keep={Path(item['path']).name for item in manifest['parts'].values()}
    for path in chunkdir.glob('*.json.gz'):
        if path.name not in keep:path.unlink()
    print(json.dumps({'format':manifest['format'],
        'sourceSHA256':manifest['sourceSha256'],
        'publicNumericObservations':len(full['benchmarks']),
        'profileReferences':len(full['meta']),
        'encodedChunkBytes':{name:part['bytes'] for name,part in manifest['parts'].items()},
        'providerCalls':0},indent=2))

if __name__=='__main__':main()
