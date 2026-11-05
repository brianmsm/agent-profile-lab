/** Author-owned public-only supplement selector.
 * Deliberately imports no private catalogs, provider captures or benchmark values.
 * This is not the Pi/OMP compiler and cannot authorize billing or routing.
 */

export const PUBLIC_PLAN_OPTIONS = {
  go: ['none','go10','plus40'],
  nan: ['none','gentle20'],
  google: ['none','plus','pro','ultra5x','ultra20x'],
} as const

export type PublicSupplementSelection = {
  go: (typeof PUBLIC_PLAN_OPTIONS.go)[number]
  nan: (typeof PUBLIC_PLAN_OPTIONS.nan)[number]
  google: (typeof PUBLIC_PLAN_OPTIONS.google)[number]
}
export const NO_PUBLIC_SUPPLEMENTS:PublicSupplementSelection = {
  go:'none', nan:'none', google:'none',
}

export const SOURCE_LINKS = {
  go:'https://dev.opencode.ai/v2/docs/console/go',
  nan:'https://cloud.nan.builders/gentle?lang=en',
  google:'https://antigravity.google/docs/plans',
} as const

function selected<T extends readonly string[]>(value:unknown, options:T):value is T[number] {
  return typeof value==='string' && options.some(option=>option===value)
}

/** For an independently reviewed, author-originated inventory only.
 * Reject unknown fields, including accidental credential material or extra billing.
 */
export function publicSupplementDeclaration(raw:unknown) {
  if(!raw||typeof raw!=='object'||Array.isArray(raw))throw new Error('Inventario inválido.')
  const data=raw as Record<string,unknown>
  if(Object.keys(data).sort().join('|')!=='go|google|nan'
    ||!selected(data.go,PUBLIC_PLAN_OPTIONS.go)
    ||!selected(data.nan,PUBLIC_PLAN_OPTIONS.nan)
    ||!selected(data.google,PUBLIC_PLAN_OPTIONS.google))
    throw new Error('Solo se permiten los planes públicos declarativos.')
  return {
    format:'agent-profile-lab.public-supplement-inventory',
    schemaVersion:1,
    referenceDate:'2026-11-05',
    status:'user-declared-not-runtime-verified',
    kind:'advisory-addons-only',
    selections:{go:data.go,nan:data.nan,google:data.google},
    sources:SOURCE_LINKS,
    pricingReference:{
      goUSDMonthly:data.go==='go10'?10:data.go==='plus40'?40:null,
      nanEURMonthly:data.nan==='gentle20'?20:null,
      google: 'Consultar precio y condiciones vigentes de la región',
    },
    piOmpRoleAssignmentsChanged:0,
    nativeConfigExported:false,
    currentAccountAccessVerified:false,
    subscriptionGrantsGeminiAPI:false,
    extraPaidUsageAuthorized:false,
    benchmarkScoresRedistributed:0,
    warnings:[
      'Inventario independiente; no se aplica al archivo nativo ni al ranking.',
      'No verifica credenciales, límites reales, compatibilidad de harness ni cuotas.',
      'Los precios son referencias históricas por moneda; consulta las fuentes antes de contratar.',
    ],
  }
}
