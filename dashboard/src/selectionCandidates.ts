import policy from '../../policies/selection-candidates.json'
import approval from '../../policies/selection-approval.json'
import evidence from '../../policies/selection-evidence.json'
import contractData from '../../contracts/harnesses.json'
import offersData from '../../catalog/offerings.json'
import {activityPolicy} from './activityProfiles'
import type {ActivitySettings} from './activityProfiles'
import type {ProfileFilters,Snapshot} from './data'
import {matchesSubscriptions} from './data'
import type {Preset} from './presetStrategies'
import {getPreset} from './presetStrategies'
import {validateProfileOrigins,resolveOrigin,originIdentity} from './accessRouting'
export const selectionPolicy=policy
export const selectionEvidence=evidence.observations as Record<string,(typeof evidence.observations)[keyof typeof evidence.observations]>
const offers=offersData.offerings as Record<string,{modelId:string;defaultAccessRouteId:string;compatibility:{selector:string;vision?:boolean}}>
const contracts=contractData.harnesses as Record<string,{roles:Record<string,{functionId:string}>}>
export interface SelectionReview {
  policyId:string;recipeId:string;label:string;offeringKey:string;admission:string;complexity:ActivitySettings['complexity'];highImpact:false
  changes:{role:string;functionId:string;fromModelKey:string;toModelKey:string;fromEffort:string;toEffort:string}[]
  functionEvidence:Record<string,{tier:string;claim:string;evidenceRefs:string[];transferLimit:string;acceptanceCriterion:string;routeCalibration:string}>
  evidenceRefs:string[];evidenceSha256:string;rationale:string;tradeoffs:string[];workload:string;state:'candidate-not-calibrated'
}
export function reviewSnapshotCompatible(snapshot:Snapshot):boolean {
  const hashes=snapshot.access?.inputSha256
  return hashes?.['policies/selection-candidates.json']===approval.policySha256&&hashes?.['policies/selection-evidence.json']===approval.evidenceSha256&&Object.entries(approval.inputSha256).every(([path,hash])=>hashes?.[path]===hash)
}
export function deriveReviewedCandidate(snapshot:Snapshot,profileId:string,recipeId:string,offeringKey:string,activity:ActivitySettings):Preset {
  if(!reviewSnapshotCompatible(snapshot))throw new Error('Este snapshot no corresponde a la revisión de selección; regenera sus datos.')
  if(!activity||Object.keys(activity).sort().join(',')!=='complexity,highImpact'||!Object.hasOwn(activityPolicy.levels,activity.complexity)||typeof activity.highImpact!=='boolean')throw new Error('Complejidad o impacto no admitidos.')
  const recipe=policy.recipes.find(r=>r.id===recipeId)
  if(!recipe||!recipe.offeringKeys.includes(offeringKey))throw new Error('Pareja receta/oferta no admitida.')
  const functionEvidence=recipe.functionEvidence as SelectionReview['functionEvidence']
  if(Object.keys(functionEvidence).sort().join(',')!==Object.keys(recipe.selections).sort().join(','))throw new Error('Falta correspondencia de evidencia por función.')
  for(const mapping of Object.values(functionEvidence)){
    if(mapping.tier!=='E2-analogy'||mapping.routeCalibration!=='not-measured'||!mapping.evidenceRefs.length||mapping.evidenceRefs.some(id=>!recipe.evidenceRefs.includes(id)))throw new Error('La candidata no puede atribuir una calibración no medida.')
  }
  const base=getPreset(snapshot,profileId),meta=base.meta
  if(activity.highImpact||!recipe.domains.includes(meta.domain)||!recipe.objectives.includes(meta.objective)||!recipe.complexities.includes(activity.complexity))throw new Error('Receta no admitida para esta actividad, prioridad o impacto.')
  const offering=offers[offeringKey],model=snapshot.catalog[offeringKey]
  if(!model||model.modelId!==offering.modelId||model.selector!==offering.compatibility.selector)throw new Error('La oferta no coincide con el catálogo revisado.')
  const resources=snapshot.access!.resourcesByPortfolio[base.portfolio],matching=resources.filter(r=>r.accessRouteId===offering.defaultAccessRouteId)
  if(matching.length!==1)throw new Error('Se requiere una suscripción declarada única; no se añade API ni gasto.')
  const resource=matching[0],origin={modelId:offering.modelId,accessRouteId:resource.accessRouteId,resourceId:resource.id,credentialRef:resource.credentialRef,plan:resource.plan}
  const routes=structuredClone(base.routes),changes:SelectionReview['changes']=[],permitted:readonly string[]=activityPolicy.levels[activity.complexity].functions
  const functions=recipe.selections as Record<string,string>,conditions=activityPolicy.conditions as Record<string,string>
  for(const role of Object.keys(base.routes).sort()){
    const r=base.routes[role],functionId=contracts[meta.harness].roles[role]?.functionId
    if(!r.enabled||!permitted.includes(functionId)||!Object.hasOwn(functions,functionId))continue
    if(policy.protectedFunctions.includes(functionId))throw new Error('Una receta no puede modificar una función protegida.')
    const effort=functions[functionId]
    resolveOrigin({modelKey:offeringKey,effort,origin},meta.targetId!)
    if(r.modelKey===offeringKey&&r.effort===effort&&JSON.stringify(originIdentity(r.origin))===JSON.stringify(originIdentity(origin)))continue
    let condition=conditions[functionId]+' '+activityPolicy.safetyCondition+' '+r.condition+' Handoff explícito con fuentes, límites y aceptación; no asumir transferencia de razonamiento oculto ni caché entre modelos.'
    if(offering.compatibility.vision!==true)condition+=' Esta vía no declara entrada de imagen: el handoff debe ser textual; no delegar lectura directa de capturas o páginas escaneadas.'
    if(recipe.maxInputTokensForEconomicArgument)condition+=` El argumento de precio bajo sólo aplica hasta ${recipe.maxInputTokensForEconomicArgument} tokens de entrada por petición; sobre ese umbral revisar la tarifa.`
    if(recipe.workload==='long-context-source-extraction')condition+=' Usar sólo si hay lectura extensa real; confirmar el contexto efectivo de la vía y citar fragmentos.'
    if(recipe.admission==='conditional-access-route')condition+=' Antes del uso operativo verificar identidad del endpoint, esfuerzo efectivo y tool use multivuelta; la ruta no está calibrada.'
    const rationale=recipe.rationale+' Revisión: '+policy.id+'/'+recipeId+'. Evidencia: '+recipe.evidenceRefs.join(', ')+'. No es un ganador empírico del perfil.'
    routes[role]={...structuredClone(r),modelKey:offeringKey,effort,origin:structuredClone(origin),fallback:{modelKey:r.modelKey,effort:r.effort,origin:structuredClone(r.origin)},condition,rationale}
    changes.push({role,functionId,fromModelKey:r.modelKey,toModelKey:offeringKey,fromEffort:r.effort,toEffort:effort})
  }
  if(!changes.length)throw new Error('Sin cambios efectivos: ya estaba elegido o no hay función admisible; no es otra configuración.')
  const selectionReview:SelectionReview={policyId:policy.id,recipeId,label:recipe.label,offeringKey,admission:recipe.admission,...activity,highImpact:false,changes,evidenceRefs:recipe.evidenceRefs,evidenceSha256:approval.evidenceSha256,rationale:recipe.rationale,tradeoffs:recipe.tradeoffs,workload:recipe.workload,state:'candidate-not-calibrated',functionEvidence}
  const id=profileId+'::review-'+recipeId+'-'+offeringKey+'-'+activity.complexity
  const result:Preset={...base,id,kind:'reviewed-candidate',routes,offloadPool:model.pool,limitations:[...policy.limitations,...recipe.tradeoffs],aliases:[id],selectionReview}
  validateProfileOrigins(snapshot,meta,routes,resources)
  return result
}
export function collectReviewedCandidates(snapshot:Snapshot,filters:ProfileFilters,activity:ActivitySettings) {
  const result:{presets:Preset[];issues:{profileId:string;message:string}[];unchanged:number}={presets:[],issues:[],unchanged:0}
  if(!filters.subscriptions||!filters.domain||!filters.objective||activity.highImpact||policy.excludedDomains.includes(filters.domain))return result
  if(!reviewSnapshotCompatible(snapshot)){result.issues.push({profileId:'selection-review',message:'Datos anteriores a esta revisión. Regenera el snapshot; no se mezclan recetas y evidencia de revisiones diferentes.'});return result}
  for(const [pid,m] of Object.entries(snapshot.meta)){
    if(m.domain!==filters.domain||m.objective!==filters.objective||(filters.harness&&m.harness!==filters.harness)||!matchesSubscriptions(snapshot.portfolios[m.portfolio],filters.subscriptions,true))continue
    const resources=snapshot.access!.resourcesByPortfolio[m.portfolio]
    for(const r of policy.recipes){
      if(!r.domains.includes(m.domain)||!r.objectives.includes(m.objective)||!r.complexities.includes(activity.complexity))continue
      for(const key of r.offeringKeys){
        if(!resources.some(resource=>resource.accessRouteId===offers[key].defaultAccessRouteId))continue
        try{result.presets.push(deriveReviewedCandidate(snapshot,pid,r.id,key,activity))}
        catch(error){const message=error instanceof Error?error.message:'Receta no disponible';if(message.startsWith('Sin cambios efectivos'))result.unchanged++;else result.issues.push({profileId:pid+'/'+r.id,message})}
      }
    }
  }
  return result
}
