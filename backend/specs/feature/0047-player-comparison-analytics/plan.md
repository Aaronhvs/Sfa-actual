# Plan: Comparador analitico de jugadores

## Archivos a crear

- [x] `specs/feature/0047-player-comparison-analytics/decisions.md` - decisiones arquitectonicas.
- [x] `specs/feature/0047-player-comparison-analytics/plan.md` - contrato de implementacion.
- [x] `../frontend/src/components/compare/PlayerPicker.tsx` - busqueda y seleccion accesible.
- [x] `../frontend/src/components/compare/ComparisonRows.tsx` - secciones y filas comparativas.
- [x] `../frontend/src/components/compare/MomentumChart.tsx` - grafica espejo por minuto.

## Archivos a modificar

- [x] `src/sfa/application/use_cases/compare_players.py` - orquestar detalle, stats, eventos y partidos.
- [x] `src/sfa/application/use_cases/get_player_events.py` - completar firma del protocolo con scope.
- [x] `src/sfa/application/use_cases/get_player_fixtures.py` - completar firma del protocolo con scope.
- [x] `src/sfa/application/use_cases/get_player_season_stats.py` - completar firma del protocolo con scope.
- [x] `src/sfa/api/v1/schemas/compare.py` - analytics aditivos por jugador.
- [x] `src/sfa/api/v1/compare.py` - aceptar scope y serializar analytics.
- [x] `src/sfa/core/dependencies.py` - construir el comparador con use cases existentes.
- [x] `tests/use_cases/test_compare_players.py` - cubrir analytics, scope y errores.
- [x] `../frontend/src/types/index.ts` - tipar analytics y rating promedio.
- [x] `../frontend/src/api/client.ts` - consumir el contrato unificado con scope.
- [x] `../frontend/src/pages/ComparePage.tsx` - activar y componer el comparador.
- [x] `../frontend/src/components/layout/Navbar.tsx` - retirar estado en construccion.
- [x] `../frontend/src/index.css` - layout, grafica, responsive y estados accesibles.

## Checklist de implementacion

- [x] Leer arquitectura, agente Architecture Engineer y skill SFA Spec.
- [x] Cargar PRODUCT.md, DESIGN.md, Impeccable y UI UX Pro Max.
- [x] Registrar baseline: 4 pruebas de compare y build frontend aprobados.
- [x] Mantener `player_a` y `player_b` backward compatible.
- [x] Agregar analytics completos para ambos jugadores.
- [x] Rechazar `season` y `scope` simultaneos.
- [x] Resolver stats, eventos y fixtures con el mismo scope.
- [x] Evitar breakdown de fixtures en el comparador.
- [x] Consumir el endpoint en una sola llamada desde React.
- [x] Agregar selector de temporada/scope y habilitar navegacion.
- [x] Mostrar volumen, por 90, eficiencia, contexto, defensa y disciplina.
- [x] Implementar grafica por tramos de cinco minutos con teclado y leyenda textual.
- [x] Implementar loading, error, seleccion parcial y estado inicial.
- [x] Verificar viewport movil, tablet y desktop con Playwright.
- [x] Ejecutar una critica visual y corregir defectos encontrados.
- [x] Ejecutar pruebas enfocadas y suite backend completa.
- [x] Ejecutar `flake8`, `isort --check-only`, `git diff --check` y `npm run build`.

## Agent Routing Brief

**DDD Designer needed:** no

La feature compone consultas existentes y calcula metricas de lectura sin agregar invariantes,
entidades persistentes ni multiplicadores al dominio de scoring.

## Verificacion

1. Abrir `/compare` y seleccionar dos jugadores de `season-2025`.
2. Confirmar que una sola llamada `/api/v1/compare` devuelve detalles y analytics.
3. Comparar precision, conversion, pase, regates, duelos, defensa y disciplina.
4. Confirmar que la grafica distingue 0-45 y 46-90+ sin incluir eventos `stats`.
5. Cambiar a Mundial y confirmar que los dos jugadores y datos respetan el scope.

## Resultado de verificacion

- `6 passed` en pruebas enfocadas del comparador.
- `478 passed` en la suite backend completa con `DEBUG=false`.
- `flake8` e `isort --check-only` aprobados.
- Build de produccion Vite aprobado.
- Playwright aprobado en 390x844, 768x1024 y 1440x1000, sin overflow horizontal.
- Grafica auditada con hover y foco de teclado por tramo.

## Follow-up visual

- [x] Centrar titulo, periodo, selectores y cabecera de la grafica.
- [x] Rehacer los resultados de busqueda como filas del ranking movil.
- [x] Mantener nombre, equipo, puntos, goles y asistencias legibles.
- [x] Agregar navegacion por teclado al listado de jugadores.
- [x] Separar filtros y resultados del ranking en viewport movil.
