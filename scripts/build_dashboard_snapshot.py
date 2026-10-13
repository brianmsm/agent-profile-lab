from benchmark_semantics import build_semantics, typed_family_coverage
#!/usr/bin/env python3
"""Snapshot agregado para la dashboard web (Vite+React).

Genera JSON de tamaño variable con routing por (portfolio, dominio, objetivo),
catálogo, portfolios, cobertura y benchmarks capturados desde evidencia. Los
resultados de validación se leen del receipt estático, no son verificaciones live.
"""
import collections
import csv
import hashlib
import json
from pathlib import Path
from dashboard_source_coverage import CYBERSECURITY_CODE_INPUTS, build_source_coverage, digest
from dashboard_strategies import build_strategy_collections
from dashboard_access import decorate_access
from dashboard_cybersecurity import build_cybersecurity_evidence, validate_evidence_boundary
from dashboard_cybersecurity_reconciliation import load_seed

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_RECEIPT = ROOT / 'validation' / 'exhaustive-validation.json'
DOMAIN_CONTRACTS = ROOT / 'data' / 'domain-objective-contracts.json'


def relative_source(path):
    return path.relative_to(ROOT).as_posix()



validation_report = json.load(open(VALIDATION_RECEIPT, encoding='utf-8'))
recorded_validation = validation_report['receipt']
for source_name in (
    'catalog/models.json','catalog/offerings.json','catalog/access-routes.json','catalog/resource-plans.json',
    'contracts/harnesses.json', 'policies/functions.json',
    'data/assignments.csv', 'data/model-catalog.json', 'data/portfolios.csv',
    'data/domain-objective-contracts.json', 'data/omp-runtime-policies.csv',
):
    with (ROOT / source_name).open('rb') as source_file:
        actual_hash = hashlib.file_digest(source_file, 'sha256').hexdigest()
    if recorded_validation.get('input_sha256', {}).get(source_name) != actual_hash:
        raise ValueError(
            f'Validación ausente u obsoleta para {source_name}. '
            'Ejecuta python3 scripts/validate_profiles.py antes de generar el snapshot.'
        )
domain_contracts = json.load(open(DOMAIN_CONTRACTS, encoding='utf-8'))['domains']
validate_evidence_boundary(domain_contracts.get('cybersecurity', {}))
# Presentation labels only: never rewrite the audited domain contracts.
domain_contracts['apps'] = {
    **domain_contracts['apps'],
    'label': 'Desarrollo de software',
    'scope': 'Software nativo, CLI, GUI, servicios y desarrollo multiplataforma para Windows, macOS, Linux y móvil; distinto del frontend/backend web.',
}
domain_contracts['web'] = {
    **domain_contracts['web'],
    'label': 'Desarrollo web',
    'scope': 'Frontend, backend y aplicaciones web; distinto del software nativo/CLI/multiplataforma. Una nota visual alta no demuestra seguridad ni corrección.',
}

rows=list(csv.DictReader(open(ROOT/'data/assignments.csv',encoding='utf-8-sig',newline='')))
cat=json.load(open(ROOT/'data/model-catalog.json'))
ports={r['id']:r for r in csv.DictReader(open(ROOT/'data/portfolios.csv',encoding='utf-8-sig'))}
policy_rows = list(csv.DictReader((ROOT / 'data' / 'omp-runtime-policies.csv').open(encoding='utf-8-sig', newline='')))
route_details, runtime_policies, strategies = build_strategy_collections(rows, cat, ports, policy_rows)

# 1. routing: pid -> {role: [model_name, thinking]}
routing=collections.defaultdict(dict)
meta={}
for r in rows:
    pid=r['profile_id']
    routing[pid][r['role']]=[r['model_name'],r['thinking']]
    if pid not in meta:
        meta[pid]={'portfolio':r['portfolio'],'harness':r['harness'],'domain':r['domain'],'objective':r['objective']}

def claude_plan(portfolio_id, portfolio):
    anthropic = portfolio.get('anthropic', 'False')
    if anthropic == 'False':
        return 'none'
    if anthropic != 'True':
        raise ValueError(f'Plan Anthropic no válido para el portfolio canónico {portfolio_id!r}')
    if 'claude-max' in portfolio_id:
        return 'max'
    if 'claude' in portfolio_id:
        return 'pro'
    raise ValueError(f'El ID canónico no permite derivar el plan Anthropic: {portfolio_id!r}')


# 2. catálogo compacto con trazabilidad canónica
catalog={m['key']:{'name':m['name'],'pool':m['pool'],'selector':m['selector'],
    'efforts':m.get('allowed_efforts',[]),'vision':m.get('vision'),
    'evidence':m.get('evidence_confidence',''),'integration':m.get('integration_confidence',''),
    'notes':m.get('notes',''),'sourceIds':m.get('source_ids',[]),'sourceUrls':m.get('source_urls',[])} for m in cat}

# 3. portfolios con precios y trazabilidad canónica
portfolios={k:{'label':v['label'],'usd':v['monthly_usd'],'eur':v['monthly_eur'],
    'openai':v['openai'],'gateway':{'none':'none','anthropic':'none','cc':'cc','go':'go'}[v['gateway']],
    'claude':claude_plan(k, v),'nan':v['nan'],
    'notes':v.get('notes',''),'sourceIds':json.loads(v.get('source_ids','[]'))} for k,v in ports.items()}


validation_limitations = recorded_validation['limitations']
validation_note = (
    f"Resultado registrado el {recorded_validation['built_at']} en "
    f"{relative_source(VALIDATION_RECEIPT)} ({recorded_validation['version']}), "
    f"con hashes de los datos de entrada comprobados al generar este snapshot: "
    f"{recorded_validation['checks_passed']} checks aprobados, "
    f"{recorded_validation['checks_failed']} fallidos. "
    + ' '.join(validation_limitations)
)
benchmarks, source_coverage, coverage_receipt = build_source_coverage(ROOT, cat, ports, rows)
benchmarks,benchmark_registry = build_semantics(benchmarks,source_coverage,ROOT)
coverage = typed_family_coverage(benchmarks,benchmark_registry)
cybersecurity_evidence = build_cybersecurity_evidence(benchmarks, cat, source_coverage, load_seed(ROOT), ROOT)
benchmark_note = (
    'Instantánea estática de evidencia capturada en las fechas de cada fila. '
    'Los resultados de proveedor, mediciones independientes y espejos pueden usar '
    'harness, esfuerzo y metodologías distintos: no forman un ranking único. '
    'Se omiten valores ausentes/no numéricos e inferencias realizadas por la ingesta; las estimaciones publicadas por productores conservan su etiqueta y no son mediciones independientes. '
    'Los costes de ejecución de benchmarks se separan de suscripciones y precios por token. '
    'OSWorld 2.1 partial (vendor) y OSWorld 2.0 strict binary (BenchLM) no son la misma métrica. '
    'Cada fila conserva su origen exacto y metodología; espejos no equivalen a medición independiente.'
    ' La cobertura describe sólo las fuentes incorporadas, no todos los benchmarks publicados. '
    'Las áreas sin métricas incorporadas no acreditan competencia; ciberseguridad usa anotaciones explícitas y no una clasificación por nombre. Ningún resultado publicado establece calibración del routing. T3 es sólo contexto de uso.'
)
provenance = {
    'kind': 'static-audit',
    'sources': [
        relative_source(ROOT / 'data' / 'assignments.csv'),
        relative_source(ROOT / 'data' / 'model-catalog.json'),
        relative_source(ROOT / 'data' / 'portfolios.csv'),
        *[relative_source(ROOT / item['path']) for item in coverage_receipt['datasets']],
        relative_source(VALIDATION_RECEIPT),
        relative_source(DOMAIN_CONTRACTS),
        relative_source(ROOT / 'data' / 'omp-runtime-policies.csv'),
        relative_source(Path(__file__).resolve().parent / 'dashboard_strategies.py'),
        *[relative_source(ROOT / name) for name in CYBERSECURITY_CODE_INPUTS],
    ],
    'validationNote': validation_note,
    'benchmarkNote': benchmark_note,
}

# 5. stats
stats={
 'rows':len(rows),'profiles':len(meta),'portfolios':len(ports),'models':len(cat),
 'groups':len(meta),
 'validators':{'passed':recorded_validation['checks_passed'],'failed':recorded_validation['checks_failed']},
 'session':f"{recorded_validation['version']} ({recorded_validation['built_at'][:10]})",
}

access_metadata=decorate_access(ROOT,catalog,ports,meta,route_details,strategies)

out={'benchmarkRegistry':benchmark_registry,'access':access_metadata,'stats':stats,'portfolios':portfolios,'catalog':catalog,
     'coverage':coverage,'meta':meta,'routing':routing,
     'routeDetails':route_details,'runtimePolicies':runtime_policies,'strategies':strategies,
     'benchmarks':benchmarks,'provenance':provenance,'domainContracts':domain_contracts,
     'sourceCoverage':source_coverage,'cybersecurityEvidence':cybersecurity_evidence}
from selection_candidates import validate_review_evidence
selection_receipt=validate_review_evidence(out,ROOT)
print('Selection review:',selection_receipt)
dest=ROOT/'dashboard'/'public'/'data'/'snapshot.json'
dest.parent.mkdir(parents=True,exist_ok=True)
with dest.open('w', encoding='utf-8') as snapshot_file:
    json.dump(out, snapshot_file, ensure_ascii=False, separators=(',', ':'))
coverage_receipt['snapshot_sha256'] = digest(dest)
coverage_dest = ROOT / 'validation' / 'source-coverage-receipt.json'
coverage_dest.parent.mkdir(parents=True, exist_ok=True)
coverage_dest.write_text(json.dumps(coverage_receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'coverage receipt: {coverage_dest}')
import os
print(f'snapshot: {dest}')
print(f'tamaño: {os.path.getsize(dest)/1024/1024:.1f} MB | perfiles: {len(meta)}')

# Split transport only after the canonical, validated source has been written.
from dashboard_delivery import build_delivery
delivery = build_delivery(out, dest)
print("deferred delivery:", {k: v["bytes"] for k,v in delivery["parts"].items()})
