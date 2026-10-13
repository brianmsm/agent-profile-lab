"""Offline Python oracle for the identical TypeScript quota planner cases."""
import sys,json
from datetime import datetime
from nan_quota_balance import plan_nan_task

def main():
    data=json.load(sys.stdin)
    if not isinstance(data,list) or len(data)>5000:raise ValueError('Bounded case array required')
    result=[]
    for item in data:
        try:
            result.append(plan_nan_task(item.get('usage'),item['task'],datetime.fromisoformat(item['now'].replace('Z','+00:00')),item.get('inflight'),item.get('requireVerified',False)))
        except ValueError as error:result.append({'exception':str(error)})
    print(json.dumps(result,ensure_ascii=False,separators=(',',':')))
if __name__=='__main__':main()
