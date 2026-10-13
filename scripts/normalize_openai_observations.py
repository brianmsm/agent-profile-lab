#!/usr/bin/env python3
"""Offline, source-local reconciliation of the captured OpenAI CSV and narrative."""
import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENAI_METRICS = ROOT / 'evidence/openai/GPT6_FAMILY_METRICS_2026-09-30.csv'
NARRATIVE = ROOT / 'evidence/openai/GPT6_FAMILY_EVIDENCE_2026-09-30.md'
OUTPUT = ROOT / 'evidence/openai/OPENAI_DASHBOARD_OBSERVATIONS_2026-10-02.json'

def relative_source(path):
    return path.relative_to(ROOT).as_posix()

# Frozen consumer normalization is appended below; no dependency on the changing generator.

def numeric_value(raw):
    raw = raw.strip()
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', raw):
        return None
    value = float(raw)
    return value if math.isfinite(value) else None


def openai_cost_unit(row, note):
    metric = row['metric'].strip()
    context = f"{row['benchmark']} {note}".lower()
    if 'per_test' in metric or re.search(r'/(?:test)\b', context):
        return 'USD / test'
    if (
        'per_task' in metric
        or re.search(r'/(?:task|tarea)\b', context)
        or (metric.startswith('frontiercode_') and row['provenance'].strip() == 'official-board')
    ):
        return 'USD / task'
    return 'USD (base no declarada)'


def openai_unit(row):
    score_type = row['score_type'].strip()
    if score_type == 'pct':
        return '%'
    if score_type == 'index':
        return 'index points'
    if score_type == 'elo':
        return 'Elo'
    if score_type == 'seconds':
        return 'seconds'
    if score_type == 'tps':
        return 'tokens/s'
    if score_type == 'combined':
        return 'composite score'
    if score_type == 'usd':
        return openai_cost_unit(row, row['notes'].strip())
    return row['score_type'] or 'score'


def openai_benchmarks():
    benchmarks = []
    local_source = relative_source(OPENAI_METRICS)
    with OPENAI_METRICS.open(encoding='utf-8-sig', newline='') as source_file:
        for line_number, row in enumerate(csv.DictReader(source_file), start=2):
            value = numeric_value(row['score'])
            note = row['notes'].strip()
            if value is None or '[INFERENCE' in note.upper():
                continue

            metric = row['metric'].strip()
            score_type = row['score_type'].strip()
            unit = openai_unit(row)
            raw_methodology = row['provenance'].strip()
            provenance_class = raw_methodology or 'not stated'
            original_source = row['source_url'].strip()
            source = original_source or local_source
            source_annotation = ''
            annotation_match = re.fullmatch(
                r'(https?://\S+)\s+\((capturado en evidence/supplemental/historical/initial-sources/data/benchmarks\.csv)\)',
                source,
            )
            if annotation_match:
                source, source_annotation = annotation_match.groups()
            provenance = f'{local_source}:L{line_number}; {provenance_class}'
            effort = row['effort'].strip() or 'no declarado'
            note_parts = [f'Métrica: {metric}; tipo registrado: {score_type}.']
            if row['unit'] == 'error_rate' or score_type in {'usd', 'seconds'}:
                note_parts.append('Menor es mejor.')
            if note:
                note_parts.append(note)
            if source_annotation:
                note_parts.append(f'URL original registrada: {original_source}.')

            benchmarks.append({
                'model': row['model_label'].strip(),
                'family': 'GPT-6',
                'benchmark': row['benchmark'].strip(),
                'value': value,
                'unit': unit,
                'effort': effort,
                'source': source,
                'date': row['captured'].strip(),
                'provenance': provenance,
                'methodology': raw_methodology,
                'note': ' '.join(note_parts),
            })

            cost = numeric_value(row['cost_usd'])
            if cost is None:
                continue
            cost_unit = openai_cost_unit(row, note)
            if cost_unit == 'USD (base no declarada)':
                cost_measure = 'coste registrado'
            else:
                cost_measure = 'coste por test' if cost_unit == 'USD / test' else 'coste por tarea'
            cost_note = [
                'Coste de ejecución del benchmark, no suscripción ni precio por token.',
                f'Métrica asociada: {metric}; {provenance_class}.',
            ]
            if cost_unit == 'USD (base no declarada)':
                cost_note.append('La fuente no declara la base de facturación; no se infiere.')
            if note:
                cost_note.append(f'Nota del registro asociado: {note}')
            if source_annotation:
                cost_note.append(f'URL original registrada: {original_source}.')
            benchmarks.append({
                'model': row['model_label'].strip(),
                'family': 'GPT-6',
                'benchmark': f"{row['benchmark'].strip()} — {cost_measure}",
                'value': cost,
                'unit': cost_unit,
                'effort': effort,
                'source': source,
                'date': row['captured'].strip(),
                'provenance': provenance,
                'methodology': raw_methodology,
                'note': ' '.join(cost_note),
            })
    return benchmarks



MODELS = {'s': 'GPT-6.1 Sol', 'a': 'GPT-6 Astra', 'l': 'GPT-6 Luna', 'o': 'GPT-6 Sol',
          'old': 'GPT-5.6 Sol', 'opus': 'Opus 5.5', 'opus5': 'Opus 5', 'fable': 'Fable 5.1'}
EFFORTS = ['max', 'xhigh', 'high', 'medium', 'low', 'non-reasoning']


def normalize():
    baseline = openai_benchmarks()
    result = [dict(row) for row in baseline]
    csv_rows = list(csv.DictReader(OPENAI_METRICS.open(encoding='utf-8-sig', newline='')))
    lines = NARRATIVE.read_text(encoding='utf-8').splitlines()
    csv_observations = []
    narrative_links = {}

    def context(row, raw=None):
        text = f"{row['methodology']} {row['note']} {row['source']}".lower()
        mirror = ('mirror' in text or 'espejo' in text or 'design arena' in row['benchmark'].lower() or
                  any(host in row['source'] for host in ('benchlm.ai', 'benchleader.com', 'llm-stats.com', 'modelgrep.com')))
        row['context'] = {
            'datasetSourceId': 'GPT6FAM',
            'sourceType': 'mirror' if mirror else row['methodology'],
            'independent': not mirror and row['methodology'] in {'independent-AA', 'independent-other'},
            'direction': 'lower' if 'Menor es mejor.' in row['note'] else 'not declared',
            'limitations': ['Mirror transcription is not independent corroboration.'] if mirror else [],
        }
        if mirror:
            row['context']['observedMethodology'] = 'mirror-only transcription; historical methodology preserved for consumer matching'
        if raw and (raw['score_type'] == 'seconds' or raw['unit'] == 'error_rate'):
            row['context']['direction'] = 'lower'
        if row['benchmark'].endswith('— coste registrado') and raw:
            declared_line = None
            declared_unit = None
            if raw['metric'] == 'intelligence_index' and raw['model_id'] != 'gpt-6-sol':
                declared_line = 48 + EFFORTS.index(row['effort'])
                declared_unit = 'USD / task'
            elif raw['metric'] == 'vals_index_pct':
                declared_line, declared_unit = 127, 'USD / test'
            if declared_line:
                row['context']['narrativeDenominator'] = {
                    'unit': declared_unit, 'locator': f'{relative_source(NARRATIVE)}:L{declared_line}',
                    'reason': 'Historical CSV consumer unit preserved; narrative explicitly declares denominator.',
                }
        if raw and raw['metric'] == 'agents_last_exam_pct' and raw['model_id'] == 'gpt-6.1-sol':
            row['context']['limitations'].append('Attribution conflict: pre-launch GPT-6 Sol blog; note attributes 56.4 to GPT-6 Sol, not 6.1. Retained historical consumer row, not corroborated.')
        if raw and raw['metric'] == 'gpqa_diamond_pct':
            row['context']['limitations'].append('Historical methodology says independent-AA but URL is OpenAI vendor; classification not silently repaired.')
        if 'under review' in text or 'scicode' in text:
            row['context']['limitations'].append('Benchmark under dataset review; not a fine-grained discriminator.')

    for row in result:
        number = int(re.search(r':L(\d+)', row['provenance']).group(1))
        context(row, csv_rows[number - 2])

    # Exact explicit effort/value pairs in CSV notes are observations too.
    # All use the original row's source/harness/date, not a guessed model URL.
    for number, raw in enumerate(csv_rows, 2):
        local = f'{relative_source(OPENAI_METRICS)}:L{number}'
        primary = next((row for row in baseline if row['provenance'].startswith(local + ';')), None)
        status = 'included' if primary else 'excluded'
        reason = 'Numeric score and associated numeric execution cost preserved exactly.'
        if not primary:
            reason = 'Explicit INFERENCE derivation, not an observed score.' if '[INFERENCE' in raw['notes'].upper() else 'Chart-only relative delta/ceiling, no absolute numeric score.'
        if primary:
            preserved_row = next(row for row in result if row['provenance'] == primary['provenance'])
            if preserved_row['context']['sourceType'] == 'mirror':
                reason += ' Historical mirror-only/chart transcription stays visible, not independently corroborated.'
            if numeric_value(raw['cost_usd']) is not None and openai_cost_unit(raw, raw['notes']) == 'USD (base no declarada)':
                reason += ' Execution-cost denominator not declared in CSV; original undeclared unit retained without inferring it.'
            if preserved_row['context']['limitations']:
                reason += ' ' + ' '.join(preserved_row['context']['limitations'])
        csv_observations.append({'locator': local, 'status': status, 'reason': reason, 'count': 1, 'raw': raw})
        if not primary:
            continue
        pairs = [] if number == 106 else re.findall(
            r'\b(xhigh|high|medium|low|NR|none)\s+([+-]?\d+(?:\.\d+)?)',
            raw['notes'].replace('−', '-'))
        for effort, value in pairs:
            effort = {'NR': 'non-reasoning', 'none': 'none'}.get(effort, effort)
            row = dict(primary)
            row.update(value=float(value), effort=effort,
                       provenance=f'{local}:notes:{effort}; {primary["methodology"]}',
                       note=f'Explicit supplementary effort in captured CSV note. {raw["notes"]}')
            context(row, raw)
            if not any((x['model'], x['benchmark'], x['effort'], x['value'], x['source'], x['unit']) ==
                       (row['model'], row['benchmark'], row['effort'], row['value'], row['source'], row['unit']) for x in result):
                result.append(row)
        if raw['metric'] == 'aa_lcr_pct' and raw['model_id'] == 'gpt-6-astra':
            for effort in EFFORTS[1:5]:
                row = dict(primary, effort=effort, value=80.0,
                           provenance=f'{local}:notes:{effort}; {primary["methodology"]}')
                context(row, raw)
                result.append(row)

    def add(line, model, benchmark, value, unit, effort='no declarado', csv_line=None,
            method=None, source=None, date=None, direction=None):
        template = next((r for r in baseline if r['provenance'].startswith(
            f'{relative_source(OPENAI_METRICS)}:L{csv_line};')), None) if csv_line else None
        if template:
            method = method or template['methodology']
            source = source or template['source']
            date = date or template['date']
        method = method or 'captured narrative; source attribution as recorded'
        source = source or relative_source(NARRATIVE)
        date = date or '2026-09-30'
        model = MODELS.get(model, model)
        row = dict(model=model, family='GPT-6' if model.startswith('GPT-6') else
                   ('GPT-5.6' if model.startswith('GPT-5.6') else 'comparison reference'),
                   benchmark=benchmark, value=float(value), unit=unit, effort=effort,
                   source=source, date=date,
                   provenance=f'{relative_source(NARRATIVE)}:L{line}; {method}',
                   methodology=method, note=f'Captured narrative: {lines[line - 1]}')
        key = ('model', 'benchmark', 'value', 'unit', 'effort', 'source')
        match = next((x for x in result if all(x[k] == row[k] for k in key)), None)
        if match:
            narrative_links.setdefault(line, []).append({'status': 'duplicate', 'benchmarkLocator': match['provenance']})
            return match
        context(row)
        if direction:
            row['context']['direction'] = direction
        result.append(row)
        narrative_links.setdefault(line, []).append({'status': 'included', 'benchmarkLocator': row['provenance']})
        return row

    def ladder(line, model, benchmark, values, unit, csv_line):
        efforts = EFFORTS[:-1] + ['none'] if line == 111 else EFFORTS
        for effort, value in zip(efforts, values):
            if value is not None:
                add(line, model, benchmark, value, unit, effort, csv_line)

    # Every explicitly attributed narrative ladder. Duplicate source/harness/value
    # observations link to CSV consumers instead of creating another scored row.
    for model, anchor, values in [('s',108,[272.81,108.86,57.97,5.72,2.12]),
                                  ('a',109,[315.42,201.83,58.39,6.21,2.97]),
                                  ('l',110,[124.04,21.48,15.18,None,2,.78])]:
        ladder(57, model, 'Time to First Token', values, 'seconds', anchor)
    for model, values, anchor in [('s',[38000,18000,13000,8000,4000],2),
                                  ('a',[27000,17000,12000,10000,4000],7),
                                  ('l',[50000,27000,20000,11000,2000],12)]:
        ladder(58, model, 'AA output tokens per task (rounded capture)', values, 'tokens / task', anchor)
    for line, benchmark, unit, entries in [
        (71,'Terminal-Bench 4.0','%', [('s',35,[56,54,52,48,31]),('a',40,[59,60,54,49,42]),('l',45,[13,8,5,3,0])]),
        (107,"Humanity's Last Exam",'%', [('s',78,[53,53,51,50,47]),('a',79,[55,55,53,53,49]),('l',80,[39,34,33,28,20,9])]),
        (110,'CritPt','%', [('s',84,[32,32,30,28,25]),('a',85,[32,31,29,29,26]),('l',86,[19,17,15,11,3,1])]),
        (122,'GDP.pdf','%', [('s',68,[31,31.8,32,30,27]),('a',69,[31,32.2,31,30.4,30.4]),('l',70,[20,17,14,14,6,5])]),
        (130,'AA-Omniscience','index points',[('l',98,[1,-2,-6,-5,-9,-22])]),
        (111,'ARC-AGI-2 semi-private','%', [('a',87,[95,93.3,92.1,92.1,85.4,59.6])]),
    ]:
        for model, anchor, values in entries:
            ladder(line, model, benchmark, values, unit, anchor)

    # Source-local distinct metric/harness or comparison-model observations.
    explicit = [
        (62,'s','SciCode',56,'%', 'xhigh',None),(62,'s','SciCode',54,'%', 'max',None),
        (72,'a','Terminal-Bench 4.0',59.60,'%', 'max',52),
        (72,'a','Terminal-Bench 4.0 — coste por tarea',9.58,'USD / task','max',52),
        (72,'l','Terminal-Bench 4.0',13.64,'%', 'max',52),
        (72,'o','Terminal-Bench 4.0',44.44,'%', 'max',52),
        (73,'a','Terminal-Bench 4.0',50.61,'%', 'low',51),
        (75,'o','FrontierCode 1.1 Extended',60.7,'%', 'max',117),
        (78,'a','VulcanBench Routine v1',12,'tasks passed / 12','low',61),
        (78,'a','VulcanBench Routine v1 — coste por tarea',.26,'USD / task','low',61),
        (82,'old','OSWorld 2.0 offline',65.7,'%', 'no declarado',63),
        (82,'a','ScreenSpot-Pro',92.7,'%', 'no declarado',63),
        (82,'old','ScreenSpot-Pro',76.9,'%', 'no declarado',63),
        (82,'o',"Agents' Last Exam",56.4,'%', 'max',129),
        (82,'opus5','OSWorld 2.0 offline',60.3,'%', 'medium',116),
        (88,'opus','Arena Code WebDev',1820.31,'Elo','max',65),
        (88,'fable','Arena Code WebDev',1753,'Elo','no declarado',65),
        (89,'a','Arena WebDev-React',1812.61,'Elo','max',65),
        (89,'a','Arena WebDev-HTML',1784.13,'Elo','max',65),
        (89,'l','Arena WebDev-React',1577.56,'Elo','max',65),
        (89,'l','Arena WebDev-HTML',1609.01,'Elo','max',65),
        (90,'a','Arena Text HF dataset',1442.9,'Elo','max',None),
        (90,'a','Arena Text rendered UI',1478,'Elo','max',None),
        (90,'l','Arena Text HF dataset',1392.4,'Elo','max',None),
        (90,'opus','Arena Text HF dataset',1517.8,'Elo','high',None),
        (91,'a','Epoch WebDev Arena replica',1800.28,'Elo','max',82),
        (92,'a','Design Arena 3D',1476,'Elo','no declarado',136),
        (92,'opus','Design Arena website',1361,'Elo','no declarado',136),
        (93,'a','BrowseComp',91.5,'%', 'no declarado',63),
        (104,'a','Terminal-Bench Science 0.1 — Vals mini-swe-agent',62.86,'%', 'max',92),
        (104,'l','Terminal-Bench Science 0.1 — Vals mini-swe-agent',4.29,'%', 'max',92),
        (105,'opus','Terminal-Bench Science cost/task',23.21,'USD / task','max',114),
        (106,'a','FrontierMath v2 Tier 4',97.6,'%', 'no declarado',63),
        (106,'a','FrontierMath v2 Tier 1-3',94,'%', 'no declarado',82),
        (112,'a','MRCR 512K-1M',96.3,'%', 'no declarado',63),
        (113,'a','SciCode',56.5,'%', 'consolidated',131),
        (113,'l','SciCode',54.6,'%', 'consolidated',131),
        (125,'a','Finance Agent v2',53.54,'%', 'max',102),
        (125,'l','Finance Agent v2',49.87,'%', 'max',102),
        (126,'a','EMB (Excel)',71.70,'%', 'max',103),
        (126,'l','EMB (Excel)',68.52,'%', 'max',103),
        (128,'l','LiveBench Data Analysis',73.4,'%', 'max',104),
        (139,'o','Factuality (prompts propensos a error)',11.4,'%', 'low',106),
        (140,'o','Restricción explícita (circunvenida)',64.4,'%', 'no declarado',107),
        (140,'a','Restricción explícita (circunvenida)',17.4,'%', 'no declarado',107),
    ]
    for spec in explicit:
        add(*spec, direction='lower' if spec[0] in {139,140} else None)
    for effort in EFFORTS[:4]:
        add(78,'a','VulcanBench Routine v1',12,'tasks passed / 12',effort,61)
    for effort in ['medium','low']:
        add(77,'l','VulcanBench Frontier v4 — completed tasks',0,'tasks / 23',effort,62)
    add(77,'l','VulcanBench Frontier v4 — timeouts',4,'timeouts / 23','max',62)

    # Explicit numeric observations in CSV notes not repeated in narrative.
    csv_note_specs = [
        (87,'a','ARC-AGI-3 standard',62.71,'%', 'max'),
        (104,'o','LiveBench Data Analysis',81.2,'%', 'max'),
        (105,'a','AIM-Text-to-SQL (BIRD subset) — strict',52.8,'%', 'medium'),
        (105,'a','AIM-Text-to-SQL (BIRD subset) — adjudicated',80.4,'%', 'medium'),
        (113,'l','Output Speed',135.2,'tokens/s','non-reasoning'),
        (131,'o','SciCode',57.6,'%', 'consolidated'),
        (137,'l','Design Arena UI component',1313,'Elo','max'),
    ]
    for anchor, model, benchmark, value, unit, effort in csv_note_specs:
        raw = csv_rows[anchor - 2]
        row = add(156, model, benchmark, value, unit, effort, anchor)
        if row['provenance'].startswith(f'{relative_source(NARRATIVE)}:L156;'):
            row['provenance'] = f'{relative_source(OPENAI_METRICS)}:L{anchor}:notes; {row["methodology"]}'
            row['note'] = f'Explicit supplementary metric in CSV note: {raw["notes"]}'
            context(row, raw)
    narrative_links.pop(156, None)  # CSV-note observations are not metrics in the MD source-list line.

    # Explicitly denominated note costs; base-not-declared costs remain context.
    for effort, value in [('xhigh',2.30),('high',1.71),('medium',1.48),('low',1.72)]:
        add(77,'a','VulcanBench Frontier v4 — coste registrado',value,
            'USD (base no declarada)',effort,61)
    # CSV already exposes baseline costs with undeclared denominators. Do not
    # pretend note values are per-task simply because they use a dollar sign.

    reasons = {
        27:'Contract prices/context; derived cache value explicitly not a measured score.',
        31:'Luna cache $0.01 is derived; contract context, not benchmark.',
        32:'Sol cache derivation and AA contract context; not scored benchmark.',
        34:'Historical contract tiering, not benchmark; Sol/Luna inheritance explicitly unverified.',
        38:'Operational policy and contract contexts, not benchmark performance.',
        40:'Ultrafast upper-bound speed/price marketing and plan price; no measured per-effort observation.',
        55:'Ranks have different comparison denominators; not a cross-model metric.',
        59:'Rounded speed ranges do not attribute a value to a particular effort; exact max CSV retained.',
        65:'Mirror-only composite clue explicitly not a claim; not independently traceable.',
        74:'DeepSWE conflicting mirror values retained in CSV; do not average or corroborate.',
        75:'Historical text says missing CSV, but low and old-Sol rows now exist; preserve them once.',
        76:'Chart-only approximate index/deltas and secondary codingfleet value; no primary absolute row.',
        77:'Missing Sol row; Luna 0/23 completions and 4/23 timeouts represented separately, not confused with composite scores.',
        78:'12/12 attributed to all five reasoning rungs; only low has an explicitly denominated cost.',
        80:'Verified absent benchmarks and missing mobile/desktop separation, not zero scores.',
        82:'Relative 2.1pp/1:7/1:10 costs and approximate durations not exact measured scores; no inferred Sol6.1 score.',
        90:'Dataset-vs-render Elo discrepancy kept in separate named measurements; votes/ranks/uncertainty are context.',
        93:'Sol6.1 ~Astra is not an absolute attributed numeric score.',
        103:'Sol6.1 BenchLM ~57 is mirror-only and already retained in CSV; missing primary row not independent evidence.',
        106:'Epoch best-across-settings 98 retained separately from vendor97.6; Erdős3 has no unit/denominator, retained as context only.',
        109:'96.0 baseline retained; 96.1 AA consolidated not independently localized; range is not another run.',
        115:'Interpretive comparison duplicates HLE/LCR/GDP.pdf; no new measurement.',
        121:'Astra mirror 51.2 retained as historical mirror consumer; others chart-only and no per-effort rows.',
        132:'Chart-only mirror and verified absent submissions explicitly not zero scores.',
        133:'Vals max-only; superseded launch index66.61 excluded, snapshot renormalization cannot be compared.',
        134:'Composite70.7/70.0 mirror clues excluded; SAGE/SNAP/Tax numeric rows already in CSV.',
        135:'Relative cost ratios duplicate explicit Vals costs; not additional tests.',
        139:'Relative gap/cost are not exact per-effort Astra values.',
        140:'Vendor report via press, not independent measurement; explicit old-Sol/Astra values included with press source.',
        141:'Omniscience max/NR numeric values already accounted in CSV/ladder.',
        183:'Vals summary duplicates recorded numeric observations; no independent extra source.',
        184:'Cognition summary duplicates medium/low score/cost rows already in CSV.',
        185:'BridgeBench editorial rating and proprietary multi-axis ratings/ranks, not success metrics; no primary URL captured.',
        186:'Secondary BridgeBench contract tiering, batch/flex/fast pricing; not independent scored benchmarks.',
    }
    narrative_observations = []
    for number, text in enumerate(lines, 1):
        links = narrative_links.get(number, [])
        if links:
            status = 'included' if any(x['status'] == 'included' for x in links) else 'duplicate'
            reason = 'Explicit attributed source-local observations; duplicates link to existing consumer rows.'
        elif 143 <= number <= 149:
            status, reason = 'excluded', 'Section explicitly INFERENCE: synthesis, not additional published observations.'
        elif number in reasons:
            status, reason = 'context', reasons[number]
        elif 48 <= number <= 54:
            status, reason = 'duplicate', 'Summary effort/index/cost table duplicates CSV Intelligence Index rows; non-reasoning absence is not zero.'
        elif number in {56,61,63,64,88,94,95,123,124,125,126,127,129,134,139,140,141}:
            status, reason = 'duplicate', 'Attributed summary numbers already represented by CSV observations and note effort expansions.'
        elif number <= 42:
            status, reason = 'context', 'Model availability/version, contract price/context, derivation or operational policy; not benchmark observations.'
        elif text.startswith('|') and re.search(r'\d', text):
            status, reason = 'duplicate', 'Table summary represented by CSV baseline and explicit supplementary observations; ranks/uncertainties retained as source context.'
        else:
            status, reason = 'context', 'Heading, prose/source vocabulary, URL references, absence or non-metric context; original line retained for audit.'
        narrative_observations.append({
            'locator': f'{relative_source(NARRATIVE)}:L{number}', 'status': status,
            'reason': reasons.get(number, reason), 'count': 1, 'text': text, 'observations': links,
        })

    base_keys = ['model','family','benchmark','value','unit','effort','source','date','provenance','methodology','note']
    preserved = sum(all(before[k] == after[k] for k in base_keys) for before, after in zip(baseline, result))
    comparison = {
        'consumer': 'dashboard Benchmark[] score and execution-cost observations',
        'baselineRows': len(baseline), 'baselineScoreRows': sum(not r['unit'].startswith('USD') for r in baseline),
        'baselineCostRows': sum(r['unit'].startswith('USD') for r in baseline),
        'exactBaselineRowsPreserved': preserved, 'removedBaselineRows': len(baseline)-preserved,
        'datasetRows': len(result), 'addedRows': len(result)-len(baseline),
        'byUnitBefore': dict(Counter(r['unit'] for r in baseline)),
        'byUnitAfter': dict(Counter(r['unit'] for r in result)),
        'mirrorConsumerRows': sum(r['context']['sourceType']=='mirror' for r in result),
        'pairMatching': 'Original baseline :L locator, suffix, effort, unit, source, methodology and date unchanged.',
    }
    def accounting(observations):
        return {'observed': len(observations),
                'included': sum(x['status']=='included' for x in observations),
                'excluded': sum(x['status']=='excluded' for x in observations),
                'observations': observations}
    artifact = {
        'schemaVersion': 1, 'benchmarks': result,
        'inputs': [{'path': relative_source(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in (OPENAI_METRICS, NARRATIVE)],
        'reconciliation': {
            'csv': accounting(csv_observations), 'narrative': accounting(narrative_observations),
            'consumerComparison': comparison,
            'referencedOrigins': sorted({
                re.sub(r'\s+\(capturado en evidence/supplemental/historical/initial-sources/data/benchmarks\.csv\)$', '', r['source_url'].strip())
                for r in csv_rows if r['source_url'].strip()
            } | {r['source'] for r in result}),
            'sources': [{'id':'GPT6FAM','title':'GPT-6 family archived metrics dataset',
                         'url':'evidence/openai/GPT6_FAMILY_METRICS_2026-09-30.csv',
                         'kind':'benchmark','evidenceType':'Local archived dataset',
                         'limitations':'Source-local attribution preserved; not independent evidence.'}],
            'notes': ['CSV observations count records; narrative observations count all lines including blank/context lines.',
                      'Inputs are historical captures, not a live recapture on 2026-10-02.',
                      'Historical mirror consumers are retained and explicitly labelled; no mirror is promoted to independent evidence.',
                      'Costs with undeclared denominators remain explicitly undeclared; contract pricing is context-only.',
                      'Supplementary effort observations from CSV notes retain exact source/harness; no URLs or efforts synthesized.',
                      'Consumer comparison uses actual normalized rows, not source-text assertions.'],
        },
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    normalize()
