"""CyberBench v1.1 literal public aggregates; never executes benchmark content.

Overall existing scores retain their published display precision. Exact underlying
precision, standard-error field, per-track settings and operational metrics are
reconciled from immutable publisher JSON. Operational rows are not quality scores.
"""
import hashlib
import json
import re

INDEX = 'evidence/supplemental/EXHAUST_VALS_AGGREGATE_INDEX_2026-10-03.json'
INDEX_RECEIPT = 'evidence/supplemental/EXHAUST_VALS_AGGREGATE_INDEX_RECEIPT_2026-10-03.json'
BASE = 'Vals CyberBench v1.1'
SETTINGS_FIELDS = ('temperature', 'top_p', 'max_output_tokens', 'reasoning',
                   'reasoning_effort', 'verbosity', 'compute_effort', 'provider', 'harness')
LIMITS = [
    'Capture date is not evaluation date; provider, route and catalog harness equivalence is not established.',
    'Published stderr is an uncertainty field in percentage points; confidence level and calculation are not specified here.',
    'Overall matches an equal-weight track mean within rounding, not pooled success over 116 tasks; no denominator inferred.',
    'Null settings are undisclosed, not defaults. Task roster size is not necessarily the measurable score denominator.',
    'CyberBench uses mini-swe-agent globally; per-model JSON harness is null. Refusals count as failures; no CyberBench-specific fallback counts found in aggregate JSON.',
]


def contribute(api):
    load, add, context, exclude = (api[k] for k in ('load', 'add', 'context', 'exclude'))
    index = load(INDEX)
    derivation = load(INDEX_RECEIPT)
    if api['INPUTS'][INDEX] != derivation['sha256']:
        raise ValueError('Vals aggregate index hash mismatch')
    captures = {}
    receipt_paths = [index['benchmarkDataReceipt'], index['benchmarkPageReceipt']]
    receipt_paths += [m['pageReceipt'] for m in index['models']]
    receipt_paths += [c['receiptPath'] for c in index['reviewedCaptures']]
    declarations = []
    for receipt_path in dict.fromkeys(receipt_paths):
        receipt = load(receipt_path)
        raw = (api['ROOT'] / receipt['path']).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        api['INPUTS'][receipt['path']] = digest
        if digest != receipt['sha256'] or receipt['httpStatus'] != 200:
            raise ValueError('Unusable Vals capture: ' + receipt_path)
        url = receipt['requestedUrl']
        sid = 'URL-' + hashlib.sha256(url.encode()).hexdigest()[:20]
        api['LEDGER'][sid] = {'url': url}
        captures[receipt_path] = (sid, receipt)
        declarations.append({'id': sid, 'title': receipt['sourceId'].replace('_', ' '),
                             'url': url, 'kind': 'benchmark', 'checked': receipt['capturedAt'],
                             'limitations': 'Static public CyberBench aggregates/context only; no independent reproduction or route validation.'})
    sid, receipt = captures[index['benchmarkDataReceipt']]
    source = receipt['requestedUrl']
    date = receipt['capturedAt'][:10]
    data = json.loads((api['ROOT'] / receipt['path']).read_bytes())
    if set(data['tasks']) != {'overall', 'poc', 'patch'} or any(len(x) != 44 for x in data['tasks'].values()):
        raise ValueError('Unexpected CyberBench model/track inventory')
    existing = {r['model']: r for r in api['ROWS'] if r['benchmark'] == BASE}
    if set(existing) != {m['label'] for m in index['models']}:
        raise ValueError('Expected all 44 existing Vals Overall observations')
    start = len(api['ROWS'])
    for model in index['models']:
        key, label = model['key'], model['label']
        for track in ('overall', 'poc', 'patch'):
            result = data['tasks'][track][key]
            projection = model['tracks'][track]
            if any(result.get(k) != v for k, v in projection.items()
                   if k not in ('taskRosterSize', 'measurableTaskCount')):
                raise ValueError('Vals source/index aggregate mismatch: ' + key)
            locator = receipt['path'] + '#/tasks/' + track + '/' + key.replace('~', '~0').replace('/', '~1')
            settings = {k: result.get(k) for k in SETTINGS_FIELDS}
            effort = result.get('reasoning_effort') or 'not stated'
            cyber = {'resultType': 'independent', 'benchmarkVersion': 'v1.1',
                     'evaluationDate': None, 'captureDate': date,
                     'taskDenominator': None, 'attemptBudget': None,
                     'settings': 'CyberBench v1.1 ' + track + '; mini-swe-agent; exact publisher per-model settings: ' + json.dumps(settings, sort_keys=True),
                     'limitations': LIMITS[:]}
            extra = {'cybersecurity': cyber, 'publishedModelKey': key,
                     'reportedUncertaintyPct': result['stderr'], 'uncertaintyField': 'stderr',
                     'publisherSettings': settings, 'track': track, 'sourceDataLocator': locator,
                     'sourceDataCaptureDate': date,
                     'taskRosterSize': projection['taskRosterSize'],
                     'measurableTaskCount': projection['measurableTaskCount'],
                     'benchmarkUpdatedDate': data['metadata']['updated']}
            def emit(name, value, unit, kind, field):
                add(sid, label, name, value, unit, effort, date, locator + '/' + field,
                    'Literal public publisher JSON aggregate; operational and uncertainty metrics are not capability scores.',
                    extra=dict(extra, metricKind=kind), source=source)
            if track == 'overall':
                row = existing[label]
                if abs(row['value'] - result['accuracy']) > 0.0051 or row['value'] != model['pageOverallAccuracy']:
                    raise ValueError('Vals Overall displayed/data score conflict: ' + key)
                original_date = row['context'].get('cybersecurity', {}).get('captureDate', row.get('date', date))
                overall_extra = dict(extra, cybersecurity=dict(cyber, captureDate=original_date))
                row['effort'] = effort
                row['methodology'] = 'Published Overall display score reconciled to exact publisher JSON; ' + cyber['settings']
                row['context'].update(overall_extra, reportedAccuracyExactPct=result['accuracy'],
                                      operationalMetadataSource=source)
                exclude(locator + '/accuracy', 'Exact underlying precision of existing Overall observation; annotated, not another trial.')
            else:
                emit(BASE + ' ' + ('PoC' if track == 'poc' else 'Patch'), result['accuracy'], '%', 'capability', 'accuracy')
            suffix = ' (' + ('Overall' if track == 'overall' else 'PoC' if track == 'poc' else 'Patch') + ')'
            emit(BASE + ' reported standard error' + suffix, result['stderr'], 'percentage points', 'uncertainty', 'stderr')
            if result['cost_per_test'] is None:
                exclude(locator + '/cost_per_test', 'Publisher null: no track cost/test published; never zero.')
            else:
                emit(BASE + ' cost per test' + suffix, result['cost_per_test'], 'USD/test', 'cost', 'cost_per_test')
            emit(BASE + ' duration' + suffix, result['latency'], 'seconds/test', 'duration', 'latency')
        page_sid, page_receipt = captures[index['benchmarkPageReceipt']]
        pricing = tuple(map(float, re.findall(r'[\d.]+', model['overallDisplay']['pricing'])))
        if len(pricing) != 2:
            raise ValueError('Unexpected Vals input/output price display')
        for direction, price in zip(('input', 'output'), pricing):
            add(page_sid, label, BASE + ' ' + direction + ' token price', price,
                'USD/million tokens', 'not applicable', page_receipt['capturedAt'][:10],
                page_receipt['path'] + '#overall-leaderboard/rank/' + str(model['rank']) + '/input-output-price/' + direction,
                'Literal publisher leaderboard price; model-page prose establishes per-million-token units. Not benchmark capability.',
                extra={'cybersecurity': dict(cyber, settings='Model token list price; not track capability or evaluation budget.'),
                       'metricKind': 'price', 'publishedModelKey': key, 'inputOutputPriceDisplay': model['overallDisplay']['pricing']},
                source=page_receipt['requestedUrl'])
    context(sid, receipt['path'] + '#aggregate-reconciliation', index,
            'All44 models across Overall/PoC/Patch reconciled; task-level records and unrelated benchmarks excluded.', date)
    for receipt_path, (capture_sid, capture) in captures.items():
        count = sum(r['sourceId'] == capture_sid for r in api['ROWS'][start:])
        api['RESULTS'].append({'sourceId': capture_sid, 'status': 'included' if count else 'context-only',
            'checked': capture['capturedAt'], 'httpStatus': capture['httpStatus'], 'benchmarkCount': count,
            'reason': 'Exhaustive public CyberBench aggregate reconciliation; duplicates, unrelated benchmarks and source patch examples are not new trials.',
            'artifacts': [capture['path'], receipt_path]})
    return declarations
