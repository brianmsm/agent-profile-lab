#!/usr/bin/env python3
"""Normalize the archived Claude sweep; never fetch or infer missing results."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / 'evidence/anthropic/CLAUDE_BENCHMARKS_SWEEP_2026-09-30.md'
PLANS = ROOT / 'evidence/anthropic/CLAUDE_PLANS_EVIDENCE_2026-09-30.json'
OUTPUT = ROOT / 'evidence/anthropic/CLAUDE_DASHBOARD_OBSERVATIONS_2026-10-02.json'
MODELS = ('Opus 5.5', 'Sonnet 5.5', 'Fable 5.1')
NUMBER = r'([~≈]?)\s*(\d+(?:\.\d+)?)'


def relative(path):
    return path.relative_to(ROOT).as_posix()


def normalize():
    lines = SWEEP.read_text(encoding='utf-8').splitlines()
    plans = json.loads(PLANS.read_text(encoding='utf-8'))
    benchmarks, observations = [], []
    path = relative(SWEEP)

    def record(locator, disposition, reason, raw, count=1):
        observations.append(dict(locator=locator, disposition=disposition,
                                 reason=reason, rawText=raw, count=count))

    def add(model_index, label, value, unit, effort, source_label, lineno, raw,
            approximate=False, detail=''):
        locator = f'{path}:L{lineno}:{MODELS[model_index]}'
        method = source_label if source_label != 'no declarado' else ''
        if detail:
            method = '; '.join(filter(None, (method, detail)))
        benchmarks.append({
            'model': f'Claude {MODELS[model_index]}', 'family': 'Claude 5',
            'benchmark': label, 'value': float(value), 'unit': unit,
            'effort': effort, 'source': path, 'date': '2026-09-30',
            'provenance': f'{path}:L{lineno}; fuente indicada en sweep: {source_label}',
            'methodology': method,
            'note': (f'Texto original: {raw}. Modelo: {MODELS[model_index]}. '
                     f'Fuente indicada en sweep: {source_label}. '
                     'Evidencia local secundaria; URL primaria específica no vinculada ni verificada.'
                     + (' El valor se publicó como aproximado.' if approximate else '')),
            'context': {'source_label': source_label, 'sourceRole': 'local-sweep',
                        'primaryVerified': False, 'locator': locator, 'rawText': raw,
                        'approximate': approximate, 'metricAndHarness': label,
                        'methodDetail': detail},
        })
        record(locator, 'included', 'Explicit attributable score; primary source not verified', raw)

    numeric_cells = 0
    for lineno, line in enumerate(lines, 1):
        if not line.startswith('|'):
            continue
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if len(cells) < 4 or cells[0] == 'Benchmark' or cells[0].startswith('---'):
            continue
        label = cells[0]
        source_label = cells[4] if len(cells) > 4 else 'OpenRouter'
        effort_match = re.search(r'\b(max|xhigh|high|medium|low)\b', label)
        effort = effort_match.group(1) if effort_match else 'no declarado'
        for index, cell in enumerate(cells[1:4]):
            locator = f'{path}:L{lineno}:{MODELS[index]}'
            first = re.match(NUMBER + r'\s*(%)?', cell)
            if not first:
                record(locator, 'excluded', 'Absent/unverified current-generation score; embedded older-generation values are not current results', cell)
                continue
            numeric_cells += 1
            unit = '%' if first.group(3) else ('Elo' if 'Elo' in label else 'unidad no declarada')
            if label.startswith('ARC-AGI-1 / -2'):
                pair = re.fullmatch(NUMBER + r'%\s*/\s*' + NUMBER + r'%', cell)
                if pair is None:
                    raise ValueError(f'Unrecognized ARC pair: {locator}')
                for version, offset in ((1, 1), (2, 3)):
                    add(index, f'ARC-AGI-{version} (high)', pair.group(offset + 1), '%', effort,
                        source_label, lineno, cell, bool(pair.group(offset)))
            else:
                detail = ''
                if lineno == 14:
                    detail = ('Fable vendor 41.7%, as explicitly distinguished in source column'
                              if index == 2 else 'BenchLM system-card mirror; strict binary metric')
                add(index, label, first.group(2), unit, effort, source_label, lineno, cell,
                    bool(first.group(1)), detail)
                old_elo = re.search(r'\bv2:\s*(\d+(?:\.\d+)?)', cell)
                if old_elo:
                    add(index, 'GDPval-AA v2', old_elo.group(1), 'Elo', effort,
                        source_label, lineno, cell, detail='v2 separated from v2.1')
            # Parenthesized rankings and foreign-model comparisons are not scores for this model.
            parenthetical = re.search(r'\(([^)]*)\)', cell)
            if parenthetical and ('#' in parenthetical.group(0) or 'Astra' in parenthetical.group(0)):
                record(locator + ':annotation', 'context', 'Ranking annotation, not an additional current-model score', parenthetical.group(0))
            if parenthetical and 'Astra' in parenthetical.group(0):
                comparison = re.search(r'Astra\s+(\d+(?:\.\d+)?)%', parenthetical.group(0))
                if comparison:
                    record(locator + ':foreign-score', 'excluded', 'Cross-family comparison owned by OpenAI dataset, not Claude', comparison.group(0))

    # Each narrative is checked against its archived line, with explicit model/effort binding.
    def narrative(lineno, model, label, token, effort='no declarado', source='no declarado', detail=''):
        raw = lines[lineno - 1]
        if token not in raw:
            raise ValueError(f'Narrative changed at L{lineno}: missing {token}')
        add(model, label, float(token.rstrip('%')), '%', effort, source, lineno, raw, detail=detail)

    for index, value, effort in ((0, '66.4%', 'xhigh'), (1, '70.6%', 'max'), (2, '55.8%', 'no declarado')):
        narrative(55, index, 'Terminal-Bench 4.0 (vendor)', value, effort, 'vendor', 'Vendor harness unspecified; not AA or Vals harness')
    for label, source, values in (
        ('Terminal-Bench 4.0 (AA)', 'AA', ('59.6', '63.6', '52.0')),
        ('Terminal-Bench 4.0 (Vals)', 'Vals', ('61.62', '53.03', '58.08')),
        ('Terminal-Bench 2.1 (Vals)', 'Vals', ('87.64', '83.15', '85.02')),
    ):
        for index, value in enumerate(values):
            narrative(55, index, label, value, source=source, detail='Triplet order Opus/Sonnet/Fable; harness unspecified')
    for index, value in enumerate(('89.9%', '81.3%', '81.2%')):
        narrative(56, index, 'SWE-bench Pro', value)
    narrative(57, 0, 'FrontierCode', '54.4%', 'max')
    narrative(57, 1, 'FrontierCode', '52.1%', 'xhigh')
    narrative(57, 1, 'FrontierCode (code-review penalized)', '46.2%', 'max',
              detail='Code-review out-of-scope penalty explicitly reported; not main-task harness equivalent')
    for index, value, effort in ((0, '57.8%', 'no declarado'), (1, '55.5%', 'low'), (2, '51.8%', 'no declarado')):
        narrative(58, index, 'CursorBench 4.0', value, effort)
    for index, value in enumerate(('66.9', '61.0', '63.1')):
        narrative(59, index, 'AA-SciCode', value, source='AA', detail='Triplet order Opus/Sonnet/Fable')
    for index in range(3):
        narrative(60, index, 'Toolathlon-Verified', '77.8%')
    for index, value in enumerate(('58', '56', '53')):
        raw = lines[60]
        if not re.search(r'\b' + value + r'\b', raw):
            raise ValueError('Changed index narrative')
        add(index, 'AA Intelligence Index v4.3.2', value, 'index', 'no declarado', 'AA', 61, raw)

    for lineno, reason in (
        (20, 'Vendor/strict ranges repeat tables; GPT comparison belongs to OpenAI owner, metric explicitly uncertain'),
        (27, 'Astra 68.1% comparison is not Opus score; belongs to OpenAI owner'),
        (31, 'Astra 31.0% comparison belongs to OpenAI owner'),
        (51, 'Opus 5 90.8% is older generation absent from current columns'),
        (77, 'Repeated AutomationBench 71.3%, OSWorld 80.1%-81.8%; routing conclusions are context'),
        (78, 'Repeated Opus 63.3%; Astra 68.1% belongs to OpenAI owner; ~5pp is a comparison, not score'),
        (79, 'Repeated GDPval 1846/1844 and normalized 67.3/67.2, not additional measurements'),
    ):
        record(f'{path}:L{lineno}:narrative-context', 'context', reason, lines[lineno - 1])
    for lineno, token, reason in (
        (20, '72.6%', 'Cross-family Astra comparison: uncertain metric; OpenAI dataset ownership'),
        (20, '60.8%', 'Cross-family GPT-5.6 Sol comparison: OpenAI dataset ownership'),
        (57, '54.6%', 'Prior Opus observation superseded by 54.4%; no version/harness established'),
        (78, '68.1%', 'Repeated cross-family Astra comparison: OpenAI dataset ownership'),
    ):
        record(f'{path}:L{lineno}:{token}:excluded', 'excluded', reason, token)
    for lineno in range(65, 74):
        record(f'{path}:L{lineno}:absence', 'context',
               'Explicit coverage absence; not a numerical benchmark observation', lines[lineno - 1])

    plan_observations = []
    for group, scores in plans['benchmarks_by_domain']['coding_agentic'].items():
        for key, value in scores.items():
            plan_observations.append({
                'locator': f'{relative(PLANS)}#/benchmarks_by_domain/coding_agentic/{group}/{key}',
                'disposition': 'excluded', 'count': 1, 'rawText': value,
                'reason': ('Cross-family OpenAI observation: owned by OpenAI dataset, not Claude' if group == 'comparison_GPT'
                           else 'Superseded plan benchmark summary; sweep authoritative for this dataset, no duplicate scores'),
            })
    for key in ('plans', 'models', 'key_differentiator'):
        plan_observations.append({
            'locator': f'{relative(PLANS)}#/{key}', 'disposition': 'context', 'count': 1,
            'rawText': json.dumps(plans[key], ensure_ascii=False),
            'reason': 'Subscription/model contract metadata; not benchmark scores',
        })
    artifacts = []
    for input_path, items, kind in ((SWEEP, observations, 'benchmark-sweep'),
                                    (PLANS, plan_observations, 'superseded-summary')):
        included = sum(item['count'] for item in items if item['disposition'] == 'included')
        excluded = sum(item['count'] for item in items if item['disposition'] == 'excluded')
        context = sum(item['count'] for item in items if item['disposition'] == 'context')
        artifacts.append({
            'path': relative(input_path), 'sha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
            'kind': kind, 'observed': included + excluded + context,
            'included': included, 'excluded': excluded, 'context': context,
            'exclusions': [{k: item[k] for k in ('locator', 'reason', 'count')}
                           for item in items if item['disposition'] == 'excluded'],
            'observations': items,
        })
    return {
        'schemaVersion': 1, 'benchmarks': benchmarks,
        'inputs': [{k: artifact[k] for k in ('path', 'sha256')} for artifact in artifacts],
        'reconciliation': {
            'artifacts': artifacts, 'numericTableCells': numeric_cells,
            'tableScoreCount': sum(1 for row in benchmarks if ':L' in row['provenance'] and int(row['provenance'].split(':L')[1].split(';')[0]) < 53),
            'narrativeScoreCount': sum(1 for row in benchmarks if int(row['provenance'].split(':L')[1].split(';')[0]) >= 53),
            'notes': [
                'Scores are attributed to the archived local sweep, not verified primary publications. Source labels do not establish equivalent harnesses.',
                'Observed counts use atomic attributable scores (ARC pairs and Elo versions separate), absent table cells and context annotations; numeric table cells also reported separately.',
                'Ranks, model/benchmark version numbers and routing conclusions are context, not scores. Triplets follow the explicit table order Opus/Sonnet/Fable.',
                'Plans pricing/model metadata remain context-only; benchmark summary superseded, including conflicting Vals Sonnet 64.14 vs sweep 53.03 and FrontierCode 54.6 vs 54.4.',
                'SWE-Pro, FrontierCode, CursorBench and Toolathlon source/harness are not declared in coding narrative; no vendor harness or effort inferred.',
            ],
        },
    }


if __name__ == '__main__':
    artifact = normalize()
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'path': relative(OUTPUT), 'benchmarks': len(artifact['benchmarks']),
                      'numericTableCells': artifact['reconciliation']['numericTableCells'],
                      'tableScores': artifact['reconciliation']['tableScoreCount'],
                      'narrativeScores': artifact['reconciliation']['narrativeScoreCount'],
                      'artifacts': [{k: item[k] for k in ('path', 'observed', 'included', 'excluded', 'context')}
                                    for item in artifact['reconciliation']['artifacts']]}, ensure_ascii=False))
