"""Bounded exact-publication cyber aggregates; static receipts, no evaluation execution.

Graphic constants below are literal printed labels, never interpolated coordinates.
Source mirrors and parent-label/gateway identities do not create additional trials.
"""
import hashlib
import json
import re

CAPTURE_DATE = '2026-10-03'
BASE = 'evidence/supplemental/'
LIMITS = ['Capture date is not evaluation date.', 'No gateway, subscription, OMP or deployed-route equivalence established.']
CANONICAL_SOURCE_IDS = {
    'https://opencode.ai/v2/docs/console/go/': 'GO',
    'https://commandcode.ai/docs/plans/goat': 'CC',
    'https://nan.builders/docs/models': 'NAN',
}


def contribute(api):
    declarations = []
    captures = {}
    for path in sorted((api['ROOT'] / BASE).glob('EXHAUST_OPEN_*_RECEIPT_2026-10-03.json')):
        relative = str(path.relative_to(api['ROOT']))
        receipt = api['load'](relative)
        raw = (api['ROOT'] / receipt['path']).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        api['INPUTS'][receipt['path']] = digest
        if digest != receipt['sha256']:
            raise ValueError('Open-model immutable receipt mismatch: ' + relative)
        sid = CANONICAL_SOURCE_IDS.get(receipt['requestedUrl'], 'URL-' + hashlib.sha256(receipt['requestedUrl'].encode()).hexdigest()[:20])
        api['LEDGER'].setdefault(sid, {'url': receipt['requestedUrl']})
        artifacts = [receipt['path'], relative]
        text = None
        if 'textExtraction' in receipt:
            extraction = receipt['textExtraction']
            text = api['load'](extraction['path'], 'text')
            if api['INPUTS'][extraction['path']] != extraction['sha256']:
                raise ValueError('Open-model text extraction mismatch: ' + relative)
            artifacts.append(extraction['path'])
        elif not receipt['headers'].get('Content-Type', '').startswith('image/'):
            text = raw.decode('utf-8', errors='replace')
        name = receipt['sourceId'].removeprefix('EXHAUST_OPEN_')
        captures[name] = (sid, receipt, text)
        declarations.append({'id': sid, 'title': receipt['sourceId'], 'url': receipt['requestedUrl'],
                             'kind': 'benchmark', 'checked': receipt['capturedAt'],
                             'limitations': 'Bounded publication/source reconciliation; only literal aggregates, not execution or route equivalence.'})
        api['context'](sid, receipt['path'] + '#reviewed-static-source', text if text is not None else {'sha256': digest, 'bytes': len(raw)},
                       'Full static capture retained for bounded reconciliation; binary charts use only explicitly printed data labels.', CAPTURE_DATE)
        api['RESULTS'].append({'sourceId': sid, 'status': 'context-only' if receipt['httpStatus'] == 200 else 'unavailable',
                               'checked': receipt['capturedAt'], 'httpStatus': receipt['httpStatus'], 'benchmarkCount': 0,
                               'reason': 'Reviewed exact static publication; no inherited parent-label or gateway scores.', 'artifacts': artifacts})
    for row in api['ROWS']:
        if row.get('sourceId') == 'MIMO' and row.get('benchmark') == 'CyberGym':
            cyber = row.setdefault('context', {}).get('cybersecurity')
            if cyber:
                cyber['limitations'].append('MiMo technical report §5.2 footnote1 states evaluation environments were corrected using §4.2.4; this is a modified CyberGym protocol, not established standard-publisher equivalence.')
                row['context']['protocolEvidence'] = captures['MIMO_REPORT'][1]['textExtraction']['path'] + '#5.2/footnote1'
        if row.get('benchmark') == 'SEC-Bench Pro (Pass@1)' and row.get('model') == 'DS-V4.1-Flash':
            cyber = row.setdefault('context', {}).get('cybersecurity')
            if cyber:
                cyber['benchmarkVersion'] = '260505'
                row['context']['protocolEvidence'] = captures['DEEPSEEK_REPORT'][1]['textExtraction']['path'] + '#evaluation/cyber-security-version'

    def emit(name, model, benchmark, value, unit, fragment, settings, denominator=None, budget=None, effort='not stated', extra=None, kind='vendor'):
        sid, receipt, _ = captures[name]
        if receipt['httpStatus'] != 200:
            raise ValueError('Numeric result from unavailable capture: ' + name)
        cyber = {'resultType': kind if model in {'GLM-5.3', 'Kimi K3', 'MiMo-V2.6-Pro', 'MiMo-V2.6-Flash'} else 'vendor-comparator' if kind == 'vendor' else kind,
                 'benchmarkVersion': None, 'evaluationDate': None, 'captureDate': CAPTURE_DATE,
                 'taskDenominator': denominator, 'attemptBudget': budget, 'settings': settings, 'limitations': list(LIMITS)}
        details = {'cybersecurity': cyber, 'captureNotEvaluationDate': True}
        details.update(extra or {})
        api['add'](sid, model, benchmark, value, unit, effort, CAPTURE_DATE, receipt['path'] + '#' + fragment,
                   'Exact published static aggregate; ' + settings, extra=details, source=receipt['requestedUrl'])
        result = next(r for r in api['RESULTS'] if r['sourceId'] == sid)
        result['benchmarkCount'] += 1
        result['status'] = 'included'
        result['reason'] = 'Literal published cyber aggregates incorporated; mirrors/absences/uncertain identity separately reconciled.'

    text = captures['GLM53_CARD'][2]
    table = [[c.strip().replace('**', '') for c in line.strip().strip('|').split('|')]
             for line in text.splitlines() if line.startswith('|')]
    header = table[0][1:]
    if header != ['GLM-5.3', 'GLM-5.2', 'Kimi K3', 'DeepSeek-V4 Pro-0813', 'Qwen3.8-Max', 'Opus 4.8', 'Fable 5 (w/ fallback)', 'GPT-5.6 Sol']:
        raise ValueError('GLM exact comparison header changed')
    common = 'Claude Code 2.1.207; max reasoning effort; temperature=1.0, top_p=1.0, max_new_tokens=128000; no web tools; domain whitelist.'
    for row in table[2:]:
        if row[0] not in {'CyberGym', 'ExploitGym (2h / 6h)', 'ExploitBench'}:
            continue
        for model, cell in zip(header, row[1:]):
            fragment = 'Benchmark/' + row[0] + '/' + model
            if cell == '–':
                api['exclude'](captures['GLM53_CARD'][1]['path'] + '#' + fragment, 'Publisher dash, not zero.')
                continue
            if model == 'Fable 5 (w/ fallback)':
                api['exclude'](captures['GLM53_CARD'][1]['path'] + '#' + fragment, 'Publication conflict: table labels Fable5 with fallback, cyber graphic and narrative label identical values Mythos5. Attribution unresolved; no score inherited by either model.')
                continue
            target = model == 'GLM-5.3'
            if row[0].startswith('ExploitGym'):
                values = [int(v.strip()) for v in cell.split('/')]
                for hours, value in zip((2, 6), values):
                    known = model in {'GLM-5.3', 'Kimi K3', 'Qwen3.8-Max'}
                    tps = {'GLM-5.3': 115, 'Kimi K3': 40, 'Qwen3.8-Max': 47}.get(model)
                    settings = (common + f' Single-run successful-task count over 869 tasks; API time rescaled using {tps} TPS plus non-API overhead.' if known else 'Vendor comparison successful-task count at 2h/6h time-normalized budget; exact comparator harness/sampling/TPS not stated; GLM target settings not transferred.')
                    emit('GLM53_CARD', model, f'ExploitGym successful tasks ({hours}h time-normalized)', value, 'successful tasks', fragment + f'/{hours}h', settings, 869 if known else None, f'{hours} hours time-normalized', 'max' if known else 'not stated', {'hours': hours, 'normalizationTPS': tps})
            elif row[0] == 'CyberGym':
                emit('GLM53_CARD', model, 'CyberGym (single-run Pass@1)' if target else 'CyberGym (vendor-comparator Pass@1)', float(cell), '%', fragment,
                     common + ' Single run over 1,507 tasks; unlimited timeout; agent inside container; Git information removed.' if target else 'Vendor comparison Pass@1; target GLM harness/settings not transferred to comparator.', 1507 if target else None, 'unlimited timeout' if target else None, 'max' if target else 'not stated')
            else:
                emit('GLM53_CARD', model, 'ExploitBench capability coverage (union across 3 revisions)' if target else 'ExploitBench capability coverage (comparator protocol undisclosed)', float(cell), '%', fragment,
                     common + ' Average task coverage from union of achieved capabilities across 3 revisions, 41 tasks, 300 interaction rounds.' if target else 'Vendor comparison capability coverage; comparator arm/revision/harness protocol not disclosed; not full-ACE success rate.', 41 if target else None, '300 interaction rounds; 3 revisions' if target else None, 'max' if target else 'not stated')

    report = captures['KIMI_REPORT'][2]
    expected = ['approximately 70%', '16 previously unknown', 'solving 14 of 36 tasks (38.9%) versus 8 of 36 (22.2%)', '10 of the 14']
    flat = ' '.join(report.split())
    if not all(s in flat for s in expected):
        raise ValueError('Kimi literal private cyber aggregate changed')
    for model, count, rate in [('Kimi K3', 14, 38.9), ('GLM-5.2', 8, 22.2)]:
        setting = 'Private 36-task suite: 16 user-space and 20 kernel tasks; expert-solvable; standard configurations and progressive kernel mitigations; exact attempt/token budget not disclosed.'
        emit('KIMI_REPORT', model, 'Kimi private exploit suite solved tasks', count, 'solved tasks', '6.2.2/private-suite/' + model + '/count', setting, 36)
        emit('KIMI_REPORT', model, 'Kimi private exploit suite solve rate', rate, '%', '6.2.2/private-suite/' + model + '/rate', setting, 36, extra={'successCount': count})
    emit('KIMI_REPORT', 'Kimi K3', 'Kimi private user-space track solved tasks', 10, 'solved tasks', '6.2.2/user-space/count', 'Published 10 of the 14 total successful tasks belong to the 16-task user-space track; no kernel result derived by subtraction.', 16)
    emit('KIMI_REPORT', 'Kimi K3', 'Kimi reviewed discovery confirmation rate (approximate)', 70, '%', '6.2.2/discovery/confirmation', 'Approximately 70% of human-reviewed candidate findings confirmed; reviewed candidate denominator undisclosed; not benchmark task success.', extra={'approximate': True})
    emit('KIMI_REPORT', 'Kimi K3', 'Kimi previously unknown confirmed vulnerabilities', 16, 'confirmed vulnerabilities', '6.2.2/discovery/unknown-count', 'Human-reviewed discovery campaign across six projects; unknown total candidate count; not normalized benchmark score.', extra={'affectedProjects': 6})
    emit('KIMI_REPORT', 'Kimi K3', 'Kimi previously unknown vulnerability affected projects', 6, 'projects', '6.2.2/discovery/unknown-project-count', 'Six projects with the 16 previously unknown confirmed vulnerabilities; project coverage, not task success.')

    # Published graphical labels; hashes above pin both values and their attribution.
    for model, value, uncertainty in [('Kimi K3', 32.2, 4.2), ('GLM-5.2', 24.4, 4.0)]:
        emit('KIMI_AISI_EXPLOITCHART', model, 'ExploitBench ladder score (mean cap, % of 16)', value, '%', 'figure1/' + model,
             'UK AISI/CAISI preliminary assessment; mean capability-ladder score, % of 16; 41 tasks. Printed uncertainty is 95% CI, not inferred from bar height.', 41,
             extra={'reportedUncertaintyPct': uncertainty, 'confidenceLevel': 0.95, 'graphicLiteral': True}, kind='independent')
    for model, values in [('Kimi K3', [0, 0, 17, 34, 41]), ('GLM-5.2', [0, 0, 6, 24, 41])]:
        for milestone, value in zip(['full exploit ACE', 'general primitives', 'V8 primitives', 'bug reproduction', 'coverage'], values):
            emit('KIMI_AISI_HEATMAP', model, 'ExploitBench tasks reaching ' + milestone, value, 'tasks', 'figure3/' + model + '/' + milestone,
                 'Exact printed Figure3 task milestone count; denominator 41. Milestone outcomes are nested and not independent successes; attempt/union protocol not stated here.', 41, extra={'graphicLiteral': True}, kind='independent')
    nist = captures['KIMI_AISI'][2]
    if not all(s in nist for s in ['100M-token', '10 attempts', 'step 17', 'step 11']):
        raise ValueError('NIST TLO textual aggregates changed')
    for model, value in [('Kimi K3', 17), ('GLM-5.2', 11)]:
        emit('KIMI_AISI', model, 'The Last Ones mean attack-path steps reached', value, 'steps', 'TLO/' + model + '/mean-steps',
             '32-step simulated corporate range; 100M-token limit; no active defenders/alert penalties; intentional path. Mean progress, not success probability.', 32, '100M tokens', kind='independent')
    emit('KIMI_AISI', 'Kimi K3', 'The Last Ones completed attempts', 1, 'completed attempts', 'TLO/Kimi K3/completions',
         'Literal one completed run out of ten attempts; 100M-token limit; no success rate derived.', 10, '100M tokens', kind='independent')
    # Static public appendix arrays are data, not executed JavaScript. Include
    # hidden-card/table cells; exclude exact card mirrors, preserve conflicts.
    appendix = captures['MIMO26_BENCH_JS'][2]
    models_block = appendix.split('const MODELS = [', 1)[1].split('];', 1)[0]
    published_models = re.findall(r"key:\s*'([^']+)'.*?name:\s*'([^']+)'", models_block)
    if len(published_models) != 11:
        raise ValueError('MiMo article exact model order changed')
    cyber_block = appendix.split("{ title: 'Cyber',", 1)[1].split('\n        ] },', 1)[0]
    matches = re.findall(r"name:\s*'([^']+)'\s*,\s*scores:\s*(\[[^\]]+\])", cyber_block)
    if len(matches) != 5:
        raise ValueError('MiMo article full cybersecurity array scope changed')
    card_receipt = api['load'](BASE + 'MIMO_CARD_MD_RECEIPT_2026-10-02.json')
    card = api['load'](card_receipt['path'], 'text')
    if api['INPUTS'][card_receipt['path']] != card_receipt['sha256']:
        raise ValueError('MiMo primary mirror-card hash changed')
    card = card.split('## 3. Evaluation Results', 1)[1].split('## 4.', 1)[0]
    card_rows = [[c.strip() for c in line.strip().strip('|').split('|')]
                 for line in card.splitlines() if line.startswith('|')]
    card_models = card_rows[0][1:]
    card_labels = {'pro': 'MiMo-V2.6 Pro', 'flash': 'MiMo-V2.6 Flash',
                   'v25': 'MiMo-V2.5 Pro', 'opus': 'Claude Opus 5',
                   'sol': 'GPT-5.6 Sol', 'fable5': 'Claude Fable 5'}
    for benchmark, encoded in matches:
        values = json.loads(encoded)
        if len(values) != len(published_models):
            raise ValueError('MiMo appendix cyber array/model width differs')
        old_row = next(row for row in card_rows if row[0] == benchmark)
        for (key, model), value in zip(published_models, values):
            fragment = 'SECTIONS/Cyber/' + benchmark + '/' + key
            if value is None:
                api['exclude'](captures['MIMO26_BENCH_JS'][1]['path'] + '#' + fragment, 'Literal null: no result, not zero.')
                continue
            previous = None
            if key in card_labels:
                cell = old_row[card_models.index(card_labels[key]) + 1]
                previous = None if cell == '-' else float(cell)
                if previous == value:
                    api['exclude'](captures['MIMO26_BENCH_JS'][1]['path'] + '#' + fragment, 'Exact same model/benchmark/value already incorporated from primary MiMo card; not another trial.')
                    continue
            settings = 'Xiaomi official article appendix public source-sheet snapshot2026-09-22; complete Cyber arrays including display-hidden cells. No benchmark-specific harness, effort, attempt budget, task denominator or score unit disclosed in article. No independent comparator rerun established.'
            emit('MIMO26_BENCH_JS', model, benchmark + ' (MiMo article appendix)', value, 'score (unit not specified)', fragment, settings,
                 extra={'publicationSnapshotDate': '2026-09-22', 'rawPublicationBenchmark': benchmark,
                        'primaryCardValue': previous, 'publicationConflict': previous is not None and previous != value,
                        'displayHidden': key == 'glm' or key == 'k3'})
    return declarations
