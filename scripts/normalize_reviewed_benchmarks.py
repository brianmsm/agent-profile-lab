#!/usr/bin/env python3
"""Offline normalization of manually approved, immutable primary captures.

Numerical cells are not trials. Every adapter owns its scope, units and joins.
Unknown/missing cells are inventoried as context; no LLM calls or page execution.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from pathlib import Path
import csv, json, math, re
from benchmark_io import ROOT, captures, page, aa_models, sha, stable_id, table_number, js_literal_object

class Corpus:
    def __init__(self,root=ROOT):
        self.root=root;self.captures=captures(root);self.rows=[];self.context=[];self.used=set();self.pages={}
        with (root/'sources/ledger.csv').open(encoding='utf-8-sig',newline='') as handle:
            self.ledger={r['source_id']:r for r in csv.DictReader(handle)}
    def raw(self,key):
        self.used.add(key);return (self.root/self.captures[key]['path']).read_text(encoding='utf-8-sig')
    def html(self,key):
        if key not in self.pages:self.pages[key]=page(self.raw(key))
        return self.pages[key]
    def add(self,key,model,label,value,unit,effort,anchor,*,suite,version,metric,kind='capability',direction='higher',denominator='tasks',record=None,protocol=None,note='',factor=1,issues=None):
        if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Invalid explicitly parsed numerical value')
        cap=self.captures[key];self.used.add(key)
        spec={'suiteId':suite,'version':version,'metricKey':metric,'kind':kind,'direction':direction,'denominator':denominator,
              'recordKey':record,'protocol':protocol or {},'captureId':key,'issueIds':issues or []}
        self.rows.append({'model':model,'family':'Reviewed primary publications','benchmark':label,'value':value*factor,'unit':unit,'effort':effort or 'not stated',
          'sourceId':cap['sourceId'],'source':cap['url'],'date':cap['capturedAt'][:10],'provenance':cap['path']+'#'+anchor,
          'methodology':f"{suite} {version}; source-local protocol and exact record; public report, not route calibration",
          'note':note,'context':{'capturedNotEvaluationDate':True,'measurementSpec':spec}})
    def cell(self,key,table,ri,ci,label,*,model=None,**kw):
        text=self.html(key).tables[table][ri][ci];parsed=table_number(text)
        if parsed is None:
            self.context.append({'captureId':key,'locator':f'table/{table}/row/{ri}/cell/{ci}','reason':'Absent, non-scalar, or annotated cell; not interpreted as zero','raw':text});return
        value,interval=parsed
        if interval:kw['note']=(kw.get('note','')+' Reported uncertainty preserved literally, not silently relabeled as SE or CI: '+interval).strip()
        self.add(key,model or self.html(key).tables[table][ri][0],label,value,anchor=f'table/{table}/row/{ri}/cell/{ci}',**kw)


def normalize_harnessrank(c):
    """Exact bounded JSON array embedded in public JS; never eval/exec it.

    Only four full-report historical harness aggregates are published in this
    approved source. No synthetic per-task samples or fabricated significance.
    """
    key='harnessrank-aggregates-20261012'
    source=c.raw(key)
    match=re.fullmatch(r'\s*window\.HARNESS_RUNS\s*=\s*(\[.*\]);\s*',source,re.S)
    if not match:raise ValueError('HarnessRank aggregate JS wrapper changed')
    data=json.loads(match.group(1))
    if not isinstance(data,list) or len(data)!=4:
        raise ValueError('HarnessRank published row count changed; manual review needed')
    expected_harnesses={'pi':('0.79.6',5),'oh-my-pi':('16.1.15',5),
                        'opencode':('1.17.9',3),'codex':('0.130.0',3)}
    expected_metrics={
        'score_mean':('pass-rate','fraction (0–1)','capability','higher'),
        'score_interval':('reported-score-interval','fraction (0–1), interval definition not declared','uncertainty','context'),
        'cost_per_task_mean_usd':('cost','USD/task','cost','lower'),
        'cost_per_task_interval_usd':('reported-cost-interval','USD/task, interval definition not declared','uncertainty','context'),
        'tokens_per_task_mean':('total-tokens','tokens/task','tokens','context'),
        'tokens_per_task_interval':('reported-total-tokens-interval','tokens/task, interval definition not declared','uncertainty','context'),
        'uncached_tokens_per_task_mean':('uncached-tokens','tokens/task','tokens','context'),
        'uncached_tokens_per_task_interval':('reported-uncached-tokens-interval','tokens/task, interval definition not declared','uncertainty','context'),
        'input_tokens_per_task_mean':('input-tokens','tokens/task','tokens','context'),
        'cache_tokens_per_task_mean':('cached-input-tokens','tokens/task','tokens','context'),
        'output_tokens_per_task_mean':('output-tokens','tokens/task','tokens','context')}
    signatures=set();ranks=set()
    for index,row in enumerate(data):
        if not isinstance(row,dict):
            raise ValueError('Non-object HarnessRank row')
        harness=row.get('harness_id')
        if harness not in expected_harnesses or harness in signatures:
            raise ValueError('Unexpected/duplicate HarnessRank harness')
        signatures.add(harness)
        version,trials=expected_harnesses[harness]
        if (row.get('aggregate') is not True or row.get('model')!='gpt-5.5' or
            row.get('harness_version')!=version or row.get('thinking_or_effort')!='medium' or
            row.get('run_type')!='full' or row.get('scope')!='full' or
            row.get('benchmark_id')!='terminal-bench-2.1' or
            row.get('dataset_ref_sha')!='sha256:7d7bdc1cbedad549fc1140404bd4dc45e5fd0ea7c4186773687d177ad3a0699a' or
            row.get('task_count')!='89' or row.get('run_count')!=trials or
            type(row.get('rank')) is not int or not 1<=row['rank']<=4):
            raise ValueError('HarnessRank source version, task denominator or trial configuration drift')
        ranks.add(row['rank'])
        model=row['model']     # exact published label, not an inferred endpoint
        record='terminal-bench-2.1/full/'+model+'/'+row['thinking_or_effort']+'/'+harness+'@'+version
        protocol={'subset':'full','tasks':89,'trialsPerTask':trials,
            'harness':harness,'harnessVersion':version,'modelLabel':model,
            'effort':'medium','benchmarkDatasetSha256':row['dataset_ref_sha'],
            'sourceReportedRecordTime':row['recorded_at'],
            'evaluationDate':None,'comparison':'source-local',
            'uncertaintyInterpretation':'not declared; source-provided interval',
            'aggregation':'mean over 3 or 5 reported full runs, not independent task samples'}
        for field,(metric,unit,kind,direction) in expected_metrics.items():
            raw=row.get(field)
            if type(raw) is not str or not re.fullmatch(r'\d+(?:\.\d+)?',raw):
                raise ValueError('HarnessRank metric field missing/non-numeric: '+field)
            number=float(raw)
            if field=='score_mean' and not 0<=number<=1:raise ValueError('Pass rate exceeds [0,1]')
            c.add(key,model,'HarnessRank Terminal-Bench 2.1 '+harness+' '+metric,
                number,unit,'medium',f'/harness/{harness}/'+field,
                suite='harnessrank',version='terminal-bench-2.1/full',
                metric=metric,kind=kind,direction=direction,denominator='task',
                record=record,protocol=protocol,
                issues=['harnessrank-historical-harness'],
                note=('Published '+harness+' '+version+' historical full-run aggregate; '
                      'source interval not assigned a confidence definition. '
                      'No extrapolation to current Gentle or OMP versions.'))
        c.context.append({'captureId':key,'locator':f'/harness/{harness}/rank',
            'sourceRank':row['rank'],'reportedConsistency':row.get('consistency_label'),
            'reason':'Rank and consistency label are producer summaries, not independent extra scores.'})
    if signatures!=set(expected_harnesses) or ranks!={1,2,3,4}:
        raise ValueError('HarnessRank table no longer contains exactly four unique ranks and harnesses')

def normalize_aa(c):
    # Reuse the audited unit/duplicate handling, with explicit new capture date/path.
    import normalize_supplemental_sources as old
    old.ROWS=[];old.CONTEXT=[];old.EXCLUDED=[]
    key='aa-same-page-current';cap=c.captures[key];models=aa_models(c.raw(key))
    old.aa_rows(list(models.values()),cap['path'],cap['capturedAt'][:10],False,cap['url'])
    for row in old.ROWS:
        row['context']=deepcopy(row['context'])
        row['context']['captureId']=key
        row['context']['manualRefresh']=True
        if 'claude-haiku-5-5' in row['context'].get('slug',''):
            row['context']['issueIds']=[]
            if 'cost' in row['benchmark'].lower():row['context']['issueIds'].append('haiku-aa-cost-provisional')
            if 'automation' in row['benchmark'].lower():row['context']['issueIds'].append('haiku-aa-automation-prerelease')
        c.rows.append(row)
    c.context.append({'captureId':key,'reason':'Full embedded model collection; semantic revisions must be compared by source slug/metric, not array index. Repeated nested scores excluded by adapter.','models':len(models),'excludedCells':sum(x['count'] for x in old.EXCLUDED),'unscoredMetadataBlocks':len(old.CONTEXT)})

def normalize_frontier(c):
    key='cognition-current';data=json.loads(c.raw(key))
    fields={'correct':('%',100,'functional-correctness','capability','higher'),'new_score':('%',100,'mergeability','capability','higher'),
            'cost':('USD/task',1,'cost','cost','lower'),'tokens':('tokens/task',1,'output-tokens','tokens','context'),
            'duration_min':('minutes/task',1,'duration','duration','lower'),'tool_calls':('calls/task',1,'tool-calls','context','context'),
            'steps':('steps/task',1,'steps','context','context'),'flagged_rate':('%',100,'flagged-rate','error-rate','lower')}
    for version,v in data.items():
        for model,efforts in v['data'].items():
            for effort,subsets in efforts.items():
                for subset,metrics in subsets.items():
                    record=f'{version}/data/{model}/{effort}/{subset}'
                    protocol={'subset':subset,'tasks':v['subsets'][subset],'harness':v['harness'].get(model),'trialsPerTask':None,'overlap':'Main is nested in Extended; not independent samples','comparison':'source-local'}
                    for field,value in metrics.items():
                        if field not in fields or value is None:continue
                        unit,factor,metric,kind,direction=fields[field]
                        c.add(key,model,f'FrontierCode {version} {subset} {metric}',value,unit,effort,'/'+record+'/'+field,suite='frontiercode',version=version,metric=metric,kind=kind,direction=direction,denominator='task',factor=factor,record=record,protocol=protocol)

def normalize_cards(c):
    # Exact reviewed source-page assertions; these cells were visually checked in the source PDFs.
    def emit(key,p,model,label,value,suite,version,metric,**kw):
        folder='ANTH-HAIKU55-CARD' if key=='haiku-system-card' else 'ANTH-SONNET55-CARD'
        text=(c.root/'evidence/captures'/folder/'text.txt').read_text().split('\f')[p-1]
        if str(value) not in text or model.replace('Claude ','') not in text:raise ValueError(f'Primary PDF cell assertion failed: {key} p{p} {model} {value}')
        c.add(key,model,label,value,kw.pop('unit','%'),kw.pop('effort','max'),f'page/{p}/{metric}/{model}',suite=suite,version=version,metric=metric,**kw)
    for key,p,model,scores in [('haiku-system-card',111,'Claude Haiku 5.5',[64.8,83.7,30.7]),('sonnet-system-card',109,'Claude Sonnet 5.5',[81.3,90.3,54.3]),('sonnet-system-card',109,'Claude Opus 5.5',[89.9,93.9,61.4])]:
        for version,value in zip(['Pro','Multilingual','Multimodal'],scores):
            emit(key,p,model,'SWE-bench '+version,value,'swe-pro',version,'score',record=f'{model}/{version}/max',protocol={'subset':version,'trialsPerTask':5,'harness':'author evaluation','comparison':'source-local','tasks':300 if version=='Multilingual' else None})
    for model,values in [('Claude Haiku 5.5',[72.4,37.1]),('Claude Sonnet 5.5',[83.9,48.8]),('Claude Opus 5.5',[87.2,53.2])]:
        for metric,value in zip(['partial-credit','strict-success'],values):
            emit('haiku-system-card',128,model,'OSWorld 2.1 offline82 '+metric,value,'osworld','2.1','offline82/'+metric,record=model+'/offline82/max',protocol={'subset':'official-offline-82-of-108','tasks':82,'trialsPerTask':5,'network':'offline VM','compaction':'server-side context management','comparison':'source-local','scoring':metric})
    for model,values in [('Claude Sonnet 5.5',[80.1,43.5]),('Claude Opus 5.5',[81.8,48.7])]:
        for metric,value in zip(['partial-credit','strict-success'],values):
            emit('sonnet-system-card',130,model,'OSWorld 2.1 full '+metric,value,'osworld','2.1','full/'+metric,record=model+'/full/max',protocol={'subset':'full-108','tasks':108,'trialsPerTask':5,'compaction':'server-side above100K','comparison':'source-local','scoring':metric})
    for model,score,se,trials,effort,fallback in [('Claude Haiku 5.5',39.2,1.9,10,'max','none; safeguard stops'),('Claude Sonnet 5.5',70.6,2.5,5,'max','default server-side'),('Claude Opus 5.5',66.4,2.6,5,'xhigh','default server-side')]:
        protocol={'tasks':66,'trialsPerTask':trials,'harness':'Claude Code --bare','network':'no egress; cached resources','serverFallback':fallback,'comparison':'source-local','uncertaintyAssumption':'Author SE treats trials as independent; task clustering not removed.'}
        for metric,value,kind,direction in [('success',score,'capability','higher'),('reported-SE',se,'uncertainty','context')]:
            emit('haiku-system-card',115,model,'Terminal-Bench 4.0 author '+metric,value,'terminalbench','4.0',metric,kind=kind,direction=direction,unit='%' if kind=='capability' else 'percentage points (SE)',effort=effort,record=model+'/tb4/'+effort,protocol=protocol)
    c.context.append({'captureId':'haiku-system-card','reason':'FrontierCode and AA comparator summaries are not added again as independent studies. Selected author-owned evaluations are extracted with page anchors; remaining PDF sections remain contextual, not silently labeled parsed.'})

def normalize_vals(c):
    # Read the exact rendered score section, not the unrelated navigation model list.
    for key,model in [('vals-haiku-current','Claude Haiku 5.5'),('vals-sonnet-current','Claude Sonnet 5.5'),('vals-opus-current','Claude Opus 5.5')]:
        text=c.html(key).text
        match=re.search(r'Benchmarks Accuracy Rankings (.+?)(?:Compare|How|Related|Benchmark Results|Sources|©)',text)
        section=match[1] if match else text[text.index('Benchmarks Accuracy Rankings ')+len('Benchmarks Accuracy Rankings '):]
        pattern=r'([A-Za-z][A-Za-z0-9 ’\'()/:.\-]+?)\s+(\d+\.\d+)\s*%\s*±\s*(\d+\.\d+)\s+\d+\s*/\s*\d+'
        seen=set()
        for m in re.finditer(pattern,section):
            label=m[1].strip()
            if label in seen:continue
            seen.add(label)
            proto={'subset':label,'harness':None,'comparison':'source-local','effort':'not declared in rendered score row','uncertainty':'Reported plus/minus; type retained unknown until methodology-linked.'}
            for metric,value,kind,direction,unit in [('score',float(m[2]),'capability','higher','%'),('uncertainty',float(m[3]),'uncertainty','context','percentage points (type not declared)')]:
                c.add(key,model,'Vals '+label+' '+metric,value,unit,'not stated','rendered/benchmark/'+label+'/'+metric,suite='vals-professional',version=label,metric=metric,kind=kind,direction=direction,record=model+'/'+label,protocol=proto)
        if not seen:raise ValueError('Vals rendered score section absent')
        cost=re.search(r'Cost / Test \(Vals Index\) \$\s*([\d.]+)',text)
        if cost:c.add(key,model,'Vals Vals Index cost',float(cost[1]),'USD/test','not stated','rendered/vals-index/cost',suite='vals-professional',version='Vals Index',metric='cost',kind='cost',direction='lower',denominator='test',record=model+'/Vals Index',protocol={'subset':'Vals Index','harness':None,'comparison':'source-local','effort':'not declared in rendered score row','uncertainty':'Reported plus/minus; type retained unknown until methodology-linked.'})
        c.context.append({'captureId':key,'reason':'Complete rendered Accuracy/Rankings section normalized. Rank/denominator pairs are ranking metadata, not task sample sizes. Per-suite cost/latency panes require separate cells; no inferred values.'})


def normalize_tables(c):
    # Declarative exact table-column adapters. Generic scraping of numeric leaves is prohibited.
    def simple(key,ti,start,cols,suite,version,modelcol=0,record_prefix='',protocol=None,model_transform=None,condition_rows=False):
        table=c.html(key).tables[ti];condition=''
        for ri in range(start,len(table)):
            row=table[ri]
            if len(row)==1 and condition_rows:condition=row[0];continue
            if len(row)<=max([modelcol]+[x[0] for x in cols]):
                c.context.append({'captureId':key,'locator':f'table/{ti}/row/{ri}','reason':'Header, merged, or incomplete row preserved as context, not a scored model.'});continue
            model=model_transform(row) if model_transform else row[modelcol]
            proto={**(protocol or {}),'condition':condition,'comparison':'source-local'}
            rec=record_prefix+model+'/'+condition
            for ci,label,unit,kind,direction,denominator in cols:
                c.cell(key,ti,ri,ci,label,model=model,suite=suite,version=version,metric=label,kind=kind,direction=direction,denominator=denominator,unit=unit,effort='not stated',record=rec,protocol=proto)
    simple('codereview',0,1,[(2,'CodeReviewBench F1','points out of 100','index','higher','PR'),(3,'CodeReviewBench precision','%','capability','higher','review finding'),(4,'CodeReviewBench recall','%','capability','higher','reference bug'),(6,'CodeReviewBench cost per PR','USD/PR','cost','lower','PR'),(7,'CodeReviewBench cost per bug','USD/bug','cost','lower','bug')],'codereview','captured-leaderboard',1,protocol={'scoring':'Human/reference defects with review matching; F1 distinct from precision and recall'},model_transform=lambda row:row[1])
    # Displayed CI has no explicit metric association in the table: keep it as contextual metadata.
    for ri,row in enumerate(c.html('codereview').tables[0][1:],1):c.context.append({'captureId':'codereview','locator':f'table/0/row/{ri}/cell/5','reason':'Displayed 95% interval, metric association not established by column; do not attach to F1 by guess.','raw':row[5]})
    simple('datascibench',2,2,[(2,'DataSciBench task success','%','capability','higher','task'),(3,'DataSciBench completion','%','capability','higher','task'),(4,'DataSciBench visualization judge','judge points','index','higher','task'),(10,'DataSciBench composite','points','index','higher','task')],'datascibench','paper-2502.13897',protocol={'harness':'paper data-analysis agent','scoring':'SR, CR, VLM and composite kept separate'})
    simple('deepresearch2',3,1,[(i,'DeepResearch II '+label,'points','index' if i==4 else 'capability','higher','task') for i,label in enumerate(['','information recall','analysis','presentation','total score']) if i],'deepresearch2','paper-2601.08536',protocol={'harness':'named research system, not bare LLM'})
    simple('swe-prbench',9,1,[(i,'SWE-PRBench '+label,'score 0–1','error-rate' if i==6 else 'index' if i<=4 else 'capability','lower' if i==6 else 'higher','PR') for i,label in enumerate(['','config_A score','config_B score','config_C score','weighted score','config_A detection rate','mean false positive rate']) if i],'swe-prbench','paper-2603.26130',protocol={'tasks':350,'scoring':'A/B/C context budgets; mean score is not task-success probability'})
    simple('minimal-mle',0,2,[(1,'MLE percentile self-select','percentile','index','higher','competition'),(2,'MLE percentile oracle','percentile','index','higher','competition'),(3,'MLE medal self-select','%','capability','higher','competition'),(4,'MLE medal oracle','%','capability','higher','competition')],'minimal-mle','paper-2609.40303-table1',protocol={'harness':'paper ablation label; backbone not inferred from label'},record_prefix='ablation/')
    table=c.html('minimal-mle').tables[1]
    for ri,row in enumerate(table[2:],2):
        for ci,h in enumerate(['Malena','AiScientist','MLEvolve'],1):
            c.cell('minimal-mle',1,ri,ci,'MLE surpassed SOTA',model=row[0],suite='minimal-mle',version='paper-2609.40303-table2',metric='surpassed-SOTA',unit='%',effort='not stated',record=row[0]+'/'+h,protocol={'harness':h,'comparison':'source-local'})
    simple('deepscholar',4,2,[(i,'DeepScholar '+label,'score 0–1','index' if i==8 else 'capability','higher','report') for i,label in enumerate(['','organization','nugget coverage','relevance','reference coverage','document importance','citation precision','claim coverage','geometric mean']) if i],'deepscholar','paper-2508.20033-main',protocol={'scoring':'Synthesis, retrieval and verifiability separate','harness':'named research system'},condition_rows=True)
    simple('deepscholar',10,2,[(6,'DeepScholar latency','seconds/report','duration','lower','report'),(7,'DeepScholar reported API cost','USD/report','cost','lower','report')],'deepscholar','paper-2508.20033-main',protocol={'scoring':'Synthesis, retrieval and verifiability separate','harness':'named research system'},condition_rows=True)
    # LongMemEval's oracle/non-oracle conditions and model sizes are never collapsed.
    table=c.html('longmemeval').tables[3];condition=''
    for ri,row in enumerate(table[1:],1):
        if len(row)==1:condition=row[0];continue
        if len(row)!=5:raise ValueError('LongMemEval table shape changed')
        model=row[0]+(' '+row[1] if row[1]!='-' else '')
        for ci,subset in [(2,'Oracle'),(3,'S')]:
            c.cell('longmemeval',3,ri,ci,'LongMemEval '+subset+' accuracy',model=model,suite='longmemeval',version='paper-2410.10813',metric='accuracy',unit='score 0–1',effort='not stated',record=model+'/'+condition+'/'+subset,protocol={'subset':subset,'harness':condition,'comparison':'source-local'})
    # Skills table0 is a second display of some table1 rows; deduplicate by experimental condition.
    seen=set()
    for ti in [0,1]:
        for ri,row in enumerate(c.html('skillsbench').tables[ti][1:],1):
            harness,model=('Claude Code',row[0]) if ti==0 else tuple(row[0].split(' · ',1))
            if (harness,model) in seen:continue
            seen.add((harness,model))
            for ci,condition in [(1,'without skills'),(2,'with skills')]:
                c.cell('skillsbench',ti,ri,ci,'SkillsBench success',model=model,suite='skillsbench',version='1.1',metric='success',unit='%',effort='not stated',record=harness+'/'+model+'/'+condition,protocol={'tasks':87,'harness':harness,'condition':condition,'pairKey':harness+'/'+model,'comparison':'paired-condition'})
    table=c.html('scaffold-effect').tables[1]
    for ri,row in enumerate(table[1:],1):
        for ci,model in [(1,'Qwen 3.6 Plus'),(2,'MiniMax M2.5')]:
            c.cell('scaffold-effect',1,ri,ci,'Scaffold Effect success',model=model,suite='scaffold-effect',version='paper-2607.22585',metric='success',unit='%',effort='study-fixed',record=model+'/'+row[0],protocol={'tasks':50,'harness':row[0],'comparison':'source-local'})
    table=c.html('scaffold-effect').tables[2]
    for ri,row in enumerate(table[1:],1):
        model={'Qwen':'Qwen 3.6 Plus','MiniMax':'MiniMax M2.5'}[row[1]];harness={'OpenHands':'OpenHands-SDK'}.get(row[0],row[0])
        for ci,metric,unit,kind,direction,denom in [(2,'tokens per solve','tokens/solved task','tokens','context','solved task'),(4,'mean turns','turns/task','context','context','task')]:
            c.cell('scaffold-effect',2,ri,ci,'Scaffold Effect '+metric,model=model,suite='scaffold-effect',version='paper-2607.22585',metric=metric,unit=unit,kind=kind,direction=direction,denominator=denom,effort='study-fixed',record=model+'/'+harness,protocol={'tasks':50,'harness':harness,'comparison':'source-local'})
    # ScienceAgentBench stores two knowledge conditions under each scaffold heading.
    table=c.html('scienceagentbench').tables[3];harness=''
    for ri,row in enumerate(table[2:],2):
        if len(row)==1:harness=row[0];continue
        if len(row)!=9:continue
        for offset,condition in [(1,'without knowledge'),(5,'with knowledge')]:
            for delta,label,unit,kind,direction,denom in [(0,'success','%','capability','higher','task'),(1,'code similarity','points','index','higher','task'),(2,'valid execution','%','capability','higher','task'),(3,'reported cost','USD/task','cost','lower','task')]:
                c.cell('scienceagentbench',3,ri,offset+delta,'ScienceAgentBench '+label,model=row[0],suite='scienceagentbench',version='paper-2410.05080',metric=label,unit=unit,kind=kind,direction=direction,denominator=denom,effort='not stated',record=row[0]+'/'+harness+'/'+condition,protocol={'tasks':102,'harness':harness,'condition':condition,'comparison':'source-local'})
    # AgentDojo arXiv duplicates rendered MathML numbers. Accept only equal copies, no eval.
    table=c.html('agentdojo').tables[3]
    for ri,row in enumerate(table[1:],1):
        if len(row)!=7:continue
        for ci,label,kind,direction in [(1,'benign utility','capability','higher'),(3,'utility under attack','capability','higher'),(5,'targeted attack success','error-rate','lower')]:
            parts=row[ci].split()
            if len(parts)!=2 or parts[0]!=parts[1] or not re.fullmatch(r'\d+(?:\.\d+)?',parts[0]):raise ValueError('AgentDojo duplicated numeric rendering changed')
            c.add('agentdojo',row[0],'AgentDojo '+label,float(parts[0]),'%','study-fixed',f'table/3/row/{ri}/cell/{ci}',suite='agentdojo',version='paper-2406.13352',metric=label,kind=kind,direction=direction,record=row[0],protocol={'harness':'paper default agent','comparison':'source-local'},note='Reported uncertainty retained verbatim (do not assume CI): '+row[ci+1])
    simple('aider',0,1,[(2,'Aider Polyglot correct','%','capability','higher','task'),(3,'Aider Polyglot evaluation cost','USD/evaluation','cost','lower','evaluation'),(5,'Aider Polyglot edit validity','%','capability','higher','edit')],'edit-format','polyglot-leaderboard',modelcol=1,model_transform=lambda r:r[1]+' ['+r[6]+']',protocol={'tasks':225,'harness':'aider','comparison':'source-local','costBasis':'complete evaluation, not per task'})
    # Explicit top-level HAL constructs; unnamed component transforms remain context.
    simple('hal-reliability',0,2,[(2,'HAL accuracy','%','capability','higher','task'),(3,'HAL reliability aggregate','score 0–1','index','higher','published aggregate')],'hal-reliability','captured-leaderboard',modelcol=1,protocol={'harness':'HAL published agent setup','comparison':'source-local'})
    simple('livesqlbench',0,1,[(3,'LiveSQLBench success','%','capability','higher','task'),(4,'LiveSQLBench cost per task','USD/task','cost','lower','task')],'livesqlbench','captured-leaderboard',modelcol=1,protocol={'harness':'submitted configuration as published','comparison':'source-local'})
    # MCP verified global summary. Service denominators differ, hence separate protocols.
    key='mcpmark-verified';table=c.html(key).tables[0]
    service_sizes={'Filesystem':30,'Github':23,'Notion':28,'Playwright':25,'Postgres':21}
    for ri,row in enumerate(table[2:],2):
        if len(row)!=10:raise ValueError('MCPMark Verified row schema changed')
        for ci,metric in [(2,'overall'),(5,'Filesystem'),(6,'Github'),(7,'Notion'),(8,'Playwright'),(9,'Postgres')]:
            condition='second recorded filesystem run published as run-1' if 'kimi-k2-7-code' in row[1] and metric=='Filesystem' else 'run-1'
            c.cell(key,0,ri,ci,'MCPMark Verified '+metric+' pass@1',model=row[1],suite='mcpmark',version='verified-127',metric='pass@1',unit='%',effort='source model label',record=row[1]+'/'+metric,protocol={'tasks':127 if metric=='overall' else service_sizes[metric],'trialsPerTask':1,'subset':metric,'condition':condition,'comparison':'source-local'},note='Scores-only models may have no task traces. Historical study update date displayed separately from capture.')
        duration=re.fullmatch(r'(\d+(?:\.\d+)?)s',row[3])
        if duration:c.add(key,row[1],'MCPMark Verified mean duration',float(duration[1]),'seconds/task','source model label',f'table/0/row/{ri}/cell/3',suite='mcpmark',version='verified-127',metric='duration',kind='duration',direction='lower',record=row[1]+'/overall',protocol={'tasks':127,'trialsPerTask':1,'subset':'overall','condition':'run-1','comparison':'source-local'})

def normalize_additional(c):
    # BFCL's public page loader explicitly selects data_overall.csv. No JS execution.
    rows=list(csv.DictReader(c.raw('bfcl-overall').splitlines()))
    expected={'Model','Overall Acc','Total Cost ($)','Latency Mean (s)','Latency Standard Deviation (s)','Memory Acc'}
    if not rows or not expected<=rows[0].keys():raise ValueError('BFCL CSV schema changed')
    for ri,row in enumerate(rows,2):
        for field,value in row.items():
            if field in {'Rank','Model','Model Link','Organization','License'}:continue
            parsed=table_number(value)
            if parsed is None:
                c.context.append({'captureId':'bfcl-overall','locator':f'line/{ri}/{field}','reason':'Metric absent or not scalar','raw':value});continue
            unit,kind,direction,denom=('%','capability','higher','source-defined tests')
            if field=='Overall Acc':kind='index'
            elif field=='Total Cost ($)':unit,kind,direction,denom='USD/evaluation','cost','lower','evaluation'
            elif field.startswith('Latency '):unit,kind,direction='seconds','uncertainty' if 'Standard Deviation' in field else 'duration','context' if 'Standard Deviation' in field else 'lower'
            elif field.startswith('Format Sensitivity'):unit,kind,direction='percentage points','uncertainty','context'
            c.add('bfcl-overall',row['Model'],'BFCL V4 '+field,parsed[0],unit,'source model label',f'line/{ri}/{field}',suite='bfcl',version='V4',metric=field,kind=kind,direction=direction,denominator=denom,record=row['Model'],protocol={'subset':'overall source CSV','harness':'BFCL function-calling vs prompt modes retained in exact model labels','comparison':'source-local','evaluationDate':None},note='New capture of historical model evaluations. Not current-model coverage. Cost is a complete evaluation, not a task cost.')
    # Exact numeric labels on author-rendered graph. Do not estimate pixel positions.
    raw=c.raw('hashline')
    blocks=re.findall(r'<div[^>]+class="edit-bench-row">(.*?)</div>',raw,re.S)
    if not blocks:raise ValueError('Hashline exact graph labels absent')
    for i,block in enumerate(blocks):
        model_html=re.search(r'<span class="edit-bench-model">(.*?)</span>',block,re.S)
        if not model_html:raise ValueError('Hashline row model missing')
        model=re.sub(r'^\d+\s*','',page(model_html[1]).text)
        labels=re.findall(r'title="(patch|replace|hashline v2|hashline) (\d+(?:\.\d+)?)%"',block)
        for mode,value in labels:
            c.add('hashline',model,'Edit-format success',float(value),'%','study-fixed',f'graph/row/{i}/{mode}',suite='edit-format',version='hashline-author-study',metric='success',record=model+'/'+mode,protocol={'harness':'author tool-format ablation','condition':mode,'pairKey':model,'comparison':'paired-condition','tasks':None,'trialsPerTask':None},note='Author graph labels, not pixel estimates or independent replication. Different tool formats; do not confuse hashline and hashline v2.')

def normalize_remaining_tables(c):
    # WorkArena source explicitly labels SR and SE, with condition-specific subsets.
    table=c.html('workarena').tables[1]
    if table[0][1:]!=['GPT-4o','GPT-4o-V','GPT-3.5','Llama3']:raise ValueError('WorkArena header changed')
    for ri,row in enumerate(table[2:],2):
        if len(row)!=9:
            c.context.append({'captureId':'workarena','locator':f'table/1/row/{ri}','reason':'Merged header or contextual row; not scored'});continue
        for model_index,model in enumerate(table[0][1:]):
            ci=1+model_index*2;record=model+'/'+row[0]
            c.cell('workarena',1,ri,ci,'WorkArena '+row[0]+' success',model=model,suite='workarena',version='paper-2403.07718',metric='success',unit='%',effort='study-fixed',record=record,protocol={'subset':row[0],'harness':'BrowserGym paper configuration','comparison':'source-local'})
            se=re.fullmatch(r'±\s*\\pm\s*(\d+(?:\.\d+)?)',row[ci+1])
            if se:c.add('workarena',model,'WorkArena '+row[0]+' reported SE',float(se[1]),'percentage points (SE)','study-fixed',f'table/1/row/{ri}/cell/{ci+1}',suite='workarena',version='paper-2403.07718',metric='reported-SE',kind='uncertainty',direction='context',record=record,protocol={'subset':row[0],'harness':'BrowserGym paper configuration','comparison':'source-local'})
    # Publisher Qwen card has HTML tables embedded in Markdown. Preserve its exact
    # variant labels. Compound cells and undocumented score units remain unresolved.
    for ti,table in enumerate(c.html('qwen-card').tables):
        if not table or table[0][1]!='Qwen3.8-Flash-Next':raise ValueError('Qwen card model table header changed')
        for ri,row in enumerate(table[1:],1):
            if len(row)!=len(table[0]) or row[0].startswith('#'):continue
            for ci,model in enumerate(table[0][1:],1):
                parsed=table_number(row[ci])
                if parsed is None:
                    c.context.append({'captureId':'qwen-card','locator':f'table/{ti}/row/{ri}/cell/{ci}','reason':'Compound metric or absent score; keep raw cell until its submetric contract is reviewed.','raw':row[ci]});continue
                c.add('qwen-card',model,'Qwen publisher '+row[0],parsed[0],'publisher score (unit not declared)','not stated',f'table/{ti}/row/{ri}/cell/{ci}',suite='qwen-public',version='Flash-Next model card',metric=row[0],kind='unclassified',direction='unknown',record=model+'/'+row[0],protocol={'subset':row[0],'harness':'publisher evaluation; exact harness not stated','comparison':'not-established'},note='A scalar reported by the author, not a percentage inferred from magnitude. Flash-Next remains only a candidate relation to the NaN service label.')
    # Literal public BIRD matrices, not functions executed in a browser. Reward,
    # phases, simulator and free/stress settings remain separate experimental cells.
    source=c.raw('bird-interact')
    for var in ['freeLeaderboardData','stressLeaderboardData']:
        obj=js_literal_object(source,var)
        if not isinstance(obj,dict) or not obj:raise ValueError('BIRD literal matrix empty')
        for condition,stages in obj.items():
            for stage,rows in stages.items():
                for ri,row in enumerate(rows):
                    if not {'model','simulator','passRate','date'}<=row.keys():raise ValueError('BIRD record schema changed')
                    value=table_number(str(row['passRate']))
                    if value is None:continue
                    c.add('bird-interact',row['model'],'BIRD-Interact '+stage+' pass rate',value[0],'%','study-fixed',f'{var}/{condition}/{stage}/{ri}/passRate',suite='bird-interact',version='published-interaction-matrix',metric='pass-rate',record=var+'/'+condition+'/'+stage+'/'+row['model'],protocol={'subset':condition,'harness':'BIRD interaction agent','simulator':row['simulator'],'condition':var,'stage':stage,'comparison':'source-local','evaluationDate':None,'sourceReportedSubmissionDate':row['date'],'submissionVerified':row.get('verified')},note='Submission date is not established as an execution date. Unverified/new submissions remain source claims. Budget field not converted to API cost without a denominator contract.')

def run(root=ROOT):
    c=Corpus(root);normalize_aa(c);normalize_frontier(c);normalize_cards(c);normalize_vals(c);normalize_tables(c);normalize_additional(c);normalize_harnessrank(c);normalize_remaining_tables(c)
    inputs={p:sha(root/p) for p in ['sources/reviewed-captures.json','scripts/normalize_reviewed_benchmarks.py','scripts/benchmark_io.py','scripts/normalize_supplemental_sources.py','catalog/benchmark-registry.json','catalog/benchmark-model-links.json','catalog/benchmark-issues.json']}
    for cap in c.captures.values():inputs[cap['path']]=cap['sha256']
    for p in (root/'evidence/captures').glob('*/text.txt'):inputs[p.relative_to(root).as_posix()]=sha(p)
    descriptors={};results=[];counts=Counter(r['sourceId'] for r in c.rows)
    for key,cap in c.captures.items():
        sid=cap['sourceId'];url=c.ledger.get(sid,{}).get('url',cap['url'])
        descriptors[sid]={'id':sid,'title':key,'url':url,'kind':cap['kind'],'checked':cap['capturedAt'],'limitations':'Captured public publication; numerical adapters are source-local and not executions through user gateways.'}
        results.append({'sourceId':sid,'status':'included' if counts[sid] else 'context-only','reason':f'{counts[sid]} scalar cells from explicitly defined adapters.' if counts[sid] else 'Source captured and registered; no fully verified scalar adapter for its publication format/section. No missing values invented.','checked':cap['capturedAt'],'artifacts':[cap['path']]})
    for key in c.captures:
        if key not in c.used:c.context.append({'captureId':key,'reason':'Context/methodology/contract capture retained; numerical coverage is not asserted.'})
    output={'schemaVersion':1,'benchmarks':c.rows,'inputs':[{'path':p,'sha256':h} for p,h in sorted(inputs.items())],
            'reconciliation':{'observed':len(c.rows),'exclusions':[],'sources':list(descriptors.values()),'source_results':results,'context':c.context,
                'scope':'Explicit public table/cell adapters. Other numeric values in documents are context unless normalized by a reviewed adapter. No universal completeness claim.'}}
    target=root/'evidence/reviewed/observations.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'observations':len(c.rows),'bySource':dict(counts),'captures':len(c.captures),'unscoredContextBlocks':len(c.context)},indent=2))
    return output
if __name__=='__main__':run()
