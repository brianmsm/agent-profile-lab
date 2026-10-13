import {resolve} from 'node:path'
import assert from 'node:assert/strict'
import {deriveReviewedCandidate} from '../dashboard/src/selectionCandidates'
import {presetNativeExport} from '../dashboard/src/presetStrategies'
import {validateSnapshot} from '../dashboard/src/snapshotIO'
import type {ActivitySettings} from '../dashboard/src/activityProfiles'
const root=resolve(import.meta.dirname,'..'),out=root+'/validation/reviewed-candidates'
const s=validateSnapshot(await Bun.file(root+'/dashboard/public/data/snapshot.json').json())
const cases: {profileId:string;recipeId:string;offeringKey:string;activity:ActivitySettings;sha256:string}[]=await Bun.file(out+'/cases.json').json()
function canonical(value:unknown):string {
 if(value===null||typeof value!=='object')return JSON.stringify(value)
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']'
 return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical((value as Record<string,unknown>)[k])).join(',')+'}'
}
const hash=(v:unknown)=>new Bun.CryptoHasher('sha256').update(canonical(v)).digest('hex')
let exports=0;const failures:{profileId:string;recipe:string;error:string}[]=[],names=new Set<string>()
const before=hash(s.routeDetails)
for(const c of cases){
 try{
  const p=deriveReviewedCandidate(s,c.profileId,c.recipeId,c.offeringKey,c.activity)
  assert.equal(hash(p),c.sha256,'Python/TypeScript recipe, roles, origins and conditions differ')
  const n=presetNativeExport(s,p)
  assert(!names.has(n.filename),'Filename collision between distinct candidates');names.add(n.filename)
  const config=p.meta.harness==='omp'?(Bun.YAML.parse(n.content) as {modelRoles:Record<string,string>}).modelRoles:JSON.parse(n.content).config
  assert.equal(Object.keys(config).length,Object.keys(p.routes).length)
  exports++
 }catch(e){failures.push({profileId:c.profileId,recipe:c.recipeId,error:String(e)})}
}
assert.equal(hash(s.routeDetails),before)
const result={cases:cases.length,successfulExports:exports,exactParity:!failures.length,uniqueArtifactNames:names.size,sourceRoutesUnmodified:true,failures,inferencesSent:0}
await Bun.write(out+'/typescript-report.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({...result,failures:failures.slice(0,8)},null,2))
if(failures.length)process.exitCode=1
