"""Account for explicitly registered residual URLs without recursive discovery."""
import hashlib
import json
import re

REFERENCES = [
    ('MIMO_CARD_MD','https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Pro-RL/raw/main/README.md'),
    ('MIMOF_CARD_MD','https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Flash-RL/raw/main/README.md'),
    ('FH_GITHUB_TREE','https://api.github.com/repos/frontier-harness-eval/eval/git/trees/main?recursive=1'),
    ('AA_GPT41','https://artificialanalysis.ai/models/gpt-4-1'),
    ('ANTH_FABLE51','https://www.anthropic.com/news/claude-fable-5-1'),
    ('VALS_OPUS55','https://www.vals.ai/models/anthropic_claude-opus-5-5'),
    ('VALS_SONNET55','https://www.vals.ai/models/anthropic_claude-sonnet-5-5'),
]


def extend(api):
    load, context, exclude, add = (api[k] for k in ('load','context','exclude','add'))
    rows, results = api['ROWS'],api['RESULTS']
    declarations=[]
    for name,url in REFERENCES:
        sid='URL-'+hashlib.sha256(url.encode()).hexdigest()[:20]
        api['LEDGER'][sid]={'url':url}
        receipt_path=f'evidence/supplemental/{name}_RECEIPT_2026-10-02.json'
        receipt=load(receipt_path)
        raw=load(receipt['path'],'text')
        if api['INPUTS'][receipt['path']] != receipt['sha256']: raise ValueError('Receipt hash mismatch: '+name)
        date=receipt['capturedAt'][:10]
        declarations.append({'id':sid,'title':url,'url':url,'kind':'benchmark' if name.startswith(('VALS_','AA_')) else 'mirror' if name.endswith('_MD') else 'press' if name.startswith('ANTH_') else 'code','checked':receipt['capturedAt'],'limitations':'Only this explicitly registered URL captured; no recursive source/model mapping.'})
        status='context-only'
        reason=''
        start=len(rows)
        if receipt['httpStatus'] != 200:
            status='unavailable'
            reason=f'Exact public GET returned HTTP {receipt["httpStatus"]}: {receipt["error"]}; archived response is not an evaluation. No inferred alternate origin or score.'
            context(sid,receipt['path']+'#http-error',{'status':receipt['httpStatus'],'error':receipt['error'],'responseBody':raw},reason,date)
        elif name.endswith('_MD'):
            section=raw.split('## 3. Evaluation Results',1)[1].split('## 4.',1)[0]
            table=[[cell.strip() for cell in line.strip().strip('|').split('|')] for line in section.splitlines() if line.strip().startswith('|')]
            primary={(r['model'],r['benchmark'],r['value']) for r in rows if r['sourceId']=='MIMO'}
            count=0
            for row in table[2:]:
                for ci,model in enumerate(table[0][1:],1):
                    try: score=float(row[ci])
                    except ValueError: continue
                    if (model,row[0],score) not in primary: raise ValueError('Markdown card no longer mirrors incorporated table: '+name)
                    count+=1
            reason=f'Raw model-card Markdown reachable; all {count} numeric evaluation cells exactly match MIMO primary comparative table. Mirror, not additional scores.'
            exclude(receipt['path']+'#evaluation-table',reason,count)
            context(sid,receipt['path']+'#markdown',raw,reason,date)
        elif name=='FH_GITHUB_TREE':
            tree=json.loads(raw)
            reason='Exact GitHub recursive tree reachable; discovery/code metadata only. Referenced FH data/version files are already separately captured. No recursive GETs and no tree metadata converted into model scores.'
            context(sid,receipt['path']+'#tree',tree,reason,date)
        elif name=='AA_GPT41':
            parser=api['Plain'](); parser.feed(raw); text=parser.text()
            speed=re.search(r'Speed # \d+ / \d+ ([\d.]+) Output tokens per second',text)
            if not speed: raise ValueError('GPT-4.1 measured speed summary missing')
            add(sid,'GPT-4.1','AA output speed (default 10k input workload)',float(speed[1]),'tokens/s','non-reasoning',date,receipt['path']+'#model-summary/speed','AA measured API-provider performance; deprecated model, only default 10k input-token workload remains updated. Summary provider not named here; do not infer Go/CC/OMP latency.',extra={'workloadInputTokens':10000,'deprecated':True,'direction':'higher','provider':'summary aggregate; not specified in displayed card'},source=url)
            # Reconcile exact serialized target scores against the existing AA capture.
            flights=[]
            for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>',raw,re.S):
                item=json.loads(match.group(1))
                if len(item)>1 and isinstance(item[1],str): flights.append(item[1])
            flight='\n'.join(flights); decoder=json.JSONDecoder(); target=None
            for match in re.finditer(r'\{"id":',flight):
                try: obj,_=decoder.raw_decode(flight[match.start():])
                except ValueError: continue
                if isinstance(obj,dict) and obj.get('slug')=='gpt-4-1' and 'intelligenceIndex' in obj:
                    target=obj; break
            if target is None: raise ValueError('GPT-4.1 target serialization absent')
            existing={(r['benchmark'],r['value']) for r in rows if r['sourceId']=='AA' and r['context'].get('slug')=='gpt-4-1' and r['date']=='2026-10-02'}
            duplicate=0
            for key,value in target.items():
                if key in api['AA_PERCENT']|api['AA_SCORE'] and api['number'](value):
                    score=value*(100 if key in api['AA_PERCENT'] else 1)
                    if ('AA '+key,score) in existing: duplicate+=1
                    else: raise ValueError('GPT-4.1 primary evaluation differs from incorporated collection: '+key)
            exclude(receipt['path']+'#serialized-target/duplicate-scores','Exact target evaluation scores already incorporated from complete AA primary collection.',duplicate)
            reason='Reachable deprecated GPT-4.1 page; exact named evaluation scores duplicate incorporated AA collection. Adds only explicit default-10k measured output speed. Other workload results historical/not updated, and undisclosed units/metadata remain context.'
            context(sid,receipt['path']+'#serialized-target',target,reason,date)
            context(sid,receipt['path']+'#prose',text,reason,date)
        elif name.startswith('VALS_'):
            parser=api['Plain'](); parser.feed(raw); text=parser.text()
            model='Claude Opus 5.5' if name=='VALS_OPUS55' else 'Claude Sonnet 5.5'
            section=text.split('Benchmarks Accuracy Rankings',1)[1].split('Proprietary Benchmarks',1)[0]
            pattern=r'\s*(.+?)\s+(\d+(?:\.\d+)?)\s*%\s*(?:±\s*(\d+(?:\.\d+)?)\s*)?(\d+)\s*/\s*(\d+)'
            matches=list(re.finditer(pattern,section))
            if not matches or section[matches[-1].end():].strip(): raise ValueError('Unparsed Vals benchmark table remainder: '+name)
            methodology='Vals independently reported benchmark accuracy; current page table, default provider Anthropic and compute effort max, temperature1. Per-benchmark providers/settings may differ. Server-side fallbacks can contribute; not base-model-only/Claude subscription/OMP measurement. Evaluation task denominators not disclosed in current table; leaderboard model-count denominators are NOT trial counts.'
            for match in matches:
                label=match[1].strip()
                meta={'direction':'higher','benchmarkVersion':label,'provider':'Anthropic default; per-benchmark exceptions possible','fallbackPolicy':'default displayed score; server-side refusal fallbacks may contribute','leaderboardRank':int(match[4]),'leaderboardModels':int(match[5]),'taskDenominator':None,'reportedUncertaintyPct':float(match[3]) if match[3] else None,'captureNotEvaluationDate':True}
                add(sid,model,'Vals '+label,float(match[2]),'%','max (page default)',date,receipt['path']+'#current-benchmark-table/'+label,methodology,extra=meta,source=url)
            summary=re.search(r'Cost / Test \(Vals Index\) \$ ([\d.]+) Latency (\d+) min (\d+) s Fallback Rate ([\d.]+)% Refusal Rate ([\d.]+)%',text)
            if not summary: raise ValueError('Vals model summary metric group absent: '+name)
            for label,value,unit,direction in [('Vals Index cost/test',float(summary[1]),'USD/test','lower'),('Vals reported latency',int(summary[2])*60+int(summary[3]),'seconds','lower'),('Vals fallback rate',float(summary[4]),'%','lower'),('Vals refusal rate',float(summary[5]),'%','lower')]:
                add(sid,model,label,value,unit,'max (page default)',date,receipt['path']+'#model-summary/'+label,methodology,extra={'direction':direction,'taskDenominator':None,'aggregation':'Not specified in displayed summary; do not infer per-task mean or client latency','fallbackPolicy':'server-side fallbacks reported; not standalone base-model score','captureNotEvaluationDate':True},source=url)
            reason=f'Public model page reachable; complete {len(matches)}-benchmark current table plus four consumption/fallback/refusal summary metrics incorporated. Historical dated Updates narrative and contract metadata remain contextual; no silent top-N or CVP/unknown-ID mapping.'
            context(sid,receipt['path']+'#current-table-original',section,'Complete original current accuracy table with uncertainty/rank/model-count denominators; summary accuracy duplicates Vals Index table row.',date)
            update=text.split('Updates ',1)[1].split('Benchmarks Models Comparison Vals Smith App Reports',1)[0]
            context(sid,receipt['path']+'#dated-updates',update,'Historical publication narrative differs from current table. Preserve exact older scores/fallback failures/task denominators/effort exception (Terminal-Bench2.1 high), not a fresh rerun or duplicate current rows.','2026-09-22' if name=='VALS_OPUS55' else '2026-09-28')
            context(sid,receipt['path']+'#page-prose',text,'Full page units/method/specs; release/catalog-navigation numeric metadata not converted into scores.',date)
        added=len(rows)-start
        if added: status='included'
        results.append({'sourceId':sid,'status':status,'checked':receipt['capturedAt'],'httpStatus':receipt['httpStatus'],'benchmarkCount':added,'reason':reason,'artifacts':[receipt['path'],receipt_path]})
    freshness=load('sources/freshness.json')
    old=next(item for item in freshness if item['source_id']=='GO-OLD')
    raw=load('evidence/supplemental/historical/model-sources/sources/GO-OLD.raw','text')
    archive='evidence/supplemental/historical/model-sources/sources/GO-OLD.raw'
    if api['INPUTS'][archive] != old['sha256']: raise ValueError('GO-OLD historical raw differs from explicit freshness receipt')
    sid='GO-OLD'
    declarations.append({'id':sid,'title':'OpenCode Go historical documentation','url':old['url'],'kind':'contract','checked':old['retrieved_at_utc'],'limitations':'Historical exact raw/HTTP freshness record from2026-09-23; not independently refreshed in this supplemental extension.'})
    context(sid,'evidence/supplemental/historical/model-sources/sources/GO-OLD.raw',raw,'Historical contract raw found at explicit freshness.raw_location, exact SHA256 verified. No benchmark and no fake current freshness.',old['retrieved_at_utc'][:10])
    context(sid,'sources/freshness.json#GO-OLD',old,'Original HTTP200/status/time/cache/header/hash historical receipt; current source retrieval not implied.',old['retrieved_at_utc'][:10])
    results.append({'sourceId':sid,'status':'context-only','checked':old['retrieved_at_utc'],'httpStatus':old['status'],'benchmarkCount':0,'reason':'Historical contract capture reachable locally and exact receipt SHA verified; no scored benchmark and no fresh retrieval claim.','artifacts':[archive,'sources/freshness.json']})
    # Explicit captured asset endpoints, not arbitrary URLs found in raw context.
    for name,owner,kind,reason in [
        ('SPECPI_DATA','SPECPI','benchmark','Exact captured study JSON; numeric observations are owned by SPECPI summary rows, not emitted again under this origin identity.'),
        ('FH_DATA','FH','benchmark','Exact captured repository study JSON; numeric observations are owned by FH summary rows, not emitted again under this origin identity.'),
        ('FH_SITE','FH','mirror','Captured linked evaluation site displays the historical FH study; discovery/display context, not additional trials or current-harness evidence.'),
        ('FH_VERSIONS','FH','code','Captured pinned study-version metadata; supports historical FH attribution but contains no independent quality evaluation.'),
    ]:
        receipt_path=f'evidence/supplemental/{name}_RECEIPT_2026-10-02.json'
        receipt=load(receipt_path)
        if receipt['httpStatus']!=200: raise ValueError('Previously captured explicit endpoint unavailable: '+name)
        sid='URL-'+hashlib.sha256(receipt['requestedUrl'].encode()).hexdigest()[:20]
        declarations.append({'id':sid,'title':receipt['requestedUrl'],'url':receipt['requestedUrl'],'kind':kind,'checked':receipt['capturedAt'],'limitations':reason})
        results.append({'sourceId':sid,'status':'context-only','checked':receipt['capturedAt'],'httpStatus':receipt['httpStatus'],'benchmarkCount':0,'reason':reason,'parentSourceId':owner,'artifacts':[receipt['path'],receipt_path]})
    return declarations
