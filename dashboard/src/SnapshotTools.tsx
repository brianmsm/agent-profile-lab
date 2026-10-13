import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { Download, RotateCcw } from 'lucide-react'
import type { Snapshot } from './data'
import { downloadFile } from './snapshotIO'
import { importSnapshot } from './snapshotClient'
import { useContext } from 'react'
import { SnapshotResource } from './snapshotResourceContext'

interface Props {
  snapshot: Snapshot | null
  onImport: (snapshot: Snapshot) => void
  onRestore: () => void
  isImported: boolean
}

interface ImportNotice {
  kind: 'success' | 'error'
  text: string
}

export default function SnapshotTools({ snapshot, onImport, onRestore, isImported }: Props) {
  const loadComplete=useContext(SnapshotResource)
  const [busy,setBusy]=useState(false)
  const [notice, setNotice] = useState<ImportNotice | null>(null)
  const importSequence = useRef(0)
  useEffect(() => () => { importSequence.current += 1 }, [])
  const sourceLabel = isImported ? 'Snapshot importado · solo esta sesión' : snapshot ? 'Snapshot del proyecto' : 'Snapshot no disponible'

  const importFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file) return
    const request = ++importSequence.current
    setBusy(true);setNotice({kind:'success',text:'Validando la importación en un procesador separado…'})
    try {
      const imported = await importSnapshot(file)
      if (request !== importSequence.current) return
      onImport(imported)
      setNotice({ kind: 'success', text: `Snapshot importado: ${file.name}. El cambio solo se conserva durante esta sesión.` })
    } catch (error) {
      if (request !== importSequence.current) return
      setNotice({ kind: 'error', text: error instanceof Error ? error.message : 'No se pudo leer el snapshot.' })
    } finally { if(request===importSequence.current)setBusy(false) }
  }

  const exportSnapshot = async () => {
    if (!snapshot) return
    const request=++importSequence.current
    setBusy(true);setNotice({kind:'success',text:'Preparando el conjunto completo; incluye toda la evidencia.'})
    try {
      const full=loadComplete?await loadComplete():snapshot
      if(request!==importSequence.current)return
      downloadFile('gentle-assess-snapshot.json', `${JSON.stringify(full, null, 2)}\n`, 'application/json;charset=utf-8')
      setNotice({kind:'success',text:'Se ha descargado el snapshot completo activo, incluida su evidencia.'})
    } catch(error){if(request===importSequence.current)setNotice({kind:'error',text:error instanceof Error?error.message:'Error de exportación'})}
    finally{if(request===importSequence.current)setBusy(false)}
  }

  return <details className="snapshot-tools">
    <summary className="snapshot-tools-heading">Datos: importar o exportar <span className="tag">{sourceLabel}</span></summary>
    <p className="section-description">Importa un JSON con portfolios, perfiles y referencias válidos, o guarda una copia completa del conjunto activo. La importación solo vive en esta pestaña y no cambia archivos del proyecto.</p>
    <div className="transfer-actions">
      <label className="import-control">Importar snapshot compatible
        <input type="file" accept="application/json,.json" aria-label="Importar snapshot JSON" onChange={importFile} />
      </label>
      <button className="text-button" type="button" onClick={exportSnapshot} disabled={!snapshot||busy}><Download size={15} /> Exportar snapshot completo</button>
      <button className="text-button" type="button" onClick={() => {
        importSequence.current += 1;setBusy(false)
        setNotice({ kind: 'success', text: 'Se ha solicitado restaurar el snapshot del proyecto.' })
        onRestore()
      }}><RotateCcw size={15} /> Restaurar snapshot del proyecto</button>
    </div>
    {notice && <p className="transfer-notice" role={notice.kind === 'error' ? 'alert' : 'status'}>{notice.text}</p>}
  </details>
}
