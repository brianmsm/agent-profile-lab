"""Reviewed, evidence-linked alternative recipes. No scoring or model calls.

The reference matrix remains archival. These alternatives are admitted explicitly,
not automatically promoted by a global leaderboard or a provider participation quota.
"""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import hashlib,json
from access_catalog import ROOT,read_json,load_catalog,target_for,resolve_binding
from harness_contracts import load_harnesses,roles_for
from activity_allocation import load_policy as activity_policy,validate_activity

POLICY='policies/selection-candidates.json';EVIDENCE='policies/selection-evidence.json';APPROVAL='policies/selection-approval.json'
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def file_sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def load_review(root=ROOT):
    policy,evidence,approval=[read_json(root/path) for path in (POLICY,EVIDENCE,APPROVAL)]
    if (policy.get('schemaVersion')!=1 or policy.get('updateMode')!='manual' or policy['id']!=evidence.get('reviewId')
        or approval.get('reviewId')!=policy['id'] or file_sha(root/POLICY)!=approval.get('policySha256')
        or file_sha(root/EVIDENCE)!=policy.get('evidenceSha256') or policy['evidenceSha256']!=approval.get('evidenceSha256')):
        raise ValueError('Selection review changed or incomplete; a new explicit approval is required')
    if any(file_sha(root/path)!=expected for path,expected in approval.get('inputSha256',{}).items()):raise ValueError('Reviewed model/access/harness contract changed; renew the explicit review')
    catalog=load_catalog(root);functions=read_json(root/'policies/functions.json')['functions'];seen=set()
    for recipe in policy['recipes']:
        if recipe['id'] in seen or not recipe['evidenceRefs'] or not recipe['selections']:raise ValueError('Empty/duplicate selection recipe')
        seen.add(recipe['id'])
        if not set(recipe['selections'])<=functions.keys() or set(recipe['selections'])&set(policy['protectedFunctions']):raise ValueError('Protected or unknown function in recipe')
        if set(recipe['domains'])&set(policy['excludedDomains']):raise ValueError('Excluded domain in recipe')
        if (set(recipe['objectives'])-{'economy','balanced','speed','best'} or set(recipe['complexities'])-{'bounded','standard','complex'}
            or set(recipe['domains'])-{'apps','web','data','research'}):raise ValueError('Unknown selection context')
        mappings=recipe.get('functionEvidence', {})
        if set(mappings)!=set(recipe['selections']):raise ValueError('Each selected function needs an explicit evidence transfer mapping')
        for function, mapping in mappings.items():
            if mapping.get('tier')!='E2-analogy' or mapping.get('routeCalibration')!='not-measured':raise ValueError('Unmeasured function cannot claim direct route calibration')
            if not mapping.get('evidenceRefs') or not set(mapping['evidenceRefs'])<=set(recipe['evidenceRefs']):raise ValueError('Function evidence must resolve within the reviewed recipe')
            if any(not isinstance(mapping.get(k),str) or len(mapping[k].strip())<20 for k in ('claim','transferLimit','acceptanceCriterion')):raise ValueError('Function transfer lacks a meaningful claim, limitation or acceptance criterion')
        refs=[evidence['observations'][k] for k in recipe['evidenceRefs']]
        if any(r['benchmark'] in evidence['exclusions']['metricLabels'] for r in refs):raise ValueError('Under-review metric cannot support selection')
        for key in recipe['offeringKeys']:
            offering=catalog['offerings'][key];binding=catalog['modelBindings'][offering['modelId']+'|'+offering['defaultAccessRouteId']]
            if binding['availability']=='historical-not-in-current-inventory':raise ValueError('Historical account model in recipe')
            if any(e and e not in binding['efforts'] for e in recipe['selections'].values()):raise ValueError('Recipe effort incompatible with access route')
            if not any(r['modelId']==offering['modelId'] and r['kind'] in ('capability','index') for r in refs):raise ValueError('Recipe lacks linked model capability evidence')
            if offering['identityRelation']=='candidate-alias' and recipe['admission']!='conditional-access-route':raise ValueError('Alias must remain explicitly conditional')
    return policy,evidence,approval

def validate_review_evidence(snapshot,root=ROOT):
    policy,evidence,approval=load_review(root)
    wanted=set(evidence['observations']);actual={}
    for row in snapshot['benchmarks']:
        id=row['measurement']['id']
        if id in wanted:
            if id in actual:raise ValueError('Duplicate selected observation ID')
            actual[id]=row
    registry=snapshot['benchmarkRegistry']
    for id,expected in evidence['observations'].items():
        row=actual.get(id)
        if row is None:raise ValueError(f'Selection observation removed: {id}; manual review needed')
        m=row['measurement'];p=registry['protocols'][m['protocolId']];metric=registry['metrics'][m['metricId']]
        if digest(row)!=expected['rowSha256'] or digest(p)!=expected['protocolSha256'] or digest(metric)!=expected['metricSha256']:
            raise ValueError(f'Selection evidence/protocol changed: {id}; do not retain an obsolete admission')
        if m['scope']!='current' or m['issueIds'] or m['modelRelation']!='published-label' or row['value'] is None:raise ValueError('Ineligible evidence in selection review')
        for field,value in {'modelId':m['modelId'],'value':row['value'],'effort':row['effort'],'benchmark':row['benchmark'],'unit':row['unit'],'kind':m['kind'],'direction':m['direction'],'sourceId':row['sourceId'],'sourceUrl':row['source'],'harness':p['harness'],'metricId':m['metricId'],'protocolId':m['protocolId'],'evaluationId':m['evaluationId']}.items():
            if expected[field]!=value:raise ValueError(f'Selection display does not match source: {field}')
    return {'reviewId':policy['id'],'recipes':len(policy['recipes']),'observations':len(actual),'evidenceSha256':approval['evidenceSha256'],'state':'external-evidence-not-route-calibrated','inferencesSent':0}

def require_review_snapshot(snapshot,approval):
    hashes=snapshot.get('access',{}).get('inputSha256',{})
    if (hashes.get(POLICY)!=approval['policySha256'] or hashes.get(EVIDENCE)!=approval['evidenceSha256']
        or any(hashes.get(path)!=expected for path,expected in approval.get('inputSha256',{}).items())):
        raise ValueError('This snapshot predates/differs from the selection review; regenerate its data')

def derive_candidate(snapshot,profile_id,recipe_id,offering_key,activity,root=ROOT,review=None,environment=None):
    policy,evidence,approval=review or load_review(root)
    cat,contracts,ap=environment or (load_catalog(root),load_harnesses(root),activity_policy(root))
    validate_activity(activity,ap);require_review_snapshot(snapshot,approval)
    recipe=next((r for r in policy['recipes'] if r['id']==recipe_id),None)
    if not recipe or offering_key not in recipe['offeringKeys']:raise ValueError('Unknown recipe/offering pairing')
    meta=snapshot['meta'][profile_id]
    if activity['highImpact'] or meta['domain'] not in recipe['domains'] or activity['complexity'] not in recipe['complexities'] or meta['objective'] not in recipe['objectives']:raise ValueError('Recipe not admitted for this task, priority or impact')
    target=target_for(cat,meta['targetId'],contracts)
    if meta['harness']!=target['harness'] or meta.get('harnessVersion')!=target['harnessVersion'] or meta.get('runtime')!=target['runtime']:raise ValueError('Snapshot target metadata differs from reviewed runtime')
    if set(snapshot['routeDetails'][profile_id])!=set(roles_for(contracts[meta['harness']],meta['domain'],meta['objective'])):raise ValueError('Snapshot role set differs from reviewed harness')
    offering=cat['offerings'][offering_key];model=snapshot['catalog'][offering_key]
    if model['modelId']!=offering['modelId'] or model['selector']!=offering['compatibility']['selector']:raise ValueError('Snapshot model changed from reviewed offering')
    resources=snapshot['access']['resourcesByPortfolio'][meta['portfolio']]
    matches=[r for r in resources if r['accessRouteId']==offering['defaultAccessRouteId']]
    if len(matches)!=1:raise ValueError('Recipe requires one already-declared subscription resource; no API inferred')
    resource=matches[0];origin={'modelId':offering['modelId'],'accessRouteId':resource['accessRouteId'],'resourceId':resource['id'],'credentialRef':resource['credentialRef'],'plan':resource['plan']}
    original=snapshot['routeDetails'][profile_id];routes=deepcopy(original);changes=[];permitted=ap['levels'][activity['complexity']]['functions']
    for role in sorted(original):
        r=original[role];function=contracts[meta['harness']]['roles'][role]['functionId']
        if not r['enabled'] or function not in permitted or function not in recipe['selections']:continue
        if function in policy['protectedFunctions']:raise ValueError('Recipe cannot modify a protected function')
        effort=recipe['selections'][function];resolve_binding(cat,target,offering['modelId'],origin['accessRouteId'],effort)
        if r['modelKey']==offering_key and r['effort']==effort and r.get('origin')==origin:continue
        condition=ap['conditions'][function]+' '+ap['safetyCondition']+' '+r['condition']+' Handoff explícito con fuentes, límites y aceptación; no asumir transferencia de razonamiento oculto ni caché entre modelos.'
        if offering['compatibility'].get('vision') is not True:condition+=' Esta vía no declara entrada de imagen: el handoff debe ser textual; no delegar lectura directa de capturas o páginas escaneadas.'
        if recipe['maxInputTokensForEconomicArgument']:condition+=f" El argumento de precio bajo sólo aplica hasta {recipe['maxInputTokensForEconomicArgument']} tokens de entrada por petición; sobre ese umbral revisar la tarifa."
        if recipe['workload']=='long-context-source-extraction':condition+=' Usar sólo si hay lectura extensa real; confirmar el contexto efectivo de la vía y citar fragmentos.'
        if recipe['admission']=='conditional-access-route':condition+=' Antes del uso operativo verificar identidad del endpoint, esfuerzo efectivo y tool use multivuelta; la ruta no está calibrada.'
        rationale=recipe['rationale']+' Revisión: '+policy['id']+'/'+recipe_id+'. Evidencia: '+', '.join(recipe['evidenceRefs'])+'. No es un ganador empírico del perfil.'
        routes[role]={**deepcopy(r),'modelKey':offering_key,'effort':effort,'origin':deepcopy(origin),'fallback':{k:deepcopy(r[k]) for k in ('modelKey','effort','origin')},'condition':condition,'rationale':rationale}
        changes.append({'role':role,'functionId':function,'fromModelKey':r['modelKey'],'toModelKey':offering_key,'fromEffort':r['effort'],'toEffort':effort})
    if not changes:raise ValueError('No effective changes: already selected or no admissible function; not another configuration')
    summary={'policyId':policy['id'],'recipeId':recipe_id,'label':recipe['label'],'offeringKey':offering_key,'admission':recipe['admission'],'complexity':activity['complexity'],'highImpact':False,'changes':changes,'evidenceRefs':recipe['evidenceRefs'],'evidenceSha256':approval['evidenceSha256'],'rationale':recipe['rationale'],'tradeoffs':recipe['tradeoffs'],'workload':recipe['workload'],'state':'candidate-not-calibrated','functionEvidence':deepcopy(recipe['functionEvidence'])}
    id=profile_id+'::review-'+recipe_id+'-'+offering_key+'-'+activity['complexity']
    coordinator=original.get('orchestrator',original.get('default'))
    return {'id':id,'kind':'reviewed-candidate','meta':deepcopy(meta),'sourceProfile':profile_id,'portfolio':meta['portfolio'],'routes':routes,'runtime':deepcopy(snapshot['runtimePolicies'][profile_id]),'coordinatorPool':snapshot['catalog'][coordinator['modelKey']]['pool'],'offloadPool':model['pool'],'limitations':policy['limitations']+recipe['tradeoffs'],'aliases':[id],'selectionReview':summary}

if __name__=='__main__':
    snapshot=read_json(ROOT/'dashboard/public/data/snapshot.json')
    print(json.dumps(validate_review_evidence(snapshot),indent=2))
