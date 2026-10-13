import {useState} from 'react'
import {Download,FileUp,RotateCcw,Save,SlidersHorizontal,Trash2} from 'lucide-react'
import functions from '../../policies/functions.json'
import {customWorkloadEqualsBase,customWorkloadRules,makeNanCustomWorkload,nanFunctionIds,sourceNanWorkload,totalAssumedTokens,validateNanCustomWorkload} from './nanCustomWorkload'
import type {NanCustomWorkload,NanScenario,FunctionWorkload} from './nanCustomWorkload'
const STORAGE='agent-profile-lab.nan-custom-workloads.v1'
const fmt=new Intl.NumberFormat('es-ES',{maximumFractionDigits:2})
function safeStorage():NanCustomWorkload[]{
  try{
    const raw=localStorage.getItem(STORAGE)
    if(!raw||raw.length>customWorkloadRules.maxImportBytes*customWorkloadRules.maxSavedScenarios)return []
    const value=JSON.parse(raw) as unknown
    if(!Array.isArray(value))return []
    return value.slice(0,customWorkloadRules.maxSavedScenarios).flatMap(item=>{
      try{return [validateNanCustomWorkload(item)]}catch{return []}
    })
  }catch{return []}
}
function download(name:string,value:NanCustomWorkload) {
  const blob=new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json;charset=utf-8'})
  const url=URL.createObjectURL(blob)
  const element=document.createElement('a')
  element.href=url
  element.download='nan-carga-'+name.toLowerCase().replace(/[^a-z0-9-]+/gu,'-').slice(0,36)+'-'+value.fingerprint.slice(0,12)+'.json'
  element.click()
  setTimeout(()=>URL.revokeObjectURL(url),0)
}
const names=functions.functions as Record<string,{definition:string}>
interface Props {
  baseScenario:NanScenario
  applied:NanCustomWorkload|null
  activeRoleFunctions:string[]
  onApply:(value:NanCustomWorkload)=>void
  onClear:()=>void
}
/** Draft is intentionally not in the profile query. Only Apply or a selected
 * saved scenario changes the actual candidate, its identity and exports. */
export default function NanCustomWorkloadEditor({baseScenario,applied,activeRoleFunctions,onApply,onClear}:Props){
  const [draft,setDraft]=useState<FunctionWorkload>(()=>structuredClone(applied?.functionWorkload||sourceNanWorkload(baseScenario)))
  const [label,setLabel]=useState(applied?.label||'Mi carga personalizada')
  const [description,setDescription]=useState(applied?.description||'Hipótesis propia de llamadas mensuales y tokens totales por llamada.')
  const [saved,setSaved]=useState<NanCustomWorkload[]>(safeStorage)
  const [onlyActive,setOnlyActive]=useState(true)
  const [expanded,setExpanded]=useState(Boolean(applied))
  const [feedback,setFeedback]=useState<{error:boolean;text:string}|null>(null)
  const [changed,setChanged]=useState(false)
  const active=new Set(activeRoleFunctions)
  const ids=onlyActive&&activeRoleFunctions.length?nanFunctionIds.filter(id=>active.has(id)):nanFunctionIds
  const currentTotal=activeRoleFunctions.reduce((sum,id)=>sum+(draft[id]?.callsPerMonth||0)*(draft[id]?.totalTokensPerCall||0),0)
  const baseTotal=totalAssumedTokens(draft)
  const selected=applied?.fingerprint||null
  const setCell=(id:string,field:'callsPerMonth'|'totalTokensPerCall',text:string)=>{
    const value=text.trim()===''?0:Number(text)
    setDraft(previous=>({...previous,[id]:{...previous[id],[field]:value}}))
    setChanged(true);setFeedback(null)
  }
  const proposal=()=>makeNanCustomWorkload(baseScenario,label,description,draft)
  const act=(kind:'apply'|'save'|'download')=>{
    try{
      const document=proposal()
      if(kind==='apply'){
        if(customWorkloadEqualsBase(document))throw new Error('Los contadores coinciden con el predefinido. No hace falta duplicar el perfil; usa Restablecer predefinido.')
        onApply(document);setFeedback({error:false,text:'Escenario aplicado. El generador y las exportaciones usan ahora estos 20 supuestos.'})
      }
      if(kind==='download'){
        download(label,document);setFeedback({error:false,text:'Se ha descargado el escenario. No se ha aplicado una configuración ni se ha ejecutado ningún modelo.'})
      }
      if(kind==='save'){
        if(saved.some(x=>x.label.toLocaleLowerCase('es')===document.label.toLocaleLowerCase('es')&&x.fingerprint!==document.fingerprint))
          throw new Error('Ya existe un escenario local con este nombre. Cambia el nombre o elimina el guardado anterior.')
        const existing=saved.some(x=>x.fingerprint===document.fingerprint)
        if(!existing&&saved.length>=customWorkloadRules.maxSavedScenarios)throw new Error('Límite de escenarios locales alcanzado; elimina uno antes de guardar.')
        const next=existing?saved:[...saved,document]
        localStorage.setItem(STORAGE,JSON.stringify(next))
        setSaved(next);setFeedback({error:false,text:existing?'Este escenario ya estaba guardado.':'Escenario guardado sólo en este navegador. Para transferirlo, exporta JSON.'})
      }
    }catch(error){
      setFeedback({error:true,text:error instanceof Error?error.message:'El escenario contiene valores no válidos.'})
    }
  }
  const loadSaved=(fingerprint:string)=>{
    const chosen=saved.find(x=>x.fingerprint===fingerprint)
    if(chosen){
      onApply(chosen)
      setFeedback({error:false,text:'Se ha cargado el escenario local en el generador.'})
    }
  }
  const removeSaved=()=>{
    const target=saved.find(x=>x.fingerprint===selected)
    if(!target){setFeedback({error:true,text:'Selecciona un escenario guardado antes de eliminarlo.'});return}
    try{
      const next=saved.filter(x=>x.fingerprint!==target.fingerprint)
      localStorage.setItem(STORAGE,JSON.stringify(next))
      setSaved(next);setFeedback({error:false,text:'Escenario borrado del almacenamiento local. No se ha eliminado ningún archivo descargado.'})
    }catch{setFeedback({error:true,text:'El navegador no permitió eliminar el escenario local.'})}
  }
  return <details className="nan-workload-editor" open={expanded} onToggle={e=>setExpanded(e.currentTarget.open)}>
    <summary><SlidersHorizontal size={16}/> Personalizar frecuencias y tokens por función {applied&&<span className="nan-workload-applied">Aplicado: {applied.label}</span>}</summary>
    {expanded&&<div className="nan-workload-content">
      <p>Edita cuántas veces al mes esperas usar cada función y cuántos <strong>tokens totales (entrada + salida)</strong> estimas por llamada. El cambio sólo afectará al perfil al pulsar <strong>Aplicar al generador</strong>. Las cuotas de NaN, los contratos y los límites de calidad no son editables aquí.</p>
      <div className="nan-workload-header">
        <label>Nombre del escenario<input type="text" maxLength={customWorkloadRules.maxLabelLength} aria-label="Nombre de carga personalizada" value={label} onChange={e=>{setLabel(e.target.value);setChanged(true)}}/></label>
        <label>Descripción de la hipótesis<input type="text" maxLength={customWorkloadRules.maxDescriptionLength} aria-label="Descripción de carga personalizada" value={description} onChange={e=>{setDescription(e.target.value);setChanged(true)}}/></label>
      </div>
      <div className="nan-workload-statistics">
        <div><small>Funciones del catálogo</small><strong>{nanFunctionIds.length}</strong></div>
        <div><small>Roles activos del perfil seleccionado</small><strong>{activeRoleFunctions.length||'Sin perfil seleccionado'}</strong></div>
        <div><small>Tokens hipotéticos/mes de los roles activos</small><strong>{activeRoleFunctions.length?fmt.format(currentTotal/1e6)+' M':'—'}</strong></div>
      </div>
      <div className="nan-workload-toolbar"><label><input type="checkbox" checked={onlyActive} onChange={e=>setOnlyActive(e.target.checked)}/> Mostrar sólo funciones activas en el perfil</label><span>{ids.length} de {nanFunctionIds.length} funciones · todas se conservarán en el archivo</span></div>
      <div className="nan-workload-table-wrap" role="region" tabIndex={0} aria-label="Frecuencias y tokens mensuales editables">
        <table className="nan-workload-table"><thead><tr><th>Función</th><th>Llamadas / mes</th><th>Tokens totales / llamada</th><th>Tokens estimados / mes</th></tr></thead>
          <tbody>{ids.map(id=><tr key={id} className={active.has(id)?'active':'inactive'}>
            <th scope="row">{id}<small>{names[id]?.definition}</small></th>
            <td><input type="number" min="0" max={customWorkloadRules.maxCallsPerMonth} step="1" aria-label={'Llamadas mensuales '+id} value={Number.isFinite(draft[id]?.callsPerMonth)?draft[id].callsPerMonth:''} onChange={e=>setCell(id,'callsPerMonth',e.target.value)}/></td>
            <td><input type="number" min="0" max={customWorkloadRules.maxTotalTokensPerCall} step="1" aria-label={'Tokens totales por llamada '+id} value={Number.isFinite(draft[id]?.totalTokensPerCall)?draft[id].totalTokensPerCall:''} onChange={e=>setCell(id,'totalTokensPerCall',e.target.value)}/></td>
            <td className="nan-workload-total">{Number.isFinite(draft[id]?.callsPerMonth*draft[id]?.totalTokensPerCall)?fmt.format(draft[id].callsPerMonth*draft[id].totalTokensPerCall):'No válido'}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <p className="footnote">Suma de una instancia por cada función del catálogo: {fmt.format(baseTotal/1e6)} M tokens hipotéticos/mes. El perfil puede usar más de un rol con la misma función; el detalle del perfil contabiliza todos los roles habilitados. Los ceros significan que no prevés esa función, no que su modelo sea incapaz de realizarla.</p>
      {changed&&<p className="nan-workload-draft" role="status">Tienes cambios en el borrador sin aplicar. El perfil y la exportación siguen reflejando el escenario anterior.</p>}
      <div className="nan-workload-actions">
        <button type="button" className="secondary-button" onClick={()=>act('apply')}>Aplicar al generador</button>
        <button type="button" className="secondary-button" onClick={()=>act('save')}><Save size={14}/> Guardar en este navegador</button>
        <button type="button" className="secondary-button" onClick={()=>act('download')}><Download size={14}/> Exportar JSON</button>
        <button type="button" className="text-button" onClick={()=>{onClear();setFeedback({error:false,text:'Vuelves a los supuestos predefinidos. Las personalizaciones guardadas siguen disponibles.'})}}><RotateCcw size={14}/> Restablecer predefinido</button>
      </div>
      <div className="nan-workload-saved">
        <label>Escenarios guardados localmente<select aria-label="Cargar escenario local" value={selected&&saved.some(x=>x.fingerprint===selected)?selected:''} onChange={e=>loadSaved(e.target.value)}>
          <option value="">Seleccionar para cargar…</option>{saved.map(x=><option key={x.fingerprint} value={x.fingerprint}>{x.label} · {x.baseScenario}</option>)}
        </select></label>
        <button type="button" className="secondary-button" disabled={!selected||!saved.some(x=>x.fingerprint===selected)} onClick={removeSaved}><Trash2 size={14}/> Eliminar guardado</button>
        <label className="nan-workload-import"><FileUp size={15}/> Importar JSON<input type="file" accept=".json,application/json" aria-label="Importar escenario de carga NaN" onChange={async e=>{
          const file=e.target.files?.[0];e.target.value=''
          if(!file)return
          if(file.size>customWorkloadRules.maxImportBytes){setFeedback({error:true,text:'Archivo demasiado grande para un escenario de carga.'});return}
          try{
            const imported=validateNanCustomWorkload(JSON.parse(await file.text()))
            onApply(imported)
            setFeedback({error:false,text:'Archivo de carga importado y aplicado. No se han consultado cuotas reales.'})
          }catch(error){setFeedback({error:true,text:error instanceof Error?error.message:'El archivo no es compatible.'})}
        }}/></label>
      </div>
      {feedback&&<p role="status" className={feedback.error?'nan-balance-warning':'nan-workload-feedback'}>{feedback.text}</p>}
      <p className="footnote">Máximos de seguridad: {fmt.format(customWorkloadRules.maxCallsPerMonth)} llamadas/mes y {fmt.format(customWorkloadRules.maxTotalTokensPerCall)} tokens totales por llamada. Guardar e importar son operaciones locales del navegador; no modifican las fuentes versionadas ni envían información a NaN.</p>
    </div>}
  </details>
}
