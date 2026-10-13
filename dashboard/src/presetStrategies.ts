import type {NanStaticPlan} from './nanStaticProfiles'
import type {SelectionReview} from './selectionCandidates'
import type { ActivityPlan } from './activityProfiles'
import { originIdentity, referenceSelector, routePool, validateProfileOrigins, requireMeteredAuthorization, hasMeteredRoutes } from './accessRouting'
import type { MeteredAuthorization } from './accessRouting'
import type { AccessResource } from './data'
import { subscriptionsOf } from './data'
import type { ProfileMeta, RouteDetail, RuntimePolicy, Snapshot, SubscriptionSelection } from './data'

export type Preset = {
  id: string; meta: ProfileMeta; kind: 'matrix' | 'openai-led' | 'nan-volume' | 'activity-distributed' | 'reviewed-candidate' | 'nan-static' | 'nan-hybrid'; sourceProfile: string
  portfolio: string; routes: Record<string, RouteDetail>; runtime: RuntimePolicy | null
  activityPlan?: ActivityPlan
  selectionReview?: SelectionReview
  nanStaticPlan?: NanStaticPlan
  coordinatorPool: string; offloadPool: string | null; limitations: string[]; aliases: string[]
}

export function getPreset(snapshot: Snapshot, id: string): Preset {
  if (Object.hasOwn(snapshot.strategies, id)) {
    const strategy = snapshot.strategies[id]
    return { ...strategy, id, meta: { ...snapshot.meta[strategy.sourceProfile], portfolio: strategy.portfolio }, runtime: snapshot.runtimePolicies[strategy.sourceProfile], aliases: [id] }
  }
  if (!Object.hasOwn(snapshot.meta, id)) throw new Error(`No existe el preset ${id}.`)
  const meta = snapshot.meta[id]
  const routes = snapshot.routeDetails[id]
  const coordinator = ['default', 'sdd-orchestrator', 'orchestrator'].map(role => routes[role]).find(route => route?.enabled)
  return { id, meta, kind: 'matrix', sourceProfile: id, portfolio: meta.portfolio, routes, runtime: snapshot.runtimePolicies[id], coordinatorPool: coordinator ? snapshot.catalog[coordinator.modelKey].pool : 'unknown', offloadPool: null, limitations: ['Matriz canónica: configuración de referencia, no calibración empírica.'], aliases: [id] }
}

/** Group only identical *native selector maps* within the visible comparison scope.
 * Origin/conditions/plan stay on separate cards; this does not assert
 * equivalent quality, access, or complete runtime behavior. */
export function nativeMapEquivalence(snapshot:Snapshot,items:Preset[]):Map<string,string[]> {
  const groups=new Map<string,string[]>(),lookup=new Map<string,string[]>()
  for(const p of items){
    const roles=Object.entries(p.routes).filter(([,r])=>r.enabled||p.meta.harness==='omp')
      .sort(([a],[b])=>a.localeCompare(b))
      .map(([role,r])=>[role,referenceSelector(snapshot,r,p.meta.targetId),r.effort,r.enabled])
    const key=JSON.stringify([p.meta.targetId,p.meta.harness,p.runtime?.advisorEnabled??null,p.runtime?.taskMaxConcurrency??null,roles])
    const group=groups.get(key)||[];group.push(p.id);groups.set(key,group)
    lookup.set(p.id,group)
  }
  return lookup
}

export function presets(snapshot: Snapshot): Preset[] {
  return [...Object.keys(snapshot.meta), ...Object.keys(snapshot.strategies)].map(id => getPreset(snapshot, id))
}

export function poolAvailable(pool: string, selection: SubscriptionSelection): boolean {
  switch (pool) {
    case 'OAI': return selection.openai !== 'none'
    case 'ANTHROPIC': return selection.claude !== 'none'
    case 'CC': return selection.gateway === 'cc'
    case 'GO': return selection.gateway === 'go'
    case 'NAN': return selection.nan
    case 'API': return selection.api === true
    case 'ANTHROPIC_API': return selection.anthropicApi === true
    default: return false
  }
}


export function compatibleWithAvailability(snapshot: Snapshot, preset: Preset, selection: SubscriptionSelection | null): boolean {
  if (!selection) return true
  const required = subscriptionsOf(snapshot.portfolios[preset.portfolio])
  // Plan identity is a contract, not a claim that an upgraded plan is equivalent.
  const activePools = Object.values(preset.routes).filter(route => route.enabled)
    .flatMap(route => [route, ...[route.fallback, route.accelerator].filter(ref => ref !== null)])
    .map(ref => routePool(snapshot, ref))
  if (activePools.includes('OAI') && required.openai !== 'none' && required.openai !== selection.openai) return false
  if (activePools.includes('ANTHROPIC') && required.claude !== selection.claude) return false
  return activePools.every(pool => poolAvailable(pool, selection))
}

function routeIdentity(snapshot: Snapshot, route: RouteDetail | undefined): unknown {
  if (!route) return null
  return [snapshot.catalog[route.modelKey].selector, route.effort,
    route.fallback ? [snapshot.catalog[route.fallback.modelKey].selector, route.fallback.effort, originIdentity(route.fallback.origin)] : null,
    route.accelerator ? [snapshot.catalog[route.accelerator.modelKey].selector, route.accelerator.effort, originIdentity(route.accelerator.origin)] : null,
    route.enabled, originIdentity(route.origin), route.condition]
}

function identity(snapshot: Snapshot, preset: Preset): string {
  return JSON.stringify([preset.nanStaticPlan ?? null,preset.selectionReview ?? null,preset.activityPlan ?? null, preset.meta.targetId ?? null, preset.meta.harnessVersion ?? null, preset.meta.runtime ?? null, preset.meta.harness, preset.meta.domain, preset.meta.objective, snapshot.portfolios[preset.portfolio].openai,
    preset.runtime ? [preset.runtime.advisorEnabled, preset.runtime.taskMaxConcurrency] : null,
    Object.keys(preset.routes).sort().map(role => [role, routeIdentity(snapshot, preset.routes[role])])])
}

export function groupEquivalentPresets(snapshot: Snapshot, items: Preset[], options: { preferFirst?: boolean } = {}): Preset[] {
  const groups = new Map<string, Preset>()
  for (const preset of items) {
    const key = identity(snapshot, preset)
    const previous = groups.get(key)
    if (!previous) groups.set(key, { ...preset, aliases: [...preset.aliases] })
    else {
      const representative = !options.preferFirst && previous.kind === 'matrix' && preset.kind !== 'matrix' ? preset : previous
      groups.set(key, { ...representative, aliases: [...new Set([...previous.aliases, ...preset.aliases])] })
    }
  }
  return [...groups.values()]
}

export function providerParticipation(snapshot: Snapshot, preset: Preset, availability: SubscriptionSelection | null) {
  const pools = new Map<string, { pool: string; state: 'assigned' | 'reserve' | 'available'; roles: string[]; reserveRoles: string[]; inactiveRoles: string[] }>()
  const obtain = (pool: string) => {
    if (!pools.has(pool)) pools.set(pool, { pool, state: 'available', roles: [], reserveRoles: [], inactiveRoles: [] })
    return pools.get(pool)!
  }
  for (const [role, route] of Object.entries(preset.routes)) {
    const primary = obtain(routePool(snapshot, route))
    ;(route.enabled ? primary.roles : primary.inactiveRoles).push(role)
    for (const auxiliary of [route.fallback, route.accelerator]) if (auxiliary) {
      const entry = obtain(routePool(snapshot, auxiliary))
      ;(route.enabled ? entry.reserveRoles : entry.inactiveRoles).push(role)
    }
  }
  const available = availability ?? subscriptionsOf(snapshot.portfolios[preset.portfolio])
  for (const pool of ['OAI', 'ANTHROPIC', 'CC', 'GO', 'NAN', 'API', 'ANTHROPIC_API']) if (poolAvailable(pool, available)) obtain(pool)
  return [...pools.values()].map(entry => ({ ...entry, state: entry.roles.length ? 'assigned' as const : entry.reserveRoles.length ? 'reserve' as const : 'available' as const,
    roles: [...new Set(entry.roles)].sort(), reserveRoles: [...new Set(entry.reserveRoles)].sort(), inactiveRoles: [...new Set(entry.inactiveRoles)].sort() }))
}

export function marginalComparisons(snapshot: Snapshot, preset: Preset) {
  const original = subscriptionsOf(snapshot.portfolios[preset.portfolio])
  return Object.entries(snapshot.meta).flatMap(([profileId, meta]) => {
    if (meta.harness !== preset.meta.harness || meta.domain !== preset.meta.domain || meta.objective !== preset.meta.objective || meta.portfolio === preset.portfolio) return []
    const reduced = subscriptionsOf(snapshot.portfolios[meta.portfolio])
    const subset = reduced.openai === original.openai && (reduced.claude === 'none' || reduced.claude === original.claude)
      && (reduced.gateway === 'none' || reduced.gateway === original.gateway) && (!reduced.nan || original.nan)
    if (!subset || JSON.stringify(reduced) === JSON.stringify(original)) return []
    const routes = snapshot.routeDetails[profileId]
    const roles = [...new Set([...Object.keys(preset.routes), ...Object.keys(routes)])]
    const comparisonRuntime = snapshot.runtimePolicies[profileId]
    const runtimeDiffers = preset.runtime?.advisorEnabled !== comparisonRuntime?.advisorEnabled || preset.runtime?.taskMaxConcurrency !== comparisonRuntime?.taskMaxConcurrency
    const changedRoles = roles.filter(role => runtimeDiffers || JSON.stringify(routeIdentity(snapshot, preset.routes[role])) !== JSON.stringify(routeIdentity(snapshot, routes[role]))).length
    const changedPrimaryRoles = roles.filter(role => {
      const left = preset.routes[role], right = routes[role]
      return !left || !right || snapshot.catalog[left.modelKey].selector !== snapshot.catalog[right.modelKey].selector || left.effort !== right.effort || left.enabled !== right.enabled || JSON.stringify(originIdentity(left.origin)) !== JSON.stringify(originIdentity(right.origin))
    }).length
    const removedPools = ['OAI', 'ANTHROPIC', 'CC', 'GO', 'NAN'].filter(pool => poolAvailable(pool, original) && !poolAvailable(pool, reduced))
    return [{ portfolio: meta.portfolio, profileId, changedRoles, changedPrimaryRoles, totalRoles: roles.length, removedPools }]
  })
}

export function presetAnalysis(snapshot: Snapshot, preset: Preset, availability?: SubscriptionSelection | null) {
  const keys = new Set(Object.values(preset.routes).flatMap(route => [route.modelKey, ...[route.fallback, route.accelerator].flatMap(aux => aux ? [aux.modelKey] : [])]))
  const catalog = Object.fromEntries([...keys].map(key => [key, snapshot.catalog[key]]))
  const sourceIds = new Set([...(snapshot.portfolios[preset.portfolio].sourceIds ?? []), ...Object.values(catalog).flatMap(model => model.sourceIds ?? [])])
  const sources = snapshot.sourceCoverage?.sources.filter(source => sourceIds.has(source.id) || Object.values(catalog).some(model => model.sourceUrls?.includes(source.url))) ?? []
  const artifactPaths = new Set(sources.flatMap(source => source.artifacts))
  const contract = snapshot.domainContracts[preset.meta.domain]
  const domainContract = { label: contract.label, gate: contract.gate, critical: contract.critical, routine: contract.routine, scope: contract.scope, ...(contract.evidenceNote ? { evidenceNote: contract.evidenceNote } : {}), ...(contract.evidenceBoundary ? { evidenceBoundary: contract.evidenceBoundary } : {}) }
  return { format: 'agent-profile-lab.profile-analysis', version: 3, executable: false, profile: {
    id: preset.id, kind: preset.kind, sourceProfile: preset.sourceProfile, meta: preset.meta, domainContract,
    subscriptions: subscriptionsOf(snapshot.portfolios[preset.portfolio]), portfolio: snapshot.portfolios[preset.portfolio],
    monthlySubscription: { USD: Number(snapshot.portfolios[preset.portfolio].usd), EUR: Number(snapshot.portfolios[preset.portfolio].eur) },
    access: snapshot.access ? { evidenceState: snapshot.access.evidenceState, resources: snapshot.access.resourcesByPortfolio[preset.portfolio], inputSha256: snapshot.access.inputSha256 } : null,
    monthlySubscriptionMeaning: 'Reference portfolio only; excludes metered usage and does not prove the cost of exported access choices.',
    nanStaticPlan:preset.nanStaticPlan ?? null, selectionReview:preset.selectionReview ?? null, activityPlan: preset.activityPlan ?? null, routing: preset.routes, runtime: preset.runtime, catalog, provenance: snapshot.provenance,
    participation: providerParticipation(snapshot, preset, availability ?? null), participationMeaning: 'Configured routes, not observed traffic or token shares.',
    limitations: [...preset.limitations, 'Native primary-model exports do not install or enforce fallback, accelerator or scope conditions; reserves and bounded conditions require runtime integration.', 'Marginal comparisons describe configuration differences, not performance. Runtime differences affect all roles.', 'Name-only benchmark records cannot establish exact-selector strategy performance.'],
    sourceReferences: snapshot.sourceCoverage ? { scope: snapshot.sourceCoverage.scope, generatedAt: snapshot.sourceCoverage.generatedAt, counterScope: 'Counters describe the active snapshot, not this selected preset.', sources, artifacts: snapshot.sourceCoverage.artifacts.filter(artifact => artifactPaths.has(artifact.path)) } : undefined,
  } }
}

function csvCell(value: string): string {
  let start = 0
  while (start < value.length && (value.charCodeAt(start) <= 31 || value.charCodeAt(start) === 127 || /\s/u.test(value[start]))) start += 1
  const safe = start < value.length && '=+@-'.includes(value[start]) ? `'${value}` : value
  return /[",\r\n]/u.test(safe) ? `"${safe.replace(/"/gu, '""')}"` : safe
}

export function presetRolesCsv(snapshot: Snapshot, preset: Preset): string {
  const rows = [['role', 'model', 'selector', 'provider', 'effort', 'enabled', 'condition', 'fallback_selector', 'fallback_effort', 'accelerator_selector', 'model_id', 'access_route', 'resource_id', 'credential_ref', 'plan', 'fallback_access_route', 'accelerator_access_route', 'fallback_model_id', 'fallback_resource_id', 'fallback_credential_ref', 'fallback_plan', 'accelerator_model_id', 'accelerator_resource_id', 'accelerator_credential_ref', 'accelerator_plan'],
    ...Object.entries(preset.routes).sort(([a], [b]) => a.localeCompare(b)).map(([role, route]) => {
      const model = snapshot.catalog[route.modelKey]
      return [role, model.name, referenceSelector(snapshot, route, preset.meta.targetId), routePool(snapshot, route), route.effort, String(route.enabled), route.condition, route.fallback ? referenceSelector(snapshot, route.fallback, preset.meta.targetId) : '', route.fallback?.effort ?? '', route.accelerator ? referenceSelector(snapshot, route.accelerator, preset.meta.targetId) : '', route.origin?.modelId ?? '', route.origin?.accessRouteId ?? '', route.origin?.resourceId ?? '', route.origin?.credentialRef ?? '', route.origin?.plan ?? '', route.fallback?.origin?.accessRouteId ?? '', route.accelerator?.origin?.accessRouteId ?? '', route.fallback?.origin?.modelId ?? '', route.fallback?.origin?.resourceId ?? '', route.fallback?.origin?.credentialRef ?? '', route.fallback?.origin?.plan ?? '', route.accelerator?.origin?.modelId ?? '', route.accelerator?.origin?.resourceId ?? '', route.accelerator?.origin?.credentialRef ?? '', route.accelerator?.origin?.plan ?? '']
    })]
  return rows.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n'
}

function nativeProfileName(snapshot: Snapshot, requestedId: string): string {
  const ids = [...new Set([...Object.keys(snapshot.meta), ...Object.keys(snapshot.strategies), requestedId])].sort()
  const validIds = ids.filter(id => /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/u.test(id) && !['constructor', 'prototype'].includes(id))
  if (validIds.includes(requestedId)) return requestedId
  const used = new Set(validIds)
  for (const id of ids) {
    if (used.has(id)) continue
    // A two-lane stable fingerprint distinguishes lossy normalization/truncation.
    // The used-name check also resolves actual collisions within this snapshot.
    let left = 0x811c9dc5
    let right = 0x9e3779b9
    for (let index = 0; index < id.length; index += 1) {
      left = Math.imul(left ^ id.charCodeAt(index), 0x01000193)
      right = Math.imul(right ^ id.charCodeAt(index), 0x85ebca6b)
    }
    const fingerprint = (left >>> 0).toString(16).padStart(8, '0') + (right >>> 0).toString(16).padStart(8, '0')
    const slug = id.replace(/[^A-Za-z0-9._-]/gu, '-')
    const prefix = /^[A-Za-z0-9]/u.test(slug) ? slug : `preset-${slug}`
    const stem = `${prefix.slice(0, 47)}-${fingerprint}`
    let name = stem
    let collision = 0
    while (used.has(name)) {
      collision += 1
      const suffix = `-${collision}`
      name = stem.slice(0, 64 - suffix.length) + suffix
    }
    used.add(name)
    if (id === requestedId) return name
  }
  throw new Error('No se pudo generar un nombre nativo para el preset.')
}

/** Low-level format serializer. User-facing exports must use presetNativeExport. */
export function serializePresetNative(snapshot: Snapshot, preset: Preset): { filename: string; content: string; mimeType: string } {
  const name = nativeProfileName(snapshot, preset.id)
  if (preset.meta.harness === 'gentle-shell') {
    const config = Object.fromEntries(Object.entries(preset.routes).filter(([, route]) => route.enabled).map(([role, route]) => [role, { model: referenceSelector(snapshot, route, preset.meta.targetId), ...(route.effort ? { thinking: route.effort } : {}) }]))
    return { filename: `${name}.export.json`, mimeType: 'application/json', content: JSON.stringify({ kind: 'gentle-pi.agent_model_profile', version: 1, name, config }, null, 2) + '\n' }
  }
  if (preset.meta.harness !== 'omp') throw new Error('Harness no soportado; no se trata como OMP por defecto.')
  if (!preset.runtime) throw new Error('El preset OMP necesita una política runtime explícita.')
  // OMP advisor activation belongs to runtime policy; disabled advisor selectors remain configured.
  const lines = ['# Primary model map only. Reserves and scope conditions require runtime integration.', '# Fallbacks, accelerators and conditions are NOT installed or enforced by this export.', 'modelRoles:', ...Object.entries(preset.routes).map(([role, route]) => `  ${JSON.stringify(role)}: ${JSON.stringify(referenceSelector(snapshot, route, preset.meta.targetId) + (route.effort ? `:${route.effort}` : ''))}`), 'advisor:', `  enabled: ${preset.runtime.advisorEnabled}`, '  syncBacklog: "off"', 'task:', '  eager: "default"', `  maxConcurrency: ${preset.runtime.taskMaxConcurrency}`]
  return { filename: `${name}.yaml`, mimeType: 'application/yaml', content: lines.join('\n') + '\n' }
}

export function presetNativeExport(snapshot: Snapshot, preset: Preset, options?: { resources?: AccessResource[]; authorization?: MeteredAuthorization }) {
  if (!snapshot.access) throw new Error('No se exporta un perfil nativo sin origen explícito. Regenera el snapshot histórico.')
  const resources = options?.resources ?? snapshot.access.resourcesByPortfolio[preset.portfolio]
  if (!resources) throw new Error('Inventario de acceso ausente.')
  validateProfileOrigins(snapshot, preset.meta, preset.routes, resources)
  requireMeteredAuthorization(hasMeteredRoutes(preset), options?.authorization)
  return serializePresetNative(snapshot, preset)
}
