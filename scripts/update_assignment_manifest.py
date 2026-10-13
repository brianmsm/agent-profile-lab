#!/usr/bin/env python3
"""Review or explicitly accept updated assignment-shard hashes.

Default is read-only. --write updates data/assignment-shards/manifest.json,
which should be reviewed in the same Git diff as edited shard CSV files.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SHARDS=ROOT/"data/assignment-shards"
MANIFEST=SHARDS/"manifest.json"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--write",action="store_true",help="Accept current shard hash and row counts")
    args=parser.parse_args()
    previous=json.loads(MANIFEST.read_text(encoding="utf-8"))
    files=sorted(SHARDS.rglob("*.csv"))
    shards={}
    for path in files:
        with path.open(encoding="utf-8-sig",newline="") as fh:
            rows=list(csv.DictReader(fh))
        relative=path.relative_to(SHARDS).as_posix()
        for row in rows:
            if f"{row['domain']}/{row['harness']}.csv"!=relative:
                raise ValueError(f"Invalid dimensions in {relative}")
        shards[relative]={"rows":len(rows),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    updated={"schemaVersion":1,"totalRows":sum(row["rows"] for row in shards.values()),"shards":shards}
    changes=[k for k in sorted(set(shards)|set(previous["shards"])) if shards.get(k)!=previous["shards"].get(k)]
    print(json.dumps({"totalRows":updated["totalRows"],"shards":len(shards),"changed":changes},indent=2))
    if args.write:
        MANIFEST.write_text(json.dumps(updated,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("Manifest updated: review and commit the diff with the CSV changes.")
    elif changes:
        print("Read-only preview. To accept these changes explicitly: python3 scripts/update_assignment_manifest.py --write")
if __name__=="__main__":main()
