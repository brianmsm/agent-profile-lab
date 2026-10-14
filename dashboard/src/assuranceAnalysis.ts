import policy from '../../policies/assurance-contract.json'
import offerData from '../../catalog/offerings.json'
import contractData from '../../contracts/harnesses.json'
import type {Snapshot} from './data'
import type {Preset} from './presetStrategies'
import {resolveOrigin,referenceSelector} from './accessRouting'
export const assurancePolicy=policy
export type AssuranceReference={selector:string;effort:string;accessRouteId?:string|null;resourceId?:string|null;credentialRef?:string|null;plan?:string|null;offeringKey?:string}
export type AssuranceRole=AssuranceReference&{enabled:boolean;functionId?:string;fallback?:AssuranceReference|null}
const offers=offerData.offerings as Record<string,{compatibility:{vision?:boolean;notes?:string}}>
const contracts=contractData.harnesses as Record<string,{roles:Record<string,{functionId:string}>}>
const resourceKey=(r:AssuranceReference)=>JSON.stringify([r.accessRouteId??null,r.resourceId??null,r.credentialRef??null,r.plan??null])
const routeKey=(r:AssuranceReference)=>JSON.stringify([r.selector,r.effort,r.accessRouteId??null,r.resourceId??null,r.credentialRef??null,r.plan??null])
export function fallbackKind(primary:AssuranceReference,fallback?:AssuranceReference|null):string{
  if(!fallback)return 'none'
  if(resourceKey(primary)!==resourceKey(fallback))return 'different-access-resource'
  if(primary.selector!==fallback.selector)return 'different-model-same-access'
  return primary.effort!==fallback.effort?'effort-alternative':'identical-retry'
}
export function assessResolved(roles:Record<string,AssuranceRole>,_harness:string,domain:string){
  const active=Object.fromEntries(Object.entries(roles).filter(([,r])=>r.enabled))
  const reviews=Object.values(active).filter(r=>policy.reviewFunctions.includes(r.functionId||''))
  const reviewRoutes=new Set(reviews.map(routeKey)),coordinator=active.orchestrator??active.default
  const critical=reviews.filter(r=>r.functionId==='critical-review'),criticalRoutes=new Set(critical.map(routeKey))
  const sharedAux=Object.keys(active).filter(k=>coordinator&&policy.auxiliaryFunctions.includes(active[k].functionId||'')&&routeKey(active[k])===routeKey(coordinator)).sort()
  const vision=(r:AssuranceReference)=>offers[r.offeringKey||'']?.compatibility.vision===true
  const imagePrimary=Object.values(active).filter(vision).length,imageReserve=Object.values(active).filter(r=>r.fallback&&vision(r.fallback)).length
  const maximum=Object.keys(active).filter(k=>active[k].effort==='max').sort()
  const accesses=new Set(Object.values(active).map(r=>r.accessRouteId)).size
  const superseded=Object.keys(active).filter(k=>active[k].fallback&&/superseded/iu.test(offers[active[k].fallback?.offeringKey||'']?.compatibility.notes||'')).sort()
  const flags=['requested-effort-only']
  if((reviews.length>1&&reviewRoutes.size===1)||(critical.length>1&&criticalRoutes.size===1))flags.push('shared-review-route')
  if(sharedAux.length>1)flags.push('uniform-auxiliary-effort')
  if(maximum.length)flags.push('maximum-effort-unmeasured')
  if(['web','agent-use'].includes(domain)&&imagePrimary===0){flags.push('no-primary-image-route');if(!imageReserve)flags.push('no-image-route')}
  if(domain==='cybersecurity')flags.push('apps-derived-security')
  if(accesses===1)flags.push('single-access-route')
  if(superseded.length)flags.push('superseded-reserve')
  return {schemaVersion:1,policyId:policy.id,evidenceTier:policy.evidenceTier,routeCalibration:policy.routeCalibration,
    operationalReadiness:policy.operationalReadiness,runtimeEnforcement:policy.runtimeEnforcement,reviewIndependence:policy.reviewIndependence,fallbackDispatch:policy.fallbackDispatch,costAndLatency:policy.costAndLatency,
    configuredRoles:Object.keys(roles).length,enabledRoles:Object.keys(active).length,disabledRoles:Object.keys(roles).length-Object.keys(active).length,
    declaredReviewRoles:reviews.length,distinctReviewRoutes:reviewRoutes.size,criticalReviewRoles:critical.length,distinctCriticalReviewRoutes:criticalRoutes.size,distinctAccessRoutes:accesses,auxiliariesMatchingCoordinator:sharedAux,
    maxEffortRoles:maximum,catalogSupersededReserveRoles:superseded,imageCapablePrimaries:imagePrimary,imageCapableFallbacks:imageReserve,
    fallbackKinds:Object.fromEntries(Object.keys(roles).sort().map(k=>[k,fallbackKind(roles[k],roles[k].fallback)])),flags,requiredExternalControls:policy.requiredExternalControls}
}
export function presetAssurance(snapshot:Snapshot,preset:Preset){
 const resolve=(r:Preset['routes'][string])=>r.origin&&preset.meta.targetId?resolveOrigin(r,preset.meta.targetId):{selector:referenceSelector(snapshot,r,preset.meta.targetId),effort:r.effort,offeringKey:r.modelKey}
 const roles=Object.fromEntries(Object.entries(preset.routes).map(([role,r])=>[role,{...resolve(r),enabled:r.enabled,functionId:contracts[preset.meta.harness]?.roles[role]?.functionId,fallback:r.fallback?resolve({...r,...r.fallback}):null}]))
 return assessResolved(roles,preset.meta.harness,preset.meta.domain)
}
