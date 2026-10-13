import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

/** Mount expensive offscreen sections once they approach the viewport, or when
 * explicitly requested. Never pretend deferred content is an empty result. */
export default function LazyPanel({children,label}:{children:ReactNode;label:string}) {
  const ref=useRef<HTMLDivElement>(null)
  const [visible,setVisible]=useState(false)
  useEffect(()=>{
    const node=ref.current
    if(!node||visible||!('IntersectionObserver' in window))return
    const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){setVisible(true);observer.disconnect()}},{rootMargin:'150px'})
    observer.observe(node);return ()=>observer.disconnect()
  },[visible])
  return <div ref={ref} className="lazy-panel">{visible?children:<section className="panel deferred-panel"><h3>{label}</h3><p>Se carga al acercarte a esta sección, sin ralentizar los filtros.</p><button type="button" className="secondary-button" onClick={()=>setVisible(true)}>Abrir {label.toLocaleLowerCase('es')}</button></section>}</div>
}
