import {describe,test,expect} from 'bun:test'
import snapshotFixture from './fixtures/activity-fixture.json'
import approval from '../../policies/nan-static-approval.json'
import type {Snapshot,ProfileFilters} from '../src/data'
import {DEFAULT_FILTERS} from '../src/data'
import {deriveNanHybridPreset,nanCompositionPolicy} from '../src/nanStaticProfiles'
import {createProfileQuery} from '../src/profileQuery'
import {compileAccessBundle} from '../src/accessExport'
import {nativeMapEquivalence,groupEquivalentPresets} from '../src/presetStrategies'
const setup=()=>{const s=structuredClone(snapshotFixture) as unknown as Snapshot;Object.assign(s.access!.inputSha256,approval.inputSha256);return s}
describe('hybrid NaN quality-first static composition',()=>{
 test('both harnesses preserve coordination and activity pipeline, but can delegate explicit closed workers',()=>{
  const s=setup()
  for(const h of ['gentle-shell','omp']){
    const id=h+'--pro100-go-nan-research-balanced'
    const p=deriveNanHybridPreset(s,id,'mixed',true,'bounded',false,'hybrid-worker')
    const helpers=p.nanStaticPlan!.composition!.helperOffloads
    expect(helpers.length).toBeGreaterThan(0)
    expect(p.portfolio).toBe('pro100-go-nan')
    expect(p.routes[h==='gentle-shell'?'orchestrator':'default'].modelKey).toBe('oa_sol61')
    expect(p.runtime).toEqual(s.runtimePolicies[p.sourceProfile])
    expect(p.nanStaticPlan!.qualityGuard.trialFractionOfExpectedNaN).toBeLessThanOrEqual(p.nanStaticPlan!.qualityGuard.trialShareCap+1e-12)
  }
 })
 test('quality gating rejects high impact, open worker and excluded domains',()=>{
  const s=setup(),id='omp--pro100-go-nan-research-balanced'
  expect(()=>deriveNanHybridPreset(s,id,'mixed',false,'standard',false,'hybrid-worker')).toThrow('acotada')
  expect(()=>deriveNanHybridPreset(s,id,'mixed',false,'bounded',true,'hybrid-worker')).toThrow()
  expect(()=>deriveNanHybridPreset(s,'omp--pro100-go-nan-agent-use-balanced','mixed',false,'bounded',false,'hybrid-worker')).toThrow()
 })
 test('no false duplication when the composition does not modify any eligible native role',()=>{
  const s=setup()
  expect(()=>deriveNanHybridPreset(s,'gentle-shell--pro100-go-nan-research-balanced','mixed',false,'standard',false,'hybrid-assist')).toThrow('No hay cambios efectivos')
 })
 test('matching exact full inventory is preferred over NaN-only subset when hybrid exists',()=>{
  const s=setup()
  const filters:ProfileFilters={...DEFAULT_FILTERS,domain:'research',objective:'balanced',strategy:'nan-static',
    subscriptions:{openai:'pro100',claude:'none',gateway:'go',nan:true},
    nanScenario:'mixed',nanTrials:true,nanComposition:'all',complexity:'bounded'}
  const q=createProfileQuery(s)
  const list=q(filters,false).items
  expect(list.length).toBeGreaterThan(0)
  expect(list[0].kind).toBe('nan-hybrid')
  expect(list[0].portfolio).toBe('pro100-go-nan')
  expect(q({...filters,nanComposition:'nan-only'},false).items.every(p=>p.kind==='nan-static')).toBe(true)
 })
 test('the experimental budget is objective-aware, not an invented quality score',()=>{
  const s=setup()
  for(const [obj,cap] of [['balanced',.3]] as const){
    const p=deriveNanHybridPreset(s,'omp--pro100-go-nan-research-'+obj,'mixed',true,'bounded',false,'hybrid-worker')
    expect(p.nanStaticPlan!.qualityGuard.trialShareCap).toBe(cap)
    expect(p.nanStaticPlan!.qualityGuard.trialFractionOfExpectedNaN).toBeLessThanOrEqual(cap+1e-12)
  }
  expect(nanCompositionPolicy.trialShareCapByObjective.best).toBe(.15)
  expect(nanCompositionPolicy.trialShareCapByObjective.economy).toBe(.35)
 })
 test('native selector equivalence is informative and does not merge differing origins or scope contracts',()=>{
  const s=setup(),p=deriveNanHybridPreset(s,'omp--pro100-go-nan-research-balanced','mixed',false,'bounded',false,'hybrid-worker')
  const twin=structuredClone(p);twin.id=p.id+'-variant';twin.routes.smol.condition+=' Contrato adicional.'
  const grouped=groupEquivalentPresets(s,[p,twin]);expect(grouped).toHaveLength(2)
  const matches=nativeMapEquivalence(s,[p,twin])
  expect(matches.get(p.id)).toEqual([p.id,twin.id])
  const altered=structuredClone(twin);altered.routes.smol.effort=p.routes.smol.effort==='high'?'medium':'high'
  const different=nativeMapEquivalence(s,[p,altered])
  expect(different.get(p.id)).toHaveLength(1)
 })
 test('native export and hash include activity and exact static composition',async()=>{
  const s=setup(),p=deriveNanHybridPreset(s,'gentle-shell--pro100-go-nan-research-balanced','mixed',true,'bounded',false,'hybrid-worker')
  const b=await compileAccessBundle(s,p,{mode:'preserve'})
  expect(b.manifest.selectionPolicy).toBe('nan-hybrid')
  expect(b.manifest.activityPlan).not.toBeNull()
  expect(b.manifest.nanStaticPlan?.composition?.helperOffloads.length).toBeGreaterThan(0)
  expect(b.manifest.nativeArtifact.sha256).toBe(new Bun.CryptoHasher('sha256').update(b.native.content).digest('hex'))
  expect(b.manifest.validation.inferencesSent).toBe(0)
 })
})
