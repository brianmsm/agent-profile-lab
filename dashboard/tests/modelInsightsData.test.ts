import { describe, expect, test } from 'bun:test'
import type { Benchmark } from '../src/data'
import { assignedModels, chartDomain, configuredRecord, explorerGroups, finiteValue, insightGroups } from '../src/modelInsightsData'
import type { AssignedModel } from '../src/modelInsightsData'

const models: AssignedModel[] = [
  { model: 'GPT-6.1 Sol', efforts: ['medium', 'high'], roles: ['worker', 'reviewer'] },
  { model: 'GPT-6 Luna', efforts: ['low'], roles: ['explore'] },
  { model: 'MiMo V2.6 Flash', efforts: [''], roles: ['status'] },
]
const base: Benchmark = {
  model: 'GPT-6.1 Sol', family: 'GPT-6', benchmark: 'Benchmark', value: 48,
  unit: '%', effort: 'medium', source: 'https://example.org/sol', date: '2026-09-30',
  methodology: 'independent-AA', provenance: 'evidence.csv:L2', note: 'Original note',
}

describe('selected-profile benchmark scope', () => {
  test('selected candidate primaries define evidence scope, excluding disabled roles and fallback-only baseline models', () => {
    const catalog = {
      candidate: { name: 'Test candidate', pool: 'NAN', selector: 'nan/test-candidate', efforts: ['low'], vision: null, evidence: '', integration: '' },
      baseline: { name: 'Test baseline', pool: 'OAI', selector: 'openai/test-baseline', efforts: ['high'], vision: null, evidence: '', integration: '' },
    }
    const assigned = assignedModels({ catalog }, {
      smol: { modelKey: 'candidate', effort: 'low', fallback: { modelKey: 'baseline', effort: 'high' }, accelerator: null, enabled: true, condition: 'Bounded test scope', rationale: '' },
      tiny: { modelKey: 'candidate', effort: 'low', fallback: null, accelerator: null, enabled: true, condition: 'Bounded test scope', rationale: '' },
      advisor: { modelKey: 'baseline', effort: 'high', fallback: null, accelerator: null, enabled: false, condition: '', rationale: '' },
    })
    const records = [{ ...base, model: 'Test candidate', effort: 'low', value: 21 }, { ...base, model: 'Test baseline', effort: 'high', value: 48 }]
    expect(assigned).toEqual([{ model: 'Test candidate', efforts: ['low'], roles: ['smol', 'tiny'] }])
    expect(insightGroups(records, assigned, false, false).map(group => group.records.map(record => record.row))).toEqual([[records[0]]])
  })

  test('exact scope excludes other efforts, unassigned names and fabricated aliases', () => {
    const records = [base, { ...base, effort: 'max' }, { ...base, model: 'GPT-6 Sol' }, { ...base, model: 'GPT-6 Luna', effort: 'low', value: 21 }]
    const exact = insightGroups(records, models, false, false)
    expect(exact[0].records.map(record => [record.row.model, record.row.effort, record.row.value])).toEqual([
      ['GPT-6.1 Sol', 'medium', 48], ['GPT-6 Luna', 'low', 21],
    ])
    expect(insightGroups(records, models, true, false)[0].records.map(record => record.configured)).toEqual([true, false, true])
  })

  test('undeclared effort never proves a configured measurement, even for unspecified routing', () => {
    const records = [{ ...base, effort: '' }, { ...base, effort: 'no declarado' }, { ...base, model: 'MiMo V2.6 Flash', effort: '' }]
    expect(records.map(row => configuredRecord(row, models))).toEqual([false, false, false])
    expect(insightGroups(records, models, false, false)).toEqual([])
    expect(insightGroups(records, models, true, false)[0].records.map(record => record.row.effort)).toEqual(['', 'no declarado', ''])
  })
})

describe('comparison boundaries', () => {
  test('separates differing dates, units and explicitly declared methods', () => {
    const records = [base, { ...base, date: '2026-09-29' }, { ...base, unit: 'index points' }, { ...base, methodology: 'vendor-reported' }]
    expect(insightGroups(records, models, false, false).map(group => group.records.map(record => record.row))).toEqual(records.map(row => [row]))
  })

  test('missing methodology isolates every provenance record, including duplicate rows', () => {
    const records = [{ ...base, methodology: undefined }, { ...base, methodology: undefined }, { ...base, methodology: '', provenance: 'evidence.csv:L3' }]
    const groups = insightGroups(records, models, false, false)
    expect(groups.map(group => [group.comparable, group.records[0].index])).toEqual([[false, 0], [false, 1], [false, 2]])
    expect(new Set(groups.map(group => group.id)).size).toBe(3)
  })

  test('undeclared date or unit does not establish a comparable cohort', () => {
    const groups = insightGroups([{ ...base, date: '' }, { ...base, date: '' }, { ...base, unit: 'unidad no declarada' }, { ...base, unit: 'unidad no declarada' }], models, false, false)
    expect(groups.map(group => group.comparable)).toEqual([false, false, false, false])
  })

  test('duplicates, zero, negative and missing values are retained, never averaged or imputed', () => {
    const records = [{ ...base, value: -6 }, { ...base, value: 0 }, { ...base, value: null }, { ...base, value: -6 }]
    const [group] = insightGroups(records, models, false, false)
    expect(group.records.map(record => record.row.value)).toEqual([-6, 0, null, -6])
    expect(chartDomain(group.records)).toEqual({ min: -6, max: 0, numeric: 3 })
    expect(chartDomain(insightGroups([{ ...base, value: null }], models, false, false)[0].records)).toEqual({ min: 0, max: 0, numeric: 0 })
    expect(chartDomain(insightGroups([{ ...base, value: 0 }], models, false, false)[0].records)).toEqual({ min: 0, max: 0, numeric: 1 })
  })

  test('large imported cohorts preserve their complete numeric extent', () => {
    const records = Array.from({ length: 200_000 }, (_, index) => ({
      row: { ...base, value: index - 100_000, provenance: `evidence.csv:L${index + 2}` },
      index,
      configured: true,
    }))
    expect(chartDomain(records)).toEqual({ min: -100_000, max: 99_999, numeric: 200_000 })
  })

  test('evaluation costs stay separate from performance and from other denominations', () => {
    const records = [base, { ...base, benchmark: 'Evaluation cost', unit: 'USD / task', value: 0.31 }, { ...base, benchmark: 'Evaluation cost', unit: 'USD (base no declarada)', value: 0.21 }, { ...base, benchmark: 'Evaluation cost', unit: 'EUR / task', value: 0.28 }]
    expect(insightGroups(records, models, false, false)[0].records.map(record => record.row.value)).toEqual([48])
    expect(insightGroups(records, models, false, true).map(group => [group.unit, group.records[0].row.value])).toEqual([
      ['USD / task', 0.31], ['USD (base no declarada)', 0.21], ['EUR / task', 0.28],
    ])
  })
})

const associatedCost: Benchmark = { ...base, benchmark: `${base.benchmark} — coste registrado`, unit: 'USD (base no declarada)', value: 0.21 }

describe('row-level result and evaluation-cost pairing', () => {
  test('keeps zero, negative and missing values without manufacturing scatter points', () => {
    const records = [
      { ...base, value: 0 }, { ...associatedCost, value: 0 },
      { ...base, value: -6, provenance: 'evidence.csv:L3' }, { ...associatedCost, value: -0.002, provenance: 'evidence.csv:L3' },
      { ...base, value: null, provenance: 'evidence.csv:L4' }, { ...associatedCost, provenance: 'evidence.csv:L4' },
      { ...base, provenance: 'evidence.csv:L5' }, { ...associatedCost, value: null, provenance: 'evidence.csv:L5' },
      { ...base, provenance: 'evidence.csv:L6' },
    ]
    const [group] = explorerGroups(records, models, false)
    expect(group.records.map(record => [record.result?.row.value, record.cost?.row.value, record.pairStatus])).toEqual([
      [0, 0, 'paired'], [-6, -0.002, 'paired'], [null, 0.21, 'paired'], [48, null, 'paired'], [48, undefined, 'missing'],
    ])
    expect(group.records.filter(record => finiteValue(record.result) && finiteValue(record.cost)).map(record => record.result!.index)).toEqual([0, 2])
    expect(explorerGroups([], models, false)).toEqual([])
  })

  test.each([
    { name: 'duplicate cost candidates', records: [base, associatedCost, { ...associatedCost, value: 0.4 }], costs: [0.21, 0.4] },
    { name: 'duplicate result candidates', records: [base, { ...base, value: 52 }, associatedCost], costs: [0.21] },
  ])('rejects $name in both join directions', ({ records, costs }) => {
    const groups = explorerGroups(records, models, false)
    const resultScope = groups.find(group => group.resultGroup)!
    expect(resultScope.records.every(record => record.pairStatus === 'ambiguous' && record.cost === undefined)).toBe(true)
    const standaloneCosts = groups.filter(group => group.costGroup).flatMap(group => group.records)
    expect(standaloneCosts.map(record => record.cost!.row.value)).toEqual(costs)
  })

  test('requires exact benchmark, name, effort, family, source, date, method and row provenance', () => {
    const mismatches: Partial<Benchmark>[] = [
      { benchmark: 'Another benchmark — coste registrado' },
      { model: 'GPT-6 Luna', effort: 'low' },
      { effort: 'high' },
      { family: 'Other family' },
      { source: 'https://example.org/different-source' },
      { date: '2026-09-29' },
      { methodology: 'vendor-reported' },
      { provenance: 'evidence.csv:L3' },
    ]
    for (const mismatch of mismatches) {
      const groups = explorerGroups([base, { ...associatedCost, ...mismatch }], models, false)
      expect(groups.find(group => group.resultGroup)!.records[0].cost).toBeUndefined()
      expect(groups.filter(group => group.costGroup).flatMap(group => group.records).map(record => record.cost!.index)).toEqual([1])
    }
  })

  test('does not infer imported associations from a source URL or provenance category alone', () => {
    for (const provenance of ['', 'independent-AA', 'evidence.csv']) {
      const groups = explorerGroups([{ ...base, provenance }, { ...associatedCost, provenance }], models, false)
      expect(groups.map(group => group.records.map(record => [record.result?.index, record.cost?.index]))).toEqual([[[0, undefined]], [[undefined, 1]]])
    }
  })

  test('separates cost denominations and currencies without dropping the independent cost', () => {
    const taskResult = { ...base, provenance: 'evidence.csv:L3' }
    const groups = explorerGroups([
      base, associatedCost, taskResult,
      { ...associatedCost, benchmark: `${base.benchmark} — coste por tarea`, unit: 'USD / task', provenance: taskResult.provenance, value: 0.31 },
      { ...associatedCost, benchmark: `${base.benchmark} — coste por tarea`, unit: 'EUR / task', provenance: 'evidence.csv:L4', value: 0.28 },
      { ...base, provenance: 'evidence.csv:L4' },
    ], models, false)
    expect(groups.filter(group => group.resultGroup).map(group => [group.costUnit, group.records.flatMap(record => record.cost ? [record.cost.row.value] : [])])).toEqual([
      ['USD (base no declarada)', [0.21]], ['USD / task', [0.31]],
    ])
    expect(groups.filter(group => group.costGroup).map(group => [group.costUnit, group.records[0].cost!.row.value])).toEqual([['EUR / task', 0.28]])
    expect(groups[0].records[1].pairStatus).toBe('other-denomination')
    expect(groups[1].records[0].pairStatus).toBe('other-denomination')
  })

  test('pairs documented row mates while keeping unknown comparison context isolated', () => {
    for (const unknown of [{ methodology: '' }, { date: '' }, { unit: 'unidad no declarada' }]) {
      const result = { ...base, ...unknown }
      const cost = { ...associatedCost, methodology: result.methodology, date: result.date }
      const groups = explorerGroups([result, cost, { ...result, provenance: 'evidence.csv:L3' }, { ...cost, provenance: 'evidence.csv:L3' }], models, false)
      expect(groups.map(group => [group.resultGroup!.comparable, group.records.map(record => [record.result!.index, record.cost!.index])])).toEqual([
        [false, [[0, 1]]], [false, [[2, 3]]],
      ])
    }
  })
})
