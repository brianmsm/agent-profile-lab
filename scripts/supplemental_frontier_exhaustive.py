"""Official-card literal labels and embedded cyber datasets; static ingestion only."""
import hashlib

from supplemental_cybersecurity import metadata

BUNDLE = 'evidence/supplemental/EXHAUST_FRONTIER_LABELS_2026-10-03.json'
OLDER_BUNDLE = 'evidence/supplemental/EXHAUST_FRONTIER_OLDER_LABELS_2026-10-03.json'
PUBLISHER_BUNDLE = 'evidence/supplemental/EXHAUST_FRONTIER_PUBLISHER_LABELS_2026-10-03.json'


def contribute(api):
    bundle = api['load'](BUNDLE)
    older = api['load'](OLDER_BUNDLE)
    bundle['rows'].extend(older['rows'])
    publishers = api['load'](PUBLISHER_BUNDLE)
    bundle['rows'].extend(publishers['rows'])
    receipts = {}
    declarations = {}

    def verified(path):
        if path in receipts:
            return receipts[path]
        receipt = api['load'](path)
        raw = (api['ROOT'] / receipt['path']).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        api['INPUTS'][receipt['path']] = digest
        if receipt['httpStatus'] != 200 or digest != receipt['sha256']:
            raise ValueError('Unusable frontier evidence: ' + path)
        if receipt.get('textExtraction'):
            extraction = receipt['textExtraction']
            api['load'](extraction['path'], 'text')
            if api['INPUTS'][extraction['path']] != extraction['sha256']:
                raise ValueError('Frontier text extraction mismatch: ' + path)
        receipts[path] = receipt
        url = receipt['requestedUrl']
        sid = 'URL-' + hashlib.sha256(url.encode()).hexdigest()[:20]
        api['LEDGER'][sid] = {'url': url}
        declarations[sid] = {'id': sid, 'title': receipt['sourceId'].replace('_', ' '),
                             'url': url, 'kind': 'benchmark', 'checked': receipt['capturedAt'],
                             'limitations': 'Static published aggregate labels only; no reproduction, interpolation or deployed route equivalence.'}
        return receipt
    for path in older['verifiedContextReceipts'] + publishers['verifiedContextReceipts']:
        verified(path)

    # Native reader output proves content inventory, not an original HTTP200 response.
    reader = api['load']('evidence/supplemental/EXHAUST_FRONTIER_OLD_RELEASE_NATIVE_READER_RECEIPT_2026-10-03.json')
    reader_text = api['load'](reader['path'], 'text')
    if reader['httpStatus'] is not None or api['INPUTS'][reader['path']] != reader['sha256']:
        raise ValueError('Unexpected native-reader representation receipt')
    reader_sid = 'URL-' + hashlib.sha256(reader['requestedUrl'].encode()).hexdigest()[:20]
    api['context'](reader_sid, reader['path'] + '#official-release-reader-inventory', reader_text,
                   'Native official release text preserved with truthful null HTTP status; original GET403. Reader-only numerical claims are not admitted as HTTP200 benchmark observations.',
                   reader['capturedAt'][:10])

    # Figure51 resolves the abbreviated prose comparator; update rather than duplicate.
    identity_receipt = verified('evidence/supplemental/EXHAUST_FRONTIER_ASTRA_FIG51_RECEIPT_2026-10-03.json')
    for existing in api['ROWS']:
        if existing['model'] == 'Sol (Astra system-card comparator)' and existing['benchmark'].startswith('OpenAI Sandbox Bench'):
            existing['model'] = 'GPT-5.6 Sol'
            existing['context']['frontierComparatorIdentity'] = {
                'locator': identity_receipt['path'] + '#Figure51/legend',
                'reason': 'Figure51 explicitly labels the abbreviated prose Sol comparator GPT-5.6 Sol.',
                'sha256': identity_receipt['sha256']}

    counts = {}
    for record in bundle['rows']:
        receipt = verified(record['receiptPath'])
        for evidence in record.get('evidenceReceipts', []):
            verified(evidence)
        url = receipt['requestedUrl']
        sid = 'URL-' + hashlib.sha256(url.encode()).hexdigest()[:20]
        model, benchmark, value = (record[k] for k in ('model', 'benchmark', 'value'))
        if ('CYBER_ANTH_FABLE51_PUBLIC_' in record['locator']
                and 'Figure3.3.1.A/page48' in record['locator']
                and benchmark in ('ExploitBench mean capability flags (AutoNudge)', 'ExploitBench Cap% (AutoNudge)')):
            axis = 'Mean nudges per run' if 'mean capability' in benchmark else 'Runs reaching cap (%)'
            reason = 'Graphic axis and caption/prose disagree on metric meaning; literal label retained as context, no assumed erratum or definite normalized unit.'
            api['context'](sid, record['locator'] + '/ambiguous/' + model + '/' + benchmark,
                           {'publishedModel': model, 'printedValue': value, 'printedAxis': axis,
                            'captionMetric': benchmark}, reason, receipt['capturedAt'][:10])
            api['exclude'](record['locator'], reason)
            continue
        # Same-card prose and graphic labels are one observation, not independent runs.
        overlaps = [r for r in api['ROWS'] if r['sourceId'] == sid and r['model'] == model
                    and r['benchmark'] == benchmark and r['value'] == value]
        if overlaps:
            api['exclude'](record['locator'], 'Exact same-card literal observation already incorporated; graphic/prose republication is not an independent trial.')
            continue
        date = receipt['capturedAt'][:10]
        kind = record.get('resultType', 'vendor')
        cyber = metadata(kind,
                         date, record['settings'], denominator=record.get('denominator'),
                         budget=record.get('budget'),
                         limits=['Exact card-specific reruns/rounding preserved; other cards and publisher protocols are not interchangeable.',
                                 'Graphic uncertainty and unlabeled intermediate values are not interpolated.'])
        cross_category = any(term in benchmark.lower() for term in ('prompt injection', 'injection robustness', 'instruction hierarchy'))
        if cross_category:
            cyber['limitations'].append('Cross-category agent-security safeguard comparator, not cyber offense capability or a cyber-specific harmful-request score.')
        api['add'](sid, model, benchmark, value, record['unit'], record.get('effort', 'not stated'), date,
                   record['locator'], ('Published cross-category agent-security safeguard comparator; ' if cross_category else 'Literal published cybersecurity aggregate; ') + record['settings'],
                   extra=dict(record.get('extra', {}), cybersecurity=cyber, captureNotEvaluationDate=True,
                              literalLabelBundles=[BUNDLE, OLDER_BUNDLE, PUBLISHER_BUNDLE],
                              crossCategorySecurityComparator=cross_category,
                              sourceCaptureSha256=receipt['sha256']), source=url)
        counts[sid] = counts.get(sid, 0) + 1
    for path, receipt in receipts.items():
        sid = 'URL-' + hashlib.sha256(receipt['requestedUrl'].encode()).hexdigest()[:20]
        if any(r['sourceId'] == sid for r in api['RESULTS']):
            continue
        api['context'](sid, receipt['path'] + '#literal-label-source',
                       {'sha256': receipt['sha256'], 'literalLabelBundle': BUNDLE},
                       'Exact public evidence bytes for official chart labels; no unlabeled values inferred.', receipt['capturedAt'][:10])
        api['RESULTS'].append({'sourceId': sid, 'status': 'included' if counts.get(sid) else 'context-only',
                              'checked': receipt['capturedAt'], 'httpStatus': receipt['httpStatus'],
                              'benchmarkCount': counts.get(sid, 0),
                              'reason': 'Verified official card/figure literal-label evidence.',
                              'artifacts': [path, receipt['path']]})
    return list(declarations.values())
