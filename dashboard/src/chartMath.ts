export interface Extent { min:number; max:number }
const readable=new Intl.NumberFormat('es-ES',{maximumSignificantDigits:4})
const scientific=new Intl.NumberFormat('es-ES',{notation:'scientific',maximumSignificantDigits:3})
/** Axis labels only. Source values, coordinates and exports are never rounded. */
export function axisNumber(value:number):string {
  return value!==0&&(Math.abs(value)<.001||Math.abs(value)>=1000000)?scientific.format(value):readable.format(value)
}
export function extent(values:(number|null|undefined)[],zero=true):Extent {
  let min=zero?0:Infinity,max=zero?0:-Infinity
  for(const v of values)if(typeof v==='number'&&Number.isFinite(v)){min=Math.min(min,v);max=Math.max(max,v)}
  return min===Infinity?{min:0,max:0}:{min,max}
}
export function ticks(domain:Extent):number[] {
  if(domain.min===domain.max)return [domain.min]
  return [0,.25,.5,.75,1].map(t=>domain.min*(1-t)+domain.max*t)
}
export function position(value:number,domain:Extent):number {
  if(domain.min===domain.max)return 50
  const scale=Math.max(Math.abs(domain.min),Math.abs(domain.max))
  return 4+92*((value/scale-domain.min/scale)/(domain.max/scale-domain.min/scale))
}
