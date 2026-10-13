"""Semantic profile invariants independent of structural serialization tests.

Declared modality is a contract, not a successful provider roundtrip. Effort order
is applied only within one model/access offering, never as a quality ranking.
"""
from copy import deepcopy

EFFORT_ORDER = ('minimal', 'low', 'medium', 'high', 'xhigh', 'max')

def critical_review_config(config: dict, critical_roles, catalog_by_selector: dict) -> dict:
    result = deepcopy(config)
    for role in critical_roles:
        if role not in result: continue
        item = result[role]
        offering = catalog_by_selector.get(item['model'])
        if not offering: raise ValueError(f'{role}: unknown critical-review selector')
        allowed = offering.get('allowed_efforts', offering.get('efforts', []))
        current = item.get('thinking', '')
        if current and current not in allowed: raise ValueError(f'{role}: unsupported source effort')
        # An ungraded route cannot be turned into a graduated route by an export.
        if not allowed:
            if current: raise ValueError(f'{role}: effort on ungraded route')
            continue
        if any(e not in EFFORT_ORDER for e in allowed): raise ValueError(f'{role}: unknown effort order')
        floor = max(EFFORT_ORDER.index('high'), EFFORT_ORDER.index(current) if current else -1)
        choices = [e for e in allowed if EFFORT_ORDER.index(e) >= floor]
        if not choices: raise ValueError(f'{role}: no supported critical-review floor')
        item['thinking'] = min(choices, key=EFFORT_ORDER.index)
    return result

def require_visual_capability(function_id: str, vision, label: str):
    if function_id == 'visual-inspection' and vision is not True:
        raise ValueError(f'{label}: visual-inspection requires declared image input for this access offering, including reserves')

def resolved_identity(selection: dict):
    return tuple(selection.get(k) for k in ('selector','effort','accessRouteId','resourceId','credentialRef','plan'))

def require_distinct_reserves(primary: dict, label: str):
    for slot in ('fallback','accelerator'):
        reserve=primary.get(slot)
        if reserve and resolved_identity(reserve)==resolved_identity(primary):
            raise ValueError(f'{label}.{slot}: reserve repeats the same effective route; a retry is not an alternative model/access configuration')
