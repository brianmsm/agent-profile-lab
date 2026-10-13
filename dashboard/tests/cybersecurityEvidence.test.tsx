import { describe, expect, test } from 'bun:test'
import { createHash } from 'node:crypto'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import type { CyberReconciliationEntry, CybersecurityResult, Snapshot } from '../src/data'
import CybersecurityEvidence from '../src/CybersecurityEvidence'
import { parseSnapshot, validateSnapshot } from '../src/snapshotIO'
import { filterReconciliationEntries } from '../src/data'

function evidenceSnapshot(): Snapshot {
  const result: CybersecurityResult = {
    id: 'cyber-zero', sourceId: 'CARD', sourceUrl: 'https://example.org/model-card', provenance: 'card.raw#table/row/2',
    benchmark: 'MiMo Cyber Bench', benchmarkVersion: null, publishedModel: 'MiMo-V2.5 Pro', value: 0, unit: '%', effort: 'not stated',
    resultType: 'vendor', captureDate: '2026-10-02', evaluationDate: null, taskDenominator: null, attemptBudget: null,
    settings: 'Harness and attempt budget not disclosed.', limitations: ['No provider or routed result established.'],
    catalogMatches: [{ catalogKey: 'nan_mimo', relationship: 'candidate-alias', reason: 'NaN label does not confirm Pro identity.' }], routeValidation: 'not-established',
  }
  return {
    stats: { rows: 0, profiles: 0, portfolios: 0, models: 2, groups: 0, validators: { passed: 1, failed: 0 }, session: 'test' },
    portfolios: {}, catalog: {
      nan_mimo: { name: 'MiMo V2.5', pool: 'NAN', selector: 'nan/mimo-v2.5', efforts: [], vision: null, evidence: '', integration: '' },
      ultra: { name: 'MiMo V2.6 Pro UltraSpeed', pool: 'CC', selector: 'commandcode/xiaomi/mimo-v2.6-pro-ultraspeed', efforts: [], vision: null, evidence: '', integration: '' },
    },
    domainContracts: { apps: { label: 'Apps', gate: 'Oracle', critical: 'Critical', routine: 'Routine', scope: 'Software' } },
    coverage: {}, meta: {}, routing: {}, routeDetails: {}, runtimePolicies: {}, strategies: {},
    benchmarks: [{ model: result.publishedModel, family: 'supplemental', benchmark: result.benchmark, value: 0, unit: '%', effort: result.effort,
      sourceId: 'CARD', source: result.sourceUrl, date: result.captureDate, provenance: result.provenance, note: 'Literal published zero',
      context: { cybersecurity: { resultType: result.resultType, benchmarkVersion: null, evaluationDate: null, captureDate: result.captureDate,
        taskDenominator: null, attemptBudget: null, settings: result.settings, limitations: result.limitations } } }],
    cybersecurityEvidence: { schemaVersion: 1, asOf: result.captureDate, scope: 'Archived public aggregate results only.', routingConclusion: 'Apps-derived routes remain unchanged; no optimized allocation established.',
      results: [result], catalogCoverage: [
        { catalogKey: 'nan_mimo', state: 'candidate-alias-only', resultIds: [result.id], reason: 'Pro identity not confirmed.' },
        { catalogKey: 'ultra', state: 'no-mapped-result', resultIds: [], reason: 'No UltraSpeed result in this corpus.' },
      ] },
  }
}

function reconciliationSnapshot(): Snapshot {
  const snapshot = evidenceSnapshot()
  const evidence = snapshot.cybersecurityEvidence!
  const result = evidence.results[0]
  snapshot.sourceCoverage = {
    scope: 'Archived card and receipt', generatedAt: result.captureDate,
    totals: { sources: 1, artifacts: 2, benchmarks: 1, excluded: 0 },
    sources: [{ id: result.sourceId, title: 'Card', url: result.sourceUrl, evidenceType: 'published aggregates', kind: 'benchmark', status: 'included',
      checked: result.captureDate, limitations: '', note: '', benchmarkCount: 1, catalogReferences: 0, portfolioReferences: 0, assignmentReferences: 0,
      artifacts: ['card.raw', 'card.receipt.json'] }],
    artifacts: ['card.raw', 'card.receipt.json'].map(path => ({ path, sha256: 'a'.repeat(64), kind: path.endsWith('.json') ? 'capture-receipt' : 'capture',
      observed: 0, included: 0, excluded: 0, exclusions: [] })), notes: [],
  }
  const entries: CyberReconciliationEntry[] = [
    { id: '', sourceId: result.sourceId, sourceUrl: result.sourceUrl, publishedModel: result.publishedModel,
      benchmark: result.benchmark, metric: result.benchmark, status: 'incorporated', reason: 'Literal aggregate linked to normalized row.',
      locator: result.provenance, resultIds: [result.id] },
    { id: '', sourceId: result.sourceId, sourceUrl: result.sourceUrl, publishedModel: null,
      benchmark: 'Capability section', metric: 'Narrative capability', status: 'unresolved', reason: 'Graphic labels unreadable; no values inferred.',
      locator: 'card.raw#capability', resultIds: [] },
  ]
  for (const entry of entries) {
    const fields = Object.fromEntries(Object.entries(entry).filter(([key]) => key !== 'id').sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0))
    entry.id = `reconcile-${createHash('sha256').update(JSON.stringify(fields)).digest('hex').slice(0, 24)}`
  }
  evidence.reconciliation = {
    schemaVersion: 1, asOf: result.captureDate, scope: 'Reviewed official card only.', searchBoundary: 'Official publication and cited benchmark sections at capture date.',
    reviewedSources: [{ sourceId: result.sourceId, sourceUrl: result.sourceUrl, captureDate: result.captureDate,
      receiptPath: 'card.receipt.json', sections: ['card.raw#table/row/2', 'card.raw#capability'], catalogKeys: Object.keys(snapshot.catalog), limitations: ['No endpoint identity established.'] }],
    entries, catalogReview: Object.keys(snapshot.catalog).map(catalogKey => ({ catalogKey, sourceIds: [result.sourceId], conclusion: `Publication identity not resolved for ${catalogKey}.` })),
    counts: { incorporated: 1, 'context-only': 0, excluded: 0, 'not-published': 0, unresolved: 1 }, closure: 'open',
  }
  return snapshot
}

describe('cybersecurity evidence import', () => {
  test('retains literal zero and null metadata without making candidate routes measured', () => {
    const snapshot = parseSnapshot(JSON.stringify(evidenceSnapshot()))
    const result = snapshot.cybersecurityEvidence!.results[0]
    expect(result.value).toBe(0)
    expect(result.taskDenominator).toBeNull()
    expect(result.evaluationDate).toBeNull()
    expect(snapshot.cybersecurityEvidence!.catalogCoverage[0].state).toBe('candidate-alias-only')
    expect(result.routeValidation).toBe('not-established')
  })

  test('old snapshots do not require the optional section', () => {
    const snapshot = evidenceSnapshot()
    delete snapshot.cybersecurityEvidence
    expect(parseSnapshot(JSON.stringify(snapshot)).cybersecurityEvidence).toBeUndefined()
  })

  test('rejects forged source links, values, locators, protocol metadata and source identities', () => {
    for (const change of [
      { sourceUrl: 'https://example.org/forged' }, { sourceUrl: 'javascript:alert(1)' }, { value: 99 },
      { provenance: 'other.raw#table' }, { sourceId: 'OTHER' }, { settings: 'Claimed native routed evaluation' }, { resultType: 'independent' },
    ]) {
      const snapshot = evidenceSnapshot()
      Object.assign(snapshot.cybersecurityEvidence!.results[0], change)
      expect(() => validateSnapshot(snapshot)).toThrow('cybersecurityEvidence')
    }
  })

  test('rejects duplicate publications even when a second unique result ID is supplied', () => {
    const snapshot = evidenceSnapshot()
    snapshot.cybersecurityEvidence!.results.push({ ...snapshot.cybersecurityEvidence!.results[0], id: 'another-id' })
    expect(() => validateSnapshot(snapshot)).toThrow('duplica un resultado')
  })

  test('rejects missing publication rows, incomplete catalog coverage and forged coverage links', () => {
    const omitted = evidenceSnapshot()
    omitted.cybersecurityEvidence!.results = []
    const incomplete = evidenceSnapshot()
    incomplete.cybersecurityEvidence!.catalogCoverage.pop()
    const forged = evidenceSnapshot()
    forged.cybersecurityEvidence!.catalogCoverage[1].resultIds = ['cyber-zero']
    const duplicated = evidenceSnapshot()
    duplicated.cybersecurityEvidence!.catalogCoverage.push(duplicated.cybersecurityEvidence!.catalogCoverage[0])
    for (const snapshot of [omitted, incomplete, forged, duplicated]) expect(() => validateSnapshot(snapshot)).toThrow('cybersecurityEvidence')
  })

  test('rejects alias escalation and inheritance by a different version or speed mode', () => {
    for (const catalogKey of ['nan_mimo', 'ultra']) {
      const snapshot = evidenceSnapshot()
      snapshot.cybersecurityEvidence!.results[0].catalogMatches = [{ catalogKey, relationship: 'published-model', reason: 'Forged exact equivalence.' }]
      expect(() => validateSnapshot(snapshot)).toThrow('no puede elevarse a published-model')
    }
    const promoted = evidenceSnapshot()
    promoted.cybersecurityEvidence!.catalogCoverage[0].state = 'measured-result'
    expect(() => validateSnapshot(promoted)).toThrow('.state')
    const calibrated = evidenceSnapshot()
    Object.assign(calibrated.cybersecurityEvidence!.results[0], { routeValidation: 'established' })
    expect(() => validateSnapshot(calibrated)).toThrow('routeValidation')
  })

  test('does not map an ordinary GLM result to Flash and keeps literal publisher abbreviations', () => {
    for (const [published, name, accepted] of [['GLM-5.3', 'GLM 5.3 Flash', false], ['DS-V4.1-Flash', 'DeepSeek V4.1 Flash', true], ['K3', 'Kimi K3', true]] as const) {
      const snapshot = evidenceSnapshot()
      snapshot.catalog.nan_mimo.name = name
      snapshot.benchmarks![0].model = published
      const result = snapshot.cybersecurityEvidence!.results[0]
      result.publishedModel = published
      result.catalogMatches[0].relationship = 'published-model'
      snapshot.catalog.nan_mimo.selector = `test/${published}`
      snapshot.cybersecurityEvidence!.catalogCoverage[0].state = 'measured-result'
      if (accepted) expect(validateSnapshot(snapshot).cybersecurityEvidence!.results[0].publishedModel).toBe(published)
      else expect(() => validateSnapshot(snapshot)).toThrow('no puede elevarse')
    }
  })

  test('rejects arbitrary candidate inheritance and provider aliases disguised by catalog names', () => {
    const unrelated = evidenceSnapshot()
    unrelated.cybersecurityEvidence!.results[0].catalogMatches[0].catalogKey = 'ultra'
    expect(() => validateSnapshot(unrelated)).toThrow('no hay correspondencia de alias candidato')
    const disguised = evidenceSnapshot()
    disguised.catalog.nan_mimo.name = 'MiMo V2.5 Pro'
    disguised.cybersecurityEvidence!.results[0].catalogMatches[0].relationship = 'published-model'
    expect(() => validateSnapshot(disguised)).toThrow('un alias no puede elevarse')
  })

  test('requires declared source lineage when a source register is present', () => {
    const snapshot = evidenceSnapshot()
    snapshot.sourceCoverage = {
      scope: 'One registered source', generatedAt: '2026-10-02', totals: { sources: 1, artifacts: 0, benchmarks: 1, excluded: 0 },
      sources: [{ id: 'CARD', title: 'Card', url: 'https://example.org/model-card', evidenceType: 'table', kind: 'benchmark', status: 'included',
        checked: '2026-10-02', limitations: '', note: '', benchmarkCount: 1, catalogReferences: 0, portfolioReferences: 0, assignmentReferences: 0, artifacts: [] }],
      artifacts: [], notes: [],
    }
    expect(validateSnapshot(snapshot).cybersecurityEvidence!.results[0].sourceId).toBe('CARD')
    snapshot.sourceCoverage.sources[0].id = 'OTHER'
    snapshot.benchmarks![0].sourceId = 'OTHER'
    expect(() => validateSnapshot(snapshot)).toThrow('sourceId no resuelve')
  })

  test('editorial scores cannot count as measured task evidence', () => {
    const snapshot = evidenceSnapshot()
    snapshot.cybersecurityEvidence!.results[0].resultType = 'editorial'
    Object.assign(snapshot.benchmarks![0].context!.cybersecurity!, { resultType: 'editorial' })
    snapshot.cybersecurityEvidence!.catalogCoverage[0].state = 'editorial-only'
    expect(validateSnapshot(snapshot).cybersecurityEvidence!.catalogCoverage[0].state).toBe('editorial-only')
    snapshot.cybersecurityEvidence!.catalogCoverage[0].state = 'measured-result'
    expect(() => validateSnapshot(snapshot)).toThrow('.state')
  })
})

describe('cybersecurity reconciliation import', () => {
  test('keeps older graph results available without inventing a reconciliation', () => {
    const snapshot = parseSnapshot(JSON.stringify(evidenceSnapshot()))
    expect(snapshot.cybersecurityEvidence!.reconciliation).toBeUndefined()
    expect(snapshot.cybersecurityEvidence!.results[0].value).toBe(0)
  })

  test('accepts open corpus with exact zero result linkage and complete model review', () => {
    const snapshot = parseSnapshot(JSON.stringify(reconciliationSnapshot()))
    expect(snapshot.cybersecurityEvidence!.reconciliation!.closure).toBe('open')
    expect(snapshot.cybersecurityEvidence!.reconciliation!.entries[0].resultIds).toEqual(['cyber-zero'])
    expect(snapshot.cybersecurityEvidence!.results[0].value).toBe(0)
  })

  test('rejects false closure and fabricated status totals', () => {
    for (const change of [
      { closure: 'reconciled-corpus' }, { closure: 'worldwide' },
      { counts: { incorporated: 1, 'context-only': 0, excluded: 0, 'not-published': 0, unresolved: 0 } },
      { counts: { incorporated: 2, 'context-only': 0, excluded: 0, 'not-published': 0, unresolved: 1 } },
    ]) {
      const snapshot = reconciliationSnapshot()
      Object.assign(snapshot.cybersecurityEvidence!.reconciliation!, change)
      expect(() => validateSnapshot(snapshot)).toThrow('reconciliation')
    }
    const closed = reconciliationSnapshot()
    const reconciliation = closed.cybersecurityEvidence!.reconciliation!
    reconciliation.entries[1].status = 'excluded'
    reconciliation.counts.unresolved = 0
    reconciliation.counts.excluded = 1
    reconciliation.closure = 'reconciled-corpus'
    expect(validateSnapshot(closed).cybersecurityEvidence!.reconciliation!.closure).toBe('reconciled-corpus')
  })

  test('rejects omissions, duplicate result linkage and fabricated incorporated references', () => {
    for (const mutate of [
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries.shift(); snapshot.cybersecurityEvidence!.reconciliation!.counts.incorporated = 0 },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[0].resultIds = ['unknown-result'] },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[0].resultIds = ['cyber-zero', 'cyber-zero'] },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[0].metric = 'Invented normalized quality' },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[0].publishedModel = 'MiMo V2.6 Pro UltraSpeed' },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[0].locator = 'card.raw#wrong-row' },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[1].resultIds = ['cyber-zero'] },
      (snapshot: Snapshot) => { const entries = snapshot.cybersecurityEvidence!.reconciliation!.entries; entries.push({ ...entries[0], id: `reconcile-${'b'.repeat(24)}` }) },
    ]) {
      const snapshot = reconciliationSnapshot()
      mutate(snapshot)
      expect(() => validateSnapshot(snapshot)).toThrow('reconciliation')
    }
  })

  test('rejects unreviewed model selectors, unknown IDs, statuses and forged source lineage', () => {
    for (const mutate of [
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.catalogReview.pop() },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.catalogReview[0].sourceIds = ['UNKNOWN'] },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.catalogReview[0].catalogKey = 'unknown-model' },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.reviewedSources[0].catalogKeys.push('unknown-model') },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.reviewedSources[0].sourceUrl = 'https://example.org/forged' },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.reviewedSources[0].receiptPath = 'unregistered.receipt.json' },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.reviewedSources[0].sections = ['unregistered.raw#section'] },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[1].locator = 'unregistered.raw#section' },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[1].locator = 'card.raw#' },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[0].id = 'unknown-id' },
      (snapshot: Snapshot) => { const entries = snapshot.cybersecurityEvidence!.reconciliation!.entries; entries[1].id = entries[0].id },
      (snapshot: Snapshot) => { Object.assign(snapshot.cybersecurityEvidence!.reconciliation!.entries[1], { status: 'measured' }) },
      (snapshot: Snapshot) => { snapshot.cybersecurityEvidence!.reconciliation!.entries[0].sourceId = 'UNKNOWN' },
      (snapshot: Snapshot) => { delete snapshot.sourceCoverage },
    ]) {
      const snapshot = reconciliationSnapshot()
      mutate(snapshot)
      expect(() => validateSnapshot(snapshot)).toThrow('reconciliation')
    }
  })

  test('a listed source with no dispositions cannot make the corpus appear closed', () => {
    const snapshot = reconciliationSnapshot()
    const registry = snapshot.sourceCoverage!
    registry.sources.push({ ...registry.sources[0], id: 'UNREVIEWED', benchmarkCount: 0 })
    registry.totals.sources++
    snapshot.cybersecurityEvidence!.reconciliation!.reviewedSources.push({ ...snapshot.cybersecurityEvidence!.reconciliation!.reviewedSources[0], sourceId: 'UNREVIEWED' })
    expect(() => validateSnapshot(snapshot)).toThrow('reconciliation')
  })

  test('a benchmark scoring URL remains exact even when its registered publication URL differs', () => {
    const snapshot = reconciliationSnapshot()
    const result = snapshot.cybersecurityEvidence!.results[0]
    result.sourceUrl = 'https://example.org/score-table'
    snapshot.benchmarks![0].source = result.sourceUrl
    snapshot.cybersecurityEvidence!.reconciliation!.entries[0].sourceUrl = result.sourceUrl
    expect(validateSnapshot(snapshot).cybersecurityEvidence!.results[0].sourceUrl).toBe(result.sourceUrl)
  })

  test('accepts detailed captured locators within a broadly inventoried source section', () => {
    const snapshot = reconciliationSnapshot()
    const reconciliation = snapshot.cybersecurityEvidence!.reconciliation!
    reconciliation.reviewedSources[0].sections = ['card.raw#table', 'card.raw#capability']
    reconciliation.entries[1].locator = 'card.raw#capability/figure/3'
    expect(validateSnapshot(snapshot).cybersecurityEvidence!.reconciliation!.entries[1].locator).toBe('card.raw#capability/figure/3')
  })
})

describe('cybersecurity reconciliation filtering and missing states', () => {
  test('filters missing model separately from all models and combines source, protocol, metric and status', () => {
    const entries = reconciliationSnapshot().cybersecurityEvidence!.reconciliation!.entries
    const filters = { query: '', source: '', model: '', benchmark: '', metric: '', status: '' }
    expect(filterReconciliationEntries(entries, { ...filters, model: 'null' }).map(row => row.status)).toEqual(['unresolved'])
    expect(filterReconciliationEntries(entries, { ...filters, model: JSON.stringify('MiMo-V2.5 Pro'), source: 'CARD', benchmark: 'MiMo Cyber Bench', metric: 'MiMo Cyber Bench', status: 'incorporated' }).map(row => row.resultIds)).toEqual([['cyber-zero']])
    expect(filterReconciliationEntries(entries, { ...filters, status: 'unresolved', metric: 'MiMo Cyber Bench' })).toEqual([])
    expect(filterReconciliationEntries(entries, { ...filters, source: 'OTHER' })).toEqual([])
    expect(filterReconciliationEntries(entries, filters).map(row => row.status)).toEqual(['incorporated', 'unresolved'])
  })

  test('finds localizers and linked result IDs without mixing cost and elapsed-time metrics', () => {
    const entries = reconciliationSnapshot().cybersecurityEvidence!.reconciliation!.entries
    const filters = { query: '', source: '', model: '', benchmark: '', metric: '', status: '' }
    expect(filterReconciliationEntries(entries, { ...filters, query: ' CARD.RAW#CAPABILITY ' }).map(row => row.status)).toEqual(['unresolved'])
    expect(filterReconciliationEntries(entries, { ...filters, query: 'cyber-zero' }).map(row => row.resultIds)).toEqual([['cyber-zero']])
    const costs = [
      { ...entries[0], metric: 'Cybench run cost (USD)' },
      { ...entries[0], id: 'time-row', metric: 'Cybench elapsed time (seconds)' },
    ]
    expect(filterReconciliationEntries(costs, { ...filters, metric: 'Cybench run cost (USD)' }).map(row => row.metric)).toEqual(['Cybench run cost (USD)'])
    expect(filterReconciliationEntries(costs, { ...filters, metric: 'Cybench elapsed time (seconds)' }).map(row => row.metric)).toEqual(['Cybench elapsed time (seconds)'])
  })

  test('renders reconciliation absence separately from an open corpus and keeps old result navigation', () => {
    const oldMarkup = renderToStaticMarkup(createElement(CybersecurityEvidence, { snapshot: evidenceSnapshot() }))
    expect(oldMarkup).toContain('data-testid="cyber-reconciliation-missing"')
    expect(oldMarkup).toContain('data-result-id="cyber-zero"')
    expect(oldMarkup).not.toContain('data-closure=')
    const openMarkup = renderToStaticMarkup(createElement(CybersecurityEvidence, { snapshot: reconciliationSnapshot() }))
    expect(openMarkup).toContain('data-closure="open"')
    expect(openMarkup).toContain('data-status="unresolved"')
    expect(openMarkup).toContain('href="#cyber-result-cyber-zero"')
    expect(openMarkup).toContain('id="cyber-result-cyber-zero"')
    const missing = evidenceSnapshot()
    delete missing.cybersecurityEvidence
    const missingMarkup = renderToStaticMarkup(createElement(CybersecurityEvidence, { snapshot: missing }))
    expect(missingMarkup).toContain('data-testid="cybersecurity-evidence-missing"')
    expect(missingMarkup).not.toContain('data-result-id=')
    expect(missingMarkup).not.toContain('data-closure=')
  })
})
