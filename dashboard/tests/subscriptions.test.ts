import { describe, expect, test } from 'bun:test'
import { matchesSubscriptions, type PortfolioInfo } from '../src/data'

const base: PortfolioInfo = { label: 'Portfolio', usd: '0', eur: '0', openai: 'none', claude: 'none', gateway: 'none', nan: 'False' }

describe('available subscription resources', () => {
  test('available extras do not force a portfolio to use them', () => {
    const available = { openai: 'plus', claude: 'max', gateway: 'cc', nan: true } as const
    expect(matchesSubscriptions({ ...base, openai: 'plus' }, available)).toBe(true)
    expect(matchesSubscriptions({ ...base, openai: 'plus', gateway: 'cc' }, available)).toBe(true)
    expect(matchesSubscriptions({ ...base, openai: 'plus' }, available, true)).toBe(false)
  })
  test('missing resources and different plan identities cannot satisfy requirements', () => {
    const available = { openai: 'plus', claude: 'pro', gateway: 'cc', nan: false } as const
    for (const requirement of [{ ...base, openai: 'pro100' as const }, { ...base, claude: 'max' as const }, { ...base, gateway: 'go' as const }, { ...base, nan: 'True' as const }]) {
      expect(matchesSubscriptions(requirement, available)).toBe(false)
    }
    expect(matchesSubscriptions({ ...base, openai: 'plus' }, null)).toBe(true)
  })
})
