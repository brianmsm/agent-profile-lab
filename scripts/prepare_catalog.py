#!/usr/bin/env python3
"""Project the normalized identity/offer catalog for historical consumers."""
import json
from pathlib import Path
from access_catalog import load_catalog, compatibility_models
ROOT=Path(__file__).resolve().parents[1]
def main():
    catalog=load_catalog()
    target=ROOT/'data/model-catalog.json'
    text=json.dumps(compatibility_models(catalog),ensure_ascii=False,indent=1)+'\n'
    if not target.exists() or target.read_text()!=text:target.write_text(text)
    print(json.dumps({'models':len(catalog['models']),'offerings':len(catalog['offerings']),
                      'accessRoutes':len(catalog['routes']),'bindings':len(catalog['modelBindings'])}))
if __name__=='__main__':main()
