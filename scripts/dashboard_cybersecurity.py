"""Public aggregate cybersecurity evidence; never a route calibration or ranking."""
import hashlib
import json
import math
from datetime import date
from urllib.parse import urlparse

from dashboard_cybersecurity_catalog import catalog_matches

EVIDENCE_BOUNDARY = {
    'routingBasis': 'Apps-derived',
    'publishedEvidence': 'published-results-present',
    'routeCalibration': 'route-calibration-not-established',
    'validationMeaning': 'structural-validation-not-efficacy',
}
METADATA_FIELDS = ('resultType', 'benchmarkVersion', 'evaluationDate', 'captureDate',
                   'taskDenominator', 'attemptBudget', 'settings', 'limitations')
RESULT_TYPES = {'independent', 'vendor', 'vendor-comparator', 'editorial'}
SCOPE = ('Sólo resultados públicos agregados con anotación explícita en el conjunto de fuentes archivadas; '
         'no es una búsqueda bibliográfica exhaustiva ni un ranking común de benchmarks.')
ROUTING_CONCLUSION = ('La asignación conservada es una extrapolación derivada de Apps, no una selección ganadora basada en ciberseguridad. '
                      'Las puntuaciones agregadas publicadas no validan esta asignación: no se ha establecido una evaluación '
                      'de ciberseguridad por rol, proveedor u OMP, ni calibración de las rutas.')


def validate_evidence_boundary(contract):
    if not isinstance(contract, dict) or contract.get('evidenceBoundary') != EVIDENCE_BOUNDARY:
        raise ValueError('Cybersecurity evidenceBoundary must preserve Apps derivation, published results and structural non-efficacy limits')
    if not isinstance(contract.get('evidenceNote'), str) or not contract['evidenceNote'].strip():
        raise ValueError('Cybersecurity evidenceNote must explain the typed boundary')


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Missing cybersecurity {label}')
    return value


def iso_date(value, label, nullable=False):
    if value is None and nullable:
        return value
    text(value, label)
    if len(value) != 10 or date.fromisoformat(value).isoformat() != value:
        raise ValueError(f'Invalid cybersecurity {label}: {value}')
    return value


def metadata(row):
    context = row.get('context', {})
    if not isinstance(context, dict):
        raise ValueError('Invalid benchmark context')
    if 'cybersecurity' not in context:
        return None
    meta = context['cybersecurity']
    if not isinstance(meta, dict) or set(meta) != set(METADATA_FIELDS):
        raise ValueError('Incomplete or unknown cybersecurity annotation fields')
    if meta['resultType'] not in RESULT_TYPES:
        raise ValueError('Invalid cybersecurity resultType')
    iso_date(meta['captureDate'], 'captureDate')
    iso_date(meta['evaluationDate'], 'evaluationDate', nullable=True)
    if meta['evaluationDate'] is not None and meta['evaluationDate'] > meta['captureDate']:
        raise ValueError('Cybersecurity evaluation date is after capture')
    for field in ('benchmarkVersion', 'attemptBudget'):
        if meta[field] is not None:
            text(meta[field], field)
    denominator = meta['taskDenominator']
    if denominator is not None and (type(denominator) not in (int, float) or not math.isfinite(denominator) or denominator <= 0 or int(denominator) != denominator):
        raise ValueError('Invalid cybersecurity taskDenominator')
    text(meta['settings'], 'settings')
    if not isinstance(meta['limitations'], list) or not meta['limitations']:
        raise ValueError('Cybersecurity limitations must be explicit')
    for limitation in meta['limitations']:
        text(limitation, 'limitation')
    return meta


def catalog_by_key(catalog):
    if isinstance(catalog, dict):
        return catalog
    result = {item['key']: item for item in catalog}
    if len(result) != len(catalog):
        raise ValueError('Duplicate cybersecurity catalog keys')
    return result


def result_id(row):
    identity = [row[field] for field in ('sourceId', 'provenance', 'model', 'benchmark', 'effort')]
    encoded = json.dumps(identity, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'cyber-' + hashlib.sha256(encoded).hexdigest()[:24]


def coverage_rows(results, catalog):
    coverage = []
    for key in catalog:
        links = [(result, match) for result in results for match in result['catalogMatches'] if match['catalogKey'] == key]
        measured = any(result['resultType'] != 'editorial' and match['relationship'] == 'published-model' for result, match in links)
        aliases = any(result['resultType'] != 'editorial' and match['relationship'] == 'candidate-alias' for result, match in links)
        state = ('measured-result' if measured else 'candidate-alias-only' if aliases
                 else 'editorial-only' if links else 'no-mapped-result')
        reasons = {
            'measured-result': 'Resultado numérico publicado de benchmark para la etiqueta de modelo vinculada; no establece calibración de ruta, proveedor ni harness.',
            'candidate-alias-only': 'Sólo hay vínculos de benchmark mediante alias candidatos sin resolver en este conjunto; no son evidencia de la versión exacta ni calibración de las rutas.',
            'editorial-only': 'Sólo hay valoraciones editoriales vinculadas en este conjunto; no son mediciones de eficacia en ciberseguridad.',
            'no-mapped-result': 'No hay resultado vinculado explícitamente en este conjunto archivado y alcance de captura; no afirma que no existan resultados publicados en otras fuentes.',
        }
        coverage.append(dict(catalogKey=key, state=state, resultIds=[result['id'] for result, _ in links], reason=reasons[state]))
    return coverage


def build_cybersecurity_evidence(benchmarks, catalog, source_coverage=None, reconciliation_seed=None, root=None):
    catalog = catalog_by_key(catalog)
    sources = None if source_coverage is None else {source['id'] for source in source_coverage['sources']}
    results = []
    ids = set()
    for row in benchmarks:
        meta = metadata(row)
        if meta is None:
            continue
        value = row.get('value')
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Annotated cybersecurity result must have a finite numeric value; missing is not zero')
        for field in ('sourceId', 'source', 'provenance', 'model', 'benchmark', 'unit', 'effort'):
            text(row.get(field), field)
        url = urlparse(row['source'])
        if url.scheme not in ('http', 'https') or not url.netloc:
            raise ValueError('Cybersecurity source must be an absolute public URL')
        if sources is not None and row['sourceId'] not in sources:
            raise ValueError('Cybersecurity sourceId has no sourceCoverage lineage')
        identifier = result_id(row)
        if identifier in ids:
            raise ValueError('Duplicate cybersecurity result identity')
        ids.add(identifier)
        results.append(dict(id=identifier, sourceId=row['sourceId'], sourceUrl=row['source'],
                            provenance=row['provenance'], benchmark=row['benchmark'],
                            publishedModel=row['model'], value=value, unit=row['unit'], effort=row['effort'],
                            **meta, catalogMatches=catalog_matches(row['model'], catalog),
                            routeValidation='not-established'))
    if not results:
        raise ValueError('Snapshot generation requires explicitly annotated cybersecurity evidence')
    evidence = dict(schemaVersion=1, asOf=max(result['captureDate'] for result in results),
                    scope=SCOPE, routingConclusion=ROUTING_CONCLUSION, results=results,
                    catalogCoverage=coverage_rows(results, catalog))
    if reconciliation_seed is not None:
        from dashboard_cybersecurity_reconciliation import build_reconciliation
        evidence['reconciliation'] = build_reconciliation(reconciliation_seed, results, catalog, source_coverage, root)
        evidence['scope'] = reconciliation_seed['scope']
        evidence['asOf'] = reconciliation_seed['asOf']
    return evidence


def validate_cybersecurity_evidence(evidence, benchmarks, catalog, source_coverage=None, reconciliation_seed=None, root=None):
    """Exact graph reconstruction rejects omissions, inferred scores and route escalation."""
    expected = build_cybersecurity_evidence(benchmarks, catalog, source_coverage, reconciliation_seed, root)
    if reconciliation_seed is None and 'reconciliation' in evidence:
        from dashboard_cybersecurity_reconciliation import validate_reconciliation
        validate_reconciliation(evidence['reconciliation'], expected['results'], catalog_by_key(catalog), source_coverage, root)
        expected['reconciliation'] = evidence['reconciliation']
        expected['scope'] = evidence['reconciliation']['scope']
        expected['asOf'] = evidence['reconciliation']['asOf']
    actual_json = json.dumps(evidence, sort_keys=True, ensure_ascii=False, allow_nan=False)
    expected_json = json.dumps(expected, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if actual_json != expected_json:
        raise ValueError('Cybersecurity evidence does not exactly preserve annotated result lineage, catalog links and scope boundary')
