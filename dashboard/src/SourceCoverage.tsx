import { useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, ExternalLink, FileText, Search } from 'lucide-react'
import { number } from './data'
import type { SourceCoverage as Coverage, SourceEntry } from './data'

const SOURCE_KIND_LABELS: Record<SourceEntry['kind'], string> = {
  benchmark: 'Benchmark', measurement: 'Medición', contract: 'Contrato', code: 'Código',
  'user-evidence': 'Evidencia del usuario', assumption: 'Supuesto', press: 'Prensa',
  telemetry: 'Telemetría (contexto)', mirror: 'Espejo', unknown: 'Tipo no determinado',
}
const STATUS_LABELS: Record<SourceEntry['status'], string> = {
  included: 'Incorporada', 'context-only': 'Solo contexto', unavailable: 'No disponible', superseded: 'Sustituida',
}
const PAGE_SIZE = 12

export default function SourceCoverage({ coverage }: { coverage?: Coverage }) {
  const [kind, setKind] = useState('')
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('es')
    return (coverage?.sources ?? []).filter(source => (!kind || source.kind === kind) && (!status || source.status === status)
      && [source.id, source.title, source.url, source.evidenceType, source.checked, source.limitations, source.note,
        SOURCE_KIND_LABELS[source.kind], STATUS_LABELS[source.status], ...source.artifacts].join(' ').toLocaleLowerCase('es').includes(needle))
  }, [coverage, kind, status, query])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pages - 1)
  const reset = () => { setKind(''); setStatus(''); setQuery(''); setPage(0) }

  if (!coverage) return <section className="panel coverage-panel" aria-labelledby="source-coverage-title">
    <div className="section-heading"><div><span className="eyebrow">REGISTRO DE FUENTES</span><h2 id="source-coverage-title">Cobertura de fuentes no declarada</h2></div></div>
    <p className="section-description">Este snapshot no incluye sourceCoverage. Sus resultados y referencias pueden consultarse, pero no es posible reconciliar aquí todas las fuentes o exclusiones. No se le asigna el registro del proyecto ni se interpreta esta ausencia como cero fuentes.</p>
  </section>

  return <section className="panel coverage-panel source-coverage-panel" aria-labelledby="source-coverage-title">
    <div className="section-heading"><div><span className="eyebrow">REGISTRO RECONCILIADO · NO ES UNA MEDIDA DE CALIDAD</span><h2 id="source-coverage-title">Qué fuentes aportan y cuáles no</h2></div><span className="record-count">{number(coverage.totals.sources)} fuentes registradas</span></div>
    <p className="section-description"><strong>Alcance declarado:</strong> {coverage.scope}<br /><strong>Generación del registro:</strong> {coverage.generatedAt}. Las fechas de comprobación son las declaradas por cada fuente; no garantizan actualización en vivo.</p>
    <p className="source-coverage-totals">{number(coverage.totals.benchmarks)} resultados activos · {number(coverage.totals.artifacts)} artifacts · {number(coverage.totals.excluded)} observaciones excluidas. Las referencias a catálogo, portfolios y asignaciones no son benchmarks.</p>
    {coverage.notes.length > 0 && <details className="method-details"><summary>Notas del alcance y reconciliación</summary>{coverage.notes.map((note, index) => <p key={index}>{note}</p>)}</details>}
    <div className="evidence-filters">
      <label>Tipo de fuente<select aria-label="Tipo de fuente" value={kind} onChange={event => { setKind(event.target.value); setPage(0) }}><option value="">Todos los tipos</option>{Object.entries(SOURCE_KIND_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Estado de fuente<select aria-label="Estado de fuente" value={status} onChange={event => { setStatus(event.target.value); setPage(0) }}><option value="">Todos los estados</option>{Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Buscar en el registro<div className="search-control"><Search size={16} /><input type="search" aria-label="Buscar fuentes registradas" placeholder="Título, ID, URL, límites o artifact…" value={query} onChange={event => { setQuery(event.target.value); setPage(0) }} /></div></label>
    </div>
    <p className="evidence-result-count" role="status">{number(filtered.length)} de {number(coverage.sources.length)} fuentes · página {safePage + 1} de {pages}</p>
    {filtered.length > 0 ? <>
      <div className="table-wrap" role="region" aria-label="Registro de fuentes; desplaza horizontalmente para consultar todas las columnas" tabIndex={0}>
        <table className="source-coverage-table"><caption className="sr-only">Fuentes del snapshot activo, estado, uso y límites</caption>
          <thead><tr><th scope="col">Fuente y origen</th><th scope="col">Tipo / estado</th><th scope="col">Uso en el snapshot</th><th scope="col">Comprobación y límites</th></tr></thead>
          <tbody>{filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE).map(source => <tr key={source.id}>
            <td><strong>{source.title}</strong><code className="benchmark-name">{source.id}</code>{/^https?:\/\//i.test(source.url)
              ? <a className="source-link" href={source.url} target="_blank" rel="noreferrer">Consultar origen <ExternalLink size={13} /><span className="sr-only"> de {source.title}; abre una nueva pestaña</span></a>
              : <span className="local-source"><FileText size={13} />{source.url || 'Origen no declarado'}</span>}<span className="source-url benchmark-name">{source.url}</span></td>
            <td><span className="tag">{SOURCE_KIND_LABELS[source.kind]}</span><span className="benchmark-name">{STATUS_LABELS[source.status]}</span><span className="muted-text">{source.evidenceType || 'Evidencia no especificada'}</span></td>
            <td><strong>{number(source.benchmarkCount)} resultados</strong><span className="benchmark-name">{number(source.catalogReferences)} referencias de catálogo<br />{number(source.portfolioReferences)} de portfolios<br />{number(source.assignmentReferences)} de asignaciones</span></td>
            <td><span className="benchmark-date">{source.checked || 'Fecha de comprobación no declarada'}</span><p>{source.limitations || 'Límites no declarados por la fuente.'}</p><details className="method-details"><summary>Notas y artifacts ({number(source.artifacts.length)})</summary><p>{source.note || 'Sin nota adicional declarada.'}</p>{source.artifacts.length > 0 ? <ul className="source-artifact-paths">{source.artifacts.map(path => <li key={path}><code>{path}</code></li>)}</ul> : <p>Sin artifact capturado asociado; consulta el estado y los límites de esta fuente.</p>}</details></td>
          </tr>)}</tbody>
        </table>
      </div>
      {pages > 1 && <div className="pagination evidence-pagination"><button className="icon-button" aria-label="Página anterior de fuentes" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}><ArrowLeft size={17} /></button><span>Página {safePage + 1} de {pages}</span><button className="icon-button" aria-label="Página siguiente de fuentes" disabled={safePage >= pages - 1} onClick={() => setPage(safePage + 1)}><ArrowRight size={17} /></button></div>}
    </> : <div className="empty-state"><Search size={25} /><h3>{coverage.sources.length ? 'No hay fuentes para estos filtros.' : 'El registro declarado no contiene fuentes.'}</h3><p>{coverage.sources.length ? 'El filtro solo afecta a este registro, no a los benchmarks ni al total del snapshot.' : 'Consulta el alcance declarado; esto no acredita cobertura externa.'}</p>{coverage.sources.length > 0 && <button className="text-button" onClick={reset}>Limpiar filtros de fuentes</button>}</div>}
    <details className="method-details artifact-reconciliation">
      <summary>Reconciliación de artifacts ({number(coverage.artifacts.length)})</summary>
      <p className="section-description">Todos los artifacts del registro, independientemente del filtro de fuentes. SHA-256 declarado por la ingesta offline; no se vuelve a verificar ni se descarga el origen desde el navegador. Los contadores son observaciones de cada artifact, no necesariamente resultados únicos.</p>
      {coverage.artifacts.length > 0 ? coverage.artifacts.map(artifact => <details className="method-details source-artifact-details" key={artifact.path}>
        <summary><code>{artifact.path}</code><span className="benchmark-name">{number(artifact.included)} incluidas · {number(artifact.excluded)} excluidas · {number(artifact.observed)} observadas</span></summary>
        <p><strong>Tipo:</strong> {artifact.kind}<br /><strong>SHA-256:</strong> <code>{artifact.sha256}</code></p>
        <p>Observaciones restantes (metadatos, contexto o duplicados según las notas de ingesta): {number(artifact.observed - artifact.included - artifact.excluded)}. Las razones de incorporación se declaran en las notas y límites de las fuentes asociadas.</p>
        {artifact.exclusions.length > 0 ? <ul className="source-artifact-paths">{artifact.exclusions.map((exclusion, index) => <li key={index}><code>{exclusion.locator}</code> · {number(exclusion.count)} observaciones · {exclusion.reason}</li>)}</ul> : <p>Sin motivos de exclusión detallados en este artifact.</p>}
        {artifact.excluded > artifact.exclusions.reduce((sum, item) => sum + item.count, 0) && <p>Hay exclusiones sin desglose de motivo; consulta las notas de reconciliación y los límites de fuente.</p>}
      </details>) : <p className="section-description">Este registro no declara artifacts capturados.</p>}
    </details>
  </section>
}
