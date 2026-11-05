# Complementos públicos de suscripción (edición declarativa)

Esta página y su selector público son **código de autoría propia** para expresar
un inventario de recursos independiente de los perfiles científicos existentes.
No son un espejo de los catálogos, tablas de cuotas o resultados de terceros
almacenados en la edición privada.

## Alcance aprobado para revisión técnica

- OpenCode Go y Go Plus, NaN Gentle y Google AI Plus/Pro/Ultra se pueden marcar
  y exportar como un JSON **declarativo**, sin credenciales, consumo o ejecución.
- Se conservan sin alteraciones las referencias nativas, las decisiones de rol,
  los 2.496 perfiles, las 33.414 asignaciones y el subconjunto público ya revisado.
- Los precios de Go y NaN se muestran como **referencias fechadas** y en monedas
  separadas. Los límites, entitlements y precios actuales deben consultarse en
  las fuentes oficiales. No se incluye tabla de precios por modelo.
- Este selector **no** genera un manifiesto nativo Pi/OMP, habilita modelos de Go,
  comprueba cuota efectiva, conecta Google Antigravity a OMP/Pi, ni atribuye
  API de Gemini a una suscripción Google AI. No activa pagos adicionales.
- Los 21 valores de benchmarks candidatos de Go, las capturas HTML/JSON,
  scores de Artificial Analysis/Vals y sus derivados numéricos **no se empaquetan**
  en esta edición. Enlaces a los proveedores sustituyen los valores.

Fuentes para consulta, sin copiar sus tablas:
[OpenCode Go](https://dev.opencode.ai/v2/docs/console/go),
[NaN Gentle](https://cloud.nan.builders/gentle?lang=en),
[Google Antigravity](https://antigravity.google/docs/plans).

## Fronteras y siguiente puerta

El inventario descargado es `agent-profile-lab.public-supplement-inventory`,
no un `compiled-profile`. La diferencia es intencionada: no se puede
considerar funcionalmente equivalente a la integración privada de suscripciones.
La paridad real exigiría una revisión específica de dependencias, autorizaciones,
transporte de herramientas, cuotas y exportación nativa.

El código debe pasar pruebas de interfaz, esquema, DLP, compilación y
`audit_built_site` sobre los assets compilados; pasar esas pruebas **no**
equivale a una revisión humana de derechos ni autoriza push o despliegue.
El procedimiento final es `republication/SAFE_SYNC.md` del privado.
