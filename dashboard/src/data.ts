import type {NanCustomWorkload} from './nanCustomWorkload'
import type { Measurement, BenchmarkRegistryData } from './benchmarkTypes'
export type OpenAIPlan = 'none' | 'plus' | 'pro100'
export type ClaudePlan = 'none' | 'pro' | 'max'
export type GatewayPlan = 'none' | 'cc' | 'go'

export interface SubscriptionSelection {
  openai: OpenAIPlan
  claude: ClaudePlan
  gateway: GatewayPlan
  nan: boolean
  api?: boolean
  anthropicApi?: boolean
}

export const EMPTY_SUBSCRIPTIONS: SubscriptionSelection = {
  openai: 'none',
  claude: 'none',
  gateway: 'none',
  nan: false,
}

export interface PortfolioInfo {
  label: string
  usd: string
  eur: string
  openai: OpenAIPlan
  gateway: GatewayPlan
  claude: ClaudePlan
  nan: 'True' | 'False'
  notes?: string
  sourceIds?: string[]
}
export interface ModelInfo {
  name: string
  pool: string
  selector: string
  efforts: string[]
  vision: boolean | null
  evidence: string
  integration: string
  notes?: string
  sourceIds?: string[]
  sourceUrls?: string[]
  modelId?: string
  defaultAccessRouteId?: string
  identityRelation?: 'published-label' | 'candidate-alias'
}

export interface AccessOrigin {
  modelId: string
  accessRouteId: string
  resourceId: string
  credentialRef: string
  plan: string
}

export interface AccessResource {
  id: string
  accessRouteId: string
  credentialRef: string
  plan: string
}

export interface AccessSnapshot {
  schemaVersion: 1
  evidenceState: 'declared-not-runtime-verified'
  resourcesByPortfolio: Record<string, AccessResource[]>
  inputSha256: Record<string, string>
}

export interface RouteReference {
  modelKey: string
  effort: string
  origin?: AccessOrigin
}

export interface ProfileMeta {
  targetId?: string
  harnessVersion?: string
  runtime?: { name: string; version: string }
  portfolio: string
  harness: string
  domain: string
  objective: string
}

export interface ProfileFilters {
  nanCustomWorkload?:NanCustomWorkload|null
  nanScenario?: 'routine'|'mixed'|'implementation'
  nanComposition?: 'all'|'nan-only'|'hybrid-preserve'|'hybrid-assist'|'hybrid-worker'
  nanTrials?: boolean
  domain: string
  objective: string
  harness: string
  subscriptions: SubscriptionSelection | null
  strategy: '' | 'matrix' | 'openai-led' | 'nan-volume' | 'activity-distributed' | 'reviewed-candidate' | 'nan-static' | 'nan-hybrid'
  complexity?: 'bounded' | 'standard' | 'complex'
  highImpact?: boolean
  profileId?: string
  portfolio: string
  search: string
}

export const DEFAULT_FILTERS: ProfileFilters = {
  domain: 'apps',
  objective: 'balanced',
  harness: '',
  subscriptions: null,
  strategy: '',
  portfolio: '',
  search: '',
}

export interface Benchmark {
  measurement?: Measurement
  model: string
  family: string
  benchmark: string
  value: number | null
  unit: string
  effort: string
  source: string
  date: string
  provenance: string
  methodology?: string
  note: string
  sourceId?: string
  context?: Record<string, unknown>
}

export type CyberResultType = 'independent' | 'vendor' | 'vendor-comparator' | 'editorial'
export type CyberCoverageState = 'measured-result' | 'candidate-alias-only' | 'editorial-only' | 'no-mapped-result'

export interface CybersecurityResult {
  id: string
  sourceId: string
  sourceUrl: string
  provenance: string
  benchmark: string
  benchmarkVersion: string | null
  publishedModel: string
  value: number
  unit: string
  effort: string
  resultType: CyberResultType
  captureDate: string
  evaluationDate: string | null
  taskDenominator: number | null
  attemptBudget: string | null
  settings: string
  limitations: string[]
  catalogMatches: { catalogKey: string; relationship: 'published-model' | 'candidate-alias'; reason: string }[]
  routeValidation: 'not-established'
}

export const CYBER_RECONCILIATION_STATUSES = ['incorporated', 'context-only', 'excluded', 'not-published', 'unresolved'] as const
export type CyberReconciliationStatus = typeof CYBER_RECONCILIATION_STATUSES[number]

export const CYBER_RECONCILIATION_STATUS_LABELS: Record<CyberReconciliationStatus, string> = {
  incorporated: 'Incorporado al grafo', 'context-only': 'Solo contexto', excluded: 'Excluido',
  'not-published': 'No publicado en la sección revisada', unresolved: 'Pendiente de resolver',
}

export interface CyberReconciliationEntry {
  id: string
  sourceId: string
  sourceUrl: string
  publishedModel: string | null
  benchmark: string
  metric: string
  status: CyberReconciliationStatus
  reason: string
  locator: string
  resultIds: string[]
}

export interface ReconciliationFilters {
  query: string
  source: string
  model: string
  benchmark: string
  metric: string
  status: string
}

export function filterReconciliationEntries(entries: CyberReconciliationEntry[], filters: ReconciliationFilters): CyberReconciliationEntry[] {
  const needle = filters.query.trim().toLocaleLowerCase('es')
  return entries.filter(row => (!filters.source || row.sourceId === filters.source)
    && (!filters.model || JSON.stringify(row.publishedModel) === filters.model)
    && (!filters.benchmark || row.benchmark === filters.benchmark)
    && (!filters.metric || row.metric === filters.metric)
    && (!filters.status || row.status === filters.status)
    && [row.id, row.sourceId, row.sourceUrl, row.publishedModel ?? 'Modelo no declarado', row.benchmark, row.metric,
      row.status, CYBER_RECONCILIATION_STATUS_LABELS[row.status], row.reason, row.locator, ...row.resultIds].join(' ').toLocaleLowerCase('es').includes(needle))
}

export interface CybersecurityReconciliation {
  schemaVersion: 1
  asOf: string
  scope: string
  searchBoundary: string
  reviewedSources: {
    sourceId: string
    sourceUrl: string
    captureDate: string
    receiptPath: string
    sections: string[]
    catalogKeys: string[]
    limitations: string[]
  }[]
  entries: CyberReconciliationEntry[]
  catalogReview: { catalogKey: string; sourceIds: string[]; conclusion: string; reviewState?: 'pending' | 'reviewed' }[]
  counts: Record<CyberReconciliationStatus, number>
  closure: 'reconciled-corpus' | 'open'
}

export interface CybersecurityEvidence {
  schemaVersion: 1
  asOf: string
  scope: string
  routingConclusion: string
  results: CybersecurityResult[]
  catalogCoverage: { catalogKey: string; state: CyberCoverageState; resultIds: string[]; reason: string }[]
  reconciliation?: CybersecurityReconciliation
}

export interface DomainContract {
  label: string
  gate: string
  critical: string
  routine: string
  scope: string
  evidenceNote?: string
  evidenceBoundary?: {
    routingBasis: 'Apps-derived'
    publishedEvidence: 'published-results-present'
    routeCalibration: 'route-calibration-not-established'
    validationMeaning: 'structural-validation-not-efficacy'
  }
}

export interface SourceEntry {
  id: string
  title: string
  url: string
  evidenceType: string
  kind: 'benchmark' | 'measurement' | 'contract' | 'code' | 'user-evidence' | 'assumption' | 'press' | 'telemetry' | 'mirror' | 'unknown'
  status: 'included' | 'context-only' | 'unavailable' | 'superseded'
  checked: string
  limitations: string
  note: string
  benchmarkCount: number
  catalogReferences: number
  portfolioReferences: number
  assignmentReferences: number
  artifacts: string[]
}

export interface SourceArtifact {
  path: string
  sha256: string
  kind: string
  observed: number
  included: number
  excluded: number
  exclusions: { locator: string; reason: string; count: number }[]
}

export interface SourceCoverage {
  scope: string
  generatedAt: string
  totals: { sources: number; artifacts: number; benchmarks: number; excluded: number }
  sources: SourceEntry[]
  artifacts: SourceArtifact[]
  notes: string[]
}

export interface RouteDetail {
  origin?: AccessOrigin
  modelKey: string
  effort: string
  fallback: RouteReference | null
  accelerator: RouteReference | null
  enabled: boolean
  condition: string
  rationale: string
}

export interface RuntimePolicy {
  advisorEnabled: boolean
  taskMaxConcurrency: number
}

export interface RoutingStrategy {
  kind: 'openai-led' | 'nan-volume'
  sourceProfile: string
  portfolio: string
  routes: Record<string, RouteDetail>
  coordinatorPool: string
  offloadPool: string | null
  limitations: string[]
}

export interface Snapshot {
  benchmarkRegistry?: BenchmarkRegistryData
  access?: AccessSnapshot
  stats: {
    rows: number
    profiles: number
    portfolios: number
    models: number
    groups: number
    validators: { passed: number; failed: number }
    session: string
  }
  portfolios: Record<string, PortfolioInfo>
  catalog: Record<string, ModelInfo>
  domainContracts: Record<string, DomainContract>
  coverage: Record<string, Record<string, string>>
  meta: Record<string, ProfileMeta>
  routing: Record<string, Record<string, [string, string]>>
  routeDetails: Record<string, Record<string, RouteDetail>>
  runtimePolicies: Record<string, RuntimePolicy | null>
  strategies: Record<string, RoutingStrategy>
  benchmarks?: Benchmark[]
  sourceCoverage?: SourceCoverage
  cybersecurityEvidence?: CybersecurityEvidence
  provenance?: { kind: string; sources: string[]; validationNote: string; benchmarkNote: string }
}

export const DOMAINS: Record<string, string> = { apps: 'Desarrollo de software', web: 'Desarrollo web', data: 'Datos', research: 'Investigación', 'agent-use': 'Uso de agentes', cybersecurity: 'Ciberseguridad' }
export const OBJECTIVES: Record<string, string> = { economy: 'Economía', balanced: 'Equilibrio', speed: 'Velocidad', best: 'Máxima calidad' }
export const number = new Intl.NumberFormat('es-ES').format
export const decimal = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 6 }).format
export const percent = new Intl.NumberFormat('es-ES', { style: 'percent', maximumFractionDigits: 1 }).format

export function subscriptionsOf(portfolio: PortfolioInfo): SubscriptionSelection {
  return {
    openai: portfolio.openai,
    claude: portfolio.claude,
    gateway: portfolio.gateway,
    nan: portfolio.nan === 'True',
  }
}

export function matchesSubscriptions(
  portfolio: PortfolioInfo,
  selection: SubscriptionSelection | null,
  exactInventory = false,
): boolean {
  if (!selection) return true
  const actual = subscriptionsOf(portfolio)
  if (exactInventory) {
    return actual.openai === selection.openai
      && actual.claude === selection.claude
      && actual.gateway === selection.gateway
      && actual.nan === selection.nan
  }
  return (actual.openai === 'none' || actual.openai === selection.openai)
    && (actual.claude === 'none' || actual.claude === selection.claude)
    && (actual.gateway === 'none' || actual.gateway === selection.gateway)
    && (!actual.nan || selection.nan)
}

export function subscriptionLabels(selection: SubscriptionSelection): string[] {
  const labels: string[] = []
  if (selection.openai === 'plus') labels.push('OpenAI Plus')
  if (selection.openai === 'pro100') labels.push('OpenAI Pro 100')
  if (selection.claude === 'pro') labels.push('Claude Pro')
  if (selection.claude === 'max') labels.push('Claude Max')
  if (selection.gateway === 'cc') labels.push('Command Code')
  if (selection.gateway === 'go') labels.push('OpenCode Go')
  if (selection.nan) labels.push('NaN')
  if (selection.api) labels.push('OpenAI API (pago por uso)')
  if (selection.anthropicApi) labels.push('Claude API (uso medido; crédito separado)')
  return labels
}

export function monthly(portfolio: PortfolioInfo) {
  const components = [[portfolio.usd, 'USD'], [portfolio.eur, 'EUR']]
    .filter(([value]) => Number(value) !== 0)
    .map(([value, currency]) => `${decimal(Number(value))} ${currency}`)
  return components.length ? components.join(' + ') : '0 USD + 0 EUR'
}

export function matchesProfile(snapshot: Snapshot, pid: string, query: string) {
  const needle = query.trim().toLocaleLowerCase('es')
  if (!needle) return true
  const meta = snapshot.meta[pid]
  const contract = snapshot.domainContracts[meta.domain]
  const text = [pid, meta.domain, snapshot.portfolios[meta.portfolio]?.label, DOMAINS[meta.domain], contract.label, OBJECTIVES[meta.objective],
    ...Object.entries(snapshot.routing[pid] || {}).flatMap(([role, [model, effort]]) => [role, model, effort])].join(' ')
  return text.toLocaleLowerCase('es').includes(needle)
}

export function tally(values: string[]) {
  const counts = new Map<string, number>()
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1)
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
}
