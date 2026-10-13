import { createEvidenceSearch } from './evidenceQuery'
import BenchmarkRegistry from './BenchmarkRegistry'
import { METRIC_LABELS, DIRECTION_LABELS } from './benchmarkTypes'
import { memo, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, BookOpen, ExternalLink, FileText, Info, Search, ShieldCheck } from 'lucide-react'
import { number } from './data'
import type { Benchmark, Snapshot } from './data'
import SourceCoverage from './SourceCoverage'
import CybersecurityEvidence from './CybersecurityEvidence'
import { isMirrorBenchmark } from './benchmarkOrigin'
import ExternalEvidenceReferences from './ExternalEvidenceReferences'
const MemoRegistry=memo(BenchmarkRegistry), MemoSources=memo(SourceCoverage), MemoCyber=memo(CybersecurityEvidence)
const COVERAGE_LABELS: Record<string, string> = { coding: 'Código', computer_use: 'Uso del ordenador', research: 'Investigación', data: 'Datos', web: 'Web', cybersecurity: 'Ciberseguridad' }
const FAMILY_LABELS: Record<string, string> = Object.assign(Object.create(null), { openai: 'OpenAI', anthropic: 'Anthropic', glm_ds_mimo: 'GLM / DeepSeek / MiMo' })
const UNITS: Record<string, string> = Object.assign(Object.create(null), { 'index points': 'puntos de índice', seconds: 'segundos', 'tokens/s': 'tokens/s', 'USD / task': 'USD / tarea', 'USD / test': 'USD / test', 'composite score': 'puntuación compuesta', 'score': 'puntuación', points: 'puntos', ms: 'milisegundos', 'ms/token': 'ms/token', 'USD / 1M tokens': 'USD / 1M tokens' })
const PAGE_SIZE = 12
const EMPTY_BENCHMARKS: Benchmark[] = []
export default function Evidence({ snapshot }: { snapshot: Snapshot }) {
  const [kind,setKind] = useState('')
  const [state,setScope] = useState(snapshot.benchmarkRegistry ? 'current' : '')
  const [family, setFamily] = useState('')
  const [benchmark, setBenchmark] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const [origin, setOrigin] = useState<'reference' | 'mirror'>('reference')
  const [coverageQuery, setCoverageQuery] = useState('')
  const [coveragePage, setCoveragePage] = useState(0)
  const coverageFamilies = useMemo(() => {
    const needle = coverageQuery.trim().toLocaleLowerCase('es')
    return Object.entries(snapshot.coverage).filter(([id]) => [id, FAMILY_LABELS[id] || id].join(' ').toLocaleLowerCase('es').includes(needle))
  }, [snapshot.coverage, coverageQuery])
  const coverageTotalPages = Math.max(1, Math.ceil(coverageFamilies.length / PAGE_SIZE))
  const safeCoveragePage = Math.min(coveragePage, coverageTotalPages - 1)
  const records = snapshot.benchmarks || EMPTY_BENCHMARKS
  const mirrorRecords = useMemo(() => {
    const kinds = new Map(snapshot.sourceCoverage?.sources.map(source => [source.id, source.kind]))
    return new Set(records.filter(row => isMirrorBenchmark(row, row.sourceId ? kinds.get(row.sourceId) : undefined)))
  }, [records, snapshot.sourceCoverage])
  const scopedRecords = useMemo(() => records.filter(row => mirrorRecords.has(row) === (origin === 'mirror') && (!state || row.measurement?.scope===state) && (!kind || row.measurement?.kind===kind)), [records, mirrorRecords, origin, state, kind])
  const families = useMemo(()=>[...new Set(scopedRecords.map(row => row.family))].sort(),[scopedRecords])
  const benchmarks = useMemo(()=>[...new Set(scopedRecords.map(row => row.benchmark))].sort(),[scopedRecords])
  const searchIndex=useMemo(()=>createEvidenceSearch(records),[records])
  const filtered=useMemo(()=>{
    const needle=query.trim().toLocaleLowerCase('es')
    return scopedRecords.filter(row=>{
      if((family&&row.family!==family)||(benchmark&&row.benchmark!==benchmark))return false
      return searchIndex(row,needle)
    })
  },[scopedRecords,family,benchmark,query,searchIndex])
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages - 1)
  const change = (kind: 'family' | 'benchmark' | 'query', value: string) => { if (kind === 'family') setFamily(value); else if (kind === 'benchmark') setBenchmark(value); else setQuery(value); setPage(0) }
  return <>
    <section className="page-heading compact"><div><span className="eyebrow">FUENTES ANTES QUE CLASIFICACIONES</span><h1>Evidencia, no promesas.</h1><p>Resultados documentados, cobertura y límites de la auditoría.<br />No equivalen a calidad garantizada ni a inferencia en vivo.</p></div><span className="heading-icon"><BookOpen size={30} /></span></section>
    <section className="provenance-banner"><ShieldCheck size={23} /><div><strong>Auditoría registrada · {snapshot.stats.session}</strong><p>{number(snapshot.stats.validators.passed)} verificaciones aprobadas · {number(snapshot.stats.validators.failed)} fallos. {snapshot.provenance?.validationNote || 'Resultado histórico de la auditoría. No se han ejecutado validadores al abrir esta página.'}</p></div></section>
    <MemoRegistry snapshot={snapshot} />
    {snapshot.provenance?.kind==='public-rights-scoped-evidence-full-reference'&&<ExternalEvidenceReferences/>}
    <section className="panel coverage-panel"><div className="section-heading"><div><span className="eyebrow">MAPA DE COBERTURA</span><h2>Qué evidencia existe por familia</h2></div><span className="scope-label">Alcance global</span></div><p className="section-description">Familias según datasets y referencias declaradas. La presencia de un benchmark no implica cobertura completa ni metodologías equivalentes. Los identificadores de familia conservan la denominación de cada dataset.</p>{Object.hasOwn(snapshot.domainContracts, 'cybersecurity') && <p className="section-description"><strong>Límite de evidencia · Ciberseguridad:</strong> {snapshot.domainContracts.cybersecurity.evidenceNote}</p>}
      <label className="control-label">Buscar familias de cobertura<div className="search-control"><Search size={16} /><input type="search" aria-label="Buscar familias de cobertura" placeholder="Nombre o identificador de familia…" value={coverageQuery} onChange={event => { setCoverageQuery(event.target.value); setCoveragePage(0) }} /></div></label>
      <div className="evidence-result-count" role="status">{number(coverageFamilies.length)} de {number(Object.keys(snapshot.coverage).length)} familias · página {safeCoveragePage + 1} de {coverageTotalPages}</div>
      {coverageFamilies.length ? <><div className="table-wrap" role="region" aria-label="Cobertura por familia; desplaza horizontalmente para consultar todas las áreas" tabIndex={0}><table className="coverage-table"><caption className="sr-only">Cobertura declarada de benchmarks por familia y área; página {safeCoveragePage + 1} de {coverageTotalPages}</caption><thead><tr><th>Familia</th>{Object.entries(COVERAGE_LABELS).map(([id, label]) => <th key={id}>{label}</th>)}</tr></thead><tbody>{coverageFamilies.slice(safeCoveragePage * PAGE_SIZE, (safeCoveragePage + 1) * PAGE_SIZE).map(([id, domains]) => <tr key={id}><th scope="row">{FAMILY_LABELS[id] || id}</th>{Object.keys(COVERAGE_LABELS).map(domain => {
      const coverage = Object.hasOwn(domains, domain) ? domains[domain] : ''
      return <td className={!coverage || coverage === '—' || /parcial|sin benchmark/i.test(coverage) ? 'coverage-missing' : ''} key={domain}>{!coverage || coverage === '—' ? 'Sin evidencia declarada' : coverage.length > 160 && !/sin benchmark/i.test(coverage) ? <details className="method-details"><summary>Ver evidencia declarada</summary><p>{coverage}</p></details> : coverage}</td>
    })}</tr>)}</tbody></table></div>{coverageTotalPages > 1 && <div className="pagination evidence-pagination"><button className="icon-button" aria-label="Página anterior de familias de cobertura" disabled={safeCoveragePage === 0} onClick={() => setCoveragePage(safeCoveragePage - 1)}><ArrowLeft size={17} /></button><span>Página {safeCoveragePage + 1} de {coverageTotalPages}</span><button className="icon-button" aria-label="Página siguiente de familias de cobertura" disabled={safeCoveragePage >= coverageTotalPages - 1} onClick={() => setCoveragePage(safeCoveragePage + 1)}><ArrowRight size={17} /></button></div>}</> : <div className="empty-state"><Search size={25} /><h3>{Object.keys(snapshot.coverage).length ? 'No hay familias para esta búsqueda.' : 'Este snapshot no declara cobertura por familias.'}</h3><p>La consulta busca nombres e identificadores, no resultados ni textos de las fuentes.</p>{coverageQuery && <button className="text-button" onClick={() => { setCoverageQuery(''); setCoveragePage(0) }}>Limpiar búsqueda de familias</button>}</div>}</section>
    <MemoCyber snapshot={snapshot} />
    <MemoSources coverage={snapshot.sourceCoverage} />
    <section className="panel benchmark-panel"><div className="section-heading"><div><span className="eyebrow">RESULTADOS DOCUMENTADOS</span><h2>Consulta los benchmarks</h2></div><span className="record-count">{number(records.length)} registros globales</span></div><div className="methodology-note"><Info size={18} /><p>{snapshot.provenance?.benchmarkNote || 'Las escalas, el esfuerzo y las fuentes pueden diferir. Compara solo resultados con metodología y población equivalentes; esta vista no crea un ranking unificado.'}</p></div>
      {records.length > 0 && <div className="benchmark-origin-scope"><span className="control-label">Procedencia de resultados · grupos separados</span><div className="chips">{([['reference', 'Referencias no espejo', records.length - mirrorRecords.size], ['mirror', 'Espejos', mirrorRecords.size]] as const).map(([value, label, count]) => <button key={value} className={`chip ${origin === value ? 'active' : ''}`} aria-pressed={origin === value} onClick={() => { setOrigin(value); setFamily(''); setBenchmark(''); setPage(0) }}>{label} ({number(count)})</button>)}</div><p className="section-description">{origin === 'mirror' ? 'Resultados reproducidos por un espejo según el tipo de fuente o las notas/metodología. Consulta el origen y sus límites: no constituyen una referencia primaria independiente.' : 'Resultados sin identificación de espejo en el registro o las notas. Esta categoría no certifica que todas las fuentes sean primarias ni que sus metodologías sean equivalentes.'}</p></div>}
      {snapshot.benchmarkRegistry && <div className="evidence-filters"><label>Tipo de métrica<select aria-label="Tipo de métrica" value={kind} onChange={e=>{setKind(e.target.value);setBenchmark('');setPage(0)}}><option value="">Todos los tipos, sin mezclarlos en una puntuación</option>{Object.entries(METRIC_LABELS).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label><label>Estado de la observación<select aria-label="Estado de observaciones" value={state} onChange={e=>{setScope(e.target.value);setPage(0)}}><option value="current">No sustituida / vigente en el corpus</option><option value="historical">Histórica</option><option value="superseded">Sustituida por captura posterior</option><option value="">Todo el historial, sin duplicarlo como evidencia independiente</option></select></label></div>}
      {records.length ? <><div className="evidence-filters"><label>Familia<select aria-label="Familia de evidencia" value={family} onChange={e => change('family', e.target.value)}><option value="">Todas las familias</option>{families.map(value => <option key={value} value={value}>{FAMILY_LABELS[value] || value}</option>)}</select></label><label>Benchmark y escala<select aria-label="Benchmark" value={benchmark} onChange={e => change('benchmark', e.target.value)}><option value="">Todos los benchmarks</option>{benchmarks.map(value => <option key={value}>{value}</option>)}</select></label><label>Buscar modelo o fuente<div className="search-control"><Search size={16} /><input type="search" aria-label="Buscar evidencia" placeholder="Modelo, fuente, esfuerzo…" value={query} onChange={e => change('query', e.target.value)} /></div></label></div><div className="evidence-result-count" aria-live="polite">{number(filtered.length)} registros filtrados · orden de la fuente, no ranking por puntuación</div>
      {filtered.length ? <><div className="table-wrap" role="region" aria-label="Resultados documentados; desplaza horizontalmente para consultar todas las columnas" tabIndex={0}><table className="benchmark-table"><caption className="sr-only">Resultados documentados con escala, esfuerzo y fuente, grupo {origin === 'mirror' ? 'espejos' : 'referencias no espejo'}</caption><thead><tr><th>Modelo / benchmark</th><th>Resultado y unidad</th><th>Esfuerzo</th><th>Fuente y método</th></tr></thead><tbody>{filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE).map((row, index) => <tr key={`${safePage}-${index}`}>
        <td><strong>{row.model}</strong><span className="benchmark-name">{row.benchmark}</span><span className="muted-text">{FAMILY_LABELS[row.family] || row.family}</span></td>
        <td className="benchmark-value">{row.value === null ? <span className="missing-value">No disponible</span> : <><strong>{new Intl.NumberFormat('es-ES', { maximumSignificantDigits: 15 }).format(row.value)}</strong><span>{UNITS[row.unit] || row.unit || 'Unidad no declarada'}</span></>}<span className="benchmark-date">{row.date || 'Fecha no declarada'}</span></td>
        <td><span className="effort-tag">{row.effort || 'No declarado'}</span>{row.measurement && <><span className="benchmark-name">{METRIC_LABELS[row.measurement.kind]}</span><span className="benchmark-name">{DIRECTION_LABELS[row.measurement.direction]}</span><span className="tag">{row.measurement.scope}</span></>}</td>
        <td>{/^https?:\/\//i.test(row.source) ? <a className="source-link" href={row.source} target="_blank" rel="noreferrer">Consultar fuente <ExternalLink size={13} /><span className="sr-only"> de {row.model}, {row.benchmark}; abre una nueva pestaña</span></a> : <span className="local-source"><FileText size={13} />{row.source || 'Fuente no declarada'}</span>}
          <span className="provenance-type">{row.provenance || 'Procedencia no declarada'}</span>
          {mirrorRecords.has(row) && <span className="tag">Espejo · no referencia primaria</span>}
          {row.sourceId && <span className="benchmark-name">{snapshot.sourceCoverage ? 'Fuente registrada' : 'ID de fuente sin registro declarado'}: <code>{row.sourceId}</code></span>}
          <span className="benchmark-name">{row.methodology || 'Método no declarado'}</span>
          {row.measurement && <p className="benchmark-name">Identidad: {row.measurement.modelId || 'no resuelta'} · {row.measurement.modelRelation}. {row.measurement.issueIds.map(id=>snapshot.benchmarkRegistry?.issues[id]?.label||id).join(' · ')}</p>}
          {row.measurement && snapshot.benchmarkRegistry && <details className="method-details"><summary>Protocolo / fechas / denominador</summary><code>{JSON.stringify(snapshot.benchmarkRegistry.protocols[row.measurement.protocolId])}</code><p>Métrica: {JSON.stringify(snapshot.benchmarkRegistry.metrics[row.measurement.metricId])}</p></details>}
          <details className="method-details"><summary>Notas y límites</summary><p>{row.note || 'Sin nota metodológica adicional en la fuente.'}</p>{row.context && <p><strong>Contexto de origen:</strong> <code>{JSON.stringify(row.context)}</code></p>}<p className="source-url">{row.source}</p></details>
        </td>
      </tr>)}</tbody></table></div><div className="pagination evidence-pagination"><button className="icon-button" aria-label="Página anterior de evidencia" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}><ArrowLeft size={17} /></button><span>Página {safePage + 1} de {totalPages}</span><button className="icon-button" aria-label="Página siguiente de evidencia" disabled={safePage >= totalPages - 1} onClick={() => setPage(safePage + 1)}><ArrowRight size={17} /></button></div></> : <div className="empty-state"><Search size={25} /><h3>No hay registros para esta consulta.</h3><p>Prueba otra familia o benchmark, o elimina el texto de búsqueda.</p><button className="text-button" onClick={() => { setFamily(''); setBenchmark(''); setQuery(''); setPage(0) }}>Limpiar consulta <ArrowRight size={16} /></button></div>}</> : <div className="empty-state"><FileText size={27} /><h3>Este snapshot no contiene resultados numéricos.</h3><p>La cobertura declarada está disponible arriba. Regenera el snapshot con las fuentes de benchmarks para consultar resultados; la ausencia de datos no es una puntuación cero.</p></div>}
    </section>
    <section className="source-register"><div><span className="eyebrow">TRAZABILIDAD</span><h2>Fuentes del snapshot</h2><p>Datos estáticos del snapshot; no se consulta a los proveedores al navegar.</p></div>{snapshot.provenance?.sources.length ? <ul>{snapshot.provenance.sources.map(source => <li key={source}><FileText size={15} /><code>{source}</code></li>)}</ul> : <p>Procedencia no declarada</p>}</section>
  </>
}
