#!/usr/bin/env python3
"""Optional local per-subtask selector with atomic reservations, NO model/API calls.

This is a hook to invoke explicitly *before* delegating a task. It does not
intercept Gentle/OMP, alter active native profiles or hold credentials.
"""
from __future__ import annotations
import argparse,hashlib,json,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
from nan_quota_balance import ROOT,KEYS,validate_usage,plan_nan_task,parse_date,load_config
DB=ROOT/'validation/nan-quota-dispatch.sqlite'

def connect(path:Path,write:bool):
    if not write and not path.exists():return None
    path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path if write else f'file:{path}?mode=ro',uri=not write,timeout=20,isolation_level=None)
    conn.row_factory=sqlite3.Row
    if write:
        conn.execute('PRAGMA busy_timeout=20000')
        conn.execute('''CREATE TABLE IF NOT EXISTS requests (
          task_id TEXT PRIMARY KEY, month TEXT NOT NULL, model_key TEXT NOT NULL,
          request_hash TEXT NOT NULL, reserved_tokens INTEGER NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('reserved','settled','released')),
          actual_tokens INTEGER, created_at TEXT NOT NULL, finished_at TEXT)''')
    return conn

def private_json(path:Path):
    data=json.loads(path.read_text(encoding='utf-8'))
    if any(k in data for k in ('api_key','key','token','authorization','Authorization')):
        raise ValueError('Credentials are never accepted in usage snapshots')
    return validate_usage(data)

def ledger(conn,month,observed_at):
    reserved={k:0 for k in KEYS};count={k:0 for k in KEYS}
    if conn is None:return {'reserved':reserved,'count':count}
    for row in conn.execute('SELECT * FROM requests WHERE status IN (\'reserved\',\'settled\')'):
        key=row['model_key']
        if row['status']=='reserved':count[key]+=1
        if row['month']==month and (row['status']=='reserved' or (row['finished_at'] and parse_date(row['finished_at'])>parse_date(observed_at))):
            reserved[key]+=row['reserved_tokens'] if row['status']=='reserved' else row['actual_tokens']
    return {'reserved':reserved,'count':count}

def request_hash(task):return hashlib.sha256(json.dumps(task,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def choose(db:Path,usage,task,now,write=False):
    conn=connect(db,write)
    try:
        if conn and write:conn.execute('BEGIN IMMEDIATE')
        if conn:
            row=conn.execute('SELECT * FROM requests WHERE task_id=?',(task['taskId'],)).fetchone()
            if row:
                if row['request_hash']!=request_hash(task):raise ValueError('Existing task ID has a different contract; use a new ID')
                if write:conn.execute('COMMIT')
                return {'status':'existing','taskId':task['taskId'],'offeringKey':row['model_key'],'reservationState':row['status'],'noNewReservation':True,'inferencesSent':0}
        d=plan_nan_task(usage,task,now,ledger(conn,usage['month'],usage['observedAt']),require_verified=write)
        if write and d['status']=='selected':
            conn.execute('INSERT INTO requests(task_id,month,model_key,request_hash,reserved_tokens,status,created_at) VALUES(?,?,?,?,?,?,?)',
                 (task['taskId'],usage['month'],d['selected'],request_hash(task),task['estimatedTotalTokens'],'reserved',now.isoformat()))
        if conn and write:conn.execute('COMMIT')
        return {**d,'taskId':task['taskId'],'reservationState':'reserved' if write and d['status']=='selected' else 'not-reserved','inferencesSent':0}
    except BaseException:
        if conn and write and conn.in_transaction:conn.execute('ROLLBACK')
        raise
    finally:
        if conn:conn.close()

def finish(db:Path,task_id:str,action:str,actual_tokens:int|None,now:datetime,confirm_not_sent=False):
    conn=connect(db,True)
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM requests WHERE task_id=?',(task_id,)).fetchone()
        if not row:raise ValueError('No reservation exists for this task ID')
        if action=='settle':
            if actual_tokens is None or type(actual_tokens) is not int or actual_tokens<0:raise ValueError('Actual consumed tokens must be supplied; zero is allowed only when measured')
            if row['status']=='settled' and row['actual_tokens']==actual_tokens:
                conn.execute('COMMIT');return {'status':'settled','taskId':task_id,'idempotent':True,'inferencesSent':0}
            if row['status']!='reserved':raise ValueError('Cannot settle a released or previously settled task differently')
            conn.execute("UPDATE requests SET status='settled',actual_tokens=?,finished_at=? WHERE task_id=?",(actual_tokens,now.isoformat(),task_id))
        elif action=='release':
            if not confirm_not_sent:raise ValueError('Release only if the request was definitely NOT sent; otherwise settle actual usage')
            if row['status'] not in ('reserved','released'):raise ValueError('Cannot release an already settled call')
            conn.execute("UPDATE requests SET status='released',finished_at=? WHERE task_id=?",(now.isoformat(),task_id))
        else:raise ValueError('Unknown completion action')
        conn.execute('COMMIT')
        return {'status':'settled' if action=='settle' else 'released','taskId':task_id,'actualTokens':actual_tokens if action=='settle' else None,'inferencesSent':0}
    except BaseException:
        if conn.in_transaction:conn.execute('ROLLBACK')
        raise
    finally:conn.close()

def validate_target(harness:str,role:str,function_id:str,domain:str,objective:str,root=ROOT):
    contracts=json.loads((root/'contracts/harnesses.json').read_text())['harnesses']
    if harness not in contracts or role not in contracts[harness]['roles']:
        raise ValueError('Unknown harness or unavailable role; native dispatch is not assumed')
    contract=contracts[harness]
    info=contract['roles'][role]
    if info['functionId']!=function_id:
        raise ValueError('Requested function does not match the native role contract')
    if info.get('kind')=='custom-role':
        raise ValueError('Custom-role registration is not verified by this dispatch hook')
    if domain not in ('apps','web','data','research','agent-use','cybersecurity') or objective not in ('economy','balanced','speed','best'):
        raise ValueError('Unknown domain or objective')
    if any(item['domain']==domain and objective in item['objectives'] and role in item['roles'] for item in contract['excludedRoles']):
        raise ValueError('Role excluded by the harness/domain/objective contract')
    if function_id not in load_config()[0]['functions']:
        raise ValueError('This native role is not eligible for automatic NaN balancing')
    return {'harness':harness,'role':role,'functionId':function_id,'domain':domain,'objective':objective}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['plan','reserve','settle','release'])
    ap.add_argument('--state',type=Path,default=DB)
    ap.add_argument('--usage',type=Path)
    ap.add_argument('--task-id')
    ap.add_argument('--function',dest='function_id')
    ap.add_argument('--domain',default='research')
    ap.add_argument('--harness',choices=['gentle-shell','omp'],help='Required for an actual reserve: exact native role contract')
    ap.add_argument('--role',help='Required for a reserve; no native profile is changed')
    ap.add_argument('--objective',choices=['economy','balanced','speed','best'],help='Required for reserve; prevents excluded-role dispatch')
    ap.add_argument('--modality',choices=['text','image','audio'],default='text')
    ap.add_argument('--input-tokens',type=int)
    ap.add_argument('--total-tokens',type=int)
    ap.add_argument('--include-trials',action='store_true')
    ap.add_argument('--high-impact',action='store_true')
    ap.add_argument('--closed-task',action='store_true')
    ap.add_argument('--acceptance-oracle',action='store_true')
    ap.add_argument('--headroom',type=float,default=.02)
    ap.add_argument('--actual-tokens',type=int)
    ap.add_argument('--confirm-not-sent',action='store_true')
    args=ap.parse_args()
    now=datetime.now(timezone.utc)
    if args.action in ('plan','reserve'):
        if not args.usage or not args.task_id or not args.function_id or args.input_tokens is None or args.total_tokens is None:
            ap.error('plan/reserve require --usage --task-id --function --input-tokens --total-tokens')
        if args.action=='reserve':
            if not args.harness or not args.role or not args.objective:ap.error('reserve requires --harness --role --objective to verify its pinned role contract')
            validate_target(args.harness,args.role,args.function_id,args.domain,args.objective)
        usage=private_json(args.usage)
        task={'taskId':args.task_id,'functionId':args.function_id,'domain':args.domain,'modality':args.modality,
              'estimatedInputTokens':args.input_tokens,'estimatedTotalTokens':args.total_tokens,
              'highImpact':args.high_impact,'closedTask':args.closed_task,'acceptanceOracle':args.acceptance_oracle,
              'includeTrials':args.include_trials,'headroomFraction':args.headroom,
              **({'harness':args.harness,'role':args.role,'objective':args.objective} if args.action=='reserve' else {})}
        result=choose(args.state,usage,task,now,write=args.action=='reserve')
    else:
        if not args.task_id:ap.error('settle/release require --task-id')
        result=finish(args.state,args.task_id,args.action,args.actual_tokens,now,args.confirm_not_sent)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['status'] not in ('selected','reserved','existing','settled','released'):sys.exit(2)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,json.JSONDecodeError,sqlite3.DatabaseError) as error:
        print(f'NaN dispatcher: {error}',file=sys.stderr);sys.exit(2)
