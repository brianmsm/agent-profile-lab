#!/usr/bin/env python3
"""Build full Gentle critical-review variants from the current explicit base profiles.

These are operational variants for candidates whose native RDD review truly warrants
higher reasoning. They are not counted as additional base matrix profiles.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
from harness_contracts import load_harnesses, is_retired
from profile_semantics import critical_review_config

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"profiles/gentle-shell"
OUT=ROOT/"profiles/gentle-shell-variants/critical-review"
OUT.mkdir(parents=True,exist_ok=True)

contract=load_harnesses()['gentle-shell']
upgrade_roles=set(contract['criticalRoles'])
catalog_by_selector={m['selector']:m for m in json.loads((ROOT/'data/model-catalog.json').read_text())}
store={}
count=0
rows=list(csv.DictReader((ROOT/"data/assignments.csv").open(encoding="utf-8-sig",newline="")))
base_names=sorted({
    f"{r['portfolio']}-{r['domain']}-{r['objective']}"
    for r in rows
    if r["harness"]=="gentle-shell"
})
# Build variants only for canonical Gentle groups; leave unrelated files intact.
for base in base_names:
    p=BASE/f"{base}.export.json"
    x=json.loads(p.read_text())
    base=x["name"]
    name=base+"-critical-review"
    config=json.loads(json.dumps(x["config"]))
    if any(is_retired(contract,role) or role not in contract["roles"] for role in config):
        raise ValueError("Source profile contains a retired or unsupported role")
    config=critical_review_config(config,upgrade_roles,catalog_by_selector)
    export={"kind":"gentle-pi.agent_model_profile","version":1,"name":name,"config":config}
    (OUT/f"{name}.export.json").write_text(json.dumps(export,ensure_ascii=False,indent=2)+"\n")
    store[name]=config
    count+=1

(ROOT/"profiles/gentle-critical-review.profiles.json").write_text(
    json.dumps({"kind":"gentle-pi.agent_model_profiles","version":1,"profiles":store},ensure_ascii=False,indent=2)+"\n"
)
print(f"Built {count} full critical-review variants.")
