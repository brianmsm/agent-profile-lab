import approval from '../../policies/nan-static-approval.json'
import functions from '../../policies/functions.json'
import scenarioCatalog from '../../policies/nan-static-workloads.json'
import rules from '../../policies/nan-custom-workload.json'
export type NanScenario = keyof typeof scenarioCatalog.scenarios
export type FunctionWorkload = Record<string,{callsPerMonth:number;totalTokensPerCall:number}>
export interface NanCustomWorkload {
  schemaVersion:1;kind:'nan-custom-workload';policyId:string;sourceWorkloadSha256:string
  baseScenario:NanScenario;label:string;description:string
  functionWorkload:FunctionWorkload;fingerprint:string
}
const knownFunctions=Object.keys(functions.functions).sort()
export const customWorkloadRules=rules
export const nanFunctionIds=knownFunctions
const isRecord=(value:unknown):value is Record<string,unknown>=>!!value&&typeof value==='object'&&!Array.isArray(value)
const identicalKeys=(value:Record<string,unknown>,expected:string[])=>JSON.stringify(Object.keys(value).sort())===JSON.stringify([...expected].sort())
function canonicalPayload(scenario:NanScenario,label:string,description:string,rows:FunctionWorkload) {
  return JSON.stringify([rules.kind,rules.policyId,approval.inputSha256['policies/nan-static-workloads.json'],scenario,label,description,
    knownFunctions.map(id=>[id,rows[id].callsPerMonth,rows[id].totalTokensPerCall])])
}
/** Two 64-bit lanes of FNV-1a for stable cross-Python/browser identity, not
 * cryptographic attestation. Native artifacts already use SHA-256. */
export function nanWorkloadFingerprint(scenario:NanScenario,label:string,description:string,rows:FunctionWorkload):string {
  const bytes=new TextEncoder().encode(canonicalPayload(scenario,label,description,rows))
  const mask=(1n<<64n)-1n,prime=1099511628211n
  let left=14695981039346656037n,right=7809847782465536322n
  for(const byte of bytes){left=((left^BigInt(byte))*prime)&mask;right=((right^BigInt(byte))*prime)&mask}
  return left.toString(16).padStart(16,'0')+right.toString(16).padStart(16,'0')
}
export function validateNanCustomWorkload(value:unknown):NanCustomWorkload {
  if(!isRecord(value)||!identicalKeys(value,['schemaVersion','kind','policyId','sourceWorkloadSha256','baseScenario','label','description','functionWorkload','fingerprint'])
    ||value.schemaVersion!==rules.schemaVersion||value.kind!==rules.kind||value.policyId!==rules.policyId||value.sourceWorkloadSha256!==approval.inputSha256['policies/nan-static-workloads.json'])
    throw new Error('El archivo no corresponde a esta revisión de escenarios. Conserva los originales de 20 funciones y migra explícitamente con scripts/migrate_nan_workload.py.')
  const scenario=value.baseScenario
  if(typeof scenario!=='string'||!Object.hasOwn(scenarioCatalog.scenarios,scenario))throw new Error('Escenario base desconocido.')
  const label=value.label,description=value.description
  if(typeof label!=='string'||!label.trim()||label!==label.trim()||label.length>rules.maxLabelLength
    ||(/[\p{Cc}]/u.test(label)||Array.from(label).some(char=>{const n=char.codePointAt(0)!;return n>=0xd800&&n<=0xdfff})))throw new Error('El nombre debe tener entre 1 y 64 caracteres imprimibles.')
  if(typeof description!=='string'||description.length>rules.maxDescriptionLength
    ||(/[\p{Cc}]/u.test(description)||Array.from(description).some(char=>{const n=char.codePointAt(0)!;return n>=0xd800&&n<=0xdfff})))throw new Error('La descripción no puede contener caracteres de control.')
  if(!isRecord(value.functionWorkload)||!identicalKeys(value.functionWorkload,knownFunctions))
    throw new Error('Faltan funciones o existen funciones ajenas a la política.')
  const rows:FunctionWorkload={}
  for(const id of knownFunctions){
    const row=value.functionWorkload[id]
    if(!isRecord(row)||!identicalKeys(row,['callsPerMonth','totalTokensPerCall'])||
      !Number.isSafeInteger(row.callsPerMonth)||Number(row.callsPerMonth)<0||Number(row.callsPerMonth)>rules.maxCallsPerMonth||
      !Number.isSafeInteger(row.totalTokensPerCall)||Number(row.totalTokensPerCall)<0||Number(row.totalTokensPerCall)>rules.maxTotalTokensPerCall||
      (Number(row.callsPerMonth)>0&&Number(row.totalTokensPerCall)===0))
      throw new Error('Valores mensuales no válidos para '+id+'.')
    rows[id]={callsPerMonth:Number(row.callsPerMonth),totalTokensPerCall:Number(row.totalTokensPerCall)}
  }
  const fingerprint=nanWorkloadFingerprint(scenario as NanScenario,label,description,rows)
  if(value.fingerprint!==fingerprint)throw new Error('Identificador de escenario alterado o inconsistente.')
  return {schemaVersion:1,kind:'nan-custom-workload',policyId:rules.policyId,sourceWorkloadSha256:approval.inputSha256['policies/nan-static-workloads.json'],
    baseScenario:scenario as NanScenario,label,description,functionWorkload:rows,fingerprint}
}
export function makeNanCustomWorkload(scenario:NanScenario,label:string,description:string,rows:FunctionWorkload):NanCustomWorkload {
  return validateNanCustomWorkload({schemaVersion:1,kind:'nan-custom-workload',
    policyId:rules.policyId,sourceWorkloadSha256:approval.inputSha256['policies/nan-static-workloads.json'],baseScenario:scenario,label,description,
    functionWorkload:rows,fingerprint:nanWorkloadFingerprint(scenario,label,description,rows)})
}
export function sourceNanWorkload(scenario:NanScenario):FunctionWorkload {
  if(!Object.hasOwn(scenarioCatalog.scenarios,scenario))throw new Error('Escenario base desconocido.')
  return structuredClone(scenarioCatalog.scenarios[scenario].functionWorkload)
}
export function customWorkloadEqualsBase(value:NanCustomWorkload):boolean {
  const base=sourceNanWorkload(value.baseScenario)
  return knownFunctions.every(id=>{
    const actual=value.functionWorkload[id],expected=base[id]
    return actual.callsPerMonth===expected.callsPerMonth&&actual.totalTokensPerCall===expected.totalTokensPerCall
  })
}
export function totalAssumedTokens(rows:FunctionWorkload):number {
  return knownFunctions.reduce((sum,id)=>sum+rows[id].callsPerMonth*rows[id].totalTokensPerCall,0)
}

/** Legacy recovery never edits localStorage or applies a profile automatically. */
export function migrateLegacyNanWorkload(value:unknown,acknowledge:boolean):NanCustomWorkload {
  if(!acknowledge)throw new Error('Confirma la copia de la hipótesis anterior de revisión al nuevo clasificador.')
  if(!isRecord(value)||!identicalKeys(value,['schemaVersion','kind','policyId','sourceWorkloadSha256','baseScenario','label','description','functionWorkload','fingerprint'])||value.sourceWorkloadSha256!=='702785699dceabdf8ef2028b411d2bb98251a749685f295d73a6946bc128ab87'||value.schemaVersion!==1||value.kind!==rules.kind||value.policyId!==rules.policyId)
    throw new Error('No es la revisión histórica de 20 funciones admitida.')
  const oldFunctions=knownFunctions.filter(id=>id!=='auxiliary-classification')
  if(!isRecord(value.functionWorkload)||!identicalKeys(value.functionWorkload,oldFunctions))throw new Error('La migración no puede eliminar funciones desconocidas.')
  const rows=structuredClone(value.functionWorkload) as FunctionWorkload
  rows['auxiliary-classification']=structuredClone(rows['independent-review'])
  const candidate=makeNanCustomWorkload(value.baseScenario as NanScenario,value.label as string,value.description as string,rows)
  const raw=JSON.stringify([value.kind,value.policyId,value.sourceWorkloadSha256,value.baseScenario,value.label,value.description,
    oldFunctions.map(id=>[id,rows[id].callsPerMonth,rows[id].totalTokensPerCall])])
  let a=14695981039346656037n,b=7809847782465536322n;const mask=(1n<<64n)-1n
  for(const byte of new TextEncoder().encode(raw)){a=((a^BigInt(byte))*1099511628211n)&mask;b=((b^BigInt(byte))*1099511628211n)&mask}
  if(value.fingerprint!==a.toString(16).padStart(16,'0')+b.toString(16).padStart(16,'0'))throw new Error('Identificador histórico inconsistente.')
  return candidate
}
