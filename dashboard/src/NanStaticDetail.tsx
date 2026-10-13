import type {NanStaticPlan} from './nanStaticProfiles'
import {nanKeys} from './nanQuotaBalance'
import {nanCompositionPolicy} from './nanStaticProfiles'
const percentage=new Intl.NumberFormat('es-ES',{style:'percent',maximumFractionDigits:1})
const millions=new Intl.NumberFormat('es-ES',{maximumFractionDigits:2})
const labels:Record<string,string>={nan_qwen:'Qwen 3.8 Flash',nan_ds:'DeepSeek V4-Flash',nan_mf:'MiMo V2.6 Flash',nan_glm:'GLM 5.3 Flash'}
export default function NanStaticDetail({plan}:{plan:NanStaticPlan}){
  const rows=nanKeys.map(k=>plan.byModel[k])
  return <section className="trace-note nan-static-detail" aria-label="Proyección de reparto proporcional estático">
    <h3>Distribución prevista del trabajo de NaN</h3>
    <p>Partimos de las <strong>cuatro cuotas completas</strong>, con un selector fijo por rol. Se comparan <strong>proporciones de tokens esperados</strong>, no número de roles ni consumo real.</p>
    {plan.customWorkload&&<p className="nan-workload-provenance"><strong>Carga personalizada aplicada:</strong> {plan.customWorkload.label} · base {plan.customWorkload.baseScenario} · referencia <code>{plan.customWorkload.fingerprint}</code>. Los 20 supuestos editados viajan en el manifiesto y JSON analítico; no proceden de observaciones reales.</p>}
    <div className="nan-static-summary">
      <div><span>Escenario</span><strong>{plan.scenarioLabel}</strong></div>
      <div><span>Desviación total del ideal</span><strong>{percentage.format(plan.distanceFromQuotaTarget)}</strong></div>
      <div><span>Tokens NaN esperados / mes</span><strong>{millions.format(plan.expectedTokensOnNaN/1e6)} M</strong></div>
      <div><span>Porcentaje estimado de trabajo entre todos los proveedores</span><strong>{percentage.format(plan.expectedShareNaNOfAllRoles)}</strong></div>
    </div>
    <div className="nan-quality-summary" role="group" aria-label="Restricciones de calidad y sensibilidad">
      <div><strong>Exposición experimental prevista</strong><span>{percentage.format(plan.qualityGuard.trialFractionOfExpectedNaN)} de tokens NaN previstos · límite {percentage.format(plan.qualityGuard.trialShareCap)}</span><small>Es una restricción de incertidumbre, no una puntuación de calidad.</small></div>
      <div><strong>Sensibilidad de los supuestos</strong><span>{percentage.format(plan.sensitivity.minimumCornerDistance)} – {percentage.format(plan.sensitivity.maximumCornerDistance)}</span><small>16 escenarios extremos con multiplicadores de {plan.sensitivity.lowerFactor}× a {plan.sensitivity.upperFactor}× por modelo. No son intervalos de confianza.</small></div>
    </div>
    {plan.composition&&<div className="nan-hybrid-composition"><h4>Perfil híbrido y procedencia funcional</h4>
      <p>Composición: <strong>{nanCompositionPolicy.compositionModes[plan.composition.mode].label}</strong>. Coordinador conservado desde <code>{plan.composition.sourceCoordinatorProfile}</code>. La política funcional previa cambia {plan.composition.activityPlan.changes.length} roles; la composición añade {plan.composition.helperOffloads.length} delegaciones explícitas a NaN.</p>
      <p>Los porcentajes de las barras describen el trabajo esperado <strong>dentro de NaN</strong>, no el reparto entre todas tus suscripciones. Las fuentes OpenAI, Claude y OpenCode Go permanecen visibles en el detalle superior.</p>
      {plan.composition.helperOffloads.length>0&&<div className="table-wrap" role="region" tabIndex={0} aria-label="Funciones añadidas al componente NaN"><table><thead><tr><th>Rol auxiliar</th><th>Fuente anterior → NaN</th><th>Donante verificable</th></tr></thead><tbody>{plan.composition.helperOffloads.map(c=><tr key={c.role}><th scope="row">{c.role}<small>{c.functionId}</small></th><td>{c.fromModelKey} → {c.toModelKey}</td><td><code>{c.sourceProfile}</code></td></tr>)}</tbody></table></div>}
    </div>}
    <p className="footnote">Esta desviación representa la distancia entre cuotas proporcionales y la asignación estimada; <strong>no es un error medido</strong>. Un 0 % no significa que el modelo sea inútil: quizá ningún rol apto tiene el tamaño necesario.</p>
    <div className="nan-static-rows">
      {rows.map(row=><div className="nan-static-model" key={row.offeringKey}>
        <div className="nan-static-model-top"><strong>{labels[row.offeringKey]}</strong><span>Objetivo {percentage.format(row.targetQuotaShare)} · estimación {percentage.format(row.expectedTokenShare)}</span></div>
        <div className="nan-static-dualbar" role="img" aria-label={`${labels[row.offeringKey]} cuota proporcional ideal ${percentage.format(row.targetQuotaShare)}, carga del perfil estimada ${percentage.format(row.expectedTokenShare)}`}>
          <div className="nan-static-bar-target" style={{width:`${100*row.targetQuotaShare}%`}}/>
          <div className="nan-static-bar-estimate" style={{width:`${100*row.expectedTokenShare}%`}}/>
        </div>
        <small>{millions.format(row.expectedTokens/1e6)} M tokens mensuales hipotéticos · {row.trialOnly?'Candidato experimental, uso no calibrado':'Admisión limitada por función'}</small>
      </div>)}
    </div>
    <p className="nan-static-legend"><span><i className="target"/> Ideal según cuota</span><span><i className="estimated"/> Perfil estático proyectado</span></p>
    <p><strong>{plan.changes.length} roles cambiados</strong> frente a la referencia. Coordinación y revisión protegidas; se preserva el principal anterior como reserva declarativa.</p>
    <div className="table-wrap" tabIndex={0} role="region" aria-label="Asignaciones proporcionales"><table><thead><tr><th>Rol</th><th>Antes → nuevo</th><th>Tokens supuestos/mes</th></tr></thead><tbody>{plan.changes.map(c=><tr key={c.role}><th scope="row">{c.role}<small>{c.functionId}</small></th><td>{c.fromModelKey} → <strong>{labels[c.toModelKey]||c.toModelKey}</strong>{c.admission==='trial'&&<small>Experimental: piloto obligatorio</small>}</td><td>{millions.format(c.expectedMonthlyTokens/1e6)} M</td></tr>)}</tbody></table></div>
    <details><summary>Supuestos de carga por función y frecuencia</summary><p>{plan.scenarioAssumptions.description}</p><div className="table-wrap" tabIndex={0}><table><thead><tr><th>Rol / función</th><th>Llamadas supuestas al mes</th><th>Tokens totales por llamada</th><th>Tokens por mes</th></tr></thead><tbody>{plan.byRole.map(row=><tr key={row.role}><th scope="row">{row.role}<small>{row.functionId}</small></th><td>{row.assumedCalls}</td><td>{row.assumedTotalTokensPerCall.toLocaleString('es-ES')}</td><td>{row.estimatedMonthlyTokens.toLocaleString('es-ES')}</td></tr>)}</tbody></table></div></details>
    <p className="footnote">No son registros reales ni calibraciones; el uso de reservas y la frecuencia real de roles pueden alterar el reparto. El archivo nativo asigna modelos por rol pero no impone un reparto dinámico, límites de cuota ni las condiciones de revisión. <strong>No necesita hooks de Gentle/OMP</strong>.</p>
    {plan.includeTrials&&<p className="nan-balance-warning">Qwen y MiMo sólo han entrado porque activaste expresamente los candidatos experimentales. Hay que probar sus respuestas y herramientas antes de adoptar este perfil para trabajo habitual.</p>}
  </section>
}
