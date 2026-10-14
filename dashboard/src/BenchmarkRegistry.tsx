import { useMemo, useState } from 'react'
import type { Snapshot } from './data'
import { number } from './data'
import { METRIC_LABELS } from './benchmarkTypes'
import { isRightsScopedEvidenceEdition, suiteHasVerifiableGap, suiteEvidencePresentation } from './registryEdition'

export default function BenchmarkRegistry({ snapshot }: { snapshot: Snapshot }) {
  const registry=snapshot.benchmarkRegistry
  const rightsScoped=isRightsScopedEvidenceEdition(snapshot)
  const [query,setQuery]=useState(''),[fn,setFn]=useState(''),[gaps,setGaps]=useState(false),[page,setPage]=useState(0)
  const suites=useMemo(()=>Object.values(registry?.suites||{}).filter(s => (!fn || s.policyFunctionIds?.includes(fn))
    && (!gaps || suiteHasVerifiableGap(s,rightsScoped))
    && [s.label,s.id,...s.domains,...(s.policyFunctionIds||[])].join(' ').toLowerCase().includes(query.toLowerCase())),[registry,query,fn,gaps,rightsScoped])
  if (!registry) return null
  const functions=[...new Set(Object.values(registry.suites).flatMap(s=>s.policyFunctionIds||[]))].sort()
  const size=8,pages=Math.max(1,Math.ceil(suites.length/size)),current=Math.min(page,pages-1)
  return <section className="panel registry-panel" aria-labelledby="registry-title">
    <div className="section-heading"><div><span className="eyebrow">ACTUALIZACIÓN MANUAL · COBERTURA POR RESPONSABILIDAD</span><h2 id="registry-title">Registro de benchmarks y lagunas</h2></div><span className="tag">Sin evaluaciones de perfiles propios</span></div>
    <p>{number(registry.stats.observations)} celdas numéricas conservadas · {number(registry.stats.currentObservations)} no sustituidas ni marcadas históricas · {number(registry.stats.suites)} familias/protocolos catalogados. <strong>No son números de experimentos independientes.</strong></p>
    <p className="footnote">Capturado no significa completamente extraído; normalizado no significa disponible para todos los modelos. Una correspondencia publicada no acredita el rendimiento en NaN, Pi u OMP. Las categorías de interés funcional son decisiones metodológicas del laboratorio.</p>
    {rightsScoped && <p className="footnote">En esta edición, las cifras indican sólo observaciones autorizadas para redistribución. Una familia con cero filas públicas no es una laguna de captura ni un resultado de calidad cero: no permite deducir qué se capturó o normalizó en el laboratorio privado.</p>}
    <div className="evidence-filters"><label>Suite, dominio o responsabilidad<input type="search" aria-label="Buscar suite o responsabilidad" value={query} onChange={e=>{setQuery(e.target.value);setPage(0)}} /></label><label>Función del perfil<select aria-label="Función del perfil para evidencia" value={fn} onChange={e=>{setFn(e.target.value);setPage(0)}}><option value="">Todas las funciones</option>{functions.map(f=><option key={f}>{f}</option>)}</select></label><label className="registry-gap-filter"><input type="checkbox" checked={gaps} onChange={e=>{setGaps(e.target.checked);setPage(0)}} />{rightsScoped?'Sólo lagunas verificables con cifras públicas':'Sólo lagunas de extracción, enlace o comparación'}</label></div>
    <p role="status">{suites.length} familias en este alcance · página {current+1} de {pages}.</p>
    <div className="table-wrap" tabIndex={0} role="region" aria-label="Estado de evidencia por suite"><table className="registry-table"><thead><tr><th>Familia / protocolo</th><th>Incorporación</th><th>Uso posible</th><th>Límites y fuentes</th></tr></thead><tbody>{suites.slice(current*size,(current+1)*size).map(s=><tr key={s.id}><th scope="row">{s.label}<span className="benchmark-name">{s.domains.join(' · ')}</span><details><summary>Funciones relacionadas</summary><p>{s.policyFunctionIds?.join(', ') || 'Pendiente'}</p></details></th><td>{suiteEvidencePresentation(s,rightsScoped).status}<br />{number(s.coverage.observations)} {rightsScoped
  ? (s.coverage.observations===1?'observación redistribuida':'observaciones redistribuidas')
  : (s.coverage.observations===1?'observación incorporada':'observaciones incorporadas')}<br />{number(s.coverage.current)} vigentes en el corpus</td><td>{number(s.coverage.linked)} enlazadas a identidades de catálogo<br />{number(s.coverage.comparable)} con protocolo estructurado<br />{number(s.coverage.decisionEligible)} aptas para criba inicial<br /><strong>Calibración de rutas: no</strong></td><td><details><summary>{suiteEvidencePresentation(s,rightsScoped).detailLabel}</summary>{rightsScoped && s.coverage.observations===0 && <p>Esta publicación no redistribuye cifras de esta familia. Consultar fuentes y límites; el cero cuenta filas de esta edición, no el trabajo científico previo.</p>}{s.limitations.map((limit,i)=><p key={i}>{limit}</p>)}<p>{s.decisionUse}</p>{s.captures.map(c=><p key={c.id}>{/^https:\/\//u.test(c.url)?<a href={c.url} target="_blank" rel="noreferrer">{c.id}</a>:c.id}<br />Capturado {c.capturedAt}<br /><code>{c.sha256}</code></p>)}</details></td></tr>)}</tbody></table></div>
    <div className="pagination"><button className="secondary-button" disabled={!current} onClick={()=>setPage(current-1)}>Anterior</button><span>{current+1} / {pages}</span><button className="secondary-button" disabled={current===pages-1} onClick={()=>setPage(current+1)}>Siguiente</button></div>
    <details className="registry-issues"><summary>Incidencias abiertas, tipos de métrica y cambios</summary>
      {Object.entries(registry.issues).map(([id,i])=><article key={id}><h3>{i.label}</h3><p>{i.note}</p><p>Estado: {i.status} · excluye: {i.blocks.join(', ')}</p></article>)}
      <p>Revisiones enlazadas entre capturas: {number(registry.stats.revisions)}. Capturar de nuevo el mismo resultado no añade una réplica experimental; un precio nuevo no supone capacidad nueva.</p>
      <div className="registry-kinds">{Object.entries(registry.stats.metricKinds).map(([key,count])=><span key={key}>{METRIC_LABELS[key as keyof typeof METRIC_LABELS] || key}: <strong>{number(count)}</strong></span>)}</div>
    </details>
  </section>
}
