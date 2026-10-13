"""Offline normalization of archived primary sources and explicitly dated studies.
No network, remote JS, inference, canonical catalogs, or fuzzy model matching.
"""
from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
import csv
import hashlib
import json
import math
import re
from dashboard_source_coverage import validate_capture_reference_identity

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/supplemental'
INPUTS = {}
ROWS = []
CONTEXT = []
EXCLUDED = []
RESULTS = []
with (ROOT/'sources/ledger.csv').open(encoding='utf-8-sig',newline='') as ledger_file:
    LEDGER = {r['source_id']:r for r in csv.DictReader(ledger_file)}

def load(path, kind='json'):
    data = (ROOT/path).read_bytes()
    INPUTS[path] = hashlib.sha256(data).hexdigest()
    text = data.decode('utf-8-sig')
    if kind == 'json': return json.loads(text)
    if kind == 'csv': return list(csv.DictReader(text.splitlines()))
    return text

def public(sid, kind='text'):
    receipt = load(f'evidence/supplemental/{sid}_RECEIPT_2026-10-02.json')
    path = receipt['path']
    data = load(path,kind)
    if INPUTS[path] != receipt['sha256'] or receipt['httpStatus'] != 200:
        raise ValueError(f'Unusable capture {sid}: {receipt}')
    return data

def number(v): return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def leaves(value, prefix=''):
    if isinstance(value,dict):
        for key,item in value.items(): yield from leaves(item,f'{prefix}/{key}')
    elif isinstance(value,list):
        for i,item in enumerate(value): yield from leaves(item,f'{prefix}/{i}')
    elif number(value): yield prefix,value

def context(sid,path,value,reason,date):
    CONTEXT.append({'sourceId':sid,'locator':path,'date':date,'reason':reason,'observations':dict(leaves(value)),'data':value})

def exclude(locator,reason,count=1): EXCLUDED.append({'locator':locator,'reason':reason,'count':count})
def add(sid,model,benchmark,value,unit,effort,date,locator,method,note='',extra=None,source=None):
    if not number(value):
        exclude(locator,'Absent/non-finite numeric value; not a zero score'); return
    ROWS.append({'model':model,'family':'supplemental','benchmark':benchmark,'value':value,'unit':unit,'effort':effort or 'not stated','source':source or LEDGER[sid]['url'],'date':date,'provenance':locator,'methodology':method,'note':note,'sourceId':sid,'context':extra or {}})

class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables=[]; self.table=None; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table': self.table=[]
        elif tag=='tr' and self.table is not None: self.row=[]
        elif tag in ('td','th') and self.row is not None: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(' '.join(' '.join(self.cell).split())); self.cell=None
        elif tag=='tr' and self.row is not None: self.table.append(self.row); self.row=None
        elif tag=='table' and self.table is not None: self.tables.append(self.table); self.table=None

def tables(sid):
    parser=Tables(); parser.feed(public(sid)); return parser.tables

def frontier():
    data=public('FCDATA','json')
    units={'new_score':('%',100,'mergeability rubric'), 'correct':('%',100,'correctness rubric'), 'cost':('USD/task',1,'mean rollout cost'), 'tokens':('tokens/task',1,'mean output tokens'), 'flagged_rate':('%',100,'flagged rate'), 'duration_min':('minutes/task',1,'mean duration'), 'tool_calls':('calls/task',1,'tool calls'), 'steps':('steps/task',1,'steps')}
    for version,v in data.items():
        for model,efforts in v['data'].items():
            for effort,subsets in efforts.items():
                for subset,metrics in subsets.items():
                    loc=f'FCDATA_PUBLIC_2026-10-02.raw#/{version}/data/{model}/{effort}/{subset}'
                    extra={'version':version,'harness':v['harness'].get(model),'subset':subset,'tasks':v['subsets'][subset],'historical':version=='v1'}
                    for field,value in metrics.items():
                        if field in units and number(value):
                            unit,factor,label=units[field]
                            add('FCDATA',model,f'FrontierCode {version} {subset} {label}',value*factor,unit,effort,'2026-10-02',loc+'/'+field,'Cognition primary JSON; '+str(extra['harness'])+'; versions/subsets independent; blocking criteria score zero; not universal success probability',extra=extra)
                        elif value is None: exclude(loc+'/'+field,'Publisher absent value; not inferred')
                        else: context('FCDATA',loc+'/'+field,value,'Unspecified metric semantics; preserved but not scored','2026-10-02')
    # Older selected views are not independently scored again. Full lineage remains input-hashed.
    old=load('evidence/supplemental/historical/model-sources/sources/frontiercode-current.json')
    context('FCDATA','evidence/supplemental/historical/model-sources/sources/frontiercode-current.json',old,'Historical 2026-09-24 selected view; superseded by complete primary capture. Not current-model evidence.','2026-09-24')
    old=load('evidence/supplemental/historical/initial-sources/data/benchmarks.csv','csv')
    selected=[r for r in old if r['source_id']=='cognition_frontiercode']
    context('FCDATA','evidence/supplemental/historical/initial-sources/data/benchmarks.csv#cognition_frontiercode',selected,'Historical 2026-09-23 score/cost/token view duplicates the complete versioned primary dataset; not extra scores.','2026-09-23')
    exclude('evidence/supplemental/historical/initial-sources/data/benchmarks.csv#other-sources','Other families in mixed artifact not selected by this slice; no silent top-N.',len(old)-len(selected))


def mimo():
    pro=next(t for t in tables('MIMO') if t[0][0]=='Benchmark')
    flash=next(t for t in tables('MIMOF') if t[0][0]=='Benchmark')
    if pro != flash: raise ValueError('MiMo mirror table changed; reconcile explicitly')
    count=0
    for i,row in enumerate(pro[1:],1):
        if not any(row[1:]): continue
        for column,model in enumerate(pro[0][1:],1):
            loc=f'MIMO_PUBLIC_2026-10-02.raw#evaluation-table/row/{i}/column/{column}'
            if row[column]=='-': exclude(loc,'Model-card dash: no evaluation reported'); continue
            value=float(row[column]); count+=1
            add('MIMO',model,row[0],value,'Elo' if row[0]=='GDPval-AA 2.1' else '%','not stated','2026-10-02',loc,'Xiaomi author evaluation; exact card benchmark versions; harness not established as Go/CC/OMP; comparators retain publisher labels',extra={'modelCard':'MiMo-V2.6-Pro-RL','mirror':'MIMOF','capturedNotEvaluationDate':True})
    exclude('MIMOF_PUBLIC_2026-10-02.raw#evaluation-table','Identical full evaluation table to MIMO primary; retained mirror receipt, not double-counted',count)
    context('MIMOF','MIMOF_PUBLIC_2026-10-02.raw#evaluation-table',flash,'Identical mirror of Pro card, including Flash results; primary rows sourceId=MIMO','2026-10-02')

AA_PERCENT = {'omniscienceAccuracy','omniscienceHallucinationRate','mlcrOverall','gdpPdfAllPass','gdpvalNormalized','itBenchSre','tau2','tauBanking','terminalbenchHard','terminalBench21','terminalBench40','terminalBenchScience','scicode','lcr','ifbench','hle','gpqa','critpt','automationBenchPartialScore'}
AA_SCORE = {'intelligenceIndex','omniscience','gdpval'}

def aa_rows(models,path,date,historical,source):
    seen={}
    for i,model in enumerate(models):
        identity=model['slug']
        if identity in seen:
            if model != seen[identity]: raise ValueError(f'Conflicting AA record {identity}')
            exclude(f'{path}#model/{i}','Repeated embedded serialization of identical model',len(list(leaves(model))))
            continue
        seen[identity]=model
        loc=f'{path}#model/{i}/{identity}'
        effort=(model.get('effort') or {}).get('label','not stated')
        extra={'slug':identity,'historical':historical,'releaseDate':model.get('releaseDate'),'indexVersion':'v4.3.2; component versions separate','capturedNotEvaluationDate':True}
        for key,value in model.items():
            if key in AA_PERCENT | AA_SCORE and number(value):
                unit='%' if key in AA_PERCENT else ('Elo' if key=='gdpval' else 'index points')
                add('AA',model['name'],f'AA {key}',value*(100 if key in AA_PERCENT else 1),unit,effort,date,loc+'/'+key,'AA primary serialized evaluations; no inference of deployment latency or harness equivalence; '+('historical snapshot' if historical else 'current static capture'),extra=extra,source=source)
            elif key=='capabilities' and isinstance(value,dict):
                for component,score in value.items():
                    if number(score): add('AA',model['name'],'AA capability '+component,score,'index points',effort,date,loc+'/'+key+'/'+component,'AA Intelligence Index domain component; not independent task success',extra=extra,source=source)
            elif key in ('intelligenceIndexCost','intelligenceIndexCostPerTask','intelligenceIndexOutputTokens','intelligenceIndexOutputTokensPerTask','intelligenceIndexTimePerTask'):
                for sub,value2 in leaves(value):
                    unit='USD/task' if key=='intelligenceIndexCostPerTask' else 'USD/evaluation' if key=='intelligenceIndexCost' else 'seconds/task' if key=='intelligenceIndexTimePerTask' else 'tokens/task' if key.endswith('PerTask') else 'tokens/evaluation'
                    add('AA',model['name'],'AA '+key+sub,value2,unit,effort,date,loc+'/'+key+sub,'AA observed evaluation consumption, not subscription cost or client latency',extra=extra,source=source)
            elif key=='intelligenceIndexEvaluations' and isinstance(value,list):
                mapped={'artificial-analysis-long-context-reasoning':'lcr','automationbench-aa':'automationBenchPartialScore','critpt':'critpt','gdp-pdf':'gdpPdfAllPass','gdpval-aa':'gdpval','humanitys-last-exam':'hle','omniscience':'omniscience','scicode':'scicode','terminalbench-4-0':'terminalBench40'}
                for ei,evaluation in enumerate(value):
                    slug=evaluation['slug']
                    eloc=loc+'/'+key+'/'+str(ei)+'/'+slug
                    for field,score in evaluation.items():
                        if not number(score): continue
                        if field=='score' and slug in mapped and model.get(mapped[slug])==score:
                            exclude(eloc+'/'+field,'Identical per-evaluation score already incorporated from named top-level field'); continue
                        unit={'costPerTask':'USD/task','outputTokensPerTask':'tokens/task','timePerTask':'seconds/task'}.get(field)
                        factor=1
                        if field=='score':
                            unit='Elo' if slug in ('aa-briefcase','gdpval-aa') else 'index points' if slug=='omniscience' else '%'
                            factor=100 if unit=='%' else 1
                        if unit:
                            add('AA',model['name'],'AA '+slug+' '+field,score*factor,unit,effort,date,eloc+'/'+field,'AA per-evaluation consumption/score; exact evaluation slug retained; costs unweighted and distinct from weighted index cost decomposition.',extra=extra,source=source)
                        else: context('AA',eloc+'/'+field,score,'Unrecognized evaluation metric unit; not inferred',date)
            elif key in AA_PERCENT | AA_SCORE and value is None: exclude(loc+'/'+key,'Evaluation absent; no score inferred')
            elif list(leaves(value)): context('AA',loc+'/'+key,value,'Metadata, API rate without independent currency contract, or metric with unspecified units; not scored',date)
    return len(seen)

def aa():
    raw=public('AA'); flights=[]
    for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>',raw,re.S):
        item=json.loads(match.group(1))
        if len(item)>1 and isinstance(item[1],str): flights.append(item[1])
    text='\n'.join(flights); decoder=json.JSONDecoder(); models=[]
    for match in re.finditer(r'\{"id":',text):
        try: obj,_=decoder.raw_decode(text[match.start():])
        except ValueError: continue
        if isinstance(obj,dict) and 'intelligenceIndex' in obj: models.append(obj)
    if not models: raise ValueError('AA primary structured models absent')
    count=aa_rows(models,'AA_PUBLIC_2026-10-02.raw','2026-10-02',False,LEDGER['AA']['url'])
    context('AA','AA_PUBLIC_2026-10-02.raw#collection-size',{'uniqueModels':count},'Full embedded collection, not only page model/top-N; scores are source-local, not canonical identities.','2026-10-02')
    old=load('evidence/supplemental/historical/initial-sources/data/aa-models.json')
    aa_rows(old,'evidence/supplemental/historical/initial-sources/data/aa-models.json','2026-09-23',True,'https://artificialanalysis.ai/models/deepseek-v4-1-flash')
    oldcsv=load('evidence/supplemental/historical/initial-sources/data/aa-model-components.csv','csv')
    context('AA','evidence/supplemental/historical/initial-sources/data/aa-model-components.csv',oldcsv,'Historical projected view of aa-models.json, not independent scores; all rows retained without top-N.','2026-09-23')
    oldraw=load('evidence/supplemental/historical/model-sources/sources/AA-MIMO.raw','text')
    exclude('evidence/supplemental/historical/model-sources/sources/AA-MIMO.raw','Historical 2026-09-24 HTML superseded by full static primary capture; no newer evaluation date inferred',1)

STUDY_UNITS={'rate':('%',100),'score_pct':('%',1),'pass_rate':('%',100),'success_rate_expected':('%',100),'cacheHitRate':('%',100),'cache_hit_rate_normalized':('%',100),'cache_hit_rate_typical':('%',100),'cost':('USD/attempt',1),'inputTokens':('tokens/attempt',1),'outputTokens':('tokens/attempt',1),'mean_input_tokens':('tokens/attempt',1),'mean_output_tokens':('tokens/attempt',1),'mean_turns':('turns/attempt',1),'median_duration_seconds':('seconds',1),'effective_cost_per_pass':('USD/success',1),'cost_per_success_normalized':('USD/success',1),'median_cost_per_success_normalized':('USD/success',1)}

def study_summary(sid,model,label,data,date,loc,method,extra):
    for key,value in data.items():
        if key in STUDY_UNITS and number(value):
            unit,factor=STUDY_UNITS[key]
            add(sid,model,label+' '+key,value*factor,unit,'study-fixed',date,loc+'/'+key,method,extra=extra)
    context(sid,loc,data,'Original summary includes exact attempts/tasks/solved/cost denominators; selected metrics appear once as rows, remaining numeric context is not additional scores.',date)

def specpi():
    data=public('SPECPI_DATA','json'); date=data['generatedAt']
    method='SpecPi exploratory study; DeepSeek V4.1 Flash fixed endpoint; repeated/nonrandom small task slices; Pi '+','.join(data['piVersions'])+'; SpecPi v0.33.0 Jev off; OMP version unspecified. No current OMP equivalence.'
    for i,harness in enumerate(data['harnesses']):
        for scope,summary in [('pooled',harness['overall']),('widened',harness['widened'])]+[('sitting_'+s['id'],s) for s in harness['sittings']]:
            study_summary('SPECPI',data['model'],f'{data["benchmark"]} {harness["label"]} {scope}',summary,date,f'SPECPI_DATA_PUBLIC_2026-10-02.raw#/harnesses/{i}/{scope}',method,{'historical':True,'harness':harness['label'],'scope':scope,'tasks':summary.get('tasks'),'attempts':summary.get('attempts')})
    for harness,summary in data['swe']['byHarness'].items():
        study_summary('SPECPI',data['model'],'SWE-bench Verified '+harness,summary,date,'SPECPI_DATA_PUBLIC_2026-10-02.raw#/swe/byHarness/'+harness,method+' SWE-bench verifier.',{'historical':True,'harness':harness,'tasks':12,'attempts':summary['attempts']})
    for row in ROWS:
        if row['sourceId']=='SPECPI':
            row['source']='https://tannermidd.github.io/SpecPi/evaluations/terminal-bench-2.json'
    context('SPECPI','SPECPI_DATA_PUBLIC_2026-10-02.raw',data,'Complete task-level oracle/attempt denominators, paired tests, spreads and metadata; task means not a new model score. Pooled/widened/sittings overlap and must not be combined.',date)
    old=load('evidence/supplemental/historical/harness-studies/evidence/specpi-terminal-bench-2.json')
    context('SPECPI','evidence/supplemental/historical/harness-studies/evidence/specpi-terminal-bench-2.json',old,'Historical 2026-09-22 subset superseded by primary 2026-09-24 dataset; preserved not labelled current.','2026-09-22')
    context('SPECPI','evidence/supplemental/historical/harness-studies/metrics/specpi-normalized.csv',load('evidence/supplemental/historical/harness-studies/metrics/specpi-normalized.csv','csv'),'Historical projected summary; duplicate view, no independent score.','2026-09-22')


def fh():
    data=public('FH_DATA','json'); versions=public('FH_VERSIONS','json'); date=data['generated_at'][:10]
    historical=load('evidence/supplemental/historical/harness-studies/evidence/frontierharness-data.json')
    historical_versions=load('evidence/supplemental/historical/harness-studies/evidence/frontierharness-versions.json')
    context('FH','evidence/supplemental/historical/harness-studies/evidence/frontierharness-data.json',historical,'Historical local capture is byte-identical to the reachable public repository dataset; no second scores.',date)
    context('FH','evidence/supplemental/historical/harness-studies/evidence/frontierharness-versions.json',historical_versions,'Historical pinned study-version view; public repository version metadata is primary.',date)
    method='FrontierHarness v1 frozen Kimi K3 gateway; deterministic verifier, one trial per task, 30 tasks/12 harnesses; golden checkpoint reset; first-turn cache repriced. Historical versions, not current Pi/OMP.'
    for i,h in enumerate(data['harnesses']):
        extra={'historical':True,'harness':h['name'],'version':versions['harnesses'].get(h['name']),'attempts':h['completed'],'tasks':h['expected'],'costedAttempts':sum(number(t.get('cost_first_cold_usd')) for t in h['task_details'])}
        study_summary('FH','Kimi K3','FrontierHarness v1 '+h['name'],h,date,f'FH_DATA_PUBLIC_2026-10-02.raw#/harnesses/{i}',method,extra)
    for row in ROWS:
        if row['sourceId']=='FH':
            row['source']='https://raw.githubusercontent.com/frontier-harness-eval/eval/main/results/eval-data.json'
    context('FH','FH_DATA_PUBLIC_2026-10-02.raw',data,'Complete 360 task-level results, costs/durations/turns and summary denominators. Public capture is current; trial generation date remains historical 2026-08-22. Boolean verifier outcome is task context, not fabricated model score.',date)
    context('FH','FH_VERSIONS_PUBLIC_2026-10-02.raw',versions,'Pinned public study versions; OMP17.4/Pi0.84.2 are not installed/current configurations.',date)
    for name in ('frontierharness-summary.csv','frontierharness-task-level.csv'):
        context('FH','evidence/supplemental/historical/harness-studies/metrics/'+name,load('evidence/supplemental/historical/harness-studies/metrics/'+name,'csv'),'Historical projection of same raw data; no duplicated scores.',date)
    # Article/site are rounded views of the same historical trials, not new samples.
    ts=tables('FH')
    for ti,table in enumerate(ts):
        context('FH',f'FH_PUBLIC_2026-10-02.raw#table/{ti}',table,'Article published 2026-09-01; task illustration table is context, not extra sample. Median cost differs from effective cost; do not equate.','2026-09-01')
    for row in ts[0][1:]:
        summary={'medianCostPerPassUSD':float(row[1][1:]),'passRatePct':float(row[2][:-1]),'cacheHitPct':float(row[3][:-1]),'medianDurationSeconds':sum(int(v)*f for v,f in zip(re.findall(r'\d+',row[4]),[60,1]))}
        context('FH','FH_PUBLIC_2026-10-02.raw#summary/'+row[0],summary,'Rounded article display of historical trial statistics; exact raw summary is primary. No double-counting repeated summaries.','2026-09-01')
    parser=Plain(); parser.feed(public('FH_SITE'))
    context('FH','FH_SITE_PUBLIC_2026-10-02.raw#display',parser.text(),'Linked evaluation site is reachable; exposes same historical harness/rate/cost/duration charts. No published newer trial/version or per-task downloadable dataset in static page. Reuse dated raw dataset, not current-model claims.',date)
    manifest=load('evidence/supplemental/historical/harness-studies/evidence/artifact-manifest.json')
    for entry in manifest:
        original='evidence/supplemental/historical/harness-studies/'+entry['path']
        if original in ('evidence/supplemental/historical/harness-studies/evidence/frontierharness-data.json','evidence/supplemental/historical/harness-studies/evidence/frontierharness-versions.json','evidence/supplemental/historical/harness-studies/evidence/specpi-terminal-bench-2.json'):
            if hashlib.sha256((ROOT/original).read_bytes()).hexdigest()!=entry['sha256']: raise ValueError('Historical manifest mismatch: '+original)
    context('FH','evidence/supplemental/historical/harness-studies/evidence/artifact-manifest.json',manifest,'Historical artifact SHA manifest; selected raw study capture hashes verified when present. Other manifest entries are lineage metadata, not additional sources/trials.',date)
    receipts=load('evidence/supplemental/historical/harness-studies/evidence/new-source-receipts.json')
    context('FH','evidence/supplemental/historical/harness-studies/evidence/new-source-receipts.json',receipts,'Original source exact URLs, captured-at timestamps and hashes for historical FH/SPECPI/COMPOSIO lineage; public recaptures have separate receipts.',date)


def composio():
    ts=tables('COMPOSIO')
    for i,t in enumerate(ts): context('COMPOSIO',f'COMPOSIO_PUBLIC_2026-10-02.raw#table/{i}',t,'Published 2026-08-04 SaaS automated final-state study, not terminal benchmark; task-level oracle checks/context denominators preserved.','2026-08-04')
    table=next(t for t in ts if t[0][:2]==['Harness','Tasks passed'])
    method='Composio SaaS applications; Kimi K3 max OpenRouter; 25 valid final-state tasks per harness, one draw; invalid infrastructure attempts replaced; cost/tool usage slice 24 tasks using 2026-07-30 list pricing. Harness versions unspecified, not current Pi/OMP.'
    for row in table[1:]:
        solved,attempts=map(int,row[1].split('/'))
        extra={'historical':True,'harness':row[0],'solved':solved,'attempts':attempts,'costTasks':24,'pricingDate':'2026-07-30'}
        for label,val,unit in [('pass rate',float(row[2][:-1]),'%'),('median runtime',float(row[3][:-1]),'seconds'),('tool calls',int(row[4]),'calls/24-task slice'),('estimated cost/success',float(row[5][1:]),'USD/success')]:
            add('COMPOSIO','Kimi K3 max','Composio SaaS '+row[0]+' '+label,val,unit,'max','2026-08-04','COMPOSIO_PUBLIC_2026-10-02.raw#overall/'+row[0]+'/'+label,method,extra=extra)
    old=load('evidence/supplemental/historical/harness-studies/metrics/composio-comparisons.csv','csv')
    context('COMPOSIO','evidence/supplemental/historical/harness-studies/metrics/composio-comparisons.csv',old,'Historical manually normalized comparison: Kimi rows duplicate primary article; DeepSeek V4 Flash rows concern a different study not the current ledger URL; not V4.1/current routing.','2026-09-24')
    exclude('evidence/supplemental/historical/harness-studies/metrics/composio-comparisons.csv#DeepSeek','Different study origin not recorded as exact URL in selected historical CSV; context retained, not silently attributed to Kimi primary article',2)


def narrative():
    # Editorial axes are publisher rating units, not percentages. Extract all nine plus overall.
    raw=public('BRIDGE')
    parser=Plain(); parser.feed(raw); text=parser.text()
    for axis in ['Reasoning','Front End','Back End','One Shot','Security','Trustworthiness','Efficiency','Speed','Cost']:
        match=re.search(re.escape(axis)+r' (\d+)(?:st|nd|rd|th) of (\d+) (\d+)',text)
        if not match: raise ValueError('Bridge axis missing '+axis)
        add('BRIDGE','GPT-6.1 Sol','BridgeBench '+axis,int(match[3]),'rating points','not stated','2026-09-29','BRIDGE_PUBLIC_2026-10-02.raw#ratings/'+axis,'Proprietary editorial comparative rating; nine axes, no success denominator or disclosed methodology.',extra={'rank':int(match[1]),'models':int(match[2]),'measuredSuccessRate':False})
    match=re.search(r'Overall rating (\d+)',text)
    add('BRIDGE','GPT-6.1 Sol','BridgeBench Overall',int(match[1]),'rating points','not stated','2026-09-29','BRIDGE_PUBLIC_2026-10-02.raw#overall','Proprietary editorial comparative rating; not probability.')
    context('BRIDGE','BRIDGE_PUBLIC_2026-10-02.raw#article',text,'API tier price/specs/illustrative job costs are contract context, not benchmark. Other-model overall leaderboard labels are a mirror navigation summary, not this page primary axis sample.','2026-09-29')
    for model,cost in [('GPT-6.1 Sol',.72),('GPT-6 Astra',3.26),('GPT-6 Sol',1.05),('GPT-5.6 Sol',1.99)]:
        add('AA61SOL',model,'AA Intelligence Index cost/task',cost,'USD/task','max','2026-09-29','AA61SOL_PUBLIC_2026-10-02.raw#cost-efficiency/'+model,'AA article Intelligence Index v4.3.2; source-local rounded prose cost, not coding-agent cost.',extra={'roundedNarrative':True})
    for model,value in [('GPT-6 Sol',60),('GPT-6.1 Sol',54)]:
        add('AA61SOL',model,'AA Omniscience hallucination rate',value,'%','max','2026-09-29','AA61SOL_PUBLIC_2026-10-02.raw#hallucination/'+model,'AA-Omniscience narrative conditional hallucination rate; not universal error rate.',extra={'roundedNarrative':True})
    for sid in ['AA61SOL','ULTRA','COGN','FC','SPECPI']:
        parser=Plain(); parser.feed(public(sid)); text=parser.text()
        reason={'AA61SOL':'Relative gains and chart-only breakdowns are context; no absolute chart score inferred. Rounded article values distinct from full AA serialized evaluations.', 'ULTRA':'Vendor advertises up to 20x output speed; no measured tokens/s, TTFT or task-duration denominator. Context/API specs and prices only, not latency observations.', 'COGN':'Owner blog republishes rounded FrontierCode1.1 Extended score/cost already included from exact FCDATA; no double-count. Narrative low/medium/max comparisons preserve original models.', 'FC':'Leaderboard landing page is methodology/display mirror of complete FCDATA, no duplicate primary rows.', 'SPECPI':'Current HTML is display/methodology of captured dataset; SWE/terminal tables overlap JSON and are not extra samples.'}[sid]
        context(sid,sid+'_PUBLIC_2026-10-02.raw#prose',text,reason,'2026-09-29' if sid in ('AA61SOL','COGN') else '2026-10-02')
        if sid in ('COGN','FC'): exclude(sid+'_PUBLIC_2026-10-02.raw#display','Display/narrative duplicate of exact FCDATA primary observations',1)
    context('ULTRA','ULTRA_PUBLIC_2026-10-02.raw#advertised-claims',{'outputSpeedMultiplierUpperBound':20,'contextTokens':1000000,'maxOutputTokens':128000,'priceUSDPerMillionTokens':{'cacheHit':.036,'inputCacheMiss':4.35,'output':8.7},'priceCNYPerMillionTokens':{'cacheHit':.25,'inputCacheMiss':30,'output':60}},'Vendor up-to speed claim lacks measured latency denominator; API contract prices and specs, not scored benchmark.','2026-10-02')
    context('AA61SOL','AA61SOL_PUBLIC_2026-10-02.raw#relative-gains',{'intelligenceIndexVsGPT6SolPoints':4,'intelligenceIndexVsGPT56SolPoints':5,'intelligenceIndexBelowAstraPoints':1,'AA_BriefcaseV11GainPoints':4,'GDPvalAA21GainPoints':5,'terminalBench40GainPoints':12,'HLEGainPoints':5,'GDPpdfGainPoints':6,'omniscienceAccuracyGainPoints':8,'codingAgentIndexMaxGainPoints':3,'codingAgentIndexXhighVsAstraPoints':1,'codingAgentIndexXhighVsSolMaxPoints':6,'codingAgentIndexXhighVsOwnMaxPoints':3,'outputTokensIncreasePctRange':[10,30],'AA_BriefcaseEloGainApprox':80},'Relative/approximate narrative differences; not absolute model scores or equivalent harness measurements.','2026-09-29')

class Plain(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self,t,a):
        if t in ('script','style'): self.skip+=1
    def handle_endtag(self,t):
        if t in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self,d):
        if not self.skip: self.parts.append(d)
    def text(self): return ' '.join(' '.join(self.parts).split())


def exhaustive_captures():
    """Register the bounded capture inventory, including unsuccessful discoveries."""
    registry = load('data/cybersecurity-exhaustive-capture-references.json')
    if registry.get('schemaVersion') != 1:
        raise ValueError('Invalid exhaustive capture reference registry')
    declarations = []
    counts = Counter(row['sourceId'] for row in ROWS)
    for reference in registry['references']:
        sid, url = reference['sourceId'], reference['url']
        receipt_path = reference['receiptPath']
        receipt = load(receipt_path)
        validate_capture_reference_identity(reference, receipt)
        raw_path = receipt['path']
        raw = (ROOT / raw_path).read_bytes()
        INPUTS[raw_path] = hashlib.sha256(raw).hexdigest()
        if INPUTS[raw_path] != receipt['sha256']:
            raise ValueError('Exhaustive capture hash mismatch: ' + raw_path)
        artifacts = [receipt_path, raw_path]
        extraction = receipt.get('textExtraction')
        if extraction:
            load(extraction['path'], 'text')
            if INPUTS[extraction['path']] != extraction['sha256']:
                raise ValueError('Exhaustive extraction hash mismatch')
            artifacts.append(extraction['path'])
        success = receipt['httpStatus'] == 200
        count = counts[sid]
        if not success and count:
            raise ValueError('Failed HTTP capture cannot produce numeric observations')
        if sid in LEDGER and LEDGER[sid]['url'] != url:
            raise ValueError('Exhaustive source identity conflicts with ledger')
        LEDGER.setdefault(sid, {'url': url})
        declarations.append(dict(id=sid, title=reference['name'].replace('_', ' '), url=url,
            kind='benchmark' if success else 'unknown', checked=receipt['capturedAt'],
            limitations='Static archived public aggregate/context bytes; no benchmark execution or route calibration.'))
        existing = next((item for item in RESULTS if item['sourceId'] == sid), None)
        if existing is not None:
            for path in artifacts:
                if path not in existing['artifacts']:
                    existing['artifacts'].append(path)
        else:
            reason = ('Captured source context; only explicitly adapted numeric observations are scores.'
                      if success else f'HTTP {receipt["httpStatus"]} capture; source remains unresolved, no numeric observation inferred.')
            RESULTS.append(dict(sourceId=sid, status='included' if count else 'context-only' if success else 'unavailable',
                checked=receipt['capturedAt'], httpStatus=receipt['httpStatus'], benchmarkCount=count,
                reason=reason, artifacts=artifacts))
            context(sid, raw_path + '#capture-disposition', dict(httpStatus=receipt['httpStatus']),
                    reason, receipt['capturedAt'][:10])
    return declarations


def main():
    for sid in sorted({'FC','FCDATA','MIMO','MIMOF','AA','AA61SOL','ULTRA','SPECPI','FH','COMPOSIO','BRIDGE','COGN'}): public(sid)
    frontier(); mimo(); aa(); specpi(); fh(); composio(); narrative()
    from supplemental_registered_refs import extend
    reference_sources=extend(globals())
    from supplemental_cybersecurity import extend as extend_cybersecurity
    reference_sources.extend(extend_cybersecurity(globals()))
    from supplemental_vals_exhaustive import contribute as contribute_vals
    from supplemental_frontier_exhaustive import contribute as contribute_frontier
    from supplemental_openmodels_exhaustive import contribute as contribute_openmodels
    from supplemental_publishers_exhaustive import contribute as contribute_publishers
    for contribute in (contribute_vals, contribute_frontier, contribute_openmodels, contribute_publishers):
        reference_sources.extend(contribute(globals()))
    reference_sources.extend(exhaustive_captures())
    sources_by_id, ids_by_url = {}, {}
    for source in reference_sources:
        previous = sources_by_id.get(source['id'])
        if previous is not None and previous['url'] != source['url']:
            raise ValueError('Conflicting exhaustive source descriptor identity')
        if source['url'] in ids_by_url and ids_by_url[source['url']] != source['id']:
            raise ValueError('Duplicate source IDs for an exact public origin')
        sources_by_id.setdefault(source['id'], source)
        ids_by_url[source['url']] = source['id']
    reference_sources = list(sources_by_id.values())
    counts=Counter(r['sourceId'] for r in ROWS)
    for sid in sorted({'FC','FCDATA','MIMO','MIMOF','AA','AA61SOL','ULTRA','SPECPI','FH','COMPOSIO','BRIDGE','COGN'}):
        receipt=load(f'evidence/supplemental/{sid}_RECEIPT_2026-10-02.json')
        RESULTS.append({'sourceId':sid,'status':'included' if counts[sid] else 'context-only','checked':receipt['capturedAt'],'httpStatus':receipt['httpStatus'],'benchmarkCount':counts[sid],'reason': 'Primary observation rows and full contextual lineage available.' if counts[sid] else {'FC':'Methodology/display mirror; exact data primary FCDATA.','MIMOF':'Identical evaluation table mirror; Flash results included via MIMO primary.','COGN':'Rounded owner-blog FrontierCode display duplicates exact FCDATA.','ULTRA':'Vendor product/contract and up-to speed claims; no measured latency units.'}[sid],'artifacts':[receipt['path'],f'evidence/supplemental/{sid}_RECEIPT_2026-10-02.json']})
    def archive_locator(locator):
        path,separator,suffix=locator.partition('#')
        if not path.startswith(('evidence/','sources/','data/','scripts/')):
            path='evidence/supplemental/'+path
        return path+separator+suffix
    for row in ROWS: row['provenance']=archive_locator(row['provenance'])
    for item in CONTEXT+EXCLUDED: item['locator']=archive_locator(item['locator'])
    for entry in RESULTS:
        sid=entry['sourceId']
        paths=set(entry['artifacts'])
        paths.update(row['provenance'].partition('#')[0] for row in ROWS if row['sourceId']==sid)
        paths.update(item['locator'].partition('#')[0] for item in CONTEXT if item['sourceId']==sid)
        for path in list(paths):
            receipt_path=path.replace('_PUBLIC_','_RECEIPT_').removesuffix('.raw')+'.json'
            if '_PUBLIC_' in path and receipt_path in INPUTS: paths.add(receipt_path)
        entry['artifacts']=sorted(path for path in paths if path in INPUTS)
    artifacts=[]
    for path,sha in sorted(INPUTS.items()):
        if path in {'sources/freshness.json', 'data/cybersecurity-exhaustive-capture-references.json'}:
            # Shared registry accounting is owned by the coverage backend.
            continue
        included=sum(row['provenance'].partition('#')[0]==path for row in ROWS)
        exclusions=[item for item in EXCLUDED if item['locator'].partition('#')[0]==path]
        excluded=sum(item['count'] for item in exclusions)
        contextual=sum(item['locator'].partition('#')[0]==path for item in CONTEXT)
        artifacts.append({'path':path,'sha256':sha,'kind':'capture-receipt' if '_RECEIPT_' in path else 'historical-source' if '/historical/' in path else 'primary-static-capture','observed':included+excluded+contextual,'included':included,'excluded':excluded,'exclusions':exclusions,'contextRecords':contextual,'countBasis':'Normalized score/value decisions plus explicit unavailable/duplicate/excluded decisions plus contextual records; overlapping raw numeric leaves are not independent observations.'})
    result={'schemaVersion':1,'benchmarks':ROWS,'inputs':[{'path':p,'sha256':sha} for p,sha in sorted(INPUTS.items())],'reconciliation':{'source_results':RESULTS,'observed':len(ROWS)+sum(e['count'] for e in EXCLUDED)+len(CONTEXT),'included':len(ROWS),'excluded':sum(e['count'] for e in EXCLUDED),'exclusions':EXCLUDED,'artifacts':artifacts,'context':CONTEXT,'notes':['Complete source-local rows; no top-N, fuzzy mapping or current-model equivalence.','Dates distinguish archival capture from historical evaluation publication.','Context raw task/summary numeric leaves deliberately do not count as independent scores.','Primary and historical captures/rounded narrative retain separate provenance; do not aggregate repeated views as trials.','AA Slopalytics mirror is a separate producer; this artifact independently archives primary page plus dated historical snapshot.','Artifact observed counts use normalized value decisions plus contextual records, not byte counts, trials or overlapping raw numeric-leaf counts.']}}
    result['reconciliation']['sources']=reference_sources
    result['reconciliation']['observed']=sum(item['observed'] for item in artifacts)
    (OUT/'SOURCE_DASHBOARD_OBSERVATIONS_2026-10-02.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps({'benchmarks':len(ROWS),'sources':len(RESULTS),'sourceCounts':dict(counts),'inputs':len(INPUTS),'excluded':sum(e['count'] for e in EXCLUDED),'contextRecords':len(CONTEXT)},indent=2))

if __name__=='__main__': main()
