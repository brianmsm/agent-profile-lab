import {describe,test,expect} from 'bun:test'
import ledger from '../../policies/objective-equivalence-ledger.json'
describe('objective equality is documented, not falsely marketed as performance differentiation',()=>{
 test('locks every active primary overlap into one of three factual, non-ranked dispositions',()=>{
  expect(ledger.schemaVersion).toBe(1)
  expect(ledger.pairs).toHaveLength(212)
  const all=ledger.pairs.filter(pair=>pair.classification==='same-effective-configuration')
  const auxiliaries=ledger.pairs.filter(pair=>pair.classification==='distinct-auxiliary-routing')
  const conditions=ledger.pairs.filter(pair=>pair.classification==='distinct-operational-contract')
  expect([all.length,auxiliaries.length,conditions.length]).toEqual([116,88,8])
  expect(all.every(pair=>pair.sameAllRoutes&&pair.sameConditions&&pair.sameResourceOrigins)).toBe(true)
  expect(auxiliaries.every(pair=>!pair.sameAllRoutes)).toBe(true)
  expect(conditions.every(pair=>pair.sameAllRoutes&&!pair.sameConditions)).toBe(true)
 })
 test('comparison never crosses portfolios/domains/harnesses or asserts empirical superiority',()=>{
  expect(ledger.method).toContain('not a model ranking')
  for(const pair of ledger.pairs){
   expect(pair.a).not.toBe(pair.b)
   expect(pair.sameActiveMain).toBe(true)
   expect(pair.objectives[0]).not.toEqual(pair.objectives[1])
   expect(pair.portfolio.length).toBeGreaterThan(0)
   expect(pair.domain.length).toBeGreaterThan(0)
   expect(pair.harness.length).toBeGreaterThan(0)
   expect(pair.activeNativeFingerprint).toMatch(/^[a-f0-9]{64}$/)
  }
 })
})
