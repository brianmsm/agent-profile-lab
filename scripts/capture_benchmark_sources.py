#!/usr/bin/env python3
"""Manual opt-in capture of explicitly registered public benchmark sources.

This command is not imported or called by rebuild/check_project. Public bytes are
archived as data, never executed. Fetch and activation are separate operations.
"""
from __future__ import annotations
import argparse, hashlib, json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=30_000_000
PUBLIC_HOSTS={'stencil.so','artificialanalysis.ai','www.anthropic.com','platform.claude.com','support.claude.com','nan.builders','harnessrank.net','www.databricks.com','arxiv.org','export.arxiv.org','blog.can.ac','aider.chat','gorilla.cs.berkeley.edu','mcpmark.ai','servicenow.github.io','bird-interact.github.io','livesqlbench.ai','www.livesqlbench.ai','www.codereviewbench.com','codereviewbench.com','www.skillsbench.ai','skillsbench.ai','hal.cs.princeton.edu','huggingface.co','cdn-lfs.huggingface.co','www-cdn.anthropic.com'}
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def validate_url(url):
    p=urlparse(url)
    if p.scheme!='https' or p.hostname not in PUBLIC_HOSTS or p.username or p.password or p.port not in (None,443):
        raise ValueError('Only explicitly allowed public HTTPS publication hosts are supported')
class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(source):
    if not source['sourceId'].replace('-','').isalnum():raise ValueError('Invalid source id')
    r={'id':source['id'],'sourceId':source['sourceId'],'url':source['url'],'kind':source.get('kind','benchmark'),'capturedAt':datetime.now(timezone.utc).isoformat(),'mode':'manual-public-get','evaluationDate':None,'noInference':True}
    try:
        validate_url(source['url'])
        request=Request(source['url'],headers={'User-Agent':'Mozilla/5.0 (manual academic source verification)'})
        with build_opener(PublicRedirect()).open(request,timeout=30) as response:
            body=response.read(MAX_BYTES+1)
            if len(body)>MAX_BYTES:raise ValueError('Capture exceeds byte limit')
            r.update(httpStatus=response.status,finalUrl=response.url,contentType=response.headers.get('Content-Type',''),headers={k:v for k,v in response.headers.items() if k.lower() in {'etag','last-modified','date'}})
        sha=hashlib.sha256(body).hexdigest();suffix='.pdf' if body.startswith(b'%PDF') else '.raw'
        path=ROOT/'evidence/captures'/source['sourceId']/(r['capturedAt'][:10]+'-'+sha[:12]+suffix)
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.read_bytes()!=body:raise ValueError('Immutable artifact collision')
        else:path.write_bytes(body)
        r.update(path=path.relative_to(ROOT).as_posix(),sha256=sha,bytes=len(body),status='captured',method='Public source bytes; capture time is not the evaluation date.')
    except Exception as error:r.update(status='unavailable',error=str(error),httpStatus=getattr(error,'code',None))
    return r

def approve(stage_path):
    stage_path=stage_path.resolve()
    if not stage_path.is_relative_to(ROOT.resolve()):raise ValueError('Stage must remain in workspace')
    stage=read(stage_path)
    if stage.get('mode')!='manual-public-get' or not isinstance(stage.get('captures'),list):raise ValueError('Invalid staging receipt')
    path=ROOT/'sources/reviewed-captures.json';index=read(path);current={r['id']:r for r in index['captures']}
    for r in stage['captures']:
        if r.get('status')!='captured':continue
        source=(ROOT/r['path']).resolve()
        if not source.is_relative_to((ROOT/'evidence/captures').resolve()) or source.is_symlink():raise ValueError('Unsafe artifact')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=r['sha256'] or source.stat().st_size!=r['bytes']:raise ValueError('SHA/size mismatch')
        previous=current.get(r['id'])
        if previous and previous['sha256']!=r['sha256']:
            key=r['id']+'@'+previous['sha256'][:12];current[key]={**previous,'id':key}
        current[r['id']]=r
    index['captures']=list(current.values());dump(path,index)
    failures=[r for r in stage['captures'] if r.get('status')!='captured']
    if failures:dump(ROOT/'sources/capture-failures.json',{'mode':'manual','attempts':failures})
    print(json.dumps({'approved':sum(r.get('status')=='captured' for r in stage['captures']),'unavailable':len(failures)}))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fetch',action='store_true');p.add_argument('--source-list',default='catalog/benchmark-sources.json')
    p.add_argument('--ids');p.add_argument('--stage',default='generated/manual-capture-stage.json');p.add_argument('--approve')
    a=p.parse_args()
    if a.approve:
        if a.fetch:raise ValueError('Fetching and approval are separate operations')
        approve(ROOT/a.approve);return
    sources=read(ROOT/a.source_list)['sources']
    if not a.fetch or not a.ids:
        print(json.dumps({'mode':'read-only','sources':[s['id'] for s in sources],'instruction':'Explicit --fetch --ids required; inspect the staged receipts before --approve.'},indent=2));return
    wanted={s['id'] for s in sources} if a.ids=='all' else set(a.ids.split(','))
    if wanted-{s['id'] for s in sources}:raise ValueError('Unknown source id')
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(fetch,[s for s in sources if s['id'] in wanted]):
            results.append(r);print(r['id'],r['status'],r.get('bytes',r.get('error')),flush=True)
    destination=(ROOT/a.stage).resolve()
    if not destination.is_relative_to(ROOT.resolve()):raise ValueError('Stage must remain in workspace')
    dump(destination,{'mode':'manual-public-get','captures':results,'inferencesSent':0})
if __name__=='__main__':main()
