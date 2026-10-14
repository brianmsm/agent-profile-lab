import {parseStrictJSON} from './strictJSON'
import { validateBenchmarkRegistry } from './benchmarkValidation'
import { validateAccessSnapshot } from './accessRouting'
import { CYBER_RECONCILIATION_STATUSES, DOMAINS, OBJECTIVES } from './data'
import type { CybersecurityEvidence, CybersecurityReconciliation, CybersecurityResult, CyberReconciliationStatus, DomainContract, RouteDetail, Snapshot, SourceCoverage } from './data'

const LEGACY_CLAUDE_MESSAGE = 'Este snapshot usa el campo antiguo «anthropic», que no distingue Claude Pro de Max. No se ha importado. Regenera el archivo con `python3 scripts/build_dashboard_snapshot.py` y vuelve a seleccionarlo.'
const DOMAIN_CONTRACT_MESSAGE = 'No se ha importado. Regenera el snapshot con `python3 scripts/build_dashboard_snapshot.py` y vuelve a seleccionarlo.'
const MONEY_STRING = /^[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function requireString(value: unknown, path: string, allowEmpty = true): asserts value is string {
  if (typeof value !== 'string' || (!allowEmpty && value.trim() === '')) {
    throw new Error(`${path} debe ser ${allowEmpty ? 'texto' : 'texto no vacío'}.`)
  }
}

function requireStringArray(value: unknown, path: string): asserts value is string[] {
  if (!Array.isArray(value)) throw new Error(`${path} debe ser una lista de textos.`)
  for (const item of value) {
    if (typeof item !== 'string') throw new Error(`${path} debe ser una lista de textos.`)
  }
}

function requireNonnegativeInteger(value: unknown, path: string): asserts value is number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new Error(`${path} debe ser un entero no negativo.`)
  }
}

function requireMoney(value: unknown, path: string): asserts value is string {
  if (typeof value !== 'string' || !MONEY_STRING.test(value.trim())) {
    throw new Error(`${path} debe ser un importe numérico finito y no negativo.`)
  }
  const amount = Number(value)
  if (!Number.isFinite(amount) || amount < 0) {
    throw new Error(`${path} debe ser un importe numérico finito y no negativo.`)
  }
}

function requireRecord(value: unknown, path: string): asserts value is Record<string, unknown> {
  if (!isRecord(value)) throw new Error(`${path} debe ser un objeto.`)
}

function requireOwnFields(value: Record<string, unknown>, fields: string[], path: string) {
  for (const field of fields) {
    if (!Object.hasOwn(value, field)) throw new Error(`Falta ${path}.${field}.`)
  }
}
function requireOwnOptionalFields(value: Record<string, unknown>, fields: string[], path: string) {
  for (const field of fields) {
    if (field in value && !Object.hasOwn(value, field)) throw new Error(`${path}.${field} debe ser un campo propio.`)
  }
}


function requireSourceCoverage(value: unknown, snapshot: Snapshot): asserts value is SourceCoverage {
  const path = 'sourceCoverage'
  requireRecord(value, path)
  requireOwnFields(value, ['scope', 'generatedAt', 'totals', 'sources', 'artifacts', 'notes'], path)
  requireString(value.scope, `${path}.scope`, false)
  requireString(value.generatedAt, `${path}.generatedAt`, false)
  requireStringArray(value.notes, `${path}.notes`)
  requireRecord(value.totals, `${path}.totals`)
  requireOwnFields(value.totals, ['sources', 'artifacts', 'benchmarks', 'excluded'], `${path}.totals`)
  for (const key of ['sources', 'artifacts', 'benchmarks', 'excluded']) requireNonnegativeInteger(value.totals[key], `${path}.totals.${key}`)
  if (!Array.isArray(value.artifacts) || !Array.isArray(value.sources)) throw new Error('sourceCoverage.sources y artifacts deben ser listas.')
  const artifacts = new Set<string>()
  let excludedTotal = 0
  for (const [index, raw] of value.artifacts.entries()) {
    const at = `${path}.artifacts[${index}]`
    requireRecord(raw, at)
    requireOwnFields(raw, ['path', 'sha256', 'kind', 'observed', 'included', 'excluded', 'exclusions'], at)
    for (const key of ['path', 'sha256', 'kind']) requireString(raw[key], `${at}.${key}`, false)
    if (!/^[a-f0-9]{64}$/i.test(raw.sha256 as string)) throw new Error(`${at}.sha256 debe ser un hash hexadecimal de 64 caracteres.`)
    if (artifacts.has(raw.path as string)) throw new Error(`${at}.path está duplicado.`)
    artifacts.add(raw.path as string)
    for (const key of ['observed', 'included', 'excluded']) requireNonnegativeInteger(raw[key], `${at}.${key}`)
    const observed = raw.observed as number
    const included = raw.included as number
    const excluded = raw.excluded as number
    if (included > observed || excluded > observed - included) throw new Error(`${at}: included + excluded no puede superar observed.`)
    excludedTotal += excluded
    requireNonnegativeInteger(excludedTotal, `${path}.totalExcluded`)
    if (!Array.isArray(raw.exclusions)) throw new Error(`${at}.exclusions debe ser una lista.`)
    let explained = 0
    for (const [reasonIndex, reason] of raw.exclusions.entries()) {
      const reasonPath = `${at}.exclusions[${reasonIndex}]`
      requireRecord(reason, reasonPath)
      requireOwnFields(reason, ['locator', 'reason', 'count'], reasonPath)
      requireString(reason.locator, `${reasonPath}.locator`, false)
      requireString(reason.reason, `${reasonPath}.reason`, false)
      requireNonnegativeInteger(reason.count, `${reasonPath}.count`)
      explained += reason.count
    }
    if (!Number.isSafeInteger(explained) || explained > excluded) throw new Error(`${at}.exclusions supera el contador excluded.`)
  }
  const sources = new Map<string, number>()
  for (const [index, raw] of value.sources.entries()) {
    const at = `${path}.sources[${index}]`
    requireRecord(raw, at)
    requireOwnFields(raw, ['id', 'title', 'url', 'evidenceType', 'kind', 'status', 'checked', 'limitations', 'note', 'benchmarkCount', 'catalogReferences', 'portfolioReferences', 'assignmentReferences', 'artifacts'], at)
    for (const key of ['id', 'title', 'url', 'evidenceType', 'kind', 'status', 'checked', 'limitations', 'note']) requireString(raw[key], `${at}.${key}`, key !== 'id' && key !== 'title')
    if (!['benchmark', 'measurement', 'contract', 'code', 'user-evidence', 'assumption', 'press', 'telemetry', 'mirror', 'unknown'].includes(raw.kind as string)) throw new Error(`${at}.kind no está admitido.`)
    if (!['included', 'context-only', 'unavailable', 'superseded'].includes(raw.status as string)) throw new Error(`${at}.status no está admitido.`)
    for (const key of ['benchmarkCount', 'catalogReferences', 'portfolioReferences', 'assignmentReferences']) requireNonnegativeInteger(raw[key], `${at}.${key}`)
    requireStringArray(raw.artifacts, `${at}.artifacts`)
    const ownArtifacts = new Set<string>()
    for (const artifact of raw.artifacts) {
      if (!artifacts.has(artifact)) throw new Error(`${at}.artifacts apunta a un artifact inexistente: ${artifact}.`)
      if (ownArtifacts.has(artifact)) throw new Error(`${at}.artifacts contiene referencias duplicadas.`)
      ownArtifacts.add(artifact)
    }
    const id = raw.id as string
    if (sources.has(id)) throw new Error(`${at}.id está duplicado: ${id}.`)
    if (raw.benchmarkCount !== 0 && (raw.status !== 'included' || raw.kind === 'telemetry')) throw new Error(`${at}: una fuente de contexto, no disponible, sustituida o de telemetría no puede aportar benchmarks.`)
    sources.set(id, raw.benchmarkCount as number)
  }
  const counts = new Map<string, number>()
  for (const [index, benchmark] of (snapshot.benchmarks ?? []).entries()) {
    if (!Object.hasOwn(benchmark, 'sourceId') || !benchmark.sourceId || !sources.has(benchmark.sourceId)) throw new Error(`benchmarks[${index}].sourceId debe resolver a una fuente propia de sourceCoverage.`)
    counts.set(benchmark.sourceId, (counts.get(benchmark.sourceId) ?? 0) + 1)
  }
  for (const [id, source] of sources) {
    if (source !== (counts.get(id) ?? 0)) throw new Error(`sourceCoverage: benchmarkCount de ${id} no coincide con los benchmarks activos.`)
  }
  for (const [section, entries] of [['catalog', snapshot.catalog], ['portfolios', snapshot.portfolios]] as const) {
    for (const [id, entry] of Object.entries(entries)) {
      for (const sourceId of entry.sourceIds ?? []) {
        if (!sources.has(sourceId)) throw new Error(`${section}.${id}.sourceIds apunta a una fuente inexistente: ${sourceId}.`)
      }
    }
  }
  if (value.totals.sources !== value.sources.length || value.totals.artifacts !== value.artifacts.length
    || value.totals.benchmarks !== (snapshot.benchmarks ?? []).length || value.totals.excluded !== excludedTotal) {
    throw new Error('sourceCoverage.totals no coincide con las fuentes, artifacts y benchmarks del snapshot activo.')
  }
}

function requireCybersecurityEvidence(value: unknown, snapshot: Snapshot): asserts value is CybersecurityEvidence {
  const path = 'cybersecurityEvidence'
  requireRecord(value, path)
  requireOwnFields(value, ['schemaVersion', 'asOf', 'scope', 'routingConclusion', 'results', 'catalogCoverage'], path)
  if (value.schemaVersion !== 1) throw new Error(`${path}.schemaVersion no está admitido.`)
  for (const key of ['asOf', 'scope', 'routingConclusion']) requireString(value[key], `${path}.${key}`, false)
  if (!Array.isArray(value.results) || !Array.isArray(value.catalogCoverage)) throw new Error(`${path}.results y catalogCoverage deben ser listas.`)
  const rows = (snapshot.benchmarks ?? []).filter(row => row.value !== null && isRecord(row.context?.cybersecurity))
  const identity = (sourceId: unknown, provenance: unknown, model: unknown, benchmark: unknown, effort: unknown) =>
    JSON.stringify([sourceId, provenance, model, benchmark, effort])
  const normalized = new Map(rows.map(row => [identity(row.sourceId, row.provenance, row.model, row.benchmark, row.effort), row]))
  if (normalized.size !== rows.length) throw new Error(`${path}: hay identidades de resultados normalizados duplicadas.`)
  const sources = new Set(snapshot.sourceCoverage?.sources.map(source => source.id))
  const results = new Map<string, CybersecurityResult>()
  const linkedRows = new Set<string>()
  const matches = new Map<string, CybersecurityResult[]>()
  // Literal publisher abbreviations, not a family/version fallback.
  const publicationNames: Record<string, string> = { 'DS-V4.1-Flash': 'DeepSeek V4.1 Flash', K3: 'Kimi K3' }
  for (const [index, raw] of value.results.entries()) {
    const at = `${path}.results[${index}]`
    requireRecord(raw, at)
    requireOwnFields(raw, ['id', 'sourceId', 'sourceUrl', 'provenance', 'benchmark', 'benchmarkVersion', 'publishedModel', 'value', 'unit', 'effort', 'resultType', 'captureDate', 'evaluationDate', 'taskDenominator', 'attemptBudget', 'settings', 'limitations', 'catalogMatches', 'routeValidation'], at)
    for (const key of ['id', 'sourceId', 'sourceUrl', 'provenance', 'benchmark', 'publishedModel', 'unit', 'effort', 'resultType', 'captureDate', 'settings']) requireString(raw[key], `${at}.${key}`, false)
    for (const key of ['benchmarkVersion', 'evaluationDate', 'attemptBudget']) {
      if (raw[key] !== null) requireString(raw[key], `${at}.${key}`, false)
    }
    if (typeof raw.value !== 'number' || !Number.isFinite(raw.value)) throw new Error(`${at}.value debe ser un número finito.`)
    if (raw.taskDenominator !== null) {
      requireNonnegativeInteger(raw.taskDenominator, `${at}.taskDenominator`)
      if (raw.taskDenominator === 0) throw new Error(`${at}.taskDenominator debe ser positivo o null.`)
    }
    if (!['independent', 'vendor', 'vendor-comparator', 'editorial'].includes(raw.resultType as string)) throw new Error(`${at}.resultType no está admitido.`)
    if (raw.routeValidation !== 'not-established') throw new Error(`${at}.routeValidation no puede establecer eficacia ni calibración de rutas.`)
    requireStringArray(raw.limitations, `${at}.limitations`)
    let url: URL
    try { url = new URL(raw.sourceUrl as string) } catch { throw new Error(`${at}.sourceUrl debe ser una URL pública HTTP(S).`) }
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error(`${at}.sourceUrl debe ser una URL pública HTTP(S) sin credenciales.`)
    if (snapshot.sourceCoverage && !sources.has(raw.sourceId as string)) throw new Error(`${at}.sourceId no resuelve al registro de fuentes.`)
    const rowId = identity(raw.sourceId, raw.provenance, raw.publishedModel, raw.benchmark, raw.effort)
    const row = normalized.get(rowId)
    if (!row || row.value !== raw.value || row.unit !== raw.unit || row.source !== raw.sourceUrl) throw new Error(`${at}: el resultado no coincide con su benchmark normalizado y fuente original.`)
    const metadata = row.context!.cybersecurity as Record<string, unknown>
    for (const key of ['resultType', 'benchmarkVersion', 'evaluationDate', 'captureDate', 'taskDenominator', 'attemptBudget', 'settings', 'limitations']) {
      if (JSON.stringify(raw[key]) !== JSON.stringify(metadata[key])) throw new Error(`${at}.${key} no coincide con el contexto normalizado.`)
    }
    if (linkedRows.has(rowId)) throw new Error(`${at}: duplica un resultado publicado; no es otra muestra.`)
    linkedRows.add(rowId)
    if (results.has(raw.id as string)) throw new Error(`${at}.id está duplicado.`)
    if (!Array.isArray(raw.catalogMatches)) throw new Error(`${at}.catalogMatches debe ser una lista.`)
    const ownMatches = new Set<string>()
    for (const [matchIndex, match] of raw.catalogMatches.entries()) {
      const matchPath = `${at}.catalogMatches[${matchIndex}]`
      requireRecord(match, matchPath)
      requireOwnFields(match, ['catalogKey', 'relationship', 'reason'], matchPath)
      requireString(match.catalogKey, `${matchPath}.catalogKey`, false)
      requireString(match.reason, `${matchPath}.reason`, false)
      if (!Object.hasOwn(snapshot.catalog, match.catalogKey)) throw new Error(`${matchPath}.catalogKey no existe en el catálogo.`)
      if (ownMatches.has(match.catalogKey)) throw new Error(`${matchPath}.catalogKey está duplicado.`)
      ownMatches.add(match.catalogKey)
      if (!['published-model', 'candidate-alias'].includes(match.relationship as string)) throw new Error(`${matchPath}.relationship no está admitido.`)
      const publicationName = Object.hasOwn(publicationNames, raw.publishedModel as string) ? publicationNames[raw.publishedModel as string] : raw.publishedModel as string
      const model = snapshot.catalog[match.catalogKey]
      const knownAlias = (model.selector === 'nan/mimo-v2.5' && publicationName.toLocaleLowerCase('en').replace(/[\s-]+/g, '') === 'mimov2.5pro')
        || (model.selector === 'nan/deepseek-v4-flash' && publicationName.toLocaleLowerCase('en').replace(/[\s-]+/g, '') === 'deepseekv4.1flash')
      if (knownAlias && match.relationship !== 'candidate-alias') throw new Error(`${matchPath}: un alias no puede elevarse a published-model.`)
      if (match.relationship === 'candidate-alias' && !knownAlias) throw new Error(`${matchPath}: no hay correspondencia de alias candidato declarada para este selector y publicación.`)
      if (match.relationship === 'published-model' && publicationName.toLocaleLowerCase('en').replace(/[\s-]+/g, '') !== snapshot.catalog[match.catalogKey].name.toLocaleLowerCase('en').replace(/[\s-]+/g, '')) {
        throw new Error(`${matchPath}: un alias o una versión distinta no puede elevarse a published-model.`)
      }
      const linked = matches.get(match.catalogKey) ?? []
      linked.push(raw as unknown as CybersecurityResult)
      matches.set(match.catalogKey, linked)
    }
    results.set(raw.id as string, raw as unknown as CybersecurityResult)
  }
  if (linkedRows.size !== rows.length) throw new Error(`${path}: debe incorporar todos los resultados numéricos de ciberseguridad normalizados, sin omisiones.`)
  const latestCapture = [...results.values()].map(result => result.captureDate).sort().at(-1)
  if (latestCapture && value.asOf !== latestCapture) throw new Error(`${path}.asOf debe ser la última fecha de captura, no la fecha de ejecución.`)
  const covered = new Set<string>()
  for (const [index, raw] of value.catalogCoverage.entries()) {
    const at = `${path}.catalogCoverage[${index}]`
    requireRecord(raw, at)
    requireOwnFields(raw, ['catalogKey', 'state', 'resultIds', 'reason'], at)
    requireString(raw.catalogKey, `${at}.catalogKey`, false)
    requireString(raw.reason, `${at}.reason`, false)
    requireStringArray(raw.resultIds, `${at}.resultIds`)
    if (!Object.hasOwn(snapshot.catalog, raw.catalogKey) || covered.has(raw.catalogKey)) throw new Error(`${at}.catalogKey no existe o está duplicado.`)
    covered.add(raw.catalogKey)
    const linked = matches.get(raw.catalogKey) ?? []
    const expected = new Set(linked.map(result => result.id))
    if (new Set(raw.resultIds).size !== raw.resultIds.length || raw.resultIds.length !== expected.size || raw.resultIds.some(id => !expected.has(id))) throw new Error(`${at}.resultIds no coincide con las correspondencias publicadas.`)
    const exact = linked.filter(result => result.catalogMatches.some(match => match.catalogKey === raw.catalogKey && match.relationship === 'published-model'))
    const state = exact.some(result => result.resultType !== 'editorial') ? 'measured-result'
      : linked.some(result => result.resultType !== 'editorial') ? 'candidate-alias-only'
        : linked.length ? 'editorial-only' : 'no-mapped-result'
    if (raw.state !== state) throw new Error(`${at}.state no coincide con los resultados, alias y contexto editorial.`)
  }
  if (covered.size !== Object.keys(snapshot.catalog).length) throw new Error(`${path}.catalogCoverage debe cubrir cada entrada del catálogo, incluidas las no utilizadas.`)
  requireOwnOptionalFields(value, ['reconciliation'], path)
  if (Object.hasOwn(value, 'reconciliation')) requireCybersecurityReconciliation(value.reconciliation, snapshot, results)
}

function requireCybersecurityReconciliation(value: unknown, snapshot: Snapshot, results: Map<string, CybersecurityResult>): asserts value is CybersecurityReconciliation {
  const path = 'cybersecurityEvidence.reconciliation'
  requireRecord(value, path)
  requireOwnFields(value, ['schemaVersion', 'asOf', 'scope', 'searchBoundary', 'reviewedSources', 'entries', 'catalogReview', 'counts', 'closure'], path)
  if (value.schemaVersion !== 1) throw new Error(`${path}.schemaVersion no está admitido.`)
  for (const key of ['scope', 'searchBoundary']) requireString(value[key], `${path}.${key}`, false)
  const requireDate = (raw: unknown, at: string) => {
    requireString(raw, at, false)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(raw) || !Number.isFinite(Date.parse(raw)) || new Date(raw).toISOString().slice(0, 10) !== raw) throw new Error(`${at} debe ser una fecha ISO válida.`)
  }
  const requireUrl = (raw: unknown, at: string) => {
    requireString(raw, at, false)
    let url: URL
    try { url = new URL(raw) } catch { throw new Error(`${at} debe ser una URL pública HTTP(S).`) }
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error(`${at} debe ser una URL pública HTTP(S) sin credenciales.`)
  }
  const requireUniqueReferences = (raw: unknown, allowed: Set<string>, at: string) => {
    requireStringArray(raw, at)
    if (new Set(raw).size !== raw.length || raw.some(id => !allowed.has(id))) throw new Error(`${at} contiene referencias desconocidas o duplicadas.`)
  }
  requireDate(value.asOf, `${path}.asOf`)
  if (!snapshot.sourceCoverage) throw new Error(`${path} requiere el registro sourceCoverage y sus artefactos de captura.`)
  if (!Array.isArray(value.reviewedSources) || !Array.isArray(value.entries) || !Array.isArray(value.catalogReview)) throw new Error(`${path}: reviewedSources, entries y catalogReview deben ser listas.`)
  const registered = new Map(snapshot.sourceCoverage.sources.map(source => [source.id, source]))
  const catalogKeys = new Set(Object.keys(snapshot.catalog))
  const reviewed = new Map<string, { sourceUrl: string; artifacts: Set<string> }>()
  for (const [index, raw] of value.reviewedSources.entries()) {
    const at = `${path}.reviewedSources[${index}]`
    requireRecord(raw, at)
    requireOwnFields(raw, ['sourceId', 'sourceUrl', 'captureDate', 'receiptPath', 'sections', 'catalogKeys', 'limitations'], at)
    for (const key of ['sourceId', 'receiptPath']) requireString(raw[key], `${at}.${key}`, false)
    requireUrl(raw.sourceUrl, `${at}.sourceUrl`)
    requireDate(raw.captureDate, `${at}.captureDate`)
    if ((raw.captureDate as string) > (value.asOf as string)) throw new Error(`${at}.captureDate no puede ser posterior al corte del corpus.`)
    requireStringArray(raw.sections, `${at}.sections`)
    requireStringArray(raw.limitations, `${at}.limitations`)
    requireUniqueReferences(raw.catalogKeys, catalogKeys, `${at}.catalogKeys`)
    const source = registered.get(raw.sourceId as string)
    if (!source || reviewed.has(raw.sourceId as string)) throw new Error(`${at}.sourceId no resuelve al registro o está duplicado.`)
    const artifacts = new Set(source.artifacts.map(item => item))
    if (source.url !== raw.sourceUrl || !artifacts.has((raw.receiptPath as string))) throw new Error(`${at}: la URL y el receipt deben pertenecer a la fuente registrada.`)
    if (!raw.sections.length || new Set(raw.sections).size !== raw.sections.length || raw.sections.some(section => {
      const separator = section.indexOf('#')
      return separator < 1 || separator === section.length - 1 || !artifacts.has(section.slice(0, separator))
    })) throw new Error(`${at}.sections requiere localizadores únicos de artefactos propios con sección explícita.`)
    reviewed.set(raw.sourceId as string, { sourceUrl: raw.sourceUrl as string, artifacts })
  }
  const reviewedIds = new Set(reviewed.keys())
  const entryIds = new Set<string>()
  const linkedResults = new Set<string>()
  const dispositions = new Set<string>()
  const disposedSources = new Set<string>()
  const counts: Record<CyberReconciliationStatus, number> = { incorporated: 0, 'context-only': 0, excluded: 0, 'not-published': 0, unresolved: 0 }
  for (const [index, raw] of value.entries.entries()) {
    const at = `${path}.entries[${index}]`
    requireRecord(raw, at)
    requireOwnFields(raw, ['id', 'sourceId', 'sourceUrl', 'publishedModel', 'benchmark', 'metric', 'status', 'reason', 'locator', 'resultIds'], at)
    for (const key of ['id', 'sourceId', 'benchmark', 'metric', 'status', 'reason', 'locator']) requireString(raw[key], `${at}.${key}`, false)
    requireUrl(raw.sourceUrl, `${at}.sourceUrl`)
    if (raw.publishedModel !== null) requireString(raw.publishedModel, `${at}.publishedModel`, false)
    requireStringArray(raw.resultIds, `${at}.resultIds`)
    if (!CYBER_RECONCILIATION_STATUSES.includes(raw.status as CyberReconciliationStatus)) throw new Error(`${at}.status no está admitido.`)
    if (!/^reconcile-[a-f0-9]{24}$/.test(raw.id as string)) throw new Error(`${at}.id debe ser un identificador hash de reconciliación.`)
    if (entryIds.has(raw.id as string)) throw new Error(`${at}.id está duplicado.`)
    entryIds.add(raw.id as string)
    const source = reviewed.get(raw.sourceId as string)
    if (!source || (raw.status !== 'incorporated' && source.sourceUrl !== raw.sourceUrl)) throw new Error(`${at}: sourceId y sourceUrl deben resolver a una fuente revisada.`)
    disposedSources.add(raw.sourceId as string)
    if (!source.artifacts.has((raw.locator as string).split('#')[0])) throw new Error(`${at}.locator no pertenece a los artefactos de la fuente revisada.`)
    const disposition = JSON.stringify([raw.sourceId, raw.publishedModel, raw.benchmark, raw.metric, raw.status, raw.locator, raw.resultIds])
    if (dispositions.has(disposition)) throw new Error(`${at}: disposición duplicada; no constituye otra revisión.`)
    dispositions.add(disposition)
    counts[raw.status as CyberReconciliationStatus]++
    if (raw.status === 'incorporated') {
      const result = raw.resultIds.length === 1 ? results.get(raw.resultIds[0]) : undefined
      if (!result || linkedResults.has(result.id) || result.sourceId !== raw.sourceId || result.sourceUrl !== raw.sourceUrl
        || result.publishedModel !== raw.publishedModel || result.benchmark !== raw.benchmark || result.benchmark !== raw.metric
        || result.provenance !== raw.locator) {
        throw new Error(`${at}: incorporated requiere un único resultado real con fuente, modelo, métrica y localizador exactos.`)
      }
      linkedResults.add(result.id)
    } else {
      if (raw.resultIds.length) throw new Error(`${at}: una disposición sin resultado incorporado no puede vincular resultIds.`)
      const separator = (raw.locator as string).indexOf('#')
      if (separator < 1 || separator === (raw.locator as string).length - 1) throw new Error(`${at}.locator debe identificar una sección explícita del artefacto revisado.`)
    }
  }
  if (linkedResults.size !== results.size) throw new Error(`${path}: cada resultado del grafo debe tener una única entrada incorporated.`)
  if ([...reviewedIds].some(sourceId => !disposedSources.has(sourceId))) throw new Error(`${path}: cada fuente revisada requiere al menos una disposición explícita.`)
  const catalogReviewed = new Set<string>()
  let pendingCatalogReview = false
  for (const [index, raw] of value.catalogReview.entries()) {
    const at = `${path}.catalogReview[${index}]`
    requireRecord(raw, at)
    requireOwnFields(raw, ['catalogKey', 'sourceIds', 'conclusion'], at)
    requireString(raw.catalogKey, `${at}.catalogKey`, false)
    requireString(raw.conclusion, `${at}.conclusion`, false)
    if (!catalogKeys.has(raw.catalogKey) || catalogReviewed.has(raw.catalogKey)) throw new Error(`${at}.catalogKey no existe o está duplicado.`)
    requireUniqueReferences(raw.sourceIds, reviewedIds, `${at}.sourceIds`)
    const state = raw.reviewState ?? 'reviewed'
    if (state !== 'pending' && state !== 'reviewed') throw new Error(`${at}: estado de revisión desconocido.`)
    if (state === 'pending') {
      if ((raw.sourceIds as string[]).length) throw new Error(`${at}: una revisión pendiente no acredita fuentes revisadas.`)
      pendingCatalogReview = true
    } else if (!(raw.sourceIds as string[]).length) throw new Error(`${at}: revisión declarada sin fuentes.`)
    catalogReviewed.add(raw.catalogKey)
  }
  if (catalogReviewed.size !== catalogKeys.size) throw new Error(`${path}.catalogReview debe cubrir todo el catálogo, incluidos los selectores sin resultados.`)
  requireRecord(value.counts, `${path}.counts`)
  requireOwnFields(value.counts, [...CYBER_RECONCILIATION_STATUSES], `${path}.counts`)
  if (Object.keys(value.counts).some(key => !CYBER_RECONCILIATION_STATUSES.includes(key as CyberReconciliationStatus))) throw new Error(`${path}.counts contiene estados desconocidos.`)
  for (const status of CYBER_RECONCILIATION_STATUSES) {
    requireNonnegativeInteger(value.counts[status], `${path}.counts.${status}`)
    if (value.counts[status] !== counts[status]) throw new Error(`${path}.counts.${status} no coincide con las disposiciones.`)
  }
  if (value.closure !== (counts.unresolved || pendingCatalogReview ? 'open' : 'reconciled-corpus')) throw new Error(`${path}.closure no coincide con los asuntos pendientes del corpus.`)
}

function requireDomainContract(value: unknown, domain: string): asserts value is DomainContract {
  const path = `domainContracts.${domain}`
  try {
    requireRecord(value, path)
    for (const key of ['label', 'gate', 'critical', 'routine', 'scope']) {
      if (!Object.hasOwn(value, key)) throw new Error(`Falta ${path}.${key}.`)
      requireString(value[key], `${path}.${key}`, false)
    }
    if (domain === 'cybersecurity' && !Object.hasOwn(value, 'evidenceNote')) {
      throw new Error(`Falta ${path}.evidenceNote: el dominio necesita límites de evidencia explícitos.`)
    }
    if (Object.hasOwn(value, 'evidenceNote')) requireString(value.evidenceNote, `${path}.evidenceNote`, false)
    requireOwnOptionalFields(value, ['evidenceBoundary'], path)
    if (Object.hasOwn(value, 'evidenceBoundary')) {
      const boundary = value.evidenceBoundary
      requireRecord(boundary, `${path}.evidenceBoundary`)
      const fields = { routingBasis: 'Apps-derived', publishedEvidence: 'published-results-present', routeCalibration: 'route-calibration-not-established', validationMeaning: 'structural-validation-not-efficacy' }
      requireOwnFields(boundary, Object.keys(fields), `${path}.evidenceBoundary`)
      for (const [key, expected] of Object.entries(fields)) {
        if (boundary[key] !== expected) throw new Error(`${path}.evidenceBoundary.${key} no está admitido.`)
      }
    }
  } catch (error) {
    throw new Error(`${error instanceof Error ? error.message : `Contrato inválido: ${path}.`} ${DOMAIN_CONTRACT_MESSAGE}`)
  }
}

export function validateSnapshot(input: unknown): Snapshot {
  requireRecord(input, 'El snapshot')
  for (const key of ['stats', 'portfolios', 'catalog', 'coverage', 'meta', 'routing', 'routeDetails', 'runtimePolicies', 'strategies']) {
    if (!Object.hasOwn(input, key)) throw new Error(`Falta el campo obligatorio «${key}» del snapshot. ${DOMAIN_CONTRACT_MESSAGE}`)
  }
  for (const field of ['sourceCoverage', 'benchmarks', 'provenance', 'cybersecurityEvidence', 'access', 'benchmarkRegistry']) {
    if (field in input && !Object.hasOwn(input, field)) throw new Error(`${field} debe ser un campo propio del snapshot.`)
  }
  if (!Object.hasOwn(input, 'domainContracts') || !isRecord(input.domainContracts) || !Object.keys(input.domainContracts).length) {
    throw new Error(`Falta un mapa domainContracts con contratos de dominio útiles. ${DOMAIN_CONTRACT_MESSAGE}`)
  }
  for (const [domain, contract] of Object.entries(input.domainContracts)) {
    if (!domain.trim()) throw new Error(`Hay un contrato de dominio sin identificador. ${DOMAIN_CONTRACT_MESSAGE}`)
    requireDomainContract(contract, domain)
  }
  requireRecord(input.stats, 'stats')
  const stats = input.stats
  for (const key of ['rows', 'profiles', 'portfolios', 'models', 'groups']) {
    requireNonnegativeInteger(stats[key], `stats.${key}`)
  }
  requireString(stats.session, 'stats.session', false)
  requireRecord(stats.validators, 'stats.validators')
  requireNonnegativeInteger(stats.validators.passed, 'stats.validators.passed')
  requireNonnegativeInteger(stats.validators.failed, 'stats.validators.failed')

  requireRecord(input.portfolios, 'portfolios')
  for (const [id, raw] of Object.entries(input.portfolios)) {
    if (!id.trim()) throw new Error('Hay un portfolio sin identificador.')
    requireRecord(raw, `portfolios.${id}`)
    const portfolio = raw
    if (!Object.hasOwn(portfolio, 'claude') && Object.hasOwn(portfolio, 'anthropic')) {
      throw new Error(LEGACY_CLAUDE_MESSAGE)
    }
    requireString(portfolio.label, `portfolios.${id}.label`, false)
    requireMoney(portfolio.usd, `portfolios.${id}.usd`)
    requireMoney(portfolio.eur, `portfolios.${id}.eur`)
    if (typeof portfolio.openai !== 'string' || !['none', 'plus', 'pro100'].includes(portfolio.openai)) {
      throw new Error(`portfolios.${id}.openai debe ser none, plus o pro100.`)
    }
    if (typeof portfolio.claude !== 'string' || !['none', 'pro', 'max'].includes(portfolio.claude)) {
      throw new Error(`portfolios.${id}.claude debe ser none, pro o max.`)
    }
    if (typeof portfolio.gateway !== 'string' || !['none', 'cc', 'go'].includes(portfolio.gateway)) {
      throw new Error(`portfolios.${id}.gateway debe ser none, cc o go.`)
    }
    if (portfolio.nan !== 'True' && portfolio.nan !== 'False') {
      throw new Error(`portfolios.${id}.nan debe ser "True" o "False".`)
    }
    if (Object.hasOwn(portfolio, 'notes')) requireString(portfolio.notes, `portfolios.${id}.notes`)
    requireOwnOptionalFields(portfolio, ['sourceIds'], `portfolios.${id}`)
    if (Object.hasOwn(portfolio, 'sourceIds')) requireStringArray(portfolio.sourceIds, `portfolios.${id}.sourceIds`)
  }

  requireRecord(input.catalog, 'catalog')
  const modelNames = new Set<string>()
  for (const [key, raw] of Object.entries(input.catalog)) {
    if (!key.trim()) throw new Error('Hay una entrada de catálogo sin identificador.')
    requireRecord(raw, `catalog.${key}`)
    requireOwnFields(raw, ['name', 'pool', 'selector', 'efforts', 'vision', 'evidence', 'integration'], `catalog.${key}`)
    const model = raw
    requireString(model.name, `catalog.${key}.name`, false)
    requireString(model.pool, `catalog.${key}.pool`, false)
    requireString(model.selector, `catalog.${key}.selector`, false)
    requireStringArray(model.efforts, `catalog.${key}.efforts`)
    if (model.vision !== null && typeof model.vision !== 'boolean') {
      throw new Error(`catalog.${key}.vision debe ser true, false o null.`)
    }
    requireString(model.evidence, `catalog.${key}.evidence`)
    requireString(model.integration, `catalog.${key}.integration`)
    if (Object.hasOwn(model, 'notes')) requireString(model.notes, `catalog.${key}.notes`)
    requireOwnOptionalFields(model, ['sourceIds', 'sourceUrls'], `catalog.${key}`)
    if (Object.hasOwn(model, 'sourceIds')) requireStringArray(model.sourceIds, `catalog.${key}.sourceIds`)
    if (Object.hasOwn(model, 'sourceUrls')) requireStringArray(model.sourceUrls, `catalog.${key}.sourceUrls`)
    modelNames.add(model.name)
  }

  requireRecord(input.coverage, 'coverage')
  for (const [family, raw] of Object.entries(input.coverage)) {
    requireRecord(raw, `coverage.${family}`)
    for (const [domain, value] of Object.entries(raw)) {
      requireString(value, `coverage.${family}.${domain}`)
    }
  }

  requireRecord(input.meta, 'meta')
  for (const [pid, raw] of Object.entries(input.meta)) {
    if (!pid.trim()) throw new Error('Hay un perfil sin identificador.')
    requireRecord(raw, `meta.${pid}`)
    requireOwnFields(raw, ['portfolio', 'harness', 'domain', 'objective'], `meta.${pid}`)
    const meta = raw
    requireString(meta.portfolio, `meta.${pid}.portfolio`, false)
    requireString(meta.harness, `meta.${pid}.harness`, false)
    if (!['omp', 'gentle-shell'].includes(meta.harness)) throw new Error(`meta.${pid}.harness no está admitido.`)
    requireString(meta.domain, `meta.${pid}.domain`, false)
    requireString(meta.objective, `meta.${pid}.objective`, false)
    if (!Object.hasOwn(input.portfolios, meta.portfolio)) {
      throw new Error(`meta.${pid}.portfolio apunta a un portfolio inexistente.`)
    }
    if (!Object.hasOwn(DOMAINS, meta.domain)) {
      throw new Error(`meta.${pid}.domain no está admitido por esta versión del dashboard.`)
    }
    if (!Object.hasOwn(input.domainContracts, meta.domain)) {
      throw new Error(`meta.${pid}.domain no tiene contrato propio en domainContracts. ${DOMAIN_CONTRACT_MESSAGE}`)
    }
    if (!Object.hasOwn(OBJECTIVES, meta.objective)) {
      throw new Error(`meta.${pid}.objective no está admitido por esta versión del dashboard.`)
    }
  }

  requireRecord(input.routing, 'routing')
  let distinctAssignments = 0
  for (const [pid, raw] of Object.entries(input.routing)) {
    if (!Object.hasOwn(input.meta, pid)) throw new Error(`routing.${pid} no tiene meta de perfil.`)
    requireRecord(raw, `routing.${pid}`)
    for (const [role, route] of Object.entries(raw)) {
      if (!role.trim()) throw new Error(`routing.${pid} contiene un rol vacío.`)
      if (!Array.isArray(route) || route.length !== 2) {
        throw new Error(`routing.${pid}.${role} debe ser [modelo, esfuerzo].`)
      }
      const [model, effort] = route
      requireString(model, `routing.${pid}.${role}[0]`, false)
      requireString(effort, `routing.${pid}.${role}[1]`)
      if (!modelNames.has(model)) throw new Error(`routing.${pid}.${role} apunta a un modelo ausente del catálogo.`)
      distinctAssignments += 1
    }
  }
  for (const pid of Object.keys(input.meta)) {
    if (!Object.hasOwn(input.routing, pid)) throw new Error(`El perfil ${pid} no tiene una entrada routing.`)
  }

  requireRecord(input.routeDetails, 'routeDetails')
  requireRecord(input.runtimePolicies, 'runtimePolicies')
  requireRecord(input.strategies, 'strategies')
  const catalog = input.catalog
  const requireRoute = (raw: unknown, path: string) => {
    requireRecord(raw, path)
    requireOwnFields(raw, ['modelKey', 'effort', 'fallback', 'accelerator', 'enabled', 'condition', 'rationale'], path)
    const requireSelection = (selection: Record<string, unknown>, at: string) => {
      requireOwnFields(selection, ['modelKey', 'effort'], at)
      requireString(selection.modelKey, `${at}.modelKey`, false)
      requireString(selection.effort, `${at}.effort`)
      if (!Object.hasOwn(catalog, selection.modelKey)) throw new Error(`${at}.modelKey no resuelve al catálogo.`)
      const model = catalog[selection.modelKey] as { efforts: string[] }
      if (selection.effort !== '' && !model.efforts.includes(selection.effort)) throw new Error(`${at}.effort no está admitido por el modelo.`)
    }
    requireSelection(raw, path)
    for (const auxiliary of ['fallback', 'accelerator']) {
      if (raw[auxiliary] !== null) {
        requireRecord(raw[auxiliary], `${path}.${auxiliary}`)
        requireSelection(raw[auxiliary], `${path}.${auxiliary}`)
      }
    }
    if (typeof raw.enabled !== 'boolean') throw new Error(`${path}.enabled debe ser booleano.`)
    requireString(raw.condition, `${path}.condition`)
    requireString(raw.rationale, `${path}.rationale`)
  }
  for (const pid of Object.keys(input.meta)) {
    if (!Object.hasOwn(input.routeDetails, pid) || !Object.hasOwn(input.runtimePolicies, pid)) throw new Error(`Falta ruta detallada o política runtime de ${pid}. ${DOMAIN_CONTRACT_MESSAGE}`)
    const details = input.routeDetails[pid]
    requireRecord(details, `routeDetails.${pid}`)
    const routing = input.routing[pid] as Record<string, [string, string]>
    if (Object.keys(details).length !== Object.keys(routing).length) throw new Error(`routeDetails.${pid} no coincide con routing.`)
    const meta = input.meta[pid] as { harness: string }
    const policy = input.runtimePolicies[pid]
    if (meta.harness === 'gentle-shell') {
      if (policy !== null) throw new Error(`runtimePolicies.${pid} debe ser null para Gentle.`)
    } else {
      requireRecord(policy, `runtimePolicies.${pid}`)
      requireOwnFields(policy, ['advisorEnabled', 'taskMaxConcurrency'], `runtimePolicies.${pid}`)
      if (typeof policy.advisorEnabled !== 'boolean') throw new Error(`runtimePolicies.${pid}.advisorEnabled debe ser booleano.`)
      requireNonnegativeInteger(policy.taskMaxConcurrency, `runtimePolicies.${pid}.taskMaxConcurrency`)
      if (policy.taskMaxConcurrency === 0) throw new Error(`runtimePolicies.${pid}.taskMaxConcurrency debe ser positivo.`)
    }
    for (const [role, detail] of Object.entries(details)) {
      requireRoute(detail, `routeDetails.${pid}.${role}`)
      // Every RouteDetail field and catalog reference was checked above.
      const route = detail as unknown as RouteDetail
      const model = catalog[route.modelKey] as { name: string }
      if (!Object.hasOwn(routing, role) || routing[role][0] !== model.name || routing[role][1] !== route.effort) throw new Error(`routeDetails.${pid}.${role} no coincide con routing canónico.`)
      const disabledAdvisor = isRecord(policy) && policy.advisorEnabled === false && ['advisor', 'advisor_deep'].includes(role)
      if (route.enabled !== !disabledAdvisor) throw new Error(`routeDetails.${pid}.${role}.enabled contradice la política runtime.`)
    }
  }
  for (const key of Object.keys(input.routeDetails)) if (!Object.hasOwn(input.meta, key)) throw new Error(`routeDetails.${key} no tiene meta.`)
  for (const key of Object.keys(input.runtimePolicies)) if (!Object.hasOwn(input.meta, key)) throw new Error(`runtimePolicies.${key} no tiene meta.`)
  for (const [id, raw] of Object.entries(input.strategies)) {
    requireRecord(raw, `strategies.${id}`)
    requireOwnFields(raw, ['kind', 'sourceProfile', 'portfolio', 'routes', 'coordinatorPool', 'offloadPool', 'limitations'], `strategies.${id}`)
    if (!['openai-led', 'nan-volume'].includes(raw.kind as string)) throw new Error(`strategies.${id}.kind inválido.`)
    requireString(raw.sourceProfile, `strategies.${id}.sourceProfile`, false)
    requireString(raw.portfolio, `strategies.${id}.portfolio`, false)
    requireString(raw.coordinatorPool, `strategies.${id}.coordinatorPool`, false)
    if (raw.offloadPool !== null) requireString(raw.offloadPool, `strategies.${id}.offloadPool`, false)
    requireStringArray(raw.limitations, `strategies.${id}.limitations`)
    if (!Object.hasOwn(input.meta, raw.sourceProfile) || !Object.hasOwn(input.portfolios, raw.portfolio)) throw new Error(`strategies.${id} contiene referencias ausentes.`)
    if (id !== `${raw.sourceProfile}::${raw.kind}` || Object.hasOwn(input.meta, id)) throw new Error(`strategies.${id} tiene identidad inválida.`)
    const meta = input.meta[raw.sourceProfile] as { domain: string; portfolio: string; harness: string }
    const sourcePortfolio = input.portfolios[meta.portfolio] as { openai: string; claude: string; gateway: string; nan: string }
    const portfolio = input.portfolios[raw.portfolio] as typeof sourcePortfolio
    if (!['plus', 'pro100'].includes(sourcePortfolio.openai) || sourcePortfolio.claude !== 'none' || sourcePortfolio.gateway !== 'none' || sourcePortfolio.nan !== 'False') throw new Error(`strategies.${id} necesita baseline OpenAI-only.`)
    if (portfolio.openai !== sourcePortfolio.openai || portfolio.claude !== 'none' || portfolio.gateway !== 'none' || portfolio.nan !== (raw.kind === 'nan-volume' ? 'True' : 'False')) throw new Error(`strategies.${id}.portfolio no es el mínimo requerido.`)
    if (raw.coordinatorPool !== 'OAI' || raw.offloadPool !== (raw.kind === 'nan-volume' ? 'NAN' : null)) throw new Error(`strategies.${id} declara pools inválidos.`)
    if (raw.kind === 'nan-volume' && ['agent-use', 'cybersecurity'].includes(meta.domain)) throw new Error(`strategies.${id}: NaN-volume no está aprobado para este dominio.`)
    requireRecord(raw.routes, `strategies.${id}.routes`)
    // Baseline details have already passed the route validator.
    const baseline = input.routeDetails[raw.sourceProfile] as Record<string, RouteDetail>
    if (Object.keys(raw.routes).length !== Object.keys(baseline).length) throw new Error(`strategies.${id} altera los roles del baseline.`)
    let changed = false
    for (const [role, detail] of Object.entries(raw.routes)) {
      requireRoute(detail, `strategies.${id}.routes.${role}`)
      if (!Object.hasOwn(baseline, role)) throw new Error(`strategies.${id} inventa un rol.`)
      // Strategy details have just passed the same route validator.
      const route = detail as unknown as RouteDetail
      const original = baseline[role]
      const unchanged = route.modelKey === original.modelKey && route.effort === original.effort && route.enabled === original.enabled
        && route.condition === original.condition && route.rationale === original.rationale
        && route.fallback?.modelKey === original.fallback?.modelKey && route.fallback?.effort === original.fallback?.effort
        && route.accelerator?.modelKey === original.accelerator?.modelKey && route.accelerator?.effort === original.accelerator?.effort
      if (unchanged) continue
      changed = true
      const bounded = meta.harness === 'gentle-shell' ? ['gentle-ai-explore'] : ['smol', 'tiny', 'memory', 'commit']
      const model = catalog[route.modelKey] as { pool: string }
      if (raw.kind !== 'nan-volume' || !bounded.includes(role) || !original.enabled || route.enabled !== original.enabled
        || model.pool !== 'NAN' || route.modelKey === original.modelKey
        || route.accelerator?.modelKey !== original.accelerator?.modelKey || route.accelerator?.effort !== original.accelerator?.effort
        || !route.fallback || route.fallback.modelKey !== original.modelKey || route.fallback.effort !== original.effort
        || !route.condition.trim() || !route.rationale.trim()) throw new Error(`strategies.${id}.${role} modifica una ruta protegida o carece de fallback/condición.`)
    }
    if (raw.kind === 'nan-volume' && !changed) throw new Error(`strategies.${id} no cambia ninguna ruta auxiliar.`)
  }

  if (input.benchmarks !== undefined) {
    if (!Array.isArray(input.benchmarks)) throw new Error('benchmarks debe ser una lista si está presente.')
    for (const [index, raw] of input.benchmarks.entries()) {
      requireRecord(raw, `benchmarks[${index}]`)
      const benchmark = raw
      requireOwnFields(benchmark, ['model', 'family', 'benchmark', 'value', 'unit', 'effort', 'source', 'date', 'provenance', 'note'], `benchmarks[${index}]`)
      for (const key of ['model', 'family', 'benchmark', 'unit', 'effort', 'source', 'date', 'provenance', 'note']) {
        requireString(benchmark[key], `benchmarks[${index}].${key}`)
      }
      if (benchmark.value !== null && (typeof benchmark.value !== 'number' || !Number.isFinite(benchmark.value))) {
        throw new Error(`benchmarks[${index}].value debe ser un número finito o null.`)
      }
      if (Object.hasOwn(benchmark, 'methodology')) {
        requireString(benchmark.methodology, `benchmarks[${index}].methodology`)
      }
      requireOwnOptionalFields(benchmark, ['sourceId', 'context', 'methodology', 'measurement'], `benchmarks[${index}]`)
      if (Object.hasOwn(benchmark, 'sourceId')) requireString(benchmark.sourceId, `benchmarks[${index}].sourceId`, false)
      if (Object.hasOwn(benchmark, 'context')) requireRecord(benchmark.context, `benchmarks[${index}].context`)
      const costRecord = /\b(?:USD|EUR|GBP|JPY|CNY)\b|[$€£¥]/i.test(String(benchmark.unit))
        || /\b(?:coste|cost)\b/i.test(String(benchmark.benchmark))
      if (costRecord && typeof benchmark.value === 'number' && benchmark.value < 0) {
        throw new Error(`benchmarks[${index}].value no puede ser un coste negativo.`)
      }
    }
  }
  if (Object.hasOwn(input, 'sourceCoverage')) requireSourceCoverage(input.sourceCoverage, input as unknown as Snapshot)
  if (Object.hasOwn(input, 'cybersecurityEvidence')) requireCybersecurityEvidence(input.cybersecurityEvidence, input as unknown as Snapshot)


  if (input.provenance !== undefined) {
    requireRecord(input.provenance, 'provenance')
    const provenance = input.provenance
    requireString(provenance.kind, 'provenance.kind', false)
    requireStringArray(provenance.sources, 'provenance.sources')
    requireString(provenance.validationNote, 'provenance.validationNote')
    requireString(provenance.benchmarkNote, 'provenance.benchmarkNote')
  }

  if (stats.profiles !== Object.keys(input.meta).length || stats.groups !== Object.keys(input.meta).length) {
    throw new Error('stats.profiles y stats.groups no coinciden con los perfiles del snapshot.')
  }
  if (stats.portfolios !== Object.keys(input.portfolios).length || stats.models !== Object.keys(input.catalog).length) {
    throw new Error('Los contadores de portfolios o modelos no coinciden con sus datos.')
  }
  if (stats.rows !== distinctAssignments) {
    throw new Error('stats.rows debe coincidir con el número de asignaciones del snapshot.')
  }

  validateBenchmarkRegistry(input as unknown as Snapshot)
  validateAccessSnapshot(input as unknown as Snapshot)
  return input as unknown as Snapshot
}

export function parseSnapshot(text: string): Snapshot {
  let parsed: unknown
  try {
    parsed = parseStrictJSON(text)
  } catch {
    throw new Error('El archivo no contiene JSON válido. Comprueba el archivo e inténtalo de nuevo.')
  }
  return validateSnapshot(parsed)
}


export function downloadFile(filename: string, content: string, mimeType: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  try {
    link.click()
  } finally {
    link.remove()
    URL.revokeObjectURL(url)
  }
}
