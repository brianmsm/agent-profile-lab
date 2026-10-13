import { useCompleteSnapshot } from './snapshotResourceContext'
import { useEffect, useRef, useState } from 'react'
import { Download } from 'lucide-react'
import type { Snapshot, SubscriptionSelection } from './data'
import { monthly } from './data'
import { downloadFile } from './snapshotIO'
import { presetAnalysis, presetRolesCsv } from './presetStrategies'
import type { Preset } from './presetStrategies'
import { compileAccessBundle, prepareAccessPreset } from './accessExport'
import type { ExportOptions, OpenAIAccessMode } from './accessExport'
import { accessTargets, hasMeteredRoutes } from './accessRouting'

type Bundle = Awaited<ReturnType<typeof compileAccessBundle>>
interface Props { snapshot: Snapshot; preset: Preset; availability: SubscriptionSelection | null }

export default function ProfileExport({ snapshot, preset, availability }: Props) {
  const loadComplete=useCompleteSnapshot(snapshot)
  const [mode, setMode] = useState<OpenAIAccessMode>('preserve')
  const [apiRef, setApiRef] = useState('api-main')
  const [apiConsent, setApiConsent] = useState(false)
  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [bundle, setBundle] = useState<Bundle | null>(null)
  const generation = useRef(0)
  const bundleGeneration = useRef(-1)
  // App keys the profile view by dataset revision; Profiles keys this editor by preset id.
  // Cancel a pending digest on unmount/replacement; local controls invalidate synchronously.
  useEffect(() => () => { generation.current += 1 }, [snapshot, preset.id])
  const invalidate = () => { generation.current += 1; setBundle(null); setNotice(''); setBusy(false) }
  const options: ExportOptions = { mode, apiCredentialRef: apiRef, apiConsent, maxAmount: Number(amount), currency }
  const portfolio = snapshot.portfolios[preset.portfolio]
  const baseName = preset.id.replace(/[^A-Za-z0-9._-]+/gu, '-')
  const hasChatGPT = Object.values(preset.routes).some(route => [route, route.fallback, route.accelerator].some(ref => ref?.origin && ['chatgpt-legacy', 'chatgpt-siwc'].includes(ref.origin.accessRouteId)))
  const target = preset.meta.targetId ? accessTargets[preset.meta.targetId] : null
  const needsApiConsent = mode === 'api' || hasMeteredRoutes(preset)
  const prepare = async () => {
    const ticket = ++generation.current
    setBusy(true); setNotice(''); setBundle(null)
    try {
      const result = await compileAccessBundle(snapshot, preset, options)
      if (ticket !== generation.current) return
      bundleGeneration.current = ticket
      setBundle(result)
      setNotice('Par preparado y ligado por SHA-256. Descarga ambos archivos. No se ha instalado nada ni verificado una cuenta remota.')
    } catch (error) {
      if (ticket === generation.current) setNotice(error instanceof Error ? error.message : 'No se pudo compilar el perfil.')
    } finally { if (ticket === generation.current) setBusy(false) }
  }
  const currentBundle = () => {
    if (!bundle || bundleGeneration.current !== generation.current) throw new Error('Las opciones han cambiado: vuelve a preparar el par antes de descargar.')
    return bundle
  }
  const exportNative = () => {
    try { const result = currentBundle(); downloadFile(result.native.filename, result.native.content, result.native.mimeType) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Exportación no disponible.') }
  }
  const exportManifest = () => {
    try {
      const result = currentBundle()
      downloadFile(result.manifest.profileName + '.manifest.json', JSON.stringify(result.manifest, null, 2) + '\n', 'application/json;charset=utf-8')
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Manifiesto no disponible.') }
  }
  const exportJson = async () => {
    const ticket=generation.current
    setNotice('Cargando las fuentes completas del análisis…')
    try {
      const complete=await loadComplete()
      if(ticket!==generation.current)return
      const prepared = snapshot.access ? prepareAccessPreset(snapshot, preset, options) : null
      const analysis = presetAnalysis(complete, prepared?.preset ?? preset, availability)
      if (analysis.profile.access && prepared) analysis.profile.access.resources = prepared.resources
      const content = { ...analysis, compilationIntent: prepared ? { targetId: preset.meta.targetId, mode, meteredAuthorization: prepared.authorization ?? null, credentialsEnforced: false } : null }
      downloadFile(`perfil-${baseName}-analisis.json`, JSON.stringify(content, null, 2) + '\n', 'application/json;charset=utf-8')
      setNotice('Análisis exportado con el origen seleccionado. El coste mensual es el portfolio de referencia, no el gasto API ni una garantía de rendimiento.')
    } catch (error) { if(ticket===generation.current)setNotice(error instanceof Error ? error.message : 'No se pudo crear el análisis.') }
  }
  const exportCsv = () => {
    try {
      const selected = snapshot.access ? prepareAccessPreset(snapshot, preset, options).preset : preset
      downloadFile(`perfil-${baseName}-roles.csv`, presetRolesCsv(snapshot, selected), 'text/csv;charset=utf-8')
      setNotice('CSV exportado con selector resuelto, modelo, vía, recurso, plan y referencia externa de credenciales; también incluye las reservas.')
    } catch (error) { setNotice(error instanceof Error ? error.message : 'No se pudo crear el CSV.') }
  }
  return <section className="panel profile-export" aria-label={`Exportación de ${preset.id}`}>
    <div className="section-heading"><div><h2>Compilar configuración y procedencia</h2><p className="section-description">Destino: <strong>{preset.meta.targetId || 'No declarado en este snapshot'}</strong>. Los archivos no instalan agentes ni cambian credenciales. El mismo selector puede corresponder a distintas vías de acceso.</p></div></div>
    <p className="footnote">Portfolio de referencia: <strong>{monthly(portfolio)}</strong> / mes. No estima el gasto de las vías API seleccionadas para exportación.</p>
    {!snapshot.access ? <p className="preset-export-warning" role="status">Origen de acceso no declarado. Este snapshot histórico admite consulta, CSV y análisis; regenera sus datos para habilitar exportaciones nativas trazadas.</p> : <fieldset className="access-controls">
      <legend>Origen de las rutas ChatGPT al exportar</legend>
      <label>Vía de acceso<select aria-label="Vía de acceso OpenAI" value={mode} disabled={!hasChatGPT} onChange={event => { invalidate(); setMode(event.target.value as OpenAIAccessMode); setApiConsent(false) }}>
        <option value="preserve">Conservar origen declarado</option><option value="legacy">ChatGPT · OAuth legacy</option>
        <option value="siwc" disabled={!target?.providers['chatgpt-siwc']}>ChatGPT · Sign in with ChatGPT {target?.providers['chatgpt-siwc'] ? '' : '(no soportado por el destino)'}</option>
        <option value="api">OpenAI API · pago por uso</option>
      </select></label>
      <p className="footnote">El cambio se aplica a las rutas ChatGPT del perfil y sus reservas, no a modelos OpenAI ofrecidos por otros gateways. Las asignaciones canónicas no cambian.</p>
      {needsApiConsent && <div className="access-api-fields">
        <label>Referencia de credenciales (no la clave)<input aria-label="Referencia de credenciales API" value={apiRef} onChange={event => { invalidate(); setApiRef(event.target.value) }} autoComplete="off" /></label>
        <label>Importe autorizado declarado<input aria-label="Importe API autorizado" type="number" min="0" step="0.01" value={amount} onChange={event => { invalidate(); setAmount(event.target.value) }} /></label>
        <label>Moneda<select aria-label="Moneda API" value={currency} onChange={event => { invalidate(); setCurrency(event.target.value) }}><option>USD</option><option>EUR</option></select></label>
        <label className="access-consent"><input type="checkbox" checked={apiConsent} onChange={event => { invalidate(); setApiConsent(event.target.checked) }} /> Autorizo declarar una ruta API de pago para esta exportación. No se enviarán peticiones.</label>
        <p className="access-budget-warning"><strong>El importe es declarativo:</strong> estos archivos no imponen un límite de gasto en Pi, OMP ni en el proveedor.</p>
      </div>}
    </fieldset>}
    <div className="preset-export-warning"><strong>El manifiesto conserva el origen esperado; no lo impone al runtime.</strong><p>Comprueba autenticación, variables de entorno, overrides y rotación de cuentas. Las reservas, aceleradores y condiciones quedan documentados, pero no se instalan automáticamente. Las rutas sin calibrar siguen sin calibrar.</p></div>
    <div className="transfer-actions">
      <button className="primary-button" type="button" onClick={prepare} disabled={!snapshot.access || busy}>{busy ? 'Preparando…' : 'Preparar configuración y manifiesto'}</button>
      <button className="secondary-button" type="button" onClick={exportCsv}><Download size={15} /> CSV con origen</button>
      <button className="text-button" type="button" onClick={exportJson}><Download size={15} /> JSON analítico</button>
    </div>
    {bundle && <div className="access-prepared"><p>SHA-256 del archivo nativo: <code>{bundle.manifest.nativeArtifact.sha256}</code></p><div className="transfer-actions">
      <button className="primary-button" type="button" onClick={exportNative}><Download size={16} /> Descargar configuración nativa</button>
      <button className="secondary-button" type="button" onClick={exportManifest}><Download size={16} /> Descargar manifiesto</button>
    </div></div>}
    {notice && <p className="transfer-notice" role="status">{notice}</p>}
  </section>
}
