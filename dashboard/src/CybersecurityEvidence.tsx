import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, ExternalLink, Info, Search } from 'lucide-react'
import { decimal, number } from './data'
import type { CyberCoverageState, CyberResultType, Snapshot } from './data'
import CybersecurityReconciliation from './CybersecurityReconciliation'
import './cybersecurityEvidence.css'

const PAGE_SIZE = 8
const STATE_LABELS: Record<CyberCoverageState, string> = {
  'measured-result': 'Resultado publicado del modelo',
  'candidate-alias-only': 'Solo alias candidato · identidad no resuelta',
  'editorial-only': 'Solo contexto editorial · no benchmark de eficacia',
  'no-mapped-result': 'Sin resultado mapeado en este corpus',
}
const TYPE_LABELS: Record<CyberResultType, string> = {
  independent: 'Independiente', vendor: 'Publicado por el fabricante',
  'vendor-comparator': 'Comparador reportado por otro fabricante', editorial: 'Editorial · no eficacia',
}

export default function CybersecurityEvidence({ snapshot }: { snapshot: Snapshot }) {
  const [query, setQuery] = useState('')
  const [selector, setSelector] = useState('')
  const [benchmark, setBenchmark] = useState('')
  const [coveragePage, setCoveragePage] = useState(0)
  const [resultPage, setResultPage] = useState(0)
  const [linkedResult, setLinkedResult] = useState<{ id: string } | null>(null)
  const evidence = snapshot.cybersecurityEvidence
  const resultsById = useMemo(() => new Map(evidence?.results.map(row => [row.id, row]) ?? []), [evidence])
  const needle = query.trim().toLocaleLowerCase('es')
  const coverage = useMemo(() => (evidence?.catalogCoverage ?? []).filter(row => {
    const model = snapshot.catalog[row.catalogKey]
    return (!selector || row.catalogKey === selector) && [row.catalogKey, model.name, model.selector, row.reason, STATE_LABELS[row.state]].join(' ').toLocaleLowerCase('es').includes(needle)
  }), [evidence, snapshot.catalog, selector, needle])
  const results = useMemo(() => (evidence?.results ?? []).filter(row => {
    const catalogText = row.catalogMatches.flatMap(match => [match.catalogKey, snapshot.catalog[match.catalogKey].name, snapshot.catalog[match.catalogKey].selector])
    return (!selector || row.catalogMatches.some(match => match.catalogKey === selector))
      && (!benchmark || row.benchmark === benchmark)
      && [row.publishedModel, row.benchmark, row.sourceId, row.settings, ...catalogText].join(' ').toLocaleLowerCase('es').includes(needle)
  }), [evidence, snapshot.catalog, selector, benchmark, needle])
  const coveragePages = Math.max(1, Math.ceil(coverage.length / PAGE_SIZE))
  const resultPages = Math.max(1, Math.ceil(results.length / PAGE_SIZE))
  const safeCoveragePage = Math.min(coveragePage, coveragePages - 1)
  const safeResultPage = Math.min(resultPage, resultPages - 1)
  const benchmarks = [...new Set(evidence?.results.map(row => row.benchmark) ?? [])].sort()
  useEffect(() => {
    if (!linkedResult) return
    const row = document.getElementById(`cyber-result-${linkedResult.id}`)
    row?.scrollIntoView({ block: 'center' })
    row?.focus({ preventScroll: true })
  }, [linkedResult])
  return <section className="panel cyber-evidence-panel" aria-labelledby="cyber-evidence-heading" data-testid="cybersecurity-evidence">
    <div className="section-heading"><div><span className="eyebrow">PUBLICACIÓN ≠ VALIDACIÓN DE RUTA</span><h2 id="cyber-evidence-heading">Ciberseguridad: resultados y correspondencia</h2></div></div>
    {!evidence ? <div className="empty-state" data-testid="cybersecurity-evidence-missing"><Info size={25} /><h3>Este snapshot no incorpora la sección de ciberseguridad.</h3><p>No se interpreta como ausencia de publicaciones ni como un resultado cero. Importa un snapshot actualizado para consultar resultados publicados y correspondencias de cada selector.</p></div> : <>
      <p className="section-description"><strong>Alcance:</strong> {evidence.scope}<br /><strong>Última captura de fuentes:</strong> {evidence.asOf} · no es una fecha de evaluación ni una medición en vivo.</p>
      <div className="methodology-note"><Info size={18} /><p><strong>Sin calibración ni eficacia de las rutas establecida.</strong> {evidence.routingConclusion} No hay ranking entre benchmarks o protocolos distintos. Las tarjetas de capacidad/riesgo sin valores numéricos son contexto, no resultados de benchmark: consulta sus notas y artefactos en el registro de fuentes.</p></div>
      <CybersecurityReconciliation snapshot={snapshot} onResultLink={id => {
        const index = evidence.results.findIndex(result => result.id === id)
        if (index < 0) return
        setQuery(''); setSelector(''); setBenchmark('')
        setResultPage(Math.floor(index / PAGE_SIZE)); setLinkedResult({ id })
      }} />
      <div className="evidence-filters cyber-filters">
        <label>Buscar publicación o selector<div className="search-control"><Search size={16} /><input type="search" aria-label="Buscar ciberseguridad" placeholder="OpenAI, Claude, DeepSeek, GLM, Kimi, NaN…" value={query} onChange={event => { setQuery(event.target.value); setCoveragePage(0); setResultPage(0) }} /></div></label>
        <label>Correspondencia del catálogo<select aria-label="Selector de ciberseguridad" value={selector} onChange={event => { setSelector(event.target.value); setCoveragePage(0); setResultPage(0) }}><option value="">Todo el catálogo · todos los pools</option>{Object.entries(snapshot.catalog).map(([key, model]) => <option key={key} value={key}>{model.name} · {model.selector}</option>)}</select></label>
        <label>Benchmark · solo resultados<select aria-label="Benchmark de ciberseguridad" value={benchmark} onChange={event => { setBenchmark(event.target.value); setResultPage(0) }}><option value="">Todos · sin ranking conjunto</option>{benchmarks.map(name => <option key={name}>{name}</option>)}</select></label>
      </div>
      <h3 className="cyber-subheading">Cobertura de cada modelo y selector</h3>
      <p className="section-description">Incluye entradas sin uso y sustituidas. «Modelo publicado» solo identifica la etiqueta del modelo; no demuestra equivalencia del proveedor, endpoint, configuración o harness. Un alias candidato no hereda un resultado del modelo publicado. El filtro de benchmark no cambia esta cobertura.</p>
      <div className="evidence-result-count" role="status">{number(coverage.length)} de {number(evidence.catalogCoverage.length)} selectores · página {safeCoveragePage + 1} de {coveragePages}</div>
      {coverage.length ? <><div className="table-wrap" role="region" aria-label="Correspondencias de ciberseguridad; desplaza horizontalmente para consultar todas las columnas" tabIndex={0}><table className="cyber-coverage-table"><caption className="sr-only">Cobertura por modelo y selector, sin eficacia de ruta establecida</caption><thead><tr><th>Modelo / selector</th><th>Estado y alcance</th><th>Publicaciones vinculadas</th></tr></thead><tbody>{coverage.slice(safeCoveragePage * PAGE_SIZE, (safeCoveragePage + 1) * PAGE_SIZE).map(row => {
        const model = snapshot.catalog[row.catalogKey]
        return <tr key={row.catalogKey} data-catalog-key={row.catalogKey}><th scope="row"><strong>{model.name}</strong><code>{model.selector}</code><span className="muted-text">{row.catalogKey} · {model.pool}</span></th><td><span className={`tag ${row.state === 'no-mapped-result' || row.state === 'candidate-alias-only' ? 'cyber-gap' : ''}`}>{STATE_LABELS[row.state]}</span><p>{row.reason}</p></td><td>{row.resultIds.length ? <details className="method-details"><summary>{number(row.resultIds.length)} resultados · ver etiquetas originales</summary><ul className="cyber-publications">{row.resultIds.map(id => {
          const result = resultsById.get(id)!
          const match = result.catalogMatches.find(item => item.catalogKey === row.catalogKey)!
          return <li key={id}><strong>{result.publishedModel}</strong> · {result.benchmark} · {TYPE_LABELS[result.resultType]}<p>{match.relationship === 'candidate-alias' ? 'Alias candidato · no identidad confirmada' : 'Etiqueta del modelo publicado'}: {match.reason}</p></li>
        })}</ul></details> : <span className="missing-value">No disponible · no es cero</span>}</td></tr>
      })}</tbody></table></div><div className="pagination evidence-pagination"><button className="icon-button" aria-label="Página anterior de selectores de ciberseguridad" disabled={safeCoveragePage === 0} onClick={() => setCoveragePage(safeCoveragePage - 1)}><ArrowLeft size={17} /></button><span>Página {safeCoveragePage + 1} de {coveragePages}</span><button className="icon-button" aria-label="Página siguiente de selectores de ciberseguridad" disabled={safeCoveragePage >= coveragePages - 1} onClick={() => setCoveragePage(safeCoveragePage + 1)}><ArrowRight size={17} /></button></div></> : <div className="empty-state"><h3>No hay selectores para esta consulta.</h3><p>Elimina el texto de búsqueda o selecciona todo el catálogo. La ausencia en este filtro no es un resultado medido.</p></div>}
      <h3 className="cyber-subheading">Valores publicados · protocolos separados</h3>
      <div className="evidence-result-count" role="status">{number(results.length)} de {number(evidence.results.length)} resultados · página {safeResultPage + 1} de {resultPages}</div>
      {results.length ? <><div className="table-wrap" role="region" aria-label="Resultados de ciberseguridad; desplaza horizontalmente para consultar todas las columnas" tabIndex={0}><table className="benchmark-table cyber-results-table"><caption className="sr-only">Resultados originales; escalas y protocolos no intercambiables</caption><thead><tr><th>Etiqueta publicada / benchmark</th><th>Valor publicado</th><th>Fuente y correspondencia</th></tr></thead><tbody>{results.slice(safeResultPage * PAGE_SIZE, (safeResultPage + 1) * PAGE_SIZE).map(row => <tr key={row.id} id={`cyber-result-${row.id}`} tabIndex={-1} data-result-id={row.id}>
        <td><strong>{row.publishedModel}</strong><span className="benchmark-name">{row.benchmark}</span><span className="benchmark-name">Versión: {row.benchmarkVersion ?? 'No declarada'}</span><span className="tag">{TYPE_LABELS[row.resultType]}</span></td>
        <td className="benchmark-value"><strong>{decimal(row.value)}</strong><span>{row.unit}</span>{row.limitations.filter(limitation => /±|uncertainty|incertidumbre/i.test(limitation)).map((limitation, index) => <span key={index}>{limitation}</span>)}{row.resultType === 'editorial' && <span className="missing-value">Puntuación editorial · no tasa de éxito ni benchmark de eficacia</span>}<span className="benchmark-date">Evaluación: {row.evaluationDate ?? 'No declarada'}</span><span>Captura: {row.captureDate}</span><span>Denominador: {row.taskDenominator === null ? 'No declarado' : number(row.taskDenominator)}</span><span>Presupuesto de intentos: {row.attemptBudget ?? 'No declarado'}</span></td>
        <td><a className="source-link" href={row.sourceUrl} target="_blank" rel="noreferrer">Consultar fuente {row.sourceId}<ExternalLink size={13} /><span className="sr-only"> de {row.publishedModel}, {row.benchmark}; abre una nueva pestaña</span></a><span className="provenance-type">Artefacto / localizador: <code>{row.provenance}</code></span>
          <details className="method-details"><summary>Configuración exacta, correspondencias y límites</summary><dl className="cyber-settings"><div><dt>Esfuerzo publicado</dt><dd>{row.effort}</dd></div><div><dt>Configuración / protocolo declarado</dt><dd>{row.settings}</dd></div></dl>
            {row.catalogMatches.length ? <ul className="cyber-publications">{row.catalogMatches.map(match => <li key={match.catalogKey}><code>{snapshot.catalog[match.catalogKey].selector}</code><p><strong>{match.relationship === 'candidate-alias' ? 'Alias candidato · identidad no resuelta' : 'Correspondencia de etiqueta publicada · no de ruta'}</strong> · {match.reason}</p></li>)}</ul> : <p>No corresponde a ninguna entrada del catálogo; se conserva la publicación original sin trasladar versiones.</p>}
            <ul className="cyber-publications">{row.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul><p><strong>Validación de ruta: no establecida.</strong> No calibra las estrategias, perfiles ni cuotas de este dashboard.</p><p className="source-url">{row.sourceUrl}</p>
          </details>
        </td>
      </tr>)}</tbody></table></div><div className="pagination evidence-pagination"><button className="icon-button" aria-label="Página anterior de resultados de ciberseguridad" disabled={safeResultPage === 0} onClick={() => setResultPage(safeResultPage - 1)}><ArrowLeft size={17} /></button><span>Página {safeResultPage + 1} de {resultPages}</span><button className="icon-button" aria-label="Página siguiente de resultados de ciberseguridad" disabled={safeResultPage >= resultPages - 1} onClick={() => setResultPage(safeResultPage + 1)}><ArrowRight size={17} /></button></div></> : <div className="empty-state"><h3>No hay resultados publicados en este alcance.</h3><p>No se infiere un cero ni ausencia universal de evidencia. Consulta el estado del selector y amplía los filtros; los alias o las fuentes de contexto no son mediciones de esa ruta.</p><button className="text-button" onClick={() => { setQuery(''); setSelector(''); setBenchmark(''); setCoveragePage(0); setResultPage(0) }}>Restablecer filtros de ciberseguridad</button></div>}
    </>}
  </section>
}
