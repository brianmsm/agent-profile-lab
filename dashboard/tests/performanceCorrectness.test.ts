import {describe,expect,test} from 'bun:test'
import fixture from './fixtures/activity-fixture.json'
import {createProfileQuery} from '../src/profileQuery'
import {presets,presetRolesCsv,presetNativeExport} from '../src/presetStrategies'
import {collectActivityPresets} from '../src/activityProfiles'
import {filteredPresets} from '../src/profileBrowser'
import {DEFAULT_FILTERS} from '../src/data'
import type {Snapshot,ProfileFilters,Benchmark} from '../src/data'
import {createBenchmarkQuery} from '../src/benchmarkQuery'
import {explorerGroups,rowMatchesModel} from '../src/modelInsightsData'
import {extent,ticks,position,axisNumber} from '../src/chartMath'
import {createEvidenceSearch} from '../src/evidenceQuery'
import {validateDeliveryManifest,unpackCore,mergeEvidence,decodeDeliveryPart} from '../src/deliveryCodec'
import {createSnapshotSession} from '../src/snapshotClient'

// Preserve the same binary64 value that the original JSON parser produces.
const precise=JSON.parse('0.12345678901234567') as number
const s=()=>structuredClone(fixture) as unknown as Snapshot
const selection={openai:'pro100',claude:'none',gateway:'go',nan:true} as const

describe('indexed queries retain exact decision and export semantics',()=>{
  test('scoped and cached profiles equal exhaustive derivation across both harnesses and activity levels',()=>{
    const snap=s(),query=createProfileQuery(snap),references=presets(snap)
    for(const complexity of ['bounded','standard','complex'] as const)for(const highImpact of [false,true]){
      const settings={complexity,highImpact},all=[...references,...collectActivityPresets(snap,selection,settings).presets]
      for(const domain of ['research','agent-use'])for(const strategy of ['', 'matrix','activity-distributed'] as const){
        const filters:ProfileFilters={...DEFAULT_FILTERS,domain,strategy,subscriptions:selection,...settings}
        const actual=query(filters,false),expected=filteredPresets(snap,filters,false,all)
        expect(actual.items).toEqual(expected)
        expect(query(filters,false)).toBe(actual)
        for(let i=0;i<Math.min(2,actual.items.length);i++){
          expect(presetRolesCsv(snap,actual.items[i])).toBe(presetRolesCsv(snap,expected[i]))
          expect(presetNativeExport(snap,actual.items[i])).toEqual(presetNativeExport(snap,expected[i]))
        }
      }
    }
  })
  test('new revisions never inherit cached routes or references',()=>{
    const a=s(),b=s(),f:ProfileFilters={...DEFAULT_FILTERS,domain:'research',strategy:'matrix',subscriptions:selection}
    b.routeDetails['gentle-shell--pro100-go-nan-research-balanced'].orchestrator.rationale='Changed source'
    const first=createProfileQuery(a)(f,false),second=createProfileQuery(b)(f,false)
    expect(second).not.toBe(first)
    expect(second.items.find(p=>p.id==='gentle-shell--pro100-go-nan-research-balanced')?.routes.orchestrator.rationale).toBe('Changed source')
  })
  test('evidence search matches original exact normalized fields; never infers matches by name alone',()=>{
    const rows=[{model:'á model',benchmark:'test',source:'https://example.org',effort:'high',note:'  Notes',provenance:'L2'}] as Benchmark[]
    const search=createEvidenceSearch(rows)
    for(const needle of ['', 'á model','high','l2','not a match']){
      expect(rows.filter(r=>search(r,needle))).toEqual(rows.filter(r=>[r.model,r.benchmark,r.source,r.sourceId,r.effort,r.provenance,r.methodology,r.note].join(' ').toLocaleLowerCase('es').includes(needle)))
    }
    expect(()=>search({...rows[0]},'high')).toThrow('otra revisión')
  })
  test('index preserves global row indices, unlinked costs and missing values',()=>{
    const base={model:'Exact',family:'x',benchmark:'task',value:precise,unit:'%',effort:'high',source:'https://example.org',date:'2026-01-01',methodology:'method',provenance:'L1',note:''}
    const rows=[{...base,model:'Unrelated'},base,{...base,value:null},{...base,benchmark:'cost',unit:'USD/task',value:.1234}]
    const models=[{model:'Exact',efforts:['high'],roles:['task']}],index=createBenchmarkQuery(rows)
    expect(index.groups(models,true)).toEqual(explorerGroups(rows,models,true))
    expect(index.matching(models[0])).toEqual(rows.filter(r=>rowMatchesModel(r,models[0])))
    expect(index.groups(models,true)).toBe(index.groups(models,true))
  })
})

describe('chart coordinates and source precision',()=>{
  test('axis abbreviation never modifies source values or extents',()=>{
    const values=[precise,51.832917831]
    const before=[...values],domain=extent(values)
    expect(axisNumber(values[0]).length).toBeLessThan(String(values[0]).length)
    expect(values).toEqual(before);expect(domain.max).toBe(values[1]);expect(domain.min).toBe(0)
    expect(ticks(domain)).toHaveLength(5);expect(position(domain.max,domain)).toBe(96)
  })
  test('negative, empty, null, single-point and extreme finite ranges stay finite',()=>{
    for(const values of [[],[null],[0],[20,20],[-5,-2],[-Number.MAX_VALUE,Number.MAX_VALUE]]){
      for(const zero of [true,false]){const d=extent(values,zero);expect(ticks(d).every(Number.isFinite)).toBe(true);expect(Number.isFinite(position(d.min,d))).toBe(true)}
    }
    expect(extent([20,30],false)).toEqual({min:20,max:30})
  })
})

describe('lossless delivery and integrity',()=>{
  const sha='a'.repeat(64),manifest=()=>({format:'apl.delivery',version:1,sourceSha256:sha,evidenceFields:['benchmarks'],parts:Object.fromEntries(['core','evidence'].map(k=>[k,{path:`chunks/${k}-${sha}.json.gz`,sha256:sha,bytes:123,decodedBytes:456}]))})
  test('foreign paths, missing fragments, duplicated fields and versions fail closed',()=>{
    expect(validateDeliveryManifest(manifest()).version).toBe(1)
    for(const mutate of [(v:any)=>{v.parts.core.path='https://evil.invalid/data'},(v:any)=>{delete v.parts.evidence},(v:any)=>{v.version=2},(v:any)=>{v.evidenceFields.push('benchmarks')},(v:any)=>{v.evidenceFields.push('routeDetails')}]){
      const v=manifest();mutate(v);expect(()=>validateDeliveryManifest(v)).toThrow()
    }
  })
  test('compressed bytes and decoded length are authenticated before parsing',async()=>{
    const raw=JSON.stringify({value:precise,text:'á\nΩ',missing:null})
    const bytes=Bun.gzipSync(new TextEncoder().encode(raw)),buffer=Uint8Array.from(bytes).buffer
    const sha256=new Bun.CryptoHasher('sha256').update(bytes).digest('hex')
    const part={path:'unused',sha256,bytes:bytes.length,decodedBytes:new TextEncoder().encode(raw).length}
    expect(await decodeDeliveryPart(buffer,part)).toEqual(JSON.parse(raw))
    await expect(decodeDeliveryPart(buffer,{...part,sha256:'0'.repeat(64)})).rejects.toThrow('Integridad')
    await expect(decodeDeliveryPart(buffer,{...part,decodedBytes:1})).rejects.toThrow('Longitud')
  })
  test('dictionary indices and evidence fields cannot silently remove data',()=>{
    const packed={format:'apl.core-transport',version:1,texts:['condition','rationale'],routes:[{modelKey:'x',condition:0,rationale:1}],snapshot:{routeDetails:{p:{role:0}},strategies:{}}}
    expect(unpackCore(packed).routeDetails.p.role.rationale).toBe('rationale')
    for(const n of [-1,.5,5]){const bad=structuredClone(packed);bad.snapshot.routeDetails.p.role=n;expect(()=>unpackCore(bad)).toThrow()}
    expect(()=>mergeEvidence(s(),{},['benchmarks'])).toThrow('incompleta')
    expect(()=>mergeEvidence(s(),{routeDetails:{}},['routeDetails'])).toThrow()
  })
})

class FakeWorker {
  onmessage:((e:{data:unknown})=>void)|null=null;onerror:((e:{message:string})=>void)|null=null;onmessageerror:(()=>void)|null=null
  sent:any[]=[];terminated=false
  postMessage(m:unknown){this.sent.push(m)} terminate(){this.terminated=true}
  emit(data:unknown){this.onmessage?.({data})}
}
const flush=()=>new Promise(r=>setTimeout(r,0))
describe('worker single-flight, atomic visibility, retry and disposal',()=>{
  test('no evidence request at startup; concurrent readers share one complete request',async()=>{
    const w=new FakeWorker(),session=createSnapshotSession(w as unknown as Worker,'http://localhost/data/delivery.json')
    expect(w.sent.map(m=>m.type)).toEqual(['init']);w.emit({id:1,ok:true,value:s()});await session.core
    const first=session.complete(),second=session.complete();expect(first).toBe(second);await flush()
    expect(w.sent.map(m=>m.type)).toEqual(['init','complete'])
    let resolved=false;first.then(()=>{resolved=true})
    w.emit({id:2,chunk:true,field:'benchmarks',offset:0,value:[{id:'exact'}]});await flush();expect(resolved).toBe(false)
    w.emit({id:2,ok:true,complete:true,fields:['benchmarks']});expect((await first).benchmarks).toEqual([{id:'exact'}] as any)
    expect(session.complete()).toBe(first);session.dispose();expect(w.terminated).toBe(true)
  })
  test('failed evidence can be retried without contaminating the core or new chunks',async()=>{
    const w=new FakeWorker(),session=createSnapshotSession(w as unknown as Worker,'http://localhost/data/delivery.json')
    w.emit({id:1,ok:true,value:s()});await session.core
    const failed=session.complete();await flush();w.emit({id:2,ok:false,error:'integrity failure'});await expect(failed).rejects.toThrow('integrity')
    const next=session.complete();await flush();w.emit({id:3,ok:true,complete:true,fields:[]});expect(await next).toEqual(await session.core)
    session.dispose()
  })
  test('out-of-order fragments reject the request instead of exposing partial results',async()=>{
    const w=new FakeWorker(),session=createSnapshotSession(w as unknown as Worker,'http://localhost/data/delivery.json')
    w.emit({id:1,ok:true,value:s()});await session.core
    const data=session.complete();await flush();w.emit({id:2,chunk:true,field:'benchmarks',offset:1500,value:[]});await expect(data).rejects.toThrow('orden')
    session.dispose()
  })
  test('dataset disposal rejects pending work and ignores late messages',async()=>{
    const w=new FakeWorker(),session=createSnapshotSession(w as unknown as Worker,'http://localhost/data/delivery.json')
    w.emit({id:1,ok:true,value:s()});await session.core
    const data=session.complete();await flush();session.dispose();await expect(data).rejects.toThrow('cancelada')
    w.emit({id:2,ok:true,complete:true,fields:[]});await expect(session.complete()).rejects.toThrow()
  })
})
