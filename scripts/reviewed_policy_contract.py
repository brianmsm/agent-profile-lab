"""Versioned, explicitly approved *declarative* safety contract invariants.

SHA pins and Git-history checks are NOT a signature, proof of operator
identity, installed permission controller, or evidence of real runtime safety.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from reviewed_git_anchors import reviewed_anchor,reviewed_blob,git
from strict_data_formats import json_loads_strict

# Maintainer-reviewed R3 state: changes require a separate policy review.
POLICY_SHA256='d4be83503a6d198617f48e34198abbf4f9d024f1bfb714c5f56b913f6b1be2ed'
CYBER_GATE_SHA256='90b7e1da7bc329e2c5f642c8ce2ed767775101e0e62aeba72f563edfb9cf7981'
# Pin the complete reviewed *normative* cybersecurity scope/critical/routine/
# gate/evidenceNote/evidenceBoundary, not merely one textual gate.
CYBER_DOMAIN_SHA256='130f63faf14be503848ef65025da5990ec9d43abedcb56a7629dfe563770c367'
CONTROL_IDS=(
    'scope-and-authorization','tool-permissions','secret-isolation',
    'acceptance-oracle','human-review-for-impact','rollback-and-audit-log')
STATES={
    'operationalReadiness':'configuration-only',
    'runtimeEnforcement':'external-not-installed',
    'reviewIndependence':'not-measured',
    'fallbackDispatch':'not-installed',
    'costAndLatency':'not-measured',
    'routeCalibration':'not-measured',
}
# Public policy history is independent of the private edition.
PUBLIC_POLICY_COMMIT='691bfc8c6088371b83de223ff4b437da98827327'
PRIVATE_POLICY_COMMIT='' # public edition must never require private history

def verify_reviewed_policy(root: Path) -> dict:
    root=root.resolve()
    policy_file=root/'policies/assurance-contract.json'
    domains_file=root/'data/domain-objective-contracts.json'
    if hashlib.sha256(policy_file.read_bytes()).hexdigest()!=POLICY_SHA256:
        raise ValueError('Safety assurance policy not approved by reviewed release')
    policy=json_loads_strict(policy_file.read_bytes())
    if tuple(policy.get('requiredExternalControls',[]))!=CONTROL_IDS:
        raise ValueError('External safety-control inventory differs from reviewed policy')
    for field,expected in STATES.items():
        if policy.get(field)!=expected:
            raise ValueError('Claimed runtime/control state differs from approved declarative policy: '+field)
    domains=json_loads_strict(domains_file.read_bytes())
    gate=domains['domains']['cybersecurity']['gate']
    if hashlib.sha256(gate.encode()).hexdigest()!=CYBER_GATE_SHA256:
        raise ValueError('Cybersecurity gate changed without policy review')
    canonical=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,
                              separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if canonical(domains['domains']['cybersecurity'])!=CYBER_DOMAIN_SHA256:
        raise ValueError('Cybersecurity normative domain contract changed without independent policy review')
    edition,_=reviewed_anchor(root)
    pin=PRIVATE_POLICY_COMMIT if edition=='private' else PUBLIC_POLICY_COMMIT
    if not pin:raise ValueError('No reviewed safety policy commit for edition')
    git(root,'merge-base','--is-ancestor',pin,'HEAD')
    if hashlib.sha256(reviewed_blob(root,pin,'policies/assurance-contract.json')).hexdigest()!=POLICY_SHA256:
        raise ValueError('Reviewed policy does not match fixed Git source')
    baseline=json_loads_strict(reviewed_blob(root,pin,'data/domain-objective-contracts.json'))
    if hashlib.sha256(baseline['domains']['cybersecurity']['gate'].encode()).hexdigest()!=CYBER_GATE_SHA256:
        raise ValueError('Reviewed cybersecurity gate differs from fixed Git source')
    if canonical(baseline['domains']['cybersecurity'])!=CYBER_DOMAIN_SHA256:
        raise ValueError('Reviewed cybersecurity domain does not match fixed Git source')
    return {'policyReviewedForCurrentStructure':True,
        'reviewedFields':['all cybersecurity domain normative fields','assurance policy full bytes'],
        'approvedGitCommit':pin,
        'policyEnforcedAtRuntime':False,
        'identityAuthenticated':False,
        'controlsVerified':False}
