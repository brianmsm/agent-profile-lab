# Dashboard — Agent Profile Lab

React + TypeScript + Vite sobre un snapshot generado. El navegador no ejecuta
modelos, modifica credenciales ni activa perfiles en un harness.

## Ejecución

```sh
# En la raíz: reconstrucción y comprobaciones completas
python3 scripts/check_project.py --rebuild --install
# Para desarrollo del frontend
cd dashboard
bun run dev
```

## Origen por rol y exportación

Las fichas muestran modelo publicado, selector, vía, plan, recurso y referencia
abstracta de credenciales. La igualdad de dos selectores no hace equivalentes
dos cuentas o mecanismos de facturación. Los primarios y sus reservas conservan
orígenes propios; CSV y JSON exportan esos campos.

En **Compilar configuración y procedencia** se elige conservar la vía declarada,
ChatGPT legacy, ChatGPT SIWC o API de pago. El cambio sólo afecta a las rutas de
ChatGPT seleccionadas y sus reservas, no a los gateways. SIWC se rechaza para
OMP 18.8.7 mientras su soporte no esté establecido.

La API exige referencia no secreta, consentimiento explícito, importe y moneda.
**Ese importe es declarativo, no un límite de gasto aplicado al proveedor.** La
casilla de API disponible en los filtros no concede permiso para gastar.

**Preparar configuración y manifiesto** valida y liga ambos con SHA-256. Hay
una descarga para cada archivo; cambiar cualquier opción invalida el par
preparado. No se activan fallbacks, aceleradores ni autenticación automáticamente.
El manifiesto advierte de overrides, variables, credenciales guardadas y rotación.

Los snapshots históricos sin origen siguen siendo consultables, pero no admiten
exportación nativa trazada hasta regenerarse. Los que contienen origen parcial,
credenciales, referencias inválidas o supuestas garantías runtime se rechazan.

## Pruebas y límites

`bun run test` incluye contratos de importación, reservas, presupuestos,
colisiones y comparación con el compilador Python. `bun run lint` y `bun run
build` verifican el frontend; `scripts/validate_access.py` reconstruye la
proyección canónica del snapshot offline.

El snapshot continúa siendo grande y estático. Su fragmentación y la calibración
empírica figuran como desarrollo posterior; no se infiere rendimiento de una vía
porque comparta el nombre publicado de un modelo.


## Evidencia tipificada y cobertura

La vista Evidencia incluye registro de suites filtrable por función, etapas de
cobertura, fuentes y lagunas. `current` significa no sustituida en el corpus; no
es garantía de ejecución reciente. Cada resultado conserva tipo, dirección,
identidad publicada, protocolo y fechas. Las observaciones históricas no se
eliminan, pero no se mezclan por defecto con la captura vigente.

El explorador de perfiles enlaza identidades verificadas y empareja costes por
registro, protocolo y denominación. Qwen Flash-Next no se equipara automáticamente
con la oferta NaN; DeepSeek puede mostrar evidencia de su identidad publicada con
una advertencia de no calibración de endpoint. Costes provisionales y resultados
con incidencias requieren una selección explícita. La vista no produce un ranking
mezclando tiempos, tokens, errores y capacidad.

Las vistas grandes se importan con `React.lazy`; el snapshot sigue siendo único y
su fragmentación es un desarrollo posterior. La reconstrucción no consulta la red.


## Recursos, actividad y navegación estadística

Las estrategias visibles dependen del inventario: «Solo OpenAI» es realmente
OpenAI; la alternativa NaN se oculta sin NaN y se restablece si queda incompatible.
«Reparto por complejidad» aplica la política compartida con Python; el detalle y
el exportador usan la misma selección que la tarjeta resaltada. El cambio de
complejidad invalida cualquier archivo preparado previamente.

Las estadísticas generales separan estado y tipo de asignación. El explorador
muestra todos los modelos y permite un top 10/25/50/todos por modelo, desgloses y
CSV completo. La navegación desde una fila conserva el ID del perfil. Las
referencias originales no cambian ni se suman las candidatas bajo demanda a sus
recuentos. Documentación: `docs/ACTIVITY_PROFILES.md` y
`docs/PARTICIPATION_STATISTICS.md` en la raíz.


## Rendimiento y entrega diferida

El dashboard usa un núcleo de perfiles comprimido, evidencia cargada al abrir su
sección, validación en un Web Worker e índices por revisión. Las exportaciones
completas esperan todos los datos; no se exportan referencias parciales. Ejecutar
`python3 -B scripts/check_project.py --rebuild --install` desde la raíz genera
`data/delivery.json` y sus fragmentos además del snapshot portable. Detalles y
mediciones: `docs/DASHBOARD_PERFORMANCE.md` y `docs/PERFORMANCE_RECEIPT.json`.


### NaN

Al seleccionar NaN aparece el planificador de cuotas independientes. La simulación
no ejecuta llamadas ni modifica perfiles nativos. Consulta `../docs/NAN_QUOTA_BALANCING.md`.


### NaN: reparto proporcional estático

En Perfiles activa NaN y usa **NaN · reparto proporcional**. Comparación visual
de proporciones ideales y estimadas según un escenario; no consumo observado.
Consulta ../docs/NAN_STATIC_PROFILES.md.


### Híbrido proporcional NaN

Al seleccionar NaN y otras suscripciones, abre NaN · reparto proporcional.
Compara composición conservadora, auxiliares o worker delimitado acotado.
La UI indica decisiones donantes y distancia de cuotas no observadas.
Consulta ../docs/NAN_HYBRID_COMPOSITION.md.


### Editor de escenarios de carga NaN

En NaN · reparto proporcional → Personalizar frecuencias y tokens por
función puedes editar las veinte funciones, aplicar, exportar, importar
y guardar escenarios locales. Escribir una cifra no cambia
automáticamente el perfil exportable. Consulta
../docs/NAN_STATIC_PROFILES.md.
