import { describe, expect, test } from 'bun:test'
import { resolve } from 'node:path'
import fixtureData from './fixtures/access-snapshot.json'
import type { Snapshot } from '../src/data'
import { validateSnapshot } from '../src/snapshotIO'
import { getPreset, groupEquivalentPresets, presetNativeExport, presetRolesCsv, compatibleWithAvailability, providerParticipation } from '../src/presetStrategies'
import { compileAccessBundle, prepareAccessPreset } from '../src/accessExport'
import { originIdentity, resolveOrigin } from '../src/accessRouting'

const G = 'gentle-shell--plus-apps-balanced'
const O = 'omp--plus-apps-balanced'
function fixture(): Snapshot { return validateSnapshot(structuredClone(fixtureData)) }
const apiOptions = { mode: 'api' as const, apiConsent: true, maxAmount: 2, currency: 'USD', apiCredentialRef: 'api-main' }

describe('explicit access snapshot contract', () => {
  test('actual origin-bearing fixture is accepted', () => {
    const s = fixture()
    expect(s.meta[G].runtime?.version).toBe('1.1.0')
    expect(s.routeDetails[G].orchestrator.origin?.accessRouteId).toBe('chatgpt-legacy')
  })
  test('deleting only the access envelope cannot relabel origins as legacy', () => {
    const s = fixture(); delete s.access
    expect(() => validateSnapshot(s)).toThrow('parciales')
  })
  test('legacy snapshots remain inspectable but traced native export is refused', () => {
    const s = fixture(); delete s.access
    for (const meta of Object.values(s.meta)) { delete meta.targetId; delete meta.runtime; delete meta.harnessVersion }
    for (const routes of Object.values(s.routeDetails)) for (const route of Object.values(routes)) for (const ref of [route, route.fallback, route.accelerator]) if (ref) delete ref.origin
    validateSnapshot(s)
    expect(() => presetNativeExport(s, getPreset(s, G))).toThrow('sin origen')
  })
  test('forged service billing claims and credential material are rejected', () => {
    const s = fixture()
    Object.assign(s.routeDetails[G].orchestrator.origin!, { billing: 'free', apiKey: 'secret' })
    expect(() => validateSnapshot(s)).toThrow()
    const another = fixture()
    Object.assign(another.access!.resourcesByPortfolio.plus[0], { accessToken: 'secret' })
    expect(() => validateSnapshot(another)).toThrow()
  })
  test('missing resource and model-identity mismatches fail', () => {
    const s = fixture(); s.routeDetails[G].orchestrator.origin!.resourceId = 'missing'
    expect(() => validateSnapshot(s)).toThrow('recurso')
    const another = fixture(); another.routeDetails[G].orchestrator.origin!.modelId = 'openai:gpt-6-astra'
    expect(() => validateSnapshot(another)).toThrow('Identidad')
  })
  test('wrong plan, runtime version and invented verification claims fail', () => {
    const s = fixture(); s.routeDetails[G].orchestrator.origin!.plan = 'metered'
    expect(() => validateSnapshot(s)).toThrow('plan')
    const another = fixture(); another.meta[G].runtime!.version = '0.87.1'
    expect(() => validateSnapshot(another)).toThrow('versionado')
    const claimed = fixture(); Object.assign(claimed.access!, { evidenceState: 'runtime-verified' })
    expect(() => validateSnapshot(claimed)).toThrow('garantía')
  })
  test('source and resource references cannot be inherited', () => {
    const s = fixture(); s.routeDetails[G].orchestrator.origin = Object.create(s.routeDetails[G].orchestrator.origin!)
    expect(() => validateSnapshot(s)).toThrow('heredados')
  })
  test('retired SDD slots cannot enter current access-bearing snapshots', () => {
    const s = fixture()
    s.routeDetails[G]['sdd-design'] = structuredClone(s.routeDetails[G].orchestrator)
    s.routing[G]['sdd-design'] = [...s.routing[G].orchestrator]
    s.stats.rows += 1
    expect(() => validateSnapshot(s)).toThrow('SDD')
  })
})

describe('identity, availability and safe transport changes', () => {
  test('equivalence includes credential scope and runtime version, not just selector', () => {
    const s = fixture(), original = getPreset(s, G)
    const account = structuredClone(original); account.id = 'other-account'; account.aliases = [account.id]
    account.routes.orchestrator.origin!.credentialRef = 'another-account'
    expect(groupEquivalentPresets(s, [original, account])).toHaveLength(2)
    const runtime = structuredClone(original); runtime.id = 'other-runtime'; runtime.meta.runtime!.version = '0.99.0'
    expect(groupEquivalentPresets(s, [original, runtime])).toHaveLength(2)
    expect(originIdentity(original.routes.orchestrator.origin)).not.toEqual(originIdentity(account.routes.orchestrator.origin))
  })
  test('same-model SIWC keeps subscription origin, not API billing', () => {
    const s = fixture(), p = getPreset(s, G)
    const next = prepareAccessPreset(s, p, { mode: 'siwc' })
    const old = resolveOrigin(p.routes.orchestrator, p.meta.targetId!)
    const current = resolveOrigin(next.preset.routes.orchestrator, next.preset.meta.targetId!)
    expect(current.modelId).toBe(old.modelId)
    expect(current.selector).toStartWith('openai/')
    expect(current.authentication).toBe('siwc-oauth')
    expect(current.billing).toBe('subscription')
    expect(p.routes.orchestrator.origin!.accessRouteId).toBe('chatgpt-legacy')
  })
  test('SIWC unsupported by pinned OMP cannot fall back automatically', () => {
    const s = fixture()
    expect(() => prepareAccessPreset(s, getPreset(s, O), { mode: 'siwc' })).toThrow('no soportada')
  })
  test('same provider with mixed SIWC/API credentials is rejected', () => {
    const s = fixture(), p = getPreset(s, G)
    const next = prepareAccessPreset(s, p, { mode: 'siwc' })
    const resources = next.resources
    resources.push({ id: 'api-other', accessRouteId: 'openai-api', credentialRef: 'api-other', plan: 'metered' })
    next.preset.routes.orchestrator.origin = { ...next.preset.routes.orchestrator.origin!, accessRouteId: 'openai-api', resourceId: 'api-other', credentialRef: 'api-other', plan: 'metered' }
    expect(() => presetNativeExport(s, next.preset, { resources, authorization: { allowed: true, maxAmount: 2, currency: 'USD' } })).toThrow('ambiguo')
  })
  test('paid API needs explicit consent even with an available ChatGPT plan', () => {
    const s = fixture(), p = getPreset(s, G)
    for (const options of [{ mode: 'api' as const }, { ...apiOptions, apiConsent: false }, { ...apiOptions, maxAmount: 0 }, { ...apiOptions, maxAmount: NaN }]) {
      expect(() => prepareAccessPreset(s, p, options)).toThrow('autorización')
    }
  })
  test('API availability is not inferred from subscription selection', () => {
    const s = fixture(), p = prepareAccessPreset(s, getPreset(s, G), apiOptions).preset
    expect(compatibleWithAvailability(s, p, { openai: 'plus', claude: 'none', gateway: 'none', nan: false })).toBe(false)
    expect(compatibleWithAvailability(s, p, { openai: 'none', claude: 'none', gateway: 'none', nan: false, api: true })).toBe(true)
    expect(providerParticipation(s, p, null).find(r => r.pool === 'API')?.state).toBe('assigned')
  })
  test('CSV preserves resolved selector and account/resource provenance', () => {
    const s = fixture(), p = prepareAccessPreset(s, getPreset(s, G), apiOptions).preset
    const csv = presetRolesCsv(s, p)
    expect(csv).toContain('access_route,resource_id,credential_ref,plan')
    expect(csv).toContain('openai-api,api-export,api-main,metered')
    expect(csv).toContain('openai/gpt-6.1-sol')
  })
  test('API references are not accepted as token literals', () => {
    const s = fixture()
    expect(() => prepareAccessPreset(s, getPreset(s, G), { ...apiOptions, apiCredentialRef: 'sk-private' })).toThrow('credenciales')
  })
})

describe('native/manifests and Python adapter agreement', () => {
  test('native bytes are linked by SHA-256 and source objects remain unchanged', async () => {
    const s = fixture(), before = JSON.stringify(s)
    const result = await compileAccessBundle(s, getPreset(s, G), { mode: 'siwc' })
    const sha = new Bun.CryptoHasher('sha256').update(result.native.content).digest('hex')
    expect(result.manifest.nativeArtifact.sha256).toBe(sha)
    expect(result.manifest.validation.credentialDispatch).toBe('not-enforced')
    expect(result.manifest.validation.inferencesSent).toBe(0)
    expect(JSON.stringify(s)).toBe(before)
  })
  test('API export is explicitly metered and never advertises an enforced cap', async () => {
    const s = fixture(), result = await compileAccessBundle(s, getPreset(s, G), apiOptions)
    expect(result.manifest.roles.orchestrator.billing).toBe('metered')
    expect(result.manifest.meteredAuthorization?.enforcement).toContain('not a provider spending cap')
    expect(result.manifest.validation.performance).toBe('not-calibrated')
  })
  test('Gentle SIWC binding matches the Python CLI compiler field by field', async () => {
    const root = resolve(import.meta.dirname, '../..')
    const process = Bun.spawnSync(['python3', '-B', 'tests/compiler_bridge.py', 'examples/requests/gentle-chatgpt-siwc.json'], { cwd: root })
    expect(process.exitCode).toBe(0)
    const python = JSON.parse(process.stdout.toString())
    const s = fixture(), p = getPreset(s, G)
    p.id = python.manifest.profileName
    const browser = await compileAccessBundle(s, p, { mode: 'siwc' })
    expect(JSON.parse(browser.native.content)).toEqual(JSON.parse(python.native.content))
    const fields = ['selector', 'modelId', 'accessRouteId', 'authentication', 'billing', 'effort', 'resourceId', 'credentialRef', 'plan']
    for (const [role, row] of Object.entries(browser.manifest.roles)) for (const field of fields) {
      expect((row as unknown as Record<string, unknown>)[field]).toEqual(python.manifest.roles[role][field])
    }
  })
})


describe('final provenance boundary regressions', () => {
  test('runtime metadata cannot be inherited from a prototype', () => {
    const s = fixture()
    s.meta[G].runtime = Object.create(s.meta[G].runtime!)
    expect(() => validateSnapshot(s)).toThrow('heredados')
  })
  test('unknown domain extensions do not leak into compiled manifests', async () => {
    const s = fixture()
    Object.assign(s.domainContracts.apps, { executable: 'untrusted-extension' })
    const bundle = await compileAccessBundle(s, getPreset(s, G), { mode: 'preserve' })
    expect(Object.hasOwn(bundle.manifest.domainContract, 'executable')).toBe(false)
  })
  test('CSV carries complete reserve resource references, not only the route name', () => {
    const s = fixture()
    const csv = presetRolesCsv(s, getPreset(s, G))
    expect(csv).toContain('fallback_model_id,fallback_resource_id,fallback_credential_ref,fallback_plan')
    expect(csv).toContain('accelerator_model_id,accelerator_resource_id,accelerator_credential_ref,accelerator_plan')
  })
})
