import {describe,expect,test} from 'bun:test'
import fixtureData from './fixtures/activity-fixture.json'
import expectedData from './fixtures/activity-parity.json'
import type {Snapshot,ProfileFilters} from '../src/data'
import {DEFAULT_FILTERS} from '../src/data'
import {deriveActivityPreset,activityPresets,collectActivityPresets,activityLevels} from '../src/activityProfiles'
import type {ActivitySettings} from '../src/activityProfiles'
import {presets,getPreset,providerParticipation,presetAnalysis,presetRolesCsv} from '../src/presetStrategies'
import {strategyAvailable,normalizeProfileFilters,filteredPresets,resolveSelection,configuredShares} from '../src/profileBrowser'
import {compileAccessBundle} from '../src/accessExport'
import {poolLabel,portfolioLabel,STRATEGIES} from '../src/presentation'
const fixture=()=>structuredClone(fixtureData) as unknown as Snapshot
const selection={openai:'pro100',claude:'none',gateway:'go',nan:true} as const
const inventory='gentle-shell--pro100-go-nan-research-balanced'
const filters:ProfileFilters={...DEFAULT_FILTERS,domain:'research',subscriptions:selection}

describe('activity allocation across Python and dashboard',()=>{
  test('48 harness / complexity / risk / resource cases match Python routes and decision provenance',()=>{
    const s=fixture()
    for(const c of expectedData){
      const p=deriveActivityPreset(s,c.profileId,c.settings as ActivitySettings)
      for(const key of ['sourceProfile','portfolio','routes','runtime','coordinatorPool','offloadPool','limitations','activityPlan'] as const)expect(p[key]).toEqual(c.result[key])
    }
  })
  test('both harnesses meaningfully assign OpenCode Go and NaN without moving coordination or reviewers',()=>{
    const s=fixture()
    for(const h of ['gentle-shell','omp']){
      const p=deriveActivityPreset(s,`${h}--pro100-go-nan-research-balanced`,{complexity:'standard',highImpact:false})
      const shares=configuredShares(s,p)
      expect(shares.entries.map(e=>e.pool).sort()).toEqual(['GO','NAN','OAI'])
      expect(shares.entries.reduce((sum,e)=>sum+e.share,0)).toBeCloseTo(1)
      expect(p.routes[h==='omp'?'default':'orchestrator']).toEqual(s.routeDetails[p.sourceProfile][h==='omp'?'default':'orchestrator'])
      expect(p.routes[h==='omp'?'judge':'review-risk']).toEqual(s.routeDetails[p.sourceProfile][h==='omp'?'judge':'review-risk'])
    }
  })
  test('sources and benchmarks are not mutated or reclassified as calibrated',()=>{
    const s=fixture(),before=JSON.stringify(s)
    const p=deriveActivityPreset(s,inventory,{complexity:'bounded',highImpact:false})
    expect(JSON.stringify(s)).toBe(before)
    expect(p.activityPlan?.state).toBe('candidate-not-calibrated')
    expect(p.kind).toBe('activity-distributed')
  })
  test('high impact preserves the coordinator reference even for a simple activity',()=>{
    const s=fixture();const p=deriveActivityPreset(s,inventory,{complexity:'bounded',highImpact:true})
    expect(p.routes).toEqual(s.routeDetails[p.sourceProfile]);expect(p.activityPlan?.changes).toHaveLength(0)
  })
  test('same resources, distinct complexity and impact are distinct native manifests',async()=>{
    const s=fixture(),hashes=[]
    for(const complexity of ['bounded','standard','complex'] as const){
      const p=deriveActivityPreset(s,inventory,{complexity,highImpact:false})
      const bundle=await compileAccessBundle(s,p,{mode:'preserve'})
      hashes.push(bundle.manifest.nativeArtifact.sha256)
      expect(bundle.manifest.activityPlan?.complexity).toBe(complexity)
      expect(bundle.manifest.resources.map(r=>r.accessRouteId).sort()).toEqual(['chatgpt-legacy','nan','opencode-go'])
      expect(bundle.manifest.status).toBe('candidate')
      expect(bundle.manifest.validation.performance).toBe('not-calibrated')
    }
    expect(new Set(hashes).size).toBe(3)
  })
  test('activity follows analysis and CSV through native exports',()=>{
    const s=fixture(),p=deriveActivityPreset(s,inventory,{complexity:'standard',highImpact:false})
    expect(presetAnalysis(s,p,selection).profile.activityPlan).toEqual(p.activityPlan)
    const csv=presetRolesCsv(s,p)
    expect(csv).toContain('opencode-go/');expect(csv).toContain('nan/');expect(csv).toContain('openai-codex/')
  })
  test('new activities require explicit subscriptions, not a paid API checkbox',()=>{
    const s=fixture();expect(activityPresets(s,null,{complexity:'bounded',highImpact:false})).toEqual([])
    expect(activityPresets(s,{openai:'pro100',claude:'none',gateway:'none',nan:false,api:true},{complexity:'standard',highImpact:false})).toEqual([])
  })
  test('unknown complexity, unavailable inventory and retired roles are not manufactured',()=>{
    const s=fixture()
    expect(()=>deriveActivityPreset(s,inventory,{complexity:'invented' as keyof typeof activityLevels,highImpact:false})).toThrow()
    expect(()=>deriveActivityPreset(s,'missing',{complexity:'standard',highImpact:false})).toThrow()
    const p=deriveActivityPreset(s,inventory,{complexity:'bounded',highImpact:false})
    expect(Object.keys(p.routes).some(role=>role.startsWith('sdd-'))).toBe(false)
    expect(Object.values(p.routes).some(r=>r.origin?.accessRouteId.includes('api'))).toBe(false)
  })
})

describe('strategy availability and selected-card consistency',()=>{
  test('NaN option is hidden and stale filter resets when NaN is unchecked',()=>{
    const f={...filters,strategy:'nan-volume' as const,subscriptions:{...selection,nan:false}}
    expect(strategyAvailable('nan-volume',f)).toBe(false);expect(normalizeProfileFilters(f).strategy).toBe('')
    expect(strategyAvailable('nan-volume',filters)).toBe(true)
    expect(strategyAvailable('nan-volume',{...filters,domain:'agent-use'})).toBe(false)
    expect(strategyAvailable('nan-volume',{...filters,highImpact:true})).toBe(false)
    expect(strategyAvailable('nan-volume',{...filters,subscriptions:null})).toBe(false)
  })
  test('full selected inventory is presented before cheaper subsets',()=>{
    const s=fixture(),f={...filters,strategy:'matrix' as const}
    const items=filteredPresets(s,f,false,presets(s))
    expect(items.length).toBeGreaterThan(2)
    expect(items[0].portfolio).toBe('pro100-go-nan')
    const state=resolveSelection(items,0,'missing',8)
    expect(state.selected).toBe(state.visible[0])
  })
  test('all alternatives offer the new distribution without falsely relabeling OpenAI-only',()=>{
    const s=fixture(),activities=activityPresets(s,selection,{complexity:'standard',highImpact:false})
    const items=filteredPresets(s,filters,false,[...presets(s),...activities])
    expect(items[0].kind).toBe('activity-distributed')
    expect(STRATEGIES['openai-led']).toBe('Solo OpenAI')
    for(const p of items.filter(p=>p.kind==='openai-led'))expect(providerParticipation(s,p).filter(p=>p.roles.length).map(p=>p.pool)).toEqual(['OAI'])
  })
  test('equivalence grouping preserves full-inventory representative against an OpenAI-only alias',()=>{
    const s=fixture(),owner=getPreset(s,'gentle-shell--pro100-research-balanced')
    const full={...getPreset(s,inventory),routes:structuredClone(owner.routes),runtime:owner.runtime}
    const solo={...owner,kind:'openai-led' as const,id:owner.id+'::openai-led',aliases:[owner.id+'::openai-led']}
    const items=filteredPresets(s,{...filters,harness:'gentle-shell',strategy:''},false,[solo,full])
    expect(items).toHaveLength(1)
    expect(items[0].id).toBe(inventory)
    expect(items[0].portfolio).toBe('pro100-go-nan')
    expect(items[0].aliases).toContain(solo.id)
    const narrowed=filteredPresets(s,{...filters,harness:'gentle-shell',strategy:'openai-led'},false,[solo,full])
    expect(narrowed[0].kind).toBe('openai-led')
  })
  test('incomplete imported donor coverage yields explicit issues instead of crashing the browser',()=>{
    const s=fixture()
    // A partial import can legitimately retain an inventory reference but no single-pool donors.
    s.meta=Object.fromEntries(Object.entries(s.meta).filter(([id])=>id===inventory))
    const c=collectActivityPresets(s,selection,{complexity:'standard',highImpact:false})
    expect(c.presets).toEqual([])
    expect(c.issues).toHaveLength(1)
    expect(c.issues[0].profileId).toBe(inventory)
    expect(c.issues[0].message).toContain('coordinación')
    expect(activityPresets(s,selection,{complexity:'standard',highImpact:false})).toEqual([])
  })
  test('a malformed donor cannot discard otherwise valid harness candidates',()=>{
    const s=fixture()
    s.routeDetails['gentle-shell--go-research-balanced']['gentle-ai-worker'].origin!.credentialRef='a-different-account'
    const c=collectActivityPresets(s,selection,{complexity:'standard',highImpact:false})
    expect(c.issues.some(i=>i.profileId===inventory)).toBe(true)
    expect(c.presets.some(p=>p.meta.harness==='omp')).toBe(true)
    expect(c.presets.some(p=>p.id.startsWith(inventory+'::'))).toBe(false)
  })
  test('selected item must be on the displayed page, not an unrelated stale detail',()=>{
    const s=fixture(),items=filteredPresets(s,{...filters,domain:'',objective:''},false,presets(s))
    const first=resolveSelection(items,0,items[0].id,2),next=resolveSelection(items,1,items[0].id,2)
    expect(first.selected?.id).toBe(items[0].id)
    expect(next.selected?.id).toBe(items[2].id)
    expect(next.visible.some(p=>p.id===next.selected?.id)).toBe(true)
    expect(resolveSelection([],99,'old',8).selected).toBeUndefined()
    const alias={...items[0],aliases:[...items[0].aliases,'known-alias']}
    expect(resolveSelection([alias],0,'known-alias',8).selected).toBe(alias)
  })
  test('exact profile navigation for top participation does not silently change the profile',()=>{
    const s=fixture(),id='omp--pro100-go-nan-research-balanced'
    const items=filteredPresets(s,{...filters,harness:'omp',portfolio:'pro100-go-nan',strategy:'matrix',profileId:id},true,presets(s))
    expect(resolveSelection(items,0,id,8).selected?.id).toBe(id)
  })
  test('visible names spell out OpenCode Go without altering source identifiers',()=>{
    const s=fixture();expect(poolLabel('GO')).toBe('OpenCode Go');expect(portfolioLabel(s.portfolios['pro100-go'])).toContain('OpenCode Go')
    expect(getPreset(s,inventory).portfolio).toBe('pro100-go-nan')
    expect(portfolioLabel({...s.portfolios['pro100-go'],label:'OpenCode Go $10 + Command Code $10'})).toBe('OpenCode Go $10 + Command Code $10')
  })
})

describe('actual CLI versus browser compilation',()=>{
  for(const [harness,complexity,targetId] of [['gentle-shell','bounded','gentle-shell@4.0.0+pi@1.1.0'],['omp','complex','omp@18.8.7']] as const){
    test(`${harness}: primary/reserve credentials, efforts and policy agree across compilers`,async()=>{
      const s=fixture(),profileId=`${harness}--pro100-go-nan-research-balanced`,settings={complexity,highImpact:false}
      const ui=await compileAccessBundle(s,deriveActivityPreset(s,profileId,settings),{mode:'preserve'})
      const root=new URL('../..',import.meta.url).pathname
      const request={schemaVersion:1,baseProfile:profileId,targetId,selectionPolicy:'activity-distributed',activity:settings}
      const run=Bun.spawnSync(['python3','-B','-c',"import sys,json;sys.path.insert(0,'scripts');from profile_compiler import compile_request;print(json.dumps(compile_request(json.loads(sys.argv[1]))['manifest']))",JSON.stringify(request)],{cwd:root})
      expect(run.exitCode).toBe(0)
      const cli=JSON.parse(run.stdout.toString())
      expect(ui.manifest.activityPlan).toEqual(cli.activityPlan)
      expect(Object.keys(ui.manifest.roles).sort()).toEqual(Object.keys(cli.roles).sort())
      for(const [role,selected] of Object.entries(ui.manifest.roles)){
        for(const field of ['modelId','selector','effort','accessRouteId','resourceId','credentialRef','plan','enabled'] as const)expect(selected[field]).toEqual(cli.roles[role][field])
        for(const reservation of ['fallback','accelerator'] as const){
          const a=selected[reservation],b=cli.roles[role][reservation]
          if(!a){expect(b).toBeNull();continue}
          for(const field of ['modelId','selector','effort','accessRouteId','resourceId','credentialRef','plan'] as const)expect(a[field]).toEqual(b[field])
        }
      }
    })
  }
})
