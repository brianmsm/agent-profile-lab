import {useEffect,useMemo,useRef,useState} from 'react'
import {ArrowLeft,ArrowRight,Download,X} from 'lucide-react'
import type {Snapshot} from './data'
import {DOMAINS,OBJECTIVES,number,percent} from './data'
import {POOL_LABELS,poolLabel,portfolioLabel} from './presentation'
import {DEFAULT_STAT_SCOPE,participationRows,scopedParticipation,groupParticipation,modelParticipationProfiles,matchesStatisticsMeta,statisticsCsv} from './participationStats'
import type {StatisticsScope,StatDimension} from './participationStats'
import {downloadFile} from './snapshotIO'

interface Props {snapshot:Snapshot;initialDomain:string;initialModel:string|null;onClose:()=>void;onProfile:(profileId:string)=>void}
const DIMENSIONS:Record<StatDimension,string>={model:'Modelo',pool:'Proveedor / vía de acceso',role:'Rol',harness:'Harness',domain:'Dominio',effort:'Esfuerzo declarado'}
const KIND_LABELS={primary:'Principales',fallback:'Reservas',accelerator:'Aceleradores'}
export default function ParticipationExplorer({snapshot,initialDomain,initialModel,onClose,onProfile}:Props){
  const dialogRef=useRef<HTMLDialogElement>(null),modelHeading=useRef<HTMLHeadingElement>(null)
  const [scope,setScope]=useState<StatisticsScope>({...DEFAULT_STAT_SCOPE,domain:initialDomain})
  const [dimension,setDimension]=useState<StatDimension>('model'),[model,setModel]=useState<string|null>(initialModel)
  const [limit,setLimit]=useState('10'),[order,setOrder]=useState<'count'|'share'>('count'),[query,setQuery]=useState(''),[zero,setZero]=useState(true)
  const [breakdownsOpen,setBreakdownsOpen]=useState(false)
  const [windowPage,setWindowPage]=useState({key:'',page:0})
  const rows=useMemo(()=>participationRows(snapshot),[snapshot])
  const scoped=useMemo(()=>scopedParticipation(rows,scope),[rows,scope])
  const groups=useMemo(()=>groupParticipation(scoped,dimension,snapshot,zero),[scoped,dimension,snapshot,zero])
  const displayGroups=useMemo(()=>groups.filter(g=>(g.label+' '+g.key).toLocaleLowerCase('es').includes(query.toLocaleLowerCase('es'))),[groups,query])
  const modelGroup=useMemo(()=>model?groupParticipation(scoped,'model',snapshot,true).find(g=>g.key===model):null,[scoped,snapshot,model])
  const matching=useMemo(()=>model?scoped.filter(r=>r.modelId===model):[],[scoped,model])
  const top=useMemo(()=>model?modelParticipationProfiles(scoped,model,order):[],[scoped,model,order])
  const filteredTop=top.filter(p=>[p.profileId,portfolioLabel(snapshot.portfolios[snapshot.meta[p.profileId].portfolio]),...p.roles].join(' ').toLocaleLowerCase('es').includes(query.toLocaleLowerCase('es')))
  const windowKey=JSON.stringify([scope,model,order,query,limit])
  const windowSize=limit==='all'?50:Number(limit),windowPages=limit==='all'?Math.max(1,Math.ceil(filteredTop.length/windowSize)):1
  const currentWindow=Math.min(windowPage.key===windowKey?windowPage.page:0,windowPages-1)
  const pageRows=filteredTop.slice(currentWindow*windowSize,(currentWindow+1)*windowSize)
  const profilesInScope=Object.values(snapshot.meta).filter(m=>matchesStatisticsMeta(m,scope)).length
  const counts=useMemo(()=>Object.fromEntries((['primary','fallback','accelerator'] as const).map(kind=>[kind,scopedParticipation(rows,{...scope,kind}).length])),[rows,scope])
  useEffect(()=>{
    const d=dialogRef.current,trigger=document.activeElement as HTMLElement|null
    if(d&&!d.open)d.showModal()
    return ()=>{if(d?.open)d.close();if(trigger?.isConnected)trigger.focus({preventScroll:true})}
  },[])
  const changeScope=(patch:Partial<StatisticsScope>)=>{setScope({...scope,...patch});setLimit('10');setQuery('')}
  const selectModel=(id:string)=>{setModel(id);setLimit('10');setQuery('');requestAnimationFrame(()=>{modelHeading.current?.focus({preventScroll:true});modelHeading.current?.scrollIntoView({block:'nearest'})})}
  const returnGeneral=()=>{setModel(null);setQuery('');setLimit('10')}
  const label=(key:string,text:string)=>dimension==='pool'?poolLabel(key):dimension==='domain'?DOMAINS[key]||text:text
  return <dialog ref={dialogRef} className="statistics-dialog" aria-labelledby="statistics-title" onCancel={e=>{e.preventDefault();onClose()}}>
    <div className="statistics-dialog-header"><div><span className="eyebrow">PARTICIPACIÓN CONFIGURADA · NO CONSUMO</span><h2 id="statistics-title">Estadísticas completas de referencias</h2></div><button type="button" className="icon-button" aria-label="Cerrar estadísticas" onClick={onClose}><X size={21}/></button></div>
    <div className="statistics-body">
      <p>Se cuentan las asignaciones de los perfiles de referencia, no la frecuencia real de uso, tokens ni resultados. Las candidatas de complejidad de la vista Perfiles no se suman a estas cifras. Cada combinación de inventario, dominio y objetivo cuenta por separado, aunque tenga rutas equivalentes.</p>
      <div className="statistics-filters">
        <label>Dominio<select aria-label="Dominio de estadísticas" value={scope.domain} onChange={e=>changeScope({domain:e.target.value})}><option value="">Todos</option>{Object.entries(DOMAINS).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
        <label>Harness<select aria-label="Harness de estadísticas" value={scope.harness} onChange={e=>changeScope({harness:e.target.value})}><option value="">Ambos</option>{[...new Set(Object.values(snapshot.meta).map(m=>m.harness))].map(h=><option key={h}>{h}</option>)}</select></label>
        <label>Prioridad<select aria-label="Prioridad de estadísticas" value={scope.objective} onChange={e=>changeScope({objective:e.target.value})}><option value="">Todas</option>{Object.entries(OBJECTIVES).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
        <label>Proveedor / acceso<select aria-label="Proveedor de estadísticas" value={scope.pool} onChange={e=>changeScope({pool:e.target.value})}><option value="">Todos</option>{Object.entries(POOL_LABELS).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
        <label>Tipo de asignación<select aria-label="Tipo de asignación estadística" value={scope.kind} onChange={e=>changeScope({kind:e.target.value as StatisticsScope['kind']})}>{Object.entries(KIND_LABELS).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
        <label>Estado del rol<select aria-label="Estado del rol estadístico" value={scope.state} onChange={e=>changeScope({state:e.target.value as StatisticsScope['state']})}><option value="enabled">Habilitados</option><option value="disabled">Deshabilitados</option><option value="all">Todos los slots</option></select></label>
      </div>
      <div className="statistics-summary" role="status"><span><strong>{number(profilesInScope)}</strong> perfiles en dominio/harness/prioridad</span><span><strong>{number(counts.primary)}</strong> principales</span><span><strong>{number(counts.fallback)}</strong> reservas</span><span><strong>{number(counts.accelerator)}</strong> aceleradores</span></div>
      <p className="footnote">Los tres tipos están separados: una reserva no es otro rol principal ni demuestra que se haya activado. Estado actual del filtro: {scope.state==='enabled'?'roles habilitados':scope.state==='disabled'?'roles deshabilitados':'todos los slots'}. Los denominadores de las tablas siguen todos los filtros.</p>
      <div className="statistics-toolbar">{model?<button className="secondary-button" onClick={returnGeneral}><ArrowLeft size={15}/>Todos los modelos y dimensiones</button>:<label>Desglosar por<select aria-label="Dimensión estadística" value={dimension} onChange={e=>{setDimension(e.target.value as StatDimension);setQuery('')}}>{Object.entries(DIMENSIONS).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>}
        <label>Buscar<input type="search" aria-label="Buscar en estadísticas" placeholder={model?'Perfil o rol…':'Modelo, proveedor o dimensión…'} value={query} onChange={e=>setQuery(e.target.value)}/></label>
        <button className="secondary-button" onClick={()=>downloadFile('participacion-configurada.csv',statisticsCsv(model?matching:scoped),'text/csv;charset=utf-8')}><Download size={15}/>CSV del alcance completo</button>
      </div>
      {!model?<><p><strong>{number(scoped.length)}</strong> {KIND_LABELS[scope.kind].toLocaleLowerCase('es')} en el alcance. La proporción de cada fila usa ese total; buscar sólo oculta filas, no cambia el denominador.</p>{dimension==='model'&&<label className="statistics-zero"><input type="checkbox" checked={zero} onChange={e=>setZero(e.target.checked)}/>Incluir identidades de catálogo sin asignaciones en este alcance</label>}
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Estadísticas generales completas"><table className="statistics-table"><thead><tr><th>{DIMENSIONS[dimension]}</th><th>Asignaciones</th><th>Proporción</th><th>Perfiles distintos</th></tr></thead><tbody>{displayGroups.map(g=><tr key={g.key}><th scope="row">{dimension==='model'?<button className="model-button" data-stat-model={g.key} onClick={()=>selectModel(g.key)}>{g.label}<ArrowRight size={14}/></button>:label(g.key,g.label)}{dimension==='model'&&<small>{g.key}</small>}</th><td>{number(g.count)}</td><td>{percent(g.share)}</td><td>{number(g.profiles)}</td></tr>)}</tbody></table></div>
        {!displayGroups.length&&<p role="status">No hay filas para estos filtros.</p>}
        <p className="footnote">{displayGroups.length} / {groups.length} filas. Todas se muestran, no sólo las primeras seis. Agrupación por identidad declarada; compartir nombre no fusiona dos modelos. La identidad de un endpoint puede seguir siendo candidata.</p>
      </>:<section className="model-statistics" aria-labelledby="model-stat-title"><h3 id="model-stat-title" ref={modelHeading} tabIndex={-1}>{modelGroup?.label||model}</h3><p><strong>{number(matching.length)}</strong> {KIND_LABELS[scope.kind].toLocaleLowerCase('es')} en <strong>{number(top.length)}</strong> perfiles. {percent(scoped.length?matching.length/scoped.length:0)} del total filtrado. No es popularidad ni cuota consumida.</p>
        <details className="model-breakdown-details" open={breakdownsOpen} onToggle={e=>setBreakdownsOpen(e.currentTarget.open)}><summary>Ver distribución por proveedor, rol, dominio, harness y esfuerzo</summary><div className="model-stat-breakdowns">{breakdownsOpen&&(['pool','role','domain','harness','effort'] as const).map(d=><details key={d} open={d==='pool'}><summary>{DIMENSIONS[d]} · desglose completo</summary>{groupParticipation(matching,d).map(g=><p key={g.key}><span>{d==='pool'?poolLabel(g.key):d==='domain'?DOMAINS[g.key]||g.label:g.label}</span><strong>{number(g.count)} · {percent(g.share)}</strong></p>)}</details>)}</div></details>
        <div className="statistics-toolbar"><h4>Perfiles con mayor participación configurada</h4><label>Mostrar<select aria-label="Cantidad de perfiles del modelo" value={limit} onChange={e=>setLimit(e.target.value)}><option value="10">Top 10</option><option value="25">Top 25</option><option value="50">Top 50</option><option value="all">Todos ({filteredTop.length})</option></select></label><label>Ordenar por<select aria-label="Orden de participación" value={order} onChange={e=>setOrder(e.target.value as 'count'|'share')}><option value="count">Número de asignaciones</option><option value="share">Proporción dentro del perfil</option></select></label></div>
        <p className="footnote">El denominador de cada perfil es su número de asignaciones del tipo y estado seleccionados{scope.pool?`, restringido a ${poolLabel(scope.pool)}`:''}. Los empates se ordenan por identificador. No se ordenan calidad, rendimiento ni ahorro.</p>
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Perfiles con participación del modelo"><table className="statistics-table model-top-table"><thead><tr><th>Perfil exacto</th><th>Asignaciones / total</th><th>Proporción</th><th>Roles y acceso</th></tr></thead><tbody>{pageRows.map(p=>{const m=snapshot.meta[p.profileId];return <tr key={p.profileId}><th scope="row"><button className="model-button" data-stat-profile={p.profileId} onClick={()=>onProfile(p.profileId)}>{m.harness} · {DOMAINS[m.domain]} · {OBJECTIVES[m.objective]}<ArrowRight size={15}/></button><small>{portfolioLabel(snapshot.portfolios[m.portfolio])}</small><code>{p.profileId}</code></th><td>{p.count} / {p.total}</td><td>{percent(p.share)}</td><td><p>{p.roles.join(', ')}</p><p>{p.pools.map(poolLabel).join(' + ')}</p></td></tr>})}</tbody></table></div>
        {limit==='all'&&<div className="pagination"><button className="secondary-button" disabled={!currentWindow} onClick={()=>setWindowPage({key:windowKey,page:currentWindow-1})}>Anterior</button><span>Todos · página {currentWindow+1} de {windowPages} · 50 por página</span><button className="secondary-button" disabled={currentWindow===windowPages-1} onClick={()=>setWindowPage({key:windowKey,page:currentWindow+1})}>Siguiente</button></div>}
        <p role="status">{pageRows.length} de {filteredTop.length} perfiles coincidentes. {limit!=='all'&&filteredTop.length>pageRows.length&&<button className="text-button" onClick={()=>setLimit('all')}>Ver todos<ArrowRight size={14}/></button>}</p>
        {!matching.length&&<p className="empty-state">Este modelo no tiene asignaciones del tipo y alcance seleccionado en las referencias. Puede existir como candidato o en la evidencia sin estar asignado.</p>}
      </section>}
    </div>
  </dialog>
}
