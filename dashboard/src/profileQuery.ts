import {collectNanStaticPresets} from './nanStaticProfiles'
import {collectReviewedCandidates} from './selectionCandidates'
import type { Snapshot, ProfileFilters } from './data'
import { presets, nativeMapEquivalence } from './presetStrategies'
import { collectActivityPresets, activitySettings } from './activityProfiles'
import { filteredPresets, normalizeProfileFilters } from './profileBrowser'

/** One engine per immutable dataset revision. No global cache by profile ID.
 * Event handlers and React render share the same exact query result. */
export function createProfileQuery(snapshot:Snapshot) {
  const references=presets(snapshot)
  type Activities=ReturnType<typeof collectActivityPresets>
  type Result={filters:ProfileFilters;references:typeof references;activity:ReturnType<typeof activitySettings>;allPresets:typeof references;items:typeof references;nativeEquivalent:Map<string,string[]>;activityIssues:Activities['issues'];reviewIssues:Activities['issues'];unchangedRecipes:number;nanStaticIssues:{profileId:string;message:string}[];nanStaticUnchanged:number}
  const activityCache=new Map<string,Activities>(),resultCache=new Map<string,Result>()
  const retain=<T,>(map:Map<string,T>,key:string,value:T,limit:number)=>{map.set(key,value);if(map.size>limit)map.delete(map.keys().next().value!);return value}
  return (input:ProfileFilters,audit:boolean):Result=>{
    const filters=normalizeProfileFilters(input), key=JSON.stringify([filters,audit])
    const cached=resultCache.get(key)
    if(cached)return cached
    const activity=activitySettings(filters)
    const activityKey=JSON.stringify([filters.subscriptions,activity,filters.domain,filters.objective,filters.harness])
    const scope={domain:filters.domain,objective:filters.objective,harness:filters.harness}
    const buildActivity=filters.strategy===''||filters.strategy==='activity-distributed'
    const collection=buildActivity?(activityCache.get(activityKey)||retain(activityCache,activityKey,collectActivityPresets(snapshot,filters.subscriptions,activity,scope),12)):{presets:[],issues:[]}
    const reviewed=filters.strategy==='reviewed-candidate'&&!audit?collectReviewedCandidates(snapshot,filters,activity):{presets:[],issues:[],unchanged:0}
    const nanStatic=filters.strategy==='nan-static'&&!audit?collectNanStaticPresets(snapshot,filters.subscriptions,filters):{presets:[],issues:[],unchanged:0}
    const allPresets=[...references,...collection.presets,...reviewed.presets,...nanStatic.presets]
    const items=filteredPresets(snapshot,filters,audit,allPresets)
    return retain(resultCache,key,{filters,references,activity,allPresets,items,nativeEquivalent:nativeMapEquivalence(snapshot,items),activityIssues:collection.issues,reviewIssues:reviewed.issues,unchangedRecipes:reviewed.unchanged,nanStaticIssues:nanStatic.issues,nanStaticUnchanged:nanStatic.unchanged},32)
  }
}
