import {describe,test,expect} from 'bun:test'
import data from './fixtures/activity-fixture.json'
import approval from '../../policies/nan-static-approval.json'
import type {ProfileFilters,Snapshot} from '../src/data'
import {DEFAULT_FILTERS} from '../src/data'
import {deriveNanStaticPreset,collectNanStaticPresets,nanStaticScenarios} from '../src/nanStaticProfiles'
import {createProfileQuery} from '../src/profileQuery'
import {presetNativeExport,presetRolesCsv,presetAnalysis} from '../src/presetStrategies'
import {compileAccessBundle} from '../src/accessExport'
import {strategyAvailable} from '../src/profileBrowser'
const fixture=()=>{
  const s=structuredClone(data) as unknown as Snapshot
  Object.assign(s.access!.inputSha256,approval.inputSha256)
  return s
}
const selection={openai:'pro100',claude:'none',gateway:'go',nan:true} as const
const filters:ProfileFilters={...DEFAULT_FILTERS,domain:'research',objective:'balanced',
  strategy:'nan-static',subscriptions:selection,nanScenario:'mixed',nanTrials:true,nanComposition:'nan-only'}
describe('static independent NaN quota strategy',()=>{
  test('works with a 100-percent, four-quota starting assumption and full scenario disclosures',()=>{
    const s=fixture(),p=deriveNanStaticPreset(s,'gentle-shell--nan-research-balanced','mixed',true,false),plan=p.nanStaticPlan!
    expect(plan.quotasStartAtFull).toBe(true);expect(plan.workloadObserved).toBe(false)
    expect(plan.state).toBe('candidate-not-calibrated')
    expect(plan.expectedTokensOnNaN).toBeGreaterThan(0)
    expect(plan.distanceFromQuotaTarget).toBeGreaterThan(0)
    expect(plan.distanceFromQuotaTarget).toBeLessThan(1)
    expect(Object.keys(nanStaticScenarios)).toEqual(['routine','mixed','implementation'])
    expect(Object.values(plan.byModel).reduce((sum,m)=>sum+m.expectedTokenShare,0)).toBeCloseTo(1)
    expect(Object.values(plan.byModel).reduce((sum,m)=>sum+m.targetQuotaShare,0)).toBeCloseTo(1)
    expect(Object.values(plan.byModel).filter(m=>m.expectedTokens>0)).toHaveLength(4)
  })
  test('trial routes require explicit opt in, and no share is artificially forced',()=>{
    const s=fixture(),p=deriveNanStaticPreset(s,'gentle-shell--nan-research-balanced','mixed',false,false)
    expect(p.nanStaticPlan?.changes.every(c=>!['nan_qwen','nan_mf'].includes(c.toModelKey))).toBe(true)
    expect(p.nanStaticPlan?.byModel.nan_qwen.expectedTokens).toBe(0)
    expect(p.nanStaticPlan?.byModel.nan_mf.expectedTokens).toBe(0)
  })
  test('protected and inactive roles stay exactly unchanged in both harnesses',()=>{
    const s=fixture()
    for(const h of ['gentle-shell','omp'])for(const scenario of ['routine','mixed','implementation'] as const){
      const id=h+'--nan-research-balanced',p=deriveNanStaticPreset(s,id,scenario,true,false)
      const changes=new Set(p.nanStaticPlan!.changes.map(c=>c.role))
      expect(p.runtime).toEqual(s.runtimePolicies[id])
      for(const [role,r] of Object.entries(p.routes)){
        expect(r.enabled).toBe(s.routeDetails[id][role].enabled)
        if(!changes.has(role))expect(r).toEqual(s.routeDetails[id][role])
        else {
          const old=s.routeDetails[id][role],original=old.fallback||{modelKey:old.modelKey,effort:old.effort,origin:old.origin}
          expect(r.fallback).toEqual(original.modelKey===r.modelKey&&original.effort===r.effort?null:original)
        }
      }
    }
  })
  test('does not promote OpenAI or OpenCode Go roles into NaN merely to use quota',()=>{
    const s=fixture()
    expect(()=>deriveNanStaticPreset(s,'gentle-shell--pro100-go-nan-research-balanced','mixed',true,false)).toThrow('No hay funciones delegables')
    expect(()=>deriveNanStaticPreset(s,'omp--pro100-go-nan-research-balanced','mixed',true,false)).toThrow('No hay funciones delegables')
    const result=collectNanStaticPresets(s,selection,filters)
    expect(result.presets.some(p=>p.portfolio==='nan')).toBe(true)
    expect(result.presets.every(p=>p.portfolio==='nan')).toBe(true)
  })
  test('availability filters preserve the exact source portfolio rather than relabeling a subset',()=>{
    const s=fixture(),query=createProfileQuery(s)
    const result=query(filters,false)
    expect(result.items.length).toBeGreaterThan(0)
    expect(result.items.every(p=>p.kind==='nan-static')).toBe(true)
    expect(result.items.every(p=>p.portfolio==='nan')).toBe(true)
    expect(result.items.every(p=>p.nanStaticPlan)).toBe(true)
    expect(query(filters,false)).toBe(result)
    expect(query({...filters,strategy:''},false).items.some(p=>p.nanStaticPlan)).toBe(false)
    expect(strategyAvailable('nan-static',{...filters,subscriptions:{...selection,nan:false}})).toBe(false)
  })
  test('complexity, objective and hypothetical work frequencies have distinct audit trails',()=>{
    const s=fixture(),id='gentle-shell--nan-research-balanced',a=deriveNanStaticPreset(s,id,'routine',true,false),b=deriveNanStaticPreset(s,id,'mixed',true,false)
    expect(a.id).not.toBe(b.id)
    expect(a.nanStaticPlan!.scenarioAssumptions.functionWorkload['bounded-exploration'].callsPerMonth).not.toEqual(b.nanStaticPlan!.scenarioAssumptions.functionWorkload['bounded-exploration'].callsPerMonth)
    expect(a.nanStaticPlan!.distanceFromQuotaTarget).not.toBe(b.nanStaticPlan!.distanceFromQuotaTarget)
  })
  test('high impact, excluded security domains and stale source metadata fail closed',()=>{
    const s=fixture()
    expect(()=>deriveNanStaticPreset(s,'gentle-shell--nan-research-balanced','mixed',true,true)).toThrow()
    expect(()=>deriveNanStaticPreset(s,'gentle-shell--nan-cybersecurity-balanced','mixed',true,false)).toThrow()
    s.access!.inputSha256['policies/nan-static-workloads.json']='0'.repeat(64)
    expect(collectNanStaticPresets(s,selection,filters).issues[0]?.message).toContain('Snapshot')
    expect(()=>deriveNanStaticPreset(s,'gentle-shell--nan-research-balanced','mixed',true,false)).toThrow('regenerar')
  })
  test('native format and analytical manifest preserve provenance and conditional trial claims',async()=>{
    const s=fixture(),p=deriveNanStaticPreset(s,'gentle-shell--nan-research-balanced','mixed',true,false)
    const native=presetNativeExport(s,p),csv=presetRolesCsv(s,p),analysis=presetAnalysis(s,p)
    expect(native.content).toContain('nan/mimo-v2.6-flash')
    expect(native.content).toContain('nan/qwen3.8-flash')
    expect(csv).toContain('nan/mimo-v2.6-flash')
    expect(analysis.profile.nanStaticPlan).toEqual(p.nanStaticPlan)
    const bundle=await compileAccessBundle(s,p,{mode:'preserve'})
    expect(bundle.manifest.nanStaticPlan).toEqual(p.nanStaticPlan)
    expect(bundle.manifest.selectionPolicy).toBe('nan-static')
    expect(bundle.manifest.nativeArtifact.sha256).toBe(new Bun.CryptoHasher('sha256').update(bundle.native.content).digest('hex'))
    expect(bundle.manifest.status).toBe('candidate')
  })
  test('source corpus and original reference routes do not mutate',()=>{
    const s=fixture(),before=JSON.stringify(s.routeDetails)
    deriveNanStaticPreset(s,'gentle-shell--nan-research-balanced','mixed',true,false)
    expect(JSON.stringify(s.routeDetails)).toBe(before)
  })
})
