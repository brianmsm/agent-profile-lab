import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { ArrowRight, BookOpen, CircleAlert, Grid2X2, Layers3, LayoutDashboard, LoaderCircle, RefreshCw, ShieldCheck } from 'lucide-react'
import Overview from './Overview'
const Profiles = lazy(() => import('./Profiles'))
const Evidence = lazy(() => import('./Evidence'))
import ThemeControl from './ThemeControl'
import SnapshotTools from './SnapshotTools'
import type { ProfileFilters, Snapshot } from './data'
import { DEFAULT_FILTERS, number, subscriptionsOf } from './data'
import { openSnapshotSession } from './snapshotClient'
import { SnapshotResource } from './snapshotResourceContext'
import { EvidenceBoundary } from './SnapshotResource'

type View = 'overview' | 'profiles' | 'evidence'
const VIEW_LABELS: Record<View, string> = { overview: 'Visión general', profiles: 'Perfiles', evidence: 'Evidencia' }
function viewFromHash(): View {
  const hash = window.location.hash.slice(1)
  return hash === 'profiles' || hash === 'evidence' ? hash : 'overview'
}
export default function App() {
  const [completeLoader,setCompleteLoader]=useState<(() => Promise<Snapshot>)|null>(null)
  const [bundledSnapshot, setBundledSnapshot] = useState<Snapshot | null>(null)
  const [importedSnapshot, setImportedSnapshot] = useState<Snapshot | null>(null)
  const [datasetVersion, setDatasetVersion] = useState(0)
  const snapshot = importedSnapshot || bundledSnapshot
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [view, setView] = useState<View>(viewFromHash)
  const previousView = useRef(view)
  const [filters, setFilters] = useState<ProfileFilters>(DEFAULT_FILTERS)
  useEffect(() => {
    if (previousView.current === view) return
    previousView.current = view
    const main = document.getElementById('main-content')
    if (!main) return
    main.focus({ preventScroll: true })
    main.scrollIntoView({ block: 'start', behavior: 'instant' })
  }, [view])
  useEffect(() => {
    let active=true
    let session:ReturnType<typeof openSnapshotSession>|undefined
    try {
      session=openSnapshotSession()
      const current=session
      session.core.then(data=>{
        if(active){setBundledSnapshot(data);setCompleteLoader(()=>current.complete);setError('')}
      }).catch(cause=>{if(active)setError(cause instanceof Error?cause.message:'Error de datos')})
    } catch(cause) {queueMicrotask(()=>{if(active)setError(cause instanceof Error?cause.message:'No se pudo iniciar el procesador de datos.')})}
    return ()=>{active=false;session?.dispose()}
  }, [attempt])
  useEffect(() => {
    const handleHash = () => setView(viewFromHash())
    window.addEventListener('hashchange', handleHash)
    return () => window.removeEventListener('hashchange', handleHash)
  }, [])
  const navigate = (next: View) => { window.location.hash = next; setView(next) }
  const openProfiles = (query = '', portfolio = '', domain = '', profileId = '') => {
    const selectedMeta = profileId && snapshot && Object.hasOwn(snapshot.meta,profileId) ? snapshot.meta[profileId] : null
    if(selectedMeta){portfolio=selectedMeta.portfolio;domain=selectedMeta.domain}
    const chosen = portfolio ? snapshot?.portfolios[portfolio] : null
    setFilters({
      domain, objective: selectedMeta?.objective || '', harness: selectedMeta?.harness || '', profileId:selectedMeta?profileId:undefined, subscriptions: chosen ? subscriptionsOf(chosen) : null,
      strategy: 'matrix', portfolio, search: query,
    })
    navigate('profiles')
  }
  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={event => {
      event.preventDefault()
      const main = document.getElementById('main-content')
      if (!main) return
      main.focus({ preventScroll: true })
      main.scrollIntoView({ block: 'start', behavior: 'instant' })
    }}>Saltar al contenido</a>
    <aside className="navigation-rail"><a className="brand" href="#overview" aria-label="Agent Profile Lab, visión general"><span className="brand-mark"><Layers3 size={24} strokeWidth={1.6} /></span><div><strong>profile<span>lab.</span></strong><small>AGENT PROFILE LAB</small></div></a><span className="nav-label">ESPACIO DE ANÁLISIS</span><nav aria-label="Navegación principal">{([{ id: 'overview', Icon: LayoutDashboard, subtitle: 'Referencias de un vistazo' }, { id: 'profiles', Icon: Grid2X2, subtitle: 'Explora las configuraciones' }, { id: 'evidence', Icon: BookOpen, subtitle: 'Fuentes y benchmarks' }] as const).map(({ id, Icon, subtitle }) => <a key={id} href={`#${id}`} className={`nav-link ${view === id ? 'active' : ''}`} aria-current={view === id ? 'page' : undefined}><Icon size={19} /><div><strong>{VIEW_LABELS[id]}</strong><small>{subtitle}</small></div>{view === id && <span className="nav-active-dot" />}</a>)}</nav><div className="rail-bottom"><div className="rail-note"><ShieldCheck size={19} /><strong>Decisiones informadas.<br />Sin métricas inventadas.</strong><p>Configuración y evidencia del corpus. No monitorización en vivo.</p></div><div className="rail-version"><span className="rail-status-dot" /><span>Corpus {snapshot?.stats.session.split(' ')[0] || 'estática'}<small>Solo lectura</small></span></div></div></aside>
    <div className="workspace">
      <header className="workspace-header">
        <span>Workspace <span className="breadcrumb-divider">/</span> <strong>{VIEW_LABELS[view]}</strong></span>
        <span className="header-status"><span />{importedSnapshot ? 'Snapshot importado' : 'Datos del proyecto'}<span className="header-session">{snapshot?.stats.session || 'Snapshot local'}</span></span>
        <ThemeControl />
      </header>
      <main id="main-content" tabIndex={-1}>
      <SnapshotResource.Provider value={importedSnapshot?null:completeLoader}>
      <SnapshotTools
        snapshot={snapshot}
        isImported={importedSnapshot !== null}
        onImport={data => {
          setImportedSnapshot(data)
          setDatasetVersion(version => version + 1)
          setFilters({ ...DEFAULT_FILTERS, domain: '', objective: '' })
        }}
        onRestore={() => {
          setImportedSnapshot(null)
          setDatasetVersion(version => version + 1)
          setFilters(DEFAULT_FILTERS)
          if (!bundledSnapshot) {
            setError('')
            setAttempt(value => value + 1)
          }
        }}
      />
      <Suspense fallback={<section className="load-state" role="status">Cargando vista…</section>}>
      {error && !snapshot ? <section className="panel load-state" role="alert"><CircleAlert size={34} /><span className="eyebrow">SNAPSHOT NO DISPONIBLE</span><h1>No pudimos cargar los datos.</h1><p>Comprueba que <code>data/delivery.json</code> y sus fragmentos está disponible en este despliegue o importa un snapshot compatible. No se muestran datos de ejemplo.</p><p className="error-reason">{error}</p><button className="primary-button" onClick={() => { setError(''); setAttempt(value => value + 1) }}><RefreshCw size={16} /> Volver a intentar</button></section>
        : !snapshot ? <section className="load-state" role="status"><LoaderCircle className="loading-spinner" size={32} /><h1>Cargando los datos.</h1><p>Preparando configuraciones y fuentes del snapshot del corpus.</p></section>
        : view === 'overview' ? <Overview key={datasetVersion} snapshot={snapshot} onProfiles={openProfiles} onEvidence={() => navigate('evidence')} />
        : view === 'profiles' ? <Profiles key={datasetVersion} snapshot={snapshot} filters={filters} onFilters={setFilters} />
        : <EvidenceBoundary key={datasetVersion} snapshot={snapshot}>{complete=><Evidence snapshot={complete}/>}</EvidenceBoundary>}
      </Suspense>
      </SnapshotResource.Provider>
      <footer className="workspace-footer"><span>Perfiles de referencia · {importedSnapshot ? 'snapshot importado' : 'corpus estático'}{snapshot ? ` · ${number(snapshot.stats.profiles)} referencias; candidatas derivadas aparte` : ''}</span><a href="#evidence">Sobre los datos <ArrowRight size={13} /></a></footer>
    </main></div>
  </div>
}
