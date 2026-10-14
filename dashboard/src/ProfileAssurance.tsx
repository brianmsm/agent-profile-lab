import {useMemo} from 'react'
import type {Snapshot} from './data'
import {OBJECTIVES} from './data'
import type {Preset} from './presetStrategies'
import {getPreset,nativeMapEquivalence} from './presetStrategies'
import {presetAssurance,assurancePolicy} from './assuranceAnalysis'
export default function ProfileAssurance({snapshot,preset}:{snapshot:Snapshot;preset:Preset}){
 const summary=useMemo(()=>presetAssurance(snapshot,preset),[snapshot,preset])
 const objectives=useMemo(()=>{
  if(preset.kind!=='matrix')return []
  const peers=Object.entries(snapshot.meta).filter(([,m])=>m.harness===preset.meta.harness&&m.domain===preset.meta.domain&&m.portfolio===preset.portfolio).map(([id])=>getPreset(snapshot,id))
  const map=nativeMapEquivalence(snapshot,peers)
  return (map.get(preset.id)||[]).filter(id=>id!==preset.id).map(id=>snapshot.meta[id].objective)
 },[snapshot,preset])
 const texts=assurancePolicy.flags as Record<string,string>
 const effortReserves=Object.values(summary.fallbackKinds).filter(v=>v==='effort-alternative').length
 return <section className="trace-note profile-assurance" aria-label="Alcance verificado de esta configuración">
   <h3>Qué acredita esta configuración</h3>
   <p><strong>Referencia o candidata razonada · sin calibración de la ruta.</strong> Configurar un rol no demuestra que se invoque, que revise de forma independiente ni que aplique sus permisos.</p>
   <p>{summary.enabledRoles} roles habilitados / {summary.configuredRoles} configurados · {summary.declaredReviewRoles} {summary.declaredReviewRoles===1?'rol de revisión declarado':'roles de revisión declarados'} / {summary.distinctReviewRoutes} {summary.distinctReviewRoutes===1?'ruta principal distinta':'rutas principales distintas'}. Independencia de errores: <strong>no medida</strong>.</p>
   {summary.criticalReviewRoles>1&&<p>Dentro del panel crítico: {summary.criticalReviewRoles} lentes / {summary.distinctCriticalReviewRoutes} {summary.distinctCriticalReviewRoutes===1?'ruta principal distinta':'rutas principales distintas'}. Compartir ruta no demuestra igualdad de respuestas ni independencia de errores.</p>}
   <p><strong>Los archivos nativos no instalan</strong> autorización, aislamiento, revisión humana, pruebas de aceptación ni despacho de reservas. Deben verificarse en el entorno de ejecución antes del uso operativo.</p>
   {objectives.length>0&&<p role="note"><strong>Mismo mapa nativo y concurrencia</strong> que {objectives.map(o=>OBJECTIVES[o as keyof typeof OBJECTIVES]).join(', ')} en estos recursos y dominio. Pueden diferir las reservas o condiciones declaradas; no hay una mejora de rendimiento demostrada por cambiar el objetivo.</p>}
   {effortReserves>0&&<p>{effortReserves} reservas sólo cambian el esfuerzo del mismo selector y recurso: <strong>son alternativas de esfuerzo, no failover de proveedor</strong>.</p>}
   <details><summary>Alertas y comprobaciones pendientes ({summary.flags.length})</summary>{summary.flags.map(flag=><p key={flag}>{texts[flag]}</p>)}
    {!!summary.auxiliariesMatchingCoordinator.length&&<p>Auxiliares iguales a coordinación: <code>{summary.auxiliariesMatchingCoordinator.join(', ')}</code>. La referencia se conserva; contrastar esfuerzos en subtareas cerradas con un oráculo independiente.</p>}
    <p>La preparación de un commit no autoriza publicarlo. El clasificador <code>judge</code> de OMP no cuenta como revisión científica.</p>
    <p>Preflight local: <code>python3 scripts/preflight_profile.py --manifest … --native … --runtime-version …</code>. No consulta cuentas ni envía inferencias.</p>
   </details>
 </section>
}
