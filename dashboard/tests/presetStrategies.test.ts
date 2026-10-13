import { describe, expect, test } from 'bun:test'
import { YAML } from 'bun'
import type { RouteDetail, Snapshot } from '../src/data'
import { compatibleWithAvailability, getPreset, groupEquivalentPresets, marginalComparisons, presetAnalysis, serializePresetNative as presetNativeExport, presets, presetRolesCsv, providerParticipation } from '../src/presetStrategies'
import { parseSnapshot, validateSnapshot } from '../src/snapshotIO'
import { isValidProfileName, parseProfileExportTextWithDrops } from '../../tests/vendor/gentle-shell-4.0.0/agent-profiles'

function fixture(): Snapshot {
  const route = (modelKey: string, enabled = true): RouteDetail => ({ modelKey, effort: 'high', fallback: null, accelerator: null, enabled, condition: 'Canonical gate', rationale: 'Baseline source' })
  const portfolios = {
    plus: { label: 'Plus', usd: '20', eur: '0', openai: 'plus' as const, claude: 'none' as const, gateway: 'none' as const, nan: 'False' as const },
    'plus-nan': { label: 'Plus + NaN', usd: '20', eur: '70', openai: 'plus' as const, claude: 'none' as const, gateway: 'none' as const, nan: 'True' as const },
  }
  const catalog = {
    oai: { name: 'Same name', pool: 'OAI', selector: 'openai-codex/exact', efforts: ['high', 'low'], vision: true, evidence: '', integration: '' },
    nan: { name: 'Same name', pool: 'NAN', selector: 'nan/exact', efforts: ['high', 'low'], vision: null, evidence: '', integration: '' },
    go: { name: 'Same name', pool: 'GO', selector: 'opencode-go/exact', efforts: ['high'], vision: null, evidence: '', integration: '' },
  }
  const baseRoutes = { default: route('oai'), smol: route('oai'), advisor: route('go', false), advisor_deep: route('go', false), reviewer: route('oai') }
  const candidateRoutes = structuredClone(baseRoutes)
  candidateRoutes.smol = { ...route('nan'), fallback: { modelKey: 'oai', effort: 'high' }, condition: 'Bounded scope, source and oracle; no delegation of open critical decisions.', rationale: 'NaN-only candidate smol; original baseline smol remains fallback.' }
  const meta = { base: { portfolio: 'plus', harness: 'omp', domain: 'apps', objective: 'balanced' }, combined: { portfolio: 'plus-nan', harness: 'omp', domain: 'apps', objective: 'balanced' } }
  const routing = Object.fromEntries(Object.keys(meta).map(id => [id, Object.fromEntries(Object.keys(baseRoutes).map(role => [role, ['Same name', 'high'] as [string, string]]))]))
  return {
    stats: { rows: 10, profiles: 2, portfolios: 2, models: 3, groups: 2, validators: { passed: 1, failed: 0 }, session: 'test' },
    portfolios, catalog, domainContracts: { apps: { label: 'Desarrollo de software', gate: 'Scoped oracle', critical: 'Review decisions', routine: 'Bounded work', scope: 'Native and CLI' } }, coverage: {}, meta, routing,
    routeDetails: { base: baseRoutes, combined: structuredClone(baseRoutes) }, runtimePolicies: { base: { advisorEnabled: false, taskMaxConcurrency: 4 }, combined: { advisorEnabled: false, taskMaxConcurrency: 4 } },
    strategies: {
      'base::openai-led': { kind: 'openai-led', sourceProfile: 'base', portfolio: 'plus', routes: structuredClone(baseRoutes), coordinatorPool: 'OAI', offloadPool: null, limitations: ['Static baseline'] },
      'base::nan-volume': { kind: 'nan-volume', sourceProfile: 'base', portfolio: 'plus-nan', routes: candidateRoutes, coordinatorPool: 'OAI', offloadPool: 'NAN', limitations: ['Conditions need runtime integration'] },
    },
  }
}

const plus = { openai: 'plus', claude: 'none', gateway: 'none', nan: false } as const

describe('exact preset identities and availability', () => {
  test('same display name cannot conflate providers in analysis, CSV or availability', () => {
    const snapshot = fixture()
    const preset = getPreset(snapshot, 'base::nan-volume')
    const analysis = presetAnalysis(snapshot, preset)
    expect(analysis.profile.routing.smol.modelKey).toBe('nan')
    expect(Object.keys(analysis.profile.catalog).sort()).toEqual(['go', 'nan', 'oai'])
    expect(presetRolesCsv(snapshot, preset)).toContain('smol,Same name,nan/exact,NAN,high,true,')
    expect(compatibleWithAvailability(snapshot, preset, plus)).toBe(false)
    expect(compatibleWithAvailability(snapshot, preset, { ...plus, nan: true })).toBe(true)
    expect(compatibleWithAvailability(snapshot, getPreset(snapshot, 'base'), plus)).toBe(true)
  })

  test('extras are optional, plan identity is retained, and active reserves need availability', () => {
    const snapshot = fixture()
    const preset = getPreset(snapshot, 'base')
    expect(compatibleWithAvailability(snapshot, preset, { ...plus, claude: 'max', gateway: 'cc', nan: true })).toBe(true)
    expect(compatibleWithAvailability(snapshot, preset, { ...plus, openai: 'pro100' })).toBe(false)
    preset.routes.smol.accelerator = { modelKey: 'go', effort: 'high' }
    expect(compatibleWithAvailability(snapshot, preset, plus)).toBe(false)
    expect(compatibleWithAvailability(snapshot, preset, { ...plus, gateway: 'go' })).toBe(true)
    preset.routes.smol.enabled = false
    expect(compatibleWithAvailability(snapshot, preset, plus)).toBe(true)
    expect(compatibleWithAvailability(snapshot, preset, null)).toBe(true)
  })

  test('deduplicates equal configurations across portfolios and prefers explicit strategies', () => {
    const snapshot = fixture()
    const grouped = groupEquivalentPresets(snapshot, presets(snapshot))
    expect(grouped.map(item => item.id)).toEqual(['base::openai-led', 'base::nan-volume'])
    expect(grouped[0].aliases).toEqual(['base', 'combined', 'base::openai-led'])
    expect(getPreset(snapshot, 'base').coordinatorPool).toBe('OAI')
  })

  test('fallback, accelerator, effort, enabled, runtime and selector changes are distinct', () => {
    const snapshot = fixture()
    const original = getPreset(snapshot, 'base')
    const variants = [
      { ...original, routes: { ...original.routes, smol: { ...original.routes.smol, modelKey: 'nan' } } },
      { ...original, routes: { ...original.routes, smol: { ...original.routes.smol, effort: 'low' } } },
      { ...original, routes: { ...original.routes, smol: { ...original.routes.smol, fallback: { modelKey: 'nan', effort: 'high' } } } },
      { ...original, routes: { ...original.routes, smol: { ...original.routes.smol, accelerator: { modelKey: 'nan', effort: 'high' } } } },
      { ...original, routes: { ...original.routes, smol: { ...original.routes.smol, enabled: false } } },
      { ...original, runtime: { advisorEnabled: false, taskMaxConcurrency: 8 } },
    ]
    for (const variant of variants) {
      const distinct = { ...variant, id: 'distinct', aliases: ['distinct'] }
      expect(groupEquivalentPresets(snapshot, [original, distinct]).map(item => item.id)).toEqual(['base', 'distinct'])
    }
    const reordered = { ...original, runtime: { taskMaxConcurrency: 4, advisorEnabled: false } }
    expect(groupEquivalentPresets(snapshot, [original, reordered]).map(item => item.id)).toEqual(['base'])
  })
})

describe('configured participation and marginal changes', () => {
  test('disabled advisors do not imply assigned traffic or reserve consumption', () => {
    const snapshot = fixture()
    const states = providerParticipation(snapshot, getPreset(snapshot, 'base::nan-volume'), { ...plus, gateway: 'go', nan: true })
    expect(states.find(state => state.pool === 'GO')).toEqual({ pool: 'GO', state: 'available', roles: [], reserveRoles: [], inactiveRoles: ['advisor', 'advisor_deep'] })
    expect(states.find(state => state.pool === 'NAN')?.roles).toEqual(['smol'])
    expect(states.find(state => state.pool === 'OAI')?.reserveRoles).toEqual(['smol'])
    expect(states.find(state => state.pool === 'OAI')?.roles).toEqual(['default', 'reviewer'])
  })

  test('full routes expose reserve-only differences and runtime differences separately from primaries', () => {
    const snapshot = fixture()
    const preset = getPreset(snapshot, 'base::nan-volume')
    expect(marginalComparisons(snapshot, preset)).toEqual([{ portfolio: 'plus', profileId: 'base', changedRoles: 1, changedPrimaryRoles: 1, totalRoles: 5, removedPools: ['NAN'] }])
    preset.routes.smol = { ...snapshot.routeDetails.base.smol, fallback: { modelKey: 'nan', effort: 'high' } }
    expect(marginalComparisons(snapshot, preset)[0]).toMatchObject({ changedRoles: 1, changedPrimaryRoles: 0, removedPools: ['NAN'] })
    snapshot.runtimePolicies.base = { advisorEnabled: false, taskMaxConcurrency: 8 }
    expect(marginalComparisons(snapshot, preset)[0]).toMatchObject({ changedRoles: 5, changedPrimaryRoles: 0 })
  })
})

describe('safe imports and native exports', () => {
  test('requires new schema, exact model keys, supported efforts and matching runtime', () => {
    for (const field of ['routeDetails', 'runtimePolicies', 'strategies']) {
      const missing = fixture() as unknown as Record<string, unknown>
      delete missing[field]
      expect(() => validateSnapshot(missing)).toThrow('build_dashboard_snapshot.py')
    }
    for (const patch of [{ modelKey: 'constructor' }, { effort: 'unsupported' }, { enabled: false }]) {
      const snapshot = fixture()
      Object.assign(snapshot.routeDetails.base.smol, patch)
      expect(() => validateSnapshot(snapshot)).toThrow()
    }
    const inherited = fixture()
    inherited.routeDetails.base.smol = Object.create(inherited.routeDetails.base.smol)
    expect(() => validateSnapshot(inherited)).toThrow()
    expect(parseSnapshot(JSON.stringify(fixture())).strategies['base::nan-volume'].routes.smol.fallback).toEqual({ modelKey: 'oai', effort: 'high' })
  })

  test('rejects strategy changes to protected roles, missing fallback, invented roles and higher-risk domains', () => {
    for (const role of ['default', 'reviewer', 'advisor']) {
      const snapshot = fixture()
      snapshot.strategies['base::nan-volume'].routes[role] = { ...snapshot.strategies['base::nan-volume'].routes.smol }
      expect(() => validateSnapshot(snapshot)).toThrow('protegida')
    }
    const noFallback = fixture()
    noFallback.strategies['base::nan-volume'].routes.smol.fallback = null
    expect(() => validateSnapshot(noFallback)).toThrow('fallback')
    const extra = fixture()
    extra.strategies['base::nan-volume'].routes.invented = { ...extra.routeDetails.base.smol }
    expect(() => validateSnapshot(extra)).toThrow('roles')
    const risky = fixture()
    risky.meta.base.domain = 'agent-use'
    risky.domainContracts['agent-use'] = risky.domainContracts.apps
    expect(() => validateSnapshot(risky)).toThrow('no está aprobado')
  })

  test('OMP YAML is an exact primary map with nonaggressive audited runtime; reserves stay analytic', () => {
    const snapshot = fixture()
    const preset = getPreset(snapshot, 'base::nan-volume')
    const native = YAML.parse(presetNativeExport(snapshot, preset).content)
    expect(native).toEqual({ modelRoles: { default: 'openai-codex/exact:high', smol: 'nan/exact:high', advisor: 'opencode-go/exact:high', advisor_deep: 'opencode-go/exact:high', reviewer: 'openai-codex/exact:high' }, advisor: { enabled: false, syncBacklog: 'off' }, task: { eager: 'default', maxConcurrency: 4 } })
    expect(presetAnalysis(snapshot, preset).profile.routing.smol.fallback).toEqual({ modelKey: 'oai', effort: 'high' })
  })

  test('Gentle native exports use importable version-one schema with exact selectors and blank effort omitted', () => {
    const snapshot = fixture()
    snapshot.meta.base.harness = 'gentle-shell'
    snapshot.runtimePolicies.base = null
    snapshot.routeDetails.base = { 'sdd-orchestrator': { ...snapshot.routeDetails.base.default, effort: '' }, 'sdd-explore': snapshot.routeDetails.base.smol }
    const native = presetNativeExport(snapshot, getPreset(snapshot, 'base'))
    expect(JSON.parse(native.content)).toEqual({ kind: 'gentle-pi.agent_model_profile', version: 1, name: 'base', config: { 'sdd-orchestrator': { model: 'openai-codex/exact' }, 'sdd-explore': { model: 'openai-codex/exact', thinking: 'high' } } })
  })

  test('accepted imported IDs export native-valid distinct names, even after lossy normalization or truncation', () => {
    const snapshot = fixture()
    const ids = ['_custom', '__proto__', 'constructor', 'prototype', 'same/name', 'same:name', `${'a'.repeat(80)}x`, `${'a'.repeat(80)}y`, 'valid-native']
    const meta = { ...snapshot.meta.base, harness: 'gentle-shell' }
    const route = snapshot.routeDetails.base.default
    snapshot.meta = Object.fromEntries(ids.map(id => [id, { ...meta }]))
    snapshot.routing = Object.fromEntries(ids.map(id => [id, { orchestrator: ['Same name', 'high'] as [string, string] }]))
    snapshot.routeDetails = Object.fromEntries(ids.map(id => [id, { orchestrator: { ...route } }]))
    snapshot.runtimePolicies = Object.fromEntries(ids.map(id => [id, null]))
    snapshot.strategies = {}
    snapshot.stats.profiles = ids.length
    snapshot.stats.groups = ids.length
    snapshot.stats.rows = ids.length
    const imported = parseSnapshot(JSON.stringify(snapshot))
    const names = ids.map(id => {
      const native = presetNativeExport(imported, getPreset(imported, id))
      const parsed = parseProfileExportTextWithDrops(native.content)!
      expect(isValidProfileName(parsed.name)).toBe(true)
      expect(parsed.config).toEqual({ orchestrator: { model: 'openai-codex/exact', thinking: 'high' } })
      expect(parsed.droppedAgents).toEqual([])
      expect(presetNativeExport(imported, getPreset(imported, id)).content).toBe(native.content)
      return parsed.name
    })
    expect(names[names.length - 1]).toBe('valid-native')
    for (let index = 0; index < names.length; index += 1) {
      expect(names.filter(name => name === names[index])).toEqual([names[index]])
    }
    // A valid imported name can already match the generated fingerprint name.
    const occupied = names[0]
    imported.meta[occupied] = { ...meta }
    imported.routeDetails[occupied] = { orchestrator: { ...route } }
    imported.runtimePolicies[occupied] = null
    const renamed = parseProfileExportTextWithDrops(presetNativeExport(imported, getPreset(imported, '_custom')).content)!
    expect(renamed.name).not.toBe(occupied)
    expect(isValidProfileName(renamed.name)).toBe(true)
    expect(parseProfileExportTextWithDrops(presetNativeExport(imported, getPreset(imported, occupied)).content)!.name).toBe(occupied)
  })
})
