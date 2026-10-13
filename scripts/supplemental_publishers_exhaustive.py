"""Static publisher aggregates for exact catalog versions; no benchmark execution.

CyberGym submission protocols are separate agent experiments, not model-route
calibration. Older publication versions remain inventoried in reconciliation.
"""
import hashlib
import json
import re
from decimal import Decimal

CAPTURE_DATE = '2026-10-03'
PREFIX = 'evidence/supplemental/'
REFERENCES = [
    ('EXHAUST_PUBLISHER_' + name, 'https://www.cybergym.io/' + route)
    for name, route in [
        ('OBSERVATORY', ''), ('CYBERGYM', 'cybergym/'),
        ('EXPLOITGYM', 'exploitgym/'), ('CYBERGYM_E2E', 'cybergym-e2e/'),
        ('CYBERGYM_DATA', 'assets/data/cybergym.json'),
        ('EXPLOITGYM_DATA', 'assets/data/exploitgym.json'),
        ('CYBERGYM_E2E_DATA', 'assets/data/cybergym-e2e.json')]
] + [
    ('EXHAUST_PUBLISHER_CYBERGYM_E2E_PAPER', 'https://arxiv.org/pdf/2606.04460'),
    ('EXHAUST_PUBLISHER_SEC_ORIGINAL_PAPER', 'https://arxiv.org/pdf/2506.11791'),
    ('EXHAUST_PUBLISHER_CYBERGYM_BLOG', 'https://rdi.berkeley.edu/blog/cybergym/'),
    ('EXHAUST_PUBLISHER_EXPLOITGYM_BLOG', 'https://rdi.berkeley.edu/blog/exploitgym/'),
    ('EXHAUST_PUBLISHER_CYBERGYM_E2E_BLOG', 'https://rdi.berkeley.edu/blog/cybergym-e2e/'),
    ('EXHAUST_FRONTIER_PUBLISHER_SECBENCH', 'https://sec-bench.github.io/'),
    ('EXHAUST_FRONTIER_PUBLISHER_SECBENCH_V8', 'https://sec-bench.github.io/v8'),
    ('EXHAUST_FRONTIER_PUBLISHER_EXPLOITBENCH', 'https://exploitbench.ai/'),
    ('EXHAUST_FRONTIER_PUBLISHER_EXPLOITBENCH_ABS', 'https://arxiv.org/abs/2605.14153'),
    ('EXHAUST_FRONTIER_PUBLISHER_EXPLOITGYM_GITHUB', 'https://github.com/sunblaze-ucb/exploitgym'),
    ('EXHAUST_PUBLISHER_DARKNAVY', 'https://deepsec.darknavy.net/blog/cybergym'),
    ('EXHAUST_PUBLISHER_DARKNAVY_BUNDLE', 'https://deepsec.darknavy.net/assets/index-DlmFO-DO.js'),
    ('EXHAUST_PUBLISHER_NSFOCUS', 'https://nsfocusglobal.com/nsfocus-ai-cybergym-level-1-technical-report/'),
    ('EXHAUST_PUBLISHER_ALIPAY', 'https://github.com/Alipay-Risk-Tech/CyberGym-Writeup'),
    ('EXHAUST_PUBLISHER_ALIPAY_REPORT', 'https://raw.githubusercontent.com/Alipay-Risk-Tech/CyberGym-Writeup/main/WRITEUP-20260906.md'),
    ('EXHAUST_PUBLISHER_SANGFOR', 'https://github.com/Sangfor-AI/cybergym-submission-sangfor-ai-v2'),
    ('EXHAUST_PUBLISHER_SANGFOR_REPORT', 'https://raw.githubusercontent.com/Sangfor-AI/cybergym-submission-sangfor-ai-v2/main/README.md'),
]
LIMITATIONS = [
    'Static publisher-reported aggregates; no independent reproduction performed.',
    'Capture date is not evaluation date; submission date is retained separately.',
    'No catalog gateway, native harness or OMP route equivalence established.',
]


def contribute(api):
    declarations = []
    for name, url in REFERENCES:
        sid = 'URL-' + hashlib.sha256(url.encode()).hexdigest()[:20]
        receipt_path = PREFIX + name + '_RECEIPT_' + CAPTURE_DATE + '.json'
        receipt = api['load'](receipt_path)
        if receipt['requestedUrl'] != url:
            raise ValueError('Publisher receipt URL mismatch: ' + name)
        raw = (api['ROOT'] / receipt['path']).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != receipt['sha256']:
            raise ValueError('Publisher capture hash mismatch: ' + name)
        api['INPUTS'][receipt['path']] = digest
        artifacts = [receipt['path'], receipt_path]
        locator = receipt['path']
        text = raw.decode('utf-8', errors='replace')
        if 'textExtraction' in receipt:
            extraction = receipt['textExtraction']
            text = api['load'](extraction['path'], 'text')
            if api['INPUTS'][extraction['path']] != extraction['sha256']:
                raise ValueError('Publisher extraction hash mismatch: ' + name)
            artifacts.append(extraction['path'])
            locator = extraction['path']
        api['LEDGER'][sid] = {'url': url}
        date = receipt['capturedAt'][:10]
        declarations.append({'id': sid, 'title': name.replace('_', ' '), 'url': url,
            'kind': 'benchmark', 'checked': receipt['capturedAt'],
            'limitations': 'Static public aggregate/report only; exact publication versions; no route calibration or benchmark execution.'})
        start = len(api['ROWS'])

        def emit(model, benchmark, value, unit, fragment, settings, denominator, budget, version, extra, effort='not stated'):
            cyber = {'resultType': 'independent', 'benchmarkVersion': version,
                'evaluationDate': None, 'captureDate': date, 'taskDenominator': denominator,
                'attemptBudget': budget, 'settings': settings, 'limitations': list(LIMITATIONS)}
            if name == 'EXHAUST_PUBLISHER_CYBERGYM_DATA':
                cyber['limitations'].append('Measures the named submitted agent-system, not standalone GLM-5.3 base-model ability or any Gentle-assess route; never pooled with vendor single-model scores.')
            if 'CyberGym' in benchmark:
                cyber['limitations'].append('Named agent-system experiment, not standalone base-model efficacy; report mirrors are not additional trials.')
            if 'Alipay' in settings:
                cyber['limitations'].append('Unresolved quality-score conflict: primary report1460/1507=96.88% versus publisher leaderboard96.75%; no separate trial established. Efficiency averages do not resolve this discrepancy.')
            if 'DoGNAVY' in settings:
                cyber['limitations'].append('Cited primary report currently describes GLM-5.2 July29 evaluation90.84%, not this GLM-5.3 leaderboard94.96%; updated exact-version corroboration unresolved.')
            if 'NSFOCUS' in settings:
                cyber['limitations'].append('Publisher submission date precedes its stated model release date; dates retained verbatim, not repaired.')
            api['add'](sid, model, benchmark, value, unit, effort, date,
                locator + '#' + fragment, settings, extra={'cybersecurity': cyber,
                'publisherSubmission': extra, 'captureNotEvaluationDate': True}, source=url)

        if receipt['httpStatus'] == 200 and name == 'EXHAUST_PUBLISHER_CYBERGYM_DATA':
            data = json.loads(raw)
            for index, row in enumerate(data['level1']):
                if row['model'] != 'GLM-5.3' or row.get('focus') != 'agent':
                    continue
                if row['agent'] not in {'DoGNAVY', 'NSFOCUS AI', 'Alipay AI4SDL', 'Sangfor AI'}:
                    raise ValueError('Unreconciled exact GLM-5.3 publisher submission')
                settings = ('CyberGym Level 1 vulnerability reproduction; team-submitted ' + row['agent']
                    + '; trials=' + str(row['trials']) + '; features=' + ', '.join(row.get('features', []))
                    + '. Dynamic sanitized vulnerable image/binary access differs from static vendor protocols. '
                    + 'Success when any disclosed trial reproduces the intended vulnerability.')
                emit('GLM-5.3', 'CyberGym Level 1 ' + row['agent'] + ' success rate',
                    float(Decimal(str(row['score_10'])) * 100), '%', '/level1/' + str(index) + '/score_10',
                    settings, 1507, str(row['trials']) + ' trial per instance', 'Level 1', row)
        elif receipt['httpStatus'] == 200 and name == 'EXHAUST_PUBLISHER_EXPLOITGYM_DATA':
            data = json.loads(raw)
            row = data['results'][0]
            if row['model'] != 'GPT-5.6 Sol (reasoning max)' or data['instances'] != {'total': 869, 'userspace': 502, 'v8': 181, 'kernel': 186}:
                raise ValueError('Unreconciled ExploitGym exact-model dataset')
            variants = [('/results/0', row)] + [('/results/0/subRows/' + str(i), dict(row, **sub)) for i, sub in enumerate(row.get('subRows', []))]
            for fragment, variant in variants:
                budget = variant['eval_note']
                settings = ('ExploitGym v1; OpenAI & ExploitGym Team; Codex CLI; maximum reasoning; '
                    + budget + '; trusted security research access; intended-vulnerability exploitation, '
                    + 'userspace/V8/kernel domain counts. Mitigated counts are separately evaluated with defenses enabled. '
                    + 'Per-task resource averages over all tasks and successful exploits are distinct populations.')
                for field in ('userspace', 'v8', 'kernel', 'on_target'):
                    denominator = 869 if field == 'on_target' else data['instances'][field]
                    emit('GPT-5.6 Sol', 'ExploitGym v1 ' + budget + ' ' + field + ' intended successes',
                        variant[field], 'instances', fragment + '/' + field, settings, denominator,
                        budget, 'v1', variant, 'maximum')
                for field, value in variant['mitigated'].items():
                    emit('GPT-5.6 Sol', 'ExploitGym v1 ' + budget + ' mitigated ' + field + ' intended successes',
                        value, 'instances', fragment + '/mitigated/' + field, settings, data['instances'][field],
                        budget, 'v1', variant, 'maximum')
                units = {'cost': 'USD/task', 'out_tokens': 'tokens/task', 'time_min': 'minutes/task', 'llm_calls': 'calls/task'}
                for population in ('metrics', 'metrics_success'):
                    for field, value in variant[population].items():
                        if value is None:
                            api['exclude'](locator + '#' + fragment + '/' + population + '/' + field, 'Publisher null, not zero.')
                            continue
                        emit('GPT-5.6 Sol', 'ExploitGym v1 ' + budget + ' ' + population + ' ' + field,
                            value, units[field], fragment + '/' + population + '/' + field, settings,
                            869 if population == 'metrics' else variant['on_target'], budget, 'v1', variant, 'maximum')
        elif receipt['httpStatus'] == 200 and name == 'EXHAUST_PUBLISHER_NSFOCUS':
            parser = api['Tables']()
            parser.feed(text)
            table = next(t for t in parser.tables if len(t) == 4 and t[-1] == ['OSS-Fuzz', '139', '3', '2', '134'])
            if table[1:] != [['CyberGym Level 1 Overall', '1507', '46', '29', '1432'], ['ARVO', '1368', '43', '27', '1298'], ['OSS-Fuzz', '139', '3', '2', '134']]:
                raise ValueError('NSFOCUS exact GLM-5.3 aggregate table mismatch')
            settings = 'CyberGym Level1 NSFOCUS AI with GLM-5.3; strict final Pass@1; full1507 tasks; dynamic isolated vulnerable image; no cross-task memory or patched-image access;270-minute default per-task limit. Default configuration is not observed per-task duration.'
            for index, cells in enumerate(table[1:], 1):
                subset, denominator, both, absent, solved = cells
                for label, value in [('both-revisions-crash', both), ('no-valid-final-PoC', absent), ('final-successes', solved)]:
                    emit('GLM-5.3', 'CyberGym Level 1 NSFOCUS AI ' + subset + ' ' + label,
                        int(value), 'instances', 'Table-4/row/' + str(index) + '/' + label,
                        settings, int(denominator), '1 final submission;270-minute default limit', 'Level 1', {'subset': subset})
            for subset, value, denominator in [('ARVO', 94.88, 1368), ('OSS-Fuzz', 96.40, 139)]:
                emit('GLM-5.3', 'CyberGym Level 1 NSFOCUS AI ' + subset + ' success rate',
                    value, '%', '5.2-GLM-5.3-results/' + subset, settings, denominator,
                    '1 final submission;270-minute default limit', 'Level 1', {'subset': subset})
            api['exclude'](locator + '#5.2-overall-95.02', 'Same NSFOCUS AI GLM-5.3 overall rate already incorporated from publisher leaderboard; not another trial.')
        elif receipt['httpStatus'] == 200 and name == 'EXHAUST_PUBLISHER_SANGFOR_REPORT':
            current = text.split('## Previous DeepSeek')[0]
            if 'GLM-5.3' not in current or '480 minutes' not in current:
                raise ValueError('Sangfor exact-model protocol changed')
            settings = 'CyberGym Level1 Sangfor AI GLM-5.3 Agent Swarm; official task-specific vulnerable images; single designated final submission;480-minute limit; all other settings stated unchanged from earlier250-minute DeepSeek run, not a controlled ablation.'
            matches = re.findall(r'\|\s*(ARVO|OSS-Fuzz|\*\*Total\*\*)\s*\|\s*\**([\d,]+)\**\s*\|\s*\**([\d,]+)\**\s*\|\s*\**([\d.]+)%', current)
            if len(matches) != 3:
                raise ValueError('Sangfor aggregate source table missing')
            for subset, denominator, solved, rate in matches:
                subset = subset.replace('*', '')
                denominator = int(denominator.replace(',', ''))
                emit('GLM-5.3', 'CyberGym Level 1 Sangfor AI ' + subset + ' final successes',
                    int(solved.replace(',', '')), 'instances', 'GLM-5.3-Result/' + subset + '/confirmed',
                    settings, denominator, '1 final submission;480-minute limit', 'Level 1', {'subset': subset})
                if subset != 'Total':
                    emit('GLM-5.3', 'CyberGym Level 1 Sangfor AI ' + subset + ' success rate',
                        float(rate), '%', 'GLM-5.3-Result/' + subset + '/success-rate',
                        settings, denominator, '1 final submission;480-minute limit', 'Level 1', {'subset': subset})
            api['exclude'](locator + '#GLM-5.3-Result/Total/success-rate', 'Same Sangfor AI97.21% submission already incorporated from publisher leaderboard; not another trial.')
        elif receipt['httpStatus'] == 200 and name == 'EXHAUST_PUBLISHER_ALIPAY_REPORT':
            if '| Model | GLM-5.3 |' not in text or '1,460' not in text:
                raise ValueError('Alipay exact-model submission report changed')
            efficiency = text.split('## Efficiency')[1].split('## Reproducibility')[0]
            settings = 'CyberGym Level1 Alipay AI4SDL GLM-5.3; LangGraph agent; full1507-task final-submission run; dynamic isolated containers; no general web access; AppleSilicon Linuxamd64 under QEMU; all-task resource accounting averages, not quality or budgets.'
            units = {'Non-cached input tokens': 'tokens/task', 'Cache-read tokens': 'tokens/task',
                'Cache-creation tokens': 'tokens/task', 'Output tokens': 'tokens/task',
                'Model requests': 'calls/task', 'Wall-clock time': 'seconds/task'}
            for label, unit in units.items():
                match = re.search(r'\|\s*' + re.escape(label) + r'\s*\|\s*([\d,]+)(?: seconds)?\s*\|', efficiency)
                if not match:
                    raise ValueError('Alipay efficiency aggregate missing: ' + label)
                emit('GLM-5.3', 'CyberGym Level 1 Alipay AI4SDL mean ' + label,
                    int(match[1].replace(',', '')), unit, 'Efficiency/' + label,
                    settings, 1507, '1 final submission;time budget not stated', 'Level 1', {'population': 'all tasks'})
            api['exclude'](locator + '#Results', 'Primary report96.88% conflicts with leaderboard96.75% for same dated submission; no separate trial established. Quality result unresolved, never pooled or silently replaced.')
        reason = ('Exact-model independent aggregate components incorporated; all other metrics/versions inventoried by reconciliation manifest.'
            if len(api['ROWS']) > start else 'Context/exclusions inventoried by reconciliation manifest; no numeric version inheritance.')
        if receipt['httpStatus'] != 200:
            reason = 'HTTP blocked/inaccessible; unresolved, no numeric observations emitted.'
        api['context'](sid, locator + '#publisher-report-context', text, reason, date)
        api['RESULTS'].append({'sourceId': sid, 'status': 'included' if len(api['ROWS']) > start else 'context-only',
            'checked': receipt['capturedAt'], 'httpStatus': receipt['httpStatus'],
            'benchmarkCount': len(api['ROWS']) - start, 'reason': reason, 'artifacts': artifacts})
    return declarations
