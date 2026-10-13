import assert from 'node:assert/strict'
import {resolve} from 'node:path'
import {validateSnapshot} from '../dashboard/src/snapshotIO'
import {deriveNanHybridPreset,deriveNanStaticPreset} from '../dashboard/src/nanStaticProfiles'
import {validateNanCustomWorkload} from '../dashboard/src/nanCustomWorkload'
import {presetNativeExport} from '../dashboard/src/presetStrategies'
import {compileAccessBundle} from '../dashboard/src/accessExport'
const root=resolve(import.meta.dirname,'..')
const snapshot=validateSnapshot(await Bun.file(root+'/dashboard/public/data/snapshot.json').json())
const cases=await Bun.file(root+'/validation/nan-custom-parity.json').json() as {
  profileId:string;scenario:'routine'|'mixed'|'implementation';mode:'nan-only'|'hybrid-worker'
  trial:boolean;customWorkload:unknown;complexity:'bounded';status:'ok'|'rejected';expected?:unknown
}[]
function parity(a:unknown,b:unknown,path='candidate') {
  if(typeof a==='number'&&typeof b==='number') {
    assert(Math.abs(a-b)<=1e-12*Math.max(1,Math.abs(a),Math.abs(b)),path+': '+a+' vs '+b);return
  }
  if(a===null||b===null||typeof a!=='object'||typeof b!=='object') {
    assert.equal(a,b,path);return
  }
  if(Array.isArray(a)||Array.isArray(b)) {
    assert(Array.isArray(a)&&Array.isArray(b));assert.equal(a.length,b.length,path+'.length')
    for(let i=0;i<a.length;i++)parity(a[i],b[i],path+'['+i+']')
    return
  }
  const x=a as Record<string,unknown>,y=b as Record<string,unknown>
  assert.deepEqual(Object.keys(x).sort(),Object.keys(y).sort(),path+'.keys')
  for(const key of Object.keys(x))parity(x[key],y[key],path+'.'+key)
}
let generated=0,rejected=0,exports=0
const failures:{profileId:string;scenario:string;mode:string;error:string}[]=[]
for(const row of cases) {
  try{
    const custom=validateNanCustomWorkload(row.customWorkload)
    let profile
    try{
      profile=row.mode==='nan-only'
        ?deriveNanStaticPreset(snapshot,row.profileId,row.scenario,row.trial,false,undefined,custom)
        :deriveNanHybridPreset(snapshot,row.profileId,row.scenario,row.trial,row.complexity,false,'hybrid-worker',custom)
    }catch(error){
      if(row.status!=='rejected')throw error
      rejected++;continue
    }
    assert.equal(row.status,'ok','Python rejected but TypeScript accepted')
    parity(profile,row.expected)
    const native=presetNativeExport(snapshot,profile)
    assert(native.content.includes('nan/'))
    assert(profile.id.includes(custom.fingerprint))
    if(exports<24){
      const bundle=await compileAccessBundle(snapshot,profile,{mode:'preserve'})
      assert.equal(bundle.manifest.nanStaticPlan?.customWorkload?.fingerprint,custom.fingerprint)
      assert.equal(bundle.manifest.nativeArtifact.sha256,new Bun.CryptoHasher('sha256').update(bundle.native.content).digest('hex'))
      exports++
    }
    generated++
  }catch(error){
    failures.push({profileId:row.profileId,scenario:row.scenario,mode:row.mode,error:String(error)})
    if(failures.length<=5)console.error(row.profileId,row.scenario,row.mode,error)
  }
}
const report={cases:cases.length,generated,rejected,exportsChecked:exports,exactParity:!failures.length,failures,inferencesSent:0}
await Bun.write(root+'/validation/nan-custom-typescript-report.json',JSON.stringify(report,null,2)+'\n')
console.log(JSON.stringify({...report,failures:failures.slice(0,5)}))
if(failures.length)process.exitCode=1
