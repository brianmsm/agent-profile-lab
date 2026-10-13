"""Lossless, content-addressed transport projections; never changes source data.

Only the transport interns equal route records and repeated explanation strings.
Full snapshot.json remains the canonical portable export. Evidence is deferred.
"""
from __future__ import annotations
import gzip, hashlib, json
from pathlib import Path

EVIDENCE_FIELDS = ('benchmarkRegistry', 'benchmarks', 'sourceCoverage', 'cybersecurityEvidence')

def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')

def pack_core(snapshot):
    texts, text_ids, routes, route_ids = [], {}, [], {}
    def text_id(value):
        if value not in text_ids:
            text_ids[value] = len(texts); texts.append(value)
        return text_ids[value]
    def route_id(route):
        key = json.dumps(route, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        if key not in route_ids:
            route_ids[key] = len(routes)
            routes.append({**route, 'condition': text_id(route['condition']), 'rationale': text_id(route['rationale'])})
        return route_ids[key]
    def route_map(mapping):
        return {role: route_id(route) for role, route in mapping.items()}
    core = {key: value for key, value in snapshot.items() if key not in EVIDENCE_FIELDS}
    core['routeDetails'] = {pid: route_map(mapping) for pid, mapping in snapshot['routeDetails'].items()}
    core['strategies'] = {sid: {**strategy, 'routes': route_map(strategy['routes'])} for sid, strategy in snapshot['strategies'].items()}
    return {'format': 'apl.core-transport', 'version': 1, 'snapshot': core, 'texts': texts, 'routes': routes}

def unpack_core(packed):
    texts = packed['texts']
    routes = [{**r, 'condition': texts[r['condition']], 'rationale': texts[r['rationale']]} for r in packed['routes']]
    def expand(mapping): return {role: routes[index] for role, index in mapping.items()}
    s = packed['snapshot']
    return {**s, 'routeDetails': {pid: expand(m) for pid,m in s['routeDetails'].items()},
            'strategies': {sid: {**st, 'routes': expand(st['routes'])} for sid,st in s['strategies'].items()}}

def build_delivery(snapshot, source_path: Path):
    packed = pack_core(snapshot)
    evidence = {key: snapshot[key] for key in EVIDENCE_FIELDS if key in snapshot}
    assert {**unpack_core(packed), **evidence} == snapshot, 'Lossless delivery roundtrip failed'
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    directory = source_path.parent / 'chunks'; directory.mkdir(exist_ok=True)
    manifest = {'format': 'apl.delivery', 'version': 1, 'sourceSha256': source_sha,
                'evidenceFields': list(evidence), 'parts': {}}
    for name, payload in [('core', packed), ('evidence', evidence)]:
        raw = encode(payload); compressed = gzip.compress(raw, compresslevel=6, mtime=0)
        sha = hashlib.sha256(compressed).hexdigest()
        filename = f'{name}-{sha}.json.gz'
        (directory / filename).write_bytes(compressed)
        manifest['parts'][name] = {'path': 'chunks/' + filename, 'sha256': sha,
                                   'bytes': len(compressed), 'decodedBytes': len(raw)}
    # Publish the manifest last; a browser never combines revisions of two files.
    dest = source_path.parent / 'delivery.json'
    tmp = dest.with_suffix('.tmp'); tmp.write_bytes(encode(manifest)); tmp.replace(dest)
    return manifest

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    source = root/'dashboard/public/data/snapshot.json'
    result = build_delivery(json.loads(source.read_bytes()), source)
    print(json.dumps(result, indent=2))
