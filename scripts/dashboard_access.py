"""Attach explicit access provenance without changing benchmark or route choices."""
from __future__ import annotations
import hashlib
from access_catalog import load_catalog, target_for
from harness_contracts import load_harnesses
from profile_compiler import source_resources, validate_resources

def decorate_access(root, compact_catalog, portfolios, meta, details, strategies):
    catalog=load_catalog(root); contracts=load_harnesses(root)
    inventories={pid:source_resources(portfolio,{}) for pid,portfolio in portfolios.items()}
    for resources in inventories.values():validate_resources(resources,catalog)
    for key,info in compact_catalog.items():
        offering=catalog['offerings'][key]
        info['modelId']=offering['modelId']
        info['defaultAccessRouteId']=offering['defaultAccessRouteId']
        info['identityRelation']=offering['identityRelation']
    for pid,info in meta.items():
        targets=[tid for tid,t in catalog['targets'].items() if t['harness']==info['harness']]
        if len(targets)!=1:raise ValueError('Explicit target/version resolution required')
        target=target_for(catalog,targets[0],contracts)
        info.update(targetId=targets[0],harnessVersion=target['harnessVersion'],runtime=target['runtime'])
    def attach(routes, portfolio):
        resources=inventories[portfolio]
        for primary in routes.values():
            for selection in [primary,primary['fallback'],primary['accelerator']]:
                if selection is None:continue
                offering=catalog['offerings'][selection['modelKey']]
                rid=offering['defaultAccessRouteId']
                matches=[r for r in resources if r['accessRouteId']==rid]
                if len(matches)!=1:raise ValueError('Origin requires exactly one baseline resource')
                resource=matches[0]
                selection['origin']={'modelId':offering['modelId'],'accessRouteId':rid,
                                     'resourceId':resource['id'],'credentialRef':resource['credentialRef'],'plan':resource['plan']}
    for pid,routes in details.items():attach(routes,meta[pid]['portfolio'])
    for strategy in strategies.values():attach(strategy['routes'],strategy['portfolio'])
    inputs=['catalog/models.json','catalog/offerings.json','catalog/access-routes.json','catalog/resource-plans.json',
            'contracts/harnesses.json','scripts/dashboard_access.py','scripts/access_catalog.py',
            'scripts/harness_contracts.py','scripts/profile_compiler.py','scripts/profile_semantics.py','scripts/dashboard_strategies.py',
            'policies/nan-static-workloads.json','policies/nan-static-approval.json',
            'policies/nan-static-composition.json','scripts/nan_static_hybrid.py',
            'policies/nan-custom-workload.json','scripts/nan_custom_workload.py','dashboard/src/nanCustomWorkload.ts',
            'dashboard/src/activityProfiles.ts',
            'catalog/access-routes.json','catalog/resource-plans.json','policies/functions.json',
            'scripts/nan_static_profiles.py','dashboard/src/nanStaticProfiles.ts',
            'scripts/nan_quota_optimizer.py','dashboard/src/nanQuotaOptimizer.ts','policies/nan-quota-balancing.json','policies/nan-quota-approval.json','catalog/account-inventory.json','policies/selection-candidates.json','policies/selection-evidence.json','policies/selection-approval.json','scripts/selection_candidates.py','policies/activity-allocation.json','scripts/activity_allocation.py','data/assignment-shards/manifest.json','data/portfolios.csv','data/omp-runtime-policies.csv','policies/assurance-contract.json','scripts/profile_assurance.py','dashboard/src/assuranceAnalysis.ts']
    return {'schemaVersion':1,'evidenceState':'declared-not-runtime-verified','resourcesByPortfolio':inventories,
            'inputSha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in inputs}}
