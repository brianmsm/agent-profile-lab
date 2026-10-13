import accessJson from '../../catalog/access-routes.json'
import plansJson from '../../catalog/resource-plans.json'
import offeringsJson from '../../catalog/offerings.json'
import harnessJson from '../../contracts/harnesses.json'
import type { AccessOrigin, AccessResource, ProfileMeta, RouteDetail, RouteReference, Snapshot } from './data'

interface AccessRoute { label: string; service: string; authentication: string; billing: 'subscription' | 'metered'; pool: string }
interface ModelBinding { modelId: string; accessRouteId: string; nativeModelId: string; efforts: string[]; offeringKey: string; identityRelation: string; availability: string }
interface Target { harness: string; harnessVersion: string; runtime: { name: string; version: string }; providers: Record<string, string> }
interface Harness { harnessVersion: string; runtime: { name: string; version: string }; roles: Record<string, { functionId: string; boundedOffload?: boolean }>; excludedRoles: { domain: string; objectives: string[]; roles: string[] }[] }
export const accessRoutes = accessJson.routes as Record<string, AccessRoute>
export const accessTargets = accessJson.targets as Record<string, Target>
const bindings = accessJson.modelBindings as Record<string, ModelBinding>
const plans = plansJson.plans as Record<string, { service: string; billing: string; plan: string; allowedModelIds?: string[] }>
const offerings = offeringsJson.offerings as Record<string, { modelId: string; identityRelation: string; defaultAccessRouteId: string; compatibility: { selector: string; vision?: boolean | null } }>
const harnesses = harnessJson.harnesses as Record<string, Harness>
const REF = /^[A-Za-z][A-Za-z0-9._-]{0,95}$/u
const originFields = ['modelId', 'accessRouteId', 'resourceId', 'credentialRef', 'plan']

function ownObject(value: unknown, fields: string[], label: string): asserts value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).some(key => !fields.includes(key)) || fields.some(key => !Object.hasOwn(value, key))) throw new Error(`${label}: campos ausentes, heredados o no admitidos.`)
}
function reference(value: unknown, label: string): asserts value is string {
  if (typeof value !== 'string' || !REF.test(value) || /^(sk[-_]|bearer|token-)/iu.test(value)) throw new Error(`${label}: usa una referencia abstracta, no credenciales ni rutas.`)
}
export function originIdentity(origin?: AccessOrigin): unknown {
  return origin ? [origin.modelId, origin.accessRouteId, origin.resourceId, origin.credentialRef, origin.plan] : null
}
export function routePool(snapshot: Snapshot, route: RouteReference): string {
  const id = route.origin?.accessRouteId
  return id && Object.hasOwn(accessRoutes, id) ? accessRoutes[id].pool : snapshot.catalog[route.modelKey].pool
}
export function targetForMeta(meta: ProfileMeta): Target {
  const id = meta.targetId
  if (!id || !Object.hasOwn(accessTargets, id)) throw new Error('Destino/versiones no declarados o no soportados; regenera con el contrato actual.')
  const target = accessTargets[id]
  ownObject(meta.runtime, ['name', 'version'], 'runtime')
  if (!Object.hasOwn(meta, 'harnessVersion') || !Object.hasOwn(meta, 'runtime') || meta.harness !== target.harness || meta.harnessVersion !== target.harnessVersion
    || meta.runtime?.name !== target.runtime.name || meta.runtime?.version !== target.runtime.version) throw new Error('Metadatos del destino no coinciden con su contrato versionado.')
  const contract = harnesses[target.harness]
  if (!contract || contract.harnessVersion !== target.harnessVersion || contract.runtime.version !== target.runtime.version) throw new Error('Adaptador y contrato de harness desincronizados.')
  return target
}
export function expectedRoles(meta: ProfileMeta): string[] {
  const target = targetForMeta(meta), contract = harnesses[target.harness]
  let roles = Object.keys(contract.roles)
  for (const rule of contract.excludedRoles) if (rule.domain === meta.domain && rule.objectives.includes(meta.objective)) roles = roles.filter(role => !rule.roles.includes(role))
  return roles
}
export function resolveOrigin(referenceValue: RouteReference, targetId: string) {
  const origin = referenceValue.origin
  ownObject(origin, originFields, 'Origen de modelo')
  for (const key of originFields) if (typeof origin[key] !== 'string' || !origin[key]) throw new Error(`Origen.${key} debe ser texto explícito.`)
  for (const key of ['resourceId', 'credentialRef', 'plan']) reference(origin[key], `Origen.${key}`)
  const typed = origin as unknown as AccessOrigin
  if (!Object.hasOwn(accessTargets, targetId)) throw new Error('Destino/versiones no soportados.')
  const target = accessTargets[targetId]
  if (!Object.hasOwn(target.providers, typed.accessRouteId)) throw new Error(`Vía ${typed.accessRouteId} no soportada en este destino; no se sustituye por API ni legacy.`)
  const key = typed.modelId + '|' + typed.accessRouteId
  if (!Object.hasOwn(bindings, key)) throw new Error('No existe un binding revisado para este modelo y vía.')
  const binding = bindings[key], route = accessRoutes[typed.accessRouteId]
  if (binding.availability === 'historical-not-in-current-inventory') throw new Error('Modelo histórico no incluido en el inventario de cuenta confirmado.')
  if (referenceValue.effort && !binding.efforts.includes(referenceValue.effort)) throw new Error('Esfuerzo incompatible con la vía seleccionada.')
  const planKey = route.service + '|' + typed.plan
  if (!Object.hasOwn(plans, planKey) || plans[planKey].billing !== route.billing) throw new Error('El plan no corresponde al servicio y facturación de la vía.')
  if (plans[planKey].allowedModelIds && !plans[planKey].allowedModelIds!.includes(typed.modelId)) throw new Error('Modelo fuera del inventario de cuenta.')
  return { ...typed, selector: target.providers[typed.accessRouteId] + '/' + binding.nativeModelId,
    provider: target.providers[typed.accessRouteId], effort: referenceValue.effort, service: route.service,
    authentication: route.authentication, billing: route.billing, identityRelation: binding.identityRelation,
    offeringKey: binding.offeringKey, availability: binding.availability, routeCalibration: 'not-established' as const }
}
export function validateResource(resource: unknown): asserts resource is AccessResource {
  ownObject(resource, ['id', 'accessRouteId', 'credentialRef', 'plan'], 'Recurso')
  for (const key of ['id', 'credentialRef', 'plan']) reference(resource[key], 'Recurso.' + key)
  if (typeof resource.accessRouteId !== 'string' || !Object.hasOwn(accessRoutes, resource.accessRouteId)) throw new Error('Vía de recurso desconocida.')
  const route = accessRoutes[resource.accessRouteId], key = route.service + '|' + String(resource.plan)
  if (!Object.hasOwn(plans, key) || plans[key].billing !== route.billing) throw new Error('Plan/recurso incoherente.')
}
export function validateProfileOrigins(snapshot: Snapshot, meta: ProfileMeta, routes: Record<string, RouteDetail>, resources: AccessResource[]) {
  const target = targetForMeta(meta), expected = expectedRoles(meta)
  if (Object.keys(routes).length !== expected.length || expected.some(role => !Object.hasOwn(routes, role))) throw new Error('Roles no admitidos por el contrato actual; no se exportan roles SDD retirados.')
  const owners = new Map<string, string>()
  const gate=snapshot.domainContracts[meta.domain]?.gate
  const functions=harnesses[meta.harness].roles
  for (const [role, route] of Object.entries(routes)) {
    if(!gate||!route.condition.includes(gate))throw new Error(`${role}: la condición no contiene el contrato de aceptación de su dominio.`)
    for (const item of [route, route.fallback, route.accelerator]) {
      if (!item) continue
      const bound = resolveOrigin(item, meta.targetId!)
      const model = snapshot.catalog[item.modelKey]
      if (!Object.hasOwn(offerings, item.modelKey) || model.modelId !== bound.modelId || offerings[item.modelKey].modelId !== bound.modelId
        || model.selector !== offerings[item.modelKey].compatibility.selector) throw new Error('Identidad de catálogo y origen no coinciden.')
      if(route.enabled&&functions[role].functionId==='visual-inspection'&&offerings[bound.offeringKey].compatibility.vision!==true)throw new Error(`${role}: esta vía no declara entrada de imagen; la capacidad visual también se exige a reservas y aceleradores.`)
      if(item!==route && item.effort===route.effort && JSON.stringify(originIdentity(item.origin))===JSON.stringify(originIdentity(route.origin)))throw new Error(`${role}: reserva idéntica al principal; un reintento no es una ruta alternativa.`)
      const match = resources.find(resource => resource.id === bound.resourceId)
      if (!match || match.accessRouteId !== bound.accessRouteId || match.credentialRef !== bound.credentialRef || match.plan !== bound.plan) throw new Error(`${role}: recurso y referencia de credenciales no declarados de forma coherente.`)
    }
    if (route.enabled) for(const item of [route,route.fallback,route.accelerator]) {
      if(!item)continue
      const origin = item.origin!, provider = target.providers[origin.accessRouteId], owner = JSON.stringify(originIdentity({ ...origin, modelId: '' }))
      if (owners.has(provider) && owners.get(provider) !== owner) throw new Error(`Namespace ${provider} ambiguo: principales y reservas no pueden seleccionar dos cuentas o mecanismos de autenticación. Usa runtimes aislados.`)
      owners.set(provider, owner)
    }
  }
}
export function validateAccessSnapshot(snapshot: Snapshot): void {
  const allRoutes = [...Object.values(snapshot.routeDetails), ...Object.values(snapshot.strategies).map(s => s.routes)]
  if (!Object.hasOwn(snapshot, 'access')) {
    if ('access' in snapshot || Object.values(snapshot.meta).some(m => 'targetId' in m)
      || allRoutes.some(routes => Object.values(routes).some(r => [r,r.fallback,r.accelerator].some(x => x && 'origin' in x)))) throw new Error('Metadatos de origen parciales; regenera el snapshot. No se infiere una suscripción.')
    return // Historical data can be inspected; traced native export remains blocked.
  }
  ownObject(snapshot.access, ['schemaVersion', 'evidenceState', 'resourcesByPortfolio', 'inputSha256'], 'access')
  const access = snapshot.access
  if (access.schemaVersion !== 1 || access.evidenceState !== 'declared-not-runtime-verified') throw new Error('Versión o garantía de acceso no admitida.')
  if (!access.resourcesByPortfolio || typeof access.resourcesByPortfolio !== 'object' || Array.isArray(access.resourcesByPortfolio)) throw new Error('Inventarios ausentes.')
  for (const [pid, resources] of Object.entries(access.resourcesByPortfolio)) {
    if (!Object.hasOwn(snapshot.portfolios, pid) || !Array.isArray(resources)) throw new Error('Inventario sin portfolio válido.')
    const ids = new Set<string>()
    for (const resource of resources) { validateResource(resource); if (ids.has(resource.id)) throw new Error('Recurso duplicado.'); ids.add(resource.id) }
  }
  if (!access.inputSha256 || typeof access.inputSha256 !== 'object' || Array.isArray(access.inputSha256)
    || !Object.keys(access.inputSha256).length || Object.values(access.inputSha256).some(value => typeof value !== 'string' || !/^[a-f0-9]{64}$/u.test(value))) throw new Error('Recibo de origen sin hashes válidos.')
  for (const [pid, meta] of Object.entries(snapshot.meta)) {
    if (!Object.hasOwn(access.resourcesByPortfolio, meta.portfolio)) throw new Error('Falta inventario del perfil.')
    validateProfileOrigins(snapshot, meta, snapshot.routeDetails[pid], access.resourcesByPortfolio[meta.portfolio])
  }
  for (const strategy of Object.values(snapshot.strategies)) {
    const meta = { ...snapshot.meta[strategy.sourceProfile], portfolio: strategy.portfolio }
    if (!Object.hasOwn(access.resourcesByPortfolio, meta.portfolio)) throw new Error('Falta inventario de la estrategia.')
    validateProfileOrigins(snapshot, meta, strategy.routes, access.resourcesByPortfolio[meta.portfolio])
  }
}

export function referenceSelector(snapshot: Snapshot, ref: RouteReference, targetId?: string): string {
  return ref.origin && targetId ? resolveOrigin(ref, targetId).selector : snapshot.catalog[ref.modelKey].selector
}

export interface MeteredAuthorization { allowed: true; maxAmount: number; currency: string }

export function requireMeteredAuthorization(required: boolean, value?: MeteredAuthorization): void {
  if (!required) return
  if (!value || value.allowed !== true || typeof value.maxAmount !== 'number' || !Number.isFinite(value.maxAmount) || value.maxAmount <= 0
    || typeof value.currency !== 'string' || !/^[A-Z]{3}$/u.test(value.currency)) throw new Error('La API de pago requiere autorización explícita, importe positivo y moneda. No se infiere de ChatGPT.')
}
export function hasMeteredRoutes(preset: { routes: Record<string, RouteDetail> }): boolean {
  return Object.values(preset.routes).some(route => route.enabled && [route, route.fallback, route.accelerator]
    .some(ref => ref?.origin && accessRoutes[ref.origin.accessRouteId]?.billing === 'metered'))
}
