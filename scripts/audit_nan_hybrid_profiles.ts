import assert from 'node:assert/strict'
import {resolve} from 'node:path'
import {validateSnapshot} from '../dashboard/src/snapshotIO'
import {deriveNanHybridPreset} from '../dashboard/src/nanStaticProfiles'
import {presetNativeExport} from '../dashboard/src/presetStrategies'
import {compileAccessBundle} from '../dashboard/src/accessExport'
const root=resolve(import.meta.dirname,'..')
const s=validateSnapshot(await Bun.file(root+'/dashboard/public/data/snapshot.json').json())
const cases=await Bun.file(root+'/validation/nan-hybrid-parity.json').json() as {
  id:string;scenario:'routine'|'mixed'|'implementation';trials:boolean;complexity:'standard'|'bounded';
  mode:'hybrid-preserve'|'hybrid-assist'|'hybrid-worker';expected:any
}[]
function compare(a:unknown,b:unknown,path='candidate'):void{
  if(typeof a==='number'&&typeof b==='number'){
    assert(Math.abs(a-b)<=1e-12*Math.max(1,Math.abs(a),Math.abs(b)),path+': number differs '+a+' vs '+b);return
  }
  if(a===null||b===null||typeof a!=='object'||typeof b!=='object'){
    assert.equal(a,b,path);return
  }
  if(Array.isArray(a)||Array.isArray(b)){
    assert(Array.isArray(a)&&Array.isArray(b),path+': array shape');assert.equal(a.length,b.length,path+'.length')
    for(let i=0;i<a.length;i++)compare(a[i],b[i],path+'['+i+']');return
  }
  const left=a as Record<string,unknown>,right=b as Record<string,unknown>
  assert.deepEqual(Object.keys(left).sort(),Object.keys(right).sort(),path+'.keys')
  for(const key of Object.keys(left))compare(left[key],right[key],path+'.'+key)
}
const failures:{id:string;mode:string;error:string}[]=[]
let exports=0,quality=0
for(const c of cases){
  try{
    const p=deriveNanHybridPreset(s,c.id,c.scenario,c.trials,c.complexity,false,c.mode)
    compare(p,c.expected)
    const n=presetNativeExport(s,p)
    assert(n.content.includes('nan/'),c.id)
    if(exports<24){
      const bundle=await compileAccessBundle(s,p,{mode:'preserve'})
      assert.equal(bundle.manifest.nanStaticPlan?.composition?.mode,c.mode)
      assert.equal(bundle.manifest.selectionPolicy,'nan-hybrid')
      assert.equal(bundle.manifest.nativeArtifact.sha256,new Bun.CryptoHasher('sha256').update(bundle.native.content).digest('hex'))
      exports++
    }
    const plan=p.nanStaticPlan!
    assert(plan.qualityGuard.trialFractionOfExpectedNaN<=plan.qualityGuard.trialShareCap+1e-12)
    quality++
  }catch(error){
    failures.push({id:c.id,mode:c.mode,error:String(error)})
    if(failures.length<6)console.error(c.id,c.mode,String(error))
  }
}
const result={cases:cases.length,exactMatching:quality,exportsChecked:exports,failures,inferencesSent:0}
await Bun.write(root+'/validation/nan-hybrid-typescript-report.json',JSON.stringify(result,null,2)+'\n')
console.log(JSON.stringify({...result,failures:failures.slice(0,5)}))
if(failures.length)process.exitCode=1
