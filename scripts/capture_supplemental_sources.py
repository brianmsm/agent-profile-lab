"""Archive static ledger GETs with exact byte hashes; never execute remote code."""
from pathlib import Path
import concurrent.futures
import csv
import datetime
import hashlib
import json
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/supplemental'
IDS = {'FC','FCDATA','MIMO','MIMOF','AA','AA61SOL','ULTRA','SPECPI','FH','COMPOSIO','BRIDGE','COGN'}

def capture(row):
    url = row['url']
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status = None
    headers = {}
    error = None
    final_url = url
    try:
        request = urllib.request.Request(url, headers={'User-Agent':'Gentle-assess source audit (static public GET)'})
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            headers = dict(response.headers)
            final_url = response.url
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        headers = dict(exc.headers)
        raw = exc.read()
        error = str(exc)
    except Exception as exc:
        raw = b''
        error = f'{type(exc).__name__}: {exc}'
    name = row['source_id'] + '_PUBLIC_2026-10-02.raw'
    (OUT / name).write_bytes(raw)
    receipt = {'sourceId':row['source_id'],'requestedUrl':url,'finalUrl':final_url,'capturedAt':stamp,'httpStatus':status,'headers':headers,'error':error,'path':str((OUT/name).relative_to(ROOT)),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'method':'GET; static bytes only; no authentication, JavaScript execution or inference'}
    (OUT / (row['source_id']+'_RECEIPT_2026-10-02.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(row['source_id'],status,len(raw),error)

if __name__ == '__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    rows = [r for r in csv.DictReader((ROOT/'sources/ledger.csv').open(encoding='utf-8-sig')) if r['source_id'] in IDS]
    rows.extend([
        {'source_id':'SPECPI_DATA','url':'https://tannermidd.github.io/SpecPi/evaluations/terminal-bench-2.json'},
        {'source_id':'FH_SITE','url':'https://frontierharness.org/'},
        {'source_id':'FH_DATA','url':'https://raw.githubusercontent.com/frontier-harness-eval/eval/main/results/eval-data.json'},
        {'source_id':'FH_VERSIONS','url':'https://raw.githubusercontent.com/frontier-harness-eval/eval/main/metadata/harness-versions.json'},
    ])
    from supplemental_registered_refs import REFERENCES
    rows.extend({'source_id':name,'url':url} for name,url in REFERENCES)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(capture,rows))
