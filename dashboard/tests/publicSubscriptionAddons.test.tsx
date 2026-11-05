import {describe,expect,test} from 'bun:test'
import {renderToStaticMarkup} from 'react-dom/server'
import React from 'react'
import {readFileSync} from 'node:fs'
import PublicSubscriptionAddons from '../src/PublicSubscriptionAddons'
import {NO_PUBLIC_SUPPLEMENTS, publicSupplementDeclaration, PUBLIC_PLAN_OPTIONS} from '../src/publicSupplementPlan'

describe('Public supplementary subscriptions and publication boundary',()=>{
  test('individual tiers are explicit and do not grant API or native access',()=>{
    expect(PUBLIC_PLAN_OPTIONS.go).toEqual(['none','go10','plus40'])
    expect(PUBLIC_PLAN_OPTIONS.nan).toEqual(['none','gentle20'])
    expect(PUBLIC_PLAN_OPTIONS.google).toEqual(['none','plus','pro','ultra5x','ultra20x'])
    for(const go of PUBLIC_PLAN_OPTIONS.go)for(const nan of PUBLIC_PLAN_OPTIONS.nan)
      for(const google of PUBLIC_PLAN_OPTIONS.google){
        const result=publicSupplementDeclaration({go,nan,google})
        expect(result.piOmpRoleAssignmentsChanged).toBe(0)
        expect(result.nativeConfigExported).toBe(false)
        expect(result.extraPaidUsageAuthorized).toBe(false)
        expect(result.subscriptionGrantsGeminiAPI).toBe(false)
        expect(result.benchmarkScoresRedistributed).toBe(0)
        expect(result.status).toBe('user-declared-not-runtime-verified')
      }
  })
  test('preserves separate currencies and regional caveats',()=>{
    const result=publicSupplementDeclaration({go:'plus40',nan:'gentle20',google:'pro'})
    expect(result.pricingReference.goUSDMonthly).toBe(40)
    expect(result.pricingReference.nanEURMonthly).toBe(20)
    expect(result.pricingReference.google).toContain('región')
    expect(result.selections).toEqual({go:'plus40',nan:'gentle20',google:'pro'})
  })
  test('rejects unknown fields, unsupported options, credentials and usage grants',()=>{
    for(const data of [
      null,{go:'go10',nan:'none',google:'pro',apiKey:'hidden'},
      {go:'free-experimental',nan:'none',google:'pro'},
      {go:'none',nan:'inference70',google:'pro'},
      {go:'none',nan:'none',google:'gemini-api'},
      {},{...NO_PUBLIC_SUPPLEMENTS,extraUsageAuthorized:true},
    ])expect(()=>publicSupplementDeclaration(data)).toThrow()
  })
  test('new public modules do not import research data or vendor catalogs',()=>{
    const code=['PublicSubscriptionAddons.tsx','publicSupplementPlan.ts']
      .map(name=>readFileSync(new URL('../src/'+name,import.meta.url),'utf8')).join('\n')
    expect(code).not.toMatch(/(?:from|import)\s*['"]\.\.\/\.\.\/(?:evidence|catalog|policies|data)\//)
    expect(code).not.toContain('benchmark_screening.json')
  })
  test('renders the isolated selector, official links and non-native disclaimer',()=>{
    const html=renderToStaticMarkup(React.createElement(PublicSubscriptionAddons))
    expect(html).toContain('Complemento OpenCode Go')
    expect(html).toContain('Google AI Ultra 20')
    expect(html).toContain('No altera los filtros de perfiles')
    expect(html).toContain('https://dev.opencode.ai/v2/docs/console/go')
    expect(html).not.toContain('benchmark_screening')
    expect(html).not.toContain('AA v5:')
  })
})
