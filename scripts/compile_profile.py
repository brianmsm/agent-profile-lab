#!/usr/bin/env python3
"""Compile one profile plus its SHA-linked manifest, offline and without installs."""
from __future__ import annotations
import argparse, json, os, sys, tempfile
from pathlib import Path
from access_catalog import ROOT, load_catalog, read_json
from profile_compiler import compile_request, verify_native
from preflight_profile import preflight

def local_path(value: str) -> Path:
    path=Path(value)
    path=path if path.is_absolute() else ROOT/path
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Input/output must remain inside this repository; never use an active agent-home path')
    return path

def publish_bundle(bundle: dict, destination: Path, overwrite: bool=False) -> tuple[Path,Path]:
    destination=local_path(str(destination))
    filename=bundle['native']['filename']
    if Path(filename).name!=filename: raise ValueError('Unsafe compiled filename')
    native=destination/filename
    manifest=destination/(bundle['manifest']['profileName']+'.manifest.json')
    for path in (destination,native,manifest):
        if path.is_symlink(): raise ValueError('Refusing symlink output')
    if not overwrite and (native.exists() or manifest.exists()):
        raise ValueError('An output already exists; inspect it or pass --overwrite explicitly')
    if not verify_native(bundle['manifest'],bundle['native']['content'].encode()):
        raise ValueError('Native content does not match its manifest')
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.compile-',dir=destination) as tmp:
        first=Path(tmp)/'native'; second=Path(tmp)/'manifest'
        first.write_text(bundle['native']['content'],encoding='utf-8')
        second.write_text(json.dumps(bundle['manifest'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        os.replace(first,native); os.replace(second,manifest)
    return native,manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group()
    source.add_argument('--request',help='Explicit JSON request with resources and route choices')
    source.add_argument('--profile',help='Baseline id, e.g. gentle-shell--plus-data-balanced')
    parser.add_argument('--target',help='Exact reviewed target id; default: current contract for baseline harness')
    parser.add_argument('--policy',choices=['matrix','openai-led','nan-volume','activity-distributed'],default='matrix')
    parser.add_argument('--complexity',choices=['bounded','standard','complex'],default=None)
    parser.add_argument('--high-impact',action='store_true')
    parser.add_argument('--chatgpt-auth',choices=['legacy','siwc'],default='legacy')
    parser.add_argument('--output',default='generated/profiles',help='Repository-local destination')
    parser.add_argument('--overwrite',action='store_true')
    parser.add_argument('--verify-manifest',help='Verify a previously compiled manifest')
    parser.add_argument('--native',help='Native file paired with --verify-manifest')
    parser.add_argument('--native-only',action='store_true',help='Historical forensic check only; does not certify current input hashes')
    args=parser.parse_args()
    if args.verify_manifest:
        if not args.native: parser.error('--verify-manifest requires --native')
        manifest=read_json(local_path(args.verify_manifest))
        native_file=local_path(args.native)
        if manifest.get('nativeArtifact',{}).get('filename')!=native_file.name:
            raise ValueError('Native filename differs from the reviewed manifest')
        raw=native_file.read_bytes()
        if not verify_native(manifest,raw):raise ValueError('Native SHA-256 mismatch; do not use this pair')
        if args.native_only:
            print('HISTORICAL-ONLY: native SHA matches this manifest. Source inputs, semantics and origin are not certified.')
            return
        state=preflight(manifest,raw,root=ROOT)
        if not state['artifactCurrent']:raise ValueError('Manifest/native/source preflight not independently reproducible: '+', '.join(state['requestReproductionErrors']))
        print('Current native and complete manifest reproducible from source and declared request. Not authenticated, executable or safe to deploy.')
        return
    if args.native_only:parser.error('--native-only requires --verify-manifest')
    if args.request:
        if args.target or args.policy!='matrix' or args.chatgpt_auth!='legacy' or args.complexity or args.high_impact:
            parser.error('Put all compilation choices inside --request; CLI overrides are not silently applied')
        request=read_json(local_path(args.request))
    else:
        if not args.profile: parser.error('Provide --profile or --request')
        harness=args.profile.split('--',1)[0]
        targets=load_catalog()['targets']
        candidates=[id for id,t in targets.items() if t['harness']==harness]
        target=args.target or (candidates[0] if len(candidates)==1 else None)
        if target is None: parser.error('An explicit --target is required')
        request={'schemaVersion':1,'baseProfile':args.profile,'targetId':target,'selectionPolicy':args.policy}
        if args.policy=='activity-distributed':request['activity']={'complexity':args.complexity or 'standard','highImpact':args.high_impact}
        elif args.complexity or args.high_impact:parser.error('--complexity/--high-impact require activity-distributed')
        if args.chatgpt_auth=='siwc':request['accessRemap']={'chatgpt-legacy':'chatgpt-siwc'}
    bundle=compile_request(request)
    native,manifest=publish_bundle(bundle,local_path(args.output),args.overwrite)
    print(json.dumps({'native':str(native.relative_to(ROOT)),'manifest':str(manifest.relative_to(ROOT)),
        'sha256':bundle['manifest']['nativeArtifact']['sha256'],'status':bundle['manifest']['status'],
        'target':bundle['manifest']['targetId'],'validation':bundle['manifest']['validation']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,FileNotFoundError) as error:
        print(f'Compilation refused: {error}',file=sys.stderr)
        raise SystemExit(1)
