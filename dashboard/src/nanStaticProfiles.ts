import {solveNanExactExpanded} from './nanQuotaOptimizer'
import workloadJson from '../../policies/nan-static-workloads.json'
import compositionJson from '../../policies/nan-static-composition.json'
import approvalJson from '../../policies/nan-static-approval.json'
import quotaJson from '../../policies/nan-quota-balancing.json'
import contractsJson from '../../contracts/harnesses.json'
import inventoryJson from '../../catalog/account-inventory.json'
import offersJson from '../../catalog/offerings.json'
import { nanKeys, nanQuotas } from './nanQuotaBalance'
import {resolveOrigin,targetForMeta,validateProfileOrigins} from './accessRouting'
import type {RouteDetail,Snapshot,SubscriptionSelection,ProfileFilters} from './data'
import {matchesSubscriptions} from './data'
import {deriveActivityPreset,activityPolicy} from './activityProfiles'
import type {Preset} from './presetStrategies'
import {validateNanCustomWorkload} from './nanCustomWorkload'
import type {NanCustomWorkload,FunctionWorkload} from './nanCustomWorkload'

export type NanScenario='routine'|'mixed'|'implementation'
export type NanComposition='nan-only'|'hybrid-preserve'|'hybrid-assist'|'hybrid-worker'
export interface NanHelperOffload {
  role:string;functionId:string;sourceProfile:string;fromModelKey:string;toModelKey:string
  expectedMonthlyTokens:number;classification:'eligible';reason:string
}
export interface NanHybridBase extends Preset {
  compositionMode:Exclude<NanComposition,'nan-only'>; helperOffloads:NanHelperOffload[]
}
export type NanKey=typeof nanKeys[number]
export interface NanStaticChange {
  role:string;functionId:string;fromModelKey:string;toModelKey:string;fromEffort:string;toEffort:string
  expectedMonthlyTokens:number;admission:string
}
export interface NanStaticPlan {
  policyId:string;scenario:NanScenario|'custom';scenarioLabel:string;includeTrials:boolean;quotasStartAtFull:true
  workloadObserved:false;state:'candidate-not-calibrated'
  expectedTokensAllEnabledRoles:number;expectedTokensOnNaN:number;expectedShareNaNOfAllRoles:number
  distanceFromQuotaTarget:number;distanceMetric:string
  scenarioAssumptions:{label:string;description:string;functionWorkload:FunctionWorkload}
  customWorkload?:NanCustomWorkload
  byModel:Record<NanKey,{
    offeringKey:NanKey;quota:number;expectedTokens:number;expectedTokenShare:number;targetQuotaShare:number
    expectedFractionOfQuota:number;idealFractionOfQuota:number;differencePercentagePoints:number;trialOnly:boolean
  }>
  byRole:{role:string;functionId:string;assumedCalls:number;assumedTotalTokensPerCall:number;estimatedMonthlyTokens:number}[]
  changes:NanStaticChange[];limitations:string[]
  qualityGuard:{trialShareCap:number;trialExpectedTokens:number;trialFractionOfExpectedNaN:number;qualityFirst:string}
  sensitivity:{minimumCornerDistance:number;maximumCornerDistance:number;lowerFactor:number;upperFactor:number;meaning:string}
  composition?:{mode:Exclude<NanComposition,'nan-only'>;activityPlan:NonNullable<Preset['activityPlan']>
    helperOffloads:NanHelperOffload[];activityInventoryProfile:string;qualityPolicyId:string;sourceCoordinatorProfile:string}
}
const offeringKeys=nanKeys as readonly NanKey[]
const targetContracts=contractsJson.harnesses as Record<string,{roles:Record<string,{functionId:string}>;excludedRoles:{domain:string;objectives:string[];roles:string[]}[]}>
const quotaFunctions=quotaJson.functions as Record<string,Partial<Record<NanKey,'eligible'|'trial'>>>
const protectedFns=new Set<string>(quotaJson.excludedFunctions)
const offerings=offersJson.offerings as Record<string,{modelId:string;defaultAccessRouteId:string}>
const assumedContext=Object.fromEntries(inventoryJson.models.map(m=>[m.offeringKey,m.reportedContext])) as Record<NanKey,number>
export const nanStaticScenarios=workloadJson.scenarios
export const nanCompositionPolicy=compositionJson
export function nanStaticCompatible(snapshot:Snapshot):boolean {
  const hashes=snapshot.access?.inputSha256
  return !!hashes&&Object.entries(approvalJson.inputSha256).every(([file,sha])=>hashes[file]===sha)
}
const cmp=(a:string,b:string)=>a<b?-1:a>b?1:0
function sourceResource(snapshot:Snapshot,portfolio:string){
  const resources=snapshot.access!.resourcesByPortfolio[portfolio]
  const nan=resources.filter(r=>r.accessRouteId==='nan')
  if(nan.length!==1)throw new Error('Se necesita un recurso NaN único y declarado.')
  return nan[0]
}
export function deriveNanStaticPreset(snapshot:Snapshot,profileId:string,scenario:NanScenario,
  includeTrials:boolean,highImpact:boolean,base?:NanHybridBase,customWorkload?:NanCustomWorkload):Preset {
  if(!nanStaticCompatible(snapshot))throw new Error('Esta política estática requiere regenerar el snapshot con sus hashes.')
  if(!Object.hasOwn(nanStaticScenarios,scenario)||typeof includeTrials!=='boolean'||typeof highImpact!=='boolean')throw new Error('Parámetros de reparto estático no admitidos.')
  const meta=snapshot.meta[profileId]
  if(!meta)throw new Error('Referencia inexistente.')
  targetForMeta(meta)
  if(highImpact||quotaJson.excludedDomains.includes(meta.domain))throw new Error('No se redistribuyen actividades críticas o de dominio excluido.')
  if(snapshot.portfolios[meta.portfolio].nan!=='True')throw new Error('La referencia no contiene NaN.')
  const original=base?.routes||snapshot.routeDetails[profileId]
  if(base&&(base.portfolio!==meta.portfolio||base.meta.harness!==meta.harness||base.meta.domain!==meta.domain||base.meta.objective!==meta.objective))throw new Error('Rutas compuestas ajenas al inventario y al harness.')
  const contract=targetContracts[meta.harness]
  if(!contract)throw new Error('Harness sin contrato.')
  const expected=Object.keys(contract.roles).filter(r=>!contract.excludedRoles.some(ex=>ex.domain===meta.domain&&ex.objectives.includes(meta.objective)&&ex.roles.includes(r))).sort()
  if(JSON.stringify(Object.keys(original).sort())!==JSON.stringify(expected))throw new Error('Contrato de roles desincronizado.')
  const custom=customWorkload?validateNanCustomWorkload(customWorkload):null
  if(custom&&custom.baseScenario!==scenario)throw new Error('El escenario editado no corresponde al escenario base seleccionado.')
  const assumptions=custom?{label:custom.label,description:custom.description,functionWorkload:custom.functionWorkload}:nanStaticScenarios[scenario]
  const res=sourceResource(snapshot,meta.portfolio),workload=assumptions.functionWorkload as FunctionWorkload
  const newRoutes=structuredClone(original)
  const eligible:{role:string;functionId:string;burden:number;route:RouteDetail;options:{key:NanKey;effort:string}[]}[]=[]
  const fixed=Object.fromEntries(offeringKeys.map(k=>[k,0])) as Record<NanKey,number>
  const byRole:NanStaticPlan['byRole']=[]
  let expectedAll=0
  for(const [role,r] of Object.entries(original).sort(([a],[b])=>cmp(a,b))){
    if(!r.enabled)continue
    const functionId=contract.roles[role].functionId
    const counts=workload[functionId]
    if(!counts)throw new Error('El escenario carece de supuestos para esta función.')
    const burden=counts.callsPerMonth*counts.totalTokensPerCall
    expectedAll+=burden
    byRole.push({role,functionId,assumedCalls:counts.callsPerMonth,assumedTotalTokensPerCall:counts.totalTokensPerCall,estimatedMonthlyTokens:burden})
    // Never demote another provider only to satisfy a NaN share target.
    if(!offeringKeys.includes(r.modelKey as NanKey))continue
    if(protectedFns.has(functionId)||!Object.hasOwn(quotaFunctions,functionId)||burden===0){
      if(offeringKeys.includes(r.modelKey as NanKey))fixed[r.modelKey as NanKey]+=burden
      continue
    }
    const options:{key:NanKey;effort:string}[]=[]
    for(const key of offeringKeys){
      const state=quotaFunctions[functionId]?.[key]
      if(!state||(state==='trial'&&!includeTrials))continue
      if(counts.totalTokensPerCall>assumedContext[key]*quotaJson.maximumInputFractionOfReportedContext)continue
      let effort=key===r.modelKey?r.effort:''
      if(key==='nan_glm'&&key!==r.modelKey){
        const donor=Object.entries(snapshot.meta).find(([pid,m])=>{
          const portfolio=snapshot.portfolios[m.portfolio],route=snapshot.routeDetails[pid]?.[role]
          return m.harness===meta.harness&&m.domain===meta.domain&&m.objective===meta.objective
            &&portfolio.nan==='True'&&portfolio.openai==='none'&&portfolio.claude==='none'&&portfolio.gateway==='none'
            &&route?.modelKey==='nan_glm'
        })
        effort=donor?snapshot.routeDetails[donor[0]][role].effort:'medium'
      }
      try{resolveOrigin({modelKey:key,effort,origin:{modelId:offerings[key].modelId,accessRouteId:res.accessRouteId,resourceId:res.id,credentialRef:res.credentialRef,plan:res.plan}},meta.targetId!)}
      catch{continue}
      options.push({key,effort})
    }
    if(!options.length){if(offeringKeys.includes(r.modelKey as NanKey))fixed[r.modelKey as NanKey]+=burden;continue}
    eligible.push({role,functionId,burden,route:r,options})
  }
  if(!eligible.length)throw new Error('No hay funciones delegables.')
  const allQuota=offeringKeys.reduce((n,k)=>n+BigInt(nanQuotas[k]),0n)
  const expectedNan=Object.values(fixed).reduce((n,x)=>n+x,0)+eligible.reduce((n,r)=>n+r.burden,0)
  if(expectedNan<=0)throw new Error('No hay consumo esperado de NaN.')
  let bestError:bigint|undefined,bestChanges=Infinity,bestTrial=Infinity,bestSignature='',bestAssignment:NanKey[]=[]
  let bestTotals:Record<NanKey,number>|null=null
  const trialCapBps=includeTrials?Math.round(10000*compositionJson.trialShareCapByObjective[meta.objective as keyof typeof compositionJson.trialShareCapByObjective]):0
  const choices:NanKey[]=[]
  const recurse=(idx:number,totals:Record<NanKey,number>,changes:number)=>{
    if(idx===eligible.length){
      const total=BigInt(expectedNan)
      const err=offeringKeys.reduce((n,key)=>{
        const delta=BigInt(totals[key])*allQuota-total*BigInt(nanQuotas[key])
        return n+(delta>=0n?delta:-delta)
      },0n)
      const trialTokens=totals.nan_qwen+totals.nan_mf
      if(BigInt(trialTokens)*10000n>BigInt(expectedNan)*BigInt(trialCapBps))return
      const signature=choices.join('\u0000')
      if(bestError===undefined||err<bestError||(err===bestError&&(trialTokens<bestTrial||(trialTokens===bestTrial&&(changes<bestChanges||(changes===bestChanges&&signature<bestSignature)))))){
        bestError=err;bestTrial=trialTokens;bestChanges=changes;bestSignature=signature;bestAssignment=[...choices];bestTotals={...totals}
      }
      return
    }
    const row=eligible[idx]
    for(const option of row.options){
      totals[option.key]+=row.burden
      choices.push(option.key)
      recurse(idx+1,totals,changes+Number(row.route.modelKey!==option.key))
      choices.pop();totals[option.key]-=row.burden
    }
  }
  if(eligible.length>10){
    const result=solveNanExactExpanded(eligible.map(r=>({burden:r.burden,previous:r.route.modelKey as NanKey,
      options:r.options.map(opt=>opt.key)})),fixed,nanQuotas,trialCapBps)
    bestError=BigInt(result.errorNumerator)
    bestTrial=result.trialTokens
    bestChanges=result.changes
    bestAssignment=result.choices
    bestTotals=result.totals
  }else{
    recurse(0,{...fixed},0)
  }
  if(!bestTotals||bestError===undefined)throw new Error('No se encontró una distribución compatible con el límite de riesgo experimental.')
  const totals=bestTotals as Record<NanKey,number>,changes:NanStaticChange[]=[]
  for(let i=0;i<eligible.length;i++){
    const row=eligible[i],key=bestAssignment[i]
    const effort=row.options.find(o=>o.key===key)!.effort
    if(row.route.modelKey===key)continue
    const origin={modelId:offerings[key].modelId,accessRouteId:res.accessRouteId,resourceId:res.id,credentialRef:res.credentialRef,plan:res.plan}
    const old=row.route.fallback?structuredClone(row.route.fallback):{
      modelKey:row.route.modelKey,effort:row.route.effort,origin:structuredClone(row.route.origin!)}
    const fallback=old.modelKey===key&&old.effort===effort?null:old
    const condition=row.route.condition+' Selector estático hipotético, sólo subtarea cerrada con fuentes, oráculo de aceptación y verificación por el propietario; sin acceso delegado a decisiones críticas. No es routing adaptativo ni un límite de tokens impuesto por el proveedor.'+(quotaFunctions[row.functionId][key]==='trial'?' Modelo trial sin equivalencia demostrada: ejecutar piloto y conservar la reserva anterior.':'')
    const rationale=`NaN reparto proporcional estático (${workloadJson.id}, escenario ${custom?'custom-'+custom.fingerprint:scenario}); estimados ${row.burden} tokens mensuales para ${row.role} bajo supuestos no calibrados. El optimizador minimiza la distancia de cuotas dentro de modelos aptos. Principal anterior preservado como reserva declarativa; no instalado. El perfil nativo no impone calidad ni reparto real.`
    const after:RouteDetail={...structuredClone(row.route),modelKey:key,effort,origin,fallback,condition,rationale}
    if(after.accelerator&&JSON.stringify(after.accelerator.origin)===JSON.stringify(origin)&&after.accelerator.effort===effort)after.accelerator=null
    newRoutes[row.role]=after
    changes.push({role:row.role,functionId:row.functionId,fromModelKey:row.route.modelKey,toModelKey:key,fromEffort:row.route.effort,toEffort:effort,expectedMonthlyTokens:row.burden,admission:quotaFunctions[row.functionId][key]!})
  }
  if(!changes.length&&!base?.helperOffloads.length)throw new Error('No hay cambios efectivos; la referencia ya es equivalente.')
  const distance=Number(bestError)/(2*expectedNan*Number(allQuota))
  const byModel=Object.fromEntries(offeringKeys.map(key=>{
    const value=totals[key],quota=nanQuotas[key]
    return [key,{offeringKey:key,quota,expectedTokens:value,expectedTokenShare:value/expectedNan,
      targetQuotaShare:quota/Number(allQuota),expectedFractionOfQuota:value/quota,
      idealFractionOfQuota:expectedNan/Number(allQuota),differencePercentagePoints:100*(value/expectedNan-quota/Number(allQuota)),
      trialOnly:key==='nan_qwen'||key==='nan_mf'}]
  })) as NanStaticPlan['byModel']
  const low=Math.round(10000*compositionJson.uncertainty.lowerTokenFactor)
  const high=Math.round(10000*compositionJson.uncertainty.upperTokenFactor)
  const stress:number[]=[]
  for(let flags=0;flags<16;flags++){
    const changed=Object.fromEntries(offeringKeys.map((key,i)=>[key,totals[key]*(flags&(1<<i)?high:low)])) as Record<NanKey,number>
    const combined=offeringKeys.reduce((sum,key)=>sum+changed[key],0)
    if(combined)stress.push(offeringKeys.reduce((n,key)=>n+Math.abs(changed[key]*Number(allQuota)-combined*nanQuotas[key]),0)/(2*combined*Number(allQuota)))
  }
  const trialTokens=totals.nan_qwen+totals.nan_mf
  const plan:NanStaticPlan={policyId:workloadJson.id,scenario:custom?'custom':scenario,scenarioLabel:assumptions.label,
    includeTrials,quotasStartAtFull:true,workloadObserved:false,state:'candidate-not-calibrated',
    expectedTokensAllEnabledRoles:expectedAll,expectedTokensOnNaN:expectedNan,
    expectedShareNaNOfAllRoles:expectedAll?expectedNan/expectedAll:0,
    distanceFromQuotaTarget:distance,distanceMetric:'total-variation-of-model-token-shares-vs-quota-shares',
    scenarioAssumptions:structuredClone(assumptions),byModel,byRole,changes,
    ...(custom?{customWorkload:structuredClone(custom)}:{}),
    qualityGuard:{trialShareCap:trialCapBps/10000,trialExpectedTokens:trialTokens,
      trialFractionOfExpectedNaN:trialTokens/expectedNan,
      qualityFirst:'role eligibility and trial-exposure hard limits; not an empirical model-quality score'},
    sensitivity:{minimumCornerDistance:Math.min(...stress),maximumCornerDistance:Math.max(...stress),
      lowerFactor:low/10000,upperFactor:high/10000,
      meaning:'16 stress scenarios on model token consumption; not confidence bounds'},
    limitations:structuredClone(workloadJson.qualityGates)}
  if(base){
    plan.composition={mode:base.compositionMode,activityPlan:structuredClone(base.activityPlan!),
      helperOffloads:structuredClone(base.helperOffloads),activityInventoryProfile:profileId,
      qualityPolicyId:compositionJson.id,sourceCoordinatorProfile:base.sourceProfile}
  }
  const id=profileId+(base?'::nan-hybrid-'+base.compositionMode+'-':'::nan-static-')+
    (custom?'custom-'+custom.fingerprint:scenario)+(includeTrials?'-trials':'-strict')
  const coordinator=newRoutes[meta.harness==='omp'?'default':'orchestrator']
  const result:Preset={id,kind:base?'nan-hybrid':'nan-static',sourceProfile:base?.sourceProfile||profileId,
    portfolio:meta.portfolio,meta:structuredClone(base?.meta||meta),routes:newRoutes,
    runtime:structuredClone(base?base.runtime:snapshot.runtimePolicies[profileId]),
    coordinatorPool:snapshot.catalog[coordinator.modelKey].pool,offloadPool:'NAN',
    limitations:[...structuredClone(workloadJson.qualityGates),...(base?structuredClone(compositionJson.limitations):[])],
    aliases:[id],nanStaticPlan:plan,...(base?{activityPlan:structuredClone(base.activityPlan!)}:{})}
  validateProfileOrigins(snapshot,meta,newRoutes,snapshot.access!.resourcesByPortfolio[meta.portfolio])
  return result
}

export function deriveNanHybridPreset(snapshot:Snapshot,profileId:string,scenario:NanScenario,
  includeTrials:boolean,complexity:'bounded'|'standard'|'complex',highImpact:boolean,
  mode:Exclude<NanComposition,'nan-only'>,customWorkload?:NanCustomWorkload):Preset{
  if(!['hybrid-preserve','hybrid-assist','hybrid-worker'].includes(mode))throw new Error('Modo híbrido no admitido.')
  if(highImpact||!['bounded','standard','complex'].includes(complexity))throw new Error('Actividad de alto impacto o complejidad no admitida.')
  if(mode==='hybrid-worker'&&complexity!=='bounded')throw new Error('El worker verificable requiere complejidad acotada.')
  if(!nanStaticCompatible(snapshot))throw new Error('Este snapshot no corresponde a la revisión híbrida de NaN.')
  const meta=snapshot.meta[profileId]
  if(!meta)throw new Error('Inventario de origen desconocido.')
  if(quotaJson.excludedDomains.includes(meta.domain))throw new Error('Dominio excluido del reparto híbrido.')
  const activity=deriveActivityPreset(snapshot,profileId,{complexity,highImpact:false})
  const validated=customWorkload?validateNanCustomWorkload(customWorkload):null
  if(validated&&validated.baseScenario!==scenario)throw new Error('El escenario personalizado no coincide con la base.')
  const routes=structuredClone(activity.routes)
  const helpers:NanHelperOffload[]=[]
  if(mode==='hybrid-assist'||mode==='hybrid-worker'){
    const workload=(validated?.functionWorkload||nanStaticScenarios[scenario].functionWorkload) as Record<string,{callsPerMonth:number;totalTokensPerCall:number}>
    const allTokens=Object.entries(routes).reduce((total,[role,r])=>{
      if(!r.enabled)return total
      const functionId=targetContracts[meta.harness].roles[role].functionId
      return total+workload[functionId].callsPerMonth*workload[functionId].totalTokensPerCall
    },0)
    const rule=compositionJson.compositionModes[mode]
    const maximum=rule.helperOffloads,cap=Math.floor(allTokens*rule.maxShareOfTotal)
    let added=0
    const resource=sourceResource(snapshot,meta.portfolio)
    const donors=Object.entries(snapshot.meta).filter(([,m])=>{
      const p=snapshot.portfolios[m.portfolio]
      return m.harness===meta.harness&&m.domain===meta.domain&&m.objective===meta.objective
        &&p.nan==='True'&&p.openai==='none'&&p.claude==='none'&&p.gateway==='none'
    })
    if(donors.length!==1)throw new Error('No hay donante único NaN nativo para este harness.')
    const [donorId]=donors[0],reference=snapshot.routeDetails[donorId]
    const functions=[...('additionalFunctions' in rule?rule.additionalFunctions:[]),...compositionJson.helperFunctionsInPriorityOrder]
    const permitted:readonly string[]=activityPolicy.levels[complexity].functions
    for(const functionId of functions){
      if(helpers.length>=maximum)break
      if(!permitted.includes(functionId)||protectedFns.has(functionId))continue
      for(const [role,r] of Object.entries(routes).sort(([a],[b])=>cmp(a,b))){
        if(helpers.length>=maximum)break
        if(!r.enabled||offeringKeys.includes(r.modelKey as NanKey)||targetContracts[meta.harness].roles[role].functionId!==functionId)continue
        const donor=reference[role],key=donor?.modelKey as NanKey
        if(!donor?.enabled||!['nan_ds','nan_glm'].includes(key)||quotaFunctions[functionId]?.[key]!=='eligible')continue
        const burden=workload[functionId].callsPerMonth*workload[functionId].totalTokensPerCall
        if(!burden||added+burden>cap)continue
        const origin={modelId:offerings[key].modelId,accessRouteId:resource.accessRouteId,
          resourceId:resource.id,credentialRef:resource.credentialRef,plan:resource.plan}
        resolveOrigin({modelKey:key,effort:donor.effort,origin},meta.targetId!)
        const old=structuredClone(r)
        const rollback={modelKey:old.modelKey,effort:old.effort,origin:structuredClone(old.origin!)}
        const condition=old.condition+' '+compositionJson.qualityFirst+' '+donor.condition+
          ' Rol auxiliar cerrado con aceptación comprobable; no se ejecutan reservas automáticamente.'
        routes[role]={...old,modelKey:key,effort:donor.effort,origin,fallback:rollback,condition,
          rationale:'Híbrido NaN auxiliar; donante '+donorId+'/'+role+
          '. El cambio es una propuesta condicionada a calidad, no una mejora demostrada.'}
        helpers.push({role,functionId,sourceProfile:donorId,fromModelKey:old.modelKey,toModelKey:key,
          expectedMonthlyTokens:burden,classification:'eligible',
          reason:'Función de bajo riesgo delimitada con donante nativo y recurso NaN declarado.'})
        added+=burden
      }
    }
  }
  const base:NanHybridBase={...activity,routes,meta:{...snapshot.meta[activity.sourceProfile],portfolio:meta.portfolio},
    portfolio:meta.portfolio,compositionMode:mode,helperOffloads:helpers}
  return deriveNanStaticPreset(snapshot,profileId,scenario,includeTrials,highImpact,base,validated||undefined)
}

export function collectNanStaticPresets(snapshot:Snapshot,selection:SubscriptionSelection|null,
  filters:Pick<ProfileFilters,'domain'|'objective'|'harness'|'nanScenario'|'nanTrials'|'highImpact'|'nanComposition'|'complexity'|'nanCustomWorkload'>){
  const result:{presets:Preset[];issues:{profileId:string;message:string}[];unchanged:number}={presets:[],issues:[],unchanged:0}
  if(!selection?.nan||!filters.domain||!filters.objective||filters.highImpact)return result
  if(!nanStaticCompatible(snapshot)){
    result.issues.push({profileId:'nan-static',message:'Snapshot desactualizado para la política estática. Regenera los datos.'})
    return result
  }
  const choice=filters.nanComposition||'all'
  if(!['all','nan-only','hybrid-preserve','hybrid-assist','hybrid-worker'].includes(choice)){
    result.issues.push({profileId:'nan-static',message:'Modo de composición desconocido.'});return result
  }
  for(const [pid,meta] of Object.entries(snapshot.meta)){
    if(meta.domain!==filters.domain||meta.objective!==filters.objective||(filters.harness&&filters.harness!==meta.harness))continue
    const portfolio=snapshot.portfolios[meta.portfolio]
    if(portfolio.nan!=='True'||!matchesSubscriptions(portfolio,selection,false))continue
    const multi=Number(portfolio.openai!=='none')+Number(portfolio.claude!=='none')+Number(portfolio.gateway!=='none')+1>=2
    let custom:NanCustomWorkload|undefined
    if(filters.nanCustomWorkload){
      try{custom=validateNanCustomWorkload(filters.nanCustomWorkload)}
      catch(error){result.issues.push({profileId:pid,message:error instanceof Error?error.message:String(error)});continue}
      if(custom.baseScenario!==(filters.nanScenario||'mixed')){
        result.issues.push({profileId:pid,message:'Escenario personalizado ajeno al escenario base seleccionado.'});continue
      }
    }
    const modes:(NanComposition)[] = choice==='all'?(multi?['hybrid-assist']:['nan-only']):[choice]
    for(const mode of modes){
      if(mode==='nan-only'&&choice==='all'&&multi)continue
      if(mode!=='nan-only'&&!multi)continue
      if(mode!=='nan-only'&&!matchesSubscriptions(portfolio,selection,true))continue
      try{
        const preset=mode==='nan-only'
          ?deriveNanStaticPreset(snapshot,pid,filters.nanScenario||'mixed',filters.nanTrials||false,filters.highImpact||false,undefined,custom)
          :deriveNanHybridPreset(snapshot,pid,filters.nanScenario||'mixed',filters.nanTrials||false,
            filters.complexity||'standard',filters.highImpact||false,mode,custom)
        result.presets.push(preset)
      }catch(error){
        const message=error instanceof Error?error.message:'No se pudo construir una candidata.'
        if(message.startsWith('No hay cambios efectivos')||message.startsWith('No hay funciones delegables')){
          result.unchanged++
        }else result.issues.push({profileId:pid+'/'+mode,message})
      }
    }
  }
  // In "all" mode, the first pass already includes separately labelled,
  // availability-compatible NaN-only subsets. Never add a duplicate if the
  // full inventory has no effective hybrid changes.

  return result
}
