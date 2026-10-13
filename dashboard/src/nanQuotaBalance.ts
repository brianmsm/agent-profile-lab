import policy from '../../policies/nan-quota-balancing.json'
import inventory from '../../catalog/account-inventory.json'
import offerings from '../../catalog/offerings.json'

export const nanPolicy=policy
export const nanInventory=inventory
export type NanOffer='nan_qwen'|'nan_ds'|'nan_mf'|'nan_glm'
export type NanUsageSource='hypothetical'|'account-screenshot'|'user-entered'|'provider-normalized'
export type NanModality='text'|'image'|'audio'
export type NanFunction=keyof typeof policy.functions
export interface NanUsage {
  schemaVersion:1; month:string; observedAt:string; source:NanUsageSource
  consumed:Record<NanOffer,number>; verifiedOffers:NanOffer[]
  approximate:boolean
}
export interface NanTask {
  taskId:string; functionId:string; domain:string; modality:NanModality; estimatedInputTokens:number; estimatedTotalTokens:number
  highImpact:boolean; closedTask:boolean; acceptanceOracle:boolean
  includeTrials:boolean; headroomFraction:number
}
export interface NanInflight { reserved:Partial<Record<NanOffer,number>>; count:Partial<Record<NanOffer,number>> }
export interface NanCandidate {
  offeringKey:NanOffer; label:string; selector:string; classification:'eligible'|'trial'|'excluded'; reason:string
  quota:number; consumed:number; reserved:number; planned:number; available:number
  usedFraction:number; projectedFraction:number; paceFraction:number; remainingAfter:number; eligible:boolean; aheadOfPace:boolean
}
export interface NanDecision {
  status:'selected'|'blocked'|'unknown-usage'|'no-eligible'|'quota-unavailable'
  selected?:NanOffer; selector?:string; reason:string; candidates:NanCandidate[]
  month:string; usageSource:NanUsageSource|null; usageStale:boolean; usedAsActual:boolean
}
const keys=inventory.models.map(m=>m.offeringKey) as NanOffer[]
const keySet=new Set<string>(keys)
const quotas=Object.fromEntries(inventory.models.map(m=>[m.offeringKey,m.monthlyTokens])) as Record<NanOffer,number>
const contexts=Object.fromEntries(inventory.models.map(m=>[m.offeringKey,m.reportedContext])) as Record<NanOffer,number>
const selectors=Object.fromEntries(keys.map(k=>[k,offerings.offerings[k as keyof typeof offerings.offerings].compatibility.selector])) as Record<NanOffer,string>
const labels=policy.labels as Record<NanOffer,string>
export const nanKeys=keys
export const nanQuotas=quotas
export const nanSelectors=selectors
export const nanFunctions=Object.keys(policy.functions) as NanFunction[]
const integer=(n:unknown)=>typeof n==='number'&&Number.isSafeInteger(n)&&n>=0
function exactMonth(value:string):boolean { return /^\d{4}-(0[1-9]|1[0-2])$/u.test(value) }
function monthAt(date:Date):string {return `${date.getUTCFullYear()}-${String(date.getUTCMonth()+1).padStart(2,'0')}`}
export function validateNanUsage(value:unknown):NanUsage {
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Formato de consumo NaN inválido.')
  const u=value as Record<string,unknown>
  if(u.schemaVersion!==1||typeof u.month!=='string'||!exactMonth(u.month)||typeof u.observedAt!=='string'||!/(Z|[+-]\d{2}:\d{2})$/u.test(u.observedAt)||!Number.isFinite(Date.parse(u.observedAt))
    ||!['hypothetical','account-screenshot','user-entered','provider-normalized'].includes(String(u.source))||typeof u.approximate!=='boolean')throw new Error('Mes, fecha, fuente o estado de estimación inválidos.')
  if(Object.keys(u).sort().join(',')!=='approximate,consumed,month,observedAt,schemaVersion,source,verifiedOffers')throw new Error('La lectura no admite credenciales ni campos desconocidos.')
  if(!u.consumed||typeof u.consumed!=='object'||Array.isArray(u.consumed))throw new Error('Faltan contadores por modelo.')
  const consumed=u.consumed as Record<string,unknown>
  if(Object.keys(consumed).length!==keys.length||keys.some(k=>!integer(consumed[k]))||Object.keys(consumed).some(k=>!keySet.has(k)))throw new Error('Los contadores deben ser enteros no negativos para los cuatro modelos del plan.')
  if(!Array.isArray(u.verifiedOffers)||u.verifiedOffers.some(k=>!keySet.has(String(k)))||new Set(u.verifiedOffers).size!==u.verifiedOffers.length)throw new Error('Las rutas verificadas no corresponden al inventario NaN.')
  if(monthAt(new Date(u.observedAt))!==u.month)throw new Error('La fecha de observación no corresponde al mes declarado en UTC.')
  return u as unknown as NanUsage
}
export function sampleNanUsage():NanUsage {
  // Approximate screenshot counters, NOT an API reading or a verified current balance.
  return {schemaVersion:1,month:'2026-10',observedAt:'2026-10-10T10:00:00Z',source:'account-screenshot',approximate:true,
    consumed:{nan_qwen:0,nan_ds:1_400_000,nan_mf:0,nan_glm:944_900_000},verifiedOffers:[]}
}
export function hypotheticalNanUsage(now:Date):NanUsage {
  return {schemaVersion:1,month:monthAt(now),observedAt:now.toISOString(),source:'hypothetical',approximate:true,
    consumed:{nan_qwen:0,nan_ds:0,nan_mf:0,nan_glm:0},verifiedOffers:[]}
}
function elapsedFraction(now:Date) {
  const y=now.getUTCFullYear(),m=now.getUTCMonth();const start=Date.UTC(y,m,1),end=Date.UTC(y,m+1,1)
  return Math.min(1,Math.max(0,(now.getTime()-start)/(end-start)))
}
export function planNanTask(usageValue:NanUsage|null,task:NanTask,now:Date,inflight:NanInflight={reserved:{},count:{}},requireVerified=false):NanDecision {
  const base={status:'blocked' as const,reason:'',candidates:[] as NanCandidate[],month:monthAt(now),usageSource:usageValue?.source??null,usageStale:false,usedAsActual:false}
  if(!Number.isFinite(now.getTime()))throw new Error('Fecha de planificación inválida.')
  if(task.highImpact||!task.closedTask||!task.acceptanceOracle||policy.excludedDomains.includes(task.domain)||policy.excludedFunctions.includes(task.functionId as never)||!Object.hasOwn(policy.functions,task.functionId)) {
    return {...base,reason:'La tarea exige una decisión abierta, un dominio protegido o carece de oráculo de aceptación; se conserva el responsable original.'}
  }
  if(!integer(task.estimatedInputTokens)||!integer(task.estimatedTotalTokens)||task.estimatedTotalTokens<task.estimatedInputTokens||task.estimatedTotalTokens===0||!Number.isFinite(task.headroomFraction)||task.headroomFraction<0||task.headroomFraction>.25||!['text','image','audio'].includes(task.modality))throw new Error('Estimaciones o restricciones de la tarea inválidas.')
  if(!usageValue)return {...base,status:'unknown-usage',reason:'Introduce contadores de los cuatro modelos o selecciona expresamente una simulación. No se presumen saldos cero.'}
  const usage=validateNanUsage(usageValue)
  const sourceIsReal=usage.source==='provider-normalized'||usage.source==='user-entered'
  const ageHours=(now.getTime()-new Date(usage.observedAt).getTime())/3_600_000
  const stale=usage.month!==monthAt(now)||ageHours<0||ageHours>policy.maximumUsageAgeHoursForDispatch
  const usedAsActual=sourceIsReal&&!usage.approximate&&!stale
  const common={month:base.month,usageSource:usage.source,usageStale:stale,usedAsActual}
  if(requireVerified&&(!usedAsActual||!usage.verifiedOffers.length))return {...base,...common,status:'unknown-usage',reason:'Para reservar un despacho se exige consumo exacto reciente, mes vigente y al menos una ruta confirmada. Una captura o simulación no sirve.'}
  if(usage.month!==monthAt(now))return {...base,...common,status:'unknown-usage',reason:'El contador pertenece a otro mes; no se arrastra ni se reinicia automáticamente.'}
  const eligible=policy.functions[task.functionId as NanFunction] as Partial<Record<NanOffer,'eligible'|'trial'>>
  const pace=elapsedFraction(now)
  const candidates=keys.map(key=>{
    const classification=eligible[key]??'excluded',quota=quotas[key],consumed=usage.consumed[key],reserved=inflight.reserved[key]??0,count=inflight.count[key]??0
    if(!integer(reserved)||!integer(count))throw new Error('Reservas y concurrencia no válidas.')
    const projected=consumed+reserved+task.estimatedTotalTokens
    const balance=quota-consumed-reserved
    let reason='Admisible para esta función cerrada, condicionado a verificar resultado y ruta.'
    if(classification==='excluded')reason='No hay justificación de calidad para esta función.'
    else if(classification==='trial'&&!task.includeTrials)reason=policy.trialReasons[key as keyof typeof policy.trialReasons]||'Prueba de calidad no autorizada.'
    else if(task.modality!=='text'&&!policy.requirements[task.modality].includes(key))reason='La modalidad no está documentada para esta oferta.'
    else if(task.estimatedInputTokens>contexts[key]*policy.maximumInputFractionOfReportedContext)reason='Entrada por encima del límite conservador de contexto declarado.'
    else if(projected>quota*(1-task.headroomFraction))reason='La tarea proyectada excede el saldo disponible con reserva de seguridad.'
    else if(requireVerified&&!usage.verifiedOffers.includes(key))reason='La vía de acceso aún no está verificada para despachar.'
    else if(requireVerified&&(count>=policy.concurrency.byOffering[key]||Object.values(inflight.count).reduce((s,n)=>s+(n||0),0)>=policy.concurrency.totalByApiKey))reason='Concurrencia declarada ocupada; no se abre otra llamada.'
    const ok=reason==='Admisible para esta función cerrada, condicionado a verificar resultado y ruta.'
    return {offeringKey:key,label:labels[key],selector:selectors[key],classification,reason,quota,consumed,reserved,planned:task.estimatedTotalTokens,
      available:Math.max(0,balance),usedFraction:(consumed+reserved)/quota,projectedFraction:projected/quota,paceFraction:pace,
      remainingAfter:Math.max(0,quota-projected),eligible:ok,aheadOfPace:(consumed+reserved)/quota>pace}
  }) as NanCandidate[]
  const admitted=candidates.filter(c=>c.eligible).sort((a,b)=>a.projectedFraction-b.projectedFraction||a.usedFraction-b.usedFraction||a.offeringKey.localeCompare(b.offeringKey))
  if(!admitted.length)return {...common,status:'no-eligible',reason:'Ninguna vía apta cumple simultáneamente calidad, contexto, cuota, modalidad y condiciones de acceso. No se sustituye por un modelo incompatible.',candidates}
  const winner=admitted[0]
  const status=winner as NanCandidate
  return {...common,status:'selected',selected:status.offeringKey,selector:status.selector,
    reason:`${status.label} presenta la menor fracción proyectada de cuota entre las opciones admitidas (${(status.projectedFraction*100).toFixed(3)} %). Es una elección para la siguiente subtarea, no un cambio de modelo a mitad de turno.`,candidates}
}
export function simulateNanTasks(usage:NanUsage,task:NanTask,count:number,now:Date) {
  if(!Number.isInteger(count)||count<1||count>500)throw new Error('Simulación limitada a 1–500 tareas.')
  const copy={...usage,consumed:{...usage.consumed}},counts=Object.fromEntries(keys.map(k=>[k,0])) as Record<NanOffer,number>
  const decisions: {offeringKey:NanOffer;estimatedTokens:number}[]=[]
  for(let i=0;i<count;i++) {
    const next=planNanTask(copy,{...task,taskId:`${task.taskId}-${i}`},now)
    if(next.status!=='selected'||!next.selected)break
    copy.consumed[next.selected]+=task.estimatedTotalTokens
    counts[next.selected]++
    decisions.push({offeringKey:next.selected,estimatedTokens:task.estimatedTotalTokens})
  }
  return {projected:copy.consumed,counts,decisions,requested:count,planned:decisions.length,
    note:'Simulación determinista de consumo estimado, no llamadas ejecutadas ni cuotas realmente descontadas.'}
}
