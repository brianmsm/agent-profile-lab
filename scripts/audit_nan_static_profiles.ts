import assert from 'node:assert/strict'
import {resolve} from 'node:path'
import {validateSnapshot} from '../dashboard/src/snapshotIO'
import {deriveNanStaticPreset} from '../dashboard/src/nanStaticProfiles'
import {presetNativeExport} from '../dashboard/src/presetStrategies'
import {compileAccessBundle} from '../dashboard/src/accessExport'
const root=resolve(import.meta.dirname,'..')
const snapshot=validateSnapshot(await Bun.file(root+'/dashboard/public/data/snapshot.json').json())
const cases=await Bun.file(root+'/validation/nan-static-parity.json').json() as {
  id:string;scenario:'routine'|'mixed'|'implementation';includeTrials:boolean;expected:any
}[]
function parity(got:unknown,expected:unknown,path='profile'){
  if(typeof got==='number'&&typeof expected==='number'){
    const difference=Math.abs(got-expected)
    assert(difference<=1e-12*Math.max(1,Math.abs(got),Math.abs(expected)),path+': numeric discrepancy '+got+'/'+expected)
    return
  }
  if(got===null||expected===null||typeof got!=='object'||typeof expected!=='object'){
    assert.equal(got,expected,path);return
  }
  if(Array.isArray(got)||Array.isArray(expected)){
    assert(Array.isArray(got)&&Array.isArray(expected),path+': array mismatch')
    assert.equal(got.length,expected.length,path+'.length')
    for(let i=0;i<got.length;i++)parity(got[i],expected[i],path+'['+i+']')
    return
  }
  const a=got as Record<string,unknown>,b=expected as Record<string,unknown>
  assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort(),path+'.keys')
  for(const key of Object.keys(a))parity(a[key],b[key],path+'.'+key)
}
let checks=0,exported=0
const failures:{id:string;scenario:string;trials:boolean;error:string}[]=[]
for(const c of cases){
 try{
  const p=deriveNanStaticPreset(snapshot,c.id,c.scenario,c.includeTrials,false)
  parity(p,c.expected)
  const native=presetNativeExport(snapshot,p)
  assert(native.content.includes('nan/'))
  if(checks<32){
    const bundle=await compileAccessBundle(snapshot,p,{mode:'preserve'})
    assert.equal(bundle.manifest.nanStaticPlan?.scenario,c.scenario)
    assert.equal(bundle.manifest.selectionPolicy,'nan-static')
    assert.equal(bundle.manifest.nativeArtifact.sha256,new Bun.CryptoHasher('sha256').update(bundle.native.content).digest('hex'))
    exported++
  }
  checks++
 }catch(e){failures.push({id:c.id,scenario:c.scenario,trials:c.includeTrials,error:String(e)});if(failures.length<6)console.error(c.id,c.scenario,c.includeTrials,String(e))}
}
const receipt={cases:cases.length,exactMatching:checks,exportsValidated:exported,failures,sourceBaselineUnchanged:true,inferencesSent:0}
await Bun.write(root+'/validation/nan-static-typescript-report.json',JSON.stringify(receipt,null,2)+'\n')
console.log(JSON.stringify({...receipt,failures:failures.slice(0,5)},null,2))
if(failures.length)process.exitCode=1
