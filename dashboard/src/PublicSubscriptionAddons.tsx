/** Public view: no provider data, scientific exports or runtime calls. */
import {useState} from 'react'
import {NO_PUBLIC_SUPPLEMENTS,publicSupplementDeclaration,SOURCE_LINKS} from './publicSupplementPlan'
import type {PublicSupplementSelection} from './publicSupplementPlan'

function savePublicInventory(selection:PublicSupplementSelection) {
  const payload=JSON.stringify(publicSupplementDeclaration(selection),null,2)+'\n'
  const blob=new Blob([payload],{type:'application/json'})
  const url=URL.createObjectURL(blob)
  try {
    const link=document.createElement('a')
    link.href=url
    link.download='agent-profile-lab-public-supplements.json'
    document.body.appendChild(link)
    try { link.click() } finally { link.remove() }
  } finally {
    // Give the browser a turn to resolve the user-triggered download.
    setTimeout(()=>URL.revokeObjectURL(url),1000)
  }
}

const GO_OPTIONS=[
  ['none','Ninguno'],['go10','Go · referencia $10/mes'],['plus40','Go Plus · referencia $40/mes'],
] as const
const NAN_OPTIONS=[
  ['none','Ninguno'],['gentle20','Gentle · referencia €20/mes'],
] as const
const GOOGLE_OPTIONS=[
  ['none','Ninguno'],['plus','Google AI Plus'],['pro','Google AI Pro'],
  ['ultra5x','Google AI Ultra 5×'],['ultra20x','Google AI Ultra 20×'],
] as const

export default function PublicSubscriptionAddons() {
  const [plan,setPlan]=useState<PublicSupplementSelection>(NO_PUBLIC_SUPPLEMENTS)
  const [notice,setNotice]=useState('')
  const change=<K extends keyof PublicSupplementSelection>(key:K,value:PublicSupplementSelection[K])=>{
    setPlan(old=>({...old,[key]:value}))
    setNotice('')
  }
  const summary=publicSupplementDeclaration(plan)
  return <details className="trace-note public-subscription-addons" data-public-boundary="declarative-only">
    <summary>Go Plus, NaN Gentle y Google AI: planes complementarios (sin acceso automático)</summary>
    <p>Selecciona las suscripciones que ya tengas para descargar un inventario orientativo.
      <strong> No altera los filtros de perfiles, su precio base, las asignaciones ni la exportación nativa.</strong>
      No comprueba la cuenta ni concede acceso a la API de Gemini, créditos o uso adicional.</p>
    <div className="subscription-groups">
      <label className="subscription-group">OpenCode Go
        <select aria-label="Complemento OpenCode Go" value={plan.go}
          onChange={e=>change('go',e.target.value as PublicSupplementSelection['go'])}>
          {GO_OPTIONS.map(([value,label])=><option value={value} key={value}>{label}</option>)}
        </select>
      </label>
      <label className="subscription-group">NaN
        <select aria-label="Complemento NaN" value={plan.nan}
          onChange={e=>change('nan',e.target.value as PublicSupplementSelection['nan'])}>
          {NAN_OPTIONS.map(([value,label])=><option value={value} key={value}>{label}</option>)}
        </select>
      </label>
      <label className="subscription-group">Google AI / Antigravity
        <select aria-label="Complemento Google AI" value={plan.google}
          onChange={e=>change('google',e.target.value as PublicSupplementSelection['google'])}>
          {GOOGLE_OPTIONS.map(([value,label])=><option value={value} key={value}>{label}</option>)}
        </select>
      </label>
    </div>
    <p className="footnote">Referencia de la investigación del 5/11/2026, no una oferta contractual actualizada.
      Cuotas y precios de Google AI dependen de la modalidad y región; las tarifas EUR y USD no se suman.
      NaN Gentle solo incluye los modelos anunciados para ese plan y no equivale a NaN Inference.</p>
    <p className="footnote">Fuentes oficiales: <a href={SOURCE_LINKS.go} target="_blank" rel="noreferrer">OpenCode Go</a>{' · '}
      <a href={SOURCE_LINKS.nan} target="_blank" rel="noreferrer">NaN Gentle</a>{' · '}
      <a href={SOURCE_LINKS.google} target="_blank" rel="noreferrer">Google Antigravity</a>.
      Las puntuaciones externas de modelos no se redistribuyen en este selector.</p>
    <p role="status" className="footnote">Inventario seleccionado: Go {summary.selections.go},
      NaN {summary.selections.nan}, Google AI {summary.selections.google}.
      No genera una configuración operativa.</p>
    <button type="button" className="secondary-button" onClick={()=>{
      savePublicInventory(plan)
      setNotice('Inventario declarativo generado; no se modificaron perfiles ni cuentas.')
    }}>Exportar inventario declarativo (JSON)</button>
    {notice&&<p role="status">{notice}</p>}
  </details>
}
