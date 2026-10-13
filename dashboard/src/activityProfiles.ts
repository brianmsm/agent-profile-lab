import policyJson from '../../policies/activity-allocation.json'
import contractsJson from '../../contracts/harnesses.json'
import type { Snapshot, PortfolioInfo, RouteDetail, ProfileFilters, SubscriptionSelection } from './data'
import { matchesSubscriptions } from './data'
import type { Preset } from './presetStrategies'
import { validateProfileOrigins, targetForMeta, routePool } from './accessRouting'

export type Complexity = 'bounded' | 'standard' | 'complex'
export interface ActivitySettings { complexity: Complexity; highImpact: boolean }
export interface ActivityChange { role: string; functionId: string; pool: string; sourceProfile: string; fromModelKey: string; toModelKey: string; fromEffort: string; toEffort: string }
export interface ActivityPlan extends ActivitySettings {
  policyId: string; inventoryProfile: string; blockedReason: string | null; state: 'candidate-not-calibrated'
  changes: ActivityChange[]; retained: { role: string; functionId: string; reason: string }[]
}
export const activityPolicy = policyJson
export const DEFAULT_ACTIVITY: ActivitySettings = { complexity: 'standard', highImpact: false }
export const activityLevels = policyJson.levels
const contracts = contractsJson.harnesses as Record<string,{roles:Record<string,{functionId:string}>}>
const preferences = policyJson.preferredPools as Record<string,string[]>
const complexPreferences = policyJson.complexPreferredPools as Record<string,string[]>
const conditions = policyJson.conditions as Record<string,string>
export function inventoryPools(portfolio: PortfolioInfo): string[] {
  const pools:string[]=[]
  if(portfolio.openai!=='none')pools.push('OAI')
  if(portfolio.claude!=='none')pools.push('ANTHROPIC')
  if(portfolio.gateway!=='none')pools.push(portfolio.gateway.toUpperCase())
  if(portfolio.nan==='True')pools.push('NAN')
  return pools
}
export function activitySettings(filters: Pick<ProfileFilters,'complexity'|'highImpact'>): ActivitySettings {
  return {complexity:filters.complexity||DEFAULT_ACTIVITY.complexity,highImpact:filters.highImpact||false}
}
export function deriveActivityPreset(snapshot: Snapshot, profileId: string, settings: ActivitySettings): Preset {
  if(!Object.hasOwn(activityLevels,settings.complexity)||typeof settings.highImpact!=='boolean')throw new Error('Complejidad o impacto no admitidos.')
  const meta=snapshot.meta[profileId]
  if(!meta||!snapshot.access)throw new Error('Se requiere referencia e inventario de origen explícitos.')
  targetForMeta(meta)
  const inventory=snapshot.portfolios[meta.portfolio],pools=inventoryPools(inventory)
  if(pools.length<2)throw new Error('El reparto requiere al menos dos recursos de suscripción.')
  const source=(pool:string)=>Object.keys(snapshot.meta).sort().find(pid=>{
    const m=snapshot.meta[pid],p=snapshot.portfolios[m.portfolio],ps=inventoryPools(p)
    return m.harness===meta.harness&&m.domain===meta.domain&&m.objective===meta.objective
      &&ps.length===1&&ps[0]===pool&&(pool!=='OAI'||p.openai===inventory.openai)&&(pool!=='ANTHROPIC'||p.claude===inventory.claude)
  })
  const sources=Object.fromEntries(pools.map(pool=>[pool,source(pool)]))
  const owner=policyJson.coordinatorPriority.find(pool=>sources[pool])
  if(!owner)throw new Error('No hay referencia de coordinación compatible con ese inventario.')
  const origin=sources[owner]!,original=snapshot.routeDetails[origin],routes=structuredClone(original)
  const blocked=settings.highImpact?'high-impact':policyJson.excludedDomains.includes(meta.domain)?'domain-not-approved':null
  const changes:ActivityChange[]=[],retained:ActivityPlan['retained']=[]
  const permitted: readonly string[]=activityLevels[settings.complexity].functions
  for(const role of Object.keys(original).sort()){
    const route=original[role],functionId=contracts[meta.harness].roles[role]?.functionId
    if(!functionId)throw new Error('Rol fuera del contrato funcional.')
    const reason=blocked||(!route.enabled?'disabled-role':policyJson.protectedFunctions.includes(functionId)?'protected-function':!permitted.includes(functionId)?'complexity-boundary':null)
    if(reason){retained.push({role,functionId,reason});continue}
    const choices=settings.complexity==='complex'?(complexPreferences[functionId]||preferences[functionId]||[]):preferences[functionId]||[]
    let found:{pool:string;sourceId:string;donor:RouteDetail}|null=null
    for(const pool of choices){
      const id=sources[pool]
      if(pool===owner||!id)continue
      const donor=snapshot.routeDetails[id][role]
      if(!donor?.enabled||routePool(snapshot,donor)!==pool)continue
      if(donor.modelKey===route.modelKey&&donor.effort===route.effort)continue
      found={pool,sourceId:id,donor};break
    }
    if(!found){retained.push({role,functionId,reason:'no-reviewed-compatible-donor'});continue}
    const {pool,sourceId,donor}=found
    const fallback={modelKey:route.modelKey,effort:route.effort,...(route.origin?{origin:structuredClone(route.origin)}:{})}
    let condition=conditions[functionId]+' '+policyJson.safetyCondition+' '+route.condition
    if(donor.condition&&!condition.includes(donor.condition))condition+=' Condiciones de la referencia donante: '+donor.condition
    routes[role]={...structuredClone(route),modelKey:donor.modelKey,effort:donor.effort,fallback,
      ...(donor.origin?{origin:structuredClone(donor.origin)}:{}),
      condition,
      rationale:`Candidata por función ${functionId}; complejidad ${settings.complexity}. Referencia donante: ${sourceId}/${role}. Coordinación y reserva: ${origin}/${role}. No es una recomendación calibrada. `+donor.rationale}
    changes.push({role,functionId,pool,sourceProfile:sourceId,fromModelKey:route.modelKey,toModelKey:donor.modelKey,fromEffort:route.effort,toEffort:donor.effort})
  }
  const plan:ActivityPlan={policyId:policyJson.id,...settings,blockedReason:blocked,inventoryProfile:profileId,changes,retained,state:'candidate-not-calibrated'}
  const id=profileId+'::activity-'+settings.complexity+(settings.highImpact?'-high-impact':'')
  const result:Preset={id,kind:'activity-distributed',sourceProfile:origin,portfolio:meta.portfolio,meta:{...snapshot.meta[origin],portfolio:meta.portfolio},routes,
    runtime:snapshot.runtimePolicies[origin],coordinatorPool:owner,offloadPool:[...new Set(changes.map(c=>c.pool))].sort().join('+')||null,
    limitations:[...policyJson.limitations],aliases:[id],activityPlan:plan}
  validateProfileOrigins(snapshot,result.meta,routes,snapshot.access.resourcesByPortfolio[result.portfolio])
  return result
}
export interface ActivityIssue { profileId: string; message: string }
export function collectActivityPresets(snapshot: Snapshot, selection: SubscriptionSelection|null, settings: ActivitySettings, scope: {domain?:string;objective?:string;harness?:string} = {}): { presets: Preset[]; issues: ActivityIssue[] } {
  const result: { presets: Preset[]; issues: ActivityIssue[] } = { presets: [], issues: [] }
  if(!selection||!snapshot.access)return result
  const inventories=new Set(Object.entries(snapshot.portfolios).filter(([,p])=>matchesSubscriptions(p,selection,true)&&inventoryPools(p).length>=2).map(([id])=>id))
  for(const [id,meta] of Object.entries(snapshot.meta)) {
    if(!inventories.has(meta.portfolio) || (scope.domain && meta.domain!==scope.domain) || (scope.objective && meta.objective!==scope.objective) || (scope.harness && meta.harness!==scope.harness))continue
    try { result.presets.push(deriveActivityPreset(snapshot,id,settings)) }
    catch(error) { result.issues.push({profileId:id,message:error instanceof Error?error.message:'No se pudo validar esta candidata.'}) }
  }
  return result
}
export function activityPresets(snapshot: Snapshot, selection: SubscriptionSelection|null, settings: ActivitySettings): Preset[] {
  return collectActivityPresets(snapshot,selection,settings).presets
}
