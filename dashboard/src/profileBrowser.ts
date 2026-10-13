import type { Snapshot, ProfileFilters } from './data'
import { matchesSubscriptions, DOMAINS, OBJECTIVES } from './data'
import { compatibleWithAvailability, groupEquivalentPresets, providerParticipation } from './presetStrategies'
import type { Preset } from './presetStrategies'
import { STRATEGIES, portfolioLabel, poolLabel } from './presentation'
import { activityPolicy } from './activityProfiles'

export function strategyAvailable(kind:ProfileFilters['strategy'],filters:ProfileFilters):boolean{
  const s=filters.subscriptions
  if(kind===''||kind==='matrix')return true
  if(kind==='nan-static'||kind==='nan-hybrid')return !!s&&s.nan
  if(kind==='reviewed-candidate')return !!s&&(s.openai!=='none'||s.claude!=='none'||s.gateway!=='none'||s.nan)
  if(kind==='openai-led')return !!s&&s.openai!=='none'
  if(kind==='nan-volume')return !!s&&s.nan&&s.openai!=='none'&&!activityPolicy.excludedDomains.includes(filters.domain)&&!filters.highImpact
  if(kind==='activity-distributed')return !!s&&Number(s.openai!=='none')+Number(s.claude!=='none')+Number(s.gateway!=='none')+Number(s.nan)>=2
  return false
}
export function normalizeProfileFilters(filters:ProfileFilters):ProfileFilters{
  return strategyAvailable(filters.strategy,filters)?filters:{...filters,strategy:''}
}
export function matchesSearch(snapshot:Snapshot,preset:Preset,query:string){
  const needle=query.trim().toLocaleLowerCase('es')
  if(!needle)return true
  return [preset.id,preset.sourceProfile,...preset.aliases,STRATEGIES[preset.kind],DOMAINS[preset.meta.domain],OBJECTIVES[preset.meta.objective],preset.meta.harness,
    portfolioLabel(snapshot.portfolios[preset.portfolio]),...Object.entries(preset.routes).flatMap(([role,r])=>[role,r.condition,r.rationale,...[r,r.fallback,r.accelerator].flatMap(x=>x?[x.modelKey,snapshot.catalog[x.modelKey]?.name,snapshot.catalog[x.modelKey]?.selector,poolLabel(snapshot.catalog[x.modelKey]?.pool||''),x.effort,x.origin?.modelId,x.origin?.accessRouteId,x.origin?.plan]:[])])].join(' ').toLocaleLowerCase('es').includes(needle)
}
export function containsId(preset:Preset,id:string|null|undefined){return !!id&&(preset.id===id||preset.aliases.includes(id))}
export function filteredPresets(snapshot:Snapshot,filters:ProfileFilters,audit:boolean,all:Preset[]){
  const candidates=all.filter(p=>{
    const m=p.meta
    return (!filters.domain||m.domain===filters.domain)&&(!filters.objective||m.objective===filters.objective)&&(!filters.harness||m.harness===filters.harness)
      &&(!filters.strategy||p.kind===filters.strategy||(filters.strategy==='nan-static'&&p.kind==='nan-hybrid'))&&strategyAvailable(p.kind,filters)
      &&(audit?p.kind==='matrix'&&matchesSubscriptions(snapshot.portfolios[p.portfolio],filters.subscriptions,true):compatibleWithAvailability(snapshot,p,filters.subscriptions))
      &&(!filters.portfolio||p.portfolio===filters.portfolio)&&matchesSearch(snapshot,p,filters.search)
  })
  const exact=(p:Preset)=>filters.subscriptions&&matchesSubscriptions(snapshot.portfolios[p.portfolio],filters.subscriptions,true)?0:1
  // Full-inventory references precede compatible subsets; this is navigation order,
  // not a performance/cost ranking. Grouping retains the exact-inventory representative.
  candidates.sort((a,b)=>exact(a)-exact(b)||a.id.localeCompare(b.id))
  const rank=(p:Preset)=>p.kind==='nan-hybrid'?-2:p.kind==='nan-static'?-1:p.kind==='activity-distributed'?0:p.kind==='matrix'&&exact(p)===0?1:p.kind==='openai-led'?2:p.kind==='nan-volume'?3:4
  return groupEquivalentPresets(snapshot,candidates,{preferFirst:true}).sort((a,b)=>rank(a)-rank(b)||exact(a)-exact(b)||a.meta.harness.localeCompare(b.meta.harness)||a.id.localeCompare(b.id))
}
export function resolveSelection(items:Preset[],page:number,selectedId:string|null|undefined,size:number){
  const pages=Math.max(1,Math.ceil(items.length/size)),safe=Math.max(0,Math.min(page,pages-1))
  const visible=items.slice(safe*size,(safe+1)*size)
  const selected=visible.find(p=>containsId(p,selectedId))||visible[0]
  return {pages,page:safe,visible,selected}
}
export function configuredShares(snapshot:Snapshot,preset:Preset){
  const entries=providerParticipation(snapshot,preset,null).filter(p=>p.roles.length)
  const total=entries.reduce((sum,p)=>sum+p.roles.length,0)
  return {entries:entries.map(e=>({...e,count:e.roles.length,share:total?e.roles.length/total:0})),total}
}
