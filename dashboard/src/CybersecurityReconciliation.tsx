import { useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, ExternalLink, Info, Search } from 'lucide-react'
import { CYBER_RECONCILIATION_STATUSES, CYBER_RECONCILIATION_STATUS_LABELS as STATUS_LABELS, filterReconciliationEntries, number } from './data'
import type { ReconciliationFilters, Snapshot } from './data'

const PAGE_SIZE = 8
const EMPTY_FILTERS: ReconciliationFilters = { query: '', source: '', model: '', benchmark: '', metric: '', status: '' }

function Pagination({ page, pages, label, onChange }: { page: number; pages: number; label: string; onChange: (page: number) => void }) {
  return <div className="pagination evidence-pagination">
    <button className="icon-button" aria-label={`Página anterior de ${label}`} disabled={page === 0} onClick={() => onChange(page - 1)}><ArrowLeft size={17} /></button>
    <span>Página {page + 1} de {pages}</span>
    <button className="icon-button" aria-label={`Página siguiente de ${label}`} disabled={page >= pages - 1} onClick={() => onChange(page + 1)}><ArrowRight size={17} /></button>
  </div>
}

export default function CybersecurityReconciliation({ snapshot, onResultLink }: { snapshot: Snapshot; onResultLink: (id: string) => void }) {
  const reconciliation = snapshot.cybersecurityEvidence?.reconciliation
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [page, setPage] = useState(0)
  const [catalogKey, setCatalogKey] = useState('')
  const [catalogPage, setCatalogPage] = useState(0)
  const entries = useMemo(() => filterReconciliationEntries(reconciliation?.entries ?? [], filters), [reconciliation, filters])
  const reviewedModels = useMemo(() => reconciliation?.catalogReview.filter(row => !catalogKey || row.catalogKey === catalogKey) ?? [], [reconciliation, catalogKey])
  const reviewedSourcesById = useMemo(() => new Map(reconciliation?.reviewedSources.map(source => [source.sourceId, source]) ?? []), [reconciliation])
  const pages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE))
  const safePage = Math.min(page, pages - 1)
  const catalogPages = Math.max(1, Math.ceil(reviewedModels.length / PAGE_SIZE))
  const safeCatalogPage = Math.min(catalogPage, catalogPages - 1)
  const updateFilter = (key: keyof ReconciliationFilters, value: string) => { setFilters(current => ({ ...current, [key]: value })); setPage(0) }
  if (!reconciliation) return <div className="methodology-note" data-testid="cyber-reconciliation-missing"><Info size={18} /><p><strong>Sin reconciliación exhaustiva del corpus en este snapshot.</strong> Los resultados publicados siguen disponibles, pero no hay inventario de secciones revisadas, exclusiones y pendientes. No se interpreta como ausencia de publicaciones ni como cero.</p></div>
  const sources = Object.fromEntries(snapshot.sourceCoverage?.sources.map(source => [source.id, source.title]) ?? [])
  const benchmarkOptions = [...new Set(reconciliation.entries.map(row => row.benchmark))].sort()
  const metricOptions = [...new Set(reconciliation.entries.map(row => row.metric))].sort()
  const models = [...new Set(reconciliation.entries.map(row => JSON.stringify(row.publishedModel)))].sort()
  return <section className="cyber-reconciliation" aria-labelledby="cyber-reconciliation-heading" data-testid="cyber-reconciliation" data-closure={reconciliation.closure}>
    <h3 className="cyber-subheading" id="cyber-reconciliation-heading">Reconciliación del corpus publicado</h3>
    <p className="section-description"><strong>Corpus:</strong> {reconciliation.scope}<br /><strong>Fecha de corte:</strong> {reconciliation.asOf}<br /><strong>Límite de búsqueda:</strong> {reconciliation.searchBoundary}</p>
    <p className="source-coverage-totals"><strong>{reconciliation.closure === 'open' ? 'Corpus abierto · pendientes sin resolver' : 'Corpus reconciliado · sin pendientes de disposición'}</strong> · {number(reconciliation.reviewedSources.length)} fuentes revisadas · {number(reconciliation.catalogReview.length)} selectores revisados. El cierre solo describe este corpus acotado; no acredita exhaustividad mundial ni calibración de rutas.</p>
    <dl className="cyber-reconciliation-counts">{CYBER_RECONCILIATION_STATUSES.map(status => <div key={status}><dt>{STATUS_LABELS[status]}</dt><dd>{number(reconciliation.counts[status])}</dd></div>)}</dl>
    <details className="method-details cyber-reviewed-sources"><summary>Fuentes, capturas y secciones revisadas</summary><ul className="cyber-publications">{reconciliation.reviewedSources.map(source => <li key={source.sourceId}>
      <a className="source-link" href={source.sourceUrl} target="_blank" rel="noreferrer">{source.sourceId} · {sources[source.sourceId] ?? source.sourceId}<ExternalLink size={13} /><span className="sr-only">; abre una nueva pestaña</span></a>
      <p>Captura: {source.captureDate} · Receipt: <code>{source.receiptPath}</code></p>
      <p>Secciones: {source.sections.length ? source.sections.join(' · ') : 'No declaradas'}</p>
      <p>Selectores revisados: {source.catalogKeys.length ? source.catalogKeys.map(key => snapshot.catalog[key].selector).join(' · ') : 'Sin correspondencia declarada'}</p>
      {source.limitations.length > 0 && <ul>{source.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>}
    </li>)}</ul></details>
    <h4 className="cyber-subheading">Inventario de resultados y disposiciones</h4>
    <p className="section-description">Los filtros siguientes solo afectan este inventario. «No publicado» se refiere a una sección revisada, no a todo Internet. Cada métrica conserva su protocolo y unidad en el resultado vinculado.</p>
    <div className="evidence-filters cyber-reconciliation-filters">
      <label>Buscar motivo, localizador o resultado<div className="search-control"><Search size={16} /><input type="search" aria-label="Buscar reconciliación" value={filters.query} onChange={event => updateFilter('query', event.target.value)} /></div></label>
      <label>Fuente<select aria-label="Fuente de reconciliación" value={filters.source} onChange={event => updateFilter('source', event.target.value)}><option value="">Todas las fuentes</option>{reconciliation.reviewedSources.map(source => <option key={source.sourceId} value={source.sourceId}>{source.sourceId} · {sources[source.sourceId] ?? source.sourceId}</option>)}</select></label>
      <label>Etiqueta de modelo publicada<select aria-label="Modelo de reconciliación" value={filters.model} onChange={event => updateFilter('model', event.target.value)}><option value="">Todos los modelos</option>{models.map(model => <option key={model} value={model}>{JSON.parse(model) ?? 'Modelo no declarado'}</option>)}</select></label>
      <label>Benchmark / sección<select aria-label="Benchmark de reconciliación" value={filters.benchmark} onChange={event => updateFilter('benchmark', event.target.value)}><option value="">Todos los benchmarks / secciones</option>{benchmarkOptions.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Métrica<select aria-label="Métrica de reconciliación" value={filters.metric} onChange={event => updateFilter('metric', event.target.value)}><option value="">Todas las métricas · sin combinación</option>{metricOptions.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Disposición<select aria-label="Estado de reconciliación" value={filters.status} onChange={event => updateFilter('status', event.target.value)}><option value="">Todos los estados</option>{CYBER_RECONCILIATION_STATUSES.map(status => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}</select></label>
    </div>
    {Object.values(filters).some(Boolean) && <button className="text-button cyber-reset" onClick={() => { setFilters(EMPTY_FILTERS); setPage(0) }}>Restablecer filtros del inventario</button>}
    <div className="evidence-result-count" role="status">{number(entries.length)} de {number(reconciliation.entries.length)} disposiciones · página {safePage + 1} de {pages}</div>
    {entries.length ? <><div className="table-wrap" role="region" aria-label="Disposiciones del corpus; desplaza horizontalmente para consultar todas las columnas" tabIndex={0}><table className="cyber-reconciliation-table"><caption className="sr-only">Disposiciones de secciones revisadas con motivos y vínculos a resultados originales</caption><thead><tr><th>Fuente / modelo publicado</th><th>Benchmark / métrica</th><th>Disposición y motivo</th><th>Localizador / resultado</th></tr></thead><tbody>{entries.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE).map(row => <tr key={row.id} data-reconciliation-id={row.id} data-status={row.status}>
      <th scope="row"><a className="source-link" href={row.sourceUrl} target="_blank" rel="noreferrer">{row.sourceId}<ExternalLink size={13} /><span className="sr-only">; abre una nueva pestaña</span></a><strong>{row.publishedModel ?? 'Modelo no declarado'}</strong></th>
      <td><strong>{row.benchmark}</strong><span className="benchmark-name">{row.metric}</span></td>
      <td><span className={`tag ${row.status !== 'incorporated' ? 'cyber-gap' : ''}`}>{STATUS_LABELS[row.status]}</span><p>{row.reason}</p></td>
      <td><code>{row.locator}</code>{row.resultIds.length ? row.resultIds.map(id => <a className="source-link cyber-result-link" href={`#cyber-result-${id}`} key={id} onClick={event => { event.preventDefault(); onResultLink(id) }}>Ver resultado original<span className="sr-only"> {id}</span></a>) : <span className="missing-value">Sin resultado numérico vinculado · no es cero</span>}</td>
    </tr>)}</tbody></table></div><Pagination page={safePage} pages={pages} label="disposiciones de reconciliación" onChange={setPage} /></> : <div className="empty-state" data-testid="cyber-reconciliation-empty"><h4>El inventario no tiene coincidencias para estos filtros.</h4><p>Restablece los filtros para consultar motivos y pendientes del corpus completo; este subconjunto vacío no demuestra ausencia de publicaciones.</p></div>}
    <h4 className="cyber-subheading">Revisión de identidad, versión y fuentes del catálogo</h4>
    <p className="section-description">Conclusiones de publicación por selector, separadas del filtro de resultados. Las variantes, aliases y modos de velocidad no heredan evidencia sin correspondencia declarada.</p>
    <div className="evidence-filters"><label>Selector revisado<select aria-label="Selector revisado en reconciliación" value={catalogKey} onChange={event => { setCatalogKey(event.target.value); setCatalogPage(0) }}><option value="">Todo el catálogo</option>{reconciliation.catalogReview.map(row => <option key={row.catalogKey} value={row.catalogKey}>{snapshot.catalog[row.catalogKey].name} · {snapshot.catalog[row.catalogKey].selector}</option>)}</select></label></div>
    <div className="evidence-result-count" role="status">{number(reviewedModels.length)} de {number(reconciliation.catalogReview.length)} selectores revisados · página {safeCatalogPage + 1} de {catalogPages}</div>
    <div className="table-wrap" role="region" aria-label="Revisión de publicaciones por selector; desplaza horizontalmente para consultar todas las columnas" tabIndex={0}><table className="cyber-coverage-table"><caption className="sr-only">Conclusión de revisión de cada selector del catálogo</caption><thead><tr><th>Modelo / selector</th><th>Conclusión de la revisión</th><th>Fuentes revisadas</th></tr></thead><tbody>{reviewedModels.slice(safeCatalogPage * PAGE_SIZE, (safeCatalogPage + 1) * PAGE_SIZE).map(row => <tr key={row.catalogKey} data-reviewed-catalog-key={row.catalogKey}><th scope="row"><strong>{snapshot.catalog[row.catalogKey].name}</strong><code>{snapshot.catalog[row.catalogKey].selector}</code></th><td>{row.conclusion}</td><td>{row.sourceIds.length ? <details className="method-details"><summary>{number(row.sourceIds.length)} fuentes revisadas</summary><ul className="cyber-publications">{row.sourceIds.map(id => <li key={id}><a className="source-link" href={reviewedSourcesById.get(id)!.sourceUrl} target="_blank" rel="noreferrer">{id}<ExternalLink size={13} /><span className="sr-only">; abre una nueva pestaña</span></a></li>)}</ul></details> : <span className="missing-value">Sin fuente revisada vinculada · consulta la conclusión</span>}</td></tr>)}</tbody></table></div>
    <Pagination page={safeCatalogPage} pages={catalogPages} label="selectores revisados" onChange={setCatalogPage} />
  </section>
}
