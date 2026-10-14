import {parseStrictJSON} from './strictJSON'
import { validateSnapshot, parseSnapshot } from './snapshotIO'
import { validateDeliveryManifest, unpackCore, mergeEvidence, decodeDeliveryPart } from './deliveryCodec'
import type { DeliveryManifest, DeliveryPart } from './deliveryCodec'
import type { Snapshot } from './data'

// No provider/API requests: only same-origin, content-addressed static assets.
let core: Snapshot | undefined, manifest: DeliveryManifest | undefined, baseURL: URL
const channel = self as unknown as { postMessage: (value: unknown) => void; onmessage: ((e: MessageEvent) => void) | null }
async function readPart(part: DeliveryPart) {
  const response=await fetch(new URL(part.path,baseURL))
  if(!response.ok)throw new Error(`Fragmento no disponible: HTTP ${response.status}`)
  const bytes=await response.arrayBuffer()
  return decodeDeliveryPart(bytes,part)
}
channel.onmessage=async(event)=>{
  const {id,type,url,file}=event.data
  try {
    if(type==='init') {
      baseURL=new URL('.',url)
      const response=await fetch(url,{cache:'no-cache'})
      if(!response.ok)throw new Error(`Entrega no disponible: HTTP ${response.status}. Regenera los datos con check_project.py --rebuild.`)
      manifest=validateDeliveryManifest(parseStrictJSON(await response.text()))
      core=validateSnapshot(unpackCore(await readPart(manifest.parts.core)))
      channel.postMessage({id,ok:true,value:core})
    } else if(type==='complete') {
      if(!core || !manifest)throw new Error('Datos base aún no disponibles.')
      const evidence=await readPart(manifest.parts.evidence)
      validateSnapshot(mergeEvidence(core,evidence,manifest.evidenceFields))
      // Bound individual main-thread deserialization tasks. Do not render an
      // incomplete dataset; the client only resolves after the final message.
      for(const [field,value] of Object.entries(evidence as Record<string,unknown>)) {
        if(field==='benchmarks' && Array.isArray(value)) {
          for(let i=0;i<value.length;i+=1500){channel.postMessage({id,chunk:true,field,offset:i,value:value.slice(i,i+1500)});await new Promise(r=>setTimeout(r,0))}
          if(!value.length)channel.postMessage({id,chunk:true,field,offset:0,value:[]})
        } else {channel.postMessage({id,field,value});await new Promise(r=>setTimeout(r,0))}
      }
      channel.postMessage({id,ok:true,complete:true,fields:manifest.evidenceFields})
    } else if(type==='import') {
      if(!(file instanceof Blob))throw new Error('Archivo de importación ausente.')
      channel.postMessage({id,ok:true,value:parseSnapshot(await file.text())})
    } else throw new Error('Operación de datos desconocida.')
  } catch(error) { channel.postMessage({id,ok:false,error:error instanceof Error?error.message:String(error)}) }
}
