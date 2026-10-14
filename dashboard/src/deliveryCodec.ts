import {parseStrictJSON} from './strictJSON'
import type { RouteDetail, Snapshot } from './data'

export const EVIDENCE_FIELDS = ['benchmarkRegistry','benchmarks','sourceCoverage','cybersecurityEvidence'] as const
export type EvidenceFields = Pick<Snapshot, typeof EVIDENCE_FIELDS[number]>
export interface DeliveryPart { path: string; sha256: string; bytes: number; decodedBytes: number }
export interface DeliveryManifest { format: 'apl.delivery'; version: 1; sourceSha256: string; evidenceFields: string[]; parts: { core: DeliveryPart; evidence: DeliveryPart } }
function record(value: unknown): value is Record<string,unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}
export function validateDeliveryManifest(value: unknown): DeliveryManifest {
  if(!record(value) || value.format!=='apl.delivery' || value.version!==1 || typeof value.sourceSha256!=='string' || !/^[a-f0-9]{64}$/u.test(value.sourceSha256)
    || !record(value.parts) || !Array.isArray(value.evidenceFields) || new Set(value.evidenceFields).size!==value.evidenceFields.length
    || value.evidenceFields.some(k=>!(EVIDENCE_FIELDS as readonly unknown[]).includes(k))) throw new Error('Manifiesto de entrega no válido.')
  for(const name of ['core','evidence']) {
    const p=value.parts[name]
    if(!record(p) || typeof p.path!=='string' || typeof p.sha256!=='string' || !/^[a-f0-9]{64}$/u.test(p.sha256)
      || p.path!==`chunks/${name}-${p.sha256}.json.gz` || !Number.isSafeInteger(p.bytes) || Number(p.bytes)<=0
      || !Number.isSafeInteger(p.decodedBytes) || Number(p.decodedBytes)<=0) throw new Error('Fragmento, ruta o hash de entrega no válido.')
  }
  return value as unknown as DeliveryManifest
}
export function unpackCore(input: unknown): Snapshot {
  if(!record(input) || input.format!=='apl.core-transport' || input.version!==1 || !record(input.snapshot)
    || !Array.isArray(input.texts) || input.texts.some(v=>typeof v!=='string') || !Array.isArray(input.routes)) throw new Error('Transporte de perfiles no válido.')
  const texts=input.texts
  const at = (values: unknown[], index: unknown) => {
    if(!Number.isSafeInteger(index) || Number(index)<0 || Number(index)>=values.length) throw new Error('Referencia de diccionario fuera de rango.')
    return values[Number(index)]
  }
  const routes=input.routes.map(raw=>{
    if(!record(raw)) throw new Error('Ruta de transporte inválida.')
    return {...raw,condition:at(texts,raw.condition),rationale:at(texts,raw.rationale)} as RouteDetail
  })
  const expand = (value: unknown) => {
    if(!record(value)) throw new Error('Mapa de rutas inválido.')
    return Object.fromEntries(Object.entries(value).map(([role,index])=>[role,at(routes,index)]))
  }
  const s=input.snapshot
  if(EVIDENCE_FIELDS.some(k=>Object.hasOwn(s,k)) || !record(s.routeDetails) || !record(s.strategies)) throw new Error('El núcleo debe separar explícitamente la evidencia.')
  return {...s,routeDetails:Object.fromEntries(Object.entries(s.routeDetails).map(([pid,m])=>[pid,expand(m)])),
    strategies:Object.fromEntries(Object.entries(s.strategies).map(([sid,value])=>{
      if(!record(value))throw new Error('Estrategia inválida.')
      return [sid,{...value,routes:expand(value.routes)}]
    }))} as unknown as Snapshot
}
export function mergeEvidence(core: Snapshot, value: unknown, fields: string[]): Snapshot {
  if(!record(value) || Object.keys(value).length!==fields.length || fields.some(k=>!Object.hasOwn(value,k))
    || Object.keys(value).some(k=>!(EVIDENCE_FIELDS as readonly string[]).includes(k))) throw new Error('Evidencia incompleta o con campos ajenos al manifiesto.')
  return {...core,...value}
}

export async function decodeDeliveryPart(bytes:ArrayBuffer,part:DeliveryPart):Promise<unknown> {
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('')
  if(bytes.byteLength!==part.bytes || hash!==part.sha256)throw new Error('Integridad del fragmento incorrecta. Recarga o regenera los datos; no se mezclan capturas.')
  const decoded=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()
  if(decoded.byteLength!==part.decodedBytes)throw new Error('Longitud del fragmento descomprimido incorrecta.')
  return parseStrictJSON(new TextDecoder('utf-8',{fatal:true}).decode(decoded))
}
