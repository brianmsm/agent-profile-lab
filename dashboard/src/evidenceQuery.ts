import type {Benchmark} from './data'
export function createEvidenceSearch(records:Benchmark[]) {
  const cache=new WeakMap<Benchmark,string>()
  const members=new Set(records)
  return (row:Benchmark,needle:string)=>{
    if(!needle)return true
    if(!members.has(row))throw new Error('La búsqueda pertenece a otra revisión de los datos.')
    let text=cache.get(row)
    if(text===undefined){text=[row.model,row.benchmark,row.source,row.sourceId,row.effort,row.provenance,row.methodology,row.note].join(' ').toLocaleLowerCase('es');cache.set(row,text)}
    return text.includes(needle)
  }
}
