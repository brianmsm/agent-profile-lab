# Fragmentos de registro históricos — no instalar automáticamente

Estos archivos se preservan como evidencia de los registros originales:

- `gentle-pi-models.json`: fragmento de Pi/Gentle del corpus inicial (Pi 0.87.1).
- `omp-models.yml`: fragmento revisado con OMP 18.3.2.
- `omp-models-v18.2.11-compat.yml`: compatibilidad histórica con OMP 18.2.11.

**No representan bootstrap verificado para Pi 1.1.0 / OMP 18.8.7 ni registran
el nuevo login SIWC.** No deben reemplazar `auth.json`, credenciales o registros
activos. No se han instalado ni se actualizan durante la generación de perfiles.

Los bindings del compilador actual están en `catalog/access-routes.json`;
`contracts/harnesses.json` fija versiones y slots. La disponibilidad real de
modelos, los esfuerzos aceptados por cada cuenta, el login y el roundtrip son
comprobaciones independientes, no acreditadas por estos fragmentos.

El parser de formato Gentle usado en las pruebas está fijado y verificado bajo
`tests/vendor/gentle-shell-4.0.0/`, con la licencia original y recibo de fuentes.
