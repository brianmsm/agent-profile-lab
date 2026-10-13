#!/usr/bin/env python3
"""Rebuild active data from hashed decisions and versioned harness contracts.

Retired decisions remain in the Git-versioned input shards and are projected into
portable functional precedents, never executable profile slots. No provider calls
or changes to installed agent homes occur here.
"""
from __future__ import annotations
import csv, gzip, hashlib, json, sys
from collections import Counter
from pathlib import Path
from harness_contracts import load_harnesses, is_retired, roles_for
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SHARDS = DATA / 'assignment-shards'

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_decisions(root: Path = ROOT) -> tuple[list[dict], list[str]]:
    directory = root / 'data/assignment-shards'
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('schemaVersion') != 1 or not isinstance(manifest.get('shards'), dict):
        raise ValueError('Invalid decision-shard manifest')
    files = sorted(p.relative_to(directory).as_posix() for p in directory.rglob('*.csv'))
    if files != sorted(manifest['shards']):
        raise ValueError('Shard manifest/files disagree')
    rows, seen, header = [], set(), None
    for relative in files:
        path = directory / relative
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError('Unsafe decision-shard path')
        entry = manifest['shards'][relative]
        if digest(path) != entry['sha256']:
            raise ValueError(f'Hash mismatch for {relative}; accept changes explicitly')
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            if header is None: header = reader.fieldnames
            if reader.fieldnames != header: raise ValueError(f'Field mismatch: {relative}')
            records = list(reader)
        if len(records) != entry['rows']: raise ValueError(f'Row count changed: {relative}')
        for row in records:
            identity = row['profile_id'], row['role']
            if identity in seen: raise ValueError(f'Duplicate assignment: {identity}')
            seen.add(identity)
            if f"{row['domain']}/{row['harness']}.csv" != relative:
                raise ValueError(f'Shard dimensions disagree: {relative}')
        rows.extend(records)
    if len(rows) != manifest['totalRows']: raise ValueError('Manifest total disagrees')
    return rows, header or []

def partition_decisions(rows: list[dict], contracts: dict) -> tuple[list[dict], list[dict]]:
    active, retired = [], []
    for row in rows:
        contract = contracts.get(row['harness'])
        if contract is None: raise ValueError(f"Unknown harness: {row['harness']}")
        if is_retired(contract, row['role']):
            retired.append(row)
        elif row['role'] not in roles_for(contract, row['domain'], row['objective']):
            raise ValueError(f"Unsupported role: {row['harness']}/{row['role']}")
        else:
            active.append(row)
    return active, retired

def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)

def main() -> None:
    from prepare_catalog import main as prepare_catalog
    prepare_catalog()
    rows, header = load_decisions()
    contracts = load_harnesses()
    active, retired = partition_decisions(rows, contracts)
    domain_contracts=json.loads((ROOT/'data/domain-objective-contracts.json').read_text())['domains']
    for row in active:
        if domain_contracts[row['domain']]['gate'] not in row['quality_gate']:
            raise ValueError(f"{row['profile_id']}/{row['role']}: quality gate belongs to another domain or is incomplete")
    functions = json.loads((ROOT / 'policies/functions.json').read_text())['functions']
    retired_map = {v['retiredNativeRole']: key for key, v in functions.items() if 'retiredNativeRole' in v}
    precedents = {}
    fields = ['domain','objective','model_key','thinking','fallback_model','fallback_thinking',
              'role_judgment','profile_context','rationale','quality_gate','source_ids','rule_ids']
    for row in retired:
        if row['role'] not in retired_map: raise ValueError('Retired role has no portable function mapping')
        function = retired_map[row['role']]
        decision = {key: row[key] for key in fields}
        key = hashlib.sha256(json.dumps([function, decision], sort_keys=True).encode()).hexdigest()[:24]
        if key not in precedents:
            precedents[key] = {'functionId': function, 'decision': decision, 'sourceProfiles': []}
        precedents[key]['sourceProfiles'].append(row['profile_id'])
    with (DATA / 'profile-index.csv').open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle); index_fields = reader.fieldnames; index = list(reader)
    counts = Counter(row['profile_id'] for row in active)
    if len(index) != len(counts) or {row['profile_id'] for row in index} != set(counts):
        raise ValueError('Profile metadata disagrees with active decision groups')
    for row in index:
        row['total_assignments'] = str(counts[row['profile_id']])
        if row['objective'] == 'best': row['objective_label'] = 'Máxima calidad'
    # All inputs have been checked before publishing derived outputs.
    write_csv(DATA / 'assignments.csv', active, header)
    (DATA / 'assignments.json').write_text(json.dumps(active, ensure_ascii=False, separators=(',', ':')))
    # Deterministic gzip bytes across repeated builds.
    (DATA / 'assignments.csv.gz').write_bytes(gzip.compress((DATA / 'assignments.csv').read_bytes(), mtime=0))
    write_csv(DATA / 'profile-index.csv', index, index_fields)
    (DATA / 'profiles.json').write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n')
    (ROOT / 'policies/functional-precedents.json').write_text(json.dumps({
        'schemaVersion': 1, 'status': 'precedents-not-calibration', 'sourceDecisions': len(retired),
        'source': 'data/assignment-shards; retired roles declared by contracts/harnesses.json',
        'precedents': precedents,
    }, ensure_ascii=False, separators=(',', ':'))+'\n')
    print(json.dumps({'activeAssignments':len(active),'retiredDecisionsPreserved':len(retired),
                      'profiles':len(index),'portablePrecedents':len(precedents)}, indent=2))

if __name__ == '__main__':
    try: main()
    except (ValueError, KeyError, FileNotFoundError) as error:
        print(f'Data preparation failed: {error}', file=sys.stderr)
        raise SystemExit(1)
