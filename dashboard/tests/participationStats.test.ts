import {describe,expect,test} from 'bun:test'
import type {Snapshot} from '../src/data'
import {DEFAULT_STAT_SCOPE,participationRows,scopedParticipation,groupParticipation,modelParticipationProfiles,statisticsCsv} from '../src/participationStats'
import fixtureData from './fixtures/activity-fixture.json'

const fixture=()=>structuredClone(fixtureData) as unknown as Snapshot

describe('complete participation statistics with explicit denominators',()=>{
  test('all primary slots partition into enabled plus disabled, without adding reserves',()=>{
    const s=fixture(),rows=participationRows(s)
    const enabled=scopedParticipation(rows,DEFAULT_STAT_SCOPE),disabled=scopedParticipation(rows,{...DEFAULT_STAT_SCOPE,state:'disabled'})
    expect(enabled.length+disabled.length).toBe(s.stats.rows)
    expect(disabled.length).toBeGreaterThan(0)
    expect(enabled.every(r=>r.enabled&&r.kind==='primary')).toBe(true)
  })
  test('every breakdown reconciles to the selected denominator',()=>{
    const rows=scopedParticipation(participationRows(fixture()),{...DEFAULT_STAT_SCOPE,domain:'research'})
    for(const dimension of ['model','pool','role','harness','domain','effort'] as const){
      const groups=groupParticipation(rows,dimension)
      expect(groups.reduce((sum,g)=>sum+g.count,0)).toBe(rows.length)
      expect(groups.reduce((sum,g)=>sum+g.share,0)).toBeCloseTo(1)
    }
  })
  test('filters are applied to both a model numerator and each profile denominator',()=>{
    const rows=scopedParticipation(participationRows(fixture()),{...DEFAULT_STAT_SCOPE,domain:'research',harness:'omp',pool:'GO'})
    expect(rows.every(r=>r.domain==='research'&&r.harness==='omp'&&r.pool==='GO')).toBe(true)
    const id=rows[0].modelId,rank=modelParticipationProfiles(rows,id)
    for(const p of rank){
      expect(p.total).toBe(rows.filter(r=>r.profileId===p.profileId).length)
      expect(p.count).toBe(rows.filter(r=>r.profileId===p.profileId&&r.modelId===id).length)
      expect(p.share).toBe(p.count/p.total)
    }
  })
  test('fallback and accelerator counts are not conflated with active primaries',()=>{
    const s=fixture(),all=participationRows(s)
    for(const kind of ['fallback','accelerator'] as const){
      const selected=scopedParticipation(all,{...DEFAULT_STAT_SCOPE,kind})
      const count=Object.values(s.routeDetails).flatMap(rs=>Object.values(rs)).filter(r=>r.enabled&&r[kind]).length
      expect(selected.length).toBe(count)
    }
  })
  test('top 10 expands to the entire ranked population, stable ties and no quality interpretation',()=>{
    const rows=scopedParticipation(participationRows(fixture()),DEFAULT_STAT_SCOPE),id='openai:gpt-6.1-sol'
    const ranked=modelParticipationProfiles(rows,id),reversed=modelParticipationProfiles([...rows].reverse(),id)
    expect(ranked.length).toBeGreaterThan(10);expect(ranked.slice(0,10)).toHaveLength(10)
    expect(reversed).toEqual(ranked)
    expect(ranked.every(r=>r.share<=1&&r.share>0)).toBe(true)
  })
  test('catalog models with zero participation stay zero, not an inferred failure',()=>{
    const s=fixture(),rows=scopedParticipation(participationRows(s),DEFAULT_STAT_SCOPE)
    const groups=groupParticipation(rows,'model',s,true),haiku=groups.find(g=>g.key==='anthropic:claude-haiku-5-5')!
    expect(haiku.count).toBe(0);expect(haiku.profiles).toBe(0);expect(modelParticipationProfiles(rows,haiku.key)).toEqual([])
  })
  test('same display name does not conflate two unrelated model identities',()=>{
    const s=fixture(),rows=scopedParticipation(participationRows(s),DEFAULT_STAT_SCOPE).slice(0,2)
    rows[0]={...rows[0],modelName:'identical',modelId:'model:a'};rows[1]={...rows[1],modelName:'identical',modelId:'model:b'}
    expect(groupParticipation(rows,'model')).toHaveLength(2)
  })
  test('CSV exports exact filtered assignments and neutralizes spreadsheet expressions',()=>{
    const rows=scopedParticipation(participationRows(fixture()),DEFAULT_STAT_SCOPE).slice(0,1)
    rows[0]={...rows[0],role:'=SUM(1,2)',modelName:'quoted "name"'}
    const csv=statisticsCsv(rows)
    expect(csv).toContain('"\'=SUM(1,2)"');expect(csv).toContain('"quoted ""name"""')
    expect(csv.split('\r\n')).toHaveLength(3)
    expect(csv).toContain('primary,true')
  })
  test('empty scope returns finite zeros, never NaN shares',()=>{
    const s=fixture(),empty=scopedParticipation(participationRows(s),{...DEFAULT_STAT_SCOPE,domain:'no-such-domain'})
    expect(empty).toHaveLength(0);expect(groupParticipation(empty,'model',s,true).every(g=>g.share===0)).toBe(true)
  })
})
