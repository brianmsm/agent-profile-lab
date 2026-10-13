/** Exact bounded branch-and-bound for larger NaN static role allocations.
 * Historical small grids still use the existing exhaustive solver.
 * No approximation is returned if the verified state budget is exceeded. */
import {nanKeys} from './nanQuotaBalance'
import type {NanOffer} from './nanQuotaBalance'
export interface NanExpandedRow {burden:number;previous:NanOffer;options:NanOffer[]}
export const NAN_MAX_SOLVER_STATES=700000
export function solveNanExactExpanded(
  rows:NanExpandedRow[],fixed:Record<NanOffer,number>,quotas:Record<NanOffer,number>,
  trialCapBps:number,maxStates=NAN_MAX_SOLVER_STATES
){
  if(rows.length<1||rows.length>32||!Number.isSafeInteger(maxStates)||maxStates<1)throw new Error('Invalid solver role count or complexity budget.')
  const keys=nanKeys as readonly NanOffer[]
  if(!Number.isInteger(trialCapBps)||trialCapBps<0||trialCapBps>10000)throw new Error('Invalid experimental cap.')
  const validInt=(n:number)=>Number.isSafeInteger(n)&&n>=0
  for(const key of keys)if(!validInt(fixed[key])||!validInt(quotas[key])||quotas[key]===0)throw new Error('Invalid quota count.')
  for(const row of rows)if(!validInt(row.burden)||!keys.includes(row.previous)||!row.options.length||row.options.some(k=>!keys.includes(k)))throw new Error('Invalid NaN role options.')
  const Q=keys.reduce((sum,k)=>sum+BigInt(quotas[k]),0n)
  const total=keys.reduce((sum,k)=>sum+fixed[k],0)+rows.reduce((sum,r)=>sum+r.burden,0)
  if(!Number.isSafeInteger(total)||total===0)throw new Error('Invalid estimated workload')
  const wanted=Object.fromEntries(keys.map(k=>[k,BigInt(total)*BigInt(quotas[k])])) as Record<NanOffer,bigint>
  const remaining=new Array<number>(rows.length+1).fill(0)
  for(let i=rows.length-1;i>=0;i--)remaining[i]=remaining[i+1]+rows[i].burden
  const current={...fixed},choices:NanOffer[]=[]
  let best:{err:bigint;trial:number;changes:number;choices:NanOffer[];totals:Record<NanOffer,number>}|null=null
  const memo=new Map<string,{changes:number;prefix:string}>()
  let visited=0
  const recurse=(i:number,changes:number)=>{
    visited++
    if(visited>maxStates)throw new Error('Exact NaN optimization complexity budget exceeded; no approximate allocation emitted')
    const trial=current.nan_qwen+current.nan_mf
    if(BigInt(trial)*10000n>BigInt(total)*BigInt(trialCapBps))return
    const left=remaining[i]
    let lower=0n
    for(const key of keys){
      const excessive=BigInt(current[key])*Q-wanted[key]
      const insufficient=wanted[key]-BigInt(current[key]+left)*Q
      if(excessive>0n)lower+=excessive
      else if(insufficient>0n)lower+=insufficient
    }
    if(best!==null&&lower>best.err)return
    const state=i+':'+keys.map(k=>current[k]).join(',')
    const prefix=choices.join('\0')
    const prior=memo.get(state)
    if(prior&&(prior.changes<changes||(prior.changes===changes&&prior.prefix<=prefix)))return
    memo.set(state,{changes,prefix})
    if(i===rows.length){
      const err=keys.reduce((sum,key)=>{
        const d=BigInt(current[key])*Q-wanted[key]
        return sum+(d>=0n?d:-d)
      },0n)
      if(best===null||err<best.err||(err===best.err&&
          (trial<best.trial||(trial===best.trial&&
          (changes<best.changes||(changes===best.changes&&prefix<best.choices.join('\0'))))))){
        best={err,trial,changes,choices:[...choices],totals:{...current}}
      }
      return
    }
    const row=rows[i]
    for(const key of row.options){
      current[key]+=row.burden
      choices.push(key)
      recurse(i+1,changes+(row.previous===key?0:1))
      choices.pop()
      current[key]-=row.burden
    }
  }
  recurse(0,0)
  if(best===null)throw new Error('No quality-admissible exact NaN allocation.')
  const result=best as {err:bigint;trial:number;changes:number;choices:NanOffer[];totals:Record<NanOffer,number>}
  return {choices:result.choices,totals:result.totals,errorNumerator:result.err.toString(),
    trialTokens:result.trial,changes:result.changes,visitedStates:visited,solver:'exact-branch-and-bound' as const}
}
