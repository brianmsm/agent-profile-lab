#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,hashlib,json,re,unicodedata
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from dashboard_cybersecurity import validate_evidence_boundary
from access_catalog import load_catalog, compatibility_models
from profile_semantics import EFFORT_ORDER
from security_gate_language import explicit_permission_contradiction


ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'data/assignments.csv'
from strict_data_formats import strict_csv_rows
rows,_=strict_csv_rows(A.read_bytes(),label='data/assignments.csv')
catalog=json.load(open(ROOT/'data/model-catalog.json')); bykey={m['key']:m for m in catalog}; bysel={m['selector']:m for m in catalog}
ports={r['id']:r for r in csv.DictReader((ROOT/'data/portfolios.csv').open(encoding='utf-8-sig',newline=''))}
domain_objective_contract=json.load(open(ROOT/'data/domain-objective-contracts.json',encoding='utf-8'))
domain_contracts=domain_objective_contract.get('domains',{})
objective_contracts=domain_objective_contract.get('objectives',{})
domains=set(domain_contracts)
objectives=set(objective_contracts)
index,_=strict_csv_rows((ROOT/'data/profile-index.csv').read_bytes(),label='data/profile-index.csv')
from metadata_contracts import label_contract, validate_labels
validate_labels(rows, label_contract(ROOT), 'active assignments')
validate_labels(index, label_contract(ROOT), 'profile index')
profiles_json=json.load(open(ROOT/'data/profiles.json'))
from harness_contracts import load_harnesses, roles_for, is_retired
harness_contracts=load_harnesses()
expected_roles={h:list(c['roles']) for h,c in harness_contracts.items()}
issues=[]; checks=[]

def check(name,ok,detail=''):
    checks.append({'check':name,'ok':bool(ok),'detail':detail})
    if not ok: issues.append((name,detail))

check('normalized_catalog_projection_exact',catalog==compatibility_models(load_catalog()),'data/model-catalog.json must be derived from catalog/offerings.json')

def normalize_text(value):
    return ''.join(ch for ch in unicodedata.normalize('NFKD',str(value)).casefold() if not unicodedata.combining(ch))

def is_negated(text,term):
    term=re.escape(term)
    return bool(re.search(rf'\b(?:no|sin|ningun\w*|not|without|prohib\w*|prohibit\w*)\b.{{0,100}}\b{term}\w*',text)
                or re.search(rf'\b{term}\w*.{{0,100}}\b(?:no|sin|ningun\w*|not|without|prohib\w*|prohibit\w*)\b',text))

def has_security_gate(value):
    text=normalize_text(value)
    required=('autoriz','alcance','activo','secret','proteg','aislad','reproduc','evid','remedi','regres','revision','human','impact','destruct','persist','real','document')
    return (not explicit_permission_contradiction(value) and all(token in text for token in required) and is_negated(text,'destruct')
            and is_negated(text,'persist') and is_negated(text,'real'))

def allowed_pools(portfolio):
    pools=set()
    if portfolio.get('openai')!='none': pools.add('OAI')
    if portfolio.get('gateway')=='go': pools.add('GO')
    if portfolio.get('gateway')=='cc': pools.add('CC')
    if portfolio.get('gateway')=='anthropic' or portfolio.get('anthropic')=='True': pools.add('ANTHROPIC')
    if portfolio.get('nan')=='True': pools.add('NAN')
    return pools

def expected_roles_for(harness,domain,objective):
    return set(roles_for(harness_contracts[harness],domain,objective))

AGENT_USE_EXCLUSIONS={
    pid:'No OpenAI primary pool and Command-only gateway; agent-use Command GUI vision remains unverified (A07).'
    for pid,p in ports.items()
    if p.get('openai')=='none' and p.get('gateway')=='cc'
}
expected_combinations={
    (h,p,d,o)
    for h in expected_roles
    for p in ports
    for d in domains
    for o in objectives
    if not (d=='agent-use' and p in AGENT_USE_EXCLUSIONS)
}
expected_ids={f'{h}--{p}-{d}-{o}' for h,p,d,o in expected_combinations}
expected_assignment_count=sum(
    len(expected_roles_for(h,d,o))
    for h,p,d,o in expected_combinations
)

groups=defaultdict(list)
for r in rows: groups[(r['harness'],r['portfolio'],r['domain'],r['objective'])].append(r)
actual_combinations=set(groups)
actual_domains={r['domain'] for r in rows}
actual_objectives={r['objective'] for r in rows}
actual_harnesses={r['harness'] for r in rows}
actual_portfolios={r['portfolio'] for r in rows}
required_domains={'data','research','cybersecurity'}
required_objectives={'economy','balanced','speed','best'}
check('domain_objective_contract_dimensions',
      bool(domains) and bool(objectives) and required_domains<=domains and objectives==required_objectives
      and actual_domains==domains and actual_objectives==objectives,
      f'domains={sorted(actual_domains)} contract={sorted(domains)} required={sorted(required_domains)} objectives={sorted(actual_objectives)} contract={sorted(objectives)} expected={sorted(required_objectives)}')
check('cybersecurity_contract_fields',
      'cybersecurity' in domain_contracts and domain_contracts.get('cybersecurity',{}).get('label')=='Ciberseguridad'
      and all(domain_contracts.get('cybersecurity',{}).get(k) for k in ('gate','critical','routine','scope','evidenceNote')),
      'cybersecurity requires label Ciberseguridad, gate, critical, routine, scope and evidenceNote')
check('harness_dimensions',actual_harnesses==set(expected_roles),f'actual={sorted(actual_harnesses)} expected={sorted(expected_roles)}')
check('portfolio_dimensions',actual_portfolios==set(ports),f'actual={sorted(actual_portfolios)} expected={sorted(ports)}')
check('portfolio_catalog_size',len(ports)==53,str(len(ports)))
check('profile_combinations_exact',actual_combinations==expected_combinations,
      f'missing={len(expected_combinations-actual_combinations)} extra={len(actual_combinations-expected_combinations)}')
check('assignment_rows',len(rows)==expected_assignment_count,f'actual={len(rows)} expected_from_contract={expected_assignment_count}')
check('profile_groups',len(groups)==len(expected_combinations),f'actual={len(groups)} expected_from_contract={len(expected_combinations)}')
profile_id_bad=[(r['profile_id'],f"{r['harness']}--{r['portfolio']}-{r['domain']}-{r['objective']}")
                for r in rows if r['profile_id']!=f"{r['harness']}--{r['portfolio']}-{r['domain']}-{r['objective']}"]
check('profile_ids_match_dimensions',not profile_id_bad,str(profile_id_bad[:20]))
for key,rs in groups.items():
    h,p,d,o=key
    expected=expected_roles_for(h,d,o)
    actual={r['role'] for r in rs}
    check('role_set_'+':'.join(key),actual==expected,f'missing={sorted(expected-actual)} extra={sorted(actual-expected)}')
    check('role_unique_'+':'.join(key),len(actual)==len(rs),f'rows={len(rs)} unique_roles={len(actual)}')

# Plan/model/effort contracts
contract_fail=[]
for r in rows:
 p=ports.get(r['portfolio'])
 if not p:
  contract_fail.append(('unknown_portfolio',r['profile_id'],r['role'],r['portfolio']));continue
 pools=allowed_pools(p)
 m=bykey.get(r['model_key'])
 if not m:
  contract_fail.append(('unknown_model_key',r['profile_id'],r['role'],r['model_key']));continue
 if r['model']!=m['selector']: contract_fail.append(('selector_mismatch',r['profile_id'],r['role'],r['model'],m['selector']))
 if m['pool'] not in pools: contract_fail.append(('primary_pool',r['profile_id'],r['role'],m['pool'],pools))
 if r['thinking'] and r['thinking'] not in m['allowed_efforts']: contract_fail.append(('thinking',r['profile_id'],r['role'],r['thinking'],m['allowed_efforts']))
 for fld,effort_fld in [('fallback_model','fallback_thinking'),('accelerator_model','accelerator_thinking')]:
  sel=r.get(fld,'')
  if not sel:
   if r.get(effort_fld,''): contract_fail.append(('orphan_'+effort_fld,r['profile_id'],r['role'],r[effort_fld]))
   continue
  fm=bysel.get(sel)
  if not fm: contract_fail.append(('unknown_'+fld,r['profile_id'],r['role'],sel))
  elif fm['pool'] not in pools: contract_fail.append((fld+'_pool',r['profile_id'],r['role'],fm['pool'],pools))
  elif r.get(effort_fld,'') and r[effort_fld] not in fm['allowed_efforts']:
   contract_fail.append((effort_fld,r['profile_id'],r['role'],r[effort_fld],fm['allowed_efforts']))
check('model_plan_effort_contracts',not contract_fail,json.dumps([tuple(str(x) for x in f) for f in contract_fail[:20]],ensure_ascii=False))

# Derived rows are a projection of the hashed SOURCE shards, not an
# independently editable replacement. The individual validator must detect
# coherent alterations to CSV/JSON/GZip rather than relying on another CI step.
from prepare_data import load_decisions,partition_decisions
from source_projection_contract import validate_source_projection
source_rows,_=partition_decisions(load_decisions(ROOT)[0],harness_contracts)
try:
 validate_source_projection(source_rows,rows)
 projection_error=''
except ValueError as e:projection_error=str(e)
check('active_source_projection_exact',not projection_error,projection_error)

# Required traceability fields and row JSON fields
trace_fail=[]
for r in rows:
 for fld in ['decision_id','role_judgment','profile_context','rationale','quality_gate','source_ids','source_urls','warnings','rule_ids']:
  if r.get(fld,'')=='': trace_fail.append((r['profile_id'],r['role'],fld))
 for fld in ['source_ids','source_urls','warnings','rule_ids']:
  try:
   value=json.loads(r[fld])
   if not isinstance(value,list) or (fld!='warnings' and not value):
    trace_fail.append((r['profile_id'],r['role'],fld,'expected-nonempty-list'))
   elif any(not isinstance(v,str) or not v.strip() for v in value):
    trace_fail.append((r['profile_id'],r['role'],fld,'non-string-or-empty-item'))
   elif fld=='source_urls' and any(not (v.startswith('https://') or v.startswith('evidence/nan/'))
                                   for v in value):
    trace_fail.append((r['profile_id'],r['role'],fld,'unreviewed-provenance-locator'))
  except (ValueError,TypeError) as e:trace_fail.append((r['profile_id'],r['role'],fld,type(e).__name__))
check('traceability_fields',not trace_fail,json.dumps(trace_fail[:20],ensure_ascii=False))

cyber_gate_bad=[]
cyber_provenance_bad=[]
cyber_route_bad=[]
rows_by_group_role={(r['harness'],r['portfolio'],r['domain'],r['objective'],r['role']):r for r in rows}
for r in rows:
 if r['domain']!='cybersecurity': continue
 if not has_security_gate(r.get('quality_gate','')): cyber_gate_bad.append((r['profile_id'],r['role'],'quality_gate'))
 provenance=' '.join(r.get(fld,'') for fld in ('profile_context','rationale','warnings'))
 provenance_norm=normalize_text(provenance)
 if not ('apps' in provenance_norm and any(w in provenance_norm for w in ('hered','deriv','clon','equival'))
         and ('ciber' in provenance_norm or 'cyber' in provenance_norm) and is_negated(provenance_norm,'evid')):
  cyber_provenance_bad.append((r['profile_id'],r['role']))
 app=rows_by_group_role.get((r['harness'],r['portfolio'],'apps',r['objective'],r['role']))
 if app is None:
  cyber_route_bad.append((r['profile_id'],r['role'],'missing_apps_reference'))
 elif any(r.get(fld,'')!=app.get(fld,'') for fld in ('model_key','model','thinking','fallback_model','fallback_thinking','accelerator_model','source_ids')):
  cyber_route_bad.append((r['profile_id'],r['role'],'apps_route_or_source_mismatch'))
cyber_contract=domain_contracts.get('cybersecurity',{})
contract_gate_bad=not has_security_gate(cyber_contract.get('gate',''))
try:
 validate_evidence_boundary(cyber_contract)
 evidence_note_bad=False
except ValueError:
 evidence_note_bad=True
check('cybersecurity_contract_gate',not contract_gate_bad,cyber_contract.get('gate',''))
check('cybersecurity_contract_evidence_boundary',not evidence_note_bad,json.dumps(cyber_contract.get('evidenceBoundary'),ensure_ascii=False))
check('cybersecurity_assignment_gates',not cyber_gate_bad,str(cyber_gate_bad[:20]))
check('cybersecurity_apps_provenance',not cyber_provenance_bad,str(cyber_provenance_bad[:20]))
check('cybersecurity_apps_route_equivalence',not cyber_route_bad,str(cyber_route_bad[:20]))


# JSON and gzip equivalence with CSV
json_rows=json.load(open(ROOT/'data/assignments.json'))
check('assignments_json_exact',json_rows==rows,f'json={len(json_rows)} csv={len(rows)}')
with gzip.open(ROOT/'data/assignments.csv.gz','rb') as f: gz=f.read()
check('assignments_gzip_exact',gz==A.read_bytes(),f'gzip_bytes={len(gz)} csv_bytes={A.stat().st_size}')

# Profile metadata exact, corrected names, native file existence
idx_ids={r['profile_id'] for r in index}
check('profile_index',len(index)==len(expected_combinations),f'actual={len(index)} expected={len(expected_combinations)}')
check('profile_index_ids_exact',len(idx_ids)==len(index) and idx_ids==expected_ids,f'diff={len(idx_ids^expected_ids)} duplicates={len(index)-len(idx_ids)}')
def _norm_meta(rs):
 return [{k: ('' if v is None else str(v)) for k,v in r.items()} for r in rs]
check('profiles_json_exact_metadata',_norm_meta(profiles_json)==_norm_meta(index),f'json={len(profiles_json)} csv={len(index)}')
name_fail=[]
for r in index:
 expected_name=f"{r['portfolio']}-{r['domain']}-{r['objective']}"
 if r['name']!=expected_name or r['profile_id']!=f"{r['harness']}--{expected_name}": name_fail.append(r['profile_id'])
 if 'audit-' in r['name'] or 'audit-' in Path(r['native_file']).name: name_fail.append('stale:'+r['profile_id'])
 if not (ROOT/r['native_file']).exists(): name_fail.append('missing:'+r['native_file'])
check('profile_names_and_paths',not name_fail,str(name_fail[:20]))

# Native serialization exact against canonical rows
native=set(); native_files=0
for p in (ROOT/'profiles/gentle-shell').glob('*.export.json'):
 native_files+=1; x=json.loads(p.read_text()); pid='gentle-shell--'+x['name']
 for role,e in x['config'].items(): native.add('\t'.join([pid,role,e['model'],e.get('thinking','')]))
for p in (ROOT/'profiles/omp').glob('*.yaml'):
 native_files+=1; pid='omp--'+p.stem; in_roles=False
 for line in p.read_text().splitlines():
  if line.strip()=='modelRoles:': in_roles=True; continue
  if in_roles and line and not line.startswith(' '):
   in_roles=False
  if not in_roles: continue
  m=re.match(r'^  ([^:]+):\s+"(.*)"$',line)
  if not m: continue
  role,value=m.groups(); mm=re.match(r'^(.*):(low|medium|high|xhigh|max|minimal)$',value)
  model,thinking=mm.groups() if mm else (value,'')
  native.add('\t'.join([pid,role,model,thinking]))
canon=set('\t'.join([r['profile_id'],r['role'],r['model'],r['thinking']]) for r in rows)
check('native_file_count',native_files==len(expected_combinations),f'actual={native_files} expected={len(expected_combinations)}')
check('native_serialization_exact',native==canon,f'native={len(native)} canon={len(canon)} missing={len(canon-native)} extra={len(native-canon)}')

# Gentle store equals all Gentle native exports exactly
store=json.load(open(ROOT/'profiles/gentle-all.profiles.json'))
gnative={}
for p in (ROOT/'profiles/gentle-shell').glob('*.export.json'):
 x=json.loads(p.read_text()); gnative[x['name']]=x['config']
check('gentle_store_exact',store.get('profiles')==gnative,f'store={len(store.get("profiles",{}))} native={len(gnative)}')

# Cross-specification checks independent from generator implementation.
wrong_gates=[(r['profile_id'],r['role']) for r in rows if domain_contracts[r['domain']]['gate'] not in r['quality_gate']]
check('all_domain_acceptance_gates_match',not wrong_gates,str(wrong_gates[:20]))
noop_reserves=[(r['profile_id'],r['role']) for r in rows if r['fallback_model'] and r['fallback_model']==r['model'] and r['fallback_thinking']==r['thinking']]
check('fallbacks_are_distinct_effective_routes',not noop_reserves,str(noop_reserves[:20]))
visual_reserves=[(r['profile_id'],r['role'],field) for r in rows if harness_contracts[r['harness']]['roles'][r['role']]['functionId']=='visual-inspection' for field in ('fallback_model','accelerator_model') if r.get(field) and bysel[r[field]].get('vision') is not True]
check('visual_reserves_preserve_image_input',not visual_reserves,str(visual_reserves[:20]))

# OMP vision role must be image-capable
vision_bad=[]
for r in rows:
 if r['harness']=='omp' and r['role']=='vision' and not bykey[r['model_key']].get('vision'): vision_bad.append((r['profile_id'],r['model']))
check('omp_vision_capable',not vision_bad,str(vision_bad[:20]))

# Exhaustive semantic regression assertions from contextual audit
rdd_high=[(r['profile_id'],r['role'],r['model']) for r in rows if r['harness']=='gentle-shell' and r['role'] in {'review-risk','review-reliability','review-resilience'} and r['thinking']=='high']
check('rdd_no_domain_high_static_defaults',not rdd_high,str(rdd_high[:20]))
old_jdb=[(r['profile_id'],r['model']) for r in rows if r['harness']=='gentle-shell' and r['role']=='jd-judge-b' and r['model_key']=='oa_oldsol']
check('jd_b_no_forced_oldsol',not old_jdb,str(old_jdb[:20]))
designer_bad=[]
for r in rows:
 if r['harness']=='omp' and r['role']=='designer' and (r['portfolio'].startswith('plus-cc') or r['portfolio'].startswith('pro100-cc')):
  if r['domain'] in {'data','research','web','apps','cybersecurity'} and not bykey[r['model_key']].get('vision'):
   designer_bad.append((r['profile_id'],r['model']))
check('omp_oai_cc_designer_direct_vision',not designer_bad,str(designer_bad[:20]))
go_research_assumption_bad=[]
for r in rows:
 if r['domain']=='research' and r['model'].startswith('opencode-go/'):
  ids=json.loads(r['source_ids'])
  warns=json.loads(r['warnings'])
  if 'GOUSER' not in ids or any('confirmar que el uso concreto' in w for w in warns):
   go_research_assumption_bad.append((r['profile_id'],r['role']))
check('go_research_user_assumption_recorded',not go_research_assumption_bad,str(go_research_assumption_bad[:20]))


# Personalization corrections: metadata, runtime policy, archive/reviewer/task and critical-review variants.
metadata_bad=[]
effort_by_key={}
for r in rows:
 m=bykey[r['model_key']]
 if r['integration_confidence']!=m['integration_confidence']:
  metadata_bad.append((r['profile_id'],r['role'],'integration_confidence',r['integration_confidence'],m['integration_confidence']))
 effort_by_key.setdefault(r['model_key'],set()).add(r['effort_semantics'])
check('model_metadata_integration_exact',not metadata_bad,str(metadata_bad[:20]))
effort_semantic_bad={k:sorted(v) for k,v in effort_by_key.items() if len(v)!=1}
check('effort_semantics_unique_per_model_route',not effort_semantic_bad,json.dumps(effort_semantic_bad,ensure_ascii=False))

runtime=list(csv.DictReader((ROOT/'data/omp-runtime-policies.csv').open(encoding='utf-8-sig',newline='')))
runtime_by_id={}
runtime_duplicates=[]
for pol in runtime:
 if pol['profile_id'] in runtime_by_id: runtime_duplicates.append(pol['profile_id'])
 runtime_by_id[pol['profile_id']]=pol
index_by_id={r['profile_id']:r for r in index}
expected_omp_ids={f"omp--{p}-{d}-{o}" for h,p,d,o in expected_combinations if h=='omp'}
check('omp_runtime_policy_rows',len(runtime)==len(expected_omp_ids),f'actual={len(runtime)} expected={len(expected_omp_ids)}')
check('omp_runtime_policy_ids_exact',set(runtime_by_id)==expected_omp_ids and not runtime_duplicates,
      f'missing={len(expected_omp_ids-set(runtime_by_id))} extra={len(set(runtime_by_id)-expected_omp_ids)} duplicates={runtime_duplicates[:20]}')
policy_metadata_bad=[]
for pol in runtime:
 expected_id=f"omp--{pol['portfolio']}-{pol['domain']}-{pol['objective']}"
 idx=index_by_id.get(pol['profile_id'])
 if pol['profile_id']!=expected_id or not idx or idx.get('harness')!='omp' or any(pol[fld]!=idx[fld] for fld in ('portfolio','domain','objective')) or not pol['profile_id'].startswith('omp--'):
  policy_metadata_bad.append((pol['profile_id'],pol['portfolio'],pol['domain'],pol['objective']))
check('omp_runtime_policy_identity_matches_profile_id_and_index',not policy_metadata_bad,str(policy_metadata_bad[:20]))
runtime_bad=[]
for r in index:
 if r['harness']!='omp': continue
 pol=runtime_by_id.get(r['profile_id'])
 if not pol:
  runtime_bad.append((r['profile_id'],'missing_policy')); continue
 if not r.get('native_file'):
  runtime_bad.append((r['profile_id'],'empty_native_file')); continue
 native_path=ROOT/r['native_file']
 if not native_path.exists():
  runtime_bad.append((r['profile_id'],'missing_native_file')); continue
 text=native_path.read_text()
 expected=[
  'advisor:\n  enabled: false\n  syncBacklog: "off"',
  f'task:\n  eager: {json.dumps(pol["task_eager"])}\n  maxConcurrency: {int(pol["task_max_concurrency"])}',
 ]
 if not all(x in text for x in expected):
  runtime_bad.append((r['profile_id'],'yaml_mismatch',pol['task_eager'],pol['task_max_concurrency']))
 if f'advisor={pol["advisor_enabled"]}' not in r.get('runtime_policy','') or f'task.eager={pol["task_eager"]}' not in r.get('runtime_policy',''):
  runtime_bad.append((r['profile_id'],'index_runtime_summary_mismatch'))
check('omp_runtime_policy_serialized',not runtime_bad,str(runtime_bad[:20]))
cyber_policy_bad=[]
for pol in runtime:
 if pol['domain']!='cybersecurity': continue
 app=runtime_by_id.get(f"omp--{pol['portfolio']}-apps-{pol['objective']}")
 if app is None:
  cyber_policy_bad.append((pol['profile_id'],'missing_apps_policy'))
 elif any(pol.get(fld)!=app.get(fld) for fld in ('task_eager','task_max_concurrency')):
  cyber_policy_bad.append((pol['profile_id'],'apps_task_policy_mismatch'))
 if pol.get('advisor_enabled')!='False' or pol.get('advisor_sync_backlog')!='off':
  cyber_policy_bad.append((pol['profile_id'],'advisor_must_be_off'))
 rationale=normalize_text(pol.get('rationale',''))
 if not ('apps' in rationale and any(w in rationale for w in ('hered','deriv','clon','conserv'))
         and ('ciber' in rationale or 'cyber' in rationale)
         and (is_negated(rationale,'eficac') or is_negated(rationale,'efficacy') or is_negated(rationale,'evid'))):
  cyber_policy_bad.append((pol['profile_id'],'missing_conservative_apps_provenance'))
check('cybersecurity_omp_runtime_policy',not cyber_policy_bad,str(cyber_policy_bad[:20]))

# A04: Apps/economy slow reviewer remains a high review whenever the role is invoked.
a04_bad=[(r['profile_id'],r['model'],r['thinking']) for r in rows if r['harness']=='omp' and r['domain']=='apps' and r['objective']=='economy' and r['role']=='slow' and r['thinking']!='high']
check('A04_omp_apps_economy_slow_high',not a04_bad,str(a04_bad[:20]))

# A05: OpenAI-only(+NaN) economy general task does not assume a closed SDD handoff.
a05_bad=[]
for p in ['plus','pro100','plus-nan','pro100-nan']:
 for d in ('data','research','apps','cybersecurity'):
  r=rows_by_group_role.get(('omp',p,d,'economy','task'))
  if r is None: a05_bad.append((p,d,'missing_task_route'))
  elif (r['model_key'],r['thinking'])!=('oa_sol61','medium'): a05_bad.append((r['profile_id'],r['model_key'],r['thinking']))
check('A05_omp_openai_economy_task_sol_medium',not a05_bad,str(a05_bad[:20]))

# Critical-review variants: full profile copies whose only routing changes are native RDD critical roles -> high.
critical_dir=ROOT/'profiles/gentle-shell-variants/critical-review'
critical_files=sorted(critical_dir.glob('*.export.json'))
critical_bad=[]
critical_roles={'review-risk','review-reliability','review-resilience','review-refuter','review-validator'}
base_by_name={}
for p in (ROOT/'profiles/gentle-shell').glob('*.export.json'):
 x=json.loads(p.read_text()); base_by_name[x['name']]=x['config']
expected_critical_names={f'{p}-{d}-{o}-critical-review' for h,p,d,o in expected_combinations if h=='gentle-shell'}
actual_critical_names=set()
for p in critical_files:
 x=json.loads(p.read_text()); name=x['name']
 actual_critical_names.add(name)
 if not name.endswith('-critical-review') or name[:-16] not in base_by_name:
  critical_bad.append((p.name,'name')); continue
 base=base_by_name[name[:-16]]
 cfg=x['config']
 if set(cfg)!=set(base): critical_bad.append((name,'role_set'))
 for role in base:
  if role in critical_roles:
   allowed=bysel[base[role]['model']]['allowed_efforts']
   before_effort=base[role].get('thinking','');after_effort=cfg.get(role,{}).get('thinking','')
   if cfg.get(role,{}).get('model')!=base[role].get('model') or (not allowed and after_effort!=before_effort):
    critical_bad.append((name,role,'critical_role_mismatch'))
   elif allowed:
    floor=max(EFFORT_ORDER.index('high'),EFFORT_ORDER.index(before_effort) if before_effort else -1)
    supported=[e for e in allowed if e in EFFORT_ORDER and EFFORT_ORDER.index(e)>=floor]
    if not supported or after_effort!=min(supported,key=EFFORT_ORDER.index):
     critical_bad.append((name,role,'critical_effort_floor_or_supported_value'))
  elif cfg.get(role)!=base.get(role):
   critical_bad.append((name,role,'noncritical_changed'))
check('critical_review_variant_names_exact',actual_critical_names==expected_critical_names,
      f'missing={len(expected_critical_names-actual_critical_names)} extra={len(actual_critical_names-expected_critical_names)}')
check('critical_review_variants_exact',not critical_bad,str(critical_bad[:20]))
check('runtime_override_files_present',all((ROOT/p).exists() for p in ['adapters/runtime-overrides/omp/advisor-on.yaml','adapters/runtime-overrides/omp/delegation-preferred.yaml','adapters/runtime-overrides/README.md']),'')

check('retired_roles_absent',all(not is_retired(harness_contracts[r['harness']],r['role']) for r in rows))
couplings={}; coupling_compared={}

# Current routing hash
lines=['\t'.join([r['profile_id'],r['role'],r['model'],r['thinking']]) for r in rows]
routing_hash=hashlib.sha256(('\n'.join(sorted(lines))+'\n').encode()).hexdigest()

# Per-profile audit table
audit=[]
for key,rs in sorted(groups.items()):
 h,p,d,o=key; pid=f'{h}--{p}-{d}-{o}'
 local_issues=[i for i in contract_fail if pid in i]
 audit.append({
  'profile_id':pid,'harness':h,'portfolio':p,'domain':d,'objective':o,
  'roles':len(rs),
  'model_plan_effort_ok':str(not any(i[0]=='model_plan_effort_contracts' and pid in i[1] for i in issues)),
  'native_file':next((x['native_file'] for x in index if x['profile_id']==pid),''),
  'context_review':rs[0]['profile_context'],
  'status':'PASS' if not any(pid in str(i) for i in issues) else 'FAIL',
 })
REPORT_DIR = ROOT/'validation'
# A fresh clone does not contain ignored/generated report directories.
REPORT_DIR.mkdir(parents=True,exist_ok=True)
with (REPORT_DIR/'profile-baselines.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(audit[0]) if audit else ['profile_id']);w.writeheader();w.writerows(audit)
# Post-audit role variance across contract-defined objectives and domains.
variance=[]
for h,rolelist in expected_roles.items():
 for role in rolelist:
  sub=[r for r in rows if r['harness']==h and r['role']==role]
  invariant=changed_series=compared=complete=0
  for p in ports:
   for d in domains:
    eligible=[o for o in objectives if (h,p,d,o) in expected_combinations and role in expected_roles_for(h,d,o)]
    if len(eligible)<2: continue
    compared+=1
    vals=[rows_by_group_role.get((h,p,d,o,role)) for o in eligible]
    if any(r is None for r in vals): continue
    complete+=1
    pairs={(r['model'],r['thinking']) for r in vals}
    if len(pairs)==1: invariant+=1
    else: changed_series+=1
  variance.append({
   'harness':h,'role':role,'unique_model_effort_pairs':len({(r['model'],r['thinking']) for r in sub}),
   'objective_invariant_series':invariant,'objective_changed_series':changed_series,
   'compared_portfolio_domain_series':compared,'complete_series':complete,
  })
with (REPORT_DIR/'role-variance.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(variance[0]));w.writeheader();w.writerows(variance)

input_paths=[
 'catalog/models.json', 'catalog/offerings.json',
 'catalog/access-routes.json', 'catalog/resource-plans.json',
 'contracts/harnesses.json',
 'policies/functions.json',
 'data/assignments.csv',
 'data/model-catalog.json',
 'data/portfolios.csv',
 'data/domain-objective-contracts.json',
 'data/omp-runtime-policies.csv',
]
input_sha256={relative:hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() for relative in input_paths}
gentle_profiles=sum(h=='gentle-shell' for h,p,d,o in actual_combinations)
omp_profiles=sum(h=='omp' for h,p,d,o in actual_combinations)
cybersecurity_profiles=sum(d=='cybersecurity' for h,p,d,o in actual_combinations)
receipt={
 'version':'contract-baseline-1',
 'built_at':datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'),
 'input_sha256':input_sha256,
 'routing_sha256':routing_hash,
 'profiles':len(groups),'assignments':len(rows),
 'gentle_profiles':gentle_profiles,'omp_profiles':omp_profiles,
 'cybersecurity_profiles':cybersecurity_profiles,
 'cybersecurity_assignments':sum(r['domain']=='cybersecurity' for r in rows),
 'agent_use_exclusions':[{'portfolio':p,'reason':reason} for p,reason in sorted(AGENT_USE_EXCLUSIONS.items())],
 'omp_runtime_policy_metadata_mismatches':len(policy_metadata_bad),
 'checks_total':len(checks),'checks_passed':sum(c['ok'] for c in checks),'checks_failed':sum(not c['ok'] for c in checks),
 'issues':issues,
 'couplings_after_review':couplings,'coupling_comparisons':coupling_compared,
 'limitations':[
  'This receipt validates assignment, policy metadata and serialized-profile structure; it does not establish model quality, cybersecurity efficacy or operational safety.',
  'Published cybersecurity benchmarks exist; no calibration of the selected routes is established.',
  'Provider plan entitlement remains distinct from model-catalog compatibility.',
  'Gentle parser and OMP startup/bootstrap checks are independent receipts and are not represented here.',
 ],
}
(REPORT_DIR/'exhaustive-validation.json').write_text(json.dumps({'receipt':receipt,'checks':checks},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
raise SystemExit(0 if not issues else 1)
