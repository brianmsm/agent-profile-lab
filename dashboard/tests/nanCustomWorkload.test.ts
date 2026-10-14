import {describe,test,expect} from 'bun:test'
import {customWorkloadRules,nanFunctionIds,makeNanCustomWorkload,validateNanCustomWorkload,sourceNanWorkload,totalAssumedTokens,nanWorkloadFingerprint,customWorkloadEqualsBase} from '../src/nanCustomWorkload'
import type {NanCustomWorkload} from '../src/nanCustomWorkload'
const make=(changes:Record<string,number>={})=>{
  const rows=sourceNanWorkload('mixed')
  for(const [id,number] of Object.entries(changes))rows[id].callsPerMonth=number
  return makeNanCustomWorkload('mixed','Mi carga semanal','Hipótesis editable',rows)
}
describe('custom workload schema and exact fingerprint',()=>{
  test('fingerprint matches the independently produced Python fixture',()=>{
    const x=make()
    expect(x.fingerprint).toBe('84d518c6c36cdf82578ec168ce3e1b59')
    expect(x.functionWorkload).toEqual(sourceNanWorkload('mixed'))
    expect(customWorkloadEqualsBase(x)).toBe(true)
    expect(nanFunctionIds).toHaveLength(21)
  })
  test('real changes alter identity and assumed totals; labels/descriptions are part of the version',()=>{
    const a=make(),b=make({'bounded-implementation':777})
    expect(b.fingerprint).not.toBe(a.fingerprint)
    expect(b.functionWorkload['bounded-implementation'].callsPerMonth).toBe(777)
    expect(totalAssumedTokens(b.functionWorkload)).toBeGreaterThan(totalAssumedTokens(a.functionWorkload))
    expect(customWorkloadEqualsBase(b)).toBe(false)
    const renamed=makeNanCustomWorkload('mixed','Otro nombre',b.description,b.functionWorkload)
    expect(renamed.fingerprint).not.toBe(b.fingerprint)
    expect(renamed.functionWorkload).toEqual(b.functionWorkload)
  })
  test('all three baseline scenarios can seed a custom scenario without altering the source',()=>{
    for(const base of ['routine','mixed','implementation'] as const){
      const a=sourceNanWorkload(base),b=sourceNanWorkload(base)
      b['status-reporting'].callsPerMonth=41
      expect(sourceNanWorkload(base)).toEqual(a)
      const x=makeNanCustomWorkload(base,'Carga '+base,'',b)
      expect(validateNanCustomWorkload(x)).toEqual(x)
    }
  })
  test('import rejects unknown functions, omitted functions, unexpected fields and misleading policy',()=>{
    const base=make()
    const mismatches=[
      {...base,functionWorkload:{...base.functionWorkload,attack:{callsPerMonth:1,totalTokensPerCall:10}}},
      {...base,functionWorkload:Object.fromEntries(Object.entries(base.functionWorkload).slice(1))},
      {...base,apiKey:'sensitive'},
      {...base,kind:'nan-provider-consumption'},
      {...base,policyId:'obsolete'},
      {...base,sourceWorkloadSha256:'0'.repeat(64)},
      {...base,baseScenario:'other'},
      {...base,fingerprint:'0'.repeat(32)}
    ]
    for(const bad of mismatches)expect(()=>validateNanCustomWorkload(bad)).toThrow()
  })
  test('bad numbers, too large calls or context and positive calls with zero tokens fail closed',()=>{
    const orig=make()
    const values=[-1,1.5,Number.NaN,Infinity,customWorkloadRules.maxCallsPerMonth+1]
    for(const v of values){
      const bad=structuredClone(orig) as NanCustomWorkload
      bad.functionWorkload['status-reporting'].callsPerMonth=v
      expect(()=>validateNanCustomWorkload(bad)).toThrow()
    }
    for(const v of [-1,Infinity,2.3,customWorkloadRules.maxTotalTokensPerCall+1,0]){
      const bad=structuredClone(orig) as NanCustomWorkload
      bad.functionWorkload['bounded-exploration'].totalTokensPerCall=v
      expect(()=>validateNanCustomWorkload(bad)).toThrow()
    }
  })
  test('empty scenario, overlong names, control chars and isolated surrogate rejected',()=>{
    const rows=sourceNanWorkload('mixed')
    for(const title of ['', ' trailing ','a'.repeat(65),'A\nB','\ud800']){
      expect(()=>makeNanCustomWorkload('mixed',title,'',rows)).toThrow()
    }
    expect(()=>makeNanCustomWorkload('mixed','Valid','\u0000',rows)).toThrow()
    expect(()=>makeNanCustomWorkload('mixed','Mi escena 💡','Texto con símbolos Ω y 🦊',rows)).not.toThrow()
  })
  test('zero calls can be expressed without removing a function; all-zero workload is not a quality recommendation',()=>{
    const rows=sourceNanWorkload('mixed')
    for(const id of nanFunctionIds)rows[id].callsPerMonth=0
    const x=makeNanCustomWorkload('mixed','Sin trabajo','Cero hipotético',rows)
    expect(totalAssumedTokens(x.functionWorkload)).toBe(0)
    expect(Object.keys(x.functionWorkload).length).toBe(21)
  })
  test('JSON export/import is a complete, versioned, deterministic local workload',()=>{
    const x=make({'status-reporting':0,'bounded-implementation':19})
    expect(validateNanCustomWorkload(JSON.parse(JSON.stringify(x)))).toEqual(x)
    expect(nanWorkloadFingerprint(x.baseScenario,x.label,x.description,x.functionWorkload)).toBe(x.fingerprint)
  })
})
