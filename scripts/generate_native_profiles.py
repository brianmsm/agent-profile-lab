#!/usr/bin/env python3
"""Deterministically serialize active baseline decisions; never install profiles."""
from __future__ import annotations
import csv, json, re
from collections import defaultdict
from pathlib import Path
from harness_contracts import load_harnesses, roles_for
from profile_semantics import critical_review_config
ROOT = Path(__file__).resolve().parents[1]

def native_text(name: str, harness: str, routes: dict, policy: dict | None = None) -> str:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', name) or name in {'constructor','prototype'}:
        raise ValueError(f'Invalid native profile name: {name}')
    if harness == 'gentle-shell':
        return json.dumps({'kind':'gentle-pi.agent_model_profile','version':1,'name':name,'config':routes}, ensure_ascii=False, indent=2)+'\n'
    if harness != 'omp' or policy is None:
        raise ValueError('Unknown harness or missing OMP runtime policy')
    values = [f'  {role}: '+json.dumps(entry['model']+(':'+entry['thinking'] if entry.get('thinking') else '')) for role,entry in routes.items()]
    enabled = str(policy.get('advisor_enabled', 'False')).lower()
    if enabled not in {'true','false'}: raise ValueError('Invalid advisor policy')
    limit = int(policy['task_max_concurrency'])
    if limit < 1: raise ValueError('Invalid concurrency')
    return '\n'.join(['# Primary selectors only; reserves and scope conditions require runtime integration.',
        'modelRoles:',*values,'advisor:',f'  enabled: {enabled}',
        '  syncBacklog: '+json.dumps(policy['advisor_sync_backlog']), 'task:',
        '  eager: '+json.dumps(policy['task_eager']),f'  maxConcurrency: {limit}'])+'\n'

def main() -> None:
    contracts = load_harnesses()
    catalog = {m['key']:m for m in json.loads((ROOT/'data/model-catalog.json').read_text())}
    with (ROOT/'data/assignments.csv').open(encoding='utf-8-sig',newline='') as handle:
        rows = list(csv.DictReader(handle))
    with (ROOT/'data/omp-runtime-policies.csv').open(encoding='utf-8-sig',newline='') as handle:
        policies = {r['profile_id']:r for r in csv.DictReader(handle)}
    groups = defaultdict(dict); metadata = {}
    for row in rows:
        pid, role = row['profile_id'],row['role']
        if role in groups[pid]: raise ValueError(f'Duplicate role: {pid}/{role}')
        meta = (row['harness'],row['portfolio'],row['domain'],row['objective'])
        if pid in metadata and metadata[pid] != meta: raise ValueError('Mixed profile identity')
        metadata[pid] = meta
        m = catalog[row['model_key']]
        if row['model'] != m['selector'] or (row['thinking'] and row['thinking'] not in m['allowed_efforts']):
            raise ValueError(f'Invalid model selection: {pid}/{role}')
        groups[pid][role] = {'model':row['model'], **({'thinking':row['thinking']} if row['thinking'] else {})}
    writes = {}; base_store = {}; critical_store = {}
    catalog_by_selector = {m['selector']:m for m in catalog.values()}
    for pid, routes in sorted(groups.items()):
        harness, portfolio, domain, objective = metadata[pid]
        contract = contracts[harness]; expected = roles_for(contract,domain,objective)
        if set(routes) != set(expected): raise ValueError(f'{pid}: roles differ from harness contract')
        name = f'{portfolio}-{domain}-{objective}'
        routes = {role:routes[role] for role in expected}
        extension = '.export.json' if harness == 'gentle-shell' else '.yaml'
        writes[ROOT/'profiles'/harness/(name+extension)] = native_text(name,harness,routes,policies.get(pid))
        if harness == 'gentle-shell':
            base_store[name] = routes
            critical = critical_review_config(routes,contract['criticalRoles'],catalog_by_selector)
            critical_name = name+'-critical-review'
            writes[ROOT/'profiles/gentle-shell-variants/critical-review'/(critical_name+'.export.json')] = native_text(critical_name,harness,critical)
            critical_store[critical_name] = critical
    for path, store in [('gentle-all.profiles.json',base_store),('gentle-critical-review.profiles.json',critical_store)]:
        writes[ROOT/'profiles'/path] = json.dumps({'kind':'gentle-pi.agent_model_profiles','version':1,'profiles':store},ensure_ascii=False,indent=2)+'\n'
    # Publish only exact expected names after validating the entire input.
    for path, text in writes.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.is_symlink(): raise ValueError(f'Refusing symlink output: {path}')
        if not path.exists() or path.read_text() != text: path.write_text(text)
    print(json.dumps({'baselineProfiles':len(groups),'criticalVariants':len(critical_store),'files':len(writes)}))

if __name__ == '__main__': main()
