"""Versioned native-role contracts and portable responsibility criteria."""
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def load_harnesses(root: Path = ROOT) -> dict:
    data = json.loads((root / 'contracts/harnesses.json').read_text())
    if data.get('schemaVersion') != 1:
        raise ValueError('Unsupported harness contract schema')
    functions = json.loads((root / 'policies/functions.json').read_text())['functions']
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
