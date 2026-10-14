#!/usr/bin/env python3
"""Preview/apply a label-only source migration; never change native selections.

The explicitly delimited legacy Claude statement is retained as historical text
with a dated supersession note. --write does NOT bless shard hashes automatically.
"""
from __future__ import annotations
from pathlib import Path
import argparse, collections, csv, json
from metadata_contracts import label_contract, expected_labels
ROOT=Path(__file__).resolve().parents[1]
HISTORICAL='sin benchmarks de computer-use, research, data o web'
ANNOTATION='[Nota histórica anterior al 2026-09-30: sin benchmarks de computer-use, research, data o web; sustituida por el inventario documental posterior. Presencia de benchmarks no demuestra eficacia de esta ruta.]'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write', action='store_true');a=parser.parse_args()
    contract=label_contract(ROOT);result={}
    for p in [ROOT/'data/profile-index.csv',*sorted((ROOT/'data/assignment-shards').glob('*/*.csv'))]:
        with p.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        counts=collections.Counter()
        for row in rows:
            for field,value in expected_labels(row,contract).items():
                if row[field]!=value:row[field]=value;counts[field]+=1
            context='profile_context' if 'profile_context' in row else 'context_review'
            old=row.get(context,'')
            if HISTORICAL in old and ANNOTATION not in old:
                row[context]=old.replace(HISTORICAL,ANNOTATION);counts['historical_note']+=1
        if counts and a.write:
            with p.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        result[str(p.relative_to(ROOT))]=dict(counts)
    print(json.dumps({'applied':a.write,'changes':result,'selectionChanges':0},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
