"""Offline, fail-closed ingestion and reconciliation for the dashboard snapshot."""
import collections
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from dashboard_cybersecurity import metadata as cybersecurity_metadata

FIELDS = ('model', 'family', 'benchmark', 'unit', 'effort', 'source', 'date', 'provenance', 'methodology', 'note')
CYBERSECURITY_CODE_INPUTS = (
    'scripts/build_dashboard_snapshot.py',
    'scripts/validate_source_coverage.py',
    'scripts/dashboard_cybersecurity.py',
    'scripts/dashboard_cybersecurity_catalog.py',
    'scripts/dashboard_cybersecurity_reconciliation.py',
    'scripts/dashboard_source_coverage.py',
    'scripts/supplemental_cybersecurity.py',
    'scripts/supplemental_openai_cybersecurity.py',
    'scripts/supplemental_vals_exhaustive.py',
    'scripts/supplemental_frontier_exhaustive.py',
    'scripts/supplemental_openmodels_exhaustive.py',
    'scripts/supplemental_publishers_exhaustive.py',
    'scripts/normalize_supplemental_sources.py',
    'scripts/supplemental_registered_refs.py',
    'scripts/capture_cybersecurity_sources.py',
    'scripts/capture_supplemental_sources.py',
)
KINDS = {'benchmark', 'measurement', 'contract', 'code', 'user-evidence', 'assumption', 'press', 'telemetry', 'mirror', 'unknown'}


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def load_json(path):
    def reject(value):
        raise ValueError(f'Nonfinite JSON in {path}: {value}')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key in {path}: {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8-sig'), parse_constant=reject, object_pairs_hook=unique)


def local_path(root, name):
    if not isinstance(name, str) or not name:
        raise ValueError('Missing local evidence path')
    name = name.removeprefix('')
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'Missing or unsafe local evidence: {name}')
    return path


def count(value, label):
    if type(value) is not int or not 0 <= value <= 9007199254740991:
        raise ValueError(f'Invalid count {label}: {value!r}')
    return value


def verify_input(root, item):
    path = local_path(root, item['path'])
    expected = item.get('sha256')
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected) or digest(path) != expected:
        raise ValueError(f'Stale or malformed input SHA256: {item["path"]}; regenerate its normalized dataset')
    return path




def source_kind(row):
    sid = row['source_id']
    if sid == 'T3USAGE': return 'telemetry'
    if sid.startswith('NANUSER'): return 'user-evidence'
    if sid == 'GOUSER': return 'assumption'
    text = row['evidence_type'].lower()
    if 'código' in text: return 'code'
    if 'press' in text: return 'press'
    if 'measurement' in text or 'medición' in text: return 'measurement'
    if any(word in text for word in ('benchmark', 'evaluación', 'evaluador', 'datos')): return 'benchmark'
    return 'contract'


def validate_capture_reference_identity(reference, captured):
    """Capture labels and exact URL identities are distinct receipt conventions."""
    if not isinstance(captured, dict) or captured.get('requestedUrl') != reference['url']:
        raise ValueError('Exhaustive capture reference disagrees with receipt URL')
    url_hash = hashlib.sha256(reference['url'].encode()).hexdigest()[:20]
    if not isinstance(captured.get('sourceId'), str) or captured['sourceId'] not in {reference['name'], 'URL-' + url_hash, url_hash}:
        raise ValueError('Exhaustive capture receipt has an unrecognized source identity')


def build_source_coverage(root, catalog, portfolios, assignments):
    manifest_path = root / 'sources/dashboard-coverage-manifest.json'
    manifest = load_json(manifest_path)
    if manifest.get('schemaVersion') != 1 or not manifest.get('datasets') or len({d['name'] for d in manifest['datasets']}) != len(manifest['datasets']) or not {'openai','anthropic','supplemental','slopalytics'} <= {d['name'] for d in manifest['datasets']}:
        raise ValueError('Coverage manifest must declare unique named datasets and preserve foundational datasets')
    with (root / 'sources/ledger.csv').open(encoding='utf-8-sig', newline='') as handle:
        ledger = list(csv.DictReader(handle))
    ledger_ids = {r['source_id'] for r in ledger}
    if len(ledger_ids) != len(ledger):
        raise ValueError('Duplicate ledger source ID')
    # JSON is a derived registry, never a freshness update.
    (root / 'sources/ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sources, by_url, artifacts, inputs = {}, {}, {}, {}
    notes = ['No fuzzy model-name matching. Exact full-provenance duplicates only are removed.',
             'Mirror observations remain mirror evidence and do not add independent AA measurements.',
             'Raw discovery index/tree URLs remain archived context, not individually referenced metric sources. Only explicitly used origins, registered descriptors and captured endpoints enter this registry; no recursive crawl is implied.',
             'Context/artifact observations use their producer-declared unit (records, lines or metric cells); they are not comparable sample sizes.']

    def register(sid, title, url, kind='unknown', evidence_type='Referenced origin', checked='', limitations='', note='No independently captured evaluation for this reference.'):
        if not sid or kind not in KINDS:
            raise ValueError(f'Invalid source registration: {sid!r}/{kind!r}')
        if sid in sources:
            if sources[sid]['url'] != url:
                raise ValueError(f'Ambiguous source ID {sid}: conflicting origins')
            return sid
        sources[sid] = dict(id=sid, title=title, url=url, evidenceType=evidence_type, kind=kind,
                            status='unavailable' if kind in {'unknown', 'benchmark', 'measurement', 'mirror'} else 'context-only',
                            checked=checked, limitations=limitations, note=note, benchmarkCount=0,
                            catalogReferences=0, portfolioReferences=0, assignmentReferences=0, artifacts=[])
        if url: by_url.setdefault(url, sid)
        return sid

    for item in ledger:
        register(item['source_id'], item['title'], item['url'], source_kind(item), item['evidence_type'], item['checked'], item['limitations'])

    def origin(url, included=False, mirror=False):
        if not isinstance(url, str) or not url:
            raise ValueError('Empty source origin')
        sid = by_url.get(url)
        if sid is None:
            sid = 'URL-' + hashlib.sha256(url.encode()).hexdigest()[:20]
            register(sid, url, url, 'mirror' if mirror else 'benchmark' if included else 'unknown',
                     note='Observed exact origin in archived normalized evidence.' if included else 'Referenced URL not independently captured; no score inferred.')
        if included and sources[sid]['kind'] == 'unknown':
            sources[sid]['kind'] = 'mirror' if mirror else 'benchmark'
            sources[sid]['evidenceType'] = 'Archived normalized origin'
        return sid

    def artifact(path, kind='input-context', observed=0, included=0, excluded=0, exclusions=None):
        path = local_path(root, path)
        name = path.relative_to(root).as_posix()
        sha = inputs.get(name) or digest(path)
        inputs[name] = sha
        record = dict(path=name, sha256=sha, kind=kind, observed=count(observed, name), included=count(included, name), excluded=count(excluded, name), exclusions=exclusions or [])
        if included + excluded > observed:
            raise ValueError(f'Artifact reconciliation exceeds observations: {name}')
        total = 0
        for exclusion in record['exclusions']:
            if not isinstance(exclusion.get('locator'), str) or not exclusion['locator'] or not isinstance(exclusion.get('reason'), str) or not exclusion['reason']:
                raise ValueError(f'Unexplained exclusion in {name}')
            total += count(exclusion.get('count'), name)
        if total != excluded:
            raise ValueError(f'Exclusion reasons do not account exactly for {name}: {total} != {excluded}')
        previous = artifacts.get(name)
        replaceable = {'input-context', 'context'}
        if previous and previous['kind'] not in replaceable and previous != record and record['kind'] not in replaceable:
            raise ValueError(f'Conflicting artifact accounting: {name}')
        if previous is None or previous['kind'] in replaceable: artifacts[name] = record
        return name

    def attach(sid, path):
        if path not in sources[sid]['artifacts']: sources[sid]['artifacts'].append(path)

    for name in ('sources/ledger.csv', 'sources/ledger.json', 'sources/dashboard-coverage-manifest.json', 'data/model-catalog.json', 'data/portfolios.csv', 'data/assignments.csv'):
        artifact(name, 'registry' if name.startswith('sources/') else 'canonical-reference-context')
    # Code lineage is context, never a public evaluation or scored observation.
    for name in CYBERSECURITY_CODE_INPUTS:
        artifact(name, 'code-input')
    reconciliation_seed = root / 'data/cybersecurity-reconciliation.json'
    if reconciliation_seed.exists():
        artifact('data/cybersecurity-reconciliation.json', 'reconciliation-seed')
    exhaustive_registry = root / 'data/cybersecurity-exhaustive-capture-references.json'
    if exhaustive_registry.exists():
        artifact('data/cybersecurity-exhaustive-capture-references.json', 'capture-reference-registry')
    for path in sorted((root / 'sources').rglob('*')):
        if path.is_file():
            artifact(path.relative_to(root).as_posix(), 'registry')
    historic_receipt = root / 'sources/fresh-2026-09-26/receipt.json'
    for item in load_json(historic_receipt):
        name = f'sources/fresh-2026-09-26/{item["source_id"]}.html'
        verify_input(root, dict(path=name, sha256=item['sha256']))
        attach(item['source_id'], name)
    for item in load_json(root / 'sources/freshness.json'):
        sid = item['source_id']
        if sid not in sources:
            register(sid, sid, item['url'], note='Historical registry freshness reference; original capture may live in a prior audit, not refreshed or scored here.')
        origin(item['url'])
        attach(sid, 'sources/freshness.json')
    for item in ledger:
        attach(item['source_id'], 'sources/ledger.csv')
        attach(item['source_id'], 'sources/ledger.json')

    for entry in manifest['context']:
        name = artifact(entry['path'], 'context', 1)
        attach(entry['sourceId'], name)
        sources[entry['sourceId']]['note'] = entry['reason']
    t3 = load_json(root / 'evidence/t3code/T3_USAGE_RECEIPT_2026-10-01.json')
    verify_input(root, {'path': 'evidence/t3code/T3_USAGE_SNAPSHOT_2026-10-01.json', 'sha256': t3['sha256']})

    benchmarks, seen = [], set()
    dataset_receipts = []
    source_result_notes = collections.defaultdict(list)
    for dataset in manifest['datasets']:
        path = local_path(root, dataset['path'])
        data = load_json(path)
        if data.get('schemaVersion') != 1 or not isinstance(data.get('benchmarks'), list) or not isinstance(data.get('reconciliation'), dict):
            raise ValueError(f'Malformed normalized dataset: {path}')
        declared_inputs = data.get('inputs')
        if not isinstance(declared_inputs, list) or not declared_inputs:
            raise ValueError(f'Missing verifiable inputs in {path}')
        for item in declared_inputs:
            input_path = verify_input(root, item)
            artifact(input_path.relative_to(root).as_posix())
            if input_path.suffix == '.json' and 'RECEIPT' in input_path.name.upper():
                captured = load_json(input_path)
                if isinstance(captured, dict):
                    for capture in captured.get('captures', []) + captured.get('derivedArtifacts', []):
                        capture_path = capture['path']
                        if '/' not in capture_path:
                            capture_path = (input_path.parent / capture_path).relative_to(root).as_posix()
                        artifact(verify_input(root, dict(path=capture_path, sha256=capture['sha256'])).relative_to(root).as_posix())
                        if capture.get('url'):
                            captured_id = origin(capture['url'])
                            attach(captured_id, local_path(root, capture_path).relative_to(root).as_posix())
                            if not sources[captured_id]['benchmarkCount']:
                                sources[captured_id]['status'] = 'context-only'
                                sources[captured_id]['note'] = 'Verified archived HTTP asset; asset capture alone is not an evaluation or independent benchmark.'
        reconciliation = data['reconciliation']
        for item in reconciliation.get('sources', []):
            register(item['id'], item['title'], item['url'], item.get('kind', 'benchmark'), item.get('evidenceType', 'Archived evidence'), item.get('checked', ''), item.get('limitations', ''))
            # Receipts can discover a URL before its producer supplies the explicit descriptor.
            # Enrich that exact identity, while leaving the historical ledger descriptor intact.
            if item['id'] not in ledger_ids:
                for field in ('title', 'kind', 'evidenceType', 'checked', 'limitations'):
                    if field in item:
                        sources[item['id']][field] = item[field]
        for url in reconciliation.get('referencedOrigins', []):
            origin(url)
        for item in reconciliation.get('source_results', []):
            sid = item['sourceId']
            if sid not in sources: raise ValueError(f'Unregistered reconciliation source: {sid}')
            source_result_notes[sid].append(f'{dataset["name"]} artifact reconciliation ({item["status"]}): {item["reason"]}')
            if item.get('checked'): sources[sid]['checked'] = item['checked']
            if not sources[sid]['benchmarkCount'] and item.get('status') in {'context-only', 'unavailable', 'superseded'}:
                sources[sid]['status'] = item['status']
            for source_path in item.get('artifacts', []):
                attach(sid, artifact(source_path))
        details = reconciliation.get('artifacts', [])
        for item in details:
            verify_input(root, item)
            artifact(item['path'], item.get('kind', 'reconciled-input'), item['observed'], item['included'], item['excluded'], item['exclusions'])
        if not details:
            # OpenAI declares independent CSV/narrative accounting blocks.
            for key, input_item in zip(('csv', 'narrative'), declared_inputs):
                block = reconciliation.get(key)
                if not block: continue
                exclusions = [dict(locator=r['locator'], reason=r['reason'], count=r.get('count', 1)) for r in block['observations'] if r['status'] == 'excluded']
                artifact(input_item['path'], 'reconciled-input', block['observed'], block['included'], block['excluded'], exclusions)
        exclusions = reconciliation.get('exclusions', reconciliation.get('excluded', []))
        if not isinstance(exclusions, list):
            raise ValueError(f'Malformed exclusion list: {path}')
        # Detailed input accounting owns its exclusions; do not count them twice on the normalized artifact.
        if details or any(key in reconciliation for key in ('csv', 'narrative')):
            exclusions = []
            observed = len(data['benchmarks'])
        else:
            observed = reconciliation.get('observed')
            if observed is None: raise ValueError(f'Missing observed count: {path}')
        excluded = sum(count(e.get('count', 1), path.name) for e in exclusions)
        duplicate_count = 0
        # Producers declare actual referenced origins explicitly. Arbitrary raw context
        # (e.g. a complete GitHub discovery tree) is not a source registry or a crawl queue.
        dataset_sources = {origin(url) for url in reconciliation.get('referencedOrigins', [])}
        producer_origin = reconciliation.get('producerMetadata', {}).get('source')
        if producer_origin:
            dataset_sources.add(origin(producer_origin))
        for index, row in enumerate(data['benchmarks']):
            if any(not isinstance(row.get(key), str) for key in FIELDS) or type(row.get('value')) not in (int, float) or not math.isfinite(row['value']):
                raise ValueError(f'Malformed benchmark {dataset["name"]}#{index}')
            context = row.get('context', {})
            if not isinstance(context, dict): raise ValueError(f'Malformed benchmark context: {dataset["name"]}#{index}')
            cybersecurity_metadata(row)
            collection_id = context.get('datasetSourceId')
            if collection_id:
                if collection_id not in sources: raise ValueError(f'Unknown dataset collection ID: {collection_id}')
                dataset_sources.add(collection_id)
                if not sources[collection_id]['benchmarkCount']:
                    sources[collection_id]['status'] = 'context-only'
                    sources[collection_id]['note'] = 'Local dataset collection: scores counted once under their exact row origin, not a second independent evaluation.'
            mirror = dataset['name'] == 'slopalytics' or row.get('context', {}).get('sourceType') == 'mirror'
            sid = row.get('sourceId')
            if sid and sid not in sources:
                raise ValueError(f'Unregistered scored sourceId {sid} in {dataset["name"]}#{index}')
            origin_id = origin(row['source'], included=True, mirror=mirror)
            sid = sid or origin_id
            if sources[sid]['kind'] == 'telemetry': raise ValueError('Telemetry cannot produce benchmarks')
            # Register the actual origin separately even when a dataset ID owns this row.
            dataset_sources.update((sid, origin_id))
            if origin_id != sid and not sources[origin_id]['benchmarkCount']:
                sources[origin_id]['status'] = 'context-only'
                sources[origin_id]['note'] = f'Origin declared by incorporated archived records owned by {sid}; no additional independent score counted for this origin.'
            row = dict(row, sourceId=sid)
            key = json.dumps({k: v for k, v in row.items() if k != 'sourceId'}, sort_keys=True, ensure_ascii=False, allow_nan=False)
            if key in seen:
                duplicate_count += 1
                continue
            seen.add(key)
            benchmarks.append(row)
            sources[sid]['benchmarkCount'] += 1
            sources[sid]['status'] = 'included'
            sources[sid]['note'] = 'Scores incorporated from archived normalized observations; methodology and local provenance remain on each row.'
        if duplicate_count:
            notes.append(f'{dataset["name"]}: {duplicate_count} exact full-provenance duplicate rows retained as reconciliation context, not active benchmarks.')
        name = artifact(dataset['path'], 'normalized-' + dataset['name'], observed, len(data['benchmarks']) - duplicate_count, excluded, exclusions)
        for sid in dataset_sources:
            attach(sid, name)
            for item in declared_inputs: attach(sid, local_path(root, item['path']).relative_to(root).as_posix())
        dataset_receipts.append(dict(name=dataset['name'], path=name, sha256=digest(path), emitted=len(data['benchmarks']), exactDuplicates=duplicate_count, active=len(data['benchmarks']) - duplicate_count, reconciliation=reconciliation))

    def references(items, field):
        for item in items:
            ids = item.get('source_ids', [])
            urls = item.get('source_urls', [])
            if isinstance(ids, str): ids = json.loads(ids or '[]')
            if isinstance(urls, str): urls = json.loads(urls or '[]')
            if not isinstance(ids, list) or not isinstance(urls, list) or any(not isinstance(v, str) or not v for v in ids + urls):
                raise ValueError(f'Malformed {field} source references')
            linked = set()
            for sid in ids:
                if sid not in sources:
                    register(sid, sid, '', note='Explicit canonical source ID has no registered origin or archived evidence; unavailable, not guessed.')
                linked.add(sid)
            linked.update(origin(url) for url in urls)
            reference_artifact = {'catalogReferences': 'data/model-catalog.json', 'portfolioReferences': 'data/portfolios.csv', 'assignmentReferences': 'data/assignments.csv'}[field]
            for sid in linked:
                sources[sid][field] += 1
                attach(sid, reference_artifact)
    references(catalog, 'catalogReferences')
    references(portfolios.values(), 'portfolioReferences')
    references(assignments, 'assignmentReferences')
    if exhaustive_registry.exists():
        registry = load_json(exhaustive_registry)
        if not isinstance(registry, dict) or set(registry) != {'schemaVersion', 'asOf', 'references'} or type(registry['schemaVersion']) is not int or registry['schemaVersion'] != 1 or not isinstance(registry['references'], list):
            raise ValueError('Invalid exhaustive capture reference registry')
        reference_urls, reference_names = set(), set()
        for reference in registry['references']:
            if not isinstance(reference, dict) or set(reference) != {'name', 'url', 'sourceId', 'receiptPath'} or any(not isinstance(value, str) or not value for value in reference.values()):
                raise ValueError('Invalid exhaustive capture reference')
            sid, url = reference['sourceId'], reference['url']
            if url in reference_urls or reference['name'] in reference_names:
                raise ValueError('Duplicate exhaustive capture reference')
            reference_urls.add(url)
            reference_names.add(reference['name'])
            if sid not in sources or sources[sid]['url'] != url:
                raise ValueError('Exhaustive capture reference disagrees with source registry')
            receipt_path = local_path(root, reference['receiptPath']).relative_to(root.resolve()).as_posix()
            if receipt_path not in sources[sid]['artifacts'] or receipt_path not in artifacts:
                raise ValueError('Exhaustive capture receipt lacks normalized source lineage')
            captured = load_json(local_path(root, receipt_path))
            validate_capture_reference_identity(reference, captured)
            verify_input(root, dict(path=captured['path'], sha256=captured['sha256']))
    for sid, source in sources.items():
        # Source results describe one producer's artifacts, not the global source's score inventory.
        if source['benchmarkCount']:
            source['status'] = 'included'
        if sid in source_result_notes:
            source['note'] += ' ' + ' '.join(source_result_notes[sid])
    coverage = dict(scope=manifest['scope'], generatedAt=datetime.now(timezone.utc).isoformat(),
                    totals=dict(sources=len(sources), artifacts=len(artifacts), benchmarks=len(benchmarks), excluded=sum(a['excluded'] for a in artifacts.values())),
                    sources=list(sources.values()), artifacts=list(artifacts.values()), notes=notes)
    validate_coverage(coverage, benchmarks)
    receipt = dict(schemaVersion=1, scope=manifest['scope'], generatedAt=coverage['generatedAt'], input_sha256=inputs,
                   totals=coverage['totals'], registrySources=len(ledger), declaredRegistryIds=[r['source_id'] for r in ledger],
                   datasets=dataset_receipts, statusCounts=dict(collections.Counter(s['status'] for s in sources.values())),
                   unavailable=[dict(id=s['id'], url=s['url'], reason=s['note']) for s in sources.values() if s['status'] == 'unavailable'],
                   checks=dict(allRegistrySourcesAccounted=True, allInputHashesVerified=True, allBenchmarkReferencesResolved=True, exactCountSums=True), notes=notes)
    return benchmarks, coverage, receipt


def validate_coverage(coverage, benchmarks):
    sources = {s['id']: s for s in coverage['sources']}
    artifacts = {a['path']: a for a in coverage['artifacts']}
    if len(sources) != len(coverage['sources']) or len(artifacts) != len(coverage['artifacts']): raise ValueError('Duplicate coverage identifiers')
    for artifact in artifacts.values():
        if not re.fullmatch('[0-9a-f]{64}', artifact['sha256']): raise ValueError('Invalid artifact hash')
        for field in ('observed', 'included', 'excluded'): count(artifact[field], field)
        if artifact['included'] + artifact['excluded'] > artifact['observed']: raise ValueError('Invalid artifact accounting')
        if sum(count(e['count'], 'exclusion') for e in artifact['exclusions']) != artifact['excluded']: raise ValueError('Unaccounted exclusions')
        if any(not e['locator'] or not e['reason'] for e in artifact['exclusions']): raise ValueError('Unexplained exclusion')
    counts = collections.Counter(row['sourceId'] for row in benchmarks)
    for sid, source in sources.items():
        if source['benchmarkCount'] != counts[sid] or any(p not in artifacts for p in source['artifacts']): raise ValueError(f'Invalid coverage references/counts: {sid}')
        if counts[sid] and source['status'] != 'included': raise ValueError(f'Scored source not included: {sid}')
        if source['kind'] not in KINDS or source['status'] not in {'included', 'context-only', 'unavailable', 'superseded'}: raise ValueError(f'Invalid source classification: {sid}')
        if source['status'] == 'unavailable' and not source['note']: raise ValueError(f'Unexplained unavailable source: {sid}')
        if source['kind'] == 'telemetry' and counts[sid]: raise ValueError('Telemetry included as benchmark')
        for field in ('benchmarkCount', 'catalogReferences', 'portfolioReferences', 'assignmentReferences'): count(source[field], field)
    if set(counts) - sources.keys(): raise ValueError('Unknown benchmark source')
    expected = dict(sources=len(sources), artifacts=len(artifacts), benchmarks=len(benchmarks), excluded=sum(a['excluded'] for a in artifacts.values()))
    if coverage['totals'] != expected: raise ValueError('Coverage total mismatch')


def family_area_coverage(benchmarks):
    """Name incorporated metrics; cybersecurity requires curated annotations."""
    areas = ('coding', 'computer_use', 'research', 'data', 'web', 'cybersecurity')
    patterns = {'coding': ('terminal-bench', 'tb4', 'frontiercode', 'deepswe', 'swe-', 'cursorbench', 'coding'),
                'computer_use': ('osworld', 'screenspot', 'automationbench'),
                'research': ('science', 'hle', 'arc-', 'gdp.pdf'),
                'data': ('gdpval', 'analystagent', 'briefcase'), 'web': ('browsecomp', 'designarena')}
    grouped = collections.defaultdict(lambda: collections.defaultdict(set))
    for row in benchmarks:
        name = row['benchmark']
        matches = [area for area, tokens in patterns.items() if any(token in name.lower() for token in tokens)]
        if isinstance(row.get('context'), dict) and 'cybersecurity' in row['context']:
            matches.append('cybersecurity')
        for area in matches or ['other']: grouped[row['family']][area].add(name)
    result = {}
    for family, metrics in sorted(grouped.items()):
        result[family] = {area: '; '.join(sorted(metrics[area])) if metrics[area] else 'Sin métricas específicas incorporadas; no inferir competencia.' for area in areas}
        if not metrics['cybersecurity']:
            result[family]['cybersecurity'] = 'Sin resultados anotados de ciberseguridad en esta familia; no concluye ausencia de resultados publicados ni competencia.'
        if metrics['other']: result[family]['other'] = '; '.join(sorted(metrics['other']))
    return result
