import {describe,test,expect} from 'bun:test'
import fixtureData from './fixtures/activity-fixture.json'
import staticApproval from '../../policies/nan-static-approval.json'
import type {Snapshot,ProfileFilters} from '../src/data'
import {DEFAULT_FILTERS} from '../src/data'
import {makeNanCustomWorkload,sourceNanWorkload,validateNanCustomWorkload} from '../src/nanCustomWorkload'
import {deriveNanStaticPreset,deriveNanHybridPreset,collectNanStaticPresets} from '../src/nanStaticProfiles'
import {createProfileQuery} from '../src/profileQuery'
import {deriveActivityPreset} from '../src/activityProfiles'
import {compileAccessBundle} from '../src/accessExport'
const fixture=()=>{
  const s=structuredClone(fixtureData) as unknown as Snapshot
  Object.assign(s.access!.inputSha256,staticApproval.inputSha256)
  return s
}
const create=(change:'implementation'|'status'|'same'='implementation')=>{
  const rows=sourceNanWorkload('mixed')
  if(change==='implementation')rows['bounded-implementation'].callsPerMonth*=4
  if(change==='status')rows['status-reporting'].callsPerMonth*=8
  return makeNanCustomWorkload('mixed','Mi carga revisada','Supuestos propios para tareas de investigación',rows)
}
describe('custom workload genuinely reaches native profile and source manifest',()=>{
  test('changing a monthly frequency changes scenario identity, workload totals and analytical provenance',async()=>{
    const s=fixture(),original=deriveNanStaticPreset(s,'gentle-shell--nan-research-balanced','mixed',true,false)
    const custom=create(),p=deriveNanStaticPreset(s,'gentle-shell--nan-research-balanced','mixed',true,false,undefined,custom)
    expect(p.id).toContain('custom-'+custom.fingerprint)
    expect(p.id).not.toEqual(original.id)
    expect(p.nanStaticPlan?.scenario).toBe('custom')
    expect(p.nanStaticPlan?.scenarioLabel).toBe('Mi carga revisada')
    expect(p.nanStaticPlan?.customWorkload).toEqual(custom)
    expect(p.nanStaticPlan?.scenarioAssumptions.functionWorkload['bounded-implementation']).toEqual(custom.functionWorkload['bounded-implementation'])
    expect(p.nanStaticPlan!.expectedTokensAllEnabledRoles).toBeGreaterThan(original.nanStaticPlan!.expectedTokensAllEnabledRoles)
    const bundle=await compileAccessBundle(s,p,{mode:'preserve'})
    expect(bundle.manifest.nanStaticPlan?.customWorkload).toEqual(custom)
    expect(bundle.manifest.nativeArtifact.sha256).toBe(new Bun.CryptoHasher('sha256').update(bundle.native.content).digest('hex'))
    expect(bundle.manifest.validation.inferencesSent).toBe(0)
  })
  test('hybrid helper budget and resulting quota forecast use the customized scenario, not only its label',()=>{
    const s=fixture(),custom=create('status')
    const p=deriveNanHybridPreset(s,'omp--pro100-go-nan-research-balanced','mixed',true,'bounded',false,'hybrid-worker',custom)
    expect(p.nanStaticPlan?.customWorkload?.fingerprint).toBe(custom.fingerprint)
    const row=p.nanStaticPlan!.byRole.find(x=>x.functionId==='status-reporting')
    expect(row?.assumedCalls).toBe(custom.functionWorkload['status-reporting'].callsPerMonth)
    expect(p.nanStaticPlan?.composition?.mode).toBe('hybrid-worker')
  })
  test('filters cache and stable preset selection honor changed workload content',()=>{
    const s=fixture(),query=createProfileQuery(s)
    const filters:ProfileFilters={...DEFAULT_FILTERS,domain:'research',objective:'balanced',
      strategy:'nan-static',subscriptions:{openai:'none',claude:'none',gateway:'none',nan:true},
      nanScenario:'mixed',nanTrials:true,nanComposition:'nan-only'}
    const a=query({...filters,nanCustomWorkload:create('implementation')},false)
    const b=query({...filters,nanCustomWorkload:create('status')},false)
    expect(a).not.toBe(b)
    expect(a.items[0].id).not.toBe(b.items[0].id)
    expect(a.items[0].nanStaticPlan?.expectedTokensAllEnabledRoles).not.toBe(b.items[0].nanStaticPlan?.expectedTokensAllEnabledRoles)
    expect(query({...filters,nanCustomWorkload:create('implementation')},false)).toBe(a)
    expect(query({...filters,nanCustomWorkload:null},false).items[0].nanStaticPlan?.scenario).toBe('mixed')
  })
  test('no stale base/scenario combination and no source mutation',()=>{
    const s=fixture(),old=JSON.stringify(s.routeDetails),custom=create()
    expect(()=>deriveNanStaticPreset(s,'omp--nan-research-balanced','routine',false,false,undefined,custom)).toThrow('escenario')
    const bad=structuredClone(custom)
    bad.functionWorkload['status-reporting'].callsPerMonth=999
    expect(()=>validateNanCustomWorkload(bad)).toThrow('Identificador')
    const result=collectNanStaticPresets(s,{openai:'none',claude:'none',gateway:'none',nan:true},
      {domain:'research',objective:'balanced',harness:'',nanScenario:'routine',nanTrials:false,nanComposition:'nan-only',
        highImpact:false,complexity:'bounded',nanCustomWorkload:custom})
    expect(result.presets).toHaveLength(0)
    expect(result.issues.length).toBeGreaterThan(0)
    expect(JSON.stringify(s.routeDetails)).toBe(old)
  })
  test('custom labels cannot silently impersonate raw provider tokens or invalidate protected roles',()=>{
    const s=fixture()
    const custom=create()
    const p=deriveNanHybridPreset(s,'gentle-shell--pro100-go-nan-research-balanced','mixed',true,'bounded',false,'hybrid-worker',custom)
    expect(p.nanStaticPlan!.workloadObserved).toBe(false)
    const baseline=deriveActivityPreset(s,'gentle-shell--pro100-go-nan-research-balanced',{complexity:'bounded',highImpact:false})
    expect(p.routes.orchestrator).toEqual(baseline.routes.orchestrator)
    expect(p.nanStaticPlan!.qualityGuard.trialFractionOfExpectedNaN).toBeLessThanOrEqual(p.nanStaticPlan!.qualityGuard.trialShareCap+1e-12)
    expect(p.runtime).toEqual(s.runtimePolicies[p.sourceProfile])
  })
})
