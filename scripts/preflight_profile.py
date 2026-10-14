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
    if not isinstance(refs,dict) or not refs or len(refs)>256:raise ValueError('Missing/bounded source hashes required')
    for required in ('contracts/harnesses.json','catalog/offerings.json','scripts/profile_compiler.py'):
        if required not in refs:raise ValueError('Required source identity missing: '+required)
    stale=[]
    for relative,digest in refs.items():
        if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Invalid source SHA-256')
        path=source_path(root,relative)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:stale.append(relative)
    return {'current':not stale,'checked':len(refs),'staleInputs':sorted(stale)}

def preflight(manifest: dict, content: bytes, runtime_version: str|None=None, root: Path=ROOT) -> dict:
    if manifest.get('format')!='agent-profile-lab.compiled-profile' or manifest.get('schemaVersion')!=1:
        raise ValueError('Unknown compiled manifest format')
    native=manifest.get('nativeArtifact',{})
    if not isinstance(native,dict) or not re.fullmatch('[0-9a-f]{64}',native.get('sha256','')):
        raise ValueError('Missing native SHA-256')
    native_ok=hashlib.sha256(content).hexdigest()==native['sha256']
    inputs=check_inputs(manifest,root)
    contract=read_json(root/'contracts/harnesses.json')['harnesses'].get(manifest.get('harness'))
    if contract is None:raise ValueError('Unknown harness')
    expected=contract['runtime']['version']
    if runtime_version is not None and not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?',runtime_version):
        raise ValueError('Use an explicit semantic runtime version, not a shell command')
    contract_ok=manifest.get('harnessVersion')==contract['harnessVersion'] and manifest.get('runtime')==contract['runtime']
    functions_ok=all(role in contract['roles'] and row.get('functionId')==contract['roles'][role]['functionId'] for role,row in manifest.get('roles',{}).items())
    expected_roles=set(roles_for(contract,manifest.get('domain',''),manifest.get('objective','')))
    roles_ok=bool(manifest.get('roles')) and functions_ok and set(manifest['roles'])==expected_roles
    version_ok=None if runtime_version is None else runtime_version==expected
    ready=native_ok and inputs['current'] and contract_ok and roles_ok and version_ok is not False
    return {'schemaVersion':1,'artifactCurrent':bool(ready),'nativeHashMatches':native_ok,'sourceInputs':inputs,
      'contractMatches':contract_ok,'roleSemanticsMatch':roles_ok,'expectedRuntimeVersion':expected,
      'declaredRuntimeVersion':runtime_version,'runtimeVersionMatches':version_ok,
      'runtimeVersionEvidence':'user-declared-not-probed' if runtime_version else 'not-provided',
      'readyForOperation':False,'controlsVerified':False,'providerCalls':0,
      'requiredNextChecks':['scope-and-authorization','tool-permissions','secret-isolation','acceptance-oracle','human-review-for-impact','actual-endpoint-identity-and-effort'],
      'meaning':'Artifact currency is not runtime compatibility, security enforcement, entitlement or empirical model quality.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--runtime-version');a=p.parse_args()
    result=preflight(read_json(a.manifest),a.native.read_bytes(),a.runtime_version)
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['artifactCurrent'] else 2)
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,OSError) as e:raise SystemExit('Preflight refused: '+str(e))
