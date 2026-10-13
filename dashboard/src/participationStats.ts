import modelCatalog from '../../catalog/models.json'
import type { Snapshot, ProfileMeta } from './data'
import { routePool } from './accessRouting'

export type ReferenceKind = 'primary' | 'fallback' | 'accelerator'
export type EnabledState = 'enabled' | 'disabled' | 'all'
export type StatDimension = 'model' | 'pool' | 'role' | 'harness' | 'domain' | 'effort'
export interface StatisticsScope { domain: string; harness: string; objective: string; pool: string; kind: ReferenceKind; state: EnabledState }
export const DEFAULT_STAT_SCOPE: StatisticsScope = { domain:'',harness:'',objective:'',pool:'',kind:'primary',state:'enabled' }
export interface ParticipationRow {
  profileId:string; role:string; kind:ReferenceKind; enabled:boolean; modelId:string; modelKey:string; modelName:string; pool:string; effort:string
  harness:string; domain:string; objective:string; portfolio:string
}
export interface StatGroup { key:string; label:string; count:number; profiles:number; share:number; modelKeys:string[] }
export interface ProfileParticipation { profileId:string; count:number; total:number; share:number; roles:string[]; pools:string[] }
const modelNames=Object.fromEntries(Object.entries(modelCatalog.models).map(([id,m])=>[id,m.name])) as Record<string,string>
export function declaredModelId(snapshot:Snapshot,key:string){ return snapshot.catalog[key].modelId||`offering:${key}` }
export function declaredModelName(snapshot:Snapshot,key:string){return modelNames[declaredModelId(snapshot,key)]||snapshot.catalog[key].name}
export function participationRows(snapshot:Snapshot):ParticipationRow[]{
  const rows:ParticipationRow[]=[]
  for(const [profileId,meta] of Object.entries(snapshot.meta)){
    for(const [role,primary] of Object.entries(snapshot.routeDetails[profileId])){
      for(const [kind,ref] of [['primary',primary],['fallback',primary.fallback],['accelerator',primary.accelerator]] as const){
        if(!ref)continue
        rows.push({profileId,role,kind,enabled:primary.enabled,modelId:ref.origin?.modelId||declaredModelId(snapshot,ref.modelKey),
          modelKey:ref.modelKey,modelName:declaredModelName(snapshot,ref.modelKey),pool:routePool(snapshot,ref),effort:ref.effort,
          harness:meta.harness,domain:meta.domain,objective:meta.objective,portfolio:meta.portfolio})
      }
    }
  }
  return rows
}
export function matchesStatisticsMeta(meta:Pick<ProfileMeta,'domain'|'harness'|'objective'>,scope:StatisticsScope){
  return (!scope.domain||meta.domain===scope.domain)&&(!scope.harness||meta.harness===scope.harness)&&(!scope.objective||meta.objective===scope.objective)
}
export function scopedParticipation(rows:ParticipationRow[],scope:StatisticsScope){
  return rows.filter(row=>matchesStatisticsMeta(row,scope)&&row.kind===scope.kind&&(!scope.pool||row.pool===scope.pool)
    &&(scope.state==='all'||row.enabled===(scope.state==='enabled')))
}
export function groupParticipation(rows:ParticipationRow[],dimension:StatDimension,snapshot?:Snapshot,includeZero=false):StatGroup[]{
  const groups=new Map<string,{label:string;count:number;profiles:Set<string>;modelKeys:Set<string>}>()
  if(dimension==='model'&&includeZero&&snapshot){
    for(const key of Object.keys(snapshot.catalog)){
      const id=declaredModelId(snapshot,key)
      const item=groups.get(id)||{label:declaredModelName(snapshot,key),count:0,profiles:new Set<string>(),modelKeys:new Set<string>()}
      item.modelKeys.add(key);groups.set(id,item)
    }
  }
  for(const row of rows){
    const key=dimension==='model'?row.modelId:row[dimension]
    const label=dimension==='model'?row.modelName:key||'Sin especificar'
    const item=groups.get(key)||{label,count:0,profiles:new Set<string>(),modelKeys:new Set<string>()}
    item.count++;item.profiles.add(row.profileId);item.modelKeys.add(row.modelKey);groups.set(key,item)
  }
  return [...groups.entries()].map(([key,g])=>({key,label:g.label,count:g.count,profiles:g.profiles.size,share:rows.length?g.count/rows.length:0,modelKeys:[...g.modelKeys].sort()}))
    .sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label)||a.key.localeCompare(b.key))
}
export function modelParticipationProfiles(rows:ParticipationRow[],modelId:string,order:'count'|'share'='count'):ProfileParticipation[]{
  const totals=new Map<string,number>(),groups=new Map<string,{count:number;roles:Set<string>;pools:Set<string>}>()
  for(const row of rows){
    totals.set(row.profileId,(totals.get(row.profileId)||0)+1)
    if(row.modelId!==modelId)continue
    const item=groups.get(row.profileId)||{count:0,roles:new Set<string>(),pools:new Set<string>()}
    item.count++;item.roles.add(row.role);item.pools.add(row.pool);groups.set(row.profileId,item)
  }
  return [...groups.entries()].map(([profileId,g])=>({profileId,count:g.count,total:totals.get(profileId)!,share:g.count/totals.get(profileId)!,roles:[...g.roles].sort(),pools:[...g.pools].sort()}))
    .sort((a,b)=>(order==='share'?b.share-a.share||b.count-a.count:b.count-a.count||b.share-a.share)||a.profileId.localeCompare(b.profileId))
}
export function statisticsCsv(rows:ParticipationRow[]):string{
  const escape=(value:unknown)=>{let s=String(value);if(/^[=+\-@\t\r]/u.test(s))s="'"+s;return /[",\r\n]/u.test(s)?'"'+s.replaceAll('"','""')+'"':s}
  const fields:(keyof ParticipationRow)[]=['profileId','harness','domain','objective','portfolio','role','kind','enabled','modelId','modelKey','modelName','pool','effort']
  return '\ufeff'+[fields.join(','),...rows.map(row=>fields.map(key=>escape(row[key])).join(','))].join('\r\n')+'\r\n'
}
