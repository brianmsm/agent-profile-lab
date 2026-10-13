#!/usr/bin/env python3
"""Blocking offline project check, with optional clean data regeneration/install."""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild',action='store_true',help='Regenerate all local projections from Git-versioned inputs')
    parser.add_argument('--install',action='store_true',help='Install frontend dependencies from the frozen lockfile')
    args=parser.parse_args()
    commands=[]
    def py(path):commands.append((ROOT,[sys.executable,'-B',path]))
    if args.rebuild:
        for path in ['scripts/prepare_data.py','scripts/generate_native_profiles.py',
                     'scripts/normalize_openai_observations.py','scripts/normalize_claude_dashboard_observations.py',
                     'evidence/slopalytics/normalize_snapshot.py','scripts/normalize_supplemental_sources.py','scripts/normalize_reviewed_benchmarks.py']:
            py(path)
    py('scripts/validate_profiles.py')
    if args.rebuild:py('scripts/build_dashboard_snapshot.py')
    for path in ['scripts/validate_source_coverage.py','scripts/validate_access.py','scripts/validate_benchmarks.py',
                 'scripts/test_harness_contracts.py','scripts/test_profile_compiler.py',
                 'scripts/test_access_projection.py','scripts/test_dashboard_strategies.py',
                 'scripts/test_dashboard_cybersecurity.py','scripts/test_resource_economics.py','scripts/test_benchmark_semantics.py','scripts/test_calibration_oracles.py','scripts/test_activity_allocation.py','scripts/test_dashboard_delivery.py','scripts/test_profile_semantics.py','scripts/test_selection_candidates.py','scripts/test_nan_quota_balance.py','scripts/test_nan_static_profiles.py','scripts/test_nan_hybrid_profiles.py','scripts/test_nan_custom_workload.py','scripts/test_nan_quota_optimizer.py','scripts/test_release_readiness.py','scripts/test_workflow_integrity.py']:
        py(path)
    py('scripts/audit_profile_semantics.py')
    py('scripts/selection_candidates.py')
    commands.append((ROOT,['bun','scripts/audit_nan_quota_parity.ts']))
    py('scripts/audit_nan_static_profiles.py')
    commands.append((ROOT,['bun','scripts/audit_nan_static_profiles.ts']))
    py('scripts/audit_nan_hybrid_profiles.py')
    commands.append((ROOT,['bun','scripts/audit_nan_hybrid_profiles.ts']))
    py('scripts/audit_nan_custom_workloads.py')
    commands.append((ROOT,['bun','scripts/audit_nan_custom_workloads.ts']))
    py('scripts/reconcile_evidence_gaps.py') if False else None
    commands.append((ROOT,[sys.executable,'-B','scripts/review_objective_equivalences.py','--verify']))
    commands.append((ROOT,[sys.executable,'-B','scripts/reconcile_evidence_gaps.py','--verify']))
    py('scripts/audit_release_readiness.py')
    commands.append((ROOT,['bun','scripts/validate_gentle_profiles.mjs']))
    if args.install:commands.append((ROOT/'dashboard',['bun','install','--frozen-lockfile']))
    for action in ['test','lint','build']:commands.append((ROOT/'dashboard',['bun','run',action]))
    commands.append((ROOT/'dashboard',['bun','-e',"import {validateSnapshot} from './src/snapshotIO'; const s=validateSnapshot(await Bun.file('public/data/snapshot.json').json()); console.log(JSON.stringify({profiles:s.stats.profiles,assignments:s.stats.rows,access:s.access.evidenceState}));"]))
    out=ROOT/'validation';out.mkdir(exist_ok=True)
    results=[]
    for index,(cwd,command) in enumerate(commands):
        log=out/f'check-{index:02d}.log';started=time.monotonic()
        with log.open('w') as handle:result=subprocess.run(command,cwd=cwd,stdout=handle,stderr=subprocess.STDOUT)
        item={'command':command,'cwd':str(cwd.relative_to(ROOT)), 'exitCode':result.returncode,'seconds':round(time.monotonic()-started,3),'log':str(log.relative_to(ROOT))}
        results.append(item)
        print(('PASS' if result.returncode==0 else 'FAIL')+' '+' '.join(command[:4]),flush=True)
        (out/'project-check.json').write_text(json.dumps({'complete':False,'steps':results},indent=2)+'\n')
        if result.returncode:
            print(log.read_text()[-10000:]);raise SystemExit(result.returncode)
    (out/'project-check.json').write_text(json.dumps({'complete':True,'steps':results,'inferencesSent':0},indent=2)+'\n')
    print(f'All {len(results)} checks completed. No model calls or installed profile changes.',flush=True)
if __name__=='__main__':main()
