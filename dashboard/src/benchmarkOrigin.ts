import type { Benchmark } from './data'

function contextText(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(contextText)
  if (typeof value === 'object' && value !== null) return Object.values(value).flatMap(contextText)
  return []
}

export function isMirrorBenchmark(row: Benchmark, sourceKind?: string): boolean {
  return sourceKind === 'mirror' || /\bmirror(?:s|ed)?\b|espejo|slopalytics/i.test([
    row.methodology, row.note, row.provenance, ...contextText(row.context),
  ].join(' '))
}
