export type MetricKind = 'capability' | 'index' | 'cost' | 'price' | 'duration' | 'tokens' | 'throughput' | 'uncertainty' | 'error-rate' | 'safety' | 'context' | 'unclassified'
export type MetricDirection = 'higher' | 'lower' | 'context' | 'unknown'
export interface Measurement {
  id: string; metricId: string; protocolId: string; evaluationId: string | null
  modelId: string | null; modelRelation: 'published-label' | 'candidate' | 'unresolved'
  candidateModelIds: string[]; kind: MetricKind; direction: MetricDirection
  scope: 'current' | 'historical' | 'superseded'; issueIds: string[]
  costLinkId: string | null; primaryCost: boolean; decisionEligible: boolean
}
export interface MetricDefinition {
  id: string; suiteId: string; key: string; label: string; unit: string
  kind: MetricKind; direction: MetricDirection; denominator: string; aggregation: string
}
export interface BenchmarkProtocol {
  id: string; suiteId: string; version: string; sourceId: string; captureRef: string
  capturedAt: string; evaluationDate: string | null; priceAsOf: string | null; dateBasis: string
  subset: string | null; tasks: number | null; trialsPerTask: number | null
  harness: string | null; harnessVersion: string | null; network: string | null
  compaction: string | null; serverFallback: string | null
  comparison: 'not-established' | 'source-local' | 'paired-condition'
  controls: Record<string, unknown>; sourceMethodology: string | null
}
export interface BenchmarkSuite {
  id: string; label: string; domains: string[]; functions: string[]; policyFunctionIds?: string[]
  priority: string; limitations: string[]; updateMode: 'manual'; decisionUse: string
  captureIds: string[]; legacyPattern: string
  captures: { id: string; sourceId: string; url: string; capturedAt: string; sha256: string; path: string }[]
  coverage: { observations: number; current: number; linked: number; comparable: number; decisionEligible: number }
  lifecycle: { discovered: boolean; captured: boolean; normalized: boolean; linked: boolean; comparable: boolean; screeningUsable: boolean; routeCalibrated: false }
}
export interface BenchmarkRegistryData {
  schemaVersion: 1; updateMode: 'manual'; suites: Record<string, BenchmarkSuite>
  metrics: Record<string, MetricDefinition>; protocols: Record<string, BenchmarkProtocol>
  issues: Record<string, { label: string; status: string; note: string; blocks: string[]; sourceCaptureId?: string }>
  revisions: { previous: string; current: string; change: string; notAnIndependentTrial: true }[]
  stats: { observations: number; currentObservations: number; metricKinds: Record<string, number>; scopeCounts: Record<string, number>; modelLinks: Record<string, number>; bySource: Record<string, number>; suites: number; metrics: number; protocols: number; revisions: number; independentTrials: string; routeCalibrations: 0 }
  modelLinks: Record<string, unknown>; inputSha256: Record<string, string>; limitations: string[]
}
export const METRIC_LABELS: Record<MetricKind, string> = {
  capability: 'Capacidad / resultado', index: 'Índice / rúbrica', cost: 'Coste', price: 'Precio', duration: 'Duración', tokens: 'Tokens', throughput: 'Velocidad de salida', uncertainty: 'Incertidumbre', 'error-rate': 'Tasa de error / ataque', safety: 'Seguridad', context: 'Contexto operativo', unclassified: 'Semántica pendiente',
}
export const DIRECTION_LABELS: Record<MetricDirection, string> = { higher: 'Mayor es mejor', lower: 'Menor es mejor', context: 'Sin dirección de calidad', unknown: 'Dirección no establecida' }
