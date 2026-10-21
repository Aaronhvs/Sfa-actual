# Plan: 0067 — Buscar nombres completos sin cambiar display

## Implementación acotada

- [ ] Reconfirmar migración libre y baseline de rama actual; suite completa antes de nuevos tests. Preservar posiciones publicadas, ranking0066 y hotfix0055/0056.
- [ ] Inspeccionar payloads conservados por identidad y muestra del endpoint de perfiles existente; documentar campos de nombre realmente disponibles sin inferirlos desde Player.name.
- [ ] Crear migración expand `player_name_aliases`, modelo/read DTO y port de almacenamiento/proveedor; uniqueness por jugador/proveedor/alias normalizado, no por nombre global. Integrar protocolo shared vigente sin modificar journal histórico.
- [ ] Implementar parser/normalización de nombre completo y firstname+lastname efectivamente presentes; textos originales/procedencia/crosswalk verificado, nulos no inventan alias y reingesta abreviada no borra aliases previos.
- [ ] Admitir importación genérica de alias público revisado con IDs, source_kind/source_ref oficial, actor/fecha y namespace de identidad externo explícito. Perfil Espart con firstname/lastname null sigue null; entrada operativa Xavi Espart procede de ficha oficial y revisión, sin hardcode de aplicación. Regresión de reingesta abreviada/null que conserva alias revisado y homónimos que no se fusionan.
- [ ] Implementar EnrichPlayerNameAliasesUseCase y adaptador CLI/tarea reanudable por IDs/missing_aliases; repositorios sin commit y DI en core/dependencies.py. Reusar payloads antes de GET; no nuevo scheduler/endpoint de búsqueda.
- [ ] Backfill acotado de identidades actuales necesarias con presupuesto/status/headers y GET secuenciales, ventana sin ingestas propias paralelas y finally de restauración. Checkpoints/cobertura; no APIs en request de ranking.
- [ ] Centralizar predicado display OR EXISTS aliases correlacionado al player_id correcto y reutilizarlo en scope/season/all-history, lista/count/equipo. Preservar min0 al buscar, positivos y use_total/honors; filtro antes de paginar, sin multiplicar scores/ranks.
- [ ] Tokenizar case/acento/espacios/puntuación de iniciales de manera consistente; todos los tokens coinciden en un mismo alias/display, sin combinar aliases ni inferir nombres desde iniciales. Tests con orden distinto y X. Espart/Xavi/Xavier, sin ramas por identidad.
- [ ] Asegurar continuidad en ingestas que sí entreguen full_name/firstname/lastname y conservar display/nickname observado. Backfill de catálogo puntuable por caché o team+season paginado antes de perfiles individuales; primera tanda acotada y faltantes explícitos. Esperar coordinación operativa de cuota antes de cualquier GET.
- [ ] Tests parser/identidad/idempotencia y Fakes completos: display abreviado + nombre largo, acentos/case/espacios, nulos, aliases repetidos/homónimos; ninguna regla por jugador/nombre.
- [ ] Tests SQL reales de listas/count/páginas/posición para las tres rutas y 0066; múltiples aliases no duplican filas ni puntos. EXPLAIN/tiempo comparativo de búsqueda normal y sin nombre.
- [ ] Suite completa sin fallos, coverage ≥80 % código nuevo/líneas cambiadas y deuda global informada, lint e integración PostgreSQL. Sin cambios UI ni de fórmulas/datos deportivos.
- [ ] Release sobre HEAD/source real: aplicar expand, desplegar consultas compatibles y completar backfill; smoke «Xavi»/abreviatura muestra mismo nombre/puntos y encuentra identidad correcta, sin regresión de aliases de equipo. Reportar cuántos aliases faltan; no declarar resuelto antes de persistir el completo del caso real.

## Agent Routing Brief

**DDD Designer needed:** no.

DTO/read model de identidad textual y filtro de lectura existentes; no aggregate ni nueva invariante de fútbol. Usar skills sfa-use-case/repository/test según componente. Arquitectura y autorización son del incremento de búsqueda; la revisión/publicación de Espart se ejecuta por0065, sin saltar sus gates ni mezclar aliases como evidencia posicional.
