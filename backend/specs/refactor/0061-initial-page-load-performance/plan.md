# Plan: Initial Page Load Performance

## Dependencias

- [ ] Terminar todos los items del spec `0060-ranking-read-performance-and-refresh`.
- [ ] Integrar y desplegar `0060` sin mezclar commits de este spec.
- [ ] Confirmar en produccion la equivalencia funcional y las medianas documentadas por `0060`.

## Archivos previstos

### A modificar en implementacion futura

- [ ] `frontend/src/pages/RankingPage.tsx` - bootstrap paralelo y reconciliacion de scope sin refetch.
- [ ] `frontend/src/api/client.ts` - deduplicacion de requests en vuelo y politica de cache compatible con abort.
- [ ] `frontend/src/components/shared/WcLiveChip.tsx` - convertir el componente en una vista de una unica fuente montada.
- [ ] `frontend/src/index.css` - reubicar visualmente la unica instancia del chip sin alterar geometria.
- [ ] `frontend/index.html` - hints y prioridades de recursos solo si el trace demuestra beneficio.
- [ ] `frontend/vercel.json` - cache explicita para HTML y assets con hash, segun hosting real.
- [ ] `backend/src/sfa/api/v1/ranking.py` - headers de cache publica del read endpoint si no se resuelven en proxy.
- [ ] `backend/src/sfa/api/v1/seasons.py` - headers de cache de metadata.
- [ ] `backend/src/sfa/api/v1/competitions.py` - headers de cache de metadata.
- [ ] `backend/src/sfa/api/v1/ranking_explanations.py` - headers de cache del carrusel.
- [ ] `backend/tests/api/test_ranking.py` - contrato de cache y ausencia de cambios de payload.
- [ ] `backend/tests/api/test_seasons.py` - contrato de cache de metadata.

### A crear solo si el framework de tests frontend lo permite sin dependencia nueva

- [ ] Prueba de lifecycle de `RankingPage` para URL sin scope, scope explicito y carrera seasons/ranking.
- [ ] Prueba del cliente para cache hit, promesa en vuelo, error, expiracion y consumidores abortados.

## Fase 0 - Baseline reproducible

- [ ] Documentar commit frontend, commit backend, fecha, region del cliente y estado de caches.
- [ ] Medir cinco cargas frias y cinco calientes de `/ranking` en desktop y Fast 4G movil.
- [ ] Guardar trace, waterfall y screenshot del primer contenido util.
- [ ] Registrar TTFB y total de `/seasons`, `/competitions`, `/ranking`, `/ranking/explanations`,
  `/wc/live` y `/wc/fixtures` cuando aplique.
- [ ] Registrar FCP, LCP, CLS, TBT/INP de laboratorio, requests y bytes transferidos.
- [ ] Ejecutar `npm run build` y conservar tabla de chunks raw/gzip.
- [ ] Medir las dimensiones y bytes de todos los assets del primer viewport.
- [ ] Confirmar si Google Fonts bloquea render y cuantos archivos WOFF2 descarga realmente para latin.
- [ ] Capturar `EXPLAIN (ANALYZE, BUFFERS)` de `SeasonRepository._get_scopes()`.
- [ ] Confirmar mediante logs SQL el numero y orden de queries de una request de ranking.

## Fase 1 - Retirar el waterfall de scope

- [ ] Definir estado separado para scope solicitado, scope canonico y lista de temporadas.
- [ ] Si existe `scope` en la URL, solicitar ese valor sin cambiar conducta actual.
- [ ] Si no existe `scope`, lanzar `fetchRanking` inmediatamente sin el parametro.
- [ ] Lanzar `fetchSeasons` y `fetchCompetitions` en paralelo con el ranking.
- [ ] Al recibir ranking, usar `response.scope` como scope canonico.
- [ ] Sincronizar selector y URL con `replace: true` sin invalidar la respuesta equivalente.
- [ ] Impedir una segunda llamada producida solo por canonizar la URL.
- [ ] Conservar `AbortController`, request id, carga inicial y refresh estable definidos en `0060`.
- [ ] Mantener skeletons actuales y reservar el mismo espacio del podio/lista.
- [ ] Verificar error independiente: si `/seasons` falla pero `/ranking` responde, mostrar ranking.
- [ ] Verificar error independiente: si `/ranking` falla, metadata no debe ocultar el error util.

## Fase 2 - Deduplicacion y requests auxiliares

- [ ] Agregar un mapa privado de promesas en vuelo en `frontend/src/api/client.ts`.
- [ ] Usar como clave URL completa, incluido query string canonico.
- [ ] Eliminar la promesa del mapa al resolver o rechazar.
- [ ] No almacenar errores en cache TTL.
- [ ] Definir semantica de abort para que un consumidor no cancele la request compartida de otros.
- [ ] Mantener el cache de datos de 60 s como capa separada de la deduplicacion.
- [ ] Montar una sola instancia de `WcLiveChip` en `RankingPage`.
- [ ] Reproducir sus dos ubicaciones responsive con contenedor/CSS, no con dos efectos React.
- [ ] Confirmar una sola request y un solo intervalo de polling en modo Mundial.
- [ ] Confirmar que el ranking normal no hace una segunda llamada a fixtures cuando `/wc/live`
  entrega un resultado suficiente o cuando el producto decide no mostrar ese contexto.

## Fase 3 - Cache HTTP de bajo riesgo

- [ ] Confirmar donde termina cada request en produccion: Vercel, Traefik o ambos.
- [ ] Configurar assets Vite con hash como `public, max-age=31536000, immutable`.
- [ ] Configurar `index.html` con revalidacion y sin cache immutable.
- [ ] Agregar `Cache-Control` corto a seasons, competitions, ranking y explicaciones segun decisions.
- [ ] Mantener `/wc/live` con TTL maximo de 10 s o `no-store` si el polling exige frescura exacta.
- [ ] Verificar `Vary` para cualquier respuesta afectada por origen o compresion.
- [ ] Verificar que query strings distintas de ranking no colisionan.
- [ ] Verificar que una recarga dentro del TTL evita transferencia completa.
- [ ] Verificar que, al vencer TTL, el navegador revalida y obtiene los puntos actuales.

## Fase 4 - Recursos bloqueantes

- [ ] Convertir `logo.png` y `logo_sfa_maestro.png` a una variante WebP/AVIF con transparencia,
  conservando PNG como fallback si la comparacion visual lo exige.
- [ ] Mantener dimensiones intrinsecas o atributos `width`/`height` para evitar CLS.
- [ ] Marcar solo la imagen que sea LCP real con `fetchPriority="high"`; no priorizar ambas a ciegas.
- [ ] Mantener fotos y escudos fuera del primer elemento como lazy/async.
- [ ] Revisar duplicacion DOM desktop/mobile de fotos del podio sin cambiar composicion.
- [ ] Medir local hosting de fuentes contra Google Fonts; aceptar el cambio solo si mejora LCP/privacidad
  sin aumentar bytes criticos.
- [ ] Generar coverage CSS por ruta.
- [ ] Si mas del 60% del CSS global no se usa en `/ranking`, proponer una segunda entrega que extraiga
  estilos de pagina respetando orden de cascada; no mezclarla con el bootstrap.

## Fase 5 - API y repositorio despues de P0-P2

- [ ] Repetir tiempos de `get_active_version`, `resolve_scope`, ranking rows y ranking total por separado.
- [ ] No optimizar consultas por debajo de 20 ms sin evidencia de contencion o volumen.
- [ ] Si `_get_scopes` es significativo, introducir cache corta en un adaptador/read repository y
  conectar por DI sin importar Redis desde application.
- [ ] Si el total sigue siendo significativo, evaluar `count(*) over()` o un resultado agregado unico,
  comparando planes y preservando pagination DTO.
- [ ] Considerar Redis para ranking solo si el P95 sigue fuera del presupuesto despues de las fases previas.
- [ ] Si se justifica Redis, definir clave con scope/season, rules version, filtros, page, limit, offset y
  `use_total`, TTL e invalidacion posterior a recalculo antes de implementar.

## Verificacion funcional

- [ ] Comparar JSON del ranking antes/despues para scope implicito y explicito.
- [ ] Confirmar mismos ids, ranks, puntos, equipos, posiciones, total y paginacion.
- [ ] Confirmar que seleccionar Total historico, Mundial, temporada, posicion, perfil y competicion funciona.
- [ ] Confirmar que buscador, filtros y paginacion conservan foco y resultados durante refresh.
- [ ] Confirmar que explicaciones corresponden exactamente a los tres jugadores visibles.
- [ ] Confirmar que no cambian textos, estructura ni jerarquia visual.

## Verificacion de rendimiento

- [ ] Ejecutar cinco runs frios y cinco calientes con el mismo perfil del baseline.
- [ ] Comparar medianas y P75, no el mejor run.
- [ ] Confirmar ranking visible < 1.5 s P50 y < 2.5 s P75 en Fast 4G.
- [ ] Confirmar `GET /ranking` < 500 ms P50 y < 800 ms P95 caliente en produccion.
- [ ] Confirmar que `/ranking` comienza antes de finalizar `/seasons`.
- [ ] Confirmar ausencia de request duplicada al canonizar scope.
- [ ] Confirmar una request en vuelo por URL y una sola instancia de polling.
- [ ] Confirmar CLS < 0.1.
- [ ] Confirmar reduccion de bytes del primer viewport y documentar porcentaje.

## Gates de calidad

- [ ] Ejecutar tests enfocados de ranking, seasons y cache HTTP.
- [ ] Ejecutar `pytest tests/` y confirmar coverage global >= 80%.
- [ ] Ejecutar `flake8 src/ tests/` sin errores nuevos.
- [ ] Ejecutar `isort --check-only src/ tests/` sin errores nuevos.
- [ ] Ejecutar `npm run build` sin errores TypeScript.
- [ ] Ejecutar Playwright desktop y mobile con screenshots y trace.
- [ ] Revisar `git diff --check`.

## Agent Routing Brief

**DDD Designer needed:** no

No se agregan conceptos de negocio. Scope, ranking y reglas versionadas ya existen. Los cambios
futuros son orquestacion de lectura, adaptadores HTTP, cache de transporte y entrega estatica,
manteniendo los ports y DTOs actuales.

