import {describe,test,expect} from 'bun:test'
import {solveNanExactExpanded,NAN_MAX_SOLVER_STATES} from '../src/nanQuotaOptimizer'
import type {NanExpandedRow} from '../src/nanQuotaOptimizer'
import type {NanOffer} from '../src/nanQuotaBalance'
const QUOTAS:{[key in NanOffer]:number}={nan_qwen:500,nan_ds:3000,nan_mf:1000,nan_glm:2000}
const EMPTY:{[key in NanOffer]:number}={nan_qwen:0,nan_ds:0,nan_mf:0,nan_glm:0}
const keys:readonly NanOffer[]=['nan_qwen','nan_ds','nan_mf','nan_glm']
function brute(rows:NanExpandedRow[],cap:number){
  const total=rows.reduce((n,r)=>n+r.burden,0),Q=6500
  let best:{score:[number,number,number,string];choices:NanOffer[];totals:typeof EMPTY}|null=null
  const assign:NanOffer[]=[]
  function go(i:number,totals:typeof EMPTY,changes:number){
    if(i===rows.length){
      const exposure=totals.nan_qwen+totals.nan_mf
      if(exposure*10000>total*cap)return
      const error=keys.reduce((sum,key)=>sum+Math.abs(totals[key]*Q-total*QUOTAS[key]),0)
      const score:[number,number,number,string]=[error,exposure,changes,assign.join('\0')]
      if(best===null||score[0]<best.score[0]||
        (score[0]===best.score[0]&&(score[1]<best.score[1]||
        (score[1]===best.score[1]&&(score[2]<best.score[2]||
        (score[2]===best.score[2]&&score[3]<best.score[3])))))){
        best={score,choices:[...assign],totals:{...totals}}
      }
      return
    }
    for(const key of rows[i].options){
      assign.push(key);totals[key]+=rows[i].burden
      go(i+1,totals,changes+Number(rows[i].previous!==key))
      totals[key]-=rows[i].burden;assign.pop()
    }
  }
  go(0,{...EMPTY},0)
  if(!best)throw new Error('no oracle selection')
  return best as {score:[number,number,number,string];choices:NanOffer[];totals:typeof EMPTY}
}
describe('expanded exact NaN role selection',()=>{
 test('13 roles with two choices match independent exhaustive objective',()=>{
  for(const count of [11,12,13]){
    const rows:NanExpandedRow[]=Array.from({length:count},(_,i)=>({
      burden:100+(i%4)*70,previous:i%3?'nan_glm':'nan_ds',options:['nan_ds','nan_glm']}))
    const actual=solveNanExactExpanded(rows,EMPTY,QUOTAS,0)
    const expected=brute(rows,0)
    expect(actual.choices).toEqual(expected.choices)
    expect(actual.totals).toEqual(expected.totals)
    expect(actual.errorNumerator).toBe(String(expected.score[0]))
  }
 })
 test('experimental quota hard cap and deterministic lexical tie',()=>{
  const rows:NanExpandedRow[]=Array.from({length:13},(_,i)=>({burden:100+(i%3)*80,previous:'nan_ds',options:['nan_qwen','nan_ds']}))
  const actual=solveNanExactExpanded(rows,EMPTY,QUOTAS,2500)
  const expected=brute(rows,2500)
  expect(actual.choices).toEqual(expected.choices)
  expect(actual.trialTokens).toBe(expected.score[1])
 })
 test('complexity and malformed assumptions reject instead of returning a heuristic',()=>{
  const rows:NanExpandedRow[]=Array.from({length:14},(_,i)=>({burden:100+i%3*10,previous:'nan_ds',options:['nan_ds','nan_glm']}))
  expect(()=>solveNanExactExpanded(rows,EMPTY,QUOTAS,0,1)).toThrow('budget exceeded')
  expect(NAN_MAX_SOLVER_STATES).toBe(700000)
  expect(()=>solveNanExactExpanded(rows,EMPTY,QUOTAS,10001)).toThrow()
  expect(()=>solveNanExactExpanded(rows,EMPTY,{...QUOTAS,nan_ds:0},0)).toThrow()
 })
})
