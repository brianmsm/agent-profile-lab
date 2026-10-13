import quotaApproval from '../../policies/nan-quota-approval.json'
import type {Snapshot} from './data'
import {useMemo,useState} from 'react'
import {Download, ShieldCheck, AlertTriangle, ChartNoAxesColumnIncreasing, RefreshCcw} from 'lucide-react'
import {nanKeys,nanPolicy,nanInventory,nanQuotas,nanFunctions,hypotheticalNanUsage,sampleNanUsage,planNanTask,simulateNanTasks,validateNanUsage} from './nanQuotaBalance'
import type {NanOffer,NanUsage,NanFunction,NanTask,NanModality} from './nanQuotaBalance'
import functions from '../../policies/functions.json'
const millions=new Intl.NumberFormat('es-ES',{maximumFractionDigits:2})
const pct=new Intl.NumberFormat('es-ES',{style:'percent',maximumFractionDigits:2})
const fmt=(t:number)=>millions.format(t/1_000_000)+' M'
const descriptions=functions.functions as Record<string,{definition:string}>
const labels=nanPolicy.labels as Record<NanOffer,string>
function saveJson(filename:string,data:unknown){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),0)}
function blankMeasured(now:Date):NanUsage {return {...hypotheticalNanUsage(now),source:'user-entered',approximate:true}}
export default function NaNQuotaPlanner({domain,snapshot}:{domain:string;snapshot:Snapshot}){
  const compatible=Object.entries(quotaApproval.sources).every(([path,sha])=>snapshot.access?.inputSha256?.[path]===sha)
  const [now,setNow]=useState(()=>new Date())
  const [usage,setUsage]=useState<NanUsage|null>(null)
  const [draft,setDraft]=useState<Partial<Record<NanOffer,number>>>({})
  const [functionId,setFunction]=useState<NanFunction>('bounded-exploration')
  const [modality,setModality]=useState<NanModality>('text')
  const [inputK,setInputK]=useState(12)
  const [totalK,setTotalK]=useState(35)
  const [count,setCount]=useState(40)
  const [trials,setTrials]=useState(false)
  const [oracle,setOracle]=useState(true)
  const [closed,setClosed]=useState(true)
  const [highImpact,setHighImpact]=useState(false)
  const [headroom,setHeadroom]=useState(2)
  const [notice,setNotice]=useState('')
  const task:NanTask=useMemo(()=>({taskId:'preview-only',functionId,domain:domain||'research',modality,estimatedInputTokens:Math.round(inputK*1000),estimatedTotalTokens:Math.round(totalK*1000),highImpact,closedTask:closed,acceptanceOracle:oracle,includeTrials:trials,headroomFraction:headroom/100}),[functionId,domain,modality,inputK,totalK,highImpact,closed,oracle,trials,headroom])
  const safeTask=totalK>=inputK&&totalK>0&&inputK>=0&&count>0
  const decision=useMemo(()=>compatible&&safeTask?planNanTask(usage,task,now):null,[usage,task,safeTask,now,compatible])
  const simulated=useMemo(()=>decision?.status==='selected'&&usage&&safeTask?simulateNanTasks(usage,task,count,now):null,[decision,usage,task,count,safeTask,now])
  const sourceText=usage?.source==='account-screenshot'?'Captura aproximada del 10 de octubre · no es lectura actual':usage?.source==='hypothetical'?'Escenario ficticio desde cero':usage?'Valores introducidos manualmente · no verificados con la API':Object.keys(draft).length?`Introducidos ${Object.keys(draft).length} de 4 contadores; los demás siguen desconocidos`:'Sin consumo declarado'
  const updateUsed=(key:NanOffer,raw:string)=>{
    const text=raw.trim()
    if(text!==''&&(!Number.isFinite(Number(text))||Number(text)<0||Number(text)>9000))return
    const next={...draft}
    if(text==='')delete next[key]
    else next[key]=Math.round(Number(text)*1_000_000)
    setDraft(next)
    if(nanKeys.every(k=>next[k]!==undefined)){
      setUsage({...blankMeasured(now),consumed:next as Record<NanOffer,number>})
      setNotice('Los cuatro contadores son valores manuales y no han sido verificados con NaN.')
    }else{
      setUsage(null)
      setNotice('Faltan contadores: no se suponen ceros ni se calcula una selección hasta tener los cuatro.')
    }
  }
  const quotas=[...nanKeys].map(key=>({key,total:nanQuotas[key],used:draft[key]??null,planned:simulated?.projected[key]??null,eligible:decision?.candidates.find(c=>c.offeringKey===key)?.eligible??false}))
  return <section className="nan-balance panel" aria-label="NaN equilibrio de cuotas por modelo">
    <div className="nan-balance-heading"><div><span className="eyebrow">POLÍTICA OPCIONAL · NAN</span><h3><ChartNoAxesColumnIncreasing size={20}/> Equilibrio de cuotas por modelo</h3><p>Simula el próximo worker o un lote de subtareas. Se intenta igualar el <strong>porcentaje utilizado de cada cupo</strong>, sólo entre modelos aceptables para esa función. No es el uso real ni cambia automáticamente Gentle u OMP.</p></div><span className="nan-balance-chip">4 cuotas independientes</span></div>
    {!compatible&&<p role="alert" className="nan-balance-warning">El snapshot importado no coincide con la versión del inventario y la política de NaN. Regenera datos o vuelve a los perfiles locales: se desactiva esta simulación para evitar decisiones de versiones mezcladas.</p>}
    <div className="nan-balance-actions"><button type="button" className="secondary-button" onClick={()=>setNow(new Date())}><RefreshCcw size={14}/> Actualizar fecha</button><button type="button" className="secondary-button" onClick={()=>{setUsage(sampleNanUsage());setDraft(sampleNanUsage().consumed);setNotice('Lectura redondeada de tu captura, potencialmente desactualizada. No equivale a GET /v1/usage.')}}>Cargar la captura como ejemplo</button><button type="button" className="secondary-button" onClick={()=>{setUsage(hypotheticalNanUsage(now));setDraft(hypotheticalNanUsage(now).consumed);setNotice('Simulación hipotética desde cero: no describe el estado de la cuenta.')}}>Simular desde cero</button><label className="nan-usage-import">Importar consumo normalizado <input type="file" accept=".json,application/json" aria-label="Importar snapshot mensual NaN" onChange={async e=>{const file=e.target.files?.[0];e.target.value='';if(!file)return;if(file.size>100_000){setNotice('El archivo de uso es demasiado grande; sólo se admiten contadores agregados.');return}try{const parsed=validateNanUsage(JSON.parse(await file.text()));setUsage(parsed);setDraft(parsed.consumed);setNotice('Snapshot importado en memoria, sin enviarlo al servidor. Se muestra su fecha y origen declarado; no valida credenciales ni calidad.')}catch(error){setNotice(error instanceof Error?error.message:'Archivo inválido; no se aplicaron valores.')}}}/></label><button type="button" className="secondary-button" onClick={()=>{setUsage(null);setDraft({});setNotice('')}}>Limpiar</button></div>
    {decision?.usageStale&&<p role="status" className="nan-balance-warning">El estado de cuota pertenece a un mes distinto o es anterior a 24 horas; el despachador no lo aceptaría como consumo actual. Actualiza manualmente los contadores.</p>}
    <p className="nan-balance-status" role="status"><ShieldCheck size={15}/>{sourceText}. {usage?`Fecha declarada: ${usage.observedAt.slice(0,16).replace('T',' ')} UTC.`:'Las casillas vacías no equivalen a saldo sin usar.'}</p>
    <p className="footnote">Leyenda: <strong>verde azulado</strong> = consumo indicado; <strong>ámbar</strong> = incremento hipotético. La referencia temporal mensual se muestra para orientar, no como obligación de gastar tokens.</p>
    <div className="nan-balance-quota-list" role="group" aria-label="Cuotas NaN observadas y proyección">
      {quotas.map(q=>{
        const used=q.used===null?0:q.used/q.total,planned=q.planned===null?used:q.planned/q.total
        return <div key={q.key} className="nan-balance-quota">
          <div className="nan-balance-quota-title"><strong>{labels[q.key]}</strong><span>{fmt(q.total)} / mes</span></div>
          <div className="nan-balance-bars" role="img" aria-label={`${labels[q.key]}: ${q.used===null?'uso desconocido':pct.format(used)+' de cuota indicada'}${q.planned===null?'':', proyectado '+pct.format(planned)}`}>
            <div className="nan-balance-bar" style={{width:`${Math.min(100,used*100)}%`}}/>
            {q.planned!==null&&<div className="nan-balance-bar forecast" style={{left:`${Math.min(100,used*100)}%`,width:`${Math.max(0,Math.min(100,planned*100)-Math.min(100,used*100))}%`}}/>}
          </div>
          <div className="nan-balance-quota-bottom"><label htmlFor={`nan-used-${q.key}`}>Consumido (millones) <input id={`nan-used-${q.key}`} type="number" min="0" max="9000" step="0.1" placeholder="Desconocido" value={q.used===null?'':Number((q.used/1e6).toFixed(6))} onChange={e=>updateUsed(q.key,e.target.value)}/></label><span>{q.used===null?'Sin dato':`${pct.format(used)} usado · ${fmt(Math.max(0,q.total-q.used))} restantes`}</span><span>{q.planned===null?'':`${pct.format(planned)} proyectado`}</span><span>{decision?.candidates.find(c=>c.offeringKey===q.key)?.aheadOfPace?'Por encima del ritmo lineal del mes':''}</span></div>
        </div>
      })}
    </div>
    <p className="nan-balance-note"><AlertTriangle size={15}/> Los datos manuales y los de captura no son una conexión a tu cuenta. Las rutas NaN no se consideran comprobadas por aparecer en un perfil. En el despacho local se exige confirmación expresa de ruta y consumo reciente.</p>
    <div className="nan-balance-controls">
      <label>Tipo de subtarea<select value={functionId} onChange={e=>setFunction(e.target.value as NanFunction)}>{nanFunctions.map(id=><option key={id} value={id}>{({'bounded-exploration':'Exploración delimitada','bounded-implementation':'Implementación delimitada','bounded-remediation':'Remediación localizada','mechanical-verification':'Comprobación mecánica','commit-preparation':'Preparación de commit','status-reporting':'Informe de estado','workspace-orientation':'Orientación del repositorio','workspace-initialization':'Preparación de entorno'} as Record<string,string>)[id]}</option>)}</select></label>
      <label>Entrada<select value={modality} onChange={e=>setModality(e.target.value as NanModality)}><option value="text">Texto / herramientas</option><option value="image">Imagen</option><option value="audio">Audio</option></select></label>
      <label>Tokens de entrada previstos (miles)<input type="number" min="0" max="1000" step="1" value={inputK} onChange={e=>setInputK(Number(e.target.value))}/></label>
      <label>Tokens totales por tarea (miles)<input type="number" min="1" max="2000" step="1" value={totalK} onChange={e=>setTotalK(Number(e.target.value))}/></label>
      <label>Tareas hipotéticas<select value={count} onChange={e=>setCount(Number(e.target.value))}><option value="10">10</option><option value="40">40</option><option value="100">100</option><option value="250">250</option></select></label>
      <label>Reserva de seguridad<select value={headroom} onChange={e=>setHeadroom(Number(e.target.value))}><option value="0">0 %</option><option value="2">2 %</option><option value="5">5 %</option><option value="10">10 %</option></select></label>
    </div>
    <p className="nan-balance-function">{descriptions[functionId]?.definition}</p>
    <div className="nan-balance-flags"><label><input type="checkbox" checked={closed} onChange={e=>setClosed(e.target.checked)}/> Subtarea cerrada y delegable</label><label><input type="checkbox" checked={oracle} onChange={e=>setOracle(e.target.checked)}/> Resultado comprobable con oráculo</label><label><input type="checkbox" checked={highImpact} onChange={e=>setHighImpact(e.target.checked)}/> Alto impacto: no redistribuir</label><label><input type="checkbox" checked={trials} onChange={e=>setTrials(e.target.checked)}/> Admitir modelos experimentales para tareas con verificación</label></div>
    {trials&&<p className="nan-balance-warning">Qwen/MiMo son candidatos de prueba, no equivalentes empíricamente demostrados a GLM o DeepSeek. Habilitarlos aquí no confirma el endpoint ni instala un despachador.</p>}
    {notice&&<p className="footnote" role="status">{notice}</p>}
    <div className="nan-balance-result" aria-live="polite">
      {decision?.status==='selected'&&decision.selected?<><strong>Próxima subtarea sugerida: {labels[decision.selected]}</strong><code>{decision.selector}</code><p>{decision.reason}</p></>:<><strong>{decision?decision.status==='blocked'?'No redistribuir esta actividad':'Sin selección de modelo':'Indica primero el consumo o carga una simulación'}</strong><p>{!safeTask?'Los tokens totales deben incluir la entrada y ser mayores que cero.':decision?.reason||'Las cuotas del plan están registradas, pero su consumo actual no se consulta automáticamente.'}</p></>}
      {compatible&&simulated&&<div className="nan-balance-sim"><h4>Proyección de {simulated.planned} de {simulated.requested} tareas</h4><div className="nan-balance-sim-grid">{nanKeys.map(key=><div key={key}><span>{labels[key]}</span><strong>{simulated.counts[key]} tareas</strong><small>{fmt(simulated.counts[key]*task.estimatedTotalTokens)} estimados</small></div>)}</div><p className="footnote">{simulated.note} El reparto en tokens no equivale al reparto por calidad o volumen de actividad.</p></div>}
      {!!decision?.candidates?.length&&<details className="nan-balance-alternatives"><summary>Por qué se admite o excluye cada modelo</summary><div className="nan-balance-reasons">{(decision?.candidates??[]).map(c=><div key={c.offeringKey}><strong>{c.label}</strong><span>{c.classification==='trial'?'Prueba condicionada':c.classification==='eligible'?'Función admisible':'Función no admitida'}</span><p>{c.reason}</p></div>)}</div></details>}
    </div>
    <div className="nan-balance-actions"><button className="secondary-button" type="button" disabled={!compatible} onClick={()=>saveJson('agent-profile-lab-nan-policy.json',{type:'nan-quota-balancing-policy',version:1,policyId:nanPolicy.id,inputSha256:quotaApproval.sources,inventory:nanInventory.models.map(m=>({offeringKey:m.offeringKey,monthlyTokens:m.monthlyTokens})),taskRequirements:task,qualityGates:nanPolicy.functions,limitations:nanPolicy.limitations,dispatch:'not-installed'})}><Download size={14}/> Exportar política</button><button className="secondary-button" type="button" disabled={!compatible||!simulated||!usage} onClick={()=>saveJson('agent-profile-lab-nan-simulation.json',{type:'nan-quota-balancing-simulation',executed:false,source:usage?.source,approximate:usage?.approximate,observedAt:usage?.observedAt,policyId:nanPolicy.id,task,decision,simulation:simulated})}><Download size={14}/> Exportar simulación</button></div>
    <p className="footnote">La distribución real requiere que un orquestador invoque <code>scripts/nan_quota_dispatch.py</code> antes de cada subtarea y registre sus tokens al terminar. No hay reorientación de llamadas iniciadas, monitorización programada ni modificación de los perfiles instalados.</p>
  </section>
}
