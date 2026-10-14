#!/usr/bin/env python3
"""Verify the reviewed descriptive-only source amendment and frozen native hashes.

Old source content remains in the repository's own Git history; this receipt
contains hashes, not private history or restricted benchmark values.
"""
from __future__ import annotations
import csv,hashlib,json
from pathlib import Path
from metadata_contracts import label_contract,validate_labels
ROOT=Path(__file__).resolve().parents[1]
LABELS={'domain_label','objective_label','portfolio_label'}
OLD='sin benchmarks de computer-use, research, data o web'
NEW='[Nota histórica anterior al 2026-09-30: sin benchmarks de computer-use, research, data o web; sustituida por el inventario documental posterior. Presencia de benchmarks no demuestra eficacia de esta ruta.]'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def normalized_rows(rows):
    return [{k:(v.replace(NEW,OLD) if k in ('profile_context','context_review') else v) for k,v in row.items() if k not in LABELS} for row in rows]
def normalized_digest(rows):
    return hashlib.sha256(json.dumps(normalized_rows(rows),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def verify_amendment(root=ROOT):
    path=root/'policies/source-metadata-amendment.json';receipt=json.loads(path.read_bytes())
    if receipt.get('schemaVersion')!=1 or receipt.get('kind')!='descriptive-source-amendment':raise ValueError('Unknown amendment')
    expected={'data/profile-index.csv'}|{str(p.relative_to(root)) for p in (root/'data/assignment-shards').glob('*/*.csv')}
    if set(receipt['sourceFiles'])!=expected:raise ValueError('Amendment coverage differs from the complete source inventory')
    if sha(root/'data/assignment-shards/manifest.json')!=receipt['currentSourceManifestSHA256']:raise ValueError('Amended source manifest changed')
    labels=label_contract(root);count=0
    for relative,record in receipt['sourceFiles'].items():
        p=root/relative
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe amended path')
        with p.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        validate_labels(rows,labels,relative)
        if len(rows)!=record['rows'] or sha(p)!=record['currentFileSHA256'] or normalized_digest(rows)!=record['originalNonlabelFieldsSHA256']:raise ValueError('Source change outside reviewed descriptive fields: '+relative)
        count+=len(rows)
    if count!=52134:raise ValueError('Source rows lost or added')
    expected_native={str(p.relative_to(root)) for folder in ['profiles/gentle-shell','profiles/omp','profiles/gentle-shell-variants/critical-review'] for p in (root/folder).glob('*') if p.is_file()}
    if set(receipt['nativeFileSHA256'])!=expected_native or len(expected_native)!=3744:raise ValueError('Native inventory changed')
    for relative,value in receipt['nativeFileSHA256'].items():
        if sha(root/relative)!=value:raise ValueError('Original native configuration changed: '+relative)
    return {'metadataValid':True,'sourceRowsPreserved':count,'nativeFilesByteIdentical':len(expected_native),'nonlabelFieldsPreserved':True,'modelCalls':0}
if __name__=='__main__':print(json.dumps(verify_amendment(),indent=2))
