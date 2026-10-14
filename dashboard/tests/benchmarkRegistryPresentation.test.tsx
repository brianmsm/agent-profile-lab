import { describe, expect, test } from 'bun:test'
import { readFileSync } from 'node:fs'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import BenchmarkRegistry from '../src/BenchmarkRegistry'
import { isRightsScopedEvidenceEdition, suiteEvidencePresentation, suiteHasVerifiableGap } from '../src/registryEdition'
import type { Snapshot } from '../src/data'
import type { BenchmarkSuite } from '../src/benchmarkTypes'

function suite(): BenchmarkSuite {
  return {
    id: 'external-example', label: 'Example publisher family', domains: ['research'],
    functions: ['source-research'], policyFunctionIds: ['source-research'],
    priority: 'context', limitations: ['No cross-harness calibration.'],
    updateMode: 'manual', decisionUse: 'Do not rank by this family.',
    captureIds: [], legacyPattern: '', captures: [],
    coverage: { observations: 0, current: 0, linked: 0, comparable: 0, decisionEligible: 0 },
    lifecycle: { discovered: true, captured: false, normalized: false, linked: false,
      comparable: false, screeningUsable: false, routeCalibrated: false },
  }
}

function snapshot(row: BenchmarkSuite, restricted: boolean): Snapshot {
  return {
    sourceCoverage: { scope: restricted ? 'Public rights-scoped observations plus links to registered sources.'
      : 'Full private research corpus', generatedAt: '2026-10-13T00:00:00Z',
      totals: { sources: 1, artifacts: 0, benchmarks: row.coverage.observations, excluded: 0 },
      sources: [], artifacts: [], notes: [] },
    benchmarkRegistry: {
      schemaVersion: 1, updateMode: 'manual', suites: { [row.id]: row },
      metrics: {}, protocols: {}, issues: {}, revisions: [], inputSha256: {}, limitations: [],
      modelLinks: {}, stats: {
        observations: row.coverage.observations, currentObservations: row.coverage.current,
        metricKinds: {}, scopeCounts: {}, modelLinks: {}, bySource: {}, suites: 1,
        metrics: 0, protocols: 0, revisions: 0, independentTrials: 'not-estimated', routeCalibrations: 0,
      },
    },
  } as unknown as Snapshot
}

describe('benchmarks: edition boundary is not a research extraction gap', () => {
  test('public zero means no redistributed rows, never no research or score zero', () => {
    const row=suite(), edition=snapshot(row,true)
    expect(isRightsScopedEvidenceEdition(edition)).toBe(true)
    expect(suiteHasVerifiableGap(row,true)).toBe(false)
    expect(suiteHasVerifiableGap(row,false)).toBe(true)
    expect(suiteEvidencePresentation(row,true).detailLabel).toBe('Alcance público y fuentes')
    const html=renderToStaticMarkup(createElement(BenchmarkRegistry,{snapshot:edition}))
    expect(html).toContain('Sin cifras redistribuidas')
    expect(html).toContain('0 observaciones redistribuidas')
    expect(html).toContain('Sólo lagunas verificables con cifras públicas')
    expect(html).toContain('no permite deducir qué se capturó o normalizó')
    expect(html).not.toContain('Sólo identificado')
    expect(html).not.toContain('Laguna documentada; no equivale a cero')
  })

  test('private capture remains a documented capture, not a public exclusion', () => {
    const row=suite()
    row.lifecycle.captured=true
    row.lifecycle.normalized=true
    row.lifecycle.linked=true
    row.lifecycle.comparable=true
    row.coverage={ observations: 1, current: 1, linked: 1, comparable: 1, decisionEligible: 0 }
    expect(suiteHasVerifiableGap(row,false)).toBe(false)
    expect(suiteEvidencePresentation(row,false).status).toBe('Fuente capturada')
    const html=renderToStaticMarkup(createElement(BenchmarkRegistry,{snapshot:snapshot(row,false)}))
    expect(html).toContain('Fuente capturada')
    expect(html).toContain('1 observación incorporada')
    expect(html).not.toContain('Sin cifras redistribuidas')
  })

  test('public numeric rows retain verifiable model/protocol gaps', () => {
    const row=suite()
    row.coverage={observations:1,current:1,linked:0,comparable:0,decisionEligible:0}
    row.lifecycle.normalized=true
    expect(suiteHasVerifiableGap(row,true)).toBe(true)
    const html=renderToStaticMarkup(createElement(BenchmarkRegistry,{snapshot:snapshot(row,true)}))
    expect(html).toContain('Resultados redistribuidos · capturas no incluidas')
    expect(html).toContain('Alcance de extracción y precauciones')
  })

  test('API consent checkbox cannot inherit full-width input style', () => {
    const css=readFileSync(new URL('../src/index.css', import.meta.url),'utf8')
    expect(css).toMatch(/\.access-consent input\[type=checkbox\]\s*\{[^}]*width:\s*18px;[^}]*height:\s*18px;[^}]*min-height:\s*18px;/su)
  })

  test('desktop selects use an in-page picker on supported browsers without changing native fallback', () => {
    const css=readFileSync(new URL('../src/index.css', import.meta.url),'utf8')
    expect(css).toContain('@media (hover: hover) and (pointer: fine)')
    expect(css).toContain('@supports (appearance: base-select)')
    expect(css).toMatch(/select:not\(\[multiple\]\):not\(\[size\]\)::picker\(select\)\s*\{[^}]*appearance:\s*base-select;/su)
    expect(css).toMatch(/select:not\(\[multiple\]\):not\(\[size\]\) option:hover,[\s\S]*?option:checked\s*\{[^}]*background:\s*var\(--teal-soft\);/u)
    expect(css).toContain('max-height: min(56vh, 420px)')
  })
})
