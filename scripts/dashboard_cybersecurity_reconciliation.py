"""Offline, bounded reconciliation of archived public aggregate evidence."""
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

STATUSES = ('incorporated', 'context-only', 'excluded', 'not-published', 'unresolved')
SEED_PATH = 'data/cybersecurity-reconciliation.json'


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Invalid reconciliation {label}')
    return value


def strings(value, label, nonempty_list=False):
    if not isinstance(value, list) or (nonempty_list and not value):
        raise ValueError(f'Invalid reconciliation {label}')
    for item in value:
        nonempty(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f'Duplicate reconciliation {label}')
    return value


def stable_id(entry):
    encoded = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return 'reconcile-' + hashlib.sha256(encoded).hexdigest()[:24]


def load_seed(root):
    from dashboard_source_coverage import load_json
    path = Path(root) / SEED_PATH
    return load_json(path) if path.exists() else None


def build_reconciliation(seed, results, catalog, source_coverage, root):
    from dashboard_source_coverage import digest, load_json, local_path
    if not isinstance(seed, dict) or set(seed) != {'schemaVersion', 'asOf', 'scope', 'searchBoundary', 'reviewedSources', 'dispositions', 'catalogReview'} or type(seed['schemaVersion']) is not int or seed['schemaVersion'] != 1:
        raise ValueError('Invalid reconciliation seed schema')
    as_of = nonempty(seed['asOf'], 'asOf')
    if len(as_of) != 10 or date.fromisoformat(as_of).isoformat() != as_of:
        raise ValueError('Invalid reconciliation asOf')
    for field in ('scope', 'searchBoundary'):
        nonempty(seed[field], field)
    if root is None or not isinstance(source_coverage, dict):
        raise ValueError('Reconciliation requires verified local sourceCoverage')
    root = Path(root)
    sources = {item['id']: item for item in source_coverage['sources']}
    artifacts = {item['path']: item for item in source_coverage['artifacts']}
    catalog_keys = set(catalog)
    seed_file = root / SEED_PATH
    if seed_file.exists():
        seed_artifact = artifacts.get(SEED_PATH)
        if seed_artifact is None or digest(seed_file) != seed_artifact['sha256']:
            raise ValueError('Reconciliation seed lacks verified sourceCoverage hash')
        if load_json(seed_file) != seed:
            raise ValueError('Reconciliation disagrees with archived seed')

    def relative(name):
        nonempty(name, 'artifact path')
        if name.startswith(''):
            name = name[len(''):]
        return local_path(root, name).relative_to(root.resolve()).as_posix()

    def verified(name, sid):
        name = relative(name)
        if name not in artifacts or name not in sources[sid]['artifacts']:
            raise ValueError(f'Reconciliation artifact lacks source lineage: {sid}/{name}')
        if digest(local_path(root, name)) != artifacts[name]['sha256']:
            raise ValueError(f'Reconciliation artifact hash mismatch: {name}')
        return name

    reviewed = seed['reviewedSources']
    if not isinstance(reviewed, list) or not reviewed:
        raise ValueError('Missing reviewed sources')
    by_id = {}
    receipt_status = {}
    for item in reviewed:
        if not isinstance(item, dict) or set(item) != {'sourceId', 'sourceUrl', 'captureDate', 'receiptPath', 'sections', 'catalogKeys', 'limitations'}:
            raise ValueError('Invalid reviewed source schema')
        sid = nonempty(item['sourceId'], 'sourceId')
        if sid not in sources or sid in by_id:
            raise ValueError(f'Unknown or duplicate reviewed source: {sid}')
        if item['sourceUrl'] != sources[sid]['url']:
            raise ValueError(f'Reviewed source URL disagrees with lineage: {sid}')
        url = urlparse(item['sourceUrl'])
        if url.scheme not in ('http', 'https') or not url.netloc:
            raise ValueError('Reviewed source must have a public URL')
        capture_date = nonempty(item['captureDate'], 'captureDate')
        if len(capture_date) != 10 or date.fromisoformat(capture_date).isoformat() != capture_date or capture_date > as_of:
            raise ValueError('Invalid reviewed capture date')
        strings(item['catalogKeys'], 'catalogKeys')
        if not set(item['catalogKeys']) <= catalog_keys:
            raise ValueError('Unknown reviewed catalog key')
        strings(item['limitations'], 'limitations')
        strings(item['sections'], 'sections', True)
        receipt_name = verified(item['receiptPath'], sid)
        receipt = load_json(local_path(root, receipt_name))
        if not isinstance(receipt, dict):
            raise ValueError('Invalid capture receipt')
        timestamp = receipt.get('capturedAt', '')
        if not isinstance(timestamp, str) or timestamp[:10] != capture_date:
            raise ValueError('Review capture date disagrees with receipt')
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if item['sourceUrl'] not in (receipt.get('requestedUrl'), receipt.get('url'), receipt.get('finalUrl')):
            raise ValueError('Review URL disagrees with capture receipt')
        status = receipt.get('httpStatus')
        if type(status) is not int or not 100 <= status <= 599:
            raise ValueError('Invalid capture HTTP status')
        receipt_status[sid] = status
        captured = verified(receipt.get('path'), sid)
        if digest(local_path(root, captured)) != receipt.get('sha256'):
            raise ValueError('Captured bytes disagree with receipt hash')
        for section in item['sections']:
            verified(section.partition('#')[0], sid)
            if not section.partition('#')[2]:
                raise ValueError('Reviewed section must have an explicit locator')
        for field in ('textExtraction',):
            derived = receipt.get(field)
            if derived:
                name = verified(derived['path'], sid)
                if digest(local_path(root, name)) != derived['sha256']:
                    raise ValueError('Derived capture hash mismatch')
        for derived in receipt.get('derivedArtifacts', []):
            name = verified(derived['path'], sid)
            if digest(local_path(root, name)) != derived['sha256']:
                raise ValueError('Derived capture hash mismatch')
        by_id[sid] = item

    entries = []
    for result in results:
        sid = result['sourceId']
        if sid not in by_id or receipt_status[sid] != 200:
            raise ValueError(f'Incorporated result lacks successful reviewed capture: {sid}')
        provenance = result['provenance']
        verified(provenance.partition('#')[0], sid)
        entry = dict(sourceId=sid, sourceUrl=result['sourceUrl'], publishedModel=result['publishedModel'],
                     benchmark=result['benchmark'], metric=result['benchmark'], status='incorporated',
                     reason='Resultado agregado publicado incorporado con su linaje exacto; no calibra rutas.',
                     locator=provenance, resultIds=[result['id']])
        entries.append(dict(id=stable_id(entry), **entry))
    if not isinstance(seed['dispositions'], list):
        raise ValueError('Invalid explicit dispositions')
    for disposition in seed['dispositions']:
        if not isinstance(disposition, dict) or set(disposition) != {'sourceId', 'publishedModel', 'benchmark', 'metric', 'status', 'reason', 'locator'}:
            raise ValueError('Invalid explicit disposition schema')
        sid = nonempty(disposition['sourceId'], 'sourceId')
        if sid not in by_id or disposition['status'] not in STATUSES[1:]:
            raise ValueError('Unknown disposition source or status')
        if disposition['publishedModel'] is not None:
            nonempty(disposition['publishedModel'], 'publishedModel')
        for field in ('benchmark', 'metric', 'reason', 'locator'):
            nonempty(disposition[field], field)
        locator = disposition['locator']
        verified(locator.partition('#')[0], sid)
        if not locator.partition('#')[2]:
            raise ValueError('Disposition locator requires an explicit source anchor')
        entry = dict(disposition, sourceUrl=by_id[sid]['sourceUrl'], resultIds=[])
        entries.append(dict(id=stable_id(entry), **entry))
    if len({entry['id'] for entry in entries}) != len(entries):
        raise ValueError('Duplicate reconciliation entry')
    if set(by_id) != {entry['sourceId'] for entry in entries}:
        raise ValueError('Reviewed sources require explicit result or section dispositions')
    unresolved_sources = {entry['sourceId'] for entry in entries if entry['status'] == 'unresolved'}
    if any(status != 200 and sid not in unresolved_sources for sid, status in receipt_status.items()):
        raise ValueError('Failed HTTP source requires an unresolved accessibility or metric disposition')
    reviews = seed['catalogReview']
    if not isinstance(reviews, list) or len(reviews) != len(catalog_keys):
        raise ValueError('Catalog review must cover the complete catalog')
    keys = set()
    for review in reviews:
        if not isinstance(review, dict) or set(review) not in ({'catalogKey', 'sourceIds', 'conclusion'}, {'catalogKey', 'sourceIds', 'conclusion', 'reviewState'}):
            raise ValueError('Invalid catalog review schema')
        key = nonempty(review['catalogKey'], 'catalogKey')
        if key not in catalog_keys or key in keys:
            raise ValueError('Unknown or duplicate catalog review key')
        keys.add(key)
        state=review.get('reviewState','reviewed')
        if state not in {'pending','reviewed'}:raise ValueError('Unknown catalog review state')
        strings(review['sourceIds'], 'review sourceIds', state=='reviewed')
        if state=='pending' and review['sourceIds']:raise ValueError('Pending review cannot claim reviewed source linkage')
        if not set(review['sourceIds']) <= set(by_id) or any(key not in by_id[sid]['catalogKeys'] for sid in review['sourceIds']):
            raise ValueError('Catalog review lacks reviewed source linkage')
        nonempty(review['conclusion'], 'catalog conclusion')
    counter = Counter(entry['status'] for entry in entries)
    return dict(schemaVersion=1, asOf=as_of, scope=seed['scope'], searchBoundary=seed['searchBoundary'],
                reviewedSources=reviewed, entries=entries, catalogReview=reviews,
                counts={status: counter[status] for status in STATUSES},
                closure='open' if counter['unresolved'] or any(r.get('reviewState')=='pending' for r in reviews) else 'reconciled-corpus')


def validate_reconciliation(reconciliation, results, catalog, source_coverage, root, seed=None):
    if not isinstance(reconciliation, dict):
        raise ValueError('Invalid reconciliation object')
    if seed is None:
        seed = {key: reconciliation.get(key) for key in ('schemaVersion', 'asOf', 'scope', 'searchBoundary', 'reviewedSources', 'catalogReview')}
        entries = reconciliation.get('entries')
        if not isinstance(entries, list):
            raise ValueError('Missing reconciliation entries')
        if any(not isinstance(entry, dict) for entry in entries):
            raise ValueError('Invalid reconciliation entry')
        seed['dispositions'] = [{key: entry.get(key) for key in ('sourceId', 'publishedModel', 'benchmark', 'metric', 'status', 'reason', 'locator')}
                                for entry in entries if entry.get('status') != 'incorporated']
    expected = build_reconciliation(seed, results, catalog, source_coverage, root)
    if json.dumps(reconciliation, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise ValueError('Reconciliation entries, lineage, counts or closure disagree with verified corpus')
