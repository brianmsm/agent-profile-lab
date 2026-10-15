#!/usr/bin/env python3
"""Offline manifest/input/native preflight. Never authenticates, installs or executes agents.

Exit 0 means current artifact + explicitly checked version (when provided), not
permission to run. Actual tools, controls, billing and model acceptance remain
external requirements. Historical examples are reported, never overwritten.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path, PurePosixPath
from access_catalog import read_json
from harness_contracts import roles_for
from profile_compiler import COMPILATION_INPUTS, compile_request
from verify_source_amendment import verify_amendment
from reviewed_policy_contract import verify_reviewed_policy
from strict_data_formats import json_loads_strict, schema_version_is_one
ROOT=Path(__file__).resolve().parents[1]
SAFE_PREFIXES=('catalog/','contracts/','policies/','scripts/','dashboard/src/')
SAFE_DATA={'data/assignment-shards/manifest.json','data/portfolios.csv','data/omp-runtime-policies.csv','data/domain-objective-contracts.json'}

def source_path(root: Path, relative: str) -> Path:
    if not isinstance(relative,str):raise ValueError('Input locator must be a string')
    posix=PurePosixPath(relative)
    if posix.is_absolute() or '..' in posix.parts or '\\' in relative or not (relative.startswith(SAFE_PREFIXES) or relative in SAFE_DATA):
        raise ValueError('Unsafe or unsupported source locator')
    path=root/relative
    if any(p.is_symlink() for p in [path,*path.parents] if p!=root.parent):
        raise ValueError('Symlink source refused')
    if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Source outside repository')
    return path

def check_inputs(manifest: dict, root: Path=ROOT) -> dict:
    refs=manifest.get('inputsSha256')
    if not isinstance(refs,dict):raise ValueError('Missing source hash inventory')
    expected=set(COMPILATION_INPUTS)
    if set(refs)!=expected:
        raise ValueError('Incomplete/unreviewed compiler dependencies; missing=' +
            ','.join(sorted(expected-set(refs)))+' extra='+','.join(sorted(set(refs)-expected)))
    stale=[]
    for relative,digest in refs.items():
        if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Invalid source SHA-256')
        path=source_path(root,relative)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:stale.append(relative)
    shard_stale=[];checked_shards=0
    manifest_path=source_path(root,'data/assignment-shards/manifest.json')
    try:
        leaves=json_loads_strict(manifest_path.read_bytes())
    except (ValueError,OSError) as e:raise ValueError('Invalid transitive shard inventory') from e
    if not schema_version_is_one(leaves.get('schemaVersion')) or not isinstance(leaves.get('shards'),dict):
        raise ValueError('Invalid source-shard index')
    base=root/'data/assignment-shards'
    actual={p.relative_to(base).as_posix() for p in base.glob('*/*.csv')}
    if len(actual)!=12 or set(leaves['shards'])!=actual:
        raise ValueError('Transitive shard coverage changed')
    for name,entry in sorted(leaves['shards'].items()):
        if not isinstance(entry,dict) or not re.fullmatch('[0-9a-f]{64}',entry.get('sha256','')):
            raise ValueError('Invalid source-shard SHA-256')
        if name not in actual:raise ValueError('Unknown source shard')
        path=base/name
        if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
            raise ValueError('Unsafe transitive shard path')
        checked_shards+=1
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            shard_stale.append('data/assignment-shards/'+name)
    return {'current':not stale and not shard_stale,'checked':len(refs),
        'expectedInputs':len(expected),'transitiveShardsChecked':checked_shards,
        'staleInputs':sorted(stale),'staleShards':sorted(shard_stale)}

def preflight(manifest: dict, content: bytes, runtime_version: str|None=None, root: Path=ROOT) -> dict:
    if not isinstance(manifest,dict) or manifest.get('format')!='agent-profile-lab.compiled-profile' or not schema_version_is_one(manifest.get('schemaVersion')):
        raise ValueError('Unknown compiled manifest format')
    native=manifest.get('nativeArtifact',{})
    if not isinstance(native,dict) or not re.fullmatch('[0-9a-f]{64}',native.get('sha256','')):
        raise ValueError('Missing native SHA-256')
    if not isinstance(content,bytes) or len(content)>32*1024*1024:
        raise ValueError('Native must be a bounded byte string')
    native_ok=hashlib.sha256(content).hexdigest()==native['sha256']
    inputs=check_inputs(manifest,root)
    anchor_result=verify_amendment(root)  # immutable historic Git blobs; no self-issued origin claims
    reviewed_policy=verify_reviewed_policy(root)
    harnesses=read_json(root/'contracts/harnesses.json')['harnesses']
    contract=harnesses.get(manifest.get('harness'))
    if contract is None:raise ValueError('Unknown harness')
    expected=contract['runtime']['version']
    if runtime_version is not None and not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?',runtime_version):
        raise ValueError('Use an explicit semantic runtime version, not a shell command')
    contract_ok=manifest.get('harnessVersion')==contract['harnessVersion'] and manifest.get('runtime')==contract['runtime']
    all_roles=manifest.get('roles')
    functions_ok=isinstance(all_roles,dict) and all(
        role in contract['roles'] and isinstance(row,dict) and row.get('functionId')==contract['roles'][role]['functionId']
        for role,row in all_roles.items())
    expected_roles=set(roles_for(contract,manifest.get('domain',''),manifest.get('objective','')))
    roles_ok=bool(all_roles) and functions_ok and set(all_roles)==expected_roles
    version_ok=None if runtime_version is None else runtime_version==expected
    reproduction_errors=[]
    native_semantic=False;manifest_semantic=False
    request=manifest.get('compilationRequest')
    if not isinstance(request,dict):
        reproduction_errors.append('compilation-request-missing; recompile from current source')
    elif inputs['current'] and anchor_result['nonlabelFieldsPreserved']:
        try:
            reproduced=compile_request(request,root)
            native_semantic=(reproduced['native']['content'].encode('utf-8')==content)
            manifest_semantic=(reproduced['manifest']==manifest)
            if not native_semantic:reproduction_errors.append('native-does-not-reproduce-from-request')
            if not manifest_semantic:reproduction_errors.append('manifest-does-not-reproduce-from-request')
        except (ValueError,KeyError,TypeError,OSError) as e:
            # Return the failure class, not source text or potential credentials.
            reproduction_errors.append('independent-source-recompilation-refused:'+type(e).__name__)
    else:reproduction_errors.append('source-inputs-are-stale')
    from reviewed_policy_contract import CONTROL_IDS
    controls=list(CONTROL_IDS)
    if not isinstance(controls,list) or len(controls)!=6 or len(set(controls))!=6:
        raise ValueError('External safety-control inventory is missing or inconsistent')
    ready=bool(native_ok and inputs['current'] and anchor_result['nonlabelFieldsPreserved'] and
        contract_ok and roles_ok and native_semantic and manifest_semantic and version_ok is not False)
    return {'schemaVersion':1,'artifactCurrent':ready,'nativeHashMatches':native_ok,
      'nativeSemanticsReproduced':native_semantic,'manifestSemanticsReproduced':manifest_semantic,
      'requestReproductionErrors':reproduction_errors,'sourceInputs':inputs,
      'historicalSourceAnchor':anchor_result['historicalAnchor'],
      'historicalSourceComparedWithGit':anchor_result['nonlabelFieldsPreserved'],
      'contractMatches':contract_ok,'roleSemanticsMatch':roles_ok,'expectedRuntimeVersion':expected,
      'declaredRuntimeVersion':runtime_version,'runtimeVersionMatches':version_ok,
      'runtimeVersionEvidence':'user-declared-not-probed' if runtime_version else 'not-provided',
      'requestAuthenticity':'not-authenticated; self-declared request reproduced from trusted sources',
      'policyReviewed':bool(reviewed_policy['policyReviewedForCurrentStructure'] and manifest.get('domain')=='cybersecurity'),
      'assurancePolicyReviewed':reviewed_policy['policyReviewedForCurrentStructure'],
      'policyReviewedScope':reviewed_policy['reviewScope'],
      'policyReviewedFields':reviewed_policy['reviewedFields'],
      'readyForOperation':False,'controlsVerified':False,'providerCalls':0,
      'requiredNextChecks':[*controls,'actual-endpoint-identity-and-effort'],
      'meaning':'Reproducible native/manifest does not authenticate the requesting person, install controls, or prove model performance.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--runtime-version');a=p.parse_args()
    manifest=read_json(a.manifest)
    if Path(manifest.get('nativeArtifact',{}).get('filename','')).name!=a.native.name:
        raise ValueError('Native filename differs from compiled-manifest name')
    result=preflight(manifest,a.native.read_bytes(),a.runtime_version)
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['artifactCurrent'] else 2)
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,OSError) as e:raise SystemExit('Preflight refused: '+str(e))
