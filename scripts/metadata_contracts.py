"""Canonical descriptive labels. IDs and native role assignments are authoritative.

This validator never repairs input implicitly. Source correction is a reviewed
migration; missing/wrong labels in a future input fail before projection.
"""
from __future__ import annotations
import csv, json
from strict_data_formats import json_loads_strict
from pathlib import Path
from strict_data_formats import json_loads_strict
ROOT = Path(__file__).resolve().parents[1]
LABEL_FIELDS = ('domain_label', 'objective_label', 'portfolio_label')

def label_contract(root: Path = ROOT) -> dict:
    c = json_loads_strict((root/'data/domain-objective-contracts.json').read_bytes())
    with (root/'data/portfolios.csv').open(encoding='utf-8-sig',newline='') as f:
        p=list(csv.DictReader(f))
    return {'domain_label': {k:v['label'] for k,v in c['domains'].items()},
            'objective_label': {k:('Máxima calidad' if k=='best' else v['label']) for k,v in c['objectives'].items()},
            'portfolio_label': {r['id']:r['label'] for r in p}}

def expected_labels(row: dict, contract: dict) -> dict:
    dimensions = {'domain_label':'domain', 'objective_label':'objective', 'portfolio_label':'portfolio'}
    try:
        return {field:contract[field][row[key]] for field,key in dimensions.items()}
    except KeyError as error:
        raise ValueError('Unknown canonical metadata dimension') from error

def validate_labels(rows: list[dict], contract: dict, label: str) -> None:
    for row in rows:
        for field,value in expected_labels(row,contract).items():
            if row.get(field) != value:
                raise ValueError(f'{label}: {row.get("profile_id", "unknown")}/{row.get("role", "index")}: invalid {field}')
