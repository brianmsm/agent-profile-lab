import type { Snapshot } from './data'
import { METRIC_LABELS, DIRECTION_LABELS } from './benchmarkTypes'
import modelLinks from '../../catalog/benchmark-model-links.json'
import modelCatalog from '../../catalog/models.json'
function object(value: unknown, label: string): asserts value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value) || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw new Error(`${label}: se requiere objeto propio, no heredado.`)
}
function fields(value: unknown, names: string[], label: string) {
  object(value, label)
  if (names.some(name => !Object.hasOwn(value, name))) throw new Error(`${label}: faltan campos propios.`)
}
function count(value: unknown, label: string) {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new Error(`${label}: contador inválido.`)
}
function strings(value: unknown, label: string): asserts value is string[] {
  if (!Array.isArray(value) || value.some(x => typeof x !== 'string' || !x)) throw new Error(`${label}: lista de textos requerida.`)
}
function own(map: object, key: unknown, label: string) {
  if (typeof key !== 'string' || !Object.hasOwn(map, key)) throw new Error(`${label}: referencia desconocida.`)
}
export function validateBenchmarkRegistry(snapshot: Snapshot) {
  const registry = snapshot.benchmarkRegistry
  if (!registry) {
    if (snapshot.benchmarks?.some(row => Object.hasOwn(row, 'measurement'))) throw new Error('No se pueden eliminar los contratos de métricas y mantener observaciones tipificadas.')
    return
  }
  fields(registry, ['schemaVersion','updateMode','suites','metrics','protocols','issues','stats','revisions','inputSha256','limitations','modelLinks'], 'benchmarkRegistry')
  if (registry.schemaVersion !== 1 || registry.updateMode !== 'manual') throw new Error('Versión o modo de actualización de benchmarks no admitido.')
  for (const name of ['suites','metrics','protocols','issues','stats','inputSha256'] as const) object(registry[name], name)
  strings(registry.limitations, 'benchmark limits')
  for (const [path, hash] of Object.entries(registry.inputSha256)) if (!path || !/^[a-f0-9]{64}$/u.test(hash)) throw new Error('Hash de entrada inválido.')
  for (const [id, suite] of Object.entries(registry.suites)) {
    fields(suite, ['id','label','domains','functions','priority','limitations','captures','coverage','lifecycle','updateMode'], id)
    if (suite.id !== id || suite.updateMode !== 'manual' || suite.lifecycle.routeCalibrated !== false) throw new Error('Suite incoherente o calibración runtime no acreditada.')
    strings(suite.domains,id);strings(suite.functions,id);strings(suite.limitations,id)
    object(suite.coverage,id);object(suite.lifecycle,id)
    for (const n of Object.values(suite.coverage)) count(n,id)
    if (Object.values(suite.lifecycle).some(x => typeof x !== 'boolean')) throw new Error('Estado de cobertura inválido.')
    if (!Array.isArray(suite.captures)) throw new Error('Capturas ausentes.')
  }
  for (const [id, metric] of Object.entries(registry.metrics)) {
    fields(metric,['id','suiteId','key','unit','kind','direction','denominator','aggregation'],id)
    if (metric.id !== id || !Object.hasOwn(METRIC_LABELS,metric.kind) || !Object.hasOwn(DIRECTION_LABELS,metric.direction)) throw new Error('Tipo/dirección de métrica inválido.')
    own(registry.suites,metric.suiteId,id)
    if (typeof metric.unit !== 'string' || !metric.unit || typeof metric.denominator !== 'string') throw new Error('Unidad/denominador ausente.')
  }
  for (const [id, p] of Object.entries(registry.protocols)) {
    fields(p,['id','suiteId','sourceId','version','captureRef','capturedAt','evaluationDate','priceAsOf','subset','tasks','trialsPerTask','harness','network','compaction','serverFallback','comparison','controls'],id)
    if (p.id !== id || !['source-local','paired-condition','not-established'].includes(p.comparison)) throw new Error('Protocolo inválido.')
    own(registry.suites,p.suiteId,id);object(p.controls,id)
    for (const n of [p.tasks,p.trialsPerTask]) if (n !== null) count(n,id)
    for (const d of [p.capturedAt,p.evaluationDate,p.priceAsOf]) if (d !== null && (typeof d !== 'string' || !/^\d{4}-\d{2}-\d{2}/u.test(d))) throw new Error('Fecha no declarada correctamente.')
  }
  const ids=new Map<string, string>(), pairs=new Map<string,string>(), kinds:Record<string,number>={}, scopes:Record<string,number>={}
  const suiteCounts:Record<string,number>={}
  for (const row of snapshot.benchmarks || []) {
    const m=row.measurement
    fields(m,['id','metricId','protocolId','evaluationId','modelId','modelRelation','candidateModelIds','kind','direction','scope','issueIds','costLinkId','primaryCost','decisionEligible'],'measurement')
    if (!m) throw new Error('Observación tipificada ausente.')
    own(registry.metrics,m.metricId,'metricId');own(registry.protocols,m.protocolId,'protocolId')
    const metric=registry.metrics[m.metricId],p=registry.protocols[m.protocolId]
    if (metric.kind !== m.kind || metric.direction !== m.direction || metric.unit !== row.unit || metric.suiteId !== p.suiteId || p.sourceId !== row.sourceId) throw new Error('Observación no coincide con la métrica, unidad o protocolo.')
    if (!['current','historical','superseded'].includes(m.scope) || !['published-label','candidate','unresolved'].includes(m.modelRelation)) throw new Error('Estado de evidencia desconocido.')
    strings(m.issueIds,'issues');strings(m.candidateModelIds,'model candidates')
    for (const id of m.issueIds) own(registry.issues,id,'issue')
    if (m.modelId !== null) {
      own(modelCatalog.models,m.modelId,'modelId')
      const sources=modelLinks.sourceLabels as Record<string,Record<string,{modelId:string}>>
      const labels=modelLinks.labels as Record<string,{modelId:string}>,slugs=modelLinks.aaSlugs as Record<string,{modelId:string}>
      const slug=typeof row.context?.slug === 'string' ? row.context.slug : ''
      const expected=sources[row.sourceId || '']?.[row.model] || slugs[slug] || labels[row.model]
      if (!expected || expected.modelId !== m.modelId || modelLinks.excludedVariantQualifiers.some(q => row.model.toLowerCase().includes(q.toLowerCase()))) throw new Error('Correspondencia de modelo publicada no acreditada por el registro de identidades.')
    }
    if (typeof m.decisionEligible !== 'boolean' || typeof m.primaryCost !== 'boolean') throw new Error('Elegibilidad debe ser booleana.')
    if (m.decisionEligible && (!['capability','index'].includes(m.kind) || !m.modelId || m.issueIds.length || m.scope !== 'current' || p.comparison === 'not-established')) throw new Error('No se puede promover evidencia problemática, histórica o sin protocolo.')
    if (ids.has(m.id)) throw new Error('ID de observación duplicado.');ids.set(m.id,m.scope)
    if (m.costLinkId !== null) {
      if (!m.evaluationId || (!['capability','index'].includes(m.kind) && !(m.kind === 'cost' && m.primaryCost))) throw new Error('Unión de coste sin registro experimental válido.')
      const key=JSON.stringify([m.evaluationId,m.protocolId,row.model,row.effort,row.sourceId])
      if (pairs.has(m.costLinkId) && pairs.get(m.costLinkId)!==key) throw new Error('Unión de coste cruza modelos, protocolos o fuentes.')
      pairs.set(m.costLinkId,key)
    }
    kinds[m.kind]=(kinds[m.kind]||0)+1;scopes[m.scope]=(scopes[m.scope]||0)+1;suiteCounts[metric.suiteId]=(suiteCounts[metric.suiteId]||0)+1
  }
  if (registry.stats.observations !== (snapshot.benchmarks||[]).length || registry.stats.routeCalibrations !== 0 || registry.stats.currentObservations !== (scopes.current||0)) throw new Error('Totales de evidencia inválidos.')
  for (const [key,value] of Object.entries(kinds)) if (registry.stats.metricKinds[key]!==value) throw new Error('Contador de tipos inválido.')
  for (const [key,value] of Object.entries(scopes)) if (registry.stats.scopeCounts[key]!==value) throw new Error('Contador de estados inválido.')
  for (const [id,s] of Object.entries(registry.suites)) if (s.coverage.observations!==(suiteCounts[id]||0)) throw new Error('Cobertura de suite no corresponde a sus observaciones.')
  if (!Array.isArray(registry.revisions)) throw new Error('Revisiones deben ser lista.')
  for (const r of registry.revisions) if (ids.get(r.previous)!=='superseded' || !ids.has(r.current) || r.notAnIndependentTrial!==true) throw new Error('Revisión sin linaje o marcada como ensayo independiente.')
}
