import {describe,test,expect} from 'bun:test'
import fixture from './fixtures/activity-fixture.json'
import type {Snapshot} from '../src/data'
import {validateProfileOrigins} from '../src/accessRouting'
import {prepareAccessPreset} from '../src/accessExport'
import {getPreset} from '../src/presetStrategies'
import {deriveActivityPreset} from '../src/activityProfiles'
const snapshot=()=>structuredClone(fixture) as unknown as Snapshot
const G='gentle-shell--pro100-research-balanced',O='omp--pro100-research-balanced'
const validate=(s:Snapshot,id:string)=>validateProfileOrigins(s,s.meta[id],s.routeDetails[id],s.access!.resourcesByPortfolio[s.meta[id].portfolio])
describe('profile semantic cross-contract regressions',()=>{
  test('research routes cannot carry a software-only quality gate',()=>{
    const s=snapshot();s.routeDetails[G].orchestrator.condition=s.domainContracts.apps.gate
    expect(()=>validate(s,G)).toThrow('dominio')
  })
  test('text-only vision primary is rejected by offering capability, not a name regex',()=>{
    const s=snapshot(),ref=s.routeDetails['omp--cc-research-balanced'].task
    s.routeDetails[O].vision={...s.routeDetails[O].vision,modelKey:ref.modelKey,effort:ref.effort,origin:ref.origin}
    s.access!.resourcesByPortfolio.pro100.push(...s.access!.resourcesByPortfolio.cc)
    expect(()=>validate(s,O)).toThrow('imagen')
  })
  test('text-only visual fallback cannot borrow the primary image capability',()=>{
    const s=snapshot(),ref=s.routeDetails['omp--cc-research-balanced'].task
    s.routeDetails[O].vision.fallback={modelKey:ref.modelKey,effort:ref.effort,origin:ref.origin}
    s.access!.resourcesByPortfolio.pro100.push(...s.access!.resourcesByPortfolio.cc)
    expect(()=>validate(s,O)).toThrow('imagen')
  })
  test('exact-origin no-op reserve is not an alternative, but a higher effort remains distinct',()=>{
    const s=snapshot(),r=s.routeDetails[G].orchestrator
    r.fallback={modelKey:r.modelKey,effort:r.effort,origin:structuredClone(r.origin)}
    expect(()=>validate(s,G)).toThrow('idéntica')
    r.fallback.effort=r.effort==='max'?'high':'max'
    expect(()=>validate(s,G)).not.toThrow()
  })
  test('an API reserve cannot share a SIWC provider namespace with another auth resource',()=>{
    const s=snapshot(),prepared=prepareAccessPreset(s,getPreset(s,G),{mode:'siwc'}),p=prepared.preset
    prepared.resources.push({id:'api-test',accessRouteId:'openai-api',credentialRef:'api-test',plan:'metered'})
    const r=p.routes.orchestrator;r.fallback={modelKey:r.modelKey,effort:'max',origin:{...r.origin!,accessRouteId:'openai-api',resourceId:'api-test',credentialRef:'api-test',plan:'metered'}}
    expect(()=>validateProfileOrigins(s,p.meta,p.routes,prepared.resources)).toThrow('ambiguo')
  })
  test('activity preserves constraints of the donor as well as of the coordinator',()=>{
    const s=snapshot();s.routeDetails['gentle-shell--go-research-balanced']['gentle-ai-worker'].condition+=' Additional donor bound: inspect only the approved files.'
    const p=deriveActivityPreset(s,'gentle-shell--pro100-go-nan-research-balanced',{complexity:'standard',highImpact:false})
    expect(p.routes['gentle-ai-worker'].condition).toContain('Additional donor bound: inspect only the approved files.')
    expect(p.routes['gentle-ai-worker'].condition).toContain(s.domainContracts.research.gate)
  })
})
