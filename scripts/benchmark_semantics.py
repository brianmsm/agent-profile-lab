"""Typed evidence graph derived offline; source-local joins, no fuzzy identities.

Unknowns stay unknown. A linked published-model score is not route calibration.
Capture recency does not rewrite the date or scope of a scientific evaluation.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse
import json,re
from benchmark_io import ROOT,stable_id,sha,captures
KINDS={'capability','index','cost','price','duration','tokens','throughput','uncertainty','error-rate','safety','context','unclassified'}
DIRECTIONS={'higher','lower','context','unknown'}
AA_COMPONENTS={'terminalBench40':('terminalbench','4.0','terminalbench-4-0'), 'terminalBench21':('terminalbench','2.1','terminalbench-2-1'),
 'terminalbenchHard':('terminalbench','2.0-hard','terminalbench-hard'),'terminalBenchScience':('terminal-science','0.1','terminalbench-science'),
 'automationBenchPartialScore':('automationbench','AA','automationbench-aa'),'gdpval':('gdpval','2.1','gdpval-aa'),
 'gdpvalNormalized':('gdpval','2.1-normalized','gdpval-aa-normalized'),'scicode':('scicode','AA','scicode'),
 'hle':('reasoning','HLE-AA','humanitys-last-exam'),'gpqa':('reasoning','GPQA','gpqa'), 'critpt':('reasoning','CritPt','critpt'),
 'omniscience':('reasoning','Omniscience','omniscience'),'omniscienceAccuracy':('reasoning','Omniscience-accuracy','omniscience-accuracy'),
 'omniscienceHallucinationRate':('reasoning','Omniscience-hallucination','omniscience-hallucination'),
 'lcr':('reasoning','AA-LCR','artificial-analysis-long-context-reasoning'),'mlcrOverall':('reasoning','multilingual-LCR','mlcr'),
 'ifbench':('reasoning','IFBench','ifbench'),'tau2':('tau-tools','tau2','tau2'),'tauBanking':('tau-tools','tau-banking','tau-banking'),
 'gdpPdfAllPass':('document-work','GDP.pdf','gdp-pdf'),'itBenchSre':('data-engineering','ITBench-SRE','itbench-sre')}
AA_BY_SLUG={v[2]:(v[0],v[1]) for v in AA_COMPONENTS.values()};AA_BY_SLUG['aa-briefcase']=('briefcase','1.1')

def read(root,path):return json.loads((root/path).read_text())
def metric_kind(row,suite):
    """Explicit source kinds first, conservative unit/construct rules second."""
    name=row['benchmark'].lower();unit=row['unit'].lower();context=row.get('context',{})
    declared=context.get('metricKind')
    # Slopalytics labels this field literally 'intelligence', and the
    # archived benchmark is named 'Intelligence index'. The construct is
    # identifiable as an index; version, evaluation setup, and *model identity*
    # are still unresolved. Keep opaque-protocol + non-eligible and never
    # treat its 678 rows as new independent AA evaluations.
    if (row.get('benchmark')=='AA mirror — Intelligence index'
        and row.get('provenance','').startswith('evidence/slopalytics/')
        and row.get('methodology','').startswith('Slopalytics AA mirror')):
        return 'index','higher'
    if declared in KINDS:return declared,'higher' if declared=='capability' else 'lower' if declared in {'cost','price','duration'} else 'context'
    if re.search(r'standard error|reported se|uncertainty|confidence interval|\bci\b',name) or '(se)' in unit:return 'uncertainty','context'
    if 'million tokens' in unit or 'token price' in name or 'pricing' in name:return 'price','context'
    if re.search(r'cost|coste|\bspend\b',name) or re.search(r'\b(?:usd|eur|gbp|cny)\b',unit):return 'cost','lower'
    if unit in {'tokens/s','tokens/second'} or 'output speed' in name:return 'throughput','higher'
    if 'tokens' in unit:return 'tokens','context'
    if re.search(r'second|minute|\bhours?\b',unit) or re.search(r'\b(latency|duration|runtime)\b',name):return 'duration','lower'
    if re.search(r'hallucination.rate|flagged.rate|refusal.rate|false.positive|attack.success|jailbreak.*success|zero.score',name):return 'error-rate','lower'
    if re.search(r'cache.hit|calls|steps|attempts|instances|tokens|effort',name) or re.search(r'calls/|steps/|instances|turns/',unit):return 'context','context'
    if 'elo' in unit or 'index' in unit or 'rating points' in unit or 'capability ' in name:return 'index','higher'
    if unit in {'%','percentage points','score 0–1','score 0-1'} and suite!='uncatalogued':
        if re.search('safety|defender success|robustness|monitor.*recall',name):return 'safety','higher'
        return 'capability','higher'
    return 'unclassified','unknown'

def default_suite(row,suites):
    sid=row.get('sourceId','');name=row['benchmark']
    if sid=='SPECPI':return 'specpi'
    if sid=='FH':return 'frontierharness'
    if sid=='COMPOSIO':return 'composio'
    if 'science' in name.lower() and 'terminal' in name.lower():return 'terminal-science'
    for suite,entry in suites.items():
        pattern=entry.get('legacyPattern')
        if pattern and re.search(pattern,name):return suite
    return 'uncatalogued'

def aa_spec(row):
    name=row['benchmark'];context=row.get('context',{});slug=context.get('slug')
    if not name.startswith('AA ') or not slug:return None
    metric=name[3:];first=metric.split(' ')[0];suite,version,record='aa-index','4.3.2','intelligence-index'
    kind,direction=metric_kind(row,'aa-index');key=metric;primary_cost=False
    if metric in AA_COMPONENTS:
        suite,version,record=AA_COMPONENTS[metric];key='score'
    elif first in AA_BY_SLUG:
        suite,version=AA_BY_SLUG[first];record=first;field=metric[len(first)+1:];key=field
        primary_cost=field=='costPerTask'
    elif metric.startswith('intelligenceIndexCostPerTask/cost/total'):
        primary_cost=True;key='weighted-cost-per-task';kind='cost';direction='lower'
    elif metric=='intelligenceIndex':key='score';kind='index';direction='higher'
    elif metric.startswith('capability '):key=metric;record=metric
    elif metric.startswith('intelligenceIndexCost'):
        record='cost-decomposition';kind='cost';direction='lower'
    proto={'subset':record,'harness':'AA evaluation setup; not the selected user harness',
           'serverFallback':'default enabled' if 'Default Fallback' in row['model'] else 'none' if 'Haiku 5.5' in row['model'] else None,
           'comparison':'source-local','methodologyGroup':'AA serialized evaluation',
           'tasks':None,'trialsPerTask':None,'network':None,'compaction':None}
    if kind=='capability' and 'hallucination' in metric.lower():kind='error-rate';direction='lower'
    return {'suiteId':suite,'version':version,'metricKey':key,'kind':kind,'direction':direction,'denominator':'task' if '/task' in row['unit'] else 'source-defined',
            'recordKey':slug+'/'+record,'protocol':proto,'primaryCost':primary_cost,'costUnit':'USD/task','modelSlug':slug,'issueIds':context.get('issueIds',[])}

def frontier_spec(row):
    if row.get('sourceId')!='FCDATA' or 'measurementSpec' in row.get('context',{}):return None
    ctx=row.get('context',{});loc=row['provenance'].partition('#')[2]
    m=re.fullmatch(r'/?(v[^/]+)/data/(.+)/([^/]+)/(main|extended)/([^/]+)',loc)
    if not m:return None
    keys={'correct':('functional-correctness','capability','higher'),'new_score':('mergeability','capability','higher'),
          'cost':('cost','cost','lower'),'tokens':('output-tokens','tokens','context'),'duration_min':('duration','duration','lower'),
          'tool_calls':('tool-calls','context','context'),'steps':('steps','context','context'),'flagged_rate':('flagged-rate','error-rate','lower')}
    if m[5] not in keys:return None
    key,kind,direction=keys[m[5]]
    return {'suiteId':'frontiercode','version':m[1],'metricKey':key,'kind':kind,'direction':direction,'denominator':'task',
      'recordKey':m[1]+'/data/'+m[2]+'/'+m[3]+'/'+m[4],'protocol':{'subset':m[4],'tasks':ctx.get('tasks'),'harness':ctx.get('harness'),'trialsPerTask':None,'overlap':'Main is nested in Extended; not independent samples','comparison':'source-local'}}

def model_link(row,links):
    context=row.get('context',{});slug=context.get('slug')
    if any(q.lower() in row['model'].lower() for q in links['excludedVariantQualifiers']):return None,'unresolved',[]
    source=links.get('sourceLabels',{}).get(row.get('sourceId',''),{}).get(row['model'])
    known=source or links['aaSlugs'].get(slug) or links['labels'].get(row['model'])
    if known:return known['modelId'],known['relation'],[]
    candidates=[r['candidateModelId'] for r in links['candidateRelations'] if row['model']==r['observedLabel'] or (slug and slug==r['observedSlug'])]
    return None,'candidate' if candidates else 'unresolved',candidates

def build_semantics(benchmarks,source_coverage,root=ROOT):
    contract=read(root,'catalog/benchmark-registry.json');suites=deepcopy(contract['suites'])
    links=read(root,'catalog/benchmark-model-links.json');issues=read(root,'catalog/benchmark-issues.json')['issues'];caps=captures(root)
    metrics={};protocols={};result=[];semantic_versions=defaultdict(list)
    capture_by_path={x['path']:x for x in caps.values()}
    for index,row in enumerate(benchmarks):
        ctx=row.get('context',{});rawspec=ctx.get('measurementSpec');spec=deepcopy(rawspec or aa_spec(row) or frontier_spec(row) or {})
        suite=spec.get('suiteId',default_suite(row,suites));version=spec.get('version','not-declared')
        if suite not in suites:raise ValueError('Unknown declared suite: '+suite)
        kind,direction=metric_kind(row,suite)
        kind=spec.get('kind',kind);direction=spec.get('direction',direction)
        if kind not in KINDS or direction not in DIRECTIONS:raise ValueError('Metric kind/direction not declared')
        denominator=spec.get('denominator',row['unit'].partition('/')[2] or 'not-declared')
        metric={'suiteId':suite,'key':spec.get('metricKey',row['benchmark']),'label':row['benchmark'], 'unit':row['unit'], 'kind':kind,'direction':direction,'denominator':denominator,'aggregation':'as-reported; no cross-protocol averaging'}
        # Display labels may change between snapshots; identity is semantic, not display text.
        metric_id=stable_id('metric',{k:v for k,v in metric.items() if k not in {'label'}})
        metrics.setdefault(metric_id,{'id':metric_id,**metric})
        cap=capture_by_path.get(row['provenance'].partition('#')[0])
        if not cap and spec.get('captureId'):cap=caps.get(spec['captureId'])
        capture_date=cap['capturedAt'] if cap else row['date']
        controls=spec.get('protocol',{})
        protocol={'suiteId':suite,'version':version,'sourceId':row['sourceId'],'captureRef':cap['id'] if cap else row['provenance'].partition('#')[0].partition(':L')[0],
                  'capturedAt':capture_date,'dateBasis':'captured-http' if cap else 'legacy-record-date; meaning may be publication or capture',
                  'evaluationDate':controls.get('evaluationDate',row['date'] if row['sourceId'] in {'SPECPI','FH','COMPOSIO'} else None), 'priceAsOf':controls.get('priceAsOf'),
                  'subset':controls.get('subset'),'tasks':controls.get('tasks'),'trialsPerTask':controls.get('trialsPerTask'),
                  'harness':controls.get('harness',ctx.get('harness')),'harnessVersion':controls.get('harnessVersion'),
                  'network':controls.get('network'),'compaction':controls.get('compaction'),'serverFallback':controls.get('serverFallback'),
                  'comparison':controls.get('comparison','not-established'),'controls':controls,
                  'sourceMethodology':row.get('methodology','') if not spec else None}
        protocol_id=stable_id('protocol',protocol);protocols.setdefault(protocol_id,{'id':protocol_id,**protocol})
        model_id,relation,candidates=model_link(row,links)
        issue_ids=list(dict.fromkeys(spec.get('issueIds',[])+ctx.get('issueIds',[])))
        if not spec:issue_ids.append('opaque-protocol')
        if kind=='unclassified':issue_ids.append('unknown-metric')
        if ctx.get('primaryVerified') is False:issue_ids.append('local-summary-unverified')
        if row['benchmark']=='OSWorld 2.0 strict binary' and row['model'] in {'Claude Opus 5.5','Claude Sonnet 5.5'}:
            issue_ids.append('legacy-osworld-version-disputed')
        if row['sourceId']=='AA' and row['benchmark'] in {'AA scicode','AA critpt'}:
            issue_ids.append('aa-benchmark-under-review')
        if set(issue_ids)-issues.keys():raise ValueError('Unregistered evidence issue')
        record=spec.get('recordKey')
        evaluation_id=stable_id('evaluation',[row['sourceId'],protocol_id,record,row['model'],row['effort']]) if record else None
        primary_cost=spec.get('primaryCost')
        if primary_cost is None:
            primary_cost=kind=='cost' and (row['unit'] in {'USD/task','USD/test','USD/PR','USD/report','USD/evaluation'})
        cost_unit=spec.get('costUnit') or {'codereview':'USD/PR','deepscholar':'USD/report','vals-professional':'USD/test','edit-format':'USD/evaluation'}.get(suite,'USD/task')
        cost_link=stable_id('pair',[evaluation_id,cost_unit]) if evaluation_id and (kind in {'capability','index'} or primary_cost) else None
        scope='historical' if ctx.get('historical') or (spec.get('version')=='v1' and suite=='frontiercode') else 'current'
        mid=stable_id('observation',[row['sourceId'],row['provenance'],row['model'],row['effort'],row['benchmark'],row['unit'],row['value']])
        measurement={'id':mid,'metricId':metric_id,'protocolId':protocol_id,'evaluationId':evaluation_id,'modelId':model_id,
                     'modelRelation':relation,'candidateModelIds':candidates,'kind':kind,'direction':direction,
                     'scope':scope,'issueIds':sorted(set(issue_ids)),'costLinkId':cost_link,'primaryCost':bool(primary_cost),
                     'decisionEligible':scope=='current' and kind in {'capability','index'} and bool(model_id) and not issue_ids and protocol['comparison']!='not-established'}
        clean_context={k:v for k,v in ctx.items() if k!='measurementSpec'}
        result.append({**row,'context':clean_context,'measurement':measurement})
        if spec and row['sourceId'] in {'AA','FCDATA'}:
            semantic_controls={k:v for k,v in controls.items() if k not in {'capturedAt','evaluationDate','priceAsOf'}}
            key=stable_id('semantic',[row['sourceId'],ctx.get('slug') or row['model'],row['effort'],suite,version,metric['key'],row['unit'],record,semantic_controls])
            semantic_versions[key].append(index)
    revisions=[]
    for key,indices in semantic_versions.items():
        ordered=sorted(indices,key=lambda i:(protocols[result[i]['measurement']['protocolId']]['capturedAt'],i))
        latest=ordered[-1];new=result[latest]
        for older in ordered[:-1]:
            old=result[older]
            if old['date']==new['date']:continue
            old['measurement']['scope']='superseded';old['measurement']['decisionEligible']=False
            changed=old['value']!=new['value'];kind=new['measurement']['kind']
            revisions.append({'previous':old['measurement']['id'],'current':new['measurement']['id'],'change':'price-or-consumption-revision' if changed and kind in {'cost','price'} else 'value-revision' if changed else 'unchanged-recapture','notAnIndependentTrial':True})
    suite_stats={key:dict(observations=0,current=0,linked=0,comparable=0,decisionEligible=0) for key in suites}
    for row in result:
        m=row['measurement'];metric=metrics[m['metricId']];stat=suite_stats[metric['suiteId']];stat['observations']+=1
        if m['scope']=='current':stat['current']+=1
        if m['modelId']:stat['linked']+=1
        if protocols[m['protocolId']]['comparison']!='not-established':stat['comparable']+=1
        if m['decisionEligible'] and m['scope']=='current':stat['decisionEligible']+=1
    for key,s in suites.items():
        stat=suite_stats[key];s['coverage']=stat;s['captures']=[caps[k] for k in s['captureIds'] if k in caps]
        s['lifecycle']={'discovered':True,'captured':bool(s['captures']) or stat['observations']>0,'normalized':stat['observations']>0,'linked':stat['linked']>0,'comparable':stat['comparable']>0,'screeningUsable':stat['decisionEligible']>0,'routeCalibrated':False}
    stats={'observations':len(result),'currentObservations':sum(x['measurement']['scope']=='current' for x in result),
           'metricKinds':dict(Counter(r['measurement']['kind'] for r in result)),'scopeCounts':dict(Counter(r['measurement']['scope'] for r in result)),
           'modelLinks':dict(Counter(r['measurement']['modelRelation'] for r in result)),
           'bySource':dict(Counter(r['sourceId'] for r in result)),'suites':len(suites),'metrics':len(metrics),'protocols':len(protocols),'revisions':len(revisions),
           'independentTrials':'not-estimated-from-row-count','routeCalibrations':0}
    inputs={p:sha(root/p) for p in ['scripts/benchmark_semantics.py','scripts/benchmark_io.py','catalog/benchmark-registry.json','catalog/benchmark-model-links.json','catalog/benchmark-issues.json','sources/reviewed-captures.json']}
    registry={'schemaVersion':1,'updateMode':'manual','suites':suites,'metrics':metrics,'protocols':protocols,'issues':issues,'revisions':revisions,'stats':stats,
              'modelLinks':links,'inputSha256':inputs,'limitations':['Counts are scalar observations, not independent trials.','Source-local comparability is not cross-harness equivalence.','Published model matches do not establish endpoint or credential performance.','Unknown metric/protocol fields remain unresolved and excluded from automatic screening.']}
    return result,registry

def typed_family_coverage(benchmarks,registry):
    """Functional coverage from declared suites, never metric-name substring counts.

    Non-performance and replaced/historical observations do not turn an area green.
    This is a navigation aid, not a statement of validation for the whole domain.
    """
    grouped=defaultdict(lambda:defaultdict(set))
    areas={'coding':'coding','agent-use':'computer_use','research':'research','data':'data','web':'web','cybersecurity':'cybersecurity'}
    for row in benchmarks:
        m=row['measurement'];suite=registry['suites'][registry['metrics'][m['metricId']]['suiteId']]
        grouped[row['family']]
        if m['scope']!='current' or m['kind'] not in {'capability','index','safety'}:continue
        for domain in suite['domains']:
            if domain in areas:grouped[row['family']][areas[domain]].add(suite['label'])
    return {family:{area:'; '.join(sorted(domains[area]))+' (cobertura parcial por protocolo; no acredita todo el dominio)' if domains[area] else 'Sin resultados vigentes tipificados para esta área; no es puntuación cero.' for area in areas.values()} for family,domains in sorted(grouped.items())}
