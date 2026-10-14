#!/usr/bin/env python3
"""Verify the reviewed descriptive-only source amendment and frozen native hashes.

Old source content remains in the repository's own Git history; this receipt
contains hashes, not private history or restricted benchmark values.
"""
from __future__ import annotations
import csv,hashlib,json,io
from strict_data_formats import strict_csv_rows
from reviewed_git_anchors import reviewed_anchor,reviewed_blob,git
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
    # Unlike self-issued digests, the original is fetched from a fixed historic
    # Git commit known by the verifier, not from a mutable receipt field.
    edition,anchor=reviewed_anchor(root)
    original_manifest=reviewed_blob(root,anchor,'data/assignment-shards/manifest.json')
    if hashlib.sha256(original_manifest).hexdigest()!=receipt.get('originalSourceManifestSHA256'):
        raise ValueError('Original source manifest SHA does not match approved Git history')
    if receipt.get('originalHistoryCommit') not in (None,anchor):
        raise ValueError('Claimed historic Git anchor differs from trusted root')
    labels=label_contract(root);count=0
    for relative,record in receipt['sourceFiles'].items():
        p=root/relative
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe amended path')
        historical=reviewed_blob(root,anchor,relative)
        historic_rows,historic_header=strict_csv_rows(historical,label='Historical '+relative)
        rows,_=strict_csv_rows(p.read_bytes(),approved=historic_header,label=relative)
        if hashlib.sha256(historical).hexdigest()!=record.get('originalFileSHA256'):
            raise ValueError('Original source SHA differs from immutable Git blob: '+relative)
        original_rows=historic_rows
        if len(original_rows)!=len(rows) or normalized_digest(rows)!=normalized_digest(original_rows):
            raise ValueError('Non-descriptive source differences relative to reviewed Git anchor: '+relative)
        if record.get('originalNonlabelFieldsSHA256')!=normalized_digest(original_rows):
            raise ValueError('Self-issued nonlabel digest disagrees with historic Git source: '+relative)
        validate_labels(rows,labels,relative)
        if len(rows)!=record['rows'] or sha(p)!=record['currentFileSHA256'] or normalized_digest(rows)!=record['originalNonlabelFieldsSHA256']:raise ValueError('Source change outside reviewed descriptive fields: '+relative)
        count+=len(rows)
    if count!=52134:raise ValueError('Source rows lost or added')
    expected_native={str(p.relative_to(root)) for folder in ['profiles/gentle-shell','profiles/omp','profiles/gentle-shell-variants/critical-review'] for p in (root/folder).glob('*') if p.is_file()}
    if set(receipt['nativeFileSHA256'])!=expected_native or len(expected_native)!=3744:raise ValueError('Native inventory changed')
    # An attacker cannot reissue hashes of modified native profiles and claim
    # historical preservation: Git itself records the reviewed original tree.
    for relative,value in receipt['nativeFileSHA256'].items():
        if sha(root/relative)!=value:raise ValueError('Original native configuration changed: '+relative)
    for folder in ('profiles/gentle-shell','profiles/omp','profiles/gentle-shell-variants/critical-review'):
        if git(root,'diff','--name-only',anchor,'--',folder).strip():
            raise ValueError('Native worktree differs from immutable historic reference: '+folder)
    return {'metadataValid':True,'sourceRowsPreserved':count,'nativeFilesByteIdentical':len(expected_native),'nonlabelFieldsPreserved':True,'modelCalls':0,'historicalAnchor':anchor,'historicalProof':'git-blob-source-comparison-not-digital-signature'}
if __name__=='__main__':print(json.dumps(verify_amendment(),indent=2))
