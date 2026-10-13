import ParticipationExplorer from './ParticipationExplorer'
import { participationRows, scopedParticipation, groupParticipation, DEFAULT_STAT_SCOPE } from './participationStats'
import { portfolioLabel } from './presentation'
import { useMemo, useState } from 'react'
import { ArrowRight, ArrowUpRight, GitBranch, Layers3, ScanLine, Wallet, BookOpen, ShieldCheck } from 'lucide-react'
import { DOMAINS, decimal, monthly, number, percent, tally } from './data'
import type { Snapshot } from './data'

interface Props { snapshot: Snapshot; onProfiles: (query?: string, portfolio?: string, domain?: string, profileId?: string) => void; onEvidence: () => void }
export default function Overview({ snapshot, onProfiles, onEvidence }: Props) {
  const [domain, setDomain] = useState('')
  const [allBudgets, setAllBudgets] = useState(false)
  const [statistics,setStatistics]=useState<{domain:string;model:string|null}|null>(null)
  const allRows=useMemo(()=>participationRows(snapshot),[snapshot])
  const summary = useMemo(() => {
    const pids = Object.keys(snapshot.meta).filter(pid => !domain || snapshot.meta[pid].domain === domain)
    const assignments = scopedParticipation(allRows,{...DEFAULT_STAT_SCOPE,domain})
    const slots = scopedParticipation(allRows,{...DEFAULT_STAT_SCOPE,domain,state:'all'}).length
    return { profiles: pids.length, assignments: assignments.length, slots,
      portfolios: new Set(pids.map(pid => snapshot.meta[pid].portfolio)).size,
      models: groupParticipation(assignments,'model'), efforts: tally(assignments.map(row => row.effort || 'Sin especificar')) }
  }, [snapshot, domain, allRows])
  const budgets = useMemo(() => Object.entries(snapshot.portfolios).sort(([, a], [, b]) => Number(a.usd) - Number(b.usd) || Number(a.eur) - Number(b.eur) || a.label.localeCompare(b.label)), [snapshot])
  let usdMax = 0
  let eurMax = 0
  for (const [, portfolio] of budgets) {
    usdMax = Math.max(usdMax, Number(portfolio.usd))
    eurMax = Math.max(eurMax, Number(portfolio.eur))
  }
  const modelRows = summary.models.slice(0, 6)
  const others = summary.models.slice(6).reduce((total, item) => total + item.count, 0)
  const scope = domain ? DOMAINS[domain] : 'Todos los dominios'
  const domainContract = Object.hasOwn(snapshot.domainContracts, domain) ? snapshot.domainContracts[domain] : null
  return <>
    <section className="page-heading">
      <div><span className="eyebrow">EXPLORAR · COMPARAR · DECIDIR</span><h1>La configuración,<br />en perspectiva.</h1><p>Entiende qué modelos sostienen cada rol y encuentra el perfil<br className="desktop-break" /> adecuado antes de poner tus agentes a trabajar.</p></div>
      <div className="snapshot-stamp"><span className="stamp-icon"><Layers3 size={22} /></span><strong>Perfiles de referencia</strong><span>{snapshot.stats.session}</span><span className="status-tag"><span />Snapshot estático</span></div>
    </section>
    <section className="overview-scope" aria-label="Alcance del resumen"><div><span className="scope-dot" /><strong>Resumen de referencias</strong><span>No es actividad ni rendimiento en vivo</span></div><label>Dominio<select aria-label="Dominio del resumen" value={domain} onChange={e => setDomain(e.target.value)}><option value="">Todos los dominios</option>{Object.entries(DOMAINS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label></section>
    {domainContract && <section className="provenance-banner" aria-label="Contrato del dominio seleccionado"><ShieldCheck size={23} /><div><strong>Contrato del dominio · {domainContract.label}</strong><p><strong>Alcance:</strong> {domainContract.scope}</p><p><strong>Gate de verificación:</strong> {domainContract.gate}</p>{Object.hasOwn(domainContract, 'evidenceNote') && <p><strong>Límite de evidencia:</strong> {domainContract.evidenceNote}</p>}</div></section>}
    <section className="metric-strip" aria-label={`Métricas de configuración: ${scope}`}>
      {[{ label: 'Perfiles configurados', value: summary.profiles, detail: 'Combinaciones de portfolio, objetivo y harness', Icon: Layers3 },
        { label: 'Principales habilitados', value: summary.assignments, detail: `${number(summary.slots)} slots; ${number(summary.slots-summary.assignments)} deshabilitados excluidos`, Icon: GitBranch },
        { label: 'Modelos asignados', value: summary.models.length, detail: 'Identidades declaradas con asignación activa', Icon: ScanLine },
        { label: 'Portfolios disponibles', value: summary.portfolios, detail: 'Alternativas de suscripción, no gasto acumulado', Icon: Wallet }].map(({ label, value, detail, Icon }) => <div className="metric" key={label}><div className="metric-label">{label}<Icon size={17} /></div><strong>{number(value)}</strong><span>{detail}</span></div>)}
    </section>
    <div className="overview-grid">
      <section className="panel distribution"><div className="section-heading"><div><span className="eyebrow">DISTRIBUCIÓN</span><h2>Los modelos detrás de los roles</h2></div><span className="scope-label">{scope}</span></div><p className="section-description">Modelos principales de roles habilitados, agrupados por identidad declarada. Pulsa un modelo para ver dónde participa; no mide consumo ni calidad.</p>
        {summary.assignments ? <div className="bar-chart" aria-label="Distribución de asignaciones por modelo">{modelRows.map(({key:modelId,label:model,count:value}, index) => <button className="bar-row" key={modelId} onClick={() => setStatistics({domain,model:modelId})} aria-label={`Explorar ${model}: ${number(value)} asignaciones`}><div className="bar-caption"><span>{model}</span><strong>{number(value)} <small>{percent(value / summary.assignments)}</small></strong></div><div className="bar-track"><span className={index === 0 ? 'bar-fill primary' : 'bar-fill'} style={{ width: `${value / summary.assignments * 100}%` }} /></div></button>)}{others > 0 && <button type="button" className="bar-row other-models" onClick={()=>setStatistics({domain,model:null})} aria-label="Ver estadísticas de todos los modelos"><div className="bar-caption"><span>Otros {summary.models.length - 6} modelos</span><strong>{number(others)} <small>{percent(others / summary.assignments)}</small></strong></div><div className="bar-track"><span className="bar-fill muted" style={{ width: `${others / summary.assignments * 100}%` }} /></div></button>}</div> : <p className="empty-state">No hay asignaciones registradas para este dominio.</p>}
        <button type="button" className="secondary-button statistics-open" onClick={()=>setStatistics({domain,model:null})}>Ver estadísticas completas <ArrowRight size={16}/></button>
        <button className="text-button" onClick={() => onProfiles('', '', domain)}>Explorar perfiles de este alcance <ArrowRight size={16} /></button>
      </section>
      <section className="panel effort-panel"><div className="section-heading"><div><span className="eyebrow">RAZONAMIENTO</span><h2>Mezcla de esfuerzo</h2></div></div><p className="section-description">{scope} · {number(summary.assignments)} asignaciones. Niveles declarados, no consumo de tokens.</p><div className="effort-list">{summary.efforts.map(([effort, value], index) => <div className="effort-row" key={effort}><div><span className={`effort-dot effort-${index}`} /><strong>{effort}</strong><span>{number(value)}</span></div><div className="bar-track"><span className={`effort-fill effort-${index}`} style={{ width: `${value / summary.assignments * 100}%` }} /></div></div>)}</div><p className="footnote">«Sin especificar» conserva los campos vacíos de la fuente; no significa esfuerzo cero.</p></section>
    </div>
    <div className="overview-grid lower-grid">
      <section className="panel budget-panel"><div className="section-heading"><div><span className="eyebrow">PRESUPUESTO DE SUSCRIPCIÓN</span><h2>Un portfolio, dos monedas</h2></div><Wallet size={20} className="muted-text" /></div><p className="section-description">Alcance global · alternativas mensuales. USD y EUR se muestran por separado, sin conversión ni suma entre portfolios.</p><div className="table-wrap"><table className="budget-table"><caption className="sr-only">Precio mensual de cada portfolio; cada moneda tiene su propia escala desde cero.</caption><thead><tr><th>Portfolio</th><th>USD / mes</th><th>EUR / mes</th><th><span className="sr-only">Abrir perfiles</span></th></tr></thead><tbody>{(allBudgets ? budgets : budgets.slice(0, 6)).map(([id, portfolio]) => <tr key={id}><td>{portfolioLabel(portfolio)}</td><td><span className="budget-number">{decimal(Number(portfolio.usd))}</span><div className="budget-track"><span style={{ width: `${usdMax ? Number(portfolio.usd) / usdMax * 100 : 0}%` }} /></div></td><td><span className="budget-number">{decimal(Number(portfolio.eur))}</span><div className="budget-track eur"><span style={{ width: `${eurMax ? Number(portfolio.eur) / eurMax * 100 : 0}%` }} /></div></td><td><button className="icon-button" aria-label={`Ver perfiles de ${portfolioLabel(portfolio)}, ${monthly(portfolio)} al mes`} onClick={() => onProfiles('', id)}><ArrowUpRight size={17} /></button></td></tr>)}</tbody></table></div><div className="budget-footer"><button className="text-button" aria-expanded={allBudgets} onClick={() => setAllBudgets(!allBudgets)}>{allBudgets ? 'Mostrar menos' : `Ver los ${budgets.length} portfolios`}<ArrowRight size={16} /></button><span>Escalas: 0–{decimal(usdMax)} USD · 0–{decimal(eurMax)} EUR</span></div><p className="footnote">No incluye precios por token, costes por tarea ni gasto real.</p></section>
      <section className="evidence-callout"><span className="callout-icon"><BookOpen size={23} /></span><span className="eyebrow">DECIDIR CON CONTEXTO</span><h2>El resultado importa.<br />La fuente, también.</h2><p>Consulta la cobertura de evidencia y los benchmarks documentados. Una puntuación aislada no cuenta toda la historia.</p><div className="audit-receipt"><ShieldCheck size={19} /><div><strong>{number(snapshot.stats.validators.passed)} verificaciones registradas</strong><span>{number(snapshot.stats.validators.failed)} fallos · auditoría, no ejecución en vivo</span></div></div><button className="primary-button" onClick={onEvidence}>Consultar evidencia <ArrowRight size={17} /></button></section>
    </div>
    {statistics&&<ParticipationExplorer key={JSON.stringify(statistics)} snapshot={snapshot} initialDomain={statistics.domain} initialModel={statistics.model} onClose={()=>setStatistics(null)} onProfile={id=>{const meta=snapshot.meta[id];setStatistics(null);onProfiles('',meta.portfolio,meta.domain,id)}}/>}
  </>
}
