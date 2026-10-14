import {describe,test,expect} from 'bun:test'
import {createElement} from 'react'
import {renderToStaticMarkup} from 'react-dom/server'
import {readFileSync} from 'node:fs'
import {resolve} from 'node:path'
import {spawnSync} from 'node:child_process'
import fixture from './fixtures/access-snapshot.json'
import type {Snapshot} from '../src/data'
import {getPreset} from '../src/presetStrategies'
import {compileAccessBundle} from '../src/accessExport'
import {presetAssurance,fallbackKind} from '../src/assuranceAnalysis'
import ProfileAssurance from '../src/ProfileAssurance'
import {migrateLegacyNanWorkload,sourceNanWorkload,makeNanCustomWorkload} from '../src/nanCustomWorkload'
import selectionPolicy from '../../policies/selection-candidates.json'
const snapshot=structuredClone(fixture) as unknown as Snapshot
const root=resolve(import.meta.dir,'../..')
describe('adversarial assurance remediation',()=>{
 for(const harness of ['gentle-shell','omp']){
  test(`${harness}: metadata assurance matches independent Python implementation`,async()=>{
   const id=Object.keys(snapshot.meta).find(id=>snapshot.meta[id].harness===harness)!
   const preset=getPreset(snapshot,id)
   const bundle=await compileAccessBundle(snapshot,preset,{mode:'preserve'})
   const payload={roles:bundle.manifest.roles,harness,domain:preset.meta.domain}
   const result=spawnSync('python3',['-B','scripts/assurance_bridge.py'],{cwd:root,input:JSON.stringify(payload)})
   expect(result.status).toBe(0)
   const python=JSON.parse(result.stdout.toString())
   expect(bundle.manifest.assurance).toEqual(python)
   expect(presetAssurance(snapshot,preset)).toEqual(python)
   expect(python.runtimeEnforcement).toBe('external-not-installed')
   expect(python.routeCalibration).toBe('not-measured')
  })
 }
 test('same selector with different effort is not provider failover',()=>{
  const p={selector:'test/model',effort:'low',accessRouteId:'test',resourceId:'a'}
  expect(fallbackKind(p,{...p,effort:'high'})).toBe('effort-alternative')
  expect(fallbackKind(p,{...p,resourceId:'b'})).toBe('different-access-resource')
  expect(fallbackKind(p,{...p,selector:'test/other'})).toBe('different-model-same-access')
 })
 test('all thirteen recipes have explicit per-function analogies and acceptance criteria',()=>{
  expect(selectionPolicy.recipes.length).toBe(13)
  for(const recipe of selectionPolicy.recipes){
   expect(Object.keys(recipe.functionEvidence).sort()).toEqual(Object.keys(recipe.selections).sort())
   for(const mapping of Object.values(recipe.functionEvidence)){
    expect(mapping.tier).toBe('E2-analogy');expect(mapping.routeCalibration).toBe('not-measured')
    expect(mapping.transferLimit.length).toBeGreaterThan(20);expect(mapping.acceptanceCriterion.length).toBeGreaterThan(20)
   }
  }
 })
 test('the view does not count labels as independent installed protection',()=>{
  const id=Object.keys(snapshot.meta).find(id=>snapshot.meta[id].harness==='omp')!
  const html=renderToStaticMarkup(createElement(ProfileAssurance,{snapshot,preset:getPreset(snapshot,id)}))
  expect(html).toContain('Qué acredita esta configuración')
  expect(html).toContain('Los archivos nativos no instalan')
  expect(html).toContain('no cuenta como revisión científica')
  expect(html).toContain('no medida')
 })
 test('reviewed legacy fingerprint migrates without losing any of its twenty rows',()=>{
  const rows=sourceNanWorkload('mixed');delete rows['auxiliary-classification']
  const old={schemaVersion:1,kind:'nan-custom-workload',policyId:'nan-static-workload-v1',sourceWorkloadSha256:'702785699dceabdf8ef2028b411d2bb98251a749685f295d73a6946bc128ab87',baseScenario:'mixed',label:'Mi carga semanal',description:'Hipótesis editable',functionWorkload:rows,fingerprint:'8b155d39d28f23f37ee76f5439be9810'}
  const before=JSON.stringify(old),migrated=migrateLegacyNanWorkload(old,true)
  expect(JSON.stringify(old)).toBe(before)
  expect(migrated).toEqual(makeNanCustomWorkload('mixed',old.label,old.description,sourceNanWorkload('mixed')))
  expect(migrated.functionWorkload['auxiliary-classification']).toEqual(old.functionWorkload['independent-review'])
  expect(Object.keys(migrated.functionWorkload).length).toBe(21)
 })
 test('legacy recovery cannot silently overwrite the old browser storage',()=>{
  const source=readFileSync(new URL('../src/NanCustomWorkloadEditor.tsx',import.meta.url),'utf8')
  expect(source).toContain("const LEGACY_STORAGE='agent-profile-lab.nan-custom-workloads.v1'")
  expect(source).toContain("const STORAGE='agent-profile-lab.nan-custom-workloads.v2'")
  expect(source).not.toContain('localStorage.setItem(LEGACY_STORAGE')
  expect(source).not.toContain('localStorage.removeItem(LEGACY_STORAGE')
  expect(()=>migrateLegacyNanWorkload({},false)).toThrow('Confirma')
  expect(()=>migrateLegacyNanWorkload({},true)).toThrow('revisión histórica')
 })
})
