import type { Benchmark, RouteDetail, Snapshot } from './data'

export interface AssignedModel {
  modelId?: string
  routeRelation?: string
  model: string
  efforts: string[]
  roles: string[]
}
export interface InsightRecord {
  row: Benchmark
  index: number
  configured: boolean
}
export interface InsightGroup {
  id: string
  benchmark: string
  unit: string
  methodology: string
  date: string
  records: InsightRecord[]
  comparable: boolean
}

export function assignedModels(snapshot: Pick<Snapshot, 'catalog'>, routes: Record<string, RouteDetail>): AssignedModel[] {
  const models = new Map<string, AssignedModel>()
  for (const [role, route] of Object.entries(routes)) {
    if (!route.enabled) continue
    const model = snapshot.catalog[route.modelKey].name
    const modelId = route.origin?.modelId || snapshot.catalog[route.modelKey].modelId
    const assigned = models.get(model) || { model, modelId, routeRelation: snapshot.catalog[route.modelKey].identityRelation, efforts: [], roles: [] }
    if (!assigned.efforts.includes(route.effort)) assigned.efforts.push(route.effort)
    assigned.roles.push(role)
    models.set(model, assigned)
  }
  return [...models.values()]
}

export function configuredRecord(row: Benchmark, models: AssignedModel[]) {
  return row.effort !== '' && row.effort !== 'no declarado' && models.some(model => rowMatchesModel(row, model) && model.efforts.includes(row.effort))
}

export function insightGroups(records: Benchmark[], models: AssignedModel[], includeOther: boolean, cost: boolean): InsightGroup[] {
  const groups = new Map<string, InsightGroup>()
  records.forEach((row, index) => {
    const evaluationCost = /\b(?:USD|EUR|GBP|JPY|CNY)\b|[$€£¥]/i.test(row.unit) || /\b(?:coste|cost)\b/i.test(row.benchmark)
    if (!models.some(model => model.model === row.model) || evaluationCost !== cost) return
    const configured = configuredRecord(row, models)
    if (!includeOther && !configured) return
    const methodology = row.methodology || ''
    // Unknown methodology/date/unit cannot establish a comparison, even for duplicate rows.
    const comparable = Boolean(methodology.trim() && row.date && row.unit && row.unit !== 'unidad no declarada')
    const id = JSON.stringify([row.benchmark, row.unit, methodology, row.date, ...(comparable ? [] : [row.provenance, row.source, index])])
    const group = groups.get(id) || { id, benchmark: row.benchmark, unit: row.unit, methodology, date: row.date, comparable, records: [] }
    group.records.push({ row, index, configured })
    groups.set(id, group)
  })
  return [...groups.values()]
}

export function chartDomain(records: InsightRecord[]) {
  let min = 0
  let max = 0
  let numeric = 0
  for (const { row } of records) {
    if (row.value === null || !Number.isFinite(row.value)) continue
    min = Math.min(min, row.value)
    max = Math.max(max, row.value)
    numeric++
  }
  return { min, max, numeric }
}

export type PairStatus = 'paired' | 'missing' | 'ambiguous' | 'other-denomination' | 'unlinked'

export interface ExplorerRecord {
  id: string
  result?: InsightRecord
  cost?: InsightRecord
  pairStatus: PairStatus
}

export interface ExplorerGroup {
  id: string
  benchmark: string
  resultGroup?: InsightGroup
  costGroup?: InsightGroup
  costUnit: string
  records: ExplorerRecord[]
}

const costSuffixes = [
  [' — coste registrado', 'USD (base no declarada)'],
  [' — coste por test', 'USD / test'],
  [' — coste por tarea', 'USD / task'],
] as const

function pairedBenchmark(row: Benchmark): string | undefined {
  const match = costSuffixes.find(([suffix, unit]) => row.benchmark.endsWith(suffix) && row.unit === unit)
  if (match) return row.benchmark.slice(0, -match[0].length)
}

function rowContext(row: Benchmark, benchmark: string): string | undefined {
  // A source URL or a methodology label alone never establishes a row-level join.
  if (!/^.+:L[1-9]\d*(?:;.*)?$/.test(row.provenance) || !row.source) return
  return JSON.stringify([benchmark, row.model, row.effort, row.family, row.source, row.date, row.methodology || '', row.provenance])
}

export function finiteValue(record: InsightRecord | undefined): record is InsightRecord {
  return record !== undefined && record.row.value !== null && Number.isFinite(record.row.value)
}

export function explorerGroups(records: Benchmark[], models: AssignedModel[], includeOther: boolean, options: TypedExplorerOptions = {}): ExplorerGroup[] {
  if (records.some(row => row.measurement)) return typedExplorerGroups(records, models, includeOther, options)
  const results = insightGroups(records, models, includeOther, false)
  const costs = insightGroups(records, models, includeOther, true)
  const resultContexts = new Map<string, InsightRecord[]>()
  const costContexts = new Map<string, InsightRecord[]>()
  for (const group of results) for (const record of group.records) {
    const key = rowContext(record.row, record.row.benchmark)
    if (key) {
      const matches = resultContexts.get(key) || []
      matches.push(record)
      resultContexts.set(key, matches)
    }
  }
  for (const group of costs) for (const record of group.records) {
    const benchmark = pairedBenchmark(record.row)
    const key = benchmark === undefined ? undefined : rowContext(record.row, benchmark)
    if (key) {
      const matches = costContexts.get(key) || []
      matches.push(record)
      costContexts.set(key, matches)
    }
  }
  const pairedCosts = new Set<number>()
  const groups: ExplorerGroup[] = []
  for (const resultGroup of results) {
    const linked = resultGroup.records.map(result => {
      const key = rowContext(result.row, result.row.benchmark)
      const candidates = key ? costContexts.get(key) || [] : []
      const ambiguous = candidates.length > 0 && (candidates.length !== 1 || resultContexts.get(key!)!.length !== 1)
      const cost = !ambiguous && candidates.length === 1 ? candidates[0] : undefined
      if (cost) pairedCosts.add(cost.index)
      return { result, cost, pairStatus: ambiguous ? 'ambiguous' : cost ? 'paired' : 'missing' } as const
    })
    const denominations = [...new Set(linked.flatMap(record => record.cost ? [record.cost.row.unit] : []))]
    // Each scatter scope has exactly one result context and one cost denomination.
    for (const costUnit of denominations.length ? denominations : ['']) {
      groups.push({
        id: JSON.stringify([resultGroup.id, costUnit]),
        benchmark: resultGroup.benchmark,
        resultGroup,
        costUnit,
        records: linked.map(record => ({
          id: `result-${record.result.index}`,
          result: record.result,
          cost: record.cost?.row.unit === costUnit ? record.cost : undefined,
          pairStatus: record.cost && record.cost.row.unit !== costUnit ? 'other-denomination' : record.pairStatus,
        })),
      })
    }
  }
  // Ambiguous, unrelated and undocumented imported costs remain available, never guessed.
  for (const costGroup of costs) {
    const unlinked = costGroup.records.filter(record => !pairedCosts.has(record.index))
    if (!unlinked.length) continue
    groups.push({
      id: JSON.stringify(['cost', costGroup.id]),
      benchmark: costGroup.benchmark,
      costGroup,
      costUnit: costGroup.unit,
      records: unlinked.map(cost => ({ id: `cost-${cost.index}`, cost, pairStatus: 'unlinked' })),
    })
  }
  return groups
}

export function rowMatchesModel(row: Benchmark, model: AssignedModel): boolean {
  // Only an explicit link to a published identity; candidate variants never silently match.
  if (row.measurement && model.modelId) return row.measurement.modelId === model.modelId
  return row.model === model.model
}
export function assignedLabel(row: Benchmark, models: AssignedModel[]): string {
  return models.find(model => rowMatchesModel(row, model))?.model || row.model
}
export interface TypedExplorerOptions { includeHistorical?: boolean; includeIssues?: boolean; includeOperational?: boolean }
export function typedExplorerGroups(records: Benchmark[], models: AssignedModel[], includeOther: boolean, options: TypedExplorerOptions, indexed?: InsightRecord[]): ExplorerGroup[] {
  const selected = (indexed || records.map((row,index) => ({row,index,configured:configuredRecord(row,models)})))
    .filter(r => r.row.measurement && models.some(model => rowMatchesModel(r.row,model))
      && (includeOther || r.configured)
      && (options.includeHistorical || r.row.measurement.scope === 'current')
      && (options.includeIssues || !r.row.measurement.issueIds.length))
  const costs = selected.filter(r => r.row.measurement!.kind === 'cost')
  const resultRows = selected.filter(r => ['capability','index'].includes(r.row.measurement!.kind)
    || (options.includeOperational && !['cost','price','unclassified'].includes(r.row.measurement!.kind)))
  const costIndex = new Map<string, InsightRecord[]>()
  for (const r of costs) {
    const m=r.row.measurement!
    if (!m.costLinkId || !m.primaryCost) continue
    const bucket=costIndex.get(m.costLinkId)||[];bucket.push(r);costIndex.set(m.costLinkId,bucket)
  }
  const groups=new Map<string,InsightGroup>()
  for (const r of resultRows) {
    const m=r.row.measurement!
    const key=JSON.stringify([m.metricId,m.protocolId])
    const group=groups.get(key)||{id:key,benchmark:r.row.benchmark,unit:r.row.unit,methodology:r.row.methodology||'',date:r.row.date,records:[],comparable:!m.issueIds.includes('opaque-protocol')}
    group.records.push(r);groups.set(key,group)
  }
  const output:ExplorerGroup[]=[],pairedCosts=new Set<number>()
  for (const resultGroup of groups.values()) {
    const evaluationCounts=new Map<string|null,number>()
    for(const r of resultGroup.records){const key=r.row.measurement!.evaluationId;evaluationCounts.set(key,(evaluationCounts.get(key)||0)+1)}
    const paired=resultGroup.records.map(result => {
      const m=result.row.measurement!, candidates=m.costLinkId?costIndex.get(m.costLinkId)||[]:[]
      // One evaluation may report multiple different constructs, but each construct must
      // have exactly one result and one cost in a given source/protocol/denomination.
      const sameMetric=evaluationCounts.get(m.evaluationId)||0
      const ambiguous=candidates.length>1 || (candidates.length>0 && sameMetric!==1)
      const cost=!ambiguous && candidates.length===1?candidates[0]:undefined
      if (cost) pairedCosts.add(cost.index)
      return {id:m.id,result,cost,pairStatus:ambiguous?'ambiguous':cost?'paired':'missing'} as ExplorerRecord
    })
    const units=[...new Set(paired.flatMap(r=>r.cost?[r.cost.row.unit]:[]))]
    for (const costUnit of units.length?units:['']) output.push({id:JSON.stringify([resultGroup.id,costUnit]),benchmark:resultGroup.benchmark,resultGroup,costUnit,records:paired.map(r=>r.cost && r.cost.row.unit!==costUnit?{...r,cost:undefined,pairStatus:'other-denomination'}:r)})
  }
  const unlinked=new Map<string,InsightGroup>()
  for(const r of costs.filter(r=>!pairedCosts.has(r.index))) {
    const m=r.row.measurement!,key=JSON.stringify([m.metricId,m.protocolId])
    const g=unlinked.get(key)||{id:key,benchmark:r.row.benchmark,unit:r.row.unit,methodology:r.row.methodology||'',date:r.row.date,records:[],comparable:!m.issueIds.includes('opaque-protocol')}
    g.records.push(r);unlinked.set(key,g)
  }
  for(const g of unlinked.values()) output.push({id:'cost:'+g.id,benchmark:g.benchmark,costGroup:g,costUnit:g.unit,records:g.records.map(cost=>({id:cost.row.measurement!.id,cost,pairStatus:'unlinked'}))})
  return output
}
