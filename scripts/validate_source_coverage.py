#!/usr/bin/env python3
"""Verify the generated snapshot/coverage receipt without network or regeneration."""
from pathlib import Path
from dashboard_source_coverage import digest, load_json, verify_input, validate_coverage
from dashboard_cybersecurity import validate_cybersecurity_evidence

ROOT = Path(__file__).resolve().parents[1]


def main():
    receipt = load_json(ROOT / 'validation/source-coverage-receipt.json')
    snapshot = load_json(ROOT / 'dashboard/public/data/snapshot.json')
    coverage = snapshot['sourceCoverage']
    validate_coverage(coverage, snapshot['benchmarks'])
    validate_cybersecurity_evidence(snapshot['cybersecurityEvidence'], snapshot['benchmarks'],
                                   snapshot['catalog'], coverage, root=ROOT)
    if receipt.get('schemaVersion') != 1 or receipt['totals'] != coverage['totals'] or receipt['generatedAt'] != coverage['generatedAt']:
        raise ValueError('Coverage receipt does not describe this snapshot')
    if receipt.get('snapshot_sha256') != digest(ROOT / 'dashboard/public/data/snapshot.json'):
        raise ValueError('Snapshot bytes do not match coverage receipt')
    if not receipt.get('input_sha256'):
        raise ValueError('Coverage receipt has no input hashes')
    for path, sha256 in receipt['input_sha256'].items():
        verify_input(ROOT, dict(path=path, sha256=sha256))
    recorded = {a['path']: a['sha256'] for a in coverage['artifacts']}
    if recorded != receipt['input_sha256']:
        raise ValueError('Receipt/artifact inventory mismatch')
    ids = {s['id'] for s in coverage['sources']}
    registry = load_json(ROOT / 'sources/ledger.json')
    ledger_ids = {r['source_id'] for r in registry}
    if ledger_ids != set(receipt['declaredRegistryIds']) or not ledger_ids <= ids or receipt['registrySources'] != len(registry):
        raise ValueError('Not all registered sources accounted')
    datasets = receipt['datasets']
    declared = load_json(ROOT / 'sources/dashboard-coverage-manifest.json')['datasets']
    if {d['name'] for d in datasets} != {d['name'] for d in declared} or len(datasets) != len(declared):
        raise ValueError('Incomplete normalized dataset inventory')
    if sum(d['active'] for d in datasets) != coverage['totals']['benchmarks']:
        raise ValueError('Dataset active counts do not sum to benchmarks')
    for dataset in datasets:
        if dataset['emitted'] != dataset['active'] + dataset['exactDuplicates'] or recorded.get(dataset['path']) != dataset['sha256']:
            raise ValueError(f'Invalid dataset reconciliation: {dataset["name"]}')
    print(f'Offline source coverage verified: {len(ids)} sources, {len(recorded)} artifacts, {len(snapshot["benchmarks"])} benchmark observations; unavailable sources are explicitly reconciled, not fabricated scores.')


if __name__ == '__main__':
    main()
