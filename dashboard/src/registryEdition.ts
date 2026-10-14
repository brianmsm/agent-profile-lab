import type { Snapshot } from './data'
import type { BenchmarkSuite } from './benchmarkTypes'

// Public counters describe redistributable rows, not whether research was performed.
export function isRightsScopedEvidenceEdition(snapshot: Snapshot): boolean {
  return snapshot.sourceCoverage?.scope?.startsWith('Public rights-scoped observations') === true
}

export function suiteHasVerifiableGap(suite: BenchmarkSuite, rightsScoped: boolean): boolean {
  // A missing public score is an edition boundary, not proof of a capture gap.
  if (rightsScoped && suite.coverage.observations === 0) return false
  return !suite.lifecycle.normalized || !suite.lifecycle.linked || !suite.lifecycle.comparable
}

export function suiteEvidencePresentation(suite: BenchmarkSuite, rightsScoped: boolean) {
  const withoutPublicRows = rightsScoped && suite.coverage.observations === 0
  return {
    status: withoutPublicRows ? 'Sin cifras redistribuidas'
      : rightsScoped ? 'Resultados redistribuidos · capturas no incluidas'
      : suite.lifecycle.captured ? 'Fuente capturada' : 'Sólo identificado',
    detailLabel: withoutPublicRows ? 'Alcance público y fuentes'
      : suite.lifecycle.normalized ? 'Alcance de extracción y precauciones' : 'Laguna documentada; no equivale a cero',
  }
}
