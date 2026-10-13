import { describe, expect, test } from 'bun:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import Profiles from '../src/Profiles'
import { DEFAULT_FILTERS, type ProfileFilters, type RouteDetail, type Snapshot } from '../src/data'

const primary: RouteDetail = { modelKey: 'openai', effort: 'high', fallback: null, accelerator: null, enabled: true, condition: '', rationale: '' }
const auxiliary: RouteDetail = { modelKey: 'nan', effort: '', fallback: { modelKey: 'openai', effort: 'high' }, accelerator: null, enabled: true, condition: 'Bounded test task with supplied sources and an explicit verification oracle.', rationale: 'Test candidate, not measured performance.' }
const snapshot: Snapshot = {
  stats: { rows: 4, profiles: 2, portfolios: 2, models: 2, groups: 1, validators: { passed: 1, failed: 0 }, session: 'empty-result-regression' },
  portfolios: {
    plus: { label: 'Test Plus', usd: '0', eur: '0', openai: 'plus', claude: 'none', gateway: 'none', nan: 'False' },
    'plus-nan': { label: 'Test Plus + NaN', usd: '0', eur: '0', openai: 'plus', claude: 'none', gateway: 'none', nan: 'True' },
  },
  catalog: {
    openai: { name: 'Test OpenAI model', pool: 'OAI', selector: 'openai/test-model', efforts: ['high'], vision: null, evidence: '', integration: '' },
    nan: { name: 'Test NaN model', pool: 'NAN', selector: 'nan/test-model', efforts: [], vision: null, evidence: '', integration: '' },
  },
  coverage: {},
  domainContracts: {
    apps: { label: 'Desarrollo de software', scope: 'Test software scope', gate: 'Test oracle', critical: 'Critical test decisions', routine: 'Bounded test tasks' },
    'agent-use': { label: 'Uso de agentes', scope: 'Test agent scope', gate: 'Closed delegation gate', critical: 'Agent decisions', routine: 'Bounded test tasks' },
  },
  meta: {
    software: { portfolio: 'plus', harness: 'omp', domain: 'apps', objective: 'balanced' },
    agents: { portfolio: 'plus', harness: 'omp', domain: 'agent-use', objective: 'balanced' },
  },
  routing: { software: { default: ['Test OpenAI model', 'high'], smol: ['Test OpenAI model', 'high'] }, agents: { default: ['Test OpenAI model', 'high'], smol: ['Test OpenAI model', 'high'] } },
  routeDetails: { software: { default: primary, smol: primary }, agents: { default: primary, smol: primary } },
  runtimePolicies: { software: { advisorEnabled: false, taskMaxConcurrency: 1 }, agents: { advisorEnabled: false, taskMaxConcurrency: 1 } },
  strategies: { 'software::nan-volume': { kind: 'nan-volume', sourceProfile: 'software', portfolio: 'plus-nan', routes: { default: primary, smol: auxiliary }, coordinatorPool: 'OAI', offloadPool: 'NAN', limitations: ['Test bounded task requirements.'] } },
}

describe('preset recovery and empty-result surface', () => {
  for (const partial of [
    { strategy: 'nan-volume', subscriptions: { openai: 'plus', claude: 'none', gateway: 'none', nan: false } },
    { domain: 'agent-use', strategy: 'nan-volume' },
  ] as Partial<ProfileFilters>[]) {
    test(`invalid NaN strategy resets to compatible references: ${JSON.stringify(partial)}`,()=>{
      const markup=renderToStaticMarkup(createElement(Profiles,{snapshot,filters:{...DEFAULT_FILTERS,...partial},onFilters:()=>{}}))
      expect(markup).not.toContain('data-strategy="nan-volume"')
      expect(markup).toContain('Perfil de referencia')
      expect(markup).toContain('id="profile-detail"')
      expect(markup).not.toContain('nan/test-model')
      const selected=markup.match(/class="profile-row selected"[^>]*data-preset-id="([^"]+)"/)
      const detail=markup.match(/id="profile-detail"[^>]*data-preset-id="([^"]+)"/)
      expect(selected?.[1]).toBe(detail?.[1])
    })
  }
  test('unmatched selector search explains recovery without stale detail or exports',()=>{
    const markup=renderToStaticMarkup(createElement(Profiles,{snapshot,filters:{...DEFAULT_FILTERS,search:'selector-not-in-this-snapshot'},onFilters:()=>{}}))
    expect(markup).toContain('No hay configuraciones en este alcance.')
    expect(markup).toContain('Ninguna configuración satisface estos filtros')
    expect(markup).toContain('Quitar búsqueda')
    expect(markup).toContain('Limpiar filtros')
    expect(markup).not.toContain('id="profile-detail"')
    expect(markup).not.toContain('aria-label="Exportar la configuración seleccionada"')
    expect(markup).not.toContain('data-testid="model-insights"')
  })
})
