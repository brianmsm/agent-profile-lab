import {selectionEvidence} from './selectionCandidates'
import type { AccessResource, RouteReference, Snapshot } from './data'
import type { Preset } from './presetStrategies'
import { presetNativeExport } from './presetStrategies'
import { resolveOrigin, targetForMeta, validateProfileOrigins, validateResource, requireMeteredAuthorization, hasMeteredRoutes } from './accessRouting'

export type OpenAIAccessMode = 'preserve' | 'legacy' | 'siwc' | 'api'
export interface ExportOptions {
  mode: OpenAIAccessMode
  apiCredentialRef?: string
  apiConsent?: boolean
  maxAmount?: number
  currency?: string
}
export function prepareAccessPreset(snapshot: Snapshot, preset: Preset, options: ExportOptions) {
  if (!snapshot.access) throw new Error('Snapshot histórico sin origen de acceso: permite análisis, pero no exportación nativa trazada. Regenera sus datos.')
  targetForMeta(preset.meta)
  if (!['preserve', 'legacy', 'siwc', 'api'].includes(options.mode)) throw new Error('Vía de exportación no admitida.')
  const sourceResources = snapshot.access.resourcesByPortfolio[preset.portfolio]
  if (!sourceResources) throw new Error('Falta inventario explícito del perfil.')
  const resources: AccessResource[] = structuredClone(sourceResources)
  const effective: Preset = { ...preset, routes: structuredClone(preset.routes) }
  let changed = false
  const remap = (ref: RouteReference) => {
    const origin = ref.origin
    if (!origin) throw new Error('Rol sin origen de modelo; no se infiere proveedor de facturación.')
    if (options.mode === 'preserve' || !['chatgpt-legacy', 'chatgpt-siwc'].includes(origin.accessRouteId)) return
    const routeId = options.mode === 'api' ? 'openai-api' : options.mode === 'siwc' ? 'chatgpt-siwc' : 'chatgpt-legacy'
    if (options.mode === 'api') {
      const resource: AccessResource = { id: 'api-export', accessRouteId: routeId, credentialRef: options.apiCredentialRef || 'api-main', plan: 'metered' }
      validateResource(resource)
      const existing = resources.find(item => item.id === resource.id)
      if (existing && JSON.stringify(existing) !== JSON.stringify(resource)) throw new Error('La referencia de recurso API colisiona con el inventario importado.')
      if (!existing) resources.push(resource)
      ref.origin = { ...origin, accessRouteId: routeId, resourceId: resource.id, credentialRef: resource.credentialRef, plan: resource.plan }
    } else {
      ref.origin = { ...origin, accessRouteId: routeId }
      const resource = resources.find(item => item.id === origin.resourceId)
      if (!resource) throw new Error('No existe el recurso ChatGPT de origen.')
      resource.accessRouteId = routeId
    }
    changed ||= origin.accessRouteId !== routeId
  }
  for (const route of Object.values(effective.routes)) for (const ref of [route, route.fallback, route.accelerator]) if (ref) remap(ref)
  const authorization = options.apiConsent ? { allowed: true as const, maxAmount: options.maxAmount!, currency: options.currency || 'USD' } : undefined
  requireMeteredAuthorization(hasMeteredRoutes(effective), authorization)
  validateProfileOrigins(snapshot, effective.meta, effective.routes, resources)
  return { preset: effective, resources, authorization, changed }
}

export async function compileAccessBundle(snapshot: Snapshot, original: Preset, options: ExportOptions) {
  const prepared = prepareAccessPreset(snapshot, original, options)
  const preset = prepared.preset
  const native = presetNativeExport(snapshot, preset, { resources: prepared.resources, authorization: prepared.authorization })
  if (!globalThis.crypto?.subtle) throw new Error('El manifiesto SHA-256 necesita un contexto seguro (HTTPS o localhost).')
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(native.content))
  const sha256 = [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('')
  const roles = Object.fromEntries(Object.entries(preset.routes).map(([role, route]) => [role, {
    ...resolveOrigin(route, preset.meta.targetId!), enabled: route.enabled, condition: route.condition, rationale: route.rationale,
    fallback: route.fallback ? resolveOrigin(route.fallback, preset.meta.targetId!) : null,
    accelerator: route.accelerator ? resolveOrigin(route.accelerator, preset.meta.targetId!) : null,
  }]))
  const domain = snapshot.domainContracts[preset.meta.domain]
  const domainContract = { label: domain.label, gate: domain.gate, critical: domain.critical, routine: domain.routine, scope: domain.scope, ...(domain.evidenceNote ? { evidenceNote: domain.evidenceNote } : {}), ...(domain.evidenceBoundary ? { evidenceBoundary: domain.evidenceBoundary } : {}) }
  const manifest = {
    format: 'agent-profile-lab.compiled-profile', schemaVersion: 1, compiler: 'dashboard',
    status: prepared.changed || preset.kind !== 'matrix' ? 'candidate' : 'baseline-projection',
    targetId: preset.meta.targetId, harness: preset.meta.harness, harnessVersion: preset.meta.harnessVersion, runtime: preset.meta.runtime,
    profileName: native.filename.replace(/\.export\.json$|\.yaml$/u, ''), domain: preset.meta.domain, objective: preset.meta.objective,
    sourceProfile: preset.sourceProfile, selectionPolicy: preset.kind, resources: prepared.resources,
    referencePortfolio: preset.portfolio, referencePortfolioMeaning: 'Fuente de decisiones; no coste total de la vía exportada.',
    meteredAuthorization: prepared.authorization ? { ...prepared.authorization, enforcement: 'declarative-only; not a provider spending cap' } : null,
    nanStaticPlan:preset.nanStaticPlan??null,
    selectionReview:preset.selectionReview?{...preset.selectionReview,evidence:preset.selectionReview.evidenceRefs.map(id=>selectionEvidence[id])}:null,
    activityPlan: preset.activityPlan ?? null, domainContract, roles,
    nativeArtifact: { filename: native.filename, sha256, encoding: 'utf-8' },
    inputsSha256: snapshot.access!.inputSha256,
    validation: { structural: 'passed', credentialDispatch: 'not-enforced', environment: 'not-checked', entitlement: 'not-verified', modelEffortAcceptance: 'not-verified-on-target', performance: 'not-calibrated', inferencesSent: 0 },
    limitations: ['El manifiesto no impone autenticación ni selecciona una cuenta; comprueba el runtime, variables de entorno, overrides y rotación.',
      'Reservas y aceleradores no se instalan automáticamente. Un selector no prueba equivalencia de checkpoint o esfuerzo.',
      'El presupuesto API es declarativo, no un límite aplicado por el proveedor.', ...preset.limitations],
  }
  return { native, manifest, prepared }
}
