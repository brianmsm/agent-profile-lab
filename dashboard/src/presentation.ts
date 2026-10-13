import type { PortfolioInfo } from './data'
export const POOL_LABELS:Record<string,string>={OAI:'ChatGPT / OpenAI',ANTHROPIC:'Claude',GO:'OpenCode Go',CC:'Command Code',NAN:'NaN',API:'OpenAI API',ANTHROPIC_API:'Claude API'}
export function poolLabel(pool:string){return pool.split('+').map(p=>POOL_LABELS[p]||p).join(' + ')}
export const STRATEGIES={matrix:'Perfil de referencia','openai-led':'Solo OpenAI','nan-volume':'OpenAI + auxiliares NaN','activity-distributed':'Reparto por complejidad','reviewed-candidate':'Alternativas por evidencia','nan-static':'NaN · reparto proporcional','nan-hybrid':'NaN · híbrido proporcional'} as const
export const STRATEGY_DESCRIPTIONS={
  'nan-hybrid':'Combina el reparto funcional por complejidad con la distribución interna de NaN. La composición auxiliares/worker es explícita y conserva coordinación y revisión.',
  'nan-static':'Construye perfiles fijos de NaN para tres escenarios hipotéticos de carga. Busca aproximar las cuotas 3B/2B/1B/500M sin contar roles como tokens; Qwen y MiMo requieren permiso experimental. No usa tu consumo actual ni es routing dinámico.',
  'reviewed-candidate':'Recetas revisadas por función, con evidencia y contrapuntos explícitos. Incluye modelos que antes no figuraban como donantes. Se abre por separado; no reemplaza las referencias ni promete una cuota óptima.',
  matrix:'Configuración previamente documentada para esos recursos, dominio y objetivo. No se vuelve a optimizar al marcar una suscripción; puede dejar recursos sin asignar.',
  'openai-led':'Todos los modelos principales proceden de ChatGPT / OpenAI. Los demás recursos seleccionados permanecen disponibles, sin participación obligatoria.',
  'nan-volume':'Mantiene la base de OpenAI y mueve sólo los auxiliares admitidos a NaN. No es un reparto de tokens ni un coordinador multi-proveedor.',
  'activity-distributed':'Construye una candidata con tus recursos: coordinación y revisión protegidas; ejecución y auxiliares se reparten por función y complejidad. Muestra los cambios y sus referencias, sin prometer ahorro.'
} as const
export function portfolioLabel(p:PortfolioInfo){return p.label.replace(/\b(?:OpenCode\s+)?Go\b/gu,'OpenCode Go').replace(/\bCommand\b(?! Code)/gu,'Command Code')}
export const DOMAIN_HELP:Record<string,string>={
  apps:'Software nativo, herramientas de terminal y aplicaciones multiplataforma; una interfaz no convierte una tarea en desarrollo web.',
  web:'Frontend, backend e integración web; incluye cambios comprobables en navegadores y servicios.',
  data:'Limpieza, transformación, análisis y modelos estadísticos. La complejidad describe el trabajo; el impacto se declara por separado.',
  research:'Búsqueda y síntesis de fuentes, contraste de afirmaciones e investigación. Extraer información no equivale a validar una conclusión científica.',
  'agent-use':'Uso de herramientas y servicios por agentes. Las candidatas de reparto automático están restringidas para este dominio.',
  cybersecurity:'Evaluación de seguridad con autorización y alcance explícitos. No se redistribuyen automáticamente funciones con esta política.'
}
