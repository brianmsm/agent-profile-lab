import {describe,test,expect} from 'bun:test'
import fixtureData from './fixtures/activity-fixture.json'
import approval from '../../policies/selection-approval.json'
import type {Snapshot,ProfileFilters} from '../src/data'
import {DEFAULT_FILTERS} from '../src/data'
import {deriveReviewedCandidate,collectReviewedCandidates,selectionPolicy,selectionEvidence} from '../src/selectionCandidates'
import {createProfileQuery} from '../src/profileQuery'
import {compileAccessBundle} from '../src/accessExport'
import {resolveOrigin} from '../src/accessRouting'
const G='gentle-shell--pro100-claude-go-nan-research-balanced'
function fixture(){
  // Unit fixture adopts explicit current review hashes; full corpus verification
  // is exercised independently by Python and the exhaustive export audit.
  const s=structuredClone(fixtureData) as unknown as Snapshot
  Object.assign(s.access!.inputSha256,approval.inputSha256,{'policies/selection-candidates.json':approval.policySha256,'policies/selection-evidence.json':approval.evidenceSha256})
  return s
}
const settings={complexity:'standard',highImpact:false} as const
const filters:ProfileFilters={...DEFAULT_FILTERS,domain:'research',objective:'balanced',strategy:'reviewed-candidate',subscriptions:{openai:'pro100',claude:'pro',gateway:'go',nan:true}}
describe('explicit evidence-reviewed alternatives',()=>{
  test('Haiku worker is generated for Gentle and OMP and never takes coordination',()=>{
    const s=fixture()
    for(const h of ['gentle-shell','omp']){
      const id=h+'--pro100-claude-go-nan-research-balanced',p=deriveReviewedCandidate(s,id,'haiku-worker','cl_haiku',settings)
      expect(p.routes[h==='omp'?'task':'gentle-ai-worker'].modelKey).toBe('cl_haiku')
      expect(p.routes[h==='omp'?'default':'orchestrator']).toEqual(s.routeDetails[id][h==='omp'?'default':'orchestrator'])
      expect(p.runtime).toEqual(s.runtimePolicies[id])
    }
  })
  test('a single Claude subscription is sufficient; API availability is not entitlement',()=>{
    const s=fixture();expect(deriveReviewedCandidate(s,'gentle-shell--claude-pro-research-balanced','haiku-worker','cl_haiku',settings).selectionReview?.changes.length).toBeGreaterThan(0)
    const rows=collectReviewedCandidates(s,{...filters,subscriptions:{openai:'pro100',claude:'none',gateway:'go',nan:true,anthropicApi:true}},settings).presets
    expect(rows.some(p=>p.selectionReview?.offeringKey==='cl_haiku')).toBe(false)
  })
  test('reviewed alternatives are opt-in and scope limited, not new baseline statistics',()=>{
    const s=fixture(),query=createProfileQuery(s)
    expect(query({...filters,strategy:''},false).items.some(p=>p.selectionReview)).toBe(false)
    expect(query(filters,false).items.every(p=>p.selectionReview)).toBe(true)
    expect(query({...filters,domain:''},false).items).toHaveLength(0)
    expect(query(filters,false)).toBe(query(filters,false))
  })
  test('impact and undecomposed complex work block worker proposals',()=>{
    const s=fixture();expect(collectReviewedCandidates(s,filters,{...settings,highImpact:true}).presets).toHaveLength(0)
    expect(()=>deriveReviewedCandidate(s,G,'haiku-worker','cl_haiku',{complexity:'complex',highImpact:false})).toThrow('no admitida')
    expect(deriveReviewedCandidate(s,G,'haiku-small','cl_haiku',{complexity:'complex',highImpact:false}).selectionReview?.changes.every(c=>c.functionId!=='bounded-implementation')).toBe(true)
  })
  test('correct model alias or price does not license the wrong recipe',()=>{
    const s=fixture();expect(()=>deriveReviewedCandidate(s,G,'mimo-nan-worker','nan_qwen',settings)).toThrow('Pareja')
    expect(()=>deriveReviewedCandidate(s,G,'haiku-worker','cl_haiku',{...settings,force:true} as typeof settings)).toThrow('Complejidad')
  })
  test('old review metadata cannot enable new recipes',()=>{
    const s=fixture();s.access!.inputSha256['policies/selection-evidence.json']='0'.repeat(64)
    expect(collectReviewedCandidates(s,filters,settings).issues).toHaveLength(1)
    expect(()=>deriveReviewedCandidate(s,G,'haiku-worker','cl_haiku',settings)).toThrow('revisión')
  })
  test('input and fallbacks are preserved and price tier is explicit',()=>{
    const s=fixture(),before=JSON.stringify(s),p=deriveReviewedCandidate(s,G,'haiku-worker','cl_haiku',settings)
    expect(JSON.stringify(s)).toBe(before)
    for(const c of p.selectionReview!.changes){const old=s.routeDetails[G][c.role];expect(p.routes[c.role].fallback).toEqual({modelKey:old.modelKey,effort:old.effort,origin:old.origin});expect(p.routes[c.role].condition).toContain('100000')}
  })
  test('changing JSON origin property order does not invent a distinct configuration',()=>{
    const s=fixture(),p=deriveReviewedCandidate(s,G,'haiku-worker','cl_haiku',settings)
    s.routeDetails[G]=p.routes
    for(const c of p.selectionReview!.changes){const r=s.routeDetails[G][c.role];r.origin=Object.fromEntries(Object.entries(r.origin!).reverse()) as typeof r.origin}
    expect(()=>deriveReviewedCandidate(s,G,'haiku-worker','cl_haiku',settings)).toThrow('Sin cambios efectivos')
  })
  test('ungraded NaN effort remains empty and full GLM and Flash are different offers',()=>{
    const s=fixture(),p=deriveReviewedCandidate(s,G,'mimo-nan-worker','nan_mf',settings)
    expect(p.selectionReview?.changes.every(c=>c.toEffort==='')).toBe(true)
    expect(selectionPolicy.recipes.find(r=>r.id==='glm-full-worker')?.offeringKeys).toContain('go_glmf')
    expect(selectionPolicy.recipes.find(r=>r.id==='glm-flash-worker')?.offeringKeys).toContain('go_glm')
  })
  test('manifest contains exact linked observations, no inferred source scores',async()=>{
    const s=fixture(),p=deriveReviewedCandidate(s,G,'haiku-worker','cl_haiku',settings),bundle=await compileAccessBundle(s,p,{mode:'preserve'})
    expect(bundle.manifest.selectionReview?.evidence).toHaveLength(7)
    expect(bundle.manifest.selectionReview?.evidence).toEqual(p.selectionReview!.evidenceRefs.map(id=>selectionEvidence[id]))
    expect(bundle.manifest.nativeArtifact.sha256).toBe(new Bun.CryptoHasher('sha256').update(bundle.native.content).digest('hex'))
    expect(resolveOrigin(p.routes['gentle-ai-worker'],p.meta.targetId!).effort).toBe('medium')
  })
})
