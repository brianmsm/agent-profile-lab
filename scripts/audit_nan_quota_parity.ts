/** Exhaustive cross-language property sweep. Does NOT contact any provider. */
import {resolve} from 'node:path'
import assert from 'node:assert/strict'
import {nanFunctions,planNanTask,hypotheticalNanUsage,sampleNanUsage} from '../dashboard/src/nanQuotaBalance'
import type {NanTask,NanUsage,NanInflight} from '../dashboard/src/nanQuotaBalance'
const root=resolve(import.meta.dirname,'..'),NOW='2026-10-10T12:00:00Z'
const origin=hypotheticalNanUsage(new Date(NOW))
const observed: NanUsage={...origin,source:'provider-normalized',approximate:false,observedAt:'2026-10-10T11:55:00Z',verifiedOffers:['nan_ds','nan_glm'],consumed:{nan_qwen:0,nan_ds:1400000,nan_mf:0,nan_glm:944900000}}
const cases: {usage:NanUsage|null;task:NanTask;now:string;requireVerified:boolean;inflight:NanInflight}[]=[]
let n=0
for(const usage of [null,origin,sampleNanUsage(),observed])
 for(const functionId of [...nanFunctions,'coordination','critical-review'])
 for(const includeTrials of [false,true])
 for(const modality of ['text','image','audio'] as const)
 for(const domain of ['research','cybersecurity']) {
  const task:NanTask={taskId:`parity-${n++}`,functionId,domain,modality,estimatedInputTokens:12000,estimatedTotalTokens:35000,closedTask:true,acceptanceOracle:true,highImpact:false,headroomFraction:.02,includeTrials}
  cases.push({usage,task,now:NOW,requireVerified:false,inflight:{reserved:{},count:{}}})
 }
for(const changed of [{headroomFraction:0},{headroomFraction:.25},{estimatedInputTokens:200000,estimatedTotalTokens:240000},{estimatedTotalTokens:1},{highImpact:true},{closedTask:false},{acceptanceOracle:false},{domain:'agent-use'},{functionId:'bounded-implementation'},{estimatedTotalTokens:1000000}]){
 const task:NanTask={taskId:`special-${n++}`,functionId:'bounded-exploration',domain:'research',modality:'text',estimatedInputTokens:12000,estimatedTotalTokens:35000,closedTask:true,acceptanceOracle:true,highImpact:false,headroomFraction:.02,includeTrials:true,...changed}
 cases.push({usage:observed,task,now:NOW,requireVerified:true,inflight:{reserved:{nan_ds:80000,nan_glm:20000},count:{nan_ds:2}}})
}
const normalized=(v:unknown):unknown=>typeof v==='number'&&!Number.isInteger(v)?Number(v.toPrecision(14)):Array.isArray(v)?v.map(normalized):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).map(([k,x])=>[k,normalized(x)])):v
const expected=cases.map(c=>{try{return planNanTask(c.usage,c.task,new Date(c.now),c.inflight,c.requireVerified)}catch(e){return {exception:e instanceof Error?e.message:String(e)}}})
const proc=Bun.spawnSync(['python3','-B','scripts/nan_quota_parity.py'],{cwd:root,stdin:Buffer.from(JSON.stringify(cases))})
if(proc.exitCode!==0){console.error(new TextDecoder().decode(proc.stderr));process.exit(2)}
const result=JSON.parse(new TextDecoder().decode(proc.stdout))
let errors=0
for(let i=0;i<cases.length;i++){
 try{assert.deepEqual(normalized(result[i]),normalized(expected[i]))}
 catch(e){if(errors++<5)console.error('DIFFERENCE',i,JSON.stringify(cases[i]),String(e))}
}
const receipt={cases:cases.length,mismatches:errors,equal:errors===0,status:'offline-checked',inferencesSent:0,sourceModels:4}
await Bun.write(root+'/validation/nan-quota-parity.json',JSON.stringify(receipt,null,2)+'\n')
console.log(JSON.stringify(receipt))
if(errors)process.exitCode=1
