"""Versioned native-role contracts and portable responsibility criteria."""
from __future__ import annotations
import json
from strict_data_formats import json_loads_strict
from pathlib import Path
from strict_data_formats import json_loads_strict
ROOT = Path(__file__).resolve().parents[1]

def load_harnesses(root: Path = ROOT) -> dict:
    data = json_loads_strict((root / 'contracts/harnesses.json').read_bytes())
    if data.get('schemaVersion') != 1:
        raise ValueError('Unsupported harness contract schema')
    functions = json_loads_strict((root / 'policies/functions.json').read_bytes())['functions']
    for harness, contract in data['harnesses'].items():
        if not contract['roles'] or any(role['functionId'] not in functions for role in contract['roles'].values()):
            raise ValueError(f'{harness}: unknown functional role')
        if not contract['harnessVersion'] or not contract['runtime']['version']:
            raise ValueError(f'{harness}: versions must be explicit')
        if not set(contract['criticalRoles']).issubset(contract['roles']):
            raise ValueError(f'{harness}: unknown critical role')
    return data['harnesses']

def roles_for(contract: dict, domain: str, objective: str) -> list[str]:
    roles = list(contract['roles'])
    for rule in contract.get('excludedRoles', []):
        if rule['domain'] == domain and objective in rule['objectives']:
            roles = [role for role in roles if role not in rule['roles']]
    return roles

def bounded_roles(contract: dict) -> frozenset[str]:
    return frozenset(role for role, meta in contract['roles'].items() if meta.get('boundedOffload', False))

def is_retired(contract: dict, role: str) -> bool:
    return any(role.startswith(prefix) for prefix in contract.get('retiredRolePrefixes', []))
