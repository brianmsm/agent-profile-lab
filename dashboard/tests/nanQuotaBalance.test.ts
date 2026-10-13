import {describe,test,expect} from 'bun:test'
import {nanInventory,nanKeys,nanPolicy,nanQuotas,nanFunctions,hypotheticalNanUsage,sampleNanUsage,planNanTask,simulateNanTasks,validateNanUsage} from '../src/nanQuotaBalance'
import type {NanTask,NanUsage} from '../src/nanQuotaBalance'
const now=new Date('2026-10-10T12:00:00.000Z')
const task=(changes:Partial<NanTask>={}):NanTask=>({taskId:'case',functionId:'bounded-exploration',domain:'research',modality:'text',estimatedInputTokens:12000,estimatedTotalTokens:35000,highImpact:false,closedTask:true,acceptanceOracle:true,includeTrials:false,headroomFraction:.02,...changes})
const actual=():NanUsage=>({schemaVersion:1,month:'2026-10',observedAt:'2026-10-10T11:55:00Z',source:'provider-normalized',approximate:false,consumed:{nan_qwen:0,nan_ds:1400000,nan_mf:0,nan_glm:944900000},verifiedOffers:['nan_ds','nan_glm']})
describe('separate NaN quotas with conservative quality gates',()=>{
  test('four limits come from exactly the current user inventory, never from historical MiMo',()=>{
    expect(Object.fromEntries(nanInventory.models.map(m=>[m.offeringKey,m.monthlyTokens]))).toEqual(nanQuotas)
    expect(nanKeys).toEqual(['nan_qwen','nan_ds','nan_mf','nan_glm'])
    expect(nanQuotas.nan_ds).toBe(3000000000);expect(nanQuotas.nan_glm).toBe(2000000000)
  })
  test('unknown usage cannot be substituted with zero and screenshots remain approximate',()=>{
    expect(planNanTask(null,task(),now).status).toBe('unknown-usage')
    expect(planNanTask(sampleNanUsage(),task(),now).usedAsActual).toBe(false)
    expect(planNanTask(hypotheticalNanUsage(now),task(),now).usedAsActual).toBe(false)
    expect(planNanTask(sampleNanUsage(),task(),now,undefined,true).status).toBe('unknown-usage')
  })
  test('GLM already at 47.2% is not spent further merely to equalize raw tokens',()=>{
    const d=planNanTask(sampleNanUsage(),task(),now)
    expect(d.selected).toBe('nan_ds')
    expect(d.candidates.find(c=>c.offeringKey==='nan_glm')!.usedFraction).toBeCloseTo(.47245)
    expect(d.candidates.find(c=>c.offeringKey==='nan_mf')!.eligible).toBe(false)
    expect(d.candidates.find(c=>c.offeringKey==='nan_qwen')!.eligible).toBe(false)
  })
  test('trial opt-in permits MiMo and Qwen only for task functions with an oracle',()=>{
    const d=planNanTask(sampleNanUsage(),task({includeTrials:true}),now)
    expect(d.selected).toBe('nan_mf')
    expect(d.candidates.find(c=>c.offeringKey==='nan_qwen')!.classification).toBe('trial')
    expect(planNanTask(sampleNanUsage(),task({includeTrials:true,closedTask:false}),now).status).toBe('blocked')
    expect(planNanTask(sampleNanUsage(),task({includeTrials:true,acceptanceOracle:false}),now).status).toBe('blocked')
  })
  test('no replacement for critical/high impact/open-ended domains, not even under quota pressure',()=>{
    for(const change of [{highImpact:true},{domain:'cybersecurity'},{domain:'agent-use'},{functionId:'coordination'},{functionId:'critical-review'},{functionId:'source-research'}]){
      expect(planNanTask(sampleNanUsage(),task({...change,includeTrials:true}),now).status).toBe('blocked')
    }
  })
  test('Qwen cannot be silently admitted for coding and larger context than the conservative declared limit',()=>{
    const code=planNanTask(hypotheticalNanUsage(now),task({includeTrials:true,functionId:'bounded-implementation'}),now)
    expect(code.candidates.find(c=>c.offeringKey==='nan_qwen')!.eligible).toBe(false)
    const large=planNanTask(hypotheticalNanUsage(now),task({includeTrials:true,estimatedInputTokens:200000,estimatedTotalTokens:240000}),now)
    expect(large.candidates.find(c=>c.offeringKey==='nan_qwen')!.reason).toContain('contexto')
  })
  test('audio with trial opt-in has only one declared suitable model, not forced diversity',()=>{
    const d=planNanTask(hypotheticalNanUsage(now),task({includeTrials:true,modality:'audio'}),now)
    expect(d.selected).toBe('nan_mf');expect(d.candidates.filter(c=>c.eligible).map(c=>c.offeringKey)).toEqual(['nan_mf'])
  })
  test('headroom and quotas cannot be overrun by a predicted task',()=>{
    const u=actual();u.consumed.nan_ds=2_970_000_000;u.consumed.nan_glm=1_970_000_000
    expect(planNanTask(u,task({estimatedInputTokens:100000,estimatedTotalTokens:1000000}),now).status).toBe('no-eligible')
    expect(planNanTask(u,task({headroomFraction:0,estimatedInputTokens:100000,estimatedTotalTokens:1000000}),now).status).toBe('selected')
  })
  test('monthly rollover is never an assumed zero reset',()=>{
    expect(planNanTask(actual(),task(),new Date('2026-11-01T00:01:00Z')).status).toBe('unknown-usage')
    expect(planNanTask(actual(),task(),now,undefined,true).status).toBe('selected')
    const stale=actual();stale.observedAt='2026-10-08T11:55:00Z'
    expect(planNanTask(stale,task(),now,undefined,true).status).toBe('unknown-usage')
  })
  test('dispatcher requires eligible verified route, not just enough quota',()=>{
    const u=actual();u.verifiedOffers=['nan_glm']
    const d=planNanTask(u,task(),now,undefined,true)
    expect(d.selected).toBe('nan_glm')
    const busy=planNanTask(u,task(),now,{reserved:{},count:{nan_glm:7}},true)
    expect(busy.status).toBe('no-eligible')
    expect(busy.candidates.find(c=>c.offeringKey==='nan_glm')!.reason).toContain('Concurrencia')
  })
  test('a batch balances normalized fractions, not raw tokens or equal call counts',()=>{
    const u=hypotheticalNanUsage(now),plan=simulateNanTasks(u,task({includeTrials:true,estimatedInputTokens:10000,estimatedTotalTokens:100000}),500,now)
    expect(plan.planned).toBe(500);expect(u.consumed.nan_ds).toBe(0)
    const fractions=nanKeys.map(k=>plan.projected[k]/nanQuotas[k])
    expect(Math.max(...fractions)-Math.min(...fractions)).toBeLessThanOrEqual(100000/500000000+1e-12)
    expect(new Set(Object.values(plan.counts)).size).toBeGreaterThan(1)
  })
  test('policy never includes protected functions and bounds trial models explicitly',()=>{
    expect(nanFunctions).not.toContain('coordination');expect(nanFunctions).not.toContain('independent-review')
    expect(nanPolicy.functions['bounded-implementation']).not.toHaveProperty('nan_qwen')
    expect(nanPolicy.concurrency.byOffering.nan_mf).toBe(5)
  })
  test('strict normalized import rejects partial, negative, unrelated, duplicated or malformed counters',()=>{
    const u=actual();expect(validateNanUsage(u)).toEqual(u)
    for(const bad of [{...u,consumed:{nan_ds:0}}, {...u,consumed:{...u.consumed,nan_extra:1}}, {...u,consumed:{...u.consumed,nan_ds:-2}}, {...u,consumed:{...u.consumed,nan_ds:1.2}}, {...u,verifiedOffers:['nan_glm','nan_glm']}, {...u,month:'2026-09'}, {...u,observedAt:'not-a-date'}])expect(()=>validateNanUsage(bad)).toThrow()
  })
  test('invalid estimates, modality and safety margin are rejected',()=>{
    for(const changes of [{estimatedTotalTokens:1,estimatedInputTokens:2},{estimatedTotalTokens:0},{estimatedTotalTokens:Infinity},{modality:'video' as never},{headroomFraction:.26}])expect(()=>planNanTask(actual(),task(changes),now)).toThrow()
  })
})
