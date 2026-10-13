import { benchmarkQueryFor } from './benchmarkQuery'
import { axisNumber, extent, ticks, position } from './chartMath'
import { METRIC_LABELS, DIRECTION_LABELS } from './benchmarkTypes'
import { useId, useMemo, useState } from 'react'
import { ExternalLink, Info } from 'lucide-react'
import { DOMAINS, OBJECTIVES, monthly, number } from './data'
import type { Snapshot } from './data'
import { assignedModels, assignedLabel, rowMatchesModel, configuredRecord, finiteValue } from './modelInsightsData'
import type { AssignedModel, ExplorerRecord, InsightRecord, PairStatus } from './modelInsightsData'
import type { Preset } from './presetStrategies'

// Preserve the source's numeric precision, including small nonzero evaluation costs.
const metricNumber = new Intl.NumberFormat('es-ES', { maximumSignificantDigits: 17 }).format
const EMPTY_RECORDS:NonNullable<Snapshot['benchmarks']>=[]
const symbols = ['●', '■', '◆', '▲', '✚', '✕']
const pairingNotes: Record<PairStatus, string> = {
  paired: 'Misma fila de origen; coste asociado documentado.',
  missing: 'Sin coste asociado documentado; no equivale a cero.',
  ambiguous: 'Asociación ambigua: varias filas coinciden. No se emparejan.',
  'other-denomination': 'El coste asociado usa otra denominación; consulta su alcance en el selector.',
  unlinked: 'Coste independiente: no hay una asociación unívoca con un resultado.',
}
type Mode = 'paired' | 'performance' | 'cost'

function recordValue(record?: InsightRecord) {
  if (!record) return 'Sin registro'
  if (record.row.value === null) return 'No disponible'
  if (!Number.isFinite(record.row.value)) return 'Valor no finito; no representable'
  return `${metricNumber(record.row.value)} ${record.row.unit || 'Unidad no declarada'}`
}

function recordLabel(record: ExplorerRecord) {
  const row = (record.result || record.cost)!.row
  return `${row.model} · ${row.effort || 'Esfuerzo no declarado'} · rendimiento: ${recordValue(record.result)} · coste: ${recordValue(record.cost)}`
}


function SourceRecord({ record, title, snapshot }: { record: InsightRecord; title: string; snapshot: Snapshot }) {
  const { row, index, configured } = record
  const measurement = row.measurement
  const protocol = measurement ? snapshot.benchmarkRegistry?.protocols[measurement.protocolId] : null
  return <article className="insight-source-record">
    <h4>{title} · registro {index + 1}</h4>
    <p><strong>{recordValue(record)}</strong> · {row.model} · <span className="effort-tag">{row.effort || 'No declarado'}</span></p>
    <p>{configured ? 'Esfuerzo del perfil; resultado externo, no una ejecución de este perfil.' : 'Otro esfuerzo o esfuerzo no declarado; no representa esta configuración.'}</p>
    {measurement && <p><strong>{METRIC_LABELS[measurement.kind]}</strong> · {DIRECTION_LABELS[measurement.direction]} · {measurement.scope}. {measurement.issueIds.map(id => snapshot.benchmarkRegistry?.issues[id]?.label || id).join(' · ')}</p>}
    {protocol && <details><summary>Protocolo y fechas separados</summary><p>Captura: {protocol.capturedAt}. Evaluación: {protocol.evaluationDate || 'no declarada'}. Precio: {protocol.priceAsOf || 'no declarado'}.</p><p>Versión {protocol.version} · subconjunto {protocol.subset || 'no declarado'} · tareas {protocol.tasks ?? 'no declaradas'} · repeticiones {protocol.trialsPerTask ?? 'no declaradas'}.</p><p>Harness: {protocol.harness || 'no declarado'} · fallback del servicio: {protocol.serverFallback || 'no declarado'} · red: {protocol.network || 'no declarada'} · compaction: {protocol.compaction || 'no declarada'}.</p></details>}
    <dl>
      <div><dt>Benchmark · familia</dt><dd>{row.benchmark} · {row.family || 'No declarada'}</dd></div>
      <div><dt>Fecha del registro · método</dt><dd>{row.date || 'No declarada'} · {row.methodology || 'No declarado'}</dd></div>
      <div><dt>Fuente</dt><dd>{/^https?:\/\//i.test(row.source) ? <a className="source-link" href={row.source} target="_blank" rel="noreferrer">Consultar fuente <ExternalLink size={13} /><span className="sr-only"> de {row.model}, {row.benchmark}; abre una nueva pestaña</span></a> : row.source || 'No declarada'}<span className="source-url">{row.source}</span></dd></div>
      <div><dt>Procedencia exacta</dt><dd>{row.provenance || 'No declarada'}</dd></div>
      <div><dt>Notas originales y límites</dt><dd>{row.note || 'Sin nota adicional.'}</dd></div>
    </dl>
  </article>
}

interface ExplorerState {
  snapshot: Snapshot
  presetId: string
  includeOther: boolean
  includeHistorical?: boolean
  includeIssues?: boolean
  includeOperational?: boolean
  hidden: string[]
  groupId: string
  mode: Mode
  selected: string | null
  preview: string | null
}

export default function ModelInsights({ snapshot, preset }: { snapshot: Snapshot; preset: Preset }) {
  const [benchmarkSearch,setBenchmarkSearch]=useState('')
  const [focusRange,setFocusRange]=useState(false)
  const [exactOpen,setExactOpen]=useState(false)
  const [methodOpen,setMethodOpen]=useState(false)
  const [exactPage,setExactPage]=useState(0)
  const records=snapshot.benchmarks || EMPTY_RECORDS
  const query=useMemo(()=>benchmarkQueryFor(records),[records])
  const models = useMemo(() => assignedModels(snapshot, preset.routes), [snapshot, preset.routes])
  const presetId = preset.id
  const [stored, setState] = useState<ExplorerState>(() => ({ snapshot, presetId, includeOther: Boolean(snapshot.benchmarkRegistry), hidden: [], groupId: '', mode: 'paired', selected: null, preview: null }))
  // An imported snapshot or a different preset starts a new scope, never stale filters/details.
  const state: ExplorerState = stored.snapshot === snapshot && stored.presetId === presetId ? stored : { snapshot, presetId, includeOther: Boolean(snapshot.benchmarkRegistry), hidden: [], groupId: '', mode: 'paired', selected: null, preview: null }
  if (state !== stored) setState(state)
  const groups = useMemo(() => query.groups(models, state.includeOther, {includeHistorical:state.includeHistorical,includeIssues:state.includeIssues,includeOperational:state.includeOperational}), [query, models, state.includeOther, state.includeHistorical, state.includeIssues, state.includeOperational])
  const group = groups.find(item => item.id === state.groupId) || groups.find(item => item.records.some(record => finiteValue(record.result) && finiteValue(record.cost))) || groups[0]
  const context = group?.resultGroup || group?.costGroup
  const hasPair = group?.records.some(record => finiteValue(record.result) && finiteValue(record.cost)) || false
  const mode: Mode = state.mode === 'paired' && !hasPair ? group?.resultGroup ? 'performance' : 'cost' : state.mode
  const visible = group?.records.filter(record => !state.hidden.includes(assignedLabel((record.result || record.cost)!.row, models))) || []
  const plotted = visible.filter(record => mode === 'paired' ? finiteValue(record.result) && finiteValue(record.cost) : finiteValue(mode === 'cost' ? record.cost : record.result))
  const selected = visible.find(record => record.id === state.selected)
  const preview = visible.find(record => record.id === state.preview) || selected
  // Keep a common axis when hiding a model; only an explicit range control zooms.
  const scopeRecords=group?.records.filter(r=>mode==='paired'?finiteValue(r.result)&&finiteValue(r.cost):finiteValue(mode==='cost'?r.cost:r.result))||[]
  const resultDomain = extent(scopeRecords.map(r=>r.result?.row.value),!focusRange)
  const costDomain = extent(scopeRecords.map(r=>r.cost?.row.value),!focusRange)
  const domain = mode === 'cost' ? costDomain : resultDomain
  const unit = mode === 'cost' ? group?.costUnit : group?.resultGroup?.unit
  const meta = preset.meta
  const portfolio = snapshot.portfolios[preset.portfolio]
  const id = useId()
  const clearSelection = { selected: null, preview: null }
  const optionNeedle=benchmarkSearch.trim().toLocaleLowerCase('es')
  const matchingOptions=groups.filter(g=>[g.benchmark,g.resultGroup?.methodology,g.costGroup?.methodology].join(' ').toLocaleLowerCase('es').includes(optionNeedle))
  const options=group&&!matchingOptions.includes(group)?[group,...matchingOptions]:matchingOptions
  const exactPages=Math.max(1,Math.ceil(visible.length/30)),safeExactPage=Math.min(exactPage,exactPages-1)
  const duplicates=mode==='paired'?plotted.length-new Set(plotted.map(r=>JSON.stringify([r.cost!.row.value,r.result!.row.value]))).size:0
  const pointEvents = (record: ExplorerRecord) => ({
    onMouseEnter: () => setState({ ...state, preview: record.id }),
    onMouseLeave: () => setState({ ...state, preview: null }),
    onFocus: () => setState({ ...state, preview: record.id }),
    onBlur: () => setState({ ...state, preview: null }),
    onClick: () => setState({ ...state, selected: record.id, preview: record.id }),
  })

  return <section className="panel model-insights" aria-labelledby={`${id}-title`} data-testid="model-insights">
    <div className="section-heading"><h2 id={`${id}-title`}>Explorar resultados y costes</h2><a className="text-button" href="#evidence">Ver Evidencia</a></div>
    <p className="section-description">Resultados externos, no de este perfil. Selecciona un punto para ver sus fuentes.</p>
    <div className="insight-explorer-controls">
      <label>Buscar benchmark<input type="search" aria-label="Buscar benchmark para gráfico" placeholder="Nombre o método…" value={benchmarkSearch} onChange={e=>setBenchmarkSearch(e.target.value)}/></label>
      <label htmlFor={`${id}-benchmark`}>Benchmark y contexto
        <select aria-label="Benchmark y contexto" id={`${id}-benchmark`} data-insight-control="benchmark" value={group?.id || ''} disabled={!groups.length} onChange={event => setState({ ...state, groupId: event.target.value, ...clearSelection })}>
          {!groups.length && <option value="">Sin registros en este alcance</option>}
          {options.map(item => {
            const scope = item.resultGroup || item.costGroup!
            return <option key={item.id} value={item.id}>{item.benchmark} · {scope.unit || 'Unidad no declarada'}{item.resultGroup && item.costUnit ? ` × ${item.costUnit}` : ''} · {scope.date || 'Fecha no declarada'}{scope.comparable ? '' : ` · registro ${scope.records[0].index + 1}`}</option>
          })}
        </select>
      </label>
      <label htmlFor={`${id}-mode`}>Vista
        <select aria-label="Vista" id={`${id}-mode`} data-insight-control="mode" value={state.mode} onChange={event => setState({ ...state, mode: event.target.value as Mode, ...clearSelection })}>
          <option value="paired">Rendimiento y coste</option><option value="performance">Rendimiento</option><option value="cost">Coste</option>
        </select>
      </label>
    </div>
    <div className="chart-toolbar"><label className="chart-range"><input type="checkbox" checked={focusRange} onChange={e=>setFocusRange(e.target.checked)}/> Ampliar al rango observado (puede excluir cero)</label><span className="footnote">{matchingOptions.length} coincidencias de contexto{optionNeedle&&!matchingOptions.length?'; se conserva el contexto seleccionado':''} · las etiquetas de ejes son abreviadas; las fuentes conservan precisión completa.</span></div>
    <div className="insight-controls">
      <label><input data-insight-control="other-efforts" type="checkbox" checked={state.includeOther} onChange={event => setState({ ...state, includeOther: event.target.checked, groupId: '', ...clearSelection })} />Incluir otros esfuerzos publicados o no declarados</label>
      {state.includeOther && <p className="footnote" role="status">Referencias ampliadas: los otros esfuerzos no representan esta configuración.</p>}
    </div>
    {snapshot.benchmarkRegistry && <div className="insight-controls typed-controls">
      <label><input type="checkbox" checked={state.includeHistorical || false} onChange={e => setState({ ...state, includeHistorical:e.target.checked, groupId:'', ...clearSelection })} />Incluir capturas históricas y sustituidas</label>
      <label><input type="checkbox" checked={state.includeIssues || false} onChange={e => setState({ ...state, includeIssues:e.target.checked, groupId:'', ...clearSelection })} />Mostrar evidencia con incidencias o protocolo incompleto</label>
      <label><input type="checkbox" checked={state.includeOperational || false} onChange={e => setState({ ...state, includeOperational:e.target.checked, groupId:'', ...clearSelection })} />Incluir métricas operativas y de error (no capacidad)</label>
      <p className="footnote">La identidad enlazada es la del modelo publicado. No acredita su comportamiento a través de NaN, ChatGPT ni otros gateways. Las variantes candidatas no se equiparan automáticamente.</p>
    </div>}
    <fieldset className="insight-legend"><legend><span>Modelos visibles · comparación</span><button type="button" className="text-button insight-reset" data-insight-control="reset" onClick={() => setState({ ...state, includeOther: Boolean(snapshot.benchmarkRegistry), hidden: [], groupId: '', mode: 'paired', ...clearSelection })}>Restablecer</button></legend>
      <div className="insight-legend-actions">{models.map((model, index) => <button type="button" key={model.model} className={`chip insight-model-toggle ${state.hidden.includes(model.model) ? '' : 'active'}`} data-insight-model={model.model} aria-pressed={!state.hidden.includes(model.model)} onClick={() => setState({ ...state, hidden: state.hidden.includes(model.model) ? state.hidden.filter(name => name !== model.model) : [...state.hidden, model.model], ...clearSelection })}>
        <span className={`insight-symbol tone-${index % 6}`} aria-hidden="true">{symbols[index % symbols.length]}</span>{model.model}{state.hidden.includes(model.model) && <span className="insight-visibility">Oculto</span>}
      </button>)}</div>
      {state.hidden.length > 0 && <p className="footnote" role="status">{number(state.hidden.length)} modelos ocultos; el enrutamiento del perfil no cambia.</p>}
    </fieldset>

    {group && context ? <>
      <div className="insight-plot-heading"><h3>{group.benchmark}</h3><span>{context.date || 'Fecha no declarada'} · {context.methodology || 'Método no declarado'}</span></div>
      {context.records[0]?.row.measurement && <p className="insight-context">{METRIC_LABELS[context.records[0].row.measurement.kind]} · {DIRECTION_LABELS[context.records[0].row.measurement.direction]} · incidencias: {context.records[0].row.measurement.issueIds.join(', ') || 'ninguna registrada'}. Consultar protocolo; no es una clasificación global.</p>}
      {!context.comparable && <p className="insight-context">Registro aislado: falta método, fecha o unidad comparable.</p>}
      {state.mode === 'paired' && !hasPair && <p className="insight-notice" role="status" data-insight-state="unpaired">No hay pares numéricos unívocos en este alcance. Se muestra {mode === 'cost' ? 'el coste independiente' : 'el rendimiento sin eje de coste'}; no se infieren valores. Cambia la vista o el benchmark para explorar los registros disponibles.</p>}
      {(group.costUnit === 'USD (base no declarada)' && mode !== 'performance') && <p className="insight-notice">USD (base no declarada): sin base de facturación; no es coste por tarea/test ni suscripción.</p>}
      <div className="insight-plot-surface">{!plotted.length ? <div className="insight-empty" role="status" data-insight-state="empty-plot"><strong>{!visible.length ? 'No hay registros visibles.' : 'No hay valores numéricos representables en esta vista.'}</strong><p>{state.hidden.length ? 'Hay modelos ocultos. Vuelve a mostrarlos o restablece la vista.' : 'Los registros ausentes o no finitos no se dibujan como cero. Consulta los valores exactos, cambia de vista o amplía el alcance de esfuerzo.'}</p></div> : mode === 'paired' ? <figure className="insight-figure" aria-label={`${group.benchmark}: coste de evaluación frente a rendimiento`}>
        <figcaption className="insight-axis-title">Y · Rendimiento · {group.resultGroup?.unit || 'Unidad no declarada'}</figcaption>
        <div className="insight-scatter-layout">
          <div className="insight-y-ticks" aria-hidden="true">{ticks(resultDomain).map((value,i)=><span key={i} style={{top:`${100-position(value,resultDomain)}%`}} title={metricNumber(value)}>{axisNumber(value)}</span>)}</div>
          <div className="insight-scatter" data-insight-plot="paired">
            <svg className="insight-grid" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" focusable="false">
              {[4,27,50,73,96].map(tick => <g key={tick}><line x1="4" x2="96" y1={tick} y2={tick} /><line x1={tick} x2={tick} y1="4" y2="96" /></g>)}
              {costDomain.min<=0&&costDomain.max>=0&&<line className="insight-zero" x1={position(0, costDomain)} x2={position(0, costDomain)} y1="4" y2="96" />}{resultDomain.min<=0&&resultDomain.max>=0&&<line className="insight-zero" x1="4" x2="96" y1={100 - position(0, resultDomain)} y2={100 - position(0, resultDomain)} />}
            </svg>
            {plotted.map(record => {
              const modelIndex = models.findIndex(model => rowMatchesModel(record.result!.row, model))
              return <button type="button" key={record.id} className={`insight-point tone-${modelIndex % 6} ${record.id === selected?.id ? 'selected' : ''}`} data-insight-record={record.id} style={{ left: `${position(record.cost!.row.value!, costDomain)}%`, top: `${100 - position(record.result!.row.value!, resultDomain)}%` }} aria-label={recordLabel(record)} aria-pressed={record.id === selected?.id} aria-controls={`${id}-selection`} title={recordLabel(record)} {...pointEvents(record)}><span aria-hidden="true">{symbols[modelIndex % symbols.length]}</span></button>
            })}
          </div>
          <div className="insight-x-ticks" aria-hidden="true">{ticks(costDomain).map((value,i)=><span key={i} style={{left:`${position(value,costDomain)}%`}} title={metricNumber(value)}>{axisNumber(value)}</span>)}</div>
        </div>
        <p className="insight-axis-title insight-x-title">X · Coste de evaluación · {group.costUnit}</p>
        <p className="footnote">Escalas lineales · {focusRange?'rango observado ampliado; revisa los ejes':'referencia cero'}. Ocultar un modelo no cambia la escala. Cada punto es una fila, sin promedios ni ranking. Los puntos coincidentes no se desplazan; usa la tabla para seleccionar cada registro.</p>
      </figure> : <figure className="insight-figure" aria-label={`${group.benchmark}: ${mode === 'cost' ? 'coste de evaluación' : 'rendimiento'}`}>
        <figcaption className="insight-axis-title">{mode === 'cost' ? 'Coste de evaluación' : 'Rendimiento'} · {unit || 'Unidad no declarada'} · {focusRange?'rango observado':'referencia cero'}</figcaption>
        <div className="insight-single-plot" data-insight-plot={mode}>
          <div className="insight-single-scale" aria-hidden="true"><span>{axisNumber(domain.min)}</span><span>{domain.min === domain.max ? 'Valor único' : axisNumber(domain.min / 2 + domain.max / 2)}</span><span>{axisNumber(domain.max)}</span></div>
          {plotted.map(record => {
            const row = (mode === 'cost' ? record.cost : record.result)!.row
            const modelIndex = models.findIndex(model => rowMatchesModel(row, model))
            return <div className="insight-single-row" key={record.id}>
              <div className="insight-single-caption"><span>{row.model} <span className="effort-tag">{row.effort || 'No declarado'}</span></span><strong>{recordValue(mode === 'cost' ? record.cost : record.result)}</strong></div>
              <div className="insight-single-track">{domain.min<=0&&domain.max>=0&&<span className="insight-single-zero" style={{ left: `${position(0, domain)}%` }} aria-hidden="true" />}<button type="button" className={`insight-point tone-${modelIndex % 6} ${record.id === selected?.id ? 'selected' : ''}`} data-insight-record={record.id} style={{ left: `${position(row.value!, domain)}%`, top: '50%' }} aria-label={recordLabel(record)} aria-pressed={record.id === selected?.id} aria-controls={`${id}-selection`} title={recordLabel(record)} {...pointEvents(record)}><span aria-hidden="true">{symbols[modelIndex % symbols.length]}</span></button></div>
            </div>
          })}
        </div>
      </figure>}
      {preview && <div className="insight-preview" role="status" aria-live="polite" data-insight-preview><strong>{(preview.result || preview.cost)!.row.model}</strong><span className="effort-tag">{(preview.result || preview.cost)!.row.effort || 'No declarado'}</span><span>Rendimiento: {recordValue(preview.result)}</span><span>Coste: {recordValue(preview.cost)}</span></div>}</div>
      {!!duplicates&&<p className="insight-notice">{duplicates} registros comparten coordenadas exactas. No se desplazan ni se promedian: selecciona cada registro con la tabla o el navegador de puntos.</p>}
      {!!visible.length&&<div className="point-navigator"><label>Navegar todos los registros<select aria-label="Seleccionar registro del gráfico" value={selected?.id||''} onChange={e=>setState({...state,selected:e.target.value||null,preview:e.target.value||null})}><option value="">Seleccionar un registro…</option>{visible.map(r=><option key={r.id} value={r.id}>{(r.result||r.cost)!.row.model} · {(r.result||r.cost)!.row.effort||'No declarado'} · registro {(r.result||r.cost)!.index+1}</option>)}</select></label><span>{plotted.length} puntos numéricos / {visible.length} registros · sin imputación</span></div>}
      {visible.length > plotted.length && <p className="insight-missing">{number(visible.length - plotted.length)} registros visibles no se dibujan en esta vista por falta de valores numéricos{mode === 'paired' ? ' o de una asociación unívoca de coste' : ''}. Se conservan en la tabla; no son ceros.</p>}
      <div id={`${id}-selection`} className={selected ? 'insight-selection' : ''} data-insight-details aria-live="polite">
        {selected && <><div className="insight-selection-heading"><h3>{(selected.result || selected.cost)!.row.model} · {(selected.result || selected.cost)!.row.effort || 'No declarado'}</h3><button type="button" className="text-button" onClick={() => setState({ ...state, ...clearSelection })}>Cerrar detalle</button></div><p className="insight-context">{pairingNotes[selected.pairStatus]}</p><div className="insight-source-grid">{selected.result && <SourceRecord record={selected.result} title="Resultado" snapshot={snapshot} />}{selected.cost && <SourceRecord record={selected.cost} title="Coste de evaluación" snapshot={snapshot} />}</div></>}
      </div>
      <details className="insight-exact-values" open={exactOpen} onToggle={e=>setExactOpen(e.currentTarget.open)}><summary>Valores exactos y selección accesible · {number(visible.length)} registros visibles</summary>{exactOpen&&<><div className="pagination"><button disabled={!safeExactPage} onClick={()=>setExactPage(safeExactPage-1)}>Anterior</button><span>Todos los registros · página {safeExactPage+1} de {exactPages} · hasta 30 por página</span><button disabled={safeExactPage>=exactPages-1} onClick={()=>setExactPage(safeExactPage+1)}>Siguiente</button></div><div className="table-wrap" tabIndex={0} role="region" aria-label="Valores exactos de los registros visibles">
        <table className="insight-table"><caption className="sr-only">{group.benchmark} · {context.methodology || 'Método no declarado'} · {context.date || 'Fecha no declarada'}. Sin combinar filas ni imputar valores.</caption><thead><tr><th scope="col">Modelo · esfuerzo</th><th scope="col">Rendimiento</th><th scope="col">Coste de evaluación</th><th scope="col">Asociación y alcance</th></tr></thead><tbody>{visible.slice(safeExactPage*30,(safeExactPage+1)*30).map(record => {
          const row = (record.result || record.cost)!.row
          return <tr key={record.id} className={record.id === selected?.id ? 'selected' : ''}><th scope="row"><button type="button" className="model-button" data-insight-table-record={record.id} aria-pressed={record.id === selected?.id} aria-controls={`${id}-selection`} onClick={() => setState({ ...state, selected: record.id, preview: record.id })}>{row.model} · {row.effort || 'No declarado'}<span className="sr-only"> · registro {(record.result || record.cost)!.index + 1}; consultar fuentes</span></button></th><td>{recordValue(record.result)}</td><td>{recordValue(record.cost)}</td><td>{pairingNotes[record.pairStatus]} {(record.result || record.cost)!.configured ? 'Esfuerzo del perfil; referencia externa.' : 'Otro esfuerzo o no declarado.'}</td></tr>
        })}</tbody></table>
      </div></>}</details>
      <details className="insight-coverage"><summary>Cobertura del benchmark y esfuerzos del perfil</summary><ul className="insight-missing">{models.map(model => <li key={model.model}><strong>{model.model}</strong> · configurados: {model.efforts.map(effort => effort || 'No declarado').join(', ')}. {group.records.some(record => rowMatchesModel((record.result || record.cost)!.row, model)) ? 'Con registros en este alcance.' : 'Sin registro para este benchmark, unidad, método, fecha y alcance de esfuerzo; no implica un resultado de cero.'}</li>)}</ul></details>
    </> : <div className="insight-empty" role="status" data-insight-state="no-records"><strong>{models.length ? 'Sin resultados comparables para las identidades, esfuerzos y controles seleccionados.' : 'Este perfil no contiene asignaciones de modelos.'}</strong><p>No se infieren equivalencias de variantes ni valores. Las referencias históricas o problemáticas requieren activar su control. {models.length > 0 && !state.includeOther && 'Puedes incluir otros esfuerzos publicados con el control superior.'} <a href="#evidence">Consultar fuentes y cobertura en Evidencia</a>.</p></div>}
    <details className="insight-methodology" open={methodOpen} onToggle={e=>setMethodOpen(e.currentTarget.open)}><summary><Info size={18} aria-hidden="true" /> Contexto del perfil y límites de comparación</summary>
      <p>{[portfolio?.label, DOMAINS[meta?.domain] || meta?.domain, OBJECTIVES[meta?.objective] || meta?.objective, meta?.harness].filter(Boolean).join(' · ')}. Suscripciones: {portfolio ? monthly(portfolio) : 'Total no disponible'} / mes; cuotas separadas de los costes de evaluación, sin conversión ni reparto entre modelos.</p>
      <ul className="insight-scope" aria-label="Modelos y esfuerzos del perfil">{methodOpen&&models.map(model => <ScopeModel key={model.model} model={model} records={query.matching(model)} models={models} />)}</ul>
      <p>Datos estáticos con la fecha de cada fuente. Identidades publicadas enlazadas explícitamente y esfuerzos declarados; un esfuerzo no declarado no equivale a uno específico. No se añaden estimaciones, ranking global ni puntuación calidad/coste.</p>
      <p>Se comparan benchmark, unidad, método y fecha declarados; esto no verifica metodologías equivalentes. Sin método, fecha o unidad, cada registro queda aislado. Los pares requieren un registro de evaluación, protocolo, modelo, esfuerzo y denominación comunes; una fila de coste puede respaldar distintas métricas del mismo ensayo, pero no sumar pruebas independientes; no basta compartir modelo o fuente. Consulta las notas originales para aproximaciones, incertidumbre y límites.</p>
    </details>
  </section>
}

function ScopeModel({ model, records, models }: { model: AssignedModel; records: Snapshot['benchmarks']; models: AssignedModel[] }) {
  const matchingName = (records || []).filter(row => rowMatchesModel(row, model))
  const matchingEffort = matchingName.filter(row => configuredRecord(row, models))
  return <li><strong>{model.model}</strong><span> · esfuerzos: {model.efforts.map(effort => effort || 'No declarado').join(', ')} · {number(model.roles.length)} roles</span><span className="muted-text">{!matchingName.length ? 'Sin evidencia para este nombre.' : !matchingEffort.length ? 'Sin registros de los esfuerzos configurados.' : `${number(matchingEffort.length)} registros con esfuerzo del perfil.`}</span></li>
}
