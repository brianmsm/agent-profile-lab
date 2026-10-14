"""Derived assurance for a concrete export. Not provider probes or a safety certificate."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
POLICY=json.loads((ROOT/'policies/assurance-contract.json').read_bytes())
def resource_key(r):return tuple(r.get(k) for k in ('accessRouteId','resourceId','credentialRef','plan'))
def route_key(r):return (r['selector'],r['effort'],*resource_key(r))
def fallback_kind(primary, fallback):
    if fallback is None:return 'none'
    if resource_key(primary)!=resource_key(fallback):return 'different-access-resource'
    if primary['selector']!=fallback['selector']:return 'different-model-same-access'
    return 'effort-alternative' if primary['effort']!=fallback['effort'] else 'identical-retry'
def assess_resolved(roles, harness, domain, offerings, policy=POLICY):
    active={k:v for k,v in roles.items() if v['enabled']}
    reviews={k:v for k,v in active.items() if v.get('functionId') in policy['reviewFunctions']}
    review_routes={route_key(v) for v in reviews.values()}
    critical=[v for v in reviews.values() if v.get('functionId')=='critical-review']
    critical_routes={route_key(v) for v in critical}
    coordinator=active.get('orchestrator',active.get('default'))
    shared_aux=sorted(k for k,v in active.items() if coordinator and v.get('functionId') in policy['auxiliaryFunctions'] and route_key(v)==route_key(coordinator))
    def vision(v):return offerings.get(v.get('offeringKey'),{}).get('compatibility',{}).get('vision') is True
    image_primary=sum(vision(v) for v in active.values())
    image_reserve=sum(vision(v['fallback']) for v in active.values() if v.get('fallback'))
    maximum=sorted(k for k,v in active.items() if v['effort']=='max')
    accesses=len({v.get('accessRouteId') for v in active.values()})
    superseded=sorted(k for k,v in active.items() if v.get('fallback') and 'superseded' in str(offerings.get(v['fallback'].get('offeringKey'),{}).get('compatibility',{}).get('notes','')).lower())
    flags=['requested-effort-only']
    if (len(reviews)>1 and len(review_routes)==1) or (len(critical)>1 and len(critical_routes)==1):flags.append('shared-review-route')
    if len(shared_aux)>1:flags.append('uniform-auxiliary-effort')
    if maximum:flags.append('maximum-effort-unmeasured')
    if domain in ('web','agent-use') and image_primary==0:
        flags.append('no-primary-image-route')
        if image_reserve==0:flags.append('no-image-route')
    if domain=='cybersecurity':flags.append('apps-derived-security')
    if accesses==1:flags.append('single-access-route')
    if superseded:flags.append('superseded-reserve')
    return {'schemaVersion':1,'policyId':policy['id'],
      **{k:policy[k] for k in ('evidenceTier','routeCalibration','operationalReadiness','runtimeEnforcement','reviewIndependence','fallbackDispatch','costAndLatency')},
      'configuredRoles':len(roles),'enabledRoles':len(active),'disabledRoles':len(roles)-len(active),
      'declaredReviewRoles':len(reviews),'distinctReviewRoutes':len(review_routes),
      'criticalReviewRoles':len(critical),'distinctCriticalReviewRoutes':len(critical_routes),
      'distinctAccessRoutes':accesses,'auxiliariesMatchingCoordinator':shared_aux,
      'maxEffortRoles':maximum,'catalogSupersededReserveRoles':superseded,'imageCapablePrimaries':image_primary,'imageCapableFallbacks':image_reserve,
      'fallbackKinds':{k:fallback_kind(v,v.get('fallback')) for k,v in sorted(roles.items())},
      'flags':flags,'requiredExternalControls':list(policy['requiredExternalControls'])}
