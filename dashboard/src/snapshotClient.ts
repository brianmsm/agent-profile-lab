import type { Snapshot } from './data'
import { mergeEvidence, EVIDENCE_FIELDS } from './deliveryCodec'

export interface SnapshotSession { core: Promise<Snapshot>; complete: () => Promise<Snapshot>; dispose: () => void }
export function createSnapshotSession(worker: Worker, url: string): SnapshotSession {
  let serial=0,disposed=false,full:Promise<Snapshot>|undefined
  const pending=new Map<number,{resolve:(s:Snapshot)=>void;reject:(e:Error)=>void;parts:Record<string,unknown>}>()
  const rejectAll=(error:Error)=>{for(const entry of pending.values())entry.reject(error);pending.clear()}
  worker.onerror=(e)=>{disposed=true;rejectAll(new Error(e.message||'Falló el procesador de datos.'));worker.terminate()}
  worker.onmessageerror=()=>{disposed=true;rejectAll(new Error('Respuesta de datos ilegible.'));worker.terminate()}
  worker.onmessage=(event)=>{
    const m=event.data,entry=pending.get(m.id)
    if(!entry || disposed)return
    if(m.field && !(EVIDENCE_FIELDS as readonly string[]).includes(m.field)){entry.reject(new Error('Campo de datos no admitido.'));pending.delete(m.id);return}
    if(m.chunk) {
      const list=(entry.parts[m.field]??=[]) as unknown[]
      if(m.field!=='benchmarks'||!Array.isArray(list)||m.offset!==list.length||!Array.isArray(m.value)){entry.reject(new Error('Fragmentos fuera de orden.'));pending.delete(m.id);return}
      for(const row of m.value)list.push(row);return
    }
    if(m.field){if(Object.hasOwn(entry.parts,m.field)){entry.reject(new Error('Campo de datos duplicado.'));pending.delete(m.id);return}entry.parts[m.field]=m.value;return}
    pending.delete(m.id)
    if(!m.ok){entry.reject(new Error(m.error||'Error de datos.'));return}
    if(m.complete)core.then(s=>{try{if(disposed)throw new Error('Carga cancelada.');entry.resolve(mergeEvidence(s,entry.parts,m.fields))}catch(e){entry.reject(e as Error)}})
    else entry.resolve(m.value)
  }
  function request(type:string):Promise<Snapshot>{
    if(disposed)return Promise.reject(new Error('La sesión de datos ya no está activa.'))
    return new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject,parts:{}});worker.postMessage({id,type,url})})
  }
  const core=request('init')
  return {core,complete:()=>full??=(core.then(()=>request('complete')).catch(error=>{full=undefined;throw error})),
    dispose:()=>{disposed=true;worker.terminate();rejectAll(new Error('Carga cancelada por cambio de conjunto de datos.'))}}
}
export function openSnapshotSession():SnapshotSession {
  return createSnapshotSession(new Worker(new URL('./snapshot.worker.ts',import.meta.url),{type:'module'}),new URL(import.meta.env.BASE_URL+'data/delivery.json',location.href).href)
}
export async function importSnapshot(file: File): Promise<Snapshot> {
  const worker=new Worker(new URL('./snapshot.worker.ts',import.meta.url),{type:'module'})
  try{return await new Promise<Snapshot>((resolve,reject)=>{
    worker.onmessage=e=>e.data.ok?resolve(e.data.value):reject(new Error(e.data.error))
    worker.onerror=e=>reject(new Error(e.message||'No se pudo validar la importación.'))
    worker.onmessageerror=()=>reject(new Error('Importación ilegible.'))
    worker.postMessage({id:1,type:'import',file})
  })}finally{worker.terminate()}
}
