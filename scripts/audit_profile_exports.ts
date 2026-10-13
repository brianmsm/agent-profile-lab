/** Exhaustive offline browser export/origin checks and Python/TS policy parity.
 * First run audit_profile_semantics.py --activities --output <directory>.
 */
import {resolve} from 'node:path'
import assert from 'node:assert/strict'
import {validateSnapshot} from '../dashboard/src/snapshotIO'
import {presets,presetNativeExport} from '../dashboard/src/presetStrategies'
import {deriveActivityPreset} from '../dashboard/src/activityProfiles'
import {validateProfileOrigins} from '../dashboard/src/accessRouting'
import type {ActivitySettings} from '../dashboard/src/activityProfiles'
const root=resolve(import.meta.dirname,'..'),output=resolve(root,process.argv[2]||'validation/profile-semantics')
if(!output.startsWith(root+'/validation/'))throw new Error('Audit outputs must stay under validation/')
const s=validateSnapshot(await Bun.file(root+'/dashboard/public/data/snapshot.json').json())
const cases: {id:string;profileId:string;activity:ActivitySettings;sha256:string}[]=await Bun.file(output+'/activity-parity-hashes.json').json()
function canonical(value:unknown):string {
  if(value===null||typeof value!=='object')return JSON.stringify(value)
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']'
  return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical((value as Record<string,unknown>)[key])).join(',')+'}'
}
const sha=(v:unknown)=>new Bun.CryptoHasher('sha256').update(canonical(v)).digest('hex')
const snapshotHash=sha(s),failure:{id:string;error:string}[]=[]
let baselineExports=0,strategyExports=0,activities=0
for(const p of presets(s)){
  try{
    validateProfileOrigins(s,p.meta,p.routes,s.access!.resourcesByPortfolio[p.portfolio])
    const native=presetNativeExport(s,p)
    if(p.kind==='matrix'){
      const base=p.sourceProfile.split('--')[1]
      const disk=await Bun.file(root+`/profiles/${p.meta.harness}/`+base+(p.meta.harness==='omp'?'.yaml':'.export.json')).text()
      if(p.meta.harness==='omp')assert.deepEqual(Bun.YAML.parse(native.content),Bun.YAML.parse(disk))
      else assert.deepEqual(JSON.parse(native.content).config,JSON.parse(disk).config)
      baselineExports++
    }else strategyExports++
  }catch(e){failure.push({id:p.id,error:String(e)})}
}
const fields=['sourceProfile','portfolio','routes','runtime','coordinatorPool','offloadPool','limitations','activityPlan'] as const
for(const c of cases){
  try{
    const p=deriveActivityPreset(s,c.profileId,c.activity)
    const actual=sha(Object.fromEntries(fields.map(k=>[k,p[k]])))
    assert.equal(actual,c.sha256,'Exact Python/TypeScript routes, conditions, origins and decision explanations must agree')
    validateProfileOrigins(s,p.meta,p.routes,s.access!.resourcesByPortfolio[p.portfolio])
    presetNativeExport(s,p)
    activities++
  }catch(e){failure.push({id:c.id,error:String(e)})}
  if((activities+failure.length)%2000===0)console.log('Activity exports checked',activities)
}
assert.equal(sha(s),snapshotHash,'Input snapshot mutation during generation')
const report={baselineExports,strategyExports,activityCases:cases.length,activityExports:activities,pythonTypescriptExactParity:failure.length===0,sourceSnapshotUnmodified:true,failures:failure,inferencesSent:0}
await Bun.write(output+'/exports-report.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,failures:failure.slice(0,10)},null,2))
if(failure.length)process.exitCode=1
