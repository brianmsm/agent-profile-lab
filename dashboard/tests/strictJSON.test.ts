import {test,expect} from 'bun:test'
import {parseStrictJSON} from '../src/strictJSON'
test('strict parser rejects duplicate BFCL value including nested chunks',()=>{
 expect(()=>parseStrictJSON('{"benchmarks":[{"value":9.99,"value":77.47}]}')).toThrow(/duplicada/)
 expect(()=>parseStrictJSON('{"safe":{"id":"ok"},"other":{"x":1,"x":2}}')).toThrow(/duplicada/)
 expect(()=>parseStrictJSON('{"name":1,"\\u006eame":2}')).toThrow(/duplicada/)
 expect(()=>parseStrictJSON('{"value":12,"value":12}')).toThrow(/duplicada/)
})
test('strict parser retains legitimate arrays and independent same-named keys',()=>{
 expect(parseStrictJSON('{"a":{"value":1},"b":{"value":2}}')).toEqual({a:{value:1},b:{value:2}})
 expect(parseStrictJSON('{"unicode":"\\u00f1","items":[null,true,3]}')).toEqual({unicode:'ñ',items:[null,true,3]})
 expect(()=>parseStrictJSON('{"bad":')).toThrow()
})
