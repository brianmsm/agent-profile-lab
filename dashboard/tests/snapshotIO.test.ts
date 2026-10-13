import { describe, expect, test } from 'bun:test'
import type { Snapshot } from '../src/data'
import { parseSnapshot, validateSnapshot } from '../src/snapshotIO'
import { getPreset, presetAnalysis, presetRolesCsv } from '../src/presetStrategies'

function validSnapshot(): Snapshot {
  return {
    stats: { rows: 1, profiles: 1, portfolios: 1, models: 1, groups: 1, validators: { passed: 1, failed: 0 }, session: 'test' },
    portfolios: {
      plus: {
        label: 'OpenAI Plus', usd: '20', eur: '0', openai: 'plus', gateway: 'none', claude: 'none', nan: 'False',
        notes: 'Plan source note', sourceIds: ['OAI'],
      },
    },
    catalog: {
      model: {
        name: 'Model One', pool: 'OAI', selector: 'provider/model-one', efforts: ['high'], vision: null,
        evidence: '', integration: '', notes: 'Catalog source note', sourceIds: ['MODEL'], sourceUrls: ['https://example.org/model'],
      },
    },
    coverage: {},
    domainContracts: {
      apps: {
        label: 'Apps y software multiplataforma', gate: 'Ejecutar CI en cada SO objetivo.',
        critical: 'Permisos y persistencia', routine: 'Módulos portables con oráculo', scope: 'CLI, GUI y servicios',
      },
    },
    meta: { profile: { portfolio: 'plus', harness: 'gentle-shell', domain: 'apps', objective: 'balanced' } },
    routing: { profile: { main: ['Model One', ''] } },
    routeDetails: { profile: { main: { modelKey: 'model', effort: '', fallback: null, accelerator: null, enabled: true, condition: '', rationale: '' } } },
    runtimePolicies: { profile: null },
    strategies: {},
    benchmarks: [{
      model: 'Model One', family: 'Test', benchmark: 'Quality', value: 0, unit: '%', effort: 'high',
      source: 'https://example.org/evidence', date: '2026-10-01', provenance: 'evidence.csv:L2', methodology: 'independent', note: 'Captured source note',
    }],
    provenance: { kind: 'test', sources: ['source.csv'], validationNote: '', benchmarkNote: '' },
  }
}

function coverageSnapshot(): Snapshot {
  const snapshot = validSnapshot()
  snapshot.benchmarks![0].sourceId = 'MODEL'
  snapshot.sourceCoverage = {
    scope: 'Registered sources only', generatedAt: '2026-10-02T00:00:00Z',
    totals: { sources: 2, artifacts: 1, benchmarks: 1, excluded: 2 },
    sources: [
      { id: 'OAI', title: 'Plan', url: 'https://example.org/plan', evidenceType: 'contract', kind: 'contract', status: 'context-only',
        checked: '', limitations: 'Not a performance measurement', note: '', benchmarkCount: 0,
        catalogReferences: 0, portfolioReferences: 1, assignmentReferences: 0, artifacts: [] },
      { id: 'MODEL', title: 'Measurement', url: 'https://example.org/evidence', evidenceType: 'table', kind: 'benchmark', status: 'included',
        checked: '2026-10-01', limitations: 'One observed score', note: 'Two context observations remain',
        benchmarkCount: 1, catalogReferences: 1, portfolioReferences: 0, assignmentReferences: 1, artifacts: ['evidence.json'] },
    ],
    artifacts: [{ path: 'evidence.json', sha256: 'a'.repeat(64), kind: 'normalized', observed: 5, included: 1, excluded: 2,
      exclusions: [{ locator: 'rows[1:3]', reason: 'No attributable score', count: 2 }] }],
    notes: ['Remaining observations are context, not scores.'],
  }
  return snapshot
}

describe('snapshot import contract', () => {
  test('accepts explicit subscription plans, optional evidence provenance and empty optional sections', () => {
    const snapshot = validSnapshot()
    snapshot.benchmarks = []
    delete snapshot.provenance
    const parsed = parseSnapshot(JSON.stringify(snapshot))
    expect(parsed.portfolios.plus.claude).toBe('none')
    expect(parsed.benchmarks).toEqual([])
    expect(parsed.provenance).toBeUndefined()
    expect(validateSnapshot(snapshot).catalog.model.sourceUrls).toEqual(['https://example.org/model'])
  })

  test('rejects ambiguous legacy subscription metadata', () => {
    const snapshot = validSnapshot()
    const oldPortfolio = snapshot.portfolios.plus as unknown as Record<string, unknown>
    delete oldPortfolio.claude
    oldPortfolio.anthropic = 'False'
    expect(() => validateSnapshot(snapshot)).toThrow()
  })

  test('rejects absent, malformed or inherited domain contracts with regeneration guidance', () => {
    const missing = validSnapshot() as unknown as Record<string, unknown>
    delete missing.domainContracts
    const unusable = [null, [], {}, { apps: { ...validSnapshot().domainContracts.apps, gate: '  ' } }]
      .map(domainContracts => ({ ...validSnapshot(), domainContracts }))
    const unmatched = validSnapshot()
    unmatched.domainContracts = { web: unmatched.domainContracts.apps }
    const inheritedMap = validSnapshot()
    inheritedMap.domainContracts = Object.assign(Object.create({ apps: inheritedMap.domainContracts.apps }), { web: inheritedMap.domainContracts.apps })
    const inheritedFields = validSnapshot()
    inheritedFields.domainContracts.apps = Object.create(inheritedFields.domainContracts.apps)
    for (const snapshot of [missing, ...unusable, unmatched, inheritedMap, inheritedFields]) {
      expect(() => validateSnapshot(snapshot)).toThrow('build_dashboard_snapshot.py')
    }
  })

  test('requires cybersecurity evidence limits even when routing is otherwise complete', () => {
    for (const evidenceNote of [undefined, '', '  ', 0]) {
      const snapshot = validSnapshot()
      snapshot.meta.profile.domain = 'cybersecurity'
      const contract = { ...snapshot.domainContracts.apps, label: 'Ciberseguridad' }
      snapshot.domainContracts = { cybersecurity: contract }
      if (evidenceNote !== undefined) Object.assign(contract, { evidenceNote })
      expect(() => parseSnapshot(JSON.stringify(snapshot))).toThrow('build_dashboard_snapshot.py')
    }
  })

  test('rejects non-string plans, non-finite costs, metrics, unsupported enums and stale counts', () => {
    const arrayPlan = validSnapshot()
    ;(arrayPlan.portfolios.plus as unknown as Record<string, unknown>).openai = ['plus']
    expect(() => validateSnapshot(arrayPlan)).toThrow()

    const badMoney = validSnapshot()
    badMoney.portfolios.plus.usd = 'Infinity'
    expect(() => validateSnapshot(badMoney)).toThrow()

    const badMetric = validSnapshot()
    badMetric.benchmarks![0].value = Number.NaN
    expect(() => validateSnapshot(badMetric)).toThrow()

    const negativeForeignCost = validSnapshot()
    negativeForeignCost.benchmarks![0] = { ...negativeForeignCost.benchmarks![0], benchmark: 'Evaluation charge', unit: 'GBP / task', value: -1 }
    expect(() => validateSnapshot(negativeForeignCost)).toThrow()

    const badDomain = validSnapshot()
    badDomain.meta.profile.domain = '__proto__'
    expect(() => validateSnapshot(badDomain)).toThrow()

    const badRows = validSnapshot()
    badRows.stats.rows = 2
    expect(() => validateSnapshot(badRows)).toThrow()
  })

  test('rejects dangling profile, portfolio and model references', () => {
    const badPortfolio = validSnapshot()
    badPortfolio.meta.profile.portfolio = 'missing'
    expect(() => validateSnapshot(badPortfolio)).toThrow()

    const badProfile = validSnapshot()
    badProfile.routing = { ghost: { main: ['Model One', 'high'] } }
    expect(() => validateSnapshot(badProfile)).toThrow()

    const badModel = validSnapshot()
    badModel.routing.profile.main[0] = 'Missing model'
    expect(() => validateSnapshot(badModel)).toThrow()
  })

  test('rejects malformed JSON without manufacturing a substitute snapshot', () => {
    expect(() => parseSnapshot('{')).toThrow()
  })
})

describe('source coverage reconciliation', () => {
  test('accepts third-party evidence without a declared registry and exact reconciled coverage', () => {
    const thirdParty = validSnapshot()
    thirdParty.benchmarks![0].sourceId = 'third-party'
    expect(validateSnapshot(thirdParty).sourceCoverage).toBeUndefined()
    expect(validateSnapshot(coverageSnapshot()).sourceCoverage!.totals.benchmarks).toBe(1)
    const ownId = coverageSnapshot()
    ownId.sourceCoverage!.sources[1].id = '__proto__'
    ownId.benchmarks![0].sourceId = '__proto__'
    ownId.catalog.model.sourceIds = ['__proto__']
    expect(validateSnapshot(ownId).sourceCoverage!.sources[1].id).toBe('__proto__')
  })

  test('rejects absent or unresolved source lineage, including prototype-looking IDs', () => {
    for (const id of [undefined, 'missing', 'constructor', '__proto__']) {
      const snapshot = coverageSnapshot()
      if (id === undefined) delete snapshot.benchmarks![0].sourceId
      else snapshot.benchmarks![0].sourceId = id
      expect(() => validateSnapshot(snapshot)).toThrow('sourceId')
    }
    for (const section of ['catalog', 'portfolios'] as const) {
      const snapshot = coverageSnapshot()
      Object.values(snapshot[section])[0].sourceIds = ['missing']
      expect(() => validateSnapshot(snapshot)).toThrow('sourceIds')
    }
    const artifact = coverageSnapshot()
    artifact.sourceCoverage!.sources[1].artifacts = ['absent.json']
    expect(() => validateSnapshot(artifact)).toThrow('artifact')
  })

  test('rejects duplicate identities and inherited registry fields', () => {
    const duplicateSource = coverageSnapshot()
    duplicateSource.sourceCoverage!.sources[1].id = 'OAI'
    const duplicateArtifact = coverageSnapshot()
    duplicateArtifact.sourceCoverage!.artifacts.push({ ...duplicateArtifact.sourceCoverage!.artifacts[0] })
    const inheritedSource = coverageSnapshot()
    inheritedSource.sourceCoverage!.sources[1] = Object.create(inheritedSource.sourceCoverage!.sources[1])
    const inheritedTotals = coverageSnapshot()
    inheritedTotals.sourceCoverage!.totals = Object.create(inheritedTotals.sourceCoverage!.totals)
    const inheritedExclusion = coverageSnapshot()
    inheritedExclusion.sourceCoverage!.artifacts[0].exclusions[0] = Object.create(inheritedExclusion.sourceCoverage!.artifacts[0].exclusions[0])
    const inheritedCoverage = coverageSnapshot()
    const coverage = inheritedCoverage.sourceCoverage
    delete inheritedCoverage.sourceCoverage
    const inheritedSnapshot = Object.assign(Object.create({ sourceCoverage: coverage }), inheritedCoverage)
    for (const snapshot of [duplicateSource, duplicateArtifact, inheritedSource, inheritedTotals, inheritedExclusion, inheritedSnapshot]) {
      expect(() => validateSnapshot(snapshot)).toThrow()
    }
  })

  test('rejects malformed types, enums, hashes and unsafe counters', () => {
    for (const patch of [
      { kind: 'primary' }, { status: 'complete' }, { url: 4 }, { evidenceType: null }, { checked: false },
      { limitations: [] }, { note: {} }, { artifacts: ['missing'] }, { benchmarkCount: '1' },
      { catalogReferences: -1 }, { portfolioReferences: 0.5 }, { assignmentReferences: Number.MAX_SAFE_INTEGER + 1 },
    ]) {
      const snapshot = coverageSnapshot()
      Object.assign(snapshot.sourceCoverage!.sources[1], patch)
      expect(() => validateSnapshot(snapshot)).toThrow()
    }
    for (const patch of [
      { sha256: 'g'.repeat(64) }, { sha256: 'a'.repeat(63) }, { kind: 2 }, { observed: Infinity }, { exclusions: {} },
      { exclusions: [{ locator: 1, reason: 'absent', count: 2 }] },
      { exclusions: [{ locator: 'row:1', reason: null, count: 2 }] },
      { exclusions: [{ locator: 'row:1', reason: 'absent', count: -1 }] },
    ]) {
      const snapshot = coverageSnapshot()
      Object.assign(snapshot.sourceCoverage!.artifacts[0], patch)
      expect(() => validateSnapshot(snapshot)).toThrow()
    }
    for (const patch of [{ generatedAt: null }, { scope: 1 }, { notes: [1] }, { sources: {} }, { artifacts: null }, { totals: [] }]) {
      const snapshot = coverageSnapshot()
      Object.assign(snapshot.sourceCoverage!, patch)
      expect(() => validateSnapshot(snapshot)).toThrow()
    }
  })

  test('rejects stale snapshot totals, source counts and impossible reconciliation', () => {
    for (const key of ['sources', 'artifacts', 'benchmarks', 'excluded'] as const) {
      const snapshot = coverageSnapshot()
      snapshot.sourceCoverage!.totals[key] += 1
      expect(() => validateSnapshot(snapshot)).toThrow('totals')
    }
    for (const patch of [{ benchmarkCount: 0 }, { status: 'context-only' }, { status: 'unavailable' }, { status: 'superseded' }, { kind: 'telemetry' }]) {
      const snapshot = coverageSnapshot()
      Object.assign(snapshot.sourceCoverage!.sources[1], patch)
      expect(() => validateSnapshot(snapshot)).toThrow()
    }
    for (const patch of [{ included: 6 }, { included: 4 }, { exclusions: [{ locator: 'rows', reason: 'Excluded', count: 3 }] }]) {
      const snapshot = coverageSnapshot()
      Object.assign(snapshot.sourceCoverage!.artifacts[0], patch)
      expect(() => validateSnapshot(snapshot)).toThrow()
    }
  })
})

describe('profile analysis exports', () => {
  test('keeps selected profile, currency-separated monthly totals, unspecified effort and exact evidence', () => {
    const snapshot = validSnapshot()
    snapshot.portfolios.plus.eur = '70'
    snapshot.benchmarks!.push({ ...snapshot.benchmarks![0], model: 'Other model', provenance: 'other.csv:L7' })
    const exported = presetAnalysis(snapshot, getPreset(snapshot, 'profile'))
    expect(exported.profile.id).toBe('profile')
    expect(exported.profile.subscriptions).toEqual({ openai: 'plus', claude: 'none', gateway: 'none', nan: false })
    expect(exported.profile.monthlySubscription).toEqual({ USD: 20, EUR: 70 })
    expect(exported.profile.routing.main.modelKey).toBe('model')
    expect(exported.profile.routing.main.effort).toBe('')
    expect(exported.profile.catalog.model.sourceUrls).toEqual(['https://example.org/model'])
    expect(exported.executable).toBe(false)
  })

  test('exports only source lineage relevant to the profile and excludes unrelated capture manifests', () => {
    const snapshot = coverageSnapshot()
    snapshot.sourceCoverage!.sources.push({
      ...snapshot.sourceCoverage!.sources[0], id: 'UNRELATED', title: 'Unrelated source',
      artifacts: ['unrelated.json'], portfolioReferences: 0,
    })
    snapshot.sourceCoverage!.artifacts.push({
      path: 'unrelated.json', sha256: 'b'.repeat(64), kind: 'capture', observed: 100, included: 0, excluded: 0, exclusions: [],
    })
    snapshot.sourceCoverage!.totals.sources += 1
    snapshot.sourceCoverage!.totals.artifacts += 1
    const references = presetAnalysis(validateSnapshot(snapshot), getPreset(snapshot, 'profile')).profile.sourceReferences!
    expect(references.sources.map(source => source.id)).toEqual(['OAI', 'MODEL'])
    expect(references.artifacts.map(artifact => artifact.path)).toEqual(['evidence.json'])
    expect(references.sources.some(source => source.id === 'UNRELATED')).toBe(false)
  })

  test('retains cybersecurity authorization gates and evidence limits without executable contract extensions', () => {
    const snapshot = validSnapshot()
    snapshot.meta.profile.domain = 'cybersecurity'
    snapshot.domainContracts = {
      cybersecurity: {
        label: 'Ciberseguridad', gate: 'Solo activos propios o autorización escrita; revisión humana.',
        critical: 'Impacto, exposición y secretos', routine: 'Análisis defensivo delimitado',
        scope: 'Auditoría defensiva y entornos autorizados',
        evidenceNote: 'Sin benchmarks específicos de ciberseguridad; código y agent-use no acreditan capacidad ciber.',
      },
    }
    Object.assign(snapshot.domainContracts.cybersecurity, { commands: ['execute-something'] })
    const exported = JSON.parse(JSON.stringify(presetAnalysis(parseSnapshot(JSON.stringify(snapshot)), getPreset(snapshot, 'profile'))))
    expect(exported.profile.domainContract.gate).toBe('Solo activos propios o autorización escrita; revisión humana.')
    expect(exported.profile.domainContract.evidenceNote).toBe('Sin benchmarks específicos de ciberseguridad; código y agent-use no acreditan capacidad ciber.')
    expect(exported.profile.domainContract.commands).toBeUndefined()
    expect(exported.executable).toBe(false)
  })

  test('quotes CSV cells and prefixes formula-leading role/model values while retaining blank effort', () => {
    const snapshot = validSnapshot()
    snapshot.catalog.model.name = '@IMPORTXML("https://example.org")'
    snapshot.catalog.model.selector = 'provider/model,"quoted"'
    const route = snapshot.routeDetails.profile.main
    snapshot.routeDetails.profile = { '=SUM(1,1)': route, '  -1+2': { ...route, condition: '@condition' } }
    const csv = presetRolesCsv(snapshot, getPreset(snapshot, 'profile'))
    expect(csv).toContain(`"'=SUM(1,1)","'@IMPORTXML(""https://example.org"")"`)
    expect(csv).toContain('"provider/model,""quoted"""')
    expect(csv).toContain("'  -1+2")
    expect(csv).toContain("'@condition")
  })
})
