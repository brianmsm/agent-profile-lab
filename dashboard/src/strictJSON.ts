/** Reject ambiguous duplicate property names before JSON.parse.
 * JSON.parse is last-wins; other JSON consumers may interpret first-wins.
 * This checks the *raw* input including Unicode-escaped property spellings.
 * Syntactic correctness is still delegated to JSON.parse.
 */
export function parseStrictJSON(text: string): unknown {
  const stack: {kind:'object'|'array';keys:Set<string>;expectKey:boolean}[]=[]
  const readString=(start:number):{end:number;value:string}=>{
    let i=start+1
    while(i<text.length){
      if(text[i]==='\\'){i+=2;continue}
      if(text[i]==='"'){const end=i+1;return {end,value:JSON.parse(text.slice(start,end)) as string}}
      i++
    }
    throw new Error('JSON sin cerrar.')
  }
  for(let i=0;i<text.length;){
    const c=text[i]
    if(c==='"'){
      const token=readString(i)
      const frame=stack.at(-1)
      if(frame?.kind==='object'&&frame.expectKey){
        if(frame.keys.has(token.value))throw new Error('JSON contiene una clave duplicada; importación rechazada.')
        frame.keys.add(token.value)
        frame.expectKey=false
      }
      i=token.end
    }else if(c==='{'){stack.push({kind:'object',keys:new Set(),expectKey:true});i++}
    else if(c==='['){stack.push({kind:'array',keys:new Set(),expectKey:false});i++}
    else if(c==='}'||c===']'){stack.pop();i++}
    else if(c===','){
      const frame=stack.at(-1)
      if(frame?.kind==='object')frame.expectKey=true
      i++
    }else i++
  }
  return JSON.parse(text) as unknown
}
