#!/usr/bin/env python3
"""Explicit, on-demand NaN usage snapshot. Never calls chat completions or logs keys.

Run manually with NAN_API_KEY in the environment. The output is local-only and
ignored by Git. Usage totals are taken from the provider's full-window totals,
NOT from the possibly paginated daily rows.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
import argparse,json,os,sys,tempfile
from nan_quota_balance import ROOT,KEYS,validate_usage,load_config,nonnegative_int
API='https://api.nan.builders/v1'
OUTPUT=ROOT/'validation/nan-usage-current.json'

def normalized_report(report,at:datetime,authorized_offers=()):
    policy,inventory,offerings=load_config()
    month=at.astimezone(timezone.utc).strftime('%Y-%m')
    start=month+'-01';end=at.astimezone(timezone.utc).date().isoformat()
    if not isinstance(report,dict) or report.get('object')!='usage.report' or report.get('start_date')!=start or report.get('end_date')!=end:
        raise ValueError('NaN usage API did not return the exact requested UTC calendar-month window')
    totals=report.get('totals')
    if not isinstance(totals,dict) or not isinstance(totals.get('by_model'),list) or not nonnegative_int(totals.get('total_tokens')):
        raise ValueError('Missing or incomplete monthly by_model totals: do not assume absent records are zeros')
    wanted={offerings[key]['compatibility']['selector'].split('/',1)[1]:key for key in KEYS}
    counts={key:0 for key in KEYS};seen=set();summed=0
    for row in totals['by_model']:
        if not isinstance(row,dict) or not isinstance(row.get('model'),str) or not nonnegative_int(row.get('total_tokens')):
            raise ValueError('Model totals must have valid model and total_tokens')
        model=row['model']
        if model in seen:raise ValueError('Repeated model in provider totals: refusing to double count')
        seen.add(model);summed+=row['total_tokens']
        if 'prompt_tokens' in row and 'completion_tokens' in row and (not nonnegative_int(row['prompt_tokens']) or not nonnegative_int(row['completion_tokens']) or row['prompt_tokens']+row['completion_tokens']!=row['total_tokens']):
            raise ValueError('Provider total_tokens mismatch with input and output counters')
        if model in wanted:counts[wanted[model]]=row['total_tokens']
    if summed!=totals['total_tokens']:
        raise ValueError('Usage window total differs from the sum of by_model entries')
    result={'schemaVersion':1,'month':month,'observedAt':at.astimezone(timezone.utc).isoformat(),'source':'provider-normalized',
       'approximate':False,'consumed':counts,'verifiedOffers':list(authorized_offers)}
    return validate_usage(result)

def parse_models(result):
    if not isinstance(result,dict) or not isinstance(result.get('data'),list):raise ValueError('/v1/models did not return a model list')
    offers=load_config()[2]
    present={item['id'] for item in result['data'] if isinstance(item,dict) and isinstance(item.get('id'),str)}
    return [key for key in KEYS if offers[key]['compatibility']['selector'].split('/',1)[1] in present]

def fetch_json(path,key):
    if not key or len(key)>1000 or any(x in key for x in '\r\n'):
        raise ValueError('NAN_API_KEY must be supplied as a private environment variable')
    url=API+path
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,request,fp,code,message,headers,newurl):return None
    opener=build_opener(NoRedirect)
    with opener.open(Request(url,headers={'Authorization':'Bearer '+key,'Accept':'application/json','User-Agent':'agent-profile-lab/manual-usage'}),timeout=20) as reply:
        if reply.geturl()!=url:raise ValueError('Unexpected usage API origin')
        if reply.status!=200:raise ValueError('NaN usage request was not successful')
        body=reply.read(2_000_001)
        if len(body)>2_000_000:raise ValueError('Unexpected oversized provider response')
    return json.loads(body)

def private_write(path:Path,contents:dict,overwrite:bool):
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(contents,ensure_ascii=False,indent=2)+'\n'
    fd,tmp=tempfile.mkstemp(prefix='.nan-usage-',suffix='.tmp',dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as fh:fh.write(payload)
        if path.exists() and not overwrite:raise FileExistsError('Usage file exists; pass --overwrite to replace explicitly')
        os.replace(tmp,path)
        os.chmod(path,0o600)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=OUTPUT)
    ap.add_argument('--overwrite',action='store_true')
    ap.add_argument('--check-model-list',action='store_true',help='Optionally confirm IDs listed by /v1/models; not a live inference/tool-call test')
    args=ap.parse_args()
    key=os.environ.get('NAN_API_KEY')
    if not key:ap.error('NAN_API_KEY missing; no remote request performed')
    now=datetime.now(timezone.utc);month=now.strftime('%Y-%m');params=f'/usage?start_date={month}-01&end_date={now.date().isoformat()}'
    try:
        data=fetch_json(params,key)
        routes=parse_models(fetch_json('/models',key)) if args.check_model_list else []
        normalized=normalized_report(data,now,routes)
        private_write(args.output,normalized,args.overwrite)
        print(json.dumps({'status':'saved-local-only','path':str(args.output),'month':month,'offeringsInModelList':routes,
          'usageSource':'provider-normalized','isRealtimeInferenceTest':False,'inferencesSent':0},ensure_ascii=False))
    except (HTTPError,URLError,ValueError,FileExistsError,json.JSONDecodeError) as e:
        # No headers, request dumps or credentials in stderr.
        kind='HTTP '+str(e.code) if isinstance(e,HTTPError) else type(e).__name__
        print(f'NaN usage could not be normalized: {kind}; no balance changed. Check the date, plan and NaN service.',file=sys.stderr)
        raise SystemExit(2)
if __name__=='__main__':main()
