"""Curated security aggregates only; other captured content is retained as context.

Vals: complete current Overall CyberBench leaderboard (not PoC/Patch track scores).
DeepSeek: three security benchmark rows, every literal nonmissing comparator cell.
Anthropic: literal-text capability results for exact Opus/Sonnet 5.5 only; no
chart interpolation, Mythos-to-Fable substitution, or deployed-route equivalence.
"""
import hashlib
import re

from capture_cybersecurity_sources import REFERENCES, CAPTURE_DATE

LIMITATIONS = ['Capture date is not evaluation date.', 'No catalog provider, subscription gateway, native harness or OMP route equivalence established.']
VALS_SETTINGS = 'CyberBench v1.1 Overall leaderboard; mini-swe-agent; 60 PoC and 56 patch track tasks; overall score aggregation/denominator unspecified; refusals count as failures; fallback-affected results may contribute. Per-model effort and sampling budget not disclosed by leaderboard.'
VALS_LIMITS = ['116 track tasks is not a disclosed overall-score denominator.', 'No CyberBench-specific fallback/refusal rate disclosed; model-page Vals Index fallback rates are not CyberBench rates.', 'CyberGym-inspired PoC track is not CyberGym; CVP variants are distinct publication models.']


def metadata(kind, date, settings, version=None, denominator=None, budget=None, limits=()):
    return {'resultType': kind, 'benchmarkVersion': version, 'evaluationDate': None,
            'captureDate': date, 'taskDenominator': denominator, 'attemptBudget': budget,
            'settings': settings, 'limitations': LIMITATIONS + list(limits)}


def annotate_existing(api):
    security = {'CyberGym', 'MiMo Cyber Bench', 'ExploitGym', 'ExploitBench', 'SEC Bench Pro'}
    for row in api['ROWS']:
        if row['sourceId'] == 'MIMO' and row['benchmark'] in security:
            kind = 'vendor' if row['model'].startswith('MiMo-') else 'vendor-comparator'
            row['context']['cybersecurity'] = metadata(kind, '2026-10-02',
                'Xiaomi comparative model-card evaluation table; benchmark-specific harness, effort, attempt budget and evaluation date not stated.',
                limits=['Comparator labels retain exact publication versions; no independent rerun established.'])
        elif row['benchmark'] == 'Vals CyberBench v1.1':
            row['context']['cybersecurity'] = metadata('independent', '2026-10-02', VALS_SETTINGS, 'v1.1', limits=VALS_LIMITS)
            uncertainty = row['context'].get('reportedUncertaintyPct')
            if uncertainty is not None:
                row['context']['cybersecurity']['limitations'].append(
                    f'Published accuracy uncertainty ± {uncertainty:g} percentage points; statistic/confidence level not specified by model-page table.')
        elif row['sourceId'] == 'BRIDGE' and row['benchmark'] == 'BridgeBench Security':
            row['context']['cybersecurity'] = metadata('editorial', '2026-10-02',
                'Proprietary BridgeBench editorial rating axis, not measured task success.',
                limits=['No task-success denominator or disclosed evaluation methodology; not an efficacy benchmark.'])


def extend(api):
    annotate_existing(api)
    load, context, add, exclude = (api[k] for k in ('load', 'context', 'add', 'exclude'))
    declarations = []
    page_uncertainty = {}
    for name, url in REFERENCES:
        sid = 'URL-' + hashlib.sha256(url.encode()).hexdigest()[:20]
        api['LEDGER'][sid] = {'url': url}
        receipt_path = f'evidence/supplemental/{name}_RECEIPT_{CAPTURE_DATE}.json'
        receipt = load(receipt_path)
        raw = (api['ROOT'] / receipt['path']).read_bytes()
        api['INPUTS'][receipt['path']] = hashlib.sha256(raw).hexdigest()
        if receipt['httpStatus'] != 200 or api['INPUTS'][receipt['path']] != receipt['sha256']:
            raise ValueError('Unusable exact cybersecurity capture: ' + name)
        artifacts = [receipt['path'], receipt_path]
        date = receipt['capturedAt'][:10]
        if 'textExtraction' in receipt:
            extraction = receipt['textExtraction']
            text = load(extraction['path'], 'text')
            if api['INPUTS'][extraction['path']] != extraction['sha256']:
                raise ValueError('PDF text hash mismatch: ' + name)
            artifacts.append(extraction['path'])
            locator = extraction['path']
        else:
            raw = raw.decode('utf-8')
            parser = api['Plain'](); parser.feed(raw); text = parser.text()
            locator = receipt['path']
        declarations.append({'id': sid, 'title': name.replace('_', ' '), 'url': url,
            'kind': 'benchmark', 'checked': receipt['capturedAt'],
            'limitations': 'Curated public security aggregates/context only; static captured bytes, not independent reproduction or route validation.'})
        start = len(api['ROWS'])
        reason = 'Full source retained as context; no scores inferred outside the explicitly curated security scope.'

        def emit(model, benchmark, value, unit, fragment, cyber, extra=None, effort='not stated'):
            details = {'cybersecurity': cyber, 'captureNotEvaluationDate': True}
            details.update(extra or {})
            add(sid, model, benchmark, value, unit, effort, date, locator + '#' + fragment,
                'Published aggregate from exact archived primary source; ' + cyber['settings'],
                extra=details, source=url)

        if name == 'CYBER_VALS_METHOD':
            parser = api['Tables'](); parser.feed(raw)
            table = next(t for t in parser.tables if t[0] == ['Rank', 'Model', 'Accuracy', 'Cost / Test', 'Input / Output Cost', 'Duration'])
            if len(table) != 45 or 'CyberBench v1.1' not in text:
                raise ValueError('Unexpected Vals Overall leaderboard/version; reconcile full source explicitly')
            existing = {r['model']: r for r in api['ROWS'] if r['benchmark'] == 'Vals CyberBench v1.1'}
            for rank, model, accuracy, cost, pricing, duration in table[1:]:
                value = float(accuracy.removesuffix('%'))
                fragment = 'overall-leaderboard/rank/' + rank
                if model in existing:
                    if existing[model]['value'] != value:
                        raise ValueError('Vals current model page/leaderboard conflict: ' + model)
                    exclude(locator + '#' + fragment, 'Same exact model/version/Overall observation already incorporated from immutable Vals model-page capture; not another trial.')
                    continue
                uncertainty = page_uncertainty.get(model)
                uncertainty_limits = [f'Published model-page accuracy uncertainty ± {uncertainty["uncertainty"]:g} percentage points; statistic/confidence level not specified by table; archived locator {uncertainty["locator"]}.'] if uncertainty else ['Overall leaderboard does not publish an uncertainty interval for this model in its table.']
                if uncertainty and uncertainty['score'] != value:
                    raise ValueError('Vals exact-model uncertainty page/Overall score conflict: ' + model)
                emit(model, 'Vals CyberBench v1.1', value, '%', fragment,
                     metadata('independent', date, VALS_SETTINGS, 'v1.1', limits=VALS_LIMITS + uncertainty_limits),
                     {'leaderboardRank': int(rank), 'leaderboardModels': 44,
                      'costPerTestUSD': float(cost.removeprefix('$')), 'inputOutputPriceDisplay': pricing,
                      'durationDisplay': duration, 'leaderboardUpdatedDate': '2026-10-01'})
            reason = 'Complete 44-model Overall CyberBench v1.1 leaderboard: 42 new observations, two exact Opus/Sonnet5.5 overlaps explicitly excluded. Cost/duration metadata not budgets; PoC/Patch tracks not scored separately.'
        elif name == 'CYBER_DEEPSEEK':
            parser = api['Tables'](); parser.feed(raw)
            table = next(t for t in parser.tables if 'DS-V4.1-Flash' in t[0])
            for ri, row in enumerate(table[1:], 1):
                if row[0] not in {'CyberGym (Pass@1)', 'SEC-Bench Pro (Pass@1)', 'ExploitGym (Pass@1)'}:
                    continue
                for ci, model in enumerate(table[0][1:], 1):
                    fragment = f'instruct-comparison/row/{ri}/column/{ci}'
                    if row[ci] == '—':
                        exclude(locator + '#' + fragment, 'Publisher dash: no numeric result; never zero.')
                        continue
                    target = model == 'DS-V4.1-Flash'
                    setup = ('DeepSeek-V4.1-Flash instruct evaluation; maximum reasoning_effort=100, temperature=1.0, top_p=0.95; Pass@1. '
                             if target else 'Publisher instruct-comparison table heading: maximum reasoning effort; comparator native effort value, temperature and top_p not stated. DeepSeek-V4.1-Flash settings (reasoning_effort=100, temperature=1.0, top_p=0.95) are not established for this comparator. Pass@1. ')
                    harness = ('DeepSeek-V4.1-Flash SEC-Bench Pro uses Claude Code harness.'
                               if target and row[0].startswith('SEC-') else
                               'Cyber-specific harness not stated for this publication model/benchmark cell; DeepSeek target SEC harness not transferred to comparators.')
                    emit(model, row[0], float(row[ci]), '%', fragment,
                         metadata('vendor' if target else 'vendor-comparator', date,
                                  setup + harness, limits=['Vendor-reported comparators, not independent reruns.', 'No cyber task denominator/attempt limit supplied; Terminal-Bench/DeepSWE sample and step settings not transferred.']),
                         {'publicationHeader': model}, effort='maximum (reasoning_effort=100)' if target else 'maximum (table heading; native value not stated)')
            reason = 'All 16 literal nonmissing cells from the three curated security rows of the instruct comparison; five missing cells explicitly excluded. Other benchmark tables remain context.'
        elif name in {'CYBER_ANTH_OPUS55', 'CYBER_ANTH_SONNET55'}:
            flat = ' '.join(text.split())
            opus = name == 'CYBER_ANTH_OPUS55'
            model = 'Claude Opus 5.5' if opus else 'Claude Sonnet 5.5'
            section = '3.3' if opus else '3.2'
            setup = 'Anthropic capability evaluation with cyber safeguards off; escape classifiers and other safety measures remain enabled. Not deployed conditions. '
            def literal(pattern):
                match = re.search(pattern, flat)
                if not match:
                    raise ValueError('Missing literal system-card result: ' + name + ': ' + pattern)
                return match
            exp = metadata('vendor', date, setup + 'ExploitBench author static uniform harness; 41 V8 environments, five trials/environment/arm; plain and AutoNudge arms. Cap% averages per-environment flag coverage over three randomly chosen trials of five, not task success.',
                           denominator=205, budget='300 turns per arm', limits=['Mean flags, Cap%, and combined full ACE count/rate are different metrics; do not aggregate arms as independent benchmark scores.'])
            if opus:
                m = literal(r'scored a mean of ([\d.]+) capability flags, for a Cap% of ([\d.]+)%.*?plain arm\. In the AutoNudge arm, it averaged ([\d.]+) flags, for a Cap% of ([\d.]+)%')
                arms = [('plain', float(m[1]), float(m[2])), ('AutoNudge', float(m[3]), float(m[4]))]
                ace = literal(r'full arbitrary code execution ([\d.]+)% of the time \((\d+)/(\d+)\)')
            else:
                m = literal(r'In the AutoNudge arm, Claude Sonnet 5\.5 averaged ([\d.]+) flags, for a Cap% of ([\d.]+)%')
                arms = [('AutoNudge', float(m[1]), float(m[2]))]
                ace = literal(r'([\d.]+)% of the time \((\d+) out of (\d+) runs\)')
            for arm, mean, cap in arms:
                emit(model, 'ExploitBench mean capability flags (' + arm + ')', mean, 'flags/trial', section + '.1/' + arm + '/mean', exp, {'arm': arm})
                emit(model, 'ExploitBench Cap% (' + arm + ')', cap, '%', section + '.1/' + arm + '/cap', dict(exp, taskDenominator=41), {'arm': arm})
            both = dict(exp, taskDenominator=int(ace[3]))
            emit(model, 'ExploitBench full ACE (combined arms)', int(ace[2]), 'successful runs', section + '.1/combined/ACE-count', both, {'arm': 'plain + AutoNudge'})
            emit(model, 'ExploitBench full ACE rate (combined arms)', float(ace[1]), '%', section + '.1/combined/ACE-rate', both, {'arm': 'plain + AutoNudge', 'successCount': int(ace[2])})
            scenario = literal(re.escape(model) + r' completed ([\d.]+)% of all challenges')
            emit(model, 'CyScenarioBench overall solve rate (10-challenge subset)', float(scenario[1]), '%', section + '.2/overall', metadata('vendor', date, setup + 'Private named 10-challenge subset; mean solve rate across challenges, not a single-trial count fraction.', denominator=10))
            binary = literal(re.escape(model) + r' produced (\d+) control-flow hijacks')
            emit(model, 'Binary Exploitation Benchmark control-flow hijacks', int(binary[1]), 'control-flow hijacks', section + '.3/hijacks', metadata('vendor', date, setup + '831 entrypoints across 228 OSS-Fuzz projects; rewritten harness since August 2026.', denominator=831, limits=['Rewritten-harness scores not comparable to earlier system cards.']))
            if opus:
                gym = literal(r'successfully exploit (\d+) and (\d+) of the (\d+) cases.*?2 hours and 6 hours respectively')
                for hours, count in [(2, gym[1]), (6, gym[2])]:
                    emit(model, f'ExploitGym successful cases ({hours} hours)', int(count), 'successful cases', section + f'.4/{hours}h/successes', metadata('vendor', date, setup + 'All standard mitigations disabled; intended-vulnerability secret-flag success verified by agent judge.', denominator=int(gym[3]), budget=f'{hours} hours wall-clock'))
            reason = 'Exact-model literal cybersecurity capability aggregates only; comparator prose/chart bars remain context. No chart bar inferred; Sonnet plain-arm and ExploitGym numbers unavailable in literal text.'
        elif name == 'CYBER_ANTH_FABLE51':
            if 'we do not report' not in text.lower():
                raise ValueError('Fable withheld-results statement absent')
            reason = 'Fable5.1 cyber capability evaluations withheld because safeguards consistently trigger fallback to Opus4.8. Shared-card Mythos5.1 capability results are not Fable results. No score row emitted.'
            context(sid, locator + '#3.2/withheld-capability-results',
                    {'publishedModel': 'Claude Fable 5.1', 'recordType': 'withheld-capability-evaluation',
                     'captureDate': date, 'evaluationDate': None, 'score': None,
                     'fallbackModel': 'Claude Opus 4.8', 'underlyingModel': 'Claude Mythos 5.1',
                     'limitations': LIMITATIONS + ['Shared underlying weights do not equate Fable safeguards with Mythos capability evaluations.']},
                    reason, date)
        elif name.startswith('CYBER_OPENAI_'):
            if 'Critical' not in text:
                raise ValueError('OpenAI cybersecurity risk assessment absent')
            reason = 'Official OpenAI Critical cybersecurity risk/capability assessment; nonnumeric Preparedness classification, not a common benchmark score. Sol6.1 uses Astra safeguards; no CyberBench/CyberGym score invented.'
            context(sid, locator + '#preparedness/cybersecurity-assessment',
                    {'publishedModel': 'GPT-6.1 Sol' if name.endswith('SOL61') else 'GPT-6 Astra',
                     'recordType': 'vendor-risk-assessment', 'riskClassification': 'Critical',
                     'captureDate': date, 'evaluationDate': None, 'score': None,
                     'framework': 'OpenAI Preparedness Framework', 'limitations': LIMITATIONS},
                    reason, date)
            from supplemental_openai_cybersecurity import ingest
            reason = ingest(api, name, raw, text, locator, date, emit, metadata)
        else:
            reason = 'Exact Vals model page archived as context; numeric CyberBench observation owned by complete Overall leaderboard, never scored again here. Other benchmarks outside curated extension scope.'
            model = {'CYBER_VALS_SOL61': 'GPT-6.1 Sol', 'CYBER_VALS_LUNA': 'GPT-6 Luna',
                     'CYBER_VALS_ASTRA': 'GPT-6 Astra', 'CYBER_VALS_SOL56': 'GPT-5.6 Sol',
                     'CYBER_VALS_FABLE51': 'Claude Fable 5.1'}[name]
            uncertainty = re.search(r'CyberBench v1\.1\s+([\d.]+)\s*%\s*±\s*([\d.]+)', text)
            if not uncertainty:
                raise ValueError('Missing exact model-page CyberBench uncertainty: ' + name)
            page_uncertainty[model] = {'score': float(uncertainty[1]), 'uncertainty': float(uncertainty[2]),
                                       'locator': locator + '#current-benchmark-table/CyberBench v1.1'}
        context(sid, locator + '#full-source-context', text, reason, date)
        added = len(api['ROWS']) - start
        api['RESULTS'].append({'sourceId': sid, 'status': 'included' if added else 'context-only',
            'checked': receipt['capturedAt'], 'httpStatus': receipt['httpStatus'], 'benchmarkCount': added,
            'reason': reason, 'artifacts': artifacts})
    return declarations
