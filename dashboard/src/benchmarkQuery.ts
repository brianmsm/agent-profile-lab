import type { Benchmark } from './data'
import { configuredRecord, explorerGroups, typedExplorerGroups } from './modelInsightsData'
import type { AssignedModel, ExplorerGroup, TypedExplorerOptions } from './modelInsightsData'

/** Exact inverted indexes for an immutable snapshot revision. Source indices and
 * original row references survive selection; no label similarity, sampling or rounding. */
export function createBenchmarkQuery(records: Benchmark[]) {
  const byId=new Map<string,number[]>(),byName=new Map<string,number[]>(),untypedName=new Map<string,number[]>()
  const add=(map:Map<string,number[]>,key:string,i:number)=>{const list=map.get(key)||[];list.push(i);map.set(key,list)}
  let typed=false
  records.forEach((row,i)=>{add(byName,row.model,i);if(row.measurement){typed=true;if(row.measurement.modelId)add(byId,row.measurement.modelId,i)}else add(untypedName,row.model,i)})
  const cache=new Map<string,ExplorerGroup[]>()
  const indices=(model:AssignedModel)=>model.modelId?[...(byId.get(model.modelId)||[]),...(untypedName.get(model.model)||[])]:byName.get(model.model)||[]
  return {
    matching:(model:AssignedModel)=>indices(model).sort((a,b)=>a-b).map(i=>records[i]),
    groups:(models:AssignedModel[],includeOther:boolean,options:TypedExplorerOptions={})=>{
      const key=JSON.stringify([models.map(m=>[m.model,m.modelId,m.efforts]),includeOther,!!options.includeHistorical,!!options.includeIssues,!!options.includeOperational])
      const hit=cache.get(key);if(hit)return hit
      const rows=[...new Set(models.flatMap(indices))].sort((a,b)=>a-b).map(index=>({row:records[index],index,configured:configuredRecord(records[index],models)}))
      const result=typed?typedExplorerGroups(records,models,includeOther,options,rows):explorerGroups(records,models,includeOther,options)
      cache.set(key,result);if(cache.size>16)cache.delete(cache.keys().next().value!)
      return result
    }
  }
}
// Only the UI uses this revision-scoped cache. Pure public functions remain
// uncached so validators and mutable test fixtures cannot inherit stale answers.
const revisions=new WeakMap<Benchmark[],ReturnType<typeof createBenchmarkQuery>>()
export function benchmarkQueryFor(records:Benchmark[]) {
  let query=revisions.get(records)
  if(!query){query=createBenchmarkQuery(records);revisions.set(records,query)}
  return query
}
