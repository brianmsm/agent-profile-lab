import { useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { Snapshot } from './data'
import { SnapshotResource } from './snapshotResourceContext'
export function EvidenceBoundary({snapshot,children}:{snapshot:Snapshot;children:(complete:Snapshot)=>ReactNode}) {
  const load=useContext(SnapshotResource)
  const [state,setState]=useState<{data?:Snapshot;error?:string}>({})
  const [attempt,retry]=useState(0)
  useEffect(()=>{
    if(!load)return
    let active=true
    load().then(data=>{if(active)setState({data})},e=>{if(active)setState({error:e.message})})
    return ()=>{active=false}
  },[load,attempt])
  if(!load)return children(snapshot)
  if(state.error)return <section className="panel deferred-panel" role="alert"><h3>No se pudo cargar la evidencia.</h3><p>{state.error}</p><button className="secondary-button" onClick={()=>{setState({});retry(n=>n+1)}}>Reintentar</button></section>
  if(!state.data)return <section className="panel deferred-panel" role="status" aria-busy="true"><h3>Cargando y validando evidencia…</h3><p>Los perfiles ya están disponibles. La evidencia se procesa aparte; todavía no se muestran resultados parciales ni ceros.</p></section>
  return children(state.data)
}
